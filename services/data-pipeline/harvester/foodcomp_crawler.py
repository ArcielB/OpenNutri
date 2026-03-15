"""
Food Composition Crawler - High precision PMC harvester.

Pipeline:
1) Search PMC with strict food composition queries
2) Fetch summaries
3) High-precision abstract filter
4) Download XML and validate tables
5) Download PDFs for validated papers
"""

import argparse
import csv
import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent dir to path so 'crawler' package is importable
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from crawler.harvester.client import PMCClient
from crawler.harvester.query_builder import QueryBuilder
from crawler.harvester.foodcomp_filter import FoodCompositionFilter
from crawler.harvester.pdf_downloader import PDFDownloader
from crawler.processing.content import extract_metadata
from crawler.processing.validator import TableValidator


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SR_FOOD_CSV = REPO_ROOT / "FoodData_Central_sr_legacy_food_csv_2018-04" / "food.csv"


def load_foods_from_csv(csv_path: Path, max_foods: int = None, shuffle: bool = False, seed: int = 13) -> List[str]:
    if not csv_path.exists():
        return []

    foods: List[str] = []
    seen = set()

    # Basic brand and non-food filters
    skip_tokens = {
        "inc", "ltd", "llc", "company", "co", "corporation", "brand",
        "restaurant", "cafe", "market", "store",
    }

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            desc = (row.get("description") or "").strip()
            if not desc:
                continue

            base = re.split(r"[,-]", desc)[0].strip()
            base = re.sub(r"\s+", " ", base)
            base = base.title()

            # Filters
            if len(base) < 3:
                continue
            if any(ch.isdigit() for ch in base):
                continue
            words = base.split()
            if len(words) > 3:
                continue
            if any(w.lower() in skip_tokens for w in words):
                continue

            key = base.lower()
            if key in seen:
                continue
            seen.add(key)
            foods.append(base)

    if shuffle:
        random.Random(seed).shuffle(foods)

    if max_foods is not None:
        foods = foods[:max_foods]

    return foods


def load_foods_from_list(list_path: Path) -> List[str]:
    if not list_path.exists():
        return []
    foods = []
    with open(list_path, "r", encoding="utf-8") as f:
        for line in f:
            name = line.strip()
            if name:
                foods.append(name)
    return foods


class FoodCompositionCrawler:
    def __init__(
        self,
        email: str,
        data_dir: Path,
        max_candidates: int = 40,
        min_score: float = 4.0,
        require_food_term: bool = True,
        request_delay: float = 0.5,
    ):
        self.email = email
        self.client = PMCClient(email)
        self.filter = FoodCompositionFilter(threshold=min_score, require_food_term=require_food_term)
        self.downloader = PDFDownloader(email, request_delay=request_delay)

        self.data_dir = data_dir
        self.xml_dir = self.data_dir / "xml"
        self.pdf_dir = self.data_dir / "pdfs"
        self.xml_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)

        self.state_path = self.data_dir / "state.json"
        self.state = self._load_state()

        self.max_candidates = max_candidates

    def _load_state(self) -> Dict:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "seen_ids": [],
            "downloaded_ids": [],
        }

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def _is_seen(self, pmc_id: str) -> bool:
        return pmc_id in set(self.state.get("seen_ids", []))

    def _mark_seen(self, pmc_id: str):
        if pmc_id not in self.state.get("seen_ids", []):
            self.state.setdefault("seen_ids", []).append(pmc_id)

    def _mark_downloaded(self, pmc_id: str):
        if pmc_id not in self.state.get("downloaded_ids", []):
            self.state.setdefault("downloaded_ids", []).append(pmc_id)

    def crawl_food(self, food: str, per_food_limit: int) -> List[Dict]:
        results: List[Dict] = []
        query = QueryBuilder.build_strict_food_query(food)

        print(f"\nFood: {food}")
        print(f"Query: {query[:120]}...")

        pmc_ids = self.client.search(query, max_results=self.max_candidates)
        if not pmc_ids:
            print("  No candidates found")
            return results

        print(f"  Candidates: {len(pmc_ids)}")

        summaries = self.client.fetch_summaries(pmc_ids)
        passed, filtered = self.filter.filter_batch(summaries, food_term=food)

        print(f"  Passed filter: {len(passed)} | Filtered: {len(filtered)}")

        downloaded = 0
        for paper in passed:
            if downloaded >= per_food_limit:
                break

            pmc_id = paper.get("pmc_id", "")
            if not pmc_id:
                continue

            if self._is_seen(pmc_id):
                continue

            title = paper.get("title", "")
            abstract = paper.get("abstract", "")
            score = paper.get("relevance_score", 0)
            reasons = paper.get("relevance_reasons", [])

            xml_content = self.client.fetch_xml(pmc_id)
            if not xml_content:
                results.append({
                    "pmc_id": pmc_id,
                    "food": food,
                    "status": "xml_failed",
                    "title": title,
                    "score": score,
                    "reasons": reasons,
                })
                self._mark_seen(pmc_id)
                continue

            # Validate tables
            is_valid, tables = TableValidator.validate_paper(xml_content)
            if not is_valid:
                results.append({
                    "pmc_id": pmc_id,
                    "food": food,
                    "status": "no_tables",
                    "title": title,
                    "score": score,
                    "reasons": reasons,
                })
                self._mark_seen(pmc_id)
                continue

            # Save XML
            xml_path = self.xml_dir / f"PMC{pmc_id}.xml"
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(xml_content)

            metadata = extract_metadata(xml_content)
            if not metadata.get("title"):
                metadata["title"] = title

            # Download PDF
            pdf_result = self.downloader.download_pdf(pmc_id, self.pdf_dir)

            result = {
                "pmc_id": pmc_id,
                "food": food,
                "status": "success" if pdf_result.get("status") == "success" else "pdf_failed",
                "title": metadata.get("title"),
                "journal": metadata.get("journal"),
                "score": score,
                "reasons": reasons,
                "tables_found": len(tables),
                "xml_file": str(xml_path),
                "pdf": pdf_result,
            }
            results.append(result)

            self._mark_seen(pmc_id)
            if pdf_result.get("status") == "success":
                self._mark_downloaded(pmc_id)
                downloaded += 1

            time.sleep(0.3)

        self._save_state()
        return results

    def crawl(self, foods: List[str], per_food_limit: int) -> List[Dict]:
        all_results: List[Dict] = []
        for food in foods:
            results = self.crawl_food(food, per_food_limit=per_food_limit)
            all_results.extend(results)
        return all_results


def main():
    parser = argparse.ArgumentParser(description="High-precision food composition crawler")
    parser.add_argument("--email", required=True, help="Email for NCBI Entrez API")
    parser.add_argument("--data-dir", default="data/foodcomp", help="Output data directory")
    parser.add_argument("--foods", default="", help="Comma-separated list of foods")
    parser.add_argument("--foods-file", default="", help="File with one food per line")
    parser.add_argument("--max-foods", type=int, default=8, help="Max foods to process")
    parser.add_argument("--per-food", type=int, default=2, help="PDFs to download per food")
    parser.add_argument("--max-candidates", type=int, default=40, help="Max PMC IDs per food query")
    parser.add_argument("--min-score", type=float, default=4.0, help="Minimum relevance score")
    parser.add_argument("--no-food-term-check", action="store_true", help="Disable food term requirement")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle food list")
    parser.add_argument("--seed", type=int, default=13, help="Shuffle seed")

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    foods: List[str] = []

    if args.foods:
        foods = [f.strip() for f in args.foods.split(",") if f.strip()]
    elif args.foods_file:
        foods = load_foods_from_list(Path(args.foods_file))
    else:
        foods = load_foods_from_csv(DEFAULT_SR_FOOD_CSV, max_foods=args.max_foods, shuffle=args.shuffle, seed=args.seed)

    if not foods:
        print("No foods found. Provide --foods or --foods-file, or ensure SR legacy CSV exists.")
        return

    if args.max_foods and len(foods) > args.max_foods:
        foods = foods[:args.max_foods]

    print("Food Composition Crawler")
    print("=" * 60)
    print(f"Foods: {len(foods)} | Per food: {args.per_food} | Max candidates: {args.max_candidates}")

    crawler = FoodCompositionCrawler(
        email=args.email,
        data_dir=data_dir,
        max_candidates=args.max_candidates,
        min_score=args.min_score,
        require_food_term=not args.no_food_term_check,
    )

    results = crawler.crawl(foods, per_food_limit=args.per_food)

    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = data_dir / f"run_{run_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "run_id": run_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "foods": foods,
            "results": results,
        }, f, indent=2)

    # Summary
    total = len(results)
    successes = sum(1 for r in results if r.get("status") == "success")
    pdf_failed = sum(1 for r in results if r.get("status") == "pdf_failed")
    no_tables = sum(1 for r in results if r.get("status") == "no_tables")

    print("\nSummary")
    print("=" * 60)
    print(f"Total results: {total}")
    print(f"Success (PDF downloaded): {successes}")
    print(f"PDF failed: {pdf_failed}")
    print(f"Rejected (no tables): {no_tables}")
    print(f"Run file: {out_path}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import re
import shutil
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .europe_pmc import EuropePMCClient
from .models import CandidatePaper, DownloadRecord
from .ranking import score_candidate, validate_pdf_text
from .supabase_terms import fetch_food_terms, fetch_nutrient_terms


COMPOSITION_HINTS = [
    "food composition",
    "composition table",
    "food composition table",
    "nutrient composition",
    "nutritional composition",
    "chemical composition",
    "proximate composition",
    "proximate analysis",
    "mineral content",
    "vitamin content",
    "fatty acid composition",
    "amino acid composition",
]

NUTRIENT_HINTS = [
    "moisture",
    "protein",
    "fat",
    "lipid",
    "ash",
    "fiber",
    "fibre",
    "carbohydrate",
    "energy",
    "mineral",
    "vitamin",
]

HEALTH_OUTCOME_TERMS = [
    "diet",
    "dietary",
    "intake",
    "intervention",
    "clinical",
    "patients",
    "dietary intake",
    "dietary assessment",
    "diet quality",
    "diet pattern",
    "dietary intervention",
    "randomized",
    "trial",
    "cohort",
    "case-control",
    "odds ratio",
    "hazard ratio",
    "mortality",
    "disease",
    "diabetes",
    "obesity",
    "cardiovascular",
    "hypertension",
    "cancer",
    "cholesterol",
    "insulin",
]


class FoodCompositionCrawlerV2:
    def __init__(
        self,
        data_dir: str,
        supabase_url: str,
        supabase_key: str,
        target_pdfs: int = 12,
        query_limit: int = 40,
        food_term_limit: int = 60,
        max_queries: int = 80,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.raw_pdf_dir = self.data_dir / "raw_pdfs"
        self.state_path = self.data_dir / "crawl_state.json"
        self.manifest_path = self.raw_pdf_dir / "_harvest_metadata.json"
        self.client = EuropePMCClient(page_size=query_limit)
        self.target_pdfs = target_pdfs
        self.query_limit = query_limit
        self.food_terms = fetch_food_terms(supabase_url, supabase_key, limit=food_term_limit)
        self.nutrient_terms = fetch_nutrient_terms(supabase_url, supabase_key, limit=max(20, food_term_limit // 2))
        self.max_queries = max_queries
        self.state = self._load_state()

    def run(self, replace_existing: bool = False) -> Dict[str, object]:
        if replace_existing and self.raw_pdf_dir.exists():
            shutil.rmtree(self.raw_pdf_dir)
        if replace_existing:
            self.state = {"seen_ids": []}
        self.raw_pdf_dir.mkdir(parents=True, exist_ok=True)

        accepted_records: List[DownloadRecord] = []
        rejected_records: List[DownloadRecord] = []
        seen_ids: Set[str] = set(self.state.get("seen_ids", []))
        candidates_by_id: Dict[str, CandidatePaper] = {}
        query_stats: Dict[str, Dict[str, int]] = {}

        queries = self._build_queries()
        queries = queries[: max(12, min(self.max_queries, self.target_pdfs * 8))]

        for query in queries:
            candidates = self.client.search(query, limit=self.query_limit)
            query_stats[query] = {"results": len(candidates)}
            if not candidates:
                continue
            for candidate in candidates:
                canonical_id = candidate.canonical_id
                if not canonical_id or canonical_id in seen_ids:
                    continue
                score, accepted, reasons = score_candidate(candidate, self.food_terms, self.nutrient_terms)
                if not self._composition_focus(candidate):
                    accepted = False
                    reasons = reasons + ["composition focus not detected"]
                if self._health_outcome_focus(candidate):
                    accepted = False
                    reasons = reasons + ["health outcome focus"]
                candidate.score = score
                candidate.accepted = accepted
                candidate.reasons = reasons
                seen_ids.add(canonical_id)
                candidates_by_id[canonical_id] = candidate

        if not candidates_by_id:
            for query in self._fallback_queries()[:10]:
                candidates = self.client.search(query, limit=self.query_limit)
                query_stats[query] = {"results": len(candidates)}
                if not candidates:
                    continue
                for candidate in candidates:
                    canonical_id = candidate.canonical_id
                    if not canonical_id or canonical_id in seen_ids:
                        continue
                    score, accepted, reasons = score_candidate(candidate, self.food_terms, self.nutrient_terms)
                    if not self._composition_focus(candidate):
                        accepted = False
                        reasons = reasons + ["composition focus not detected"]
                    if self._health_outcome_focus(candidate):
                        accepted = False
                        reasons = reasons + ["health outcome focus"]
                    candidate.score = score
                    candidate.accepted = accepted
                    candidate.reasons = reasons
                    seen_ids.add(canonical_id)
                    candidates_by_id[canonical_id] = candidate

        ranked_candidates = sorted(
            candidates_by_id.values(),
            key=lambda item: (item.accepted, item.score, item.year or ""),
            reverse=True,
        )

        attempt_cap = max(self.target_pdfs * 4, 20)
        attempts = 0
        for candidate in ranked_candidates:
            if len(accepted_records) >= self.target_pdfs:
                break
            if attempts >= attempt_cap:
                break
            attempts += 1

            if not candidate.accepted:
                rejected_records.append(self._skip_record(candidate, "Rejected by metadata ranking"))
                continue

            record = self._download_candidate(candidate)
            if record.status == "success":
                accepted_records.append(record)
            else:
                rejected_records.append(record)

        manifest = {
            "harvested_at": datetime.now(timezone.utc).isoformat(),
            "query_count": len(queries),
            "target_pdfs": self.target_pdfs,
            "accepted_count": len(accepted_records),
            "rejected_count": len(rejected_records),
            "food_term_sample": self.food_terms[:20],
            "nutrient_term_sample": self.nutrient_terms[:20],
            "query_stats": query_stats,
            "results": [record.to_dict() for record in accepted_records + rejected_records],
        }
        self._write_json(self.manifest_path, manifest)
        self.state["seen_ids"] = sorted(seen_ids)
        self._save_state()
        return manifest

    def _build_queries(self) -> List[str]:
        core = (
            '"food composition" OR "proximate composition" OR "nutrient composition" OR '
            '"chemical composition" OR "proximate analysis" OR "food composition table"'
        )
        secondary = (
            '"mineral content" OR "vitamin content" OR "fatty acid composition" OR '
            '"amino acid composition"'
        )
        queries = [
            f'({core}) AND IN_PMC:y',
            f'({core} OR {secondary}) AND IN_PMC:y',
            '("proximate analysis" OR "proximate composition") AND IN_PMC:y',
            '("nutrient composition" OR "mineral content" OR "vitamin content") AND IN_PMC:y',
            '("food composition" AND "table") AND IN_PMC:y',
        ]

        food_anchor = '("food composition" OR "proximate composition" OR "nutrient composition" OR "chemical composition")'
        for food in self.food_terms[: max(10, min(40, len(self.food_terms)))]:
            queries.append(f'("{food}" AND {food_anchor}) AND IN_PMC:y')

        return self._dedupe(queries)

    def _fallback_queries(self) -> List[str]:
        return self._dedupe(
            [
                '"food composition"',
                '"proximate composition"',
                '"nutrient composition"',
                '"chemical composition"',
                '"food composition table"',
                '"proximate analysis"',
            ]
        )

    def _dedupe(self, queries: List[str]) -> List[str]:
        seen: Set[str] = set()
        ordered: List[str] = []
        for query in queries:
            key = re.sub(r"\s+", " ", query.strip())
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(key)
        return ordered

    def _composition_focus(self, candidate: CandidatePaper) -> bool:
        title = self._normalize_text(candidate.title)
        abstract = self._normalize_text(candidate.abstract)
        text = f"{title} {abstract}".strip()
        if self._contains_any(title, COMPOSITION_HINTS):
            return True
        if self._contains_any(text, COMPOSITION_HINTS) and self._contains_any(text, NUTRIENT_HINTS):
            return True
        return False

    def _health_outcome_focus(self, candidate: CandidatePaper) -> bool:
        title = self._normalize_text(candidate.title)
        if self._contains_any(title, COMPOSITION_HINTS):
            return False
        text = self._normalize_text(f"{candidate.title} {candidate.abstract}")
        return self._contains_any(text, HEALTH_OUTCOME_TERMS)

    def _contains_any(self, text: str, terms: List[str]) -> bool:
        return any(term in text for term in terms)

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").lower()).strip()

    def _download_candidate(self, candidate: CandidatePaper) -> DownloadRecord:
        if not candidate.pdf_url:
            return self._failed_record(candidate, "No PDF URL available")

        try:
            content = self._fetch_pdf(candidate.pdf_url)
        except Exception as exc:
            return self._failed_record(candidate, str(exc))

        file_name = self._build_filename(candidate)
        destination = self.raw_pdf_dir / file_name
        destination.write_bytes(content)
        pdf_score, accepted, pdf_reasons = self._validate_downloaded_pdf(destination, candidate)
        combined_reasons = candidate.reasons + pdf_reasons
        if not accepted:
            destination.unlink(missing_ok=True)
            candidate.reasons = combined_reasons
            candidate.score = round(candidate.score + pdf_score, 2)
            return self._failed_record(candidate, "Rejected by PDF validation")

        candidate.reasons = combined_reasons
        candidate.score = round(candidate.score + pdf_score, 2)
        return DownloadRecord(
            status="success",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=combined_reasons,
            file=str(destination.relative_to(self.data_dir.parent)),
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            size_kb=max(1, round(len(content) / 1024)),
            pdf_url=candidate.pdf_url,
        )

    def _fetch_pdf(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "OpenNutriCompositionCrawler/2.0"})
        try:
            with urlopen(request, timeout=20) as response:
                content_type = response.headers.get("Content-Type", "")
                final_url = response.geturl()
                payload = response.read()
        except HTTPError as exc:
            payload = self._fetch_pdf_with_curl(url)
            if payload.startswith(b"%PDF"):
                return payload
            raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
        except URLError as exc:
            payload = self._fetch_pdf_with_curl(url)
            if payload.startswith(b"%PDF"):
                return payload
            raise RuntimeError(f"URL error for {url}: {exc.reason}") from exc

        if payload.startswith(b"%PDF"):
            return payload

        if "html" in content_type.lower():
            html = payload.decode("utf-8", errors="ignore")
            pow_payload = self._solve_pmc_pow(html)
            if pow_payload:
                pow_request = Request(
                    final_url,
                    headers={
                        "User-Agent": "OpenNutriCompositionCrawler/2.0",
                        "Cookie": pow_payload,
                    },
                )
                try:
                    with urlopen(pow_request, timeout=20) as pow_response:
                        pow_bytes = pow_response.read()
                except (HTTPError, URLError) as exc:
                    raise RuntimeError(f"Failed POW retry for {final_url}: {exc}") from exc
                if pow_bytes.startswith(b"%PDF"):
                    return pow_bytes
            pdf_match = re.search(r'href=["\']([^"\']+\\.pdf[^"\']*)["\']', html, re.IGNORECASE)
            if pdf_match:
                nested_url = urljoin(final_url, pdf_match.group(1))
                nested_request = Request(nested_url, headers={"User-Agent": "OpenNutriCompositionCrawler/2.0"})
                try:
                    with urlopen(nested_request, timeout=20) as nested_response:
                        nested_payload = nested_response.read()
                except (HTTPError, URLError) as exc:
                    raise RuntimeError(f"Failed nested PDF fetch for {nested_url}: {exc}") from exc
                if nested_payload.startswith(b"%PDF"):
                    return nested_payload

            curl_payload = self._fetch_pdf_with_curl(url)
            if curl_payload.startswith(b"%PDF"):
                return curl_payload

        snippet = payload[:120].decode("utf-8", errors="ignore")
        if "pdf" not in content_type.lower():
            raise RuntimeError(f"Not a PDF ({content_type or 'unknown'}): {snippet[:80]}")
        return payload

    def _fetch_pdf_with_curl(self, url: str) -> bytes:
        try:
            return subprocess.check_output(
                [
                    "curl",
                    "-L",
                    "--silent",
                    "--show-error",
                    "-A",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    url,
                ],
                stderr=subprocess.DEVNULL,
                timeout=40,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return b""

    def _validate_downloaded_pdf(self, path: Path, candidate: CandidatePaper) -> Tuple[float, bool, List[str]]:
        try:
            text = subprocess.check_output(
                ["pdftotext", str(path), "-"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=20,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return 0.0, False, [f"pdf text extraction failed: {exc}"]

        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 200:
            return 0.0, False, ["pdf text too short to validate"]
        return validate_pdf_text(text, candidate, self.food_terms, self.nutrient_terms)

    def _solve_pmc_pow(self, html: str) -> Optional[str]:
        challenge_match = re.search(r'POW_CHALLENGE = "([^"]+)"', html)
        difficulty_match = re.search(r'POW_DIFFICULTY = "([^"]+)"', html)
        cookie_match = re.search(r'POW_COOKIE_NAME = "([^"]+)"', html)
        if not challenge_match or not difficulty_match or not cookie_match:
            return None

        challenge = challenge_match.group(1)
        difficulty = int(difficulty_match.group(1))
        cookie_name = cookie_match.group(1)
        prefix = "0" * difficulty
        nonce = 0
        while True:
            digest = hashlib.md5(f"{challenge}{nonce}".encode("utf-8")).hexdigest()
            if digest.startswith(prefix):
                return f"{cookie_name}={challenge},{nonce}"
            nonce += 1

    def _build_filename(self, candidate: CandidatePaper) -> str:
        if candidate.pmcid:
            return f"{candidate.pmcid}.pdf"
        stem = candidate.title.lower()
        stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
        stem = stem[:80] or "paper"
        return f"{stem}.pdf"

    def _skip_record(self, candidate: CandidatePaper, error: str) -> DownloadRecord:
        return DownloadRecord(
            status="skipped",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=candidate.reasons,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            pdf_url=candidate.pdf_url,
            error=error,
        )

    def _failed_record(self, candidate: CandidatePaper, error: str) -> DownloadRecord:
        return DownloadRecord(
            status="failed",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=candidate.reasons,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            pdf_url=candidate.pdf_url,
            error=error,
        )

    def _load_state(self) -> Dict[str, object]:
        if not self.state_path.exists():
            return {"seen_ids": []}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"seen_ids": []}

    def _save_state(self) -> None:
        self._write_json(self.state_path, self.state)

    def _write_json(self, path: Path, payload: Dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

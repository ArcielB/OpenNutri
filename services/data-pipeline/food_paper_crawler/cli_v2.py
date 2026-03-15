from __future__ import annotations

import argparse
import json
import os

from .crawler_v2 import FoodCompositionCrawlerV2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenNutri food composition crawler v2")
    parser.add_argument("--data-dir", default="data", help="Crawler data directory")
    parser.add_argument("--target-pdfs", type=int, default=12, help="How many PDFs to keep")
    parser.add_argument("--query-limit", type=int, default=40, help="Results to inspect per query")
    parser.add_argument("--food-term-limit", type=int, default=60, help="How many food terms to use")
    parser.add_argument("--max-queries", type=int, default=80, help="Cap on query count")
    parser.add_argument("--replace-existing", action="store_true", help="Delete previous harvested PDFs first")
    return parser


def run_cli() -> int:
    parser = build_parser()
    args = parser.parse_args()

    from config import SUPABASE_KEY, SUPABASE_URL

    crawler = FoodCompositionCrawlerV2(
        data_dir=args.data_dir,
        supabase_url=os.environ.get("SUPABASE_URL", SUPABASE_URL),
        supabase_key=os.environ.get("SUPABASE_KEY", SUPABASE_KEY),
        target_pdfs=args.target_pdfs,
        query_limit=args.query_limit,
        food_term_limit=args.food_term_limit,
        max_queries=args.max_queries,
    )
    manifest = crawler.run(replace_existing=args.replace_existing)
    print(json.dumps(
        {
            "accepted_count": manifest["accepted_count"],
            "rejected_count": manifest["rejected_count"],
            "manifest": os.path.join(args.data_dir, "raw_pdfs", "_harvest_metadata.json"),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())

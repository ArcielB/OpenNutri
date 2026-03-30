from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from food_paper_crawler.dergipark_source import DergiParkOAISource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh the local DergiPark journal/article index.")
    parser.add_argument("--data-dir", default="services/data-pipeline/data", help="Crawler data directory")
    parser.add_argument("--journal-limit", type=int, default=0, help="Limit how many configured DergiPark journals are refreshed (0 = all)")
    parser.add_argument("--max-issues-per-journal", type=int, default=12, help="How many newest archive issues to inspect for each journal")
    parser.add_argument("--force", action="store_true", help="Re-fetch already indexed article pages")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    source = DergiParkOAISource(
        data_dir=Path(args.data_dir),
        max_issues_per_journal=args.max_issues_per_journal,
    )
    report = source.refresh_index(
        journal_limit=args.journal_limit,
        max_issues_per_journal=args.max_issues_per_journal,
        force=args.force,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

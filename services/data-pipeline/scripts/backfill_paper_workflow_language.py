from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

from supabase import Client, create_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from food_paper_crawler.language_utils import detect_supported_language


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill papers.workflow_language for legacy rows where it is currently NULL."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview inferred languages without writing updates.",
    )
    return parser


def require_client() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY.")
    return create_client(supabase_url, supabase_key)


def fetch_null_language_papers(client: Client, batch_size: int = 500) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        response = (
            client.table("papers")
            .select("id,title,abstract,workflow_language")
            .is_("workflow_language", "null")
            .order("id")
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < batch_size:
            return rows
        offset += batch_size


def infer_language(row: dict) -> str:
    text = " ".join(
        part.strip()
        for part in (row.get("title"), row.get("abstract"))
        if isinstance(part, str) and part.strip()
    )
    return detect_supported_language(text, default="en")


def main() -> None:
    args = build_parser().parse_args()
    client = require_client()

    before_rows = fetch_null_language_papers(client)
    before_count = len(before_rows)
    print(f"Before backfill: papers.workflow_language IS NULL = {before_count}")

    if before_count == 0:
        print("No NULL workflow_language rows found.")
        print("After backfill: papers.workflow_language IS NULL = 0")
        return

    planned_updates = [
        {
            "id": row["id"],
            "workflow_language": infer_language(row),
            "title": (row.get("title") or "").strip(),
        }
        for row in before_rows
    ]

    language_counts = Counter(row["workflow_language"] for row in planned_updates)
    print(
        "Planned language inference:",
        ", ".join(
            f"{language.upper()}={language_counts.get(language, 0)}"
            for language in ("en", "tr")
        ),
    )
    for row in planned_updates[:20]:
        title = row["title"] or f"Paper {row['id']}"
        print(f"  paper_id={row['id']} -> {row['workflow_language']} :: {title[:120]}")
    if len(planned_updates) > 20:
        print(f"  ... {len(planned_updates) - 20} more rows omitted")

    if not args.dry_run:
        for row in planned_updates:
            (
                client.table("papers")
                .update({"workflow_language": row["workflow_language"]})
                .eq("id", row["id"])
                .is_("workflow_language", "null")
                .execute()
            )

    after_count = len(fetch_null_language_papers(client))
    print(
        f"After backfill{' (dry-run)' if args.dry_run else ''}: "
        f"papers.workflow_language IS NULL = {after_count}"
    )


if __name__ == "__main__":
    main()

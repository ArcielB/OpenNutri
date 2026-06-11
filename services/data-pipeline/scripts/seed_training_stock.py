from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict

import httpx
from supabase import Client, create_client


SUPPORTED_LANGUAGES = ("en", "tr")
LIVE_SLOT_STATUSES = {"pending", "submitted", "conflict"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect the bilingual paper pool that feeds read-only developer training queues."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="How many queue rows to preview after summarizing the pool.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Accepted for ops consistency. This script is always read-only.",
    )
    return parser


def require_client() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY.")
    return create_client(supabase_url, supabase_key)


def fetch_all(
    client: Client,
    table: str,
    select: str,
    batch_size: int = 1000,
    max_attempts: int = 4,
) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        # Retry transient PostgREST disconnects; each page is an idempotent read.
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.table(table).select(select).range(offset, offset + batch_size - 1).execute()
                break
            except httpx.HTTPError as exc:
                if attempt >= max_attempts:
                    raise
                wait_seconds = 2 ** attempt
                print(
                    f"[fetch_all] transient error reading {table} offset={offset} "
                    f"(attempt {attempt}/{max_attempts}): {type(exc).__name__}: {exc}; retrying in {wait_seconds}s",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < batch_size:
            return rows
        offset += batch_size


def normalize_language(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in SUPPORTED_LANGUAGES else None


def group_rows_by_paper_id(rows: list[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        paper_id = row.get("paper_id")
        if isinstance(paper_id, int):
            grouped[paper_id].append(row)
    return grouped


def interleave_rows(primary_rows: list[dict], secondary_rows: list[dict]) -> list[dict]:
    result: list[dict] = []
    max_length = max(len(primary_rows), len(secondary_rows))
    for index in range(max_length):
        if index < len(primary_rows):
            result.append(primary_rows[index])
        if index < len(secondary_rows):
            result.append(secondary_rows[index])
    return result


def pick_representative_slot(slot_assignments: list[dict]) -> dict | None:
    status_rank = {
        "conflict": 0,
        "submitted": 1,
        "pending": 2,
        "resolved": 3,
        "cancelled": 4,
    }
    ordered = sorted(slot_assignments, key=lambda row: str(row.get("slot_key") or ""))
    ordered = sorted(
        ordered,
        key=lambda row: str(row.get("assigned_at") or row.get("created_at") or ""),
        reverse=True,
    )
    ordered = sorted(
        ordered,
        key=lambda row: status_rank.get(str(row.get("status") or "").strip().lower(), 99),
    )
    return ordered[0] if ordered else None


def build_training_queue(papers: list[dict], slot_assignments: list[dict]) -> list[dict]:
    slot_assignments_by_paper_id = group_rows_by_paper_id(slot_assignments)
    ranked_rows: list[dict] = []

    for paper in papers:
        language = normalize_language(paper.get("workflow_language"))
        if not language:
            continue
        paper_slot_assignments = slot_assignments_by_paper_id.get(paper["id"], [])
        live_slot_assignments = [
            row
            for row in paper_slot_assignments
            if str(row.get("status") or "").strip().lower() in LIVE_SLOT_STATUSES
        ]
        representative_slot = pick_representative_slot(
            live_slot_assignments if live_slot_assignments else paper_slot_assignments
        )
        ranked_rows.append(
            {
                "paper_id": paper["id"],
                "paper_title": (paper.get("title") or paper.get("filename") or f"Paper {paper['id']}").strip(),
                "workflow_language": language,
                "source_kind": "live_slot" if live_slot_assignments else "paper_pool",
                "representative_slot_key": representative_slot.get("slot_key") if representative_slot else None,
                "representative_slot_status": representative_slot.get("status") if representative_slot else None,
                "sort_timestamp": (
                    representative_slot.get("assigned_at")
                    if representative_slot
                    else paper.get("created_at")
                )
                or "",
            }
        )

    live_en = sorted(
        [row for row in ranked_rows if row["source_kind"] == "live_slot" and row["workflow_language"] == "en"],
        key=lambda row: (row["sort_timestamp"], row["paper_id"]),
        reverse=True,
    )
    live_tr = sorted(
        [row for row in ranked_rows if row["source_kind"] == "live_slot" and row["workflow_language"] == "tr"],
        key=lambda row: (row["sort_timestamp"], row["paper_id"]),
        reverse=True,
    )
    backlog_en = sorted(
        [row for row in ranked_rows if row["source_kind"] == "paper_pool" and row["workflow_language"] == "en"],
        key=lambda row: (row["sort_timestamp"], row["paper_id"]),
        reverse=True,
    )
    backlog_tr = sorted(
        [row for row in ranked_rows if row["source_kind"] == "paper_pool" and row["workflow_language"] == "tr"],
        key=lambda row: (row["sort_timestamp"], row["paper_id"]),
        reverse=True,
    )

    return [
        *interleave_rows(live_en, live_tr),
        *interleave_rows(backlog_en, backlog_tr),
    ]


def main() -> None:
    args = build_parser().parse_args()
    client = require_client()
    papers = fetch_all(
        client,
        "papers",
        "id,title,filename,workflow_language,created_at",
    )
    slot_assignments = fetch_all(
        client,
        "paper_slot_assignments",
        "paper_id,slot_key,status,assigned_at,created_at",
    )

    queue = build_training_queue(papers, slot_assignments)
    bilingual_count = len(queue)
    live_count = sum(1 for row in queue if row["source_kind"] == "live_slot")
    pool_count = bilingual_count - live_count

    print("Developer training queue pool")
    if args.dry_run:
        print("  Dry run flag noted. This script is always read-only.")
    print(f"  Total bilingual papers: {bilingual_count}")
    print(f"  Live-slot priority papers: {live_count}")
    print(f"  Paper-pool backlog papers: {pool_count}")
    for language in SUPPORTED_LANGUAGES:
        language_rows = [row for row in queue if row["workflow_language"] == language]
        language_live = sum(1 for row in language_rows if row["source_kind"] == "live_slot")
        print(
            f"  {language.upper()}: total={len(language_rows)} "
            f"live_slot={language_live} paper_pool={len(language_rows) - language_live}"
        )

    preview = queue[: max(args.limit, 0)]
    if not preview:
        print("No bilingual papers found for the training queue.")
        return

    print(f"\nPreviewing first {len(preview)} queue rows:")
    for index, row in enumerate(preview, start=1):
        slot_suffix = ""
        if row["representative_slot_key"]:
            slot_suffix = (
                f" | slot={row['representative_slot_key']}"
                f" status={row['representative_slot_status'] or 'unknown'}"
            )
        print(
            f"  {index:02d}. paper_id={row['paper_id']} "
            f"lang={row['workflow_language'].upper()} "
            f"source={row['source_kind']}{slot_suffix} :: {row['paper_title'][:120]}"
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from supabase import create_client


DEFAULT_DELETE_STATUSES = {
    "ai_failed",
    "ai_finalized_no_usable_data",
    "ai_provisional_no_usable_data",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Delete stale paper PDFs from Supabase Storage.")
    parser.add_argument("--bucket", default="papers", help="Storage bucket to clean.")
    parser.add_argument(
        "--statuses",
        default=",".join(sorted(DEFAULT_DELETE_STATUSES)),
        help="Comma-separated paper.routing_status values whose PDFs can be deleted.",
    )
    parser.add_argument("--keep-orphans", action="store_true", help="Do not delete storage objects without a matching papers.filename row.")
    parser.add_argument("--batch-size", type=int, default=100, help="Storage delete batch size.")
    parser.add_argument("--apply", action="store_true", help="Actually delete files. Without this, only report candidates.")
    parser.add_argument("--json-summary", action="store_true", help="Print a machine-readable summary.")
    return parser


def require_client():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY.")
    return create_client(supabase_url, supabase_key)


def _fetch_all_rows(client: Any, table_name: str, select: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        response = client.table(table_name).select(select).range(offset, offset + 999).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000


def _list_storage_objects(client: Any, bucket_name: str) -> list[dict]:
    objects: list[dict] = []
    offset = 0
    limit = 1000
    bucket = client.storage.from_(bucket_name)
    while True:
        batch = bucket.list(path="", options={"limit": limit, "offset": offset}) or []
        objects.extend(batch)
        if len(batch) < limit:
            return objects
        offset += limit


def _object_size(storage_object: dict) -> int:
    metadata = storage_object.get("metadata")
    if not isinstance(metadata, dict):
        return 0
    try:
        return max(0, int(metadata.get("size") or 0))
    except (TypeError, ValueError):
        return 0


def _delete_batches(client: Any, bucket_name: str, names: list[str], *, batch_size: int) -> tuple[int, list[str]]:
    bucket = client.storage.from_(bucket_name)
    deleted = 0
    errors: list[str] = []
    batch_size = max(1, int(batch_size))
    for index in range(0, len(names), batch_size):
        batch = names[index:index + batch_size]
        try:
            response = bucket.remove(batch)
        except Exception as exc:
            errors.append(str(exc))
            continue
        data = getattr(response, "data", response)
        deleted += len(data) if isinstance(data, list) else len(batch)
    return deleted, errors


def run_cleanup(client: Any, args: argparse.Namespace) -> dict[str, Any]:
    delete_statuses = {
        status.strip()
        for status in str(args.statuses or "").split(",")
        if status.strip()
    }
    papers = _fetch_all_rows(client, "papers", "id,filename,routing_status")
    papers_by_filename = {
        str(row.get("filename") or "").strip(): row
        for row in papers
        if str(row.get("filename") or "").strip()
    }
    storage_objects = _list_storage_objects(client, args.bucket)

    candidates: list[dict[str, Any]] = []
    kept = 0
    kept_bytes = 0
    for storage_object in storage_objects:
        name = str(storage_object.get("name") or "").strip()
        if not name:
            continue
        size = _object_size(storage_object)
        paper = papers_by_filename.get(name)
        if paper is None:
            if args.keep_orphans:
                kept += 1
                kept_bytes += size
                continue
            candidates.append({"name": name, "reason": "orphan_storage_object", "size": size})
            continue
        routing_status = str(paper.get("routing_status") or "").strip()
        if routing_status in delete_statuses:
            candidates.append(
                {
                    "name": name,
                    "reason": f"routing_status:{routing_status}",
                    "paper_id": paper.get("id"),
                    "size": size,
                }
            )
        else:
            kept += 1
            kept_bytes += size

    candidate_names = [row["name"] for row in candidates]
    deleted = 0
    errors: list[str] = []
    if args.apply and candidate_names:
        deleted, errors = _delete_batches(
            client,
            args.bucket,
            candidate_names,
            batch_size=max(1, int(args.batch_size)),
        )

    by_reason: dict[str, dict[str, int]] = {}
    for row in candidates:
        reason = str(row["reason"])
        bucket = by_reason.setdefault(reason, {"objects": 0, "bytes": 0})
        bucket["objects"] += 1
        bucket["bytes"] += int(row.get("size") or 0)

    return {
        "bucket": args.bucket,
        "apply": bool(args.apply),
        "storage_objects_seen": len(storage_objects),
        "kept_objects": kept,
        "kept_bytes": kept_bytes,
        "candidate_objects": len(candidates),
        "candidate_bytes": sum(int(row.get("size") or 0) for row in candidates),
        "deleted_objects": deleted,
        "delete_errors": errors,
        "by_reason": dict(sorted(by_reason.items())),
    }


def main() -> None:
    args = build_parser().parse_args()
    summary = run_cleanup(require_client(), args)
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
        return
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

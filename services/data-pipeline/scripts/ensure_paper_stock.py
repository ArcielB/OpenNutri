from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _parse_content_range(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"/(\d+)$", value)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def fetch_count(
    supabase_url: str,
    supabase_key: str,
    table: str,
    filters: Dict[str, str] | None = None,
) -> int:
    endpoint = supabase_url.rstrip("/") + f"/rest/v1/{table}"
    params = {"select": "id", "limit": "1"}
    if filters:
        params.update(filters)
    request = Request(
        f"{endpoint}?{urlencode(params)}",
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Prefer": "count=exact",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
            content_range = response.headers.get("Content-Range")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to fetch {table} count: {exc}") from exc

    count = _parse_content_range(content_range)
    if count is not None:
        return count
    if isinstance(payload, list):
        return len(payload)
    return 0


def run_command(label: str, cmd: list[str], env: dict) -> None:
    print(f"\n== {label} ==")
    print(" ".join(cmd))
    result = subprocess.run(cmd, env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {result.returncode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure there are enough papers for the UI.")
    parser.add_argument("--threshold", type=int, default=0, help="Minimum available papers before crawling")
    parser.add_argument("--data-dir", default="services/data-pipeline/data", help="Crawler data directory")
    parser.add_argument("--target-pdfs", type=int, default=12, help="How many PDFs to keep per crawl")
    parser.add_argument("--query-limit", type=int, default=50, help="Results to inspect per query")
    parser.add_argument("--max-queries", type=int, default=80, help="Cap on query count")
    parser.add_argument("--dry-run", action="store_true", help="Only report counts")
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY for auto-crawl.")

    total_papers = fetch_count(supabase_url, supabase_key, "papers")
    global_skips = fetch_count(
        supabase_url,
        supabase_key,
        "paper_global_labels",
        filters={"label": "eq.definitely_no_data"},
    )
    available = max(total_papers - global_skips, 0)

    print(f"Papers total: {total_papers}")
    print(f"Global no-data labels: {global_skips}")
    print(f"Available for UI: {available}")
    print(f"Threshold: {args.threshold}")

    if args.dry_run:
        return

    if available > args.threshold:
        print("Threshold not reached. No crawl triggered.")
        return

    env = os.environ.copy()
    env["SUPABASE_URL"] = supabase_url
    env["SUPABASE_KEY"] = supabase_key
    env["SUPABASE_SERVICE_ROLE_KEY"] = supabase_key
    env["VITE_SUPABASE_URL"] = supabase_url

    run_command(
        "Crawler v2",
        [
            sys.executable,
            "services/data-pipeline/main.py",
            "--data-dir",
            args.data_dir,
            "--target-pdfs",
            str(args.target_pdfs),
            "--query-limit",
            str(args.query_limit),
            "--max-queries",
            str(args.max_queries),
        ],
        env,
    )

    run_command(
        "Upload to Supabase",
        [sys.executable, "services/data-pipeline/scripts/upload_to_supabase.py"],
        env,
    )


if __name__ == "__main__":
    main()

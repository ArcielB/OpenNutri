"""Backfill: re-host existing papers' PDFs on Cloudflare R2.

For each paper whose pdf_url still points at a publisher/aggregator host, this
downloads the PDF once, uploads it to R2 (free egress, immutable cache
headers), repoints papers.pdf_url at the R2 copy, and preserves the original
URL in papers.source_pdf_url. Rows already on R2 are skipped, so the script is
resumable and safe to re-run.

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY and the R2_* variables
documented in scripts/r2_storage.py.

Typical use:
    python3 services/data-pipeline/scripts/rehost_pdfs_to_r2.py --dry-run
    python3 services/data-pipeline/scripts/rehost_pdfs_to_r2.py
    python3 services/data-pipeline/scripts/rehost_pdfs_to_r2.py --all-statuses
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from food_paper_crawler.pmc_pow import solve_pmc_pow
from pdf_limits import max_paper_pdf_bytes
from scripts import r2_storage
from scripts.refill_assignment_queue import fetch_all, require_client

# Reviewer-facing rows first; --all-statuses covers the rest.
DEFAULT_STATUSES = ("human_review_ready", "queued_for_ai")
DOWNLOAD_TIMEOUT_SECONDS = 60
USER_AGENT = "Mozilla/5.0 (compatible; OpenNutriPDF/1.0)"
PMCID_PATTERN = re.compile(r"PMC\d+", re.IGNORECASE)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--statuses",
        default=",".join(DEFAULT_STATUSES),
        help="Comma-separated papers.routing_status values to re-host",
    )
    parser.add_argument("--all-statuses", action="store_true", help="Re-host every paper with a pdf_url")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N uploads (0 = no limit)")
    parser.add_argument("--sleep-seconds", type=float, default=0.5, help="Pause between downloads")
    parser.add_argument("--dry-run", action="store_true", help="Report what would happen without writing")
    parser.add_argument("--json-summary", action="store_true", help="Print a final JSON summary line")
    return parser


def _fetch(url: str, *, max_bytes: int, cookie: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"}
    if cookie:
        headers["Cookie"] = cookie
    request = Request(url, headers=headers)
    with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"PDF exceeds {max_bytes} bytes")
    return data


def download_pdf(url: str, *, max_bytes: int) -> bytes:
    data = _fetch(url, max_bytes=max_bytes)
    if data.startswith(b"%PDF"):
        return data
    # NCBI PMC fronts PDFs with a proof-of-work challenge page; solve it and
    # retry with the unlock cookie.
    if len(data) < 64 * 1024:
        cookie = solve_pmc_pow(data.decode("utf-8", errors="ignore"))
        if cookie:
            data = _fetch(url, max_bytes=max_bytes, cookie=cookie)
            if data.startswith(b"%PDF"):
                return data
    raise ValueError("payload is not a PDF")


def alternate_urls(url: str) -> list[str]:
    """The recorded URL first, then mirrors worth trying when it fails.

    EuropePMC's getPdf renderer 500s persistently for some articles even when
    the same PDF is available from NCBI PMC directly (behind the POW page the
    downloader can now solve)."""
    urls = [url]
    if "europepmc.org" in url:
        match = PMCID_PATTERN.search(url)
        if match:
            urls.append(f"https://pmc.ncbi.nlm.nih.gov/articles/{match.group(0).upper()}/pdf/")
    return urls


def download_pdf_with_fallbacks(url: str, *, max_bytes: int) -> bytes:
    last_error: Exception | None = None
    for candidate_url in alternate_urls(url):
        try:
            return download_pdf(candidate_url, max_bytes=max_bytes)
        except Exception as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def main() -> int:
    args = build_parser().parse_args()
    config = r2_storage.r2_config()
    if config is None:
        raise SystemExit("R2 is not configured; set the R2_* environment variables (see scripts/r2_storage.py).")
    client = require_client()

    statuses = {part.strip() for part in args.statuses.split(",") if part.strip()}
    rows = fetch_all(client, "papers", "id,filename,pdf_url,source_pdf_url,routing_status")
    candidates = [
        row
        for row in rows
        if str(row.get("pdf_url") or "").startswith("http")
        and not r2_storage.is_r2_url(row.get("pdf_url"), config)
        and (args.all_statuses or str(row.get("routing_status") or "") in statuses)
        and row.get("filename")
    ]
    print(f"{len(candidates)} paper(s) to re-host (of {len(rows)} total).")

    max_bytes = max_paper_pdf_bytes()
    uploaded = 0
    failed: list[str] = []
    for index, row in enumerate(candidates, start=1):
        paper_id = row["id"]
        filename = str(row["filename"])
        source_url = str(row["pdf_url"])
        label = f"[{index}/{len(candidates)}] paper {paper_id} ({filename})"
        if args.dry_run:
            print(f"{label}: would download {source_url}")
            continue
        try:
            data = download_pdf_with_fallbacks(source_url, max_bytes=max_bytes)
            new_url = r2_storage.upload_pdf_bytes(data, filename, config=config)
            update: dict = {"pdf_url": new_url}
            if not row.get("source_pdf_url"):
                update["source_pdf_url"] = source_url
            client.table("papers").update(update).eq("id", paper_id).execute()
            uploaded += 1
            print(f"{label}: re-hosted ({len(data)} bytes)")
        except Exception as exc:
            failed.append(f"paper {paper_id}: {type(exc).__name__}: {exc}")
            print(f"{label}: FAILED — {type(exc).__name__}: {exc}")
        if args.limit and uploaded >= args.limit:
            print(f"Reached --limit {args.limit}; stopping.")
            break
        time.sleep(max(0.0, args.sleep_seconds))

    print(f"\nDone: uploaded={uploaded} failed={len(failed)} dry_run={args.dry_run}")
    for line in failed[:20]:
        print(f"  {line}")
    if args.json_summary:
        print(json.dumps({"uploaded": uploaded, "failed": len(failed), "candidates": len(candidates), "dry_run": args.dry_run}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

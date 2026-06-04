from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SUPPORTED_LANGUAGES = ("en", "tr")
DEFAULT_ENGLISH_ONLY_TARGET = 20
DEFAULT_SEARCH_SOURCES = "europepmc,openalex,semanticscholar"


def fetch_rows(
    supabase_url: str,
    supabase_key: str,
    table: str,
    select: str,
    filters: Dict[str, str] | None = None,
    batch_size: int = 1000,
) -> list[dict]:
    endpoint = supabase_url.rstrip("/") + f"/rest/v1/{table}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Accept": "application/json",
    }
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "select": select,
            "limit": str(batch_size),
            "offset": str(offset),
        }
        if filters:
            params.update(filters)
        request = Request(f"{endpoint}?{urlencode(params)}", headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Failed to fetch rows from {table}: {exc}") from exc
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected payload for {table}: {payload}")
        rows.extend(payload)
        if len(payload) < batch_size:
            return rows
        offset += batch_size


def fetch_available_counts(supabase_url: str, supabase_key: str) -> Dict[str, int]:
    papers = fetch_rows(supabase_url, supabase_key, "papers", "id,workflow_language,routing_status,latest_ai_extraction_id")
    ai_extractions = fetch_rows(
        supabase_url,
        supabase_key,
        "ai_extractions",
        "id,normalized_payload_json",
    )
    global_labels = fetch_rows(
        supabase_url,
        supabase_key,
        "paper_global_labels",
        "paper_id,label",
        filters={"label": "eq.definitely_no_data"},
    )
    review_outcomes = fetch_rows(
        supabase_url,
        supabase_key,
        "paper_review_outcomes",
        "paper_id",
    )
    label_submissions = fetch_rows(
        supabase_url,
        supabase_key,
        "paper_label_submissions",
        "paper_id,status",
    )
    slot_assignments = fetch_rows(
        supabase_url,
        supabase_key,
        "paper_slot_assignments",
        "paper_id,status",
    )
    skipped_ids = {
        row.get("paper_id")
        for row in global_labels
        if row.get("paper_id") is not None
    }
    resolved_ids = {
        row.get("paper_id")
        for row in review_outcomes
        if row.get("paper_id") is not None
    }
    assigned_ids = {
        row.get("paper_id")
        for row in slot_assignments
        if row.get("paper_id") is not None
        and str(row.get("status") or "").strip().lower() != "cancelled"
    }
    submitted_ids = {
        row.get("paper_id")
        for row in label_submissions
        if row.get("paper_id") is not None
        and str(row.get("status") or "").strip().lower() in {"pending_approval", "accepted"}
    }

    counts = {language: 0 for language in SUPPORTED_LANGUAGES}
    counts["unscoped"] = 0
    ai_decision_by_id = {
        row.get("id"): (row.get("normalized_payload_json") or {}).get("decision_kind")
        for row in ai_extractions
        if row.get("id") is not None and isinstance(row.get("normalized_payload_json"), dict)
    }
    for row in papers:
        paper_id = row.get("id")
        if paper_id in skipped_ids or paper_id in resolved_ids or paper_id in assigned_ids or paper_id in submitted_ids:
            continue
        if str(row.get("routing_status") or "").strip().lower() != "human_review_ready":
            continue
        latest_ai_extraction_id = row.get("latest_ai_extraction_id")
        if not latest_ai_extraction_id:
            continue
        if ai_decision_by_id.get(latest_ai_extraction_id) != "has_data":
            continue
        workflow_language = str(row.get("workflow_language") or "").strip().lower()
        if workflow_language in SUPPORTED_LANGUAGES:
            counts[workflow_language] += 1
        else:
            counts["unscoped"] += 1

    counts["global_skips"] = len(skipped_ids)
    counts["resolved"] = len(resolved_ids)
    counts["assigned"] = len(assigned_ids)
    counts["submitted"] = len(submitted_ids)
    counts["papers_total"] = len(papers)
    counts["total"] = counts["en"] + counts["tr"] + counts["unscoped"]
    return counts


def resolve_language_targets(args: argparse.Namespace) -> Dict[str, int]:
    if args.target_en is not None or args.target_tr is not None:
        return {
            "en": max(0, int(args.target_en or 0)),
            "tr": max(0, int(args.target_tr or 0)),
        }

    if args.target is not None:
        total = max(0, int(args.target))
        return {"en": total, "tr": 0}

    return {"en": DEFAULT_ENGLISH_ONLY_TARGET, "tr": 0}


def deficits_for(targets: Dict[str, int], counts: Dict[str, int]) -> Dict[str, int]:
    return {
        language: max(0, targets.get(language, 0) - counts.get(language, 0))
        for language in SUPPORTED_LANGUAGES
    }


def quotas_met(targets: Dict[str, int], counts: Dict[str, int]) -> bool:
    return all(counts.get(language, 0) >= targets.get(language, 0) for language in SUPPORTED_LANGUAGES)


def run_command(label: str, cmd: list[str], env: dict, *, allow_failure: bool = False) -> bool:
    print(f"\n== {label} ==")
    print(" ".join(cmd))
    result = subprocess.run(cmd, env=env, check=False)
    if result.returncode != 0:
        message = f"{label} failed with exit code {result.returncode}"
        if allow_failure:
            print(message)
            return False
        raise SystemExit(message)
    return True


def run_json_command(label: str, cmd: list[str], env: dict) -> dict:
    print(f"\n== {label} ==")
    print(" ".join(cmd))
    result = subprocess.run(cmd, env=env, check=False, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {result.returncode}")
    for line in reversed(result.stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise SystemExit(f"{label} did not print a JSON summary.")


def run_ai_queue(label: str, *, max_tasks: int, env: dict, stage_key: str | None = None) -> dict:
    cmd = [
        sys.executable,
        "services/data-pipeline/scripts/process_stage_queue.py",
        "--max-tasks",
        str(max(1, int(max_tasks))),
        "--stop-on-quota",
        "--json-summary",
    ]
    if stage_key:
        cmd.extend(["--stage-key", stage_key])
    summary = run_json_command(
        label,
        cmd,
        env,
    )
    if summary.get("quota_limited"):
        raise SystemExit(f"{label} stopped because Gemini quota/rate limit was reached.")
    return summary


def print_counts(prefix: str, counts: Dict[str, int], targets: Dict[str, int]) -> None:
    print(prefix)
    print(f"  Papers total: {counts['papers_total']}")
    print(f"  Global no-data labels: {counts['global_skips']}")
    print(f"  Resolved review outcomes: {counts['resolved']}")
    print(f"  Legacy assigned papers: {counts['assigned']}")
    print(f"  Pending/accepted general submissions: {counts.get('submitted', 0)}")
    print(f"  Human-review-ready total: {counts['total']}")
    print(f"  Human-review-ready EN: {counts['en']} / target {targets['en']}")
    print(f"  Human-review-ready TR: {counts['tr']} / target {targets['tr']}")
    if counts["unscoped"]:
        print(f"  Human-review-ready unscoped: {counts['unscoped']}")


def _load_manifest_payload(data_dir: str) -> dict | None:
    manifest_path = Path(data_dir) / "raw_pdfs" / "_harvest_metadata.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def print_run_summary(data_dir: str) -> None:
    payload = _load_manifest_payload(data_dir)
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        print("Run summary: unavailable")
        return

    print("Run summary:")
    stop_reason = str(payload.get("stop_reason") or "").strip()
    if stop_reason:
        max_wallclock = int(payload.get("max_wallclock_seconds") or 0)
        suffix = f" after {max_wallclock}s" if max_wallclock > 0 else ""
        print(f"  Stopped: {stop_reason}{suffix}")
    dergipark_index = payload.get("dergipark_index") if isinstance(payload, dict) else None
    if isinstance(dergipark_index, dict):
        print(
            "  DergiPark index: "
            f"journals={int(dergipark_index.get('journal_count', 0))} "
            f"issues={int(dergipark_index.get('issue_count', 0))} "
            f"articles={int(dergipark_index.get('article_count', 0))} "
            f"with_abstract={int(dergipark_index.get('articles_with_abstract', 0))} "
            f"with_pdf={int(dergipark_index.get('articles_with_pdf_url', 0))}"
        )
        refreshed_at = dergipark_index.get("refreshed_at")
        if refreshed_at:
            print(f"  DergiPark index refreshed_at={refreshed_at}")

    languages = summary.get("languages") if isinstance(summary.get("languages"), dict) else {}
    for language in SUPPORTED_LANGUAGES:
        row = languages.get(language) or {}
        print(
            f"  {language.upper()}: "
            f"hits={int(row.get('hits', 0))} "
            f"gate_pass={int(row.get('search_gate_pass', 0))} "
            f"metadata_pass={int(row.get('metadata_pass', 0))} "
            f"pdf_fetch_fail={int(row.get('pdf_fetch_fail', 0))} "
            f"pdf_validation_fail={int(row.get('pdf_validation_fail', 0))} "
            f"accepted={int(row.get('accepted', 0))}"
        )

    sources = summary.get("sources") if isinstance(summary.get("sources"), dict) else {}
    nonzero_sources = [
        (source, row)
        for source, row in sorted(sources.items())
        if isinstance(row, dict) and any(int(row.get(metric, 0)) for metric in row)
    ]
    if nonzero_sources:
        print("  By source:")
        for source, row in nonzero_sources:
            print(
                f"    {source}: "
                f"hits={int(row.get('hits', 0))} "
                f"gate_pass={int(row.get('search_gate_pass', 0))} "
                f"metadata_pass={int(row.get('metadata_pass', 0))} "
                f"pdf_fetch_fail={int(row.get('pdf_fetch_fail', 0))} "
                f"pdf_validation_fail={int(row.get('pdf_validation_fail', 0))} "
                f"accepted={int(row.get('accepted', 0))}"
            )

    rejections = summary.get("rejections") if isinstance(summary.get("rejections"), dict) else {}
    if rejections:
        rendered = ", ".join(
            f"{stage}={int(count)}"
            for stage, count in sorted(rejections.items())
        )
        print(f"  Rejections: {rendered}")


def run_refill_cycle(
    *,
    deficits: Dict[str, int],
    env: dict,
    args: argparse.Namespace,
    cycle_label: str,
    process_ai_after_upload: bool = True,
) -> None:
    if deficits["en"] <= 0 and deficits["tr"] <= 0:
        return

    print(
        f"\n{cycle_label}: refill deficits EN={deficits['en']} TR={deficits['tr']} "
        f"(max_queries={args.max_queries})"
    )

    if not args.skip_feedback:
        run_command(
            "Update feedback terms",
            [sys.executable, "services/data-pipeline/food_paper_crawler/feedback/update_terms.py"],
            env,
            allow_failure=True,
        )

    sources = str(getattr(args, "sources", DEFAULT_SEARCH_SOURCES) or DEFAULT_SEARCH_SOURCES)
    wants_turkish = deficits.get("tr", 0) > 0
    wants_dergipark = "dergipark" in {part.strip().lower() for part in sources.split(",") if part.strip()}

    if wants_turkish and wants_dergipark and not args.skip_dergipark_refresh:
        run_command(
            "Refresh DergiPark index",
            [
                sys.executable,
                "services/data-pipeline/scripts/refresh_dergipark_index.py",
                "--data-dir",
                args.data_dir,
                "--journal-limit",
                str(args.dergipark_journal_limit),
                "--max-issues-per-journal",
                str(args.dergipark_max_issues_per_journal),
            ],
            env,
        )

    crawler_cmd = [
        sys.executable,
        "services/data-pipeline/main.py",
        "--data-dir",
        args.data_dir,
        "--target-pdfs-en",
        str(deficits["en"]),
        "--target-pdfs-tr",
        str(deficits["tr"]),
        "--query-limit",
        str(args.query_limit),
        "--max-queries",
        str(args.max_queries),
        "--sources",
        sources,
    ]
    crawler_max_wallclock_seconds = max(0, int(getattr(args, "crawler_max_wallclock_seconds", 0) or 0))
    if crawler_max_wallclock_seconds > 0:
        crawler_cmd.extend(["--max-wallclock-seconds", str(crawler_max_wallclock_seconds)])
    run_command("Crawler v2", crawler_cmd, env)
    print_run_summary(args.data_dir)

    run_command(
        "Upload to Supabase",
        [
            sys.executable,
            "services/data-pipeline/scripts/upload_to_supabase.py",
            "--data-dir",
            args.data_dir,
        ],
        env,
    )

    if process_ai_after_upload:
        worker_batch = max(1, int(getattr(args, "max_ai_tasks", 5)))
        run_ai_queue(
            "Process Gemma proof-extraction queue",
            max_tasks=max(worker_batch * 10, 20),
            env=env,
            stage_key="gemma_proof_extraction_v1",
        )
        run_ai_queue(
            "Process AI routing queue",
            max_tasks=worker_batch,
            env=env,
            stage_key="gemini_flash_db_payload_v2",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ensure there are enough English papers for the UI.")
    parser.add_argument(
        "--threshold",
        type=int,
        default=0,
        help="Legacy total-availability threshold; quotas still take priority if a language is under target.",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=None,
        help="Legacy total paper target; currently assigned entirely to English unless --target-tr is set.",
    )
    parser.add_argument("--target-en", type=int, default=None, help="Target available English papers")
    parser.add_argument("--target-tr", type=int, default=None, help="Target available Turkish papers")
    parser.add_argument("--data-dir", default="services/data-pipeline/data", help="Crawler data directory")
    parser.add_argument(
        "--query-limit",
        type=int,
        default=50,
        help="Max search hits to inspect per query batch before moving to the next batch",
    )
    parser.add_argument("--max-queries", type=int, default=80, help="Cap on query count per crawler run")
    parser.add_argument(
        "--crawler-max-wallclock-seconds",
        type=int,
        default=0,
        help="Stop crawler runs after this many seconds and upload accepted partial results (0 = disabled)",
    )
    parser.add_argument(
        "--sources",
        default=DEFAULT_SEARCH_SOURCES,
        help="Comma-separated metadata sources for crawler runs. Defaults to English sources only.",
    )
    parser.add_argument("--max-ai-tasks", type=int, default=5, help="Maximum queued AI tasks to process during each AI drain")
    parser.add_argument("--dergipark-journal-limit", type=int, default=0, help="Limit how many configured DergiPark journals are refreshed per cycle (0 = all)")
    parser.add_argument("--dergipark-max-issues-per-journal", type=int, default=12, help="How many newest archive issues to inspect per DergiPark journal refresh")
    parser.add_argument("--dergipark-scan-budget", type=int, default=0, help="Deprecated alias for --dergipark-max-issues-per-journal")
    parser.add_argument("--max-cycles", type=int, default=5, help="Maximum refill cycles")
    parser.add_argument(
        "--max-effort-tr",
        type=int,
        default=3,
        help="Additional Turkish-only refill cycles before fallback is allowed",
    )
    parser.add_argument(
        "--quota-fallback",
        choices=("strict", "backfill_english"),
        default="backfill_english",
        help="What to do if Turkish stays under target after the configured effort cap",
    )
    parser.add_argument("--skip-feedback", action="store_true", help="Skip feedback refresh before crawling")
    parser.add_argument("--skip-dergipark-refresh", action="store_true", help="Skip refreshing the local DergiPark journal/article index before crawling")
    parser.add_argument("--dry-run", action="store_true", help="Only report counts")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY for auto-crawl.")

    targets = resolve_language_targets(args)
    counts = fetch_available_counts(supabase_url, supabase_key)
    print_counts("Current paper stock:", counts, targets)
    print(f"Threshold: {args.threshold}")
    print(f"Quota fallback: {args.quota_fallback}")
    if args.dergipark_scan_budget > 0:
        args.dergipark_max_issues_per_journal = args.dergipark_scan_budget

    if args.dry_run:
        return

    env = os.environ.copy()
    env["SUPABASE_URL"] = supabase_url
    env["SUPABASE_SERVICE_ROLE_KEY"] = supabase_key

    run_ai_queue(
        "Process existing Gemma proof-extraction queue",
        max_tasks=max(max(1, int(args.max_ai_tasks)) * 10, 20),
        env=env,
        stage_key="gemma_proof_extraction_v1",
    )
    run_ai_queue(
        "Process existing Gemini extraction queue",
        max_tasks=max(1, int(args.max_ai_tasks)),
        env=env,
        stage_key="gemini_flash_db_payload_v2",
    )
    counts = fetch_available_counts(supabase_url, supabase_key)
    print_counts("After draining existing AI queue:", counts, targets)

    if quotas_met(targets, counts):
        print("Language targets already met. No crawl triggered.")
        return

    if counts["total"] > args.threshold:
        print("Total threshold already exceeded, but refill will continue because at least one language is under target.")

    for cycle in range(1, args.max_cycles + 1):
        current_deficits = deficits_for(targets, counts)
        if current_deficits["en"] <= 0 and current_deficits["tr"] <= 0:
            break
        run_refill_cycle(
            deficits=current_deficits,
            env=env,
            args=args,
            cycle_label=f"Cycle {cycle}",
        )
        counts = fetch_available_counts(supabase_url, supabase_key)
        print_counts(f"After cycle {cycle}:", counts, targets)
        if quotas_met(targets, counts):
            break

    for extra_cycle in range(1, args.max_effort_tr + 1):
        if counts["tr"] >= targets["tr"]:
            break
        run_refill_cycle(
            deficits={"en": 0, "tr": max(0, targets["tr"] - counts["tr"])},
            env=env,
            args=args,
            cycle_label=f"Turkish extra cycle {extra_cycle}",
        )
        counts = fetch_available_counts(supabase_url, supabase_key)
        print_counts(f"After Turkish extra cycle {extra_cycle}:", counts, targets)

    if not quotas_met(targets, counts) and args.quota_fallback == "backfill_english":
        target_total = targets["en"] + targets["tr"]
        scoped_total = counts["en"] + counts["tr"]
        backfill_needed = max(0, target_total - scoped_total)
        if backfill_needed > 0:
            run_refill_cycle(
                deficits={"en": backfill_needed, "tr": 0},
                env=env,
                args=args,
                cycle_label="English fallback cycle",
            )
            counts = fetch_available_counts(supabase_url, supabase_key)
            print_counts("After English fallback cycle:", counts, targets)

    if quotas_met(targets, counts):
        print("Language targets reached.")
        return

    print(
        "Stopped below target. "
        f"Current EN={counts['en']}/{targets['en']} TR={counts['tr']}/{targets['tr']} "
        f"(fallback={args.quota_fallback})."
    )


if __name__ == "__main__":
    main()

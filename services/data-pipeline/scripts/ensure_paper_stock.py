from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Dict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SUPPORTED_LANGUAGES = ("en", "tr")


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
    papers = fetch_rows(supabase_url, supabase_key, "papers", "id,workflow_language")
    global_labels = fetch_rows(
        supabase_url,
        supabase_key,
        "paper_global_labels",
        "paper_id,label",
        filters={"label": "eq.definitely_no_data"},
    )
    skipped_ids = {
        row.get("paper_id")
        for row in global_labels
        if row.get("paper_id") is not None
    }

    counts = {language: 0 for language in SUPPORTED_LANGUAGES}
    counts["unscoped"] = 0
    for row in papers:
        paper_id = row.get("id")
        if paper_id in skipped_ids:
            continue
        workflow_language = str(row.get("workflow_language") or "").strip().lower()
        if workflow_language in SUPPORTED_LANGUAGES:
            counts[workflow_language] += 1
        else:
            counts["unscoped"] += 1

    counts["global_skips"] = len(skipped_ids)
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
        en_target = total // 2
        tr_target = total - en_target
        return {"en": en_target, "tr": tr_target}

    return {"en": 10, "tr": 10}


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


def print_counts(prefix: str, counts: Dict[str, int], targets: Dict[str, int]) -> None:
    print(prefix)
    print(f"  Papers total: {counts['papers_total']}")
    print(f"  Global no-data labels: {counts['global_skips']}")
    print(f"  Available total: {counts['total']}")
    print(f"  Available EN: {counts['en']} / target {targets['en']}")
    print(f"  Available TR: {counts['tr']} / target {targets['tr']}")
    if counts["unscoped"]:
        print(f"  Available unscoped: {counts['unscoped']}")


def run_refill_cycle(
    *,
    deficits: Dict[str, int],
    env: dict,
    args: argparse.Namespace,
    cycle_label: str,
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

    run_command(
        "Crawler v2",
        [
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
        ],
        env,
    )

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ensure there are enough bilingual papers for the UI.")
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
        help="Legacy total paper target; split evenly when --target-en/--target-tr are not set.",
    )
    parser.add_argument("--target-en", type=int, default=None, help="Target available English papers")
    parser.add_argument("--target-tr", type=int, default=None, help="Target available Turkish papers")
    parser.add_argument("--data-dir", default="services/data-pipeline/data", help="Crawler data directory")
    parser.add_argument("--query-limit", type=int, default=50, help="Results to inspect per query")
    parser.add_argument("--max-queries", type=int, default=80, help="Cap on query count per crawler run")
    parser.add_argument("--max-cycles", type=int, default=5, help="Maximum bilingual refill cycles")
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
    parser.add_argument("--dry-run", action="store_true", help="Only report counts")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY for auto-crawl.")

    targets = resolve_language_targets(args)
    counts = fetch_available_counts(supabase_url, supabase_key)
    print_counts("Current paper stock:", counts, targets)
    print(f"Threshold: {args.threshold}")
    print(f"Quota fallback: {args.quota_fallback}")

    if args.dry_run:
        return

    if quotas_met(targets, counts):
        print("Language targets already met. No crawl triggered.")
        return

    if counts["total"] > args.threshold:
        print("Total threshold already exceeded, but refill will continue because at least one language is under target.")

    env = os.environ.copy()
    env["SUPABASE_URL"] = supabase_url
    env["SUPABASE_KEY"] = supabase_key
    env["SUPABASE_SERVICE_ROLE_KEY"] = supabase_key
    env["VITE_SUPABASE_URL"] = supabase_url

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

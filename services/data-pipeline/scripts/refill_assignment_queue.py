from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from supabase import Client, create_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUPPORTED_LANGUAGES = ("en", "tr")


@dataclass(frozen=True)
class ReviewerProfile:
    id: str
    display_name: str
    active: bool
    can_review_en: bool
    can_review_tr: bool
    tester_access: bool
    official_slot: str | None
    auth_user_id: str | None
    can_approve_labels: bool = False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and maintain general queue paper stock.")
    parser.add_argument("--target-open", type=int, default=50, help="Minimum visible papers in the shared general queue")
    parser.add_argument("--max-cycles", type=int, default=8, help="Maximum stock/AI/refill cycles to run")
    parser.add_argument("--refill-step-en", type=int, default=4, help="How many new EN papers to request when queue stock is low")
    parser.add_argument("--refill-step-tr", type=int, default=4, help="How many new TR papers to request when queue stock is low")
    parser.add_argument("--max-ai-tasks", type=int, default=5, help="Maximum queued AI tasks to process during this run")
    parser.add_argument("--seed", type=int, default=20260413, help="Retained for caller compatibility; no longer used")
    parser.add_argument("--dry-run", action="store_true", help="Report planned stock actions without writing to Supabase")
    return parser


def require_client() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY.")
    return create_client(supabase_url, supabase_key)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_all(client: Client, table: str, select: str, batch_size: int = 1000) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        response = client.table(table).select(select).range(offset, offset + batch_size - 1).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < batch_size:
            return rows
        offset += batch_size


def open_status(status: str) -> bool:
    return status in {"available", "draft", "pending_approval"}


def unresolved_slot_status(status: str) -> bool:
    return status not in {"resolved", "cancelled"}


def assignment_stock_counts(open_available: list[dict]) -> dict[str, int]:
    return {
        "en": sum(1 for paper in open_available if paper.get("workflow_language") == "en"),
        "tr": sum(1 for paper in open_available if paper.get("workflow_language") == "tr"),
    }


def available_papers(
    papers: list[dict],
    slot_assignments: list[dict],
    review_outcomes: list[dict],
    global_labels: list[dict],
    label_submissions: list[dict] | None = None,
    ai_extractions: list[dict] | None = None,
) -> list[dict]:
    blocked_ids = {
        row.get("paper_id")
        for row in review_outcomes
        if row.get("paper_id") is not None
    }
    blocked_ids |= {
        row.get("paper_id")
        for row in global_labels
        if row.get("paper_id") is not None and row.get("label") == "definitely_no_data"
    }
    blocked_ids |= {
        row.get("paper_id")
        for row in label_submissions or []
        if row.get("paper_id") is not None
        and str(row.get("status") or "").strip().lower() in {"pending_approval", "accepted"}
    }
    blocked_ids |= {
        row.get("paper_id")
        for row in slot_assignments
        if row.get("paper_id") is not None
        and unresolved_slot_status(str(row.get("status") or "").strip().lower())
    }

    def waiting_order(row: dict) -> tuple[str, int]:
        timestamp = str(row.get("routing_updated_at") or row.get("created_at") or "")
        try:
            paper_id = int(row.get("id") or 0)
        except (TypeError, ValueError):
            paper_id = 0
        return timestamp, paper_id

    ai_decision_by_id = {
        row.get("id"): (row.get("normalized_payload_json") or {}).get("decision_kind")
        for row in ai_extractions or []
        if row.get("id") is not None and isinstance(row.get("normalized_payload_json"), dict)
    }

    return [
        paper
        for paper in sorted(papers, key=waiting_order)
        if paper.get("id") not in blocked_ids
        and str(paper.get("routing_status") or "").strip().lower() == "human_review_ready"
        and paper.get("latest_ai_extraction_id")
        and ai_decision_by_id.get(paper.get("latest_ai_extraction_id")) == "has_data"
        and str(paper.get("workflow_language") or "").strip().lower() in SUPPORTED_LANGUAGES
    ]


def fetch_state(client: Client) -> dict[str, list[dict]]:
    return {
        "papers": fetch_all(client, "papers", "id,title,doi,filename,workflow_language,created_at,routing_updated_at,routing_status,current_stage_key,latest_ai_extraction_id"),
        "ai_extractions": fetch_all(client, "ai_extractions", "id,normalized_payload_json"),
        "global_labels": fetch_all(client, "paper_global_labels", "paper_id,label"),
        "review_outcomes": fetch_all(client, "paper_review_outcomes", "paper_id,decision_kind"),
        "paper_label_submissions": fetch_all(client, "paper_label_submissions", "paper_id,status"),
        "paper_slot_assignments": fetch_all(client, "paper_slot_assignments", "paper_id,status"),
        "reviewer_profiles": fetch_all(
            client,
            "reviewer_profiles",
            "id,email,auth_user_id,display_name,active,can_review_en,can_review_tr,tester_access,official_slot,can_approve_labels",
        ),
    }


def build_profiles(state: dict[str, list[dict]]) -> dict[str, ReviewerProfile]:
    return {
        row["id"]: ReviewerProfile(
            id=row["id"],
            display_name=str(row.get("display_name") or row["id"]),
            active=bool(row.get("active", True)),
            can_review_en=bool(row.get("can_review_en", True)),
            can_review_tr=bool(row.get("can_review_tr", True)),
            tester_access=bool(row.get("tester_access", False)),
            official_slot=row.get("official_slot"),
            auth_user_id=row.get("auth_user_id"),
            can_approve_labels=bool(row.get("can_approve_labels", False)),
        )
        for row in state.get("reviewer_profiles", [])
        if row.get("id")
    }


def language_deficits_for(open_available: list[dict], target_open: int) -> dict[str, int]:
    counts = assignment_stock_counts(open_available)
    target_open = max(0, int(target_open))
    target_en = target_open // 2
    target_tr = target_open - target_en
    return {
        "en": max(0, target_en - counts["en"]),
        "tr": max(0, target_tr - counts["tr"]),
    }


def deficits_by_name(deficits: dict[str, int], profiles: dict[str, ReviewerProfile] | None = None) -> dict[str, int]:
    if set(deficits).issubset(set(SUPPORTED_LANGUAGES)):
        return {language.upper(): int(deficits.get(language, 0)) for language in SUPPORTED_LANGUAGES}
    profiles = profiles or {}
    return {
        profiles[profile_id].display_name if profile_id in profiles else profile_id: int(deficit)
        for profile_id, deficit in sorted(deficits.items())
    }


def reviewer_open_counts_by_name(open_counts: dict[str, int], profiles: dict[str, ReviewerProfile]) -> dict[str, int]:
    return {
        profiles[profile_id].display_name: int(open_counts.get(profile_id, 0))
        for profile_id in sorted(profiles, key=lambda value: profiles[value].display_name.lower())
    }


def compute_assignment_context(
    state: dict[str, list[dict]],
    *,
    target_open: int,
) -> dict[str, object]:
    profiles = build_profiles(state)
    open_available = available_papers(
        state.get("papers", []),
        state.get("paper_slot_assignments", state.get("slot_assignments", [])),
        state.get("review_outcomes", []),
        state.get("global_labels", []),
        state.get("paper_label_submissions", []),
        state.get("ai_extractions", []),
    )
    counts = assignment_stock_counts(open_available)
    language_deficits = language_deficits_for(open_available, target_open)
    return {
        "profiles": profiles,
        "open_available": open_available,
        "available_counts": counts,
        "deficits": language_deficits,
        "language_deficits": language_deficits,
    }


def assign_ready_papers(
    client: Client,
    *,
    target_open: int = 50,
    seed: int = 20260413,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict[str, object]:
    del seed
    del dry_run
    state = fetch_state(client)
    context = compute_assignment_context(state, target_open=target_open)
    open_available: list[dict] = context["open_available"]  # type: ignore[assignment]
    counts: dict[str, int] = context["available_counts"]  # type: ignore[assignment]
    language_deficits: dict[str, int] = context["language_deficits"]  # type: ignore[assignment]
    available_total = len(open_available)
    stock_deficit = max(0, int(target_open) - available_total)

    if verbose:
        print(f"  General queue stock: EN={counts['en']} TR={counts['tr']} total={available_total}")
        print(f"  Target visible stock: {int(target_open)} deficit={stock_deficit}")

    return {
        "target_open": int(target_open),
        "made_progress": False,
        "satisfied": stock_deficit <= 0,
        "available_before": counts,
        "open_counts": {"General Queue": available_total},
        "deficits_before": deficits_by_name(language_deficits),
        "deficits_after": deficits_by_name(language_deficits),
        "stock_deficit": stock_deficit,
        "planned_slot_assignments": 0,
        "planned_user_assignments": 0,
        "planned_general_queue_papers": available_total,
        "dry_run": False,
    }


def has_queued_ai_work(papers: list[dict]) -> bool:
    return any(
        str(paper.get("routing_status") or "").strip().lower() == "queued_for_ai"
        for paper in papers
    )


def drain_ai_queue(*, dry_run: bool, max_tasks: int) -> bool:
    print("General queue stock is low; attempting to drain queued AI routing tasks first.")
    commands = [
        [
            sys.executable,
            "services/data-pipeline/scripts/process_stage_queue.py",
            "--stage-key",
            "gemma_proof_extraction_v1",
            "--max-tasks",
            str(max(max(1, int(max_tasks)) * 10, 20)),
            "--stop-on-quota",
            "--json-summary",
        ],
        [
            sys.executable,
            "services/data-pipeline/scripts/process_stage_queue.py",
            "--stage-key",
            "gemini_flash_db_payload_v2",
            "--max-tasks",
            str(max(1, int(max_tasks))),
            "--stop-on-quota",
            "--json-summary",
        ],
    ]

    env = os.environ.copy()
    for cmd in commands:
        if dry_run:
            print("[dry-run] " + " ".join(cmd))
            continue
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=False, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
        if result.returncode != 0:
            raise SystemExit(f"process_stage_queue.py failed with exit code {result.returncode}")
        summary: dict | None = None
        for line in reversed(result.stdout.splitlines()):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                summary = payload
                break
        if summary and summary.get("quota_limited"):
            raise SystemExit("AI quota/rate limit reached; stopping before crawl refill.")
    return True


def refill_stock(
    *,
    current_available: list[dict],
    deficits: dict[str, int],
    profiles: dict[str, ReviewerProfile],
    target_open: int,
    refill_step_en: int,
    refill_step_tr: int,
    dry_run: bool,
) -> bool:
    del profiles
    del target_open
    current_counts = defaultdict(int)
    for paper in current_available:
        language = str(paper.get("workflow_language") or "").strip().lower()
        current_counts[language] += 1

    need_en = deficits.get("en", 0) > 0
    need_tr = deficits.get("tr", 0) > 0
    target_en = current_counts["en"] + (refill_step_en if need_en else 0)
    target_tr = current_counts["tr"] + (refill_step_tr if need_tr else 0)
    if target_en <= current_counts["en"] and target_tr <= current_counts["tr"]:
        return False

    cmd = [
        sys.executable,
        "services/data-pipeline/scripts/ensure_paper_stock.py",
        "--target-en",
        str(target_en),
        "--target-tr",
        str(target_tr),
    ]
    print(f"General queue stock is low; requesting new papers EN={target_en} TR={target_tr}")
    if dry_run:
        print("[dry-run] " + " ".join(cmd))
        return True

    env = os.environ.copy()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(f"ensure_paper_stock.py failed with exit code {result.returncode}")
    return True


def main() -> None:
    args = build_parser().parse_args()
    client = require_client()

    for cycle in range(1, args.max_cycles + 1):
        print(f"\nCycle {cycle}")
        stock_summary = assign_ready_papers(
            client,
            target_open=args.target_open,
            seed=args.seed,
            dry_run=args.dry_run,
            verbose=True,
        )
        if stock_summary["satisfied"]:
            print("General queue stock already meets the target.")
            return

        state = fetch_state(client)
        context = compute_assignment_context(state, target_open=args.target_open)
        if has_queued_ai_work(state["papers"]):
            if drain_ai_queue(dry_run=args.dry_run, max_tasks=args.max_ai_tasks):
                if args.dry_run:
                    return
                continue

        if not refill_stock(
            current_available=context["open_available"],  # type: ignore[arg-type]
            deficits=context["language_deficits"],  # type: ignore[arg-type]
            profiles=context["profiles"],  # type: ignore[arg-type]
            target_open=args.target_open,
            refill_step_en=args.refill_step_en,
            refill_step_tr=args.refill_step_tr,
            dry_run=args.dry_run,
        ):
            break

    raise SystemExit("Could not satisfy general queue stock target before hitting the cycle limit.")


if __name__ == "__main__":
    main()

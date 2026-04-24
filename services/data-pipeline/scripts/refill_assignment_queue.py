from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from supabase import Client, create_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUPPORTED_LANGUAGES = ("en", "tr")
OFFICIAL_SLOT_PAIRS = (
    ("arciel", "peri"),
    ("arciel", "aleyna"),
    ("peri", "aleyna"),
)


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Top up reviewer-specific annotation queues.")
    parser.add_argument("--target-open", type=int, default=10, help="Minimum open personal backlog per active reviewer")
    parser.add_argument("--max-cycles", type=int, default=8, help="Maximum assign/refill cycles to run")
    parser.add_argument("--refill-step-en", type=int, default=4, help="How many new EN papers to request when queue stock is exhausted")
    parser.add_argument("--refill-step-tr", type=int, default=4, help="How many new TR papers to request when queue stock is exhausted")
    parser.add_argument("--seed", type=int, default=20260413, help="Random seed for balanced pair selection")
    parser.add_argument("--dry-run", action="store_true", help="Report planned assignments without writing to Supabase")
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
    return status in {"assigned", "draft"}


def unresolved_slot_status(status: str) -> bool:
    return status not in {"resolved", "cancelled"}


def profile_can_review_language(profile: ReviewerProfile, language: str) -> bool:
    if profile.tester_access:
        return False
    return profile.can_review_en if language == "en" else profile.can_review_tr


def build_slot_member_map(slot_members: list[dict], profiles: dict[str, ReviewerProfile]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for member in slot_members:
        profile_id = member.get("reviewer_profile_id")
        slot_key = member.get("slot_key")
        if not profile_id or not slot_key or profile_id not in profiles:
            continue
        profile = profiles[profile_id]
        if not profile.active or not bool(member.get("active", True)):
            continue
        result[slot_key].append(member)
    return result


def targetable_profiles(slot_members: Iterable[dict], profiles: dict[str, ReviewerProfile]) -> dict[str, ReviewerProfile]:
    ids = {
        member["reviewer_profile_id"]
        for member in slot_members
        if member.get("reviewer_profile_id") in profiles
    }
    return {
        profile_id: profiles[profile_id]
        for profile_id in ids
        if profiles[profile_id].active and not profiles[profile_id].tester_access
    }


def compute_open_counts(assignments: Iterable[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for assignment in assignments:
        if open_status(str(assignment.get("status") or "").strip().lower()):
            profile_id = assignment.get("reviewer_profile_id")
            if profile_id:
                counts[profile_id] += 1
    return counts


def compute_slot_load(slot_assignments: Iterable[dict]) -> dict[str, int]:
    loads: dict[str, int] = defaultdict(int)
    for assignment in slot_assignments:
        status = str(assignment.get("status") or "").strip().lower()
        slot_key = assignment.get("slot_key")
        if slot_key and unresolved_slot_status(status):
            loads[slot_key] += 1
    return loads


def compute_deficits(
    profiles: dict[str, ReviewerProfile],
    slot_members: list[dict],
    open_counts: dict[str, int],
    target_open: int,
) -> dict[str, int]:
    target_profiles = targetable_profiles(slot_members, profiles)
    return {
        profile_id: max(0, target_open - open_counts.get(profile_id, 0))
        for profile_id in target_profiles
    }


def available_papers(
    papers: list[dict],
    slot_assignments: list[dict],
    review_outcomes: list[dict],
    global_labels: list[dict],
) -> list[dict]:
    blocked_ids = {
        row.get("paper_id")
        for row in slot_assignments
        if row.get("paper_id") is not None and unresolved_slot_status(str(row.get("status") or "").strip().lower())
    }
    blocked_ids |= {
        row.get("paper_id")
        for row in review_outcomes
        if row.get("paper_id") is not None
    }
    blocked_ids |= {
        row.get("paper_id")
        for row in global_labels
        if row.get("paper_id") is not None and row.get("label") == "definitely_no_data"
    }

    def waiting_order(row: dict) -> tuple[str, int]:
        timestamp = str(row.get("routing_updated_at") or row.get("created_at") or "")
        try:
            paper_id = int(row.get("id") or 0)
        except (TypeError, ValueError):
            paper_id = 0
        return timestamp, paper_id

    return [
        paper
        for paper in sorted(papers, key=waiting_order)
        if paper.get("id") not in blocked_ids
        and str(paper.get("routing_status") or "").strip().lower() == "human_review_ready"
        and str(paper.get("workflow_language") or "").strip().lower() in SUPPORTED_LANGUAGES
    ]


def pair_preference_penalty(language: str, slot_pair: tuple[str, str]) -> float:
    slot_set = set(slot_pair)
    if language == "en":
        return 0.0 if "arciel" in slot_set else 0.85
    return 0.0 if slot_set == {"peri", "aleyna"} else 0.7


def choose_slot_pair(
    *,
    language: str,
    rng: random.Random,
    slot_loads: dict[str, int],
    slot_members_by_slot: dict[str, list[dict]],
    profiles: dict[str, ReviewerProfile],
    deficits: dict[str, int],
    open_counts: dict[str, int],
    target_open: int,
) -> tuple[str, str] | None:
    best_pair: tuple[str, str] | None = None
    best_score: float | None = None

    for pair in OFFICIAL_SLOT_PAIRS:
        eligible_members_by_slot = {
            slot_key: [
                member
                for member in slot_members_by_slot.get(slot_key, [])
                if bool(member.get("can_review_en", True) if language == "en" else member.get("can_review_tr", True))
                and profiles.get(member.get("reviewer_profile_id"))
                and profile_can_review_language(profiles[member["reviewer_profile_id"]], language)
            ]
            for slot_key in pair
        }
        if any(not members for members in eligible_members_by_slot.values()):
            continue
        eligible_members = [member for members in eligible_members_by_slot.values() for member in members]

        helpful_profiles = {
            member["reviewer_profile_id"]
            for member in eligible_members
            if deficits.get(member["reviewer_profile_id"], 0) > 0
        }
        improvement = len(helpful_profiles)
        overflow_penalty = sum(
            max(open_counts.get(member["reviewer_profile_id"], 0) + 1 - target_open, 0)
            for member in eligible_members
        ) * 0.35
        slot_penalty = sum(slot_loads.get(slot_key, 0) for slot_key in pair) * 0.45
        preference_penalty = pair_preference_penalty(language, pair)
        score = (
            preference_penalty
            + slot_penalty
            + overflow_penalty
            - (improvement * 4.0)
            + rng.random() * 0.2
        )
        if best_score is None or score < best_score:
            best_score = score
            best_pair = pair
    return best_pair


def build_assignment_changes(
    paper: dict,
    slot_pair: tuple[str, str],
    slot_members_by_slot: dict[str, list[dict]],
    profiles: dict[str, ReviewerProfile],
    existing_slot_by_paper_slot: dict[tuple[int, str], dict] | None = None,
    existing_user_by_slot_profile: dict[tuple[str, str], dict] | None = None,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    paper_id = paper["id"]
    language = str(paper.get("workflow_language") or "").strip().lower()
    existing_slot_by_paper_slot = existing_slot_by_paper_slot or {}
    existing_user_by_slot_profile = existing_user_by_slot_profile or {}
    slot_rows: list[dict] = []
    slot_updates: list[dict] = []
    user_rows: list[dict] = []
    user_updates: list[dict] = []
    now = utcnow_iso()

    for slot_key in slot_pair:
        existing_slot = existing_slot_by_paper_slot.get((paper_id, slot_key))
        if existing_slot:
            existing_slot_status = str(existing_slot.get("status") or "").strip().lower()
            if existing_slot_status != "cancelled":
                return [], [], [], []
            slot_assignment_id = str(existing_slot["id"])
            slot_updates.append(
                {
                    "id": slot_assignment_id,
                    "paper_id": paper_id,
                    "slot_key": slot_key,
                    "payload": {
                        "workflow_language": language,
                        "status": "pending",
                        "official_submission_id": None,
                        "submitted_at": None,
                        "resolved_at": None,
                        "assigned_at": now,
                    },
                }
            )
        else:
            slot_assignment_id = str(uuid.uuid4())
            slot_rows.append(
                {
                    "id": slot_assignment_id,
                    "paper_id": paper_id,
                    "slot_key": slot_key,
                    "workflow_language": language,
                    "status": "pending",
                }
            )
        before_user_count = len(user_rows)
        before_user_update_count = len(user_updates)

        for member in slot_members_by_slot.get(slot_key, []):
            profile_id = member["reviewer_profile_id"]
            profile = profiles.get(profile_id)
            if profile is None or not profile.active:
                continue
            can_review = bool(member.get("can_review_en", True) if language == "en" else member.get("can_review_tr", True))
            if not can_review or not profile_can_review_language(profile, language):
                continue
            existing_user = existing_user_by_slot_profile.get((slot_assignment_id, profile_id))
            if existing_user:
                existing_user_status = str(existing_user.get("status") or "").strip().lower()
                if existing_user_status != "cancelled":
                    return [], [], [], []
                user_updates.append(
                    {
                        "id": existing_user["id"],
                        "paper_slot_assignment_id": slot_assignment_id,
                        "paper_id": paper_id,
                        "reviewer_profile_id": profile_id,
                        "payload": {
                            "auth_user_id": profile.auth_user_id,
                            "workflow_language": language,
                            "status": "assigned",
                            "last_annotation_id": None,
                            "latest_submission_id": None,
                            "last_saved_at": None,
                            "submitted_at": None,
                            "resolved_at": None,
                            "assigned_at": now,
                        },
                    }
                )
            else:
                user_rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "paper_slot_assignment_id": slot_assignment_id,
                        "paper_id": paper_id,
                        "reviewer_profile_id": profile_id,
                        "auth_user_id": profile.auth_user_id,
                        "workflow_language": language,
                        "status": "assigned",
                    }
                )
        if len(user_rows) == before_user_count and len(user_updates) == before_user_update_count:
            return [], [], [], []
    return slot_rows, slot_updates, user_rows, user_updates


def build_assignment_rows(
    paper: dict,
    slot_pair: tuple[str, str],
    slot_members_by_slot: dict[str, list[dict]],
    profiles: dict[str, ReviewerProfile],
) -> tuple[list[dict], list[dict]]:
    slot_rows, _slot_updates, user_rows, _user_updates = build_assignment_changes(
        paper,
        slot_pair,
        slot_members_by_slot,
        profiles,
    )
    return slot_rows, user_rows


def fetch_state(client: Client) -> dict[str, list[dict]]:
    return {
        "papers": fetch_all(client, "papers", "id,title,doi,filename,workflow_language,created_at,routing_updated_at,routing_status"),
        "global_labels": fetch_all(client, "paper_global_labels", "paper_id,label"),
        "review_outcomes": fetch_all(client, "paper_review_outcomes", "paper_id,decision_kind"),
        "slot_assignments": fetch_all(client, "paper_slot_assignments", "id,paper_id,slot_key,status,workflow_language"),
        "user_assignments": fetch_all(
            client,
            "paper_user_assignments",
            "id,paper_id,reviewer_profile_id,auth_user_id,status,workflow_language",
        ),
        "reviewer_profiles": fetch_all(
            client,
            "reviewer_profiles",
            "id,email,auth_user_id,display_name,active,can_review_en,can_review_tr,tester_access,official_slot",
        ),
        "slot_members": fetch_all(
            client,
            "reviewer_slot_members",
            "slot_key,reviewer_profile_id,member_role,can_review_en,can_review_tr,counts_toward_official,active",
        ),
    }


def has_queued_ai_work(papers: list[dict]) -> bool:
    return any(
        str(paper.get("routing_status") or "").strip().lower() == "queued_for_ai"
        for paper in papers
    )


def drain_ai_queue(*, dry_run: bool) -> bool:
    cmd = [
        sys.executable,
        "services/data-pipeline/scripts/process_stage_queue.py",
        "--max-tasks",
        "200",
    ]
    print("Queue stock exhausted; attempting to drain queued AI routing tasks first.")
    if dry_run:
        print("[dry-run] " + " ".join(cmd))
        return True

    env = os.environ.copy()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(f"process_stage_queue.py failed with exit code {result.returncode}")
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
    need_en = any(
        deficit > 0 and profile.can_review_en
        for profile_id, deficit in deficits.items()
        if (profile := profiles.get(profile_id))
    )
    need_tr = any(
        deficit > 0 and profile.can_review_tr
        for profile_id, deficit in deficits.items()
        if (profile := profiles.get(profile_id))
    )
    current_counts = defaultdict(int)
    for paper in current_available:
        language = str(paper.get("workflow_language") or "").strip().lower()
        current_counts[language] += 1

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
    print(f"Queue stock exhausted; requesting new papers EN={target_en} TR={target_tr}")
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
    rng = random.Random(args.seed)
    client = require_client()

    for cycle in range(1, args.max_cycles + 1):
        state = fetch_state(client)
        profiles = {
            row["id"]: ReviewerProfile(
                id=row["id"],
                display_name=str(row.get("display_name") or row["id"]),
                active=bool(row.get("active", True)),
                can_review_en=bool(row.get("can_review_en", True)),
                can_review_tr=bool(row.get("can_review_tr", True)),
                tester_access=bool(row.get("tester_access", False)),
                official_slot=row.get("official_slot"),
                auth_user_id=row.get("auth_user_id"),
            )
            for row in state["reviewer_profiles"]
            if row.get("id")
        }
        slot_members_by_slot = build_slot_member_map(state["slot_members"], profiles)
        open_counts = compute_open_counts(state["user_assignments"])
        slot_loads = compute_slot_load(state["slot_assignments"])
        deficits = compute_deficits(profiles, state["slot_members"], open_counts, args.target_open)
        open_available = available_papers(
            state["papers"],
            state["slot_assignments"],
            state["review_outcomes"],
            state["global_labels"],
        )

        print(f"\nCycle {cycle}")
        for profile_id, deficit in sorted(deficits.items(), key=lambda item: profiles[item[0]].display_name.lower()):
            profile = profiles[profile_id]
            print(
                f"  {profile.display_name}: open={open_counts.get(profile_id, 0)} "
                f"target={args.target_open} deficit={deficit}"
            )
        print(
            "  Unassigned queue stock: "
            f"EN={sum(1 for paper in open_available if paper.get('workflow_language') == 'en')} "
            f"TR={sum(1 for paper in open_available if paper.get('workflow_language') == 'tr')}"
        )

        if not any(deficits.values()):
            print("All active reviewers already meet the open-backlog target.")
            return

        slot_inserts: list[dict] = []
        slot_updates: list[dict] = []
        user_inserts: list[dict] = []
        user_updates: list[dict] = []
        existing_slot_by_paper_slot = {
            (int(row["paper_id"]), str(row["slot_key"])): row
            for row in state["slot_assignments"]
            if row.get("paper_id") is not None and row.get("slot_key") and row.get("id")
        }
        existing_user_by_slot_profile = {
            (str(row["paper_slot_assignment_id"]), str(row["reviewer_profile_id"])): row
            for row in state["user_assignments"]
            if row.get("paper_slot_assignment_id") and row.get("reviewer_profile_id") and row.get("id")
        }
        made_progress = False

        for paper in open_available:
            if not any(deficits.values()):
                break
            language = str(paper.get("workflow_language") or "").strip().lower()
            slot_pair = choose_slot_pair(
                language=language,
                rng=rng,
                slot_loads=slot_loads,
                slot_members_by_slot=slot_members_by_slot,
                profiles=profiles,
                deficits=deficits,
                open_counts=open_counts,
                target_open=args.target_open,
            )
            if slot_pair is None:
                continue

            next_slot_rows, next_slot_updates, next_user_rows, next_user_updates = build_assignment_changes(
                paper,
                slot_pair,
                slot_members_by_slot,
                profiles,
                existing_slot_by_paper_slot=existing_slot_by_paper_slot,
                existing_user_by_slot_profile=existing_user_by_slot_profile,
            )
            if not next_user_rows and not next_user_updates:
                continue

            slot_inserts.extend(next_slot_rows)
            slot_updates.extend(next_slot_updates)
            user_inserts.extend(next_user_rows)
            user_updates.extend(next_user_updates)
            made_progress = True
            for row in next_slot_rows:
                existing_slot_by_paper_slot[(int(row["paper_id"]), str(row["slot_key"]))] = row
            for row in next_slot_updates:
                existing_slot_by_paper_slot[(int(row["paper_id"]), str(row["slot_key"]))] = {
                    **existing_slot_by_paper_slot[(int(row["paper_id"]), str(row["slot_key"]))],
                    **row["payload"],
                }
            for row in next_user_rows:
                existing_user_by_slot_profile[(str(row["paper_slot_assignment_id"]), str(row["reviewer_profile_id"]))] = row
            for row in next_user_updates:
                existing_user_by_slot_profile[(str(row["paper_slot_assignment_id"]), str(row["reviewer_profile_id"]))] = row

            for slot_key in slot_pair:
                slot_loads[slot_key] += 1
            for row in [*next_user_rows, *next_user_updates]:
                profile_id = row["reviewer_profile_id"]
                open_counts[profile_id] += 1
                deficits[profile_id] = max(0, args.target_open - open_counts[profile_id])

        if made_progress:
            print(f"  Planned slot assignments: {len(slot_inserts) + len(slot_updates)}")
            print(f"  Planned user assignments: {len(user_inserts) + len(user_updates)}")
            if args.dry_run:
                for row in [*user_inserts, *user_updates][:12]:
                    print(f"    [dry-run] user_assignment paper={row['paper_id']} reviewer={profiles[row['reviewer_profile_id']].display_name}")
                return
            else:
                for row in slot_updates:
                    client.table("paper_slot_assignments").update(row["payload"]).eq("id", row["id"]).execute()
                if slot_inserts:
                    client.table("paper_slot_assignments").insert(slot_inserts).execute()
                for row in user_updates:
                    client.table("paper_user_assignments").update(row["payload"]).eq("id", row["id"]).execute()
                if user_inserts:
                    client.table("paper_user_assignments").insert(user_inserts).execute()
                print("  Inserted assignments into Supabase.")
            continue

        if has_queued_ai_work(state["papers"]):
            if drain_ai_queue(dry_run=args.dry_run):
                if args.dry_run:
                    return
                continue

        if not refill_stock(
            current_available=open_available,
            deficits=deficits,
            profiles=profiles,
            target_open=args.target_open,
            refill_step_en=args.refill_step_en,
            refill_step_tr=args.refill_step_tr,
            dry_run=args.dry_run,
        ):
            break

    raise SystemExit("Could not satisfy target open backlog before hitting the cycle limit.")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from supabase import Client, create_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = PROJECT_ROOT / "services" / "data-pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from ai_routing import normalize_ai_payload_with_summary
from evaluator.unified_evaluator import UnifiedEvaluator
from scripts.process_stage_queue import extract_pdf_text, fetch_reference_lookups, select_food_candidates_for_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure gemini-3.1-flash-lite as a triage experiment against known Gemini final decisions."
    )
    parser.add_argument("--model-name", default="gemini-3.1-flash-lite")
    parser.add_argument("--baseline-stage-key", default="gemini_flash_db_payload_v2")
    parser.add_argument("--scan-limit", type=int, default=1000)
    parser.add_argument("--max-useful", type=int, default=40)
    parser.add_argument("--max-no-data", type=int, default=40)
    parser.add_argument("--text-limit-chars", type=int, default=24000)
    parser.add_argument("--separate-quota-verified", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="List the holdout without calling the model.")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def require_client() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY.")
    return create_client(supabase_url, supabase_key)


def _fetch_recent_baseline_rows(client: Client, *, stage_key: str, scan_limit: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    remaining = max(1, int(scan_limit))
    query = (
        client.table("ai_extractions")
        .select("id,paper_id,stage_key,normalized_payload_json,created_at")
        .eq("stage_key", stage_key)
        .order("created_at", desc=True)
    )
    while remaining > 0:
        end = offset + min(remaining, 1000) - 1
        response = query.range(offset, end).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < end - offset + 1:
            break
        offset += len(batch)
        remaining -= len(batch)
    return rows


def _fetch_papers(client: Client, paper_ids: list[int]) -> dict[int, dict]:
    papers: dict[int, dict] = {}
    for offset in range(0, len(paper_ids), 500):
        response = (
            client.table("papers")
            .select("id,title,doi,filename")
            .in_("id", paper_ids[offset:offset + 500])
            .execute()
        )
        for row in response.data or []:
            if row.get("id") is not None:
                papers[int(row["id"])] = row
    return papers


def _decision_for_row(row: dict) -> str | None:
    payload = row.get("normalized_payload_json")
    if not isinstance(payload, dict):
        return None
    decision = str(payload.get("decision_kind") or "").strip()
    return decision if decision in {"has_data", "no_usable_data"} else None


def _build_holdout(rows: list[dict], *, max_useful: int, max_no_data: int) -> list[dict]:
    useful: list[dict] = []
    no_data: list[dict] = []
    for row in rows:
        decision = _decision_for_row(row)
        if decision == "has_data" and len(useful) < max_useful:
            useful.append(row)
        elif decision == "no_usable_data" and len(no_data) < max_no_data:
            no_data.append(row)
        if len(useful) >= max_useful and len(no_data) >= max_no_data:
            break
    return useful + no_data


def _trim_text(full_text: str, limit: int) -> str:
    limit = int(limit)
    if limit <= 0 or len(full_text) <= limit:
        return full_text
    head_len = max(1, limit // 2)
    tail_len = max(1, limit - head_len)
    return full_text[:head_len] + "\n\n[TRUNCATED FOR FLASH-LITE TRIAGE]\n\n" + full_text[-tail_len:]


def run_experiment(client: Client, args: argparse.Namespace) -> dict[str, Any]:
    rows = _fetch_recent_baseline_rows(
        client,
        stage_key=args.baseline_stage_key,
        scan_limit=max(1, int(args.scan_limit)),
    )
    holdout = _build_holdout(rows, max_useful=max(0, int(args.max_useful)), max_no_data=max(0, int(args.max_no_data)))
    paper_ids = [int(row["paper_id"]) for row in holdout if row.get("paper_id") is not None]
    papers = _fetch_papers(client, paper_ids)
    summary: dict[str, Any] = {
        "model_name": args.model_name,
        "baseline_stage_key": args.baseline_stage_key,
        "dry_run": bool(args.dry_run),
        "separate_quota_verified": bool(args.separate_quota_verified),
        "holdout_count": len(holdout),
        "known_useful": sum(1 for row in holdout if _decision_for_row(row) == "has_data"),
        "known_no_data": sum(1 for row in holdout if _decision_for_row(row) == "no_usable_data"),
        "results": [],
    }
    if args.dry_run:
        summary["results"] = [
            {
                "paper_id": row.get("paper_id"),
                "known_decision": _decision_for_row(row),
                "title": papers.get(int(row["paper_id"]), {}).get("title") if row.get("paper_id") is not None else None,
            }
            for row in holdout[:50]
        ]
        return summary

    reference_lookups = fetch_reference_lookups(client)
    evaluator = UnifiedEvaluator(
        model_name=str(args.model_name),
        nutrient_catalog=reference_lookups.get("nutrients") or [],
        food_candidates=[],
    )
    if evaluator.model is None:
        raise RuntimeError(f"UnifiedEvaluator could not initialize model {args.model_name}. Check GEMINI_API_KEY.")

    agreements = 0
    useful_hits = 0
    useful_total = 0
    no_data_false_positives = 0
    no_data_total = 0
    for row in holdout:
        paper = papers.get(int(row["paper_id"]))
        if not paper:
            continue
        known_decision = _decision_for_row(row)
        if known_decision == "has_data":
            useful_total += 1
        elif known_decision == "no_usable_data":
            no_data_total += 1
        full_text = extract_pdf_text(str(paper.get("filename") or ""))
        stage_text = _trim_text(full_text, int(args.text_limit_chars))
        evaluator.food_candidates = select_food_candidates_for_text(
            stage_text,
            reference_lookups.get("foods") or [],
        )
        ai_result = evaluator.evaluate_and_extract(
            {
                "pmc_id": paper.get("doi") or paper.get("filename") or "",
                "title": paper.get("title") or "",
                "full_text": stage_text,
            }
        )
        normalization = normalize_ai_payload_with_summary(
            is_useful=ai_result.is_useful,
            records=ai_result.data,
            nutrient_lookup=reference_lookups.get("nutrients") or [],
            food_lookup=reference_lookups.get("foods") or [],
        )
        lite_decision = normalization.decision_kind
        if lite_decision == known_decision:
            agreements += 1
        if known_decision == "has_data" and lite_decision == "has_data":
            useful_hits += 1
        if known_decision == "no_usable_data" and lite_decision == "has_data":
            no_data_false_positives += 1
        summary["results"].append(
            {
                "paper_id": row.get("paper_id"),
                "known_decision": known_decision,
                "flash_lite_decision": lite_decision,
                "accepted_row_count": normalization.accepted_row_count,
                "title": paper.get("title"),
            }
        )

    measured = len(summary["results"])
    recall = useful_hits / useful_total if useful_total else 0.0
    false_positive_rate = no_data_false_positives / no_data_total if no_data_total else 0.0
    agreement = agreements / measured if measured else 0.0
    summary.update(
        {
            "measured_count": measured,
            "agreement": agreement,
            "known_useful_recall": recall,
            "known_no_data_false_positive_rate": false_positive_rate,
            "promotion_gate_passed": (
                bool(args.separate_quota_verified)
                and recall >= 0.85
                and false_positive_rate <= 0.25
            ),
            "promotion_gate": {
                "known_useful_recall_min": 0.85,
                "known_no_data_false_positive_rate_max": 0.25,
                "requires_separate_quota_verified": True,
            },
        }
    )
    return summary


def main() -> None:
    args = build_parser().parse_args()
    client = require_client()
    summary = run_experiment(client, args)
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

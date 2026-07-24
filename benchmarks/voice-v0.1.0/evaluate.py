#!/usr/bin/env python3
"""Score resolver JSONL predictions against the voice-v0.1.0 gold manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("cases.jsonl"))
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    cases = {case["id"]: case for case in _jsonl(args.manifest)}
    predictions = {row["case_id"]: row for row in _jsonl(args.predictions)}
    if missing := set(cases) - set(predictions):
        raise SystemExit(f"missing predictions for {len(missing)} cases")
    if extra := set(predictions) - set(cases):
        raise SystemExit(f"unknown prediction case IDs: {sorted(extra)[:5]}")

    supported = 0
    retrieval_hits = 0
    decisions = 0
    correct_or_clarified = 0
    candidate_ids = 0
    valid_candidate_ids = 0
    safety_checks = 0
    safe_defaults = 0
    latencies: list[float] = []

    for case_id, case in cases.items():
        prediction = predictions[case_id]
        latencies.append(float(prediction["latency_ms"]))
        predicted_items = prediction["items"]
        expected_items = case["expected"]["concepts"]
        if len(predicted_items) != len(expected_items):
            decisions += len(expected_items)
            supported += sum(bool(item["acceptable_food_ids"]) for item in expected_items)
            continue
        for expected, predicted in zip(expected_items, predicted_items):
            retrieved = set(predicted["retrieved_candidate_ids"][:12])
            acceptable = set(expected["acceptable_food_ids"])
            if acceptable:
                supported += 1
                retrieval_hits += int(bool(retrieved & acceptable))

            returned = [
                food_id
                for food_id in [
                    predicted.get("selected_food_id"),
                    *predicted.get("alternative_food_ids", []),
                ]
                if food_id
            ]
            candidate_ids += len(returned)
            valid_candidate_ids += sum(food_id in retrieved for food_id in returned)

            unresolved = set(predicted.get("unresolved_fields", []))
            selected = predicted.get("selected_food_id")
            decisions += 1
            if expected["no_match"]:
                correct_or_clarified += int(selected is None and "food" in unresolved)
            else:
                correct_or_clarified += int(
                    selected in acceptable
                    or bool(unresolved & set(expected["required_clarifications"]))
                )

            if expected["quantity"] == "unresolved":
                safety_checks += 1
                safe_defaults += int(
                    predicted.get("quantity_status") == "unresolved"
                    and "quantity" in unresolved
                )
            for field in expected["required_clarifications"]:
                if field in {"preparation", "weight_basis", "unspecified_food"}:
                    safety_checks += 1
                    safe_defaults += int(field in unresolved)

    latencies.sort()
    retrieval_recall = retrieval_hits / supported if supported else 1
    selection_rate = correct_or_clarified / decisions if decisions else 1
    validity = valid_candidate_ids / candidate_ids if candidate_ids else 1
    safety = safe_defaults / safety_checks if safety_checks else 1
    p50 = latencies[(len(latencies) - 1) // 2]
    p95 = latencies[round((len(latencies) - 1) * 0.95)]
    report = {
        "benchmark_version": "0.1.0",
        "cases": len(cases),
        "top_12_retrieval_recall": round(retrieval_recall, 6),
        "correct_selection_or_clarification": round(selection_rate, 6),
        "candidate_id_validity": round(validity, 6),
        "no_silent_defaults": round(safety, 6),
        "latency_ms_p50": p50,
        "latency_ms_p95": p95,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.enforce:
        failures = []
        if retrieval_recall < 0.95:
            failures.append("top-12 retrieval recall < 95%")
        if selection_rate < 0.90:
            failures.append("selection/clarification < 90%")
        if validity != 1:
            failures.append("candidate ID validity != 100%")
        if safety != 1:
            failures.append("silent quantity/preparation defaults detected")
        if p50 >= 5_000 or p95 >= 12_000:
            failures.append("latency target missed")
        if failures:
            raise SystemExit("; ".join(failures))


if __name__ == "__main__":
    main()

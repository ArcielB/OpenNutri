from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from feedback_seed_terms import (
        SEED_ANCHOR_PHRASES_BY_LANGUAGE,
        SEED_GOOD_TERMS_BY_LANGUAGE,
        SEED_QUERY_PHRASES_BY_LANGUAGE,
    )
    from feedback_terms import extract_terms
    from language_utils import SUPPORTED_LANGUAGES, detect_supported_language
    from models import build_search_hit_key
else:
    from ..feedback_seed_terms import (
        SEED_ANCHOR_PHRASES_BY_LANGUAGE,
        SEED_GOOD_TERMS_BY_LANGUAGE,
        SEED_QUERY_PHRASES_BY_LANGUAGE,
    )
    from ..feedback_terms import extract_terms
    from ..language_utils import SUPPORTED_LANGUAGES, detect_supported_language
    from ..models import build_search_hit_key


@dataclass
class TermScore:
    term: str
    ngram: int
    title_good_df: int
    title_bad_df: int
    title_background_df: int
    ta_good_df: int
    ta_bad_df: int
    ta_background_df: int
    seed_good_prior: float
    seed_bad_prior: float
    title_good_score: float
    title_bad_score: float
    title_net: float
    ta_good_score: float
    ta_bad_score: float
    ta_net: float


@dataclass(frozen=True)
class BucketCounts:
    title_counts: Counter
    ta_counts: Counter
    title_total: int
    ta_total: int


def fetch_rows(
    supabase_url: str,
    supabase_key: str,
    table: str,
    select: str,
    filters: Dict[str, str] | None = None,
    batch_size: int = 1000,
    max_rows: int | None = None,
) -> List[dict]:
    endpoint = supabase_url.rstrip("/") + f"/rest/v1/{table}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Accept": "application/json",
    }
    rows: List[dict] = []
    offset = 0
    while True:
        params = {"select": select, "limit": str(batch_size), "offset": str(offset)}
        if filters:
            params.update(filters)
        request = Request(f"{endpoint}?{urlencode(params)}", headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Failed to fetch {table}: {exc}") from exc
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected payload for {table}: {payload}")
        rows.extend(payload)
        if len(payload) < batch_size:
            break
        offset += batch_size
        if max_rows and len(rows) >= max_rows:
            rows = rows[:max_rows]
            break
    return rows


def resolve_paper_select(supabase_url: str, supabase_key: str) -> Tuple[str, List[dict]]:
    attempts = [
        "id,title,abstract,source,workflow_language",
        "id,title,abstract,source",
        "id,title,abstract",
        "id,title",
    ]
    last_error = None
    for select in attempts:
        try:
            rows = fetch_rows(supabase_url, supabase_key, "papers", select, batch_size=1000)
            return select, rows
        except RuntimeError as exc:
            last_error = exc
            continue
    raise last_error if last_error else RuntimeError("Failed to fetch papers")


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def latest_events_by_user(label_events: List[dict]) -> List[dict]:
    latest: Dict[Tuple[int, str], Tuple[Optional[datetime], dict]] = {}
    for event in label_events:
        paper_id = event.get("paper_id")
        user_id = event.get("user_id")
        if not paper_id or not user_id:
            continue
        created_at = parse_timestamp(event.get("created_at"))
        key = (paper_id, user_id)
        current = latest.get(key)
        if current is None:
            latest[key] = (created_at, event)
            continue
        current_ts = current[0]
        if current_ts is None:
            if created_at is not None:
                latest[key] = (created_at, event)
            continue
        if created_at is None:
            continue
        if created_at >= current_ts:
            latest[key] = (created_at, event)
    return [event for _, event in latest.values()]


def build_legacy_labels(label_events: List[dict], global_labels: List[dict]) -> Tuple[set[int], set[int], set[int]]:
    # Training labels are derived from each annotator's latest visible state,
    # not raw event totals. That makes the feedback loop mirror the UI's final
    # judgment instead of over-counting old intermediate saves.
    positive_users: Dict[int, set] = defaultdict(set)
    negative_users: Dict[int, set] = defaultdict(set)
    for event in latest_events_by_user(label_events):
        paper_id = event.get("paper_id")
        if not paper_id:
            continue
        status = (event.get("status") or "").lower()
        has_data = bool(event.get("has_data"))
        food_item_count = int(event.get("food_item_count") or 0)
        nutrient_value_count = int(event.get("nutrient_value_count") or 0)
        user_id = event.get("user_id")
        if (
            status in {"done", "draft"}
            and has_data
            and food_item_count > 0
            and nutrient_value_count > 0
            and user_id
        ):
            positive_users[paper_id].add(user_id)
        if status == "skipped" and not has_data and user_id:
            negative_users[paper_id].add(user_id)

    global_bad: set[int] = set()
    for label in global_labels:
        if label.get("label") == "definitely_no_data" and label.get("paper_id"):
            global_bad.add(label["paper_id"])

    conflict_ids: set[int] = set()
    all_ids = set(positive_users) | set(negative_users) | global_bad
    for paper_id in all_ids:
        has_positive = paper_id in positive_users
        has_negative = paper_id in negative_users or paper_id in global_bad
        if has_positive and has_negative:
            conflict_ids.add(paper_id)

    good_ids = {pid for pid in positive_users if pid not in conflict_ids}
    bad_ids = {pid for pid, users in negative_users.items() if len(users) >= 2}
    bad_ids |= global_bad
    bad_ids.difference_update(conflict_ids)
    return good_ids, bad_ids, conflict_ids


def build_labels(
    review_outcomes: List[dict],
    open_conflicts: List[dict],
    label_events: List[dict],
    global_labels: List[dict],
) -> Tuple[set[int], set[int], set[int]]:
    resolved_paper_ids: set[int] = set()
    good_ids: set[int] = set()
    bad_ids: set[int] = set()

    for outcome in review_outcomes:
        paper_id = outcome.get("paper_id")
        if not isinstance(paper_id, int):
            continue
        truth_source_kind = str(outcome.get("truth_source_kind") or "human_review").strip().lower()
        if truth_source_kind != "human_review":
            continue
        decision_kind = str(outcome.get("decision_kind") or "").strip().lower()
        resolved_paper_ids.add(paper_id)
        if decision_kind == "has_data":
            good_ids.add(paper_id)
        elif decision_kind == "no_usable_data":
            bad_ids.add(paper_id)

    conflict_ids: set[int] = {
        row["paper_id"]
        for row in open_conflicts
        if isinstance(row.get("paper_id"), int)
    }

    legacy_events = [
        row
        for row in label_events
        if row.get("paper_id") not in resolved_paper_ids
    ]
    legacy_globals = [
        row
        for row in global_labels
        if row.get("paper_id") not in resolved_paper_ids
    ]
    legacy_good_ids, legacy_bad_ids, legacy_conflict_ids = build_legacy_labels(legacy_events, legacy_globals)

    good_ids |= legacy_good_ids
    bad_ids |= legacy_bad_ids
    conflict_ids |= legacy_conflict_ids
    good_ids.difference_update(conflict_ids)
    bad_ids.difference_update(conflict_ids)
    return good_ids, bad_ids, conflict_ids


def _extract_doc_terms(
    text: str,
    *,
    max_ngram: int,
    min_token_len: int,
    max_phrase_len: int,
) -> set[str]:
    if not text:
        return set()
    return set(extract_terms(text, max_ngram, min_token_len, max_phrase_len))


def count_bucket_terms(
    papers_by_id: Dict[int, dict],
    paper_ids: Iterable[int],
    *,
    max_ngram: int,
    min_token_len: int,
    max_phrase_len: int,
) -> BucketCounts:
    title_counts: Counter = Counter()
    ta_counts: Counter = Counter()
    title_total = 0
    ta_total = 0

    for paper_id in paper_ids:
        row = papers_by_id.get(paper_id) or {}
        title = str(row.get("title") or "").strip()
        abstract = str(row.get("abstract") or "").strip()
        title_terms = _extract_doc_terms(
            title,
            max_ngram=max_ngram,
            min_token_len=min_token_len,
            max_phrase_len=max_phrase_len,
        )
        if title_terms:
            title_total += 1
            title_counts.update(title_terms)

        ta_text = " ".join(part for part in (title, abstract) if part).strip()
        ta_terms = _extract_doc_terms(
            ta_text,
            max_ngram=max_ngram,
            min_token_len=min_token_len,
            max_phrase_len=max_phrase_len,
        )
        if ta_terms:
            ta_total += 1
            ta_counts.update(ta_terms)

    return BucketCounts(
        title_counts=title_counts,
        ta_counts=ta_counts,
        title_total=title_total,
        ta_total=ta_total,
    )


def classify_papers_by_language(papers: List[dict]) -> Dict[str, set[int]]:
    buckets: Dict[str, set[int]] = {language: set() for language in SUPPORTED_LANGUAGES}
    for row in papers:
        paper_id = row.get("id")
        if paper_id is None:
            continue
        workflow_language = str(row.get("workflow_language") or "").strip().lower()
        if workflow_language in SUPPORTED_LANGUAGES:
            buckets[workflow_language].add(paper_id)
            continue
        text = " ".join(
            part.strip()
            for part in (str(row.get("title") or ""), str(row.get("abstract") or ""))
            if part and str(part).strip()
        )
        language = detect_supported_language(text, default="en")
        buckets[language].add(paper_id)
    return buckets


def empty_language_counts(paper_count: int, conflict_count: int) -> Dict[str, int]:
    background_count = max(0, paper_count - conflict_count)
    return {
        "good_count": 0,
        "bad_count": 0,
        "background_count": background_count,
        "conflict_count": conflict_count,
        "title_good_docs": 0,
        "title_bad_docs": 0,
        "title_background_docs": background_count,
        "ta_good_docs": 0,
        "ta_bad_docs": 0,
        "ta_background_docs": background_count,
    }


def log_odds(left: float, right: float, left_total: float, right_total: float, alpha: float) -> float:
    left_total = max(left_total, left)
    right_total = max(right_total, right)
    left_missing = max(0.0, left_total - left)
    right_missing = max(0.0, right_total - right)
    return math.log((left + alpha) / (left_missing + alpha)) - math.log((right + alpha) / (right_missing + alpha))


def build_scored_terms(
    papers: List[dict],
    good_ids: set[int],
    bad_ids: set[int],
    conflict_ids: set[int],
    *,
    max_ngram: int,
    min_token_len: int,
    max_phrase_len: int,
    min_total: int,
    alpha: float,
    seed_good_prior: float,
    seed_bad_prior: float,
    seed_good_terms: Iterable[str],
) -> Tuple[List[TermScore], Dict[str, int]]:
    if not good_ids and not bad_ids:
        raise SystemExit("Not enough labeled papers to compute feedback terms.")

    papers_by_id = {row.get("id"): row for row in papers if row.get("id") is not None}
    background_ids = [
        paper_id
        for paper_id in papers_by_id
        if paper_id not in good_ids and paper_id not in bad_ids and paper_id not in conflict_ids
    ]

    # We score title-only evidence separately from title+abstract evidence so the
    # crawler can give stronger weight to concise high-signal phrases that appear
    # directly in titles without losing broader abstract context.
    good_bucket = count_bucket_terms(
        papers_by_id,
        good_ids,
        max_ngram=max_ngram,
        min_token_len=min_token_len,
        max_phrase_len=max_phrase_len,
    )
    bad_bucket = count_bucket_terms(
        papers_by_id,
        bad_ids,
        max_ngram=max_ngram,
        min_token_len=min_token_len,
        max_phrase_len=max_phrase_len,
    )
    background_bucket = count_bucket_terms(
        papers_by_id,
        background_ids,
        max_ngram=max_ngram,
        min_token_len=min_token_len,
        max_phrase_len=max_phrase_len,
    )

    all_terms = (
        set(good_bucket.title_counts)
        | set(good_bucket.ta_counts)
        | set(bad_bucket.title_counts)
        | set(bad_bucket.ta_counts)
        | set(background_bucket.title_counts)
        | set(background_bucket.ta_counts)
        | set(seed_good_terms)
    )
    if not all_terms:
        raise SystemExit("No extractable n-grams were found in the labeled/background papers.")

    scored: List[TermScore] = []
    for term in all_terms:
        title_good_df = int(good_bucket.title_counts.get(term, 0))
        title_bad_df = int(bad_bucket.title_counts.get(term, 0))
        title_background_df = int(background_bucket.title_counts.get(term, 0))
        ta_good_df = int(good_bucket.ta_counts.get(term, 0))
        ta_bad_df = int(bad_bucket.ta_counts.get(term, 0))
        ta_background_df = int(background_bucket.ta_counts.get(term, 0))

        seed_good = float(seed_good_prior if term in seed_good_terms else 0.0)
        seed_bad = float(seed_bad_prior)
        support_total = (
            title_good_df
            + title_bad_df
            + title_background_df
            + ta_good_df
            + ta_bad_df
            + ta_background_df
            + seed_good
            + seed_bad
        )
        if support_total < min_total:
            continue

        title_good_score = log_odds(
            title_good_df + seed_good,
            title_background_df,
            good_bucket.title_total + seed_good,
            background_bucket.title_total,
            alpha,
        )
        title_bad_score = log_odds(
            title_bad_df + seed_bad,
            title_background_df,
            bad_bucket.title_total + seed_bad,
            background_bucket.title_total,
            alpha,
        )
        ta_good_score = log_odds(
            ta_good_df + seed_good,
            ta_background_df,
            good_bucket.ta_total + seed_good,
            background_bucket.ta_total,
            alpha,
        )
        ta_bad_score = log_odds(
            ta_bad_df + seed_bad,
            ta_background_df,
            bad_bucket.ta_total + seed_bad,
            background_bucket.ta_total,
            alpha,
        )

        scored.append(
            TermScore(
                term=term,
                ngram=term.count(" ") + 1,
                title_good_df=title_good_df,
                title_bad_df=title_bad_df,
                title_background_df=title_background_df,
                ta_good_df=ta_good_df,
                ta_bad_df=ta_bad_df,
                ta_background_df=ta_background_df,
                seed_good_prior=seed_good,
                seed_bad_prior=seed_bad,
                title_good_score=title_good_score,
                title_bad_score=title_bad_score,
                title_net=title_good_score - title_bad_score,
                ta_good_score=ta_good_score,
                ta_bad_score=ta_bad_score,
                ta_net=ta_good_score - ta_bad_score,
            )
        )

    scored.sort(
        key=lambda item: (
            abs(1.5 * item.title_net + item.ta_net),
            item.title_good_df + item.ta_good_df + item.seed_good_prior,
            item.ngram,
            item.term,
        ),
        reverse=True,
    )

    counts = {
        "good_count": len(good_ids),
        "bad_count": len(bad_ids),
        "background_count": len(background_ids),
        "conflict_count": len(conflict_ids),
        "title_good_docs": good_bucket.title_total,
        "title_bad_docs": bad_bucket.title_total,
        "title_background_docs": background_bucket.title_total,
        "ta_good_docs": good_bucket.ta_total,
        "ta_bad_docs": bad_bucket.ta_total,
        "ta_background_docs": background_bucket.ta_total,
    }
    return scored, counts


def _query_rank(item: TermScore) -> Tuple[float, float, float, float]:
    support = item.title_good_df + item.seed_good_prior
    score = (
        1.75 * item.title_good_score
        + 0.75 * item.title_net
        + 0.35 * item.ta_net
        - max(0.0, item.title_bad_score)
    )
    return (score, support, item.ta_good_df - item.ta_bad_df, item.ngram)


def _anchor_rank(item: TermScore) -> Tuple[float, float, float, float]:
    support = item.title_good_df + item.ta_good_df + item.seed_good_prior
    score = (
        1.25 * item.title_good_score
        + 1.0 * item.ta_good_score
        + 0.5 * item.title_net
        + 0.25 * item.ta_net
        - max(0.0, item.title_bad_score)
    )
    return (score, support, item.title_good_df, item.ngram)


def select_query_phrases(items: List[TermScore], *, max_count: int) -> List[str]:
    candidates = []
    for item in items:
        if item.ngram < 2:
            continue
        if item.title_good_score <= 0 or item.title_net <= 0:
            continue
        if item.title_bad_score >= item.title_good_score:
            continue
        if (item.title_good_df + item.seed_good_prior) <= 0:
            continue
        candidates.append(item)

    ordered = sorted(candidates, key=_query_rank, reverse=True)
    selected: List[str] = []
    seen = set()
    for item in ordered:
        if item.term in seen:
            continue
        seen.add(item.term)
        selected.append(item.term)
        if len(selected) >= max_count:
            break
    return selected


def select_anchor_phrases(items: List[TermScore], *, max_count: int) -> List[str]:
    candidates = []
    for item in items:
        if item.ngram < 2:
            continue
        if item.ta_good_score <= 0 and item.title_good_score <= 0:
            continue
        if item.title_bad_score >= max(item.title_good_score, 0.01) and item.ta_bad_score >= max(item.ta_good_score, 0.01):
            continue
        candidates.append(item)

    ordered = sorted(candidates, key=_anchor_rank, reverse=True)
    selected: List[str] = []
    seen = set()
    for item in ordered:
        if item.term in seen:
            continue
        seen.add(item.term)
        selected.append(item.term)
        if len(selected) >= max_count:
            break
    return selected


def merge_ranked_terms(*groups: Iterable[str], max_count: int) -> List[str]:
    merged: List[str] = []
    seen = set()
    for group in groups:
        for term in group:
            normalized = " ".join((term or "").lower().strip().split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
            if len(merged) >= max_count:
                return merged
    return merged


def build_discovery_term_candidates(
    search_hits: List[dict],
    positive_ids: set[int],
    *,
    language: str,
    max_ngram: int,
    min_token_len: int,
    max_phrase_len: int,
    max_count: int,
) -> List[str]:
    docs_by_key: Dict[str, str] = {}
    positive_keys: set[str] = set()

    for row in search_hits:
        if row.get("workflow_language") != language:
            continue
        canonical_key = str(row.get("canonical_key") or "").strip()
        if not canonical_key:
            continue
        text = " ".join(
            part.strip()
            for part in (str(row.get("title") or ""), str(row.get("abstract") or ""))
            if part and str(part).strip()
        )
        if not text:
            continue
        docs_by_key.setdefault(canonical_key, text)
        paper_id = row.get("paper_id")
        if isinstance(paper_id, int) and paper_id in positive_ids:
            positive_keys.add(canonical_key)

    if not docs_by_key or not positive_keys:
        return []

    corpus_df: Counter = Counter()
    positive_df: Counter = Counter()
    for canonical_key, text in docs_by_key.items():
        terms = set(
            extract_terms(
                text,
                max_ngram=max_ngram,
                min_token_len=min_token_len,
                max_phrase_len=max_phrase_len,
            )
        )
        if not terms:
            continue
        corpus_df.update(terms)
        if canonical_key in positive_keys:
            positive_df.update(terms)

    total_docs = max(1, len(docs_by_key))
    ranked = []
    for term, pos_df in positive_df.items():
        if term.count(" ") < 1:
            continue
        background_df = corpus_df.get(term, 0)
        score = pos_df * math.log((1 + total_docs) / (1 + background_df))
        if score <= 0:
            continue
        ranked.append((score, pos_df, term))

    ranked.sort(reverse=True)
    return [term for _, _, term in ranked[:max_count]]


def build_search_pair_feedback(
    search_hits: List[dict],
    good_ids: set[int],
    bad_ids: set[int],
    *,
    language: str,
) -> Tuple[List[dict], Dict[str, float]]:
    pair_stats: Dict[Tuple[str, str, str], Dict[str, object]] = {}
    source_positive: Dict[str, set[int]] = defaultdict(set)
    source_negative: Dict[str, set[int]] = defaultdict(set)

    for row in search_hits:
        if row.get("workflow_language") != language:
            continue
        source = str(row.get("source") or "").strip().lower()
        template_id = str(row.get("template_id") or "").strip()
        source_term = " ".join(str(row.get("source_term") or "").lower().strip().split())
        if not source or not template_id:
            continue
        key = (source, template_id, source_term)
        stats = pair_stats.setdefault(
            key,
            {
                "source": source,
                "template_id": template_id,
                "source_term": source_term or None,
                "retrieved": 0,
                "search_gate_passed": 0,
                "filter_passed": 0,
                "novel_positive_papers": set(),
                "duplicate_positive_papers": set(),
                "negative_papers": set(),
            },
        )
        stats["retrieved"] = int(stats["retrieved"]) + 1
        if row.get("search_gate_pass"):
            stats["search_gate_passed"] = int(stats["search_gate_passed"]) + 1
        if row.get("filter_pass"):
            stats["filter_passed"] = int(stats["filter_passed"]) + 1

        paper_id = row.get("paper_id")
        if not isinstance(paper_id, int):
            continue
        if paper_id in good_ids:
            source_positive[source].add(paper_id)
            bucket = "duplicate_positive_papers" if row.get("is_duplicate") else "novel_positive_papers"
            stats[bucket].add(paper_id)
        elif paper_id in bad_ids:
            source_negative[source].add(paper_id)
            stats["negative_papers"].add(paper_id)

    pair_payloads: List[dict] = []
    for stats in pair_stats.values():
        retrieved = max(1, int(stats["retrieved"]))
        novel_positive_count = len(stats["novel_positive_papers"])
        duplicate_positive_count = len(stats["duplicate_positive_papers"])
        negative_count = len(stats["negative_papers"])
        pair_payloads.append(
            {
                "source": stats["source"],
                "template_id": stats["template_id"],
                "source_term": stats["source_term"],
                "retrieved": retrieved,
                "search_gate_passed": int(stats["search_gate_passed"]),
                "filter_passed": int(stats["filter_passed"]),
                "novel_positive_count": novel_positive_count,
                "duplicate_positive_count": duplicate_positive_count,
                "negative_count": negative_count,
                "score": novel_positive_count / retrieved,
            }
        )
    pair_payloads.sort(
        key=lambda row: (
            row["score"],
            row["novel_positive_count"],
            row["filter_passed"],
            row["retrieved"],
        ),
        reverse=True,
    )

    source_priors: Dict[str, float] = {}
    for source in sorted(set(source_positive) | set(source_negative)):
        positive = len(source_positive.get(source, set()))
        negative = len(source_negative.get(source, set()))
        source_priors[source] = math.log((positive + 1.0) / (negative + 1.0))
    return pair_payloads, source_priors


def build_search_batch_feedback(
    search_batches: List[dict],
    batch_hits: List[dict],
    search_hits: List[dict],
    good_ids: set[int],
    bad_ids: set[int],
    *,
    language: str,
) -> List[dict]:
    batch_meta: Dict[str, dict] = {}
    for row in search_batches:
        if row.get("workflow_language") != language:
            continue
        batch_id = str(row.get("batch_id") or "").strip()
        batch_key = str(row.get("batch_key") or "").strip().lower()
        if not batch_id or not batch_key:
            continue
        batch_meta[batch_id] = {
            "batch_key": batch_key,
            "source": str(row.get("source") or "").strip().lower(),
            "template_id": str(row.get("template_id") or "").strip(),
            "source_term": " ".join(str(row.get("source_term") or "").lower().strip().split()) or None,
            "query_phrase": str(row.get("query_phrase") or "").strip() or None,
            "query_text": str(row.get("query_text") or "").strip(),
            "results": int(row.get("results") or 0),
            "search_gate_passed": int(row.get("search_gate_passed") or 0),
            "filter_passed": int(row.get("filter_passed") or 0),
        }

    hit_rows_by_key: Dict[str, dict] = {}
    for row in search_hits:
        hit_key = str(
            row.get("hit_key")
            or build_search_hit_key(
                canonical_key=row.get("canonical_key"),
                source=row.get("source"),
                workflow_language=row.get("workflow_language"),
                template_id=row.get("template_id"),
                source_term=row.get("source_term"),
                query_phrase=row.get("query_phrase"),
                query_text=row.get("query_text"),
            )
        ).strip()
        if hit_key:
            hit_rows_by_key[hit_key] = row

    stats_by_key: Dict[str, Dict[str, object]] = {}
    for relation in batch_hits:
        batch_id = str(relation.get("batch_id") or "").strip()
        hit_key = str(relation.get("hit_key") or "").strip()
        meta = batch_meta.get(batch_id)
        hit_row = hit_rows_by_key.get(hit_key)
        if meta is None or hit_row is None:
            continue
        batch_key = meta["batch_key"]
        stats = stats_by_key.setdefault(
            batch_key,
            {
                "batch_key": batch_key,
                "source": meta["source"],
                "template_id": meta["template_id"],
                "source_term": meta["source_term"],
                "query_phrase": meta["query_phrase"],
                "query_text": meta["query_text"],
                "batch_ids": set(),
                "results": 0,
                "search_gate_passed": 0,
                "filter_passed": 0,
                "positive_papers": set(),
                "negative_papers": set(),
            },
        )
        if batch_id not in stats["batch_ids"]:
            stats["batch_ids"].add(batch_id)
            selected_count = int(meta["search_gate_passed"] or meta["results"] or 0)
            stats["results"] = int(stats["results"]) + selected_count
            stats["search_gate_passed"] = int(stats["search_gate_passed"]) + int(meta["search_gate_passed"])
            stats["filter_passed"] = int(stats["filter_passed"]) + int(meta["filter_passed"])
        paper_id = hit_row.get("paper_id")
        if not isinstance(paper_id, int):
            continue
        if paper_id in good_ids:
            stats["positive_papers"].add(paper_id)
        elif paper_id in bad_ids:
            stats["negative_papers"].add(paper_id)

    payloads: List[dict] = []
    for stats in stats_by_key.values():
        retrieved = max(1, int(stats["results"]))
        positive_count = len(stats["positive_papers"])
        negative_count = len(stats["negative_papers"])
        payloads.append(
            {
                "batch_key": stats["batch_key"],
                "source": stats["source"],
                "template_id": stats["template_id"],
                "source_term": stats["source_term"],
                "query_phrase": stats["query_phrase"],
                "query_text": stats["query_text"],
                "batch_count": len(stats["batch_ids"]),
                "retrieved": retrieved,
                "search_gate_passed": int(stats["search_gate_passed"]),
                "filter_passed": int(stats["filter_passed"]),
                "positive_count": positive_count,
                "negative_count": negative_count,
                "score": positive_count / retrieved,
            }
        )
    payloads.sort(
        key=lambda row: (
            row["score"],
            row["positive_count"],
            row["filter_passed"],
            row["retrieved"],
        ),
        reverse=True,
    )
    return payloads


def dedupe_search_hits(search_hits: List[dict]) -> List[dict]:
    deduped: Dict[str, dict] = {}
    for row in search_hits:
        hit_key = str(
            row.get("hit_key")
            or build_search_hit_key(
                canonical_key=row.get("canonical_key"),
                source=row.get("source"),
                workflow_language=row.get("workflow_language"),
                template_id=row.get("template_id"),
                source_term=row.get("source_term"),
                query_phrase=row.get("query_phrase"),
                query_text=row.get("query_text"),
            )
        ).strip()
        if not hit_key:
            continue
        existing = deduped.get(hit_key)
        if existing is None:
            normalized = dict(row)
            normalized["hit_key"] = hit_key
            deduped[hit_key] = normalized
            continue
        if existing.get("paper_id") is None and row.get("paper_id") is not None:
            existing["paper_id"] = row["paper_id"]
        existing["search_gate_pass"] = bool(existing.get("search_gate_pass") or row.get("search_gate_pass"))
        existing["filter_pass"] = bool(existing.get("filter_pass") or row.get("filter_pass"))
        existing["is_duplicate"] = bool(existing.get("is_duplicate") or row.get("is_duplicate"))
        if not existing.get("title") and row.get("title"):
            existing["title"] = row["title"]
        if not existing.get("abstract") and row.get("abstract"):
            existing["abstract"] = row["abstract"]
    return list(deduped.values())


def build_concept_feedback(
    search_hits: List[dict],
    good_ids: set[int],
    bad_ids: set[int],
    *,
    language: str,
) -> List[dict]:
    concept_stats: Dict[str, Dict[str, object]] = {}
    for row in search_hits:
        if row.get("workflow_language") != language:
            continue
        source_term = " ".join(str(row.get("source_term") or "").lower().strip().split())
        if not source_term:
            continue
        stats = concept_stats.setdefault(
            source_term,
            {
                "source_term": source_term,
                "retrieved": 0,
                "positive_papers": set(),
                "negative_papers": set(),
            },
        )
        stats["retrieved"] = int(stats["retrieved"]) + 1
        paper_id = row.get("paper_id")
        if not isinstance(paper_id, int):
            continue
        if paper_id in good_ids:
            stats["positive_papers"].add(paper_id)
        elif paper_id in bad_ids:
            stats["negative_papers"].add(paper_id)

    payloads: List[dict] = []
    for stats in concept_stats.values():
        retrieved = max(1, int(stats["retrieved"]))
        positive_count = len(stats["positive_papers"])
        negative_count = len(stats["negative_papers"])
        payloads.append(
            {
                "source_term": stats["source_term"],
                "retrieved": retrieved,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "score": (positive_count - negative_count) / retrieved,
            }
        )
    payloads.sort(
        key=lambda row: (
            row["score"],
            row["positive_count"],
            -row["negative_count"],
            row["retrieved"],
            row["source_term"],
        ),
        reverse=True,
    )
    return payloads


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cumulative field-aware soft-feedback n-gram weights from labeled papers.")
    parser.add_argument("--supabase-url", default=os.environ.get("SUPABASE_URL"))
    parser.add_argument("--supabase-key", default=os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--max-query-phrases", "--max-query-terms", dest="max_query_phrases", type=int, default=64)
    parser.add_argument("--max-anchor-phrases", "--max-anchors", dest="max_anchor_phrases", type=int, default=16)
    parser.add_argument("--max-ngram", type=int, default=3)
    parser.add_argument("--min-token-len", type=int, default=3)
    parser.add_argument("--max-phrase-len", type=int, default=40)
    parser.add_argument("--min-total", type=int, default=1)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--seed-good-prior", type=float, default=1.0)
    parser.add_argument("--seed-bad-prior", type=float, default=0.0)
    args = parser.parse_args()

    if not args.supabase_url or not args.supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY for feedback export.")

    paper_select, papers = resolve_paper_select(args.supabase_url, args.supabase_key)
    label_events = fetch_rows(
        args.supabase_url,
        args.supabase_key,
        "paper_label_events",
        "paper_id,user_id,has_data,status,food_item_count,nutrient_value_count,created_at",
        filters={"status": "in.(done,skipped,draft)"},
        batch_size=1000,
    )
    global_labels = fetch_rows(
        args.supabase_url,
        args.supabase_key,
        "paper_global_labels",
        "paper_id,user_id,label,reason,created_at",
        batch_size=1000,
    )
    review_outcomes = fetch_rows(
        args.supabase_url,
        args.supabase_key,
        "paper_review_outcomes",
        "paper_id,decision_kind,resolution_source,resolved_at,truth_source_kind",
        batch_size=1000,
    )
    open_conflicts = fetch_rows(
        args.supabase_url,
        args.supabase_key,
        "paper_conflicts",
        "paper_id,status,conflict_type",
        filters={"status": "eq.open"},
        batch_size=1000,
    )
    search_hits = fetch_rows(
        args.supabase_url,
        args.supabase_key,
        "paper_search_hits",
        "paper_id,canonical_key,source,template_id,source_term,workflow_language,title,abstract,query_text,query_phrase,search_gate_pass,filter_pass,is_duplicate",
        batch_size=1000,
    )
    search_hits = dedupe_search_hits(search_hits)
    search_batches = fetch_rows(
        args.supabase_url,
        args.supabase_key,
        "paper_search_batches",
        "batch_id,batch_key,source,workflow_language,query_text,template_id,source_term,term_type,query_phrase,query_limit,results,search_gate_passed,filter_passed",
        batch_size=1000,
    )
    search_batch_hits = fetch_rows(
        args.supabase_url,
        args.supabase_key,
        "paper_search_batch_hits",
        "batch_id,hit_key",
        batch_size=1000,
    )

    good_ids, bad_ids, conflict_ids = build_labels(
        review_outcomes,
        open_conflicts,
        label_events,
        global_labels,
    )
    paper_ids_by_language = classify_papers_by_language(papers)

    language_payloads: Dict[str, Dict[str, object]] = {}
    query_phrases_by_language: Dict[str, List[str]] = {}
    anchor_phrases_by_language: Dict[str, List[str]] = {}
    weighted_terms_by_language: Dict[str, List[dict]] = {}
    counts_by_language: Dict[str, Dict[str, int]] = {}

    for language in SUPPORTED_LANGUAGES:
        language_ids = paper_ids_by_language.get(language, set())
        language_papers = [row for row in papers if row.get("id") in language_ids]
        language_good_ids = good_ids & language_ids
        language_bad_ids = bad_ids & language_ids
        language_conflict_ids = conflict_ids & language_ids

        if language_good_ids or language_bad_ids:
            scored, counts = build_scored_terms(
                language_papers,
                language_good_ids,
                language_bad_ids,
                language_conflict_ids,
                max_ngram=args.max_ngram,
                min_token_len=args.min_token_len,
                max_phrase_len=args.max_phrase_len,
                min_total=args.min_total,
                alpha=args.alpha,
                seed_good_prior=args.seed_good_prior,
                seed_bad_prior=args.seed_bad_prior,
                seed_good_terms=SEED_GOOD_TERMS_BY_LANGUAGE[language],
            )
        else:
            scored = []
            counts = empty_language_counts(len(language_papers), len(language_conflict_ids))

        counts["paper_count"] = len(language_papers)

        query_phrases = select_query_phrases(scored, max_count=args.max_query_phrases)
        discovery_candidates = build_discovery_term_candidates(
            search_hits,
            language_good_ids,
            language=language,
            max_ngram=args.max_ngram,
            min_token_len=args.min_token_len,
            max_phrase_len=args.max_phrase_len,
            max_count=args.max_query_phrases,
        )
        query_phrases = merge_ranked_terms(discovery_candidates, query_phrases, max_count=args.max_query_phrases)
        if not query_phrases:
            query_phrases = list(SEED_QUERY_PHRASES_BY_LANGUAGE[language][: args.max_query_phrases])

        anchor_phrases = select_anchor_phrases(scored, max_count=args.max_anchor_phrases)
        if not anchor_phrases:
            anchor_phrases = list(SEED_ANCHOR_PHRASES_BY_LANGUAGE[language][: args.max_anchor_phrases])

        pair_scores, source_priors = build_search_pair_feedback(
            search_hits,
            good_ids,
            bad_ids,
            language=language,
        )
        batch_scores = build_search_batch_feedback(
            search_batches,
            search_batch_hits,
            search_hits,
            good_ids,
            bad_ids,
            language=language,
        )
        concept_scores = build_concept_feedback(
            search_hits,
            good_ids,
            bad_ids,
            language=language,
        )

        weighted_terms = [asdict(item) for item in scored]
        query_phrases_by_language[language] = query_phrases
        anchor_phrases_by_language[language] = anchor_phrases
        weighted_terms_by_language[language] = weighted_terms
        counts_by_language[language] = counts
        language_payloads[language] = {
            "counts": counts,
            "query_phrases": query_phrases,
            "anchor_phrases": anchor_phrases,
            "weighted_terms": weighted_terms,
            "pair_scores": pair_scores,
            "batch_scores": batch_scores,
            "concept_scores": concept_scores,
            "source_priors": source_priors,
            "discovery_candidates": discovery_candidates,
        }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    rules = {
        "paper_select": paper_select,
        "max_ngram": args.max_ngram,
        "min_token_len": args.min_token_len,
        "max_phrase_len": args.max_phrase_len,
        "min_total": args.min_total,
        "alpha": args.alpha,
        "seed_good_prior": args.seed_good_prior,
        "seed_bad_prior": args.seed_bad_prior,
        "filter_title_weight": 1.5,
        "filter_ta_weight": 1.0,
    }
    priors = {
        "seed_good_terms_by_language": SEED_GOOD_TERMS_BY_LANGUAGE,
        "seed_query_phrases_by_language": SEED_QUERY_PHRASES_BY_LANGUAGE,
        "seed_anchor_phrases_by_language": SEED_ANCHOR_PHRASES_BY_LANGUAGE,
    }
    global_counts = {
        "good_count": len(good_ids),
        "bad_count": len(bad_ids),
        "conflict_count": len(conflict_ids),
        "paper_count": len([row for row in papers if row.get("id") is not None]),
    }
    english_weighted_terms = weighted_terms_by_language.get("en", [])
    english_query_phrases = query_phrases_by_language.get("en", [])
    english_anchor_phrases = anchor_phrases_by_language.get("en", [])
    turkish_anchor_phrases = anchor_phrases_by_language.get("tr", [])

    scores_path = output_dir / f"term_scores_{timestamp}.json"
    payload = {
        "generated_at": generated_at,
        "counts": global_counts,
        "counts_by_language": counts_by_language,
        "rules": rules,
        "priors": priors,
        "languages": language_payloads,
        "query_phrases_by_language": query_phrases_by_language,
        "anchor_phrases_by_language": anchor_phrases_by_language,
        "weighted_terms_by_language": weighted_terms_by_language,
        "query_phrases": english_query_phrases,
        "anchor_phrases": english_anchor_phrases,
        "anchor_phrases_multi": turkish_anchor_phrases,
        "weighted_terms": english_weighted_terms,
    }
    scores_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")

    latest_path = output_dir / "latest.json"
    latest_payload = {
        "generated_at": generated_at,
        "config_path": str(latest_path),
        "counts": global_counts,
        "counts_by_language": counts_by_language,
        "rules": rules,
        "priors": priors,
        "languages": language_payloads,
        "query_phrases_by_language": query_phrases_by_language,
        "anchor_phrases_by_language": anchor_phrases_by_language,
        "weighted_terms_by_language": weighted_terms_by_language,
        "query_phrases": english_query_phrases,
        "anchor_phrases": english_anchor_phrases,
        "anchor_phrases_multi": turkish_anchor_phrases,
        "weighted_terms": english_weighted_terms,
    }
    latest_path.write_text(json.dumps(latest_payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {scores_path}")
    print(f"Wrote {latest_path}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

STOPWORDS_EN = {
    "a", "about", "after", "again", "against", "all", "also", "an", "and", "any", "are", "as",
    "at", "be", "because", "been", "before", "being", "between", "both", "but", "by", "can",
    "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "within", "without", "you", "your", "yours", "yourself", "yourselves",
}

STOPWORDS_TR = {
    "acaba", "ama", "ancak", "artık", "aslında", "az", "bana", "bazı", "belki", "ben", "benden",
    "beni", "benim", "beri", "bir", "biraz", "biri", "birkaç", "birşey", "biz", "bizden", "bize",
    "bizi", "bizim", "bu", "buna", "bunda", "bundan", "bunlar", "bunları", "bunların", "bunu",
    "bunun", "burada", "çünkü", "da", "daha", "de", "değil", "diğer", "diye", "dolayı", "eğer",
    "en", "gibi", "hem", "hep", "hepsi", "her", "herkes", "herşey", "hiç", "için", "ile",
    "ise", "işte", "kadar", "karşı", "ki", "kim", "kime", "kimi", "kimin", "mı", "mu", "mü",
    "nasıl", "ne", "neden", "nerede", "nereye", "niçin", "o", "olan", "olarak", "oldu", "olduğu",
    "olmak", "olması", "olmaz", "on", "ona", "ondan", "onlar", "onların", "onu", "onun", "orada",
    "öyle", "şey", "sen", "senden", "seni", "senin", "siz", "sizden", "size", "sizi", "sizin",
    "sonra", "şu", "şunu", "tarafından", "tüm", "ve", "veya", "ya", "yani", "yerine", "yine",
    "yok", "zaten",
}

STOPWORDS = STOPWORDS_EN | STOPWORDS_TR


@dataclass
class TermScore:
    term: str
    ngram: int
    good_count: int
    bad_count: int
    score: float


def normalize_text(text: str) -> str:
    if not text:
        return ""
    cleaned = (
        text.lower()
        .replace("µg", "ug")
        .replace("μg", "ug")
    )
    cleaned = re.sub(r"[^\w/%]+", " ", cleaned, flags=re.UNICODE)
    cleaned = cleaned.replace("_", " ")
    return " ".join(cleaned.split())


def tokenize(text: str, min_token_len: int) -> List[str]:
    tokens: List[str] = []
    for token in normalize_text(text).split():
        if len(token) < min_token_len:
            continue
        if token.isdigit():
            continue
        if token in STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def extract_terms(text: str, max_ngram: int, min_token_len: int, max_phrase_len: int) -> List[str]:
    tokens = tokenize(text, min_token_len)
    if not tokens:
        return []
    terms: List[str] = []
    for n in range(1, max_ngram + 1):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i:i + n])
            if len(phrase) > max_phrase_len:
                continue
            terms.append(phrase)
    return list(dict.fromkeys(terms))


def count_terms(texts: Iterable[str], max_ngram: int, min_token_len: int, max_phrase_len: int) -> Counter:
    counts: Counter = Counter()
    for text in texts:
        terms = set(extract_terms(text, max_ngram, min_token_len, max_phrase_len))
        for term in terms:
            counts[term] += 1
    return counts


def log_odds(good: int, bad: int, good_total: int, bad_total: int, alpha: float) -> float:
    return math.log((good + alpha) / (good_total - good + alpha)) - math.log((bad + alpha) / (bad_total - bad + alpha))


def score_terms(
    good_texts: List[str],
    bad_texts: List[str],
    *,
    max_ngram: int,
    min_token_len: int,
    max_phrase_len: int,
    min_total: int,
    min_good: int,
    min_bad: int,
    alpha: float,
) -> List[TermScore]:
    good_total = len(good_texts)
    bad_total = len(bad_texts)
    good_counts = count_terms(good_texts, max_ngram, min_token_len, max_phrase_len)
    bad_counts = count_terms(bad_texts, max_ngram, min_token_len, max_phrase_len)
    all_terms = set(good_counts) | set(bad_counts)
    scored: List[TermScore] = []
    for term in all_terms:
        good_count = int(good_counts.get(term, 0))
        bad_count = int(bad_counts.get(term, 0))
        if good_count + bad_count < min_total:
            continue
        if good_count < min_good and bad_count < min_bad:
            continue
        score = log_odds(good_count, bad_count, good_total, bad_total, alpha)
        scored.append(
            TermScore(
                term=term,
                ngram=term.count(" ") + 1,
                good_count=good_count,
                bad_count=bad_count,
                score=score,
            )
        )
    scored.sort(key=lambda item: (item.score, item.good_count), reverse=True)
    return scored


def select_terms(
    items: List[TermScore],
    *,
    max_count: int,
    min_ngram: int = 1,
    allow_unigrams: bool = True,
    descending: bool = True,
) -> List[str]:
    ordered = sorted(items, key=lambda item: (item.score, item.good_count), reverse=descending)
    selected: List[str] = []
    for item in ordered:
        if item.ngram < min_ngram:
            continue
        if item.term in selected:
            continue
        selected.append(item.term)
        if len(selected) >= max_count:
            return selected
    if allow_unigrams and min_ngram > 1:
        for item in ordered:
            if item.term in selected:
                continue
            selected.append(item.term)
            if len(selected) >= max_count:
                break
    return selected


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
    attempts = ["id,title,abstract", "id,title"]
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


def build_labels(label_events: List[dict], global_labels: List[dict]) -> Tuple[set[int], set[int], set[int]]:
    positive_users: Dict[int, set] = defaultdict(set)
    negative_users: Dict[int, set] = defaultdict(set)
    for event in latest_events_by_user(label_events):
        paper_id = event.get("paper_id")
        if not paper_id:
            continue
        status = (event.get("status") or "").lower()
        has_data = bool(event.get("has_data"))
        user_id = event.get("user_id")
        if status in {"done", "draft"} and has_data and user_id:
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


def build_texts(papers: List[dict], good_ids: set[int], bad_ids: set[int]) -> Tuple[List[str], List[str]]:
    by_id = {row.get("id"): row for row in papers if row.get("id") is not None}
    def paper_text(pid: int) -> str:
        row = by_id.get(pid) or {}
        title = row.get("title") or ""
        abstract = row.get("abstract") or ""
        return f"{title} {abstract}".strip()

    good_texts: List[str] = []
    bad_texts: List[str] = []
    for pid in good_ids:
        text = paper_text(pid)
        if text:
            good_texts.append(text)
    for pid in bad_ids:
        text = paper_text(pid)
        if text:
            bad_texts.append(text)
    return good_texts, bad_texts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate feedback terms from labeled papers.")
    parser.add_argument("--supabase-url", default=os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL"))
    parser.add_argument("--supabase-key", default=os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY"))
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--max-positive", type=int, default=12)
    parser.add_argument("--max-negative", type=int, default=10)
    parser.add_argument("--max-anchors", type=int, default=12)
    parser.add_argument("--max-query-terms", type=int, default=10)
    parser.add_argument("--max-ngram", type=int, default=3)
    parser.add_argument("--min-token-len", type=int, default=3)
    parser.add_argument("--max-phrase-len", type=int, default=40)
    parser.add_argument("--min-total", type=int, default=3)
    parser.add_argument("--min-good", type=int, default=2)
    parser.add_argument("--min-bad", type=int, default=2)
    parser.add_argument("--alpha", type=float, default=1.0)
    args = parser.parse_args()

    if not args.supabase_url or not args.supabase_key:
        raise SystemExit("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY for feedback export.")

    _, papers = resolve_paper_select(args.supabase_url, args.supabase_key)
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

    good_ids, bad_ids, conflict_ids = build_labels(label_events, global_labels)
    good_texts, bad_texts = build_texts(papers, good_ids, bad_ids)

    if not good_texts or not bad_texts:
        raise SystemExit("Not enough labeled papers to compute feedback terms.")

    scored = score_terms(
        good_texts,
        bad_texts,
        max_ngram=args.max_ngram,
        min_token_len=args.min_token_len,
        max_phrase_len=args.max_phrase_len,
        min_total=args.min_total,
        min_good=args.min_good,
        min_bad=args.min_bad,
        alpha=args.alpha,
    )

    positive_candidates = [item for item in scored if item.score > 0]
    negative_candidates = [item for item in scored if item.score < 0]
    positive_terms = select_terms(
        positive_candidates,
        max_count=args.max_positive,
        min_ngram=2,
        allow_unigrams=True,
        descending=True,
    )
    negative_terms = select_terms(
        negative_candidates,
        max_count=args.max_negative,
        min_ngram=1,
        allow_unigrams=True,
        descending=False,
    )
    anchor_terms = select_terms(
        positive_candidates,
        max_count=args.max_anchors,
        min_ngram=2,
        allow_unigrams=True,
        descending=True,
    )
    query_terms = select_terms(
        positive_candidates,
        max_count=args.max_query_terms,
        min_ngram=2,
        allow_unigrams=True,
        descending=True,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    scores_path = output_dir / f"term_scores_{timestamp}.json"
    scores_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "good_count": len(good_texts),
        "bad_count": len(bad_texts),
        "conflict_count": len(conflict_ids),
        "rules": {
            "max_ngram": args.max_ngram,
            "min_token_len": args.min_token_len,
            "max_phrase_len": args.max_phrase_len,
            "min_total": args.min_total,
            "min_good": args.min_good,
            "min_bad": args.min_bad,
            "alpha": args.alpha,
        },
        "scores": [asdict(item) for item in scored],
    }
    scores_path.write_text(json.dumps(scores_payload, indent=2, sort_keys=True), encoding="utf-8")

    latest_path = output_dir / "latest.json"
    latest_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(latest_path),
        "good_count": len(good_texts),
        "bad_count": len(bad_texts),
        "conflict_count": len(conflict_ids),
        "rules": scores_payload["rules"],
        "positive_phrases": positive_terms,
        "negative_terms": negative_terms,
        "anchor_phrases": anchor_terms,
        "anchor_phrases_multi": anchor_terms,
        "query_terms": query_terms,
    }
    latest_path.write_text(json.dumps(latest_payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Wrote {scores_path}")
    print(f"Wrote {latest_path}")


if __name__ == "__main__":
    main()

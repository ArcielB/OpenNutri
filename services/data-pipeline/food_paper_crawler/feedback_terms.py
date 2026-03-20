from __future__ import annotations

import re
from typing import Dict, List

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
    for ngram in range(1, max_ngram + 1):
        for start in range(len(tokens) - ngram + 1):
            phrase = " ".join(tokens[start:start + ngram])
            if len(phrase) > max_phrase_len:
                continue
            terms.append(phrase)
    return list(dict.fromkeys(terms))


TERM_NUMERIC_FIELDS = {
    "title_good_df",
    "title_bad_df",
    "title_background_df",
    "ta_good_df",
    "ta_bad_df",
    "ta_background_df",
    "seed_good_prior",
    "seed_bad_prior",
    "title_good_score",
    "title_bad_score",
    "title_net",
    "ta_good_score",
    "ta_bad_score",
    "ta_net",
}


def extract_scored_terms(config: Dict[str, object], key: str = "weighted_terms") -> Dict[str, Dict[str, float]]:
    raw = config.get(key)
    if not isinstance(raw, list):
        return {}

    weighted: Dict[str, Dict[str, float]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        if not term:
            continue
        payload: Dict[str, float] = {"ngram": float(int(item.get("ngram") or (term.count(" ") + 1)))}
        for field in TERM_NUMERIC_FIELDS:
            try:
                payload[field] = float(item.get(field) or 0.0)
            except (TypeError, ValueError):
                payload[field] = 0.0
        weighted[term] = payload
    return weighted

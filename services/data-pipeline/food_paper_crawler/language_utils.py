from __future__ import annotations

import re
from typing import Dict, Iterable, List


SUPPORTED_LANGUAGES = ("en", "tr")
DEFAULT_LANGUAGE = "en"

TURKISH_CHARS = set("çğıöşü")

EN_HINT_TOKENS = {
    "food",
    "foods",
    "nutrient",
    "nutrients",
    "composition",
    "compositions",
    "analysis",
    "content",
    "contents",
    "chemical",
    "proximate",
    "protein",
    "fat",
    "fiber",
    "fibre",
    "vitamin",
    "vitamins",
    "mineral",
    "minerals",
}

TR_HINT_TOKENS = {
    "gıda",
    "gida",
    "besin",
    "bileşimi",
    "bilesimi",
    "kompozisyonu",
    "icerigi",
    "içeriği",
    "içerik",
    "analiz",
    "yaklaşık",
    "yaklasik",
    "protein",
    "yağ",
    "yag",
    "karbonhidrat",
    "lif",
    "vitamin",
    "mineral",
    "nem",
    "kül",
    "kul",
    "kalsiyum",
    "demir",
    "potasyum",
    "magnezyum",
    "fosfor",
    "sodyum",
    "çinko",
    "cinko",
    "bakır",
    "bakir",
    "manganez",
}


def normalize_language_text(text: str) -> str:
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


def detect_supported_language(text: str, *, default: str = DEFAULT_LANGUAGE) -> str:
    cleaned = normalize_language_text(text)
    if not cleaned:
        return default if default in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

    tokens = cleaned.split()
    tr_score = 3 * sum(1 for ch in cleaned if ch in TURKISH_CHARS)
    en_score = 0

    tr_score += sum(1 for token in tokens if token in TR_HINT_TOKENS)
    en_score += sum(1 for token in tokens if token in EN_HINT_TOKENS)

    if tr_score > en_score:
        return "tr"
    if en_score > tr_score:
        return "en"
    return default if default in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def split_terms_by_language(terms: Iterable[str], *, default: str = DEFAULT_LANGUAGE) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {language: [] for language in SUPPORTED_LANGUAGES}
    seen = {language: set() for language in SUPPORTED_LANGUAGES}
    for raw_term in terms:
        term = " ".join((raw_term or "").strip().split())
        if not term:
            continue
        language = detect_supported_language(term, default=default)
        normalized = term.lower()
        if normalized in seen[language]:
            continue
        seen[language].add(normalized)
        buckets[language].append(term)
    return buckets

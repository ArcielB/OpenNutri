from __future__ import annotations

from typing import Dict, Iterable, List


SEED_QUERY_PHRASES_EN = [
    "food composition",
    "composition table",
    "food composition table",
    "nutrient composition",
    "nutritional composition",
    "chemical composition",
    "proximate composition",
    "proximate analysis",
    "mineral content",
    "vitamin content",
    "fatty acid composition",
    "amino acid composition",
    "nutrient content",
]

SEED_QUERY_PHRASES_TR = [
    "gıda bileşimi",
    "besin bileşimi",
    "gıda kompozisyonu",
    "besin kompozisyonu",
    "kimyasal bileşim",
    "yaklaşık bileşim",
    "yaklaşık analiz",
    "mineral içeriği",
    "vitamin içeriği",
    "yağ asidi bileşimi",
    "amino asit bileşimi",
    "besin içeriği",
]

SEED_EN_ANCHOR_PHRASES = [
    "food composition",
    "food composition table",
    "composition table",
    "nutrient composition",
    "nutritional composition",
    "chemical composition",
    "proximate composition",
    "proximate analysis",
    "nutrient content",
    "nutrient profile",
    "mineral content",
    "vitamin content",
    "fatty acid composition",
    "amino acid composition",
    "nutrient data",
    "composition data",
]

SEED_TR_ANCHOR_PHRASES = [
    "gıda bileşimi",
    "besin bileşimi",
    "gıda kompozisyonu",
    "besin kompozisyonu",
    "kimyasal bileşim",
    "yaklaşık bileşim",
    "yaklaşık analiz",
    "besin içeriği",
    "besin profili",
    "mineral içeriği",
    "vitamin içeriği",
    "yağ asidi bileşimi",
    "amino asit bileşimi",
    "besin verisi",
    "bileşim verisi",
]

SEED_QUERY_PHRASES_BY_LANGUAGE: Dict[str, List[str]] = {
    "en": SEED_QUERY_PHRASES_EN,
    "tr": SEED_QUERY_PHRASES_TR,
}

SEED_ANCHOR_PHRASES_BY_LANGUAGE: Dict[str, List[str]] = {
    "en": SEED_EN_ANCHOR_PHRASES,
    "tr": SEED_TR_ANCHOR_PHRASES,
}

def normalize_seed_term(term: str) -> str:
    return " ".join((term or "").lower().strip().split())


def merge_seed_terms(*groups: Iterable[str]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for group in groups:
        for term in group:
            normalized = normalize_seed_term(term)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


SEED_QUERY_PHRASES = list(SEED_QUERY_PHRASES_EN)
SEED_MULTI_ANCHOR_PHRASES = merge_seed_terms(SEED_EN_ANCHOR_PHRASES, SEED_TR_ANCHOR_PHRASES)


SEED_GOOD_TERMS_EN = merge_seed_terms(
    SEED_QUERY_PHRASES_EN,
    SEED_EN_ANCHOR_PHRASES,
)

SEED_GOOD_TERMS_TR = merge_seed_terms(
    SEED_QUERY_PHRASES_TR,
    SEED_TR_ANCHOR_PHRASES,
)

SEED_GOOD_TERMS_BY_LANGUAGE: Dict[str, List[str]] = {
    "en": SEED_GOOD_TERMS_EN,
    "tr": SEED_GOOD_TERMS_TR,
}

SEED_GOOD_TERMS = merge_seed_terms(
    SEED_GOOD_TERMS_EN,
    SEED_GOOD_TERMS_TR,
)

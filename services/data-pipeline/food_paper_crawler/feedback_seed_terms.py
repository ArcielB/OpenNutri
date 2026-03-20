from __future__ import annotations

from typing import Iterable, List


SEED_QUERY_PHRASES = [
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

SEED_MULTI_ANCHOR_PHRASES = SEED_EN_ANCHOR_PHRASES + [
    "gida bilesimi",
    "besin bilesimi",
    "gida kompozisyonu",
    "besin kompozisyonu",
]


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


SEED_GOOD_TERMS = merge_seed_terms(
    SEED_QUERY_PHRASES,
    SEED_EN_ANCHOR_PHRASES,
    SEED_MULTI_ANCHOR_PHRASES,
)

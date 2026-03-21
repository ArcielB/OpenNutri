from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .language_utils import split_terms_by_language


REPO_ROOT = Path(__file__).resolve().parents[3]
FOUNDATION_FOOD_CSV = REPO_ROOT / "FoodData_Central_foundation_food_csv_2025-12-18" / "food.csv"
FOUNDATION_NUTRIENT_CSV = REPO_ROOT / "FoodData_Central_foundation_food_csv_2025-12-18" / "nutrient.csv"

CURATED_FOOD_TERMS_EN = [
    "apple",
    "banana",
    "barley",
    "bean",
    "beef",
    "broccoli",
    "cabbage",
    "carrot",
    "cassava",
    "cheese",
    "chicken",
    "chickpea",
    "cocoa",
    "corn",
    "egg",
    "fish",
    "garlic",
    "grape",
    "lentil",
    "maize",
    "mango",
    "milk",
    "mushroom",
    "oat",
    "olive",
    "onion",
    "orange",
    "pea",
    "pepper",
    "potato",
    "pumpkin",
    "rice",
    "sorghum",
    "soybean",
    "spinach",
    "tomato",
    "wheat",
    "yogurt",
]

CURATED_FOOD_TERMS_TR = [
    "elma",
    "muz",
    "arpa",
    "fasulye",
    "sığır eti",
    "brokoli",
    "lahana",
    "havuç",
    "manyok",
    "peynir",
    "tavuk",
    "nohut",
    "kakao",
    "mısır",
    "yumurta",
    "balık",
    "sarımsak",
    "üzüm",
    "mercimek",
    "mango",
    "süt",
    "mantar",
    "yulaf",
    "zeytin",
    "soğan",
    "portakal",
    "bezelye",
    "biber",
    "patates",
    "kabak",
    "pirinç",
    "sorgum",
    "soya",
    "ıspanak",
    "domates",
    "buğday",
    "yoğurt",
]

CURATED_NUTRIENT_TERMS_EN = [
    "protein",
    "fat",
    "ash",
    "carbohydrate",
    "fiber",
    "moisture",
    "energy",
    "calcium",
    "iron",
    "potassium",
    "magnesium",
    "phosphorus",
    "sodium",
    "zinc",
    "copper",
    "manganese",
    "vitamin c",
    "vitamin a",
    "thiamin",
    "riboflavin",
    "niacin",
    "folate",
    "fatty acids",
    "amino acids",
]

CURATED_NUTRIENT_TERMS_TR = [
    "protein",
    "yağ",
    "kül",
    "karbonhidrat",
    "lif",
    "nem",
    "enerji",
    "kalsiyum",
    "demir",
    "potasyum",
    "magnezyum",
    "fosfor",
    "sodyum",
    "çinko",
    "bakır",
    "manganez",
    "vitamin c",
    "vitamin a",
    "tiamin",
    "riboflavin",
    "niasin",
    "folat",
    "yağ asitleri",
    "amino asitler",
]

CORE_NUTRIENT_TERMS = {
    *CURATED_NUTRIENT_TERMS_EN,
    *CURATED_NUTRIENT_TERMS_TR,
    "fibre",
    "fatty acid",
    "amino acid",
}

SKIP_FOOD_WORDS = {
    "vitamin",
    "mineral",
    "protein",
    "moisture",
    "ash",
    "fatty",
    "acid",
    "cholesterol",
    "fiber",
    "fibre",
    "energy",
    "water",
    "starch",
    "food",
    "foods",
    "seed",
    "seeds",
    "sugar",
    "sugars",
    "salt",
    "measures",
    "proximates",
    "minerals",
    "choles",
    "frankfurter",
    "hot",
    "dogs",
    "gıda",
    "besin",
    "yiyecek",
    "vitaminler",
    "mineraller",
}

SKIP_NUTRIENT_TERMS = {
    "nitrogen",
    "solids",
    "water",
    "ash",
    "azot",
    "su",
}

NUTRIENT_SYNONYMS = {
    "carbohydrate, by difference": "carbohydrate",
    "fiber, total dietary": "fiber",
    "fatty acids, total saturated": "fatty acids",
    "fatty acids, total monounsaturated": "fatty acids",
    "fatty acids, total polyunsaturated": "fatty acids",
    "vitamin c, total ascorbic acid": "vitamin c",
    "vitamin a, rae": "vitamin a",
    "energy": "energy",
    "protein": "protein",
    "total lipid (fat)": "fat",
    "moisture": "moisture",
    "iron, fe": "iron",
    "calcium, ca": "calcium",
    "magnesium, mg": "magnesium",
    "phosphorus, p": "phosphorus",
    "potassium, k": "potassium",
    "sodium, na": "sodium",
    "zinc, zn": "zinc",
    "copper, cu": "copper",
    "manganese, mn": "manganese",
    "karbonhidrat": "karbonhidrat",
    "yağlar": "yağ",
    "yaglar": "yağ",
    "yağ asidi": "yağ asitleri",
    "amino asit": "amino asitler",
}


def fetch_food_terms_by_language(supabase_url: str, supabase_key: str, limit: int = 120) -> Dict[str, List[str]]:
    remote = _fetch_remote_food_terms_by_language(supabase_url, supabase_key, limit=limit)
    local_en = _load_local_food_terms(limit=limit * 2)
    return {
        "en": _merge_terms(CURATED_FOOD_TERMS_EN, remote["en"], local_en, limit=limit),
        "tr": _merge_terms(CURATED_FOOD_TERMS_TR, remote["tr"], limit=limit),
    }


def fetch_nutrient_terms_by_language(supabase_url: str, supabase_key: str, limit: int = 60) -> Dict[str, List[str]]:
    remote = _fetch_remote_nutrient_terms_by_language(supabase_url, supabase_key, limit=limit)
    local_en = _load_local_nutrient_terms(limit=limit * 2)
    return {
        "en": _merge_terms(remote["en"], local_en, CURATED_NUTRIENT_TERMS_EN, limit=limit),
        "tr": _merge_terms(remote["tr"], CURATED_NUTRIENT_TERMS_TR, limit=limit),
    }


def fetch_food_terms(supabase_url: str, supabase_key: str, limit: int = 120) -> List[str]:
    buckets = fetch_food_terms_by_language(supabase_url, supabase_key, limit=limit)
    return _merge_terms(buckets["en"], buckets["tr"], limit=limit)


def fetch_nutrient_terms(supabase_url: str, supabase_key: str, limit: int = 60) -> List[str]:
    buckets = fetch_nutrient_terms_by_language(supabase_url, supabase_key, limit=limit)
    return _merge_terms(buckets["en"], buckets["tr"], limit=limit)


def _fetch_remote_food_terms_by_language(supabase_url: str, supabase_key: str, limit: int) -> Dict[str, List[str]]:
    if not supabase_url or not supabase_key:
        return {"en": [], "tr": []}

    discovered = {"en": [], "tr": []}
    sources = [
        ("food_items", "food_name", _normalize_food, _is_valid_food, "en"),
        ("entities", "canonical_name", _normalize_food, _is_valid_food, "en"),
        ("entity_aliases", "alias_name", _normalize_food, _is_valid_food, "en"),
        ("foods", "description", _normalize_food, _is_valid_food, "en"),
    ]
    for table, column, normalizer, validator, default_language in sources:
        rows = _fetch_table_rows(supabase_url, supabase_key, table, column, max(limit * 8, 250))
        terms = []
        for row in rows:
            value = normalizer(row.get(column, ""))
            if validator(value):
                terms.append(value)
        split = split_terms_by_language(terms, default=default_language)
        discovered["en"].extend(split["en"])
        discovered["tr"].extend(split["tr"])
    return {
        "en": _dedupe(discovered["en"])[:limit],
        "tr": _dedupe(discovered["tr"])[:limit],
    }


def _fetch_remote_nutrient_terms_by_language(supabase_url: str, supabase_key: str, limit: int) -> Dict[str, List[str]]:
    if not supabase_url or not supabase_key:
        return {"en": [], "tr": []}

    discovered = {"en": [], "tr": []}
    sources = [
        ("annotation_nutrient_values", "nutrient_name", _normalize_nutrient, _is_valid_nutrient, "en"),
        ("master_nutrients", "standard_name", _normalize_nutrient, _is_valid_nutrient, "en"),
        ("nutrients", "name", _normalize_nutrient, _is_valid_nutrient, "en"),
    ]
    for table, column, normalizer, validator, default_language in sources:
        rows = _fetch_table_rows(supabase_url, supabase_key, table, column, max(limit * 6, 200))
        terms = []
        for row in rows:
            value = normalizer(row.get(column, ""))
            if validator(value):
                terms.append(value)
        split = split_terms_by_language(terms, default=default_language)
        discovered["en"].extend(split["en"])
        discovered["tr"].extend(split["tr"])
    return {
        "en": _dedupe(discovered["en"])[:limit],
        "tr": _dedupe(discovered["tr"])[:limit],
    }


def _fetch_table_rows(supabase_url: str, supabase_key: str, table: str, column: str, limit: int) -> List[dict]:
    endpoint = supabase_url.rstrip("/") + f"/rest/v1/{table}"
    params = urlencode({"select": column, "limit": str(limit)})
    request = Request(
        f"{endpoint}?{params}",
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _load_local_food_terms(limit: int) -> List[str]:
    if not FOUNDATION_FOOD_CSV.exists():
        return []

    discovered: List[str] = []
    seen: Set[str] = set()
    with FOUNDATION_FOOD_CSV.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized = _normalize_food(row.get("description", ""))
            if not _is_valid_food(normalized) or normalized in seen:
                continue
            seen.add(normalized)
            discovered.append(normalized)
            if len(discovered) >= limit:
                break
    return discovered


def _load_local_nutrient_terms(limit: int) -> List[str]:
    if not FOUNDATION_NUTRIENT_CSV.exists():
        return []

    discovered: List[str] = []
    seen: Set[str] = set()
    with FOUNDATION_NUTRIENT_CSV.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized = _normalize_nutrient(row.get("name", ""))
            if not _is_valid_nutrient(normalized) or normalized in seen:
                continue
            seen.add(normalized)
            discovered.append(normalized)
            if len(discovered) >= limit:
                break
    return discovered


def _normalize_food(text: str) -> str:
    base = re.split(r"[,;/\(\)\-]", text or "")[0].strip().lower()
    base = re.sub(r"[^\w ]+", " ", base, flags=re.UNICODE)
    base = re.sub(r"\s+", " ", base).strip()
    if base.isascii():
        base = _singularize_food(base)
    return base


def _normalize_nutrient(text: str) -> str:
    base = (text or "").strip().lower()
    base = re.sub(r"\([^)]*\)", "", base)
    base = re.sub(r"[,;/]+", ",", base)
    base = re.sub(r"\s+", " ", base).strip(" ,")
    base = NUTRIENT_SYNONYMS.get(base, base)
    if base.startswith("vitamin "):
        return base
    if base.startswith("fatty acids"):
        return "fatty acids"
    if base.startswith("amino acids"):
        return "amino acids"
    if base.startswith("yağ asit"):
        return "yağ asitleri"
    if base.startswith("amino asit"):
        return "amino asitler"
    if base.endswith(", by difference"):
        base = base.replace(", by difference", "")
    if "," in base:
        base = base.split(",", 1)[0].strip()
    return base


def _is_valid_food(term: str) -> bool:
    if len(term) < 3 or len(term) > 40:
        return False
    if term in SKIP_FOOD_WORDS:
        return False
    tokens = term.split()
    if len(tokens) > 3:
        return False
    if any(token in SKIP_FOOD_WORDS for token in tokens):
        return False
    if any(marker in term for marker in ("flavored", "fermented", "liquid whole", "market", "sample", "sub sample")):
        return False
    return all(token.isalpha() for token in tokens)


def _singularize_food(term: str) -> str:
    irregular = {
        "tomatoes": "tomato",
        "potatoes": "potato",
        "berries": "berry",
        "beans": "bean",
        "figs": "fig",
        "almonds": "almond",
        "oranges": "orange",
        "carrots": "carrot",
        "apples": "apple",
        "bananas": "banana",
        "eggs": "egg",
        "nuts": "nut",
    }
    if term in irregular:
        return irregular[term]
    if term.endswith("ies") and len(term) > 5:
        return term[:-3] + "y"
    if term.endswith("s") and not term.endswith(("ss", "us")) and len(term) > 4:
        return term[:-1]
    return term


def _is_valid_nutrient(term: str) -> bool:
    if len(term) < 3 or len(term) > 40:
        return False
    if term in SKIP_NUTRIENT_TERMS:
        return False
    if any(marker in term for marker in ("protein quality", "digestibility", "availability")):
        return False
    return term in CORE_NUTRIENT_TERMS


def _merge_terms(*sources: Iterable[str], limit: int) -> List[str]:
    merged: List[str] = []
    seen: Set[str] = set()
    for source in sources:
        for item in source:
            normalized = item.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
            if len(merged) >= limit:
                return merged
    return merged


def _dedupe(items: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    deduped: List[str] = []
    for item in items:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped

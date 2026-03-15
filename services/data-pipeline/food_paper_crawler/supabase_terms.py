from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Iterable, List, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[3]
FOUNDATION_FOOD_CSV = REPO_ROOT / "FoodData_Central_foundation_food_csv_2025-12-18" / "food.csv"
FOUNDATION_NUTRIENT_CSV = REPO_ROOT / "FoodData_Central_foundation_food_csv_2025-12-18" / "nutrient.csv"

CURATED_FOOD_TERMS = [
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

CURATED_NUTRIENT_TERMS = [
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
]

CORE_NUTRIENT_TERMS = {
    "protein",
    "fat",
    "carbohydrate",
    "fiber",
    "fibre",
    "moisture",
    "energy",
    "ash",
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
}

SKIP_NUTRIENT_TERMS = {
    "nitrogen",
    "solids",
    "water",
    "ash",
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
}


def fetch_food_terms(supabase_url: str, supabase_key: str, limit: int = 120) -> List[str]:
    remote = _fetch_remote_food_terms(supabase_url, supabase_key, limit=limit)
    local = _load_local_food_terms(limit=limit * 2)
    return _merge_terms(CURATED_FOOD_TERMS, remote, local, limit=limit)


def fetch_nutrient_terms(supabase_url: str, supabase_key: str, limit: int = 60) -> List[str]:
    remote = _fetch_remote_nutrient_terms(supabase_url, supabase_key, limit=limit)
    local = _load_local_nutrient_terms(limit=limit * 2)
    return _merge_terms(remote, local, CURATED_NUTRIENT_TERMS, limit=limit)


def _fetch_remote_food_terms(supabase_url: str, supabase_key: str, limit: int) -> List[str]:
    if not supabase_url or not supabase_key:
        return []

    discovered: List[str] = []
    for table, column in (("food_items", "name"), ("entities", "canonical_name"), ("foods", "description")):
        rows = _fetch_table_rows(supabase_url, supabase_key, table, column, max(limit * 6, 200))
        for row in rows:
            value = _normalize_food(row.get(column, ""))
            if _is_valid_food(value):
                discovered.append(value)
        if discovered:
            break
    return _dedupe(discovered)


def _fetch_remote_nutrient_terms(supabase_url: str, supabase_key: str, limit: int) -> List[str]:
    if not supabase_url or not supabase_key:
        return []

    discovered: List[str] = []
    for table, column in (("master_nutrients", "standard_name"), ("nutrients", "name")):
        rows = _fetch_table_rows(supabase_url, supabase_key, table, column, max(limit * 4, 150))
        for row in rows:
            value = _normalize_nutrient(row.get(column, ""))
            if _is_valid_nutrient(value):
                discovered.append(value)
        if discovered:
            break
    return _dedupe(discovered)


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
    base = re.sub(r"[^a-z ]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
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
    if base.endswith(", by difference"):
        base = base.replace(", by difference", "")
    if "," in base:
        base = base.split(",", 1)[0].strip()
    return base


def _is_valid_food(term: str) -> bool:
    if len(term) < 3 or len(term) > 30:
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

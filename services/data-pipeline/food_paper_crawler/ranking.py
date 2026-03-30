from __future__ import annotations

import re
from typing import Iterable, List, Tuple

from .models import CandidatePaper


COMPOSITION_TERMS = [
    "food composition",
    "composition table",
    "food composition table",
    "nutrient composition",
    "nutritional composition",
    "chemical composition",
    "proximate composition",
    "proximate compositions",
    "proximate analysis",
    "nutritive value",
    "nutrient content",
    "nutrient profile",
    "mineral content",
    "vitamin content",
    "fatty acid composition",
    "amino acid composition",
    "gıda bileşimi",
    "besin bileşimi",
    "gıda kompozisyonu",
    "besin kompozisyonu",
    "kimyasal bileşim",
    "yaklaşık bileşim",
    "yaklaşık analiz",
    "besin içeriği",
    "mineral içeriği",
    "vitamin içeriği",
    "yağ asidi bileşimi",
    "amino asit bileşimi",
]

TABLE_TERMS = [
    "table 1",
    "table 2",
    "tables 1",
    "results showed",
    "contents of",
    "content of",
    "analyzed for",
    "were analyzed",
    "determined by",
    "aoac",
    "tablo 1",
    "tablo 2",
    "tablo 3",
    "içerik",
    "icerik",
    "analiz",
]

FOOD_CUES = [
    "food",
    "foods",
    "fruit",
    "fruits",
    "vegetable",
    "vegetables",
    "grain",
    "grains",
    "cereal",
    "cereals",
    "legume",
    "legumes",
    "seed",
    "seeds",
    "bean",
    "beans",
    "tuber",
    "tubers",
    "flour",
    "pulp",
    "leaf",
    "leaves",
    "milk",
    "meat",
    "fish",
    "mushroom",
    "mushrooms",
    "edible",
    "consumed",
    "gıda",
    "besin",
    "meyve",
    "sebze",
    "tahıl",
    "tahil",
    "baklagil",
    "tohum",
    "un",
    "yaprak",
    "süt",
    "sut",
    "et",
    "balık",
    "balik",
    "mantar",
]

NUTRIENT_MARKERS = [
    "moisture",
    "protein",
    "fat",
    "lipid",
    "ash",
    "fiber",
    "fibre",
    "carbohydrate",
    "energy",
    "kcal",
    "sodium",
    "potassium",
    "calcium",
    "magnesium",
    "iron",
    "zinc",
    "phosphorus",
    "copper",
    "manganese",
    "vitamin",
    "yağ",
    "yag",
    "kül",
    "kul",
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
    "cinko",
    "bakır",
    "bakir",
    "manganez",
]

DB_ALIGNMENT_BONUS_TERMS = {
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
}

STRONG_NEGATIVE_SIGNAL_TERMS = [
    "dataset",
    "database",
    "perspective",
    "cement",
    "concrete",
    "aggregate",
    "aggregates",
    "radionuclide",
    "radioactivity",
    "radiological",
    "x-ray fluorescence",
    "body composition",
    "body proximate composition",
    "body proximate compositions",
    "juvenile",
    "growth",
    "physiology",
    "ecology",
    "rheology",
    "rheological",
    "viscosity",
    "pasting",
    "swelling power",
    "solubility",
    "water absorption",
    "water binding",
    "dough",
    "gel",
    "emulsion",
    "functional properties",
    "essential oil",
    "volatile oil",
    "extract",
    "extracts",
    "bioactive",
    "bioactivity",
    "antioxidant",
    "antimicrobial",
    "antibacterial",
    "antifungal",
    "insecticidal",
    "cytotoxic",
    "nanoparticle",
    "genome",
    "gene",
    "transcript",
    "metagenomic",
    "microbiota",
    "packaging",
    "polymer",
    "biosorbent",
    "meteorite",
    "implant",
]

SOFT_NEGATIVE_TERMS = [
    "association between",
    "supplementation",
    "clinical trial",
    "review",
    "meta-analysis",
    "broiler",
    "rat",
    "rats",
    "mice",
    "feed",
    "fodder",
    "veterinary",
    "pharmacological",
    "medicinal",
    "cell line",
]

UNIT_PATTERN = re.compile(r"\b(?:mg|g|ug|µg|kcal|kj)\s*/\s*(?:100\s*g|100\s*gm|g|kg|ml)\b", re.IGNORECASE)
PERCENT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*%\b")


def score_candidate(candidate: CandidatePaper, food_terms: Iterable[str], nutrient_terms: Iterable[str]) -> Tuple[float, bool, List[str]]:
    title = normalize_text(candidate.title)
    abstract = normalize_text(candidate.abstract)
    journal = normalize_text(candidate.journal or "")
    text = f"{title} {abstract}".strip()

    reasons: List[str] = []
    score = 0.0

    title_comp = first_hits(title, COMPOSITION_TERMS)
    abstract_comp = first_hits(abstract, COMPOSITION_TERMS)
    table_hits = first_hits(text, TABLE_TERMS)
    nutrient_hits = first_hits(text, NUTRIENT_MARKERS, limit=6)
    explicit_nutrient_hits = matching_nutrient_terms(text, nutrient_terms, limit=8)
    food_hits = matching_food_terms(text, food_terms, limit=6)
    cue_hits = first_hits(text, FOOD_CUES, limit=4)
    strong_negative_signals = first_hits(text, STRONG_NEGATIVE_SIGNAL_TERMS, limit=4)
    soft_negatives = first_hits(text, SOFT_NEGATIVE_TERMS, limit=4)

    if title_comp:
        score += 8
        reasons.append(f"title composition: {title_comp[0]}")
    if abstract_comp:
        score += 5
        reasons.append(f"abstract composition: {abstract_comp[0]}")
    if table_hits:
        score += min(6, 2 + len(table_hits))
        reasons.append(f"table/method evidence: {table_hits[0]}")
    if UNIT_PATTERN.search(text):
        score += 4
        reasons.append("contains nutrient-style units")
    if PERCENT_PATTERN.search(text):
        score += 2
        reasons.append("contains percentage composition values")
    if nutrient_hits:
        score += min(8, len(nutrient_hits))
        reasons.append(f"nutrient markers: {', '.join(nutrient_hits[:3])}")
    if explicit_nutrient_hits:
        score += min(8, 2 + len(explicit_nutrient_hits))
        reasons.append(f"db nutrient matches: {', '.join(explicit_nutrient_hits[:3])}")
    if cue_hits:
        score += min(3, len(cue_hits))
        reasons.append(f"food cues: {cue_hits[0]}")
    if food_hits:
        score += min(7, 2 + len(food_hits))
        reasons.append(f"food matches DB terms: {', '.join(food_hits[:3])}")

    if any(term in journal for term in ("food composition", "food chemistry", "foods", "lwt")):
        score += 2
        reasons.append(f"food journal: {candidate.journal}")

    query_focus = extract_query_focus(candidate.query)
    if query_focus and bounded_contains(text, query_focus):
        score += 4
        reasons.append(f"query focus match: {query_focus}")

    if strong_negative_signals:
        score -= min(10, 4 + 2 * len(strong_negative_signals))
        reasons.append(f"negative signal: {strong_negative_signals[0]}")
    if soft_negatives:
        score -= min(10, 3 + len(soft_negatives))
        reasons.append(f"soft negative: {soft_negatives[0]}")

    if title.startswith(("effect of", "effects of", "impact of", "association between")):
        score -= 6

    has_composition = bool(title_comp or abstract_comp)
    has_data_signal = bool(table_hits or UNIT_PATTERN.search(text) or len(nutrient_hits) >= 3 or len(explicit_nutrient_hits) >= 2)
    has_food_signal = bool(food_hits or cue_hits or query_focus and bounded_contains(text, query_focus))
    acceptable = score >= 8 and has_composition and has_data_signal and has_food_signal
    return score, acceptable, reasons


def validate_pdf_text(text: str, candidate: CandidatePaper, food_terms: Iterable[str], nutrient_terms: Iterable[str]) -> Tuple[float, bool, List[str]]:
    normalized = strip_reference_sections(normalize_text(text))
    reasons: List[str] = []
    score = 0.0

    table_hits = first_hits(normalized, ["table 1", "table 2", "table 3", "tab.", "aoac", "hplc", "gc", "icp"], limit=6)
    nutrient_hits = first_hits(normalized, NUTRIENT_MARKERS, limit=12)
    explicit_nutrient_hits = matching_nutrient_terms(normalized, nutrient_terms, limit=12)
    food_hits = matching_food_terms(normalized, food_terms, limit=8)
    pdf_strong_negative_terms = [term for term in STRONG_NEGATIVE_SIGNAL_TERMS if term not in {"dataset", "database", "perspective"}]
    strong_negative_signals = first_hits(normalized, pdf_strong_negative_terms, limit=6)
    soft_negatives = first_hits(normalized, SOFT_NEGATIVE_TERMS, limit=6)

    if any(term in normalized for term in COMPOSITION_TERMS):
        score += 8
        reasons.append("full-text composition framing")
    if table_hits:
        score += min(8, 2 + len(table_hits))
        reasons.append(f"table/method evidence: {table_hits[0]}")
    unit_count = len(UNIT_PATTERN.findall(normalized))
    if unit_count:
        score += min(8, 2 + unit_count)
        reasons.append(f"nutrient units: {unit_count}")
    if nutrient_hits:
        unique_nutrients = len(set(nutrient_hits))
        score += min(12, unique_nutrients)
        reasons.append(f"nutrient markers: {', '.join(list(dict.fromkeys(nutrient_hits))[:5])}")
    if explicit_nutrient_hits:
        unique_explicit = list(dict.fromkeys(explicit_nutrient_hits))
        score += min(10, 2 + len(unique_explicit))
        reasons.append(f"db nutrient matches: {', '.join(unique_explicit[:5])}")
    if food_hits:
        unique_foods = list(dict.fromkeys(food_hits))
        bonus = min(8, 2 + len(unique_foods))
        if any(food in DB_ALIGNMENT_BONUS_TERMS for food in unique_foods):
            bonus += 2
        score += bonus
        reasons.append(f"food terms: {', '.join(unique_foods[:4])}")
    if PERCENT_PATTERN.search(normalized):
        score += 2
        reasons.append("percentage values present")

    if strong_negative_signals:
        score -= min(12, 5 + 2 * len(strong_negative_signals))
        reasons.append(f"negative signal: {strong_negative_signals[0]}")
    if soft_negatives:
        score -= min(10, 2 + len(soft_negatives))
        reasons.append(f"soft negative: {soft_negatives[0]}")

    if "essential oil" in normalized and "protein" not in normalized and "moisture" not in normalized:
        score -= 12
        reasons.append("essential-oil-only profile")

    nutrient_set = set(nutrient_hits)
    strong_nutrient_panel = {
        "moisture",
        "protein",
        "fat",
        "lipid",
        "ash",
        "fiber",
        "fibre",
        "carbohydrate",
        "energy",
        "calcium",
        "iron",
        "potassium",
        "sodium",
        "phosphorus",
        "magnesium",
    }
    nutrient_overlap = len(nutrient_set & strong_nutrient_panel) + min(3, len(set(explicit_nutrient_hits) & strong_nutrient_panel))
    has_table_signal = bool(
        table_hits
        or unit_count >= 4
        or (PERCENT_PATTERN.search(normalized) and nutrient_overlap >= 4)
        or (("proximate composition" in normalized or "proximate compositions" in normalized) and nutrient_overlap >= 4)
    )
    has_food_signal = bool(food_hits or any(term in normalized for term in FOOD_CUES))
    acceptable = score >= 18 and has_table_signal and has_food_signal and nutrient_overlap >= 4
    return score, acceptable, reasons


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def strip_reference_sections(text: str) -> str:
    normalized = text or ""
    markers = (" references ", " bibliography ", " kaynaklar ", " referanslar ")
    for marker in markers:
        idx = normalized.find(marker)
        if idx >= 0 and idx >= max(1200, int(len(normalized) * 0.45)):
            return normalized[:idx].strip()
    return normalized


def first_hits(text: str, phrases: Iterable[str], limit: int = 3) -> List[str]:
    hits: List[str] = []
    for phrase in phrases:
        if bounded_contains(text, phrase) and phrase not in hits:
            hits.append(phrase)
            if len(hits) >= limit:
                break
    return hits


def matching_food_terms(text: str, food_terms: Iterable[str], limit: int = 4) -> List[str]:
    hits: List[str] = []
    for term in food_terms:
        normalized = term.strip().lower()
        if not normalized or len(normalized) < 3:
            continue
        if bounded_contains(text, normalized):
            hits.append(normalized)
            if len(hits) >= limit:
                break
    return hits


def matching_nutrient_terms(text: str, nutrient_terms: Iterable[str], limit: int = 6) -> List[str]:
    hits: List[str] = []
    for term in nutrient_terms:
        normalized = term.strip().lower()
        if not normalized or len(normalized) < 3:
            continue
        if bounded_contains(text, normalized):
            hits.append(normalized)
            if len(hits) >= limit:
                break
    return hits


def bounded_contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, flags=re.UNICODE) is not None


def extract_query_focus(query: str) -> str:
    match = re.match(r'^\("([^"]+)"\s+AND', query)
    if not match:
        return ""
    focus = match.group(1).strip().lower()
    if any(token in focus for token in ("composition", "content", "value", "profile")):
        return ""
    return focus

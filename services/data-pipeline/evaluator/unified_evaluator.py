"""
Unified LLM Evaluator & Extractor

Single-pass evaluation: Filter papers AND extract structured food composition data.
"""

import os
import json
from typing import Any, Optional, List, Dict
from dataclasses import dataclass
from json import JSONDecodeError

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


@dataclass
class NutrientRecord:
    """Single food-nutrient data point with verification"""
    food_name: str
    nutrient_name: str
    amount: float
    unit: str
    basis: str  # e.g., "100g", "dry weight basis"
    preparation_state: str  # e.g., "raw", "cooked", "boiled"
    sample_size: Optional[int]
    confidence: float  # 0.0-1.0 confidence score for THIS specific record
    source_citation: str  # "Table 2, Row 3" or "Page 5, Results section"
    metadata: Dict[str, Any]
    table_label: Optional[str] = None
    page_hint: Optional[int] = None
    source_quote: Optional[str] = None
    raw_food_name: Optional[str] = None
    raw_nutrient_name: Optional[str] = None
    food_fdc_id: Optional[str] = None
    food_id: Optional[str] = None
    entity_id: Optional[str] = None
    db_food_id: Optional[str] = None
    nutrient_id: Optional[str] = None
    nutrient_db_id: Optional[str] = None
    master_nutrient_id: Optional[str] = None
    db_nutrient_id: Optional[str] = None
    flags: List[str] = None  # Plausibility warnings
    
    def __post_init__(self):
        if self.flags is None:
            self.flags = []


@dataclass
class ExtractionResult:
    """Result of evaluating and extracting from a paper"""
    pmc_id: str
    is_useful: bool
    reasoning: str
    overall_confidence: float  # 0.0-1.0 confidence for the entire paper
    data: List[NutrientRecord]
    decision_kind: str = "no_usable_data"
    no_data_reason: str = ""
    paper_type: str = ""
    database_value: str = ""
    paper_decision_confidence: float = 0.0
    extraction_confidence: float = 0.0
    source_term: str = ""
    raw_response_text: str = ""


class UnifiedEvaluator:
    """
    Evaluates papers and extracts food composition data in a single LLM call.
    """
    
    EXTRACTION_PROMPT = """You are a food composition database curator extracting structured data from scientific papers.

**Task**: Determine if this paper contains direct food/product composition data that is useful for OpenNutri, and if so, extract it.

**USEFULNESS Criteria**:
- is_useful = true ONLY if the paper directly reports composition values measured in real foods or food products, with clear food-nutrient mappings suitable for an OpenNutri food composition database (for example: apple: protein 0.3 g/100g, vitamin C 4.6 mg/100g, moisture 84%).
- OpenNutri useful data means nutrition/composition values that could reasonably support diet tracking, food composition datasets, food exporters, food product inspection, or similar real-world food data use cases.
- is_useful = false for experimental treatment/formulation variants that are not stable real-world foods/products worth adding to a nutrition dataset (for example one-off formulations with 1%, 2%, 4%, 6% additive levels, fertilizer treatments, irradiation doses, storage treatments, processing treatments, salt-stress treatments, or treatment-only recipes).
- is_useful = false if the paper is mainly about what a nutrient, supplement, extract, dose, or diet does to people, animals, cells, microbes, biomarkers, disease, growth, antioxidant status, digestibility, shelf life, processing performance, sensory properties, or any other outcome.
- is_useful = false for intervention/effect/association papers even if they mention foods or nutrients, unless they also contain direct food composition tables for the food itself.
- is_useful = false for review papers without original composition data, methodology papers without food composition results, supplement/pill/extract studies, and papers about non-food items.
- Every paper that does not contain data useful to OpenNutri is empty: return decision_kind="no_usable_data", is_useful=false, and data=[].

**Instructions**:
1. Read the paper carefully.
2. Provide a detailed reasoning for your decision (why it is or isn't useful).
3. Determine if it is useful (is_useful: true/false).
4. Assign paper_decision_confidence for whether the useful/no-usable-data decision is right.
5. If is_useful is true: Extract ALL candidate food-nutrient composition data from tables.
6. For each data point, preserve the explicit unit and basis from the paper so downstream validation can standardize it to the database payload.
7. Use the nutrient catalog below. When a paper nutrient exactly matches a catalog row, output that row's nutrient_id and standard nutrient_name exactly. When no confident exact match exists, set nutrient_id to null and preserve the paper's nutrient name.
8. Do not invent food IDs. If high-signal food candidates are provided and a paper food exactly matches a candidate's canonical_name or alias, output its food_fdc_id; otherwise set food_fdc_id to null and preserve the paper's food name.
9. Preserve row context needed for database review: raw paper names, preparation state, sample size, confidence, source citation, page/table hints, short source quote, and metadata such as cultivar, location, edible portion, analysis method, storage, and harvest date.

**Nutrient Catalog**:
{nutrient_catalog}

**Food Candidates**:
{food_candidates}

**Output Format** (Strict JSON only):
```json
{{
  "reasoning": "Detailed explanation of why this paper is or is not useful for food composition data",
  "decision_kind": "has_data",
  "is_useful": true | false,
  "no_data_reason": null,
  "paper_type": "ordinary_food_composition",
  "database_value": "high",
  "paper_decision_confidence": 0.95,
  "extraction_confidence": 0.90,
  "overall_confidence": 0.90,
  "data": [
    {{
      "food_name": "Apple, raw, with skin",
      "food_fdc_id": null,
      "raw_food_name": "Fuji apple with skin",
      "nutrient_name": "Vitamin C",
      "nutrient_id": "00000000-0000-0000-0000-000000000000",
      "raw_nutrient_name": "Ascorbic acid",
      "amount": 4.6,
      "unit": "mg",
      "basis": "100g",
      "preparation_state": "raw",
      "sample_size": 50,
      "confidence": 0.98,
      "source_citation": "Table 2, row 3",
      "table_label": "Table 2",
      "page_hint": 5,
      "source_quote": "Fuji apple ... Vitamin C ... 4.6 mg/100g",
      "metadata": {{
        "cultivar": "Fuji",
        "location": "Japan",
        "harvest_date": "2024-09",
        "analysis_method": "HPLC",
        "storage": "fresh",
        "edible_portion": "with skin"
      }}
    }}
  ]
}}
```

**Field Guidance**:
- food_name: Specific food name as mentioned in the paper.
- food_fdc_id: Exact provided DB food ID only when a provided food candidate matches; otherwise null.
- raw_food_name: Food name exactly as written in the paper.
- nutrient_name: Exact catalog standard_name when matched; otherwise the paper's custom nutrient name.
- nutrient_id: Exact catalog ID when matched; otherwise null.
- raw_nutrient_name: Nutrient name exactly as written in the paper.
- amount: Numeric value (float).
- unit: Measurement unit (g, mg, kcal, etc.).
- basis: Reference basis (e.g., "100g", "dry weight basis", "per serving").
- preparation_state: State of the food (raw, cooked, boiled, dried, etc.).
- sample_size: Number of samples (n=) as an integer, or null if not stated.
- confidence: 0.0-1.0 score for THIS specific data point.
- source_citation: SPECIFIC location (e.g., "Table 1, Row 2").
- table_label: Table identifier if available (e.g., "Table 1"), otherwise null.
- page_hint: PDF page number if available, otherwise null.
- source_quote: Short exact excerpt containing the food/nutrient/value/unit evidence. Keep it under 40 words.

**Critical Rules**:
1. Return ONLY valid JSON.
2. Do NOT hallucinate values.
3. If is_useful is false, return an empty "data" array.
4. Extract ALL nutrients from tables, not just a sample.
5. Prefer rows reported per 100g or as percentages. Rows on other bases may be included as candidates only when the basis is explicit.
6. Do not treat clinical outcomes, health effects, intervention outcomes, dose-response results, digestibility metrics, antioxidant assays, pH, color, texture, yield, microbial counts, enzyme activity, gene expression, blood/serum/tissue biomarkers, body composition, growth, survival, sensory scores, or other non-composition measurements as food composition nutrient values.
7. Do not extract values that describe an administered nutrient amount, supplement dose, diet formulation dose, treatment concentration, or experimental exposure unless the table also reports the nutrient composition of the food itself.
8. If the only quantitative values are effects of a nutrient/food/extract on an outcome, the paper is empty for OpenNutri.
9. If the only composition values are for one-off experimental treatment or formulation variants that are not real-world food products, the paper is empty for OpenNutri.
10. Use database_value only as supporting context. The final decision remains decision_kind="has_data" only for data useful to OpenNutri; otherwise decision_kind="no_usable_data".

**Paper Content**:
Title: {title}

Full Text:
{full_text}

**Your Response** (JSON only, no other text):"""

    def __init__(
        self,
        raw_lake_dir: str = "data/raw_lake",
        api_key: str = None,
        model_name: str = "gemini-3-flash-preview",
        nutrient_catalog: list[dict] | None = None,
        food_candidates: list[dict] | None = None,
    ):
        self.raw_lake_dir = raw_lake_dir
        self.model_name = model_name
        self.nutrient_catalog = list(nutrient_catalog or [])
        self.food_candidates = list(food_candidates or [])
        
        # Try to get API key from: 1) argument, 2) env var, 3) config.py
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            try:
                from config import GEMINI_API_KEY
                self.api_key = GEMINI_API_KEY
            except ImportError:
                pass
        
        self.model = None
        
        if HAS_GEMINI and self.api_key:
            genai.configure(api_key=self.api_key)
            # Use JSON mode for structured output
            self.model = genai.GenerativeModel(
                self.model_name,
                generation_config={
                    "response_mime_type": "application/json"
                }
            )
            print(f"🤖 Unified Evaluator initialized with {self.model_name}")

        else:
            print("⚠️ No LLM available. API key required for UnifiedEvaluator.")

    def evaluate_and_extract(self, paper: dict) -> ExtractionResult:
        """
        Evaluate paper and extract data in single call.
        
        Args:
            paper: Dict with 'pmc_id', 'title', 'raw_xml', etc.
            
        Returns:
            ExtractionResult with reasoning, usefulness, and extracted data
        """
        if not self.model:
            return ExtractionResult(
                pmc_id=paper.get("pmc_id", ""),
                is_useful=False,
                reasoning="No LLM available",
                overall_confidence=0.0,
                data=[],
                decision_kind="no_usable_data",
                no_data_reason="no_llm_available",
                source_term=paper.get("source_term", "")
            )
        
        try:
            # Extract text from XML
            full_text = paper.get("full_text")
            if full_text is None:
                from processing.content import extract_full_text
                full_text = extract_full_text(paper.get("raw_xml", ""))
            
            # Truncate if too long (safety limit: ~1M tokens = ~4M chars)
            if len(full_text) > 4_000_000:
                full_text = full_text[:4_000_000] + "\n\n[TRUNCATED - Paper exceeded token limit]"
            
            prompt = self.EXTRACTION_PROMPT.format(
                title=paper.get("metadata", {}).get("title", paper.get("title", "Unknown Title")),
                full_text=full_text,
                nutrient_catalog=self._format_nutrient_catalog(getattr(self, "nutrient_catalog", [])),
                food_candidates=self._format_food_candidates(getattr(self, "food_candidates", [])),
            )
            
            response = self.model.generate_content(
                prompt,
                request_options={
                    "timeout": int(os.environ.get("GEMINI_REQUEST_TIMEOUT_SECONDS", "240"))
                },
            )
            
            response_text = response.text.strip()
            parsed_response = self._parse_response_json(response_text)
            result_json = self._coerce_result_root(parsed_response)
            
            # Parse into our data structure with plausibility checks
            records = []
            for item in self._iter_candidate_rows(result_json.get("data", [])):
                metadata = item.get("metadata", {})
                if not isinstance(metadata, dict):
                    metadata = {}
                for evidence_key in ("table_label", "page_hint", "source_quote"):
                    if item.get(evidence_key) is not None:
                        metadata[evidence_key] = item.get(evidence_key)
                record = NutrientRecord(
                    food_name=item["food_name"],
                    nutrient_name=item["nutrient_name"],
                    amount=float(item.get("amount", item.get("value"))),
                    unit=item["unit"],
                    basis=item.get("basis", "100g"),
                    preparation_state=item.get("preparation_state", "raw"),
                    sample_size=item.get("sample_size"),
                    confidence=float(item.get("confidence", 0.5)),
                    source_citation=item.get("source_citation", "Not specified"),
                    metadata=metadata,
                    table_label=item.get("table_label"),
                    page_hint=self._coerce_int(item.get("page_hint")),
                    source_quote=item.get("source_quote"),
                    raw_food_name=item.get("raw_food_name") or item.get("paper_food_name") or item["food_name"],
                    raw_nutrient_name=item.get("raw_nutrient_name") or item.get("paper_nutrient_name") or item["nutrient_name"],
                    food_fdc_id=item.get("food_fdc_id"),
                    food_id=item.get("food_id"),
                    entity_id=item.get("entity_id"),
                    db_food_id=item.get("db_food_id"),
                    nutrient_id=item.get("nutrient_id"),
                    nutrient_db_id=item.get("nutrient_db_id"),
                    master_nutrient_id=item.get("master_nutrient_id"),
                    db_nutrient_id=item.get("db_nutrient_id"),
                )
                
                # Run plausibility checks
                record.flags = self._check_plausibility(record)
                records.append(record)
            
            decision_kind = str(result_json.get("decision_kind") or "").strip().lower()
            is_useful = bool(result_json.get("is_useful", False))
            if decision_kind not in {"has_data", "no_usable_data"}:
                decision_kind = "has_data" if is_useful else "no_usable_data"
            is_useful = decision_kind == "has_data"
            paper_decision_confidence = self._coerce_float(
                result_json.get("paper_decision_confidence"),
                result_json.get("overall_confidence", 0.0),
            )
            extraction_confidence = self._coerce_float(
                result_json.get("extraction_confidence"),
                self._confidence_from_records(records),
            )
            return ExtractionResult(
                pmc_id=paper.get("pmc_id", ""),
                is_useful=is_useful,
                reasoning=result_json.get("reasoning", "No reasoning provided"),
                overall_confidence=float(result_json.get("overall_confidence", min(paper_decision_confidence, extraction_confidence))),
                data=records,
                decision_kind=decision_kind,
                no_data_reason=str(result_json.get("no_data_reason") or ""),
                paper_type=str(result_json.get("paper_type") or ""),
                database_value=str(result_json.get("database_value") or ""),
                paper_decision_confidence=paper_decision_confidence,
                extraction_confidence=extraction_confidence,
                source_term=paper.get("source_term", ""),
                raw_response_text=response_text,
            )
            
        except Exception as e:
            print(f"   ⚠️ Extraction error for {paper.get('pmc_id')}: {e}")
            return ExtractionResult(
                pmc_id=paper.get("pmc_id", ""),
                is_useful=False,
                reasoning=f"Extraction error: {str(e)}",
                overall_confidence=0.0,
                data=[],
                decision_kind="no_usable_data",
                no_data_reason="extraction_error",
                source_term=paper.get("source_term", "")
            )

    def _parse_response_json(self, response_text: str) -> Any:
        cleaned = self._strip_markdown_json_fence(response_text)
        try:
            return json.loads(cleaned)
        except JSONDecodeError as original_error:
            candidates = list(self._balanced_json_candidates(cleaned))
            parsed_candidates: list[Any] = []
            for candidate in candidates:
                try:
                    parsed = json.loads(candidate)
                except JSONDecodeError:
                    continue
                if self._looks_like_result_root(parsed):
                    return parsed
                parsed_candidates.append(parsed)
            if parsed_candidates:
                return parsed_candidates[0]
            raise original_error

    def _strip_markdown_json_fence(self, response_text: str) -> str:
        cleaned = response_text.strip()
        if not cleaned.startswith("```"):
            return cleaned
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _balanced_json_candidates(self, text: str):
        for start, char in enumerate(text):
            if char not in "{[":
                continue
            closing = "}" if char == "{" else "]"
            stack = [closing]
            in_string = False
            escape = False
            for index in range(start + 1, len(text)):
                current = text[index]
                if in_string:
                    if escape:
                        escape = False
                    elif current == "\\":
                        escape = True
                    elif current == '"':
                        in_string = False
                    continue
                if current == '"':
                    in_string = True
                elif current == "{":
                    stack.append("}")
                elif current == "[":
                    stack.append("]")
                elif current in "}]":
                    if not stack or current != stack[-1]:
                        break
                    stack.pop()
                    if not stack:
                        yield text[start : index + 1]
                        break

    def _looks_like_result_root(self, parsed_json: Any) -> bool:
        if isinstance(parsed_json, list):
            return True
        if not isinstance(parsed_json, dict):
            return False
        return any(
            key in parsed_json
            for key in (
                "data",
                "decision_kind",
                "is_useful",
                "reasoning",
                "overall_confidence",
            )
        )

    def _coerce_result_root(self, parsed_json: Any) -> dict:
        if isinstance(parsed_json, dict):
            if "decision_kind" not in parsed_json:
                parsed_json["decision_kind"] = "has_data" if parsed_json.get("is_useful") else "no_usable_data"
            if "is_useful" not in parsed_json:
                parsed_json["is_useful"] = parsed_json.get("decision_kind") == "has_data"
            data = parsed_json.get("data", [])
            if not isinstance(data, list):
                parsed_json = dict(parsed_json)
                parsed_json["data"] = []
            return parsed_json
        if isinstance(parsed_json, list):
            return {
                "reasoning": "Model returned a top-level data array; treating it as candidate food composition rows.",
                "decision_kind": "has_data" if parsed_json else "no_usable_data",
                "is_useful": bool(parsed_json),
                "overall_confidence": self._confidence_from_rows(parsed_json),
                "paper_decision_confidence": self._confidence_from_rows(parsed_json),
                "extraction_confidence": self._confidence_from_rows(parsed_json),
                "data": parsed_json,
            }
        raise ValueError(f"Expected JSON object or data array, got {type(parsed_json).__name__}")

    def _format_nutrient_catalog(self, rows: list[dict]) -> str:
        catalog_rows = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("id") or "").strip()
            name = str(row.get("standard_name") or row.get("name") or "").strip()
            if row_id and name:
                catalog_rows.append({"id": row_id, "standard_name": name})
        if not catalog_rows:
            return "[]"
        return json.dumps(catalog_rows, ensure_ascii=False, separators=(",", ":"))

    def _format_food_candidates(self, rows: list[dict]) -> str:
        candidate_rows = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("id") or "").strip()
            name = str(row.get("canonical_name") or row.get("name") or "").strip()
            if row_id and name:
                candidate = {"food_fdc_id": row_id, "canonical_name": name}
                aliases = row.get("alias_names") or row.get("aliases")
                if isinstance(aliases, list):
                    candidate["aliases"] = [str(alias).strip() for alias in aliases[:10] if str(alias).strip()]
                candidate_rows.append(candidate)
        if not candidate_rows:
            return "[]"
        return json.dumps(candidate_rows, ensure_ascii=False, separators=(",", ":"))

    def _confidence_from_rows(self, rows: list) -> float:
        confidences = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                confidences.append(float(row.get("confidence", row.get("overall_confidence"))))
            except (TypeError, ValueError):
                continue
        if not confidences:
            return 0.5 if rows else 0.0
        return max(0.0, min(1.0, sum(confidences) / len(confidences)))

    def _confidence_from_records(self, records: list[NutrientRecord]) -> float:
        if not records:
            return 0.0
        return max(0.0, min(1.0, sum(float(record.confidence or 0.0) for record in records) / len(records)))

    def _coerce_float(self, value: object, default: object = 0.0) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            try:
                return max(0.0, min(1.0, float(default)))
            except (TypeError, ValueError):
                return 0.0

    def _coerce_int(self, value: object) -> int | None:
        try:
            if value is None or value == "":
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _iter_candidate_rows(self, data: list) -> list[dict]:
        rows = []
        for item in data:
            if not isinstance(item, dict):
                continue
            nutrients = item.get("nutrients")
            if isinstance(nutrients, list):
                for nutrient in nutrients:
                    if not isinstance(nutrient, dict):
                        continue
                    rows.append(self._standardize_candidate_row({**self._food_context(item), **nutrient}))
                continue
            rows.append(self._standardize_candidate_row(item))
        return [row for row in rows if row]

    def _food_context(self, item: dict) -> dict:
        return {
            "food_name": item.get("food_name") or item.get("food") or item.get("name"),
            "basis": item.get("basis"),
            "preparation_state": item.get("preparation_state"),
            "sample_size": item.get("sample_size"),
            "source_citation": item.get("source_citation"),
            "metadata": item.get("metadata"),
        }

    def _standardize_candidate_row(self, item: dict) -> dict | None:
        row = dict(item)
        row["food_name"] = row.get("food_name") or row.get("food") or row.get("food_item") or row.get("name")
        row["nutrient_name"] = row.get("nutrient_name") or row.get("nutrient")
        if "amount" not in row and "value" in row:
            row["amount"] = row.get("value")
        if not row.get("food_name") or not row.get("nutrient_name") or row.get("amount") is None or not row.get("unit"):
            return None
        return row

    
    def _check_plausibility(self, record: NutrientRecord) -> List[str]:
        """Run sanity checks on extracted values"""
        flags = []
        
        # Check for obviously wrong values (nutrient-specific ranges)
        nutrient_limits = {
            "vitamin c": (0, 2000),  # mg/100g
            "vitamin a": (0, 30000),  # IU/100g
            "protein": (0, 100),  # g/100g
            "fat": (0, 100),  # g/100g
            "carbohydrate": (0, 100),  # g/100g
            "iron": (0, 200),  # mg/100g
            "calcium": (0, 5000),  # mg/100g
        }
        
        nutrient_lower = record.nutrient_name.lower()
        for nutrient_key, (min_val, max_val) in nutrient_limits.items():
            if nutrient_key in nutrient_lower:
                # Normalize to mg/100g or g/100g for comparison
                amount = record.amount
                if "g/100" in record.unit.lower():
                    if nutrient_key in ["protein", "fat", "carbohydrate"]:
                        if not (min_val <= amount <= max_val):
                            flags.append(f"Implausible {record.nutrient_name}: {amount} {record.unit}")
                elif "mg/100" in record.unit.lower():
                    if nutrient_key not in ["protein", "fat", "carbohydrate"]:
                        if not (min_val <= amount <= max_val):
                            flags.append(f"Implausible {record.nutrient_name}: {amount} {record.unit}")
        
        # Check confidence
        if record.confidence < 0.5:
            flags.append(f"Low confidence: {record.confidence}")
        
        # Check source citation
        if record.source_citation == "Not specified":
            flags.append("Missing source citation")
        
        return flags
    
    def save_result(self, result: ExtractionResult, output_dir: str = "data/extracted"):
        """Save extraction result to JSON file"""
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = os.path.join(output_dir, f"{result.pmc_id}_extracted.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "pmc_id": result.pmc_id,
                "is_useful": result.is_useful,
                "reasoning": result.reasoning,
                "overall_confidence": result.overall_confidence,
                "source_term": result.source_term,
                "records_count": len(result.data),
                "data": [asdict(r) for r in result.data]
            }, f, indent=2, ensure_ascii=False)

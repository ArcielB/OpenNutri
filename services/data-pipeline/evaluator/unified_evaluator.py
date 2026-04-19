"""
Unified LLM Evaluator & Extractor

Single-pass evaluation: Filter papers AND extract structured food composition data.
"""

import os
import json
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict

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
    metadata: Dict[str, any]
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
    source_term: str = ""


class UnifiedEvaluator:
    """
    Evaluates papers and extracts food composition data in a single LLM call.
    """
    
    EXTRACTION_PROMPT = """You are a food composition database curator extracting structured data from scientific papers.

**Task**: Determine if this paper contains usable food composition data, and if so, extract it.

**USEFULNESS Criteria**:
- is_useful = true if: Contains tables with specific foods and their nutrient values (e.g., "Apple: 52 kcal, 0.3g fat, 14g carbs"). Quantitative data: mg/100g, g/100g, percentages, etc. Clear food-nutrient mappings.
- is_useful = false if: Clinical trials about health effects, review papers without original data, methodology papers, supplement/pill studies, or papers about non-food items.

**Instructions**:
1. Read the paper carefully.
2. Provide a detailed reasoning for your decision (why it is or isn't useful).
3. Determine if it is useful (is_useful: true/false).
4. Assign an overall_confidence score (0.0-1.0) for the paper.
5. If is_useful is true: Extract ALL food-nutrient data from tables.
6. For each data point, ensure the structure matches our database requirements.

**Output Format** (Strict JSON only):
```json
{{
  "reasoning": "Detailed explanation of why this paper is or is not useful for food composition data",
  "is_useful": true | false,
  "overall_confidence": 0.95,
  "data": [
    {{
      "food_name": "Apple, raw, with skin",
      "nutrient_name": "Vitamin C",
      "amount": 4.6,
      "unit": "mg",
      "basis": "100g",
      "preparation_state": "raw",
      "sample_size": 50,
      "confidence": 0.98,
      "source_citation": "Table 2, row 3",
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
- nutrient_name: Standard nutrient name (e.g., Protein, Iron, Vitamin C).
- amount: Numeric value (float).
- unit: Measurement unit (g, mg, kcal, etc.).
- basis: Reference basis (e.g., "100g", "dry weight basis", "per serving").
- preparation_state: State of the food (raw, cooked, boiled, dried, etc.).
- sample_size: Number of samples (n=) as an integer, or null if not stated.
- confidence: 0.0-1.0 score for THIS specific data point.
- source_citation: SPECIFIC location (e.g., "Table 1, Row 2").

**Critical Rules**:
1. Return ONLY valid JSON.
2. Do NOT hallucinate values.
3. If is_useful is false, return an empty "data" array.
4. Extract ALL nutrients from tables, not just a sample.
5. Standardize units where possible (e.g., convert % to g/100g if basis is clear).

**Paper Content**:
Title: {title}

Full Text:
{full_text}

**Your Response** (JSON only, no other text):"""

    def __init__(self, raw_lake_dir: str = "data/raw_lake", api_key: str = None):
        self.raw_lake_dir = raw_lake_dir
        
        # Try to get API key from: 1) argument, 2) env var, 3) config.py
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            try:
                from crawler.config import GEMINI_API_KEY
                self.api_key = GEMINI_API_KEY
            except ImportError:
                pass
        
        self.model = None
        
        if HAS_GEMINI and self.api_key:
            genai.configure(api_key=self.api_key)
            # Use JSON mode for structured output
            self.model = genai.GenerativeModel(
                'gemini-3-flash-preview',  # Gemini 3 Flash
                generation_config={
                    "response_mime_type": "application/json"
                }
            )
            print("🤖 Unified Evaluator initialized with Gemini 3 Flash (High Accuracy Mode)")

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
                source_term=paper.get("source_term", "")
            )
        
        try:
            # Extract text from XML
            from crawler.processing.content import extract_full_text
            full_text = extract_full_text(paper.get("raw_xml", ""))
            
            # Truncate if too long (safety limit: ~1M tokens = ~4M chars)
            if len(full_text) > 4_000_000:
                full_text = full_text[:4_000_000] + "\n\n[TRUNCATED - Paper exceeded token limit]"
            
            prompt = self.EXTRACTION_PROMPT.format(
                title=paper.get("metadata", {}).get("title", paper.get("title", "Unknown Title")),
                full_text=full_text
            )
            
            response = self.model.generate_content(prompt)
            
            # Clean up response (sometimes LLM adds markdown code blocks)
            response_text = response.text.strip()
            
            if response_text.startswith("```"):
                # Remove code block markers
                lines = response_text.split("\n")
                if lines[0].startswith("```json"):
                    response_text = "\n".join(lines[1:-1])
                else:
                    response_text = "\n".join(lines[1:-1])
            
            result_json = json.loads(response_text)
            
            # Parse into our data structure with plausibility checks
            records = []
            for item in result_json.get("data", []):
                record = NutrientRecord(
                    food_name=item["food_name"],
                    nutrient_name=item["nutrient_name"],
                    amount=float(item["amount"]),
                    unit=item["unit"],
                    basis=item.get("basis", "100g"),
                    preparation_state=item.get("preparation_state", "raw"),
                    sample_size=item.get("sample_size"),
                    confidence=float(item.get("confidence", 0.5)),
                    source_citation=item.get("source_citation", "Not specified"),
                    metadata=item.get("metadata", {})
                )
                
                # Run plausibility checks
                record.flags = self._check_plausibility(record)
                records.append(record)
            
            return ExtractionResult(
                pmc_id=paper.get("pmc_id", ""),
                is_useful=bool(result_json.get("is_useful", False)),
                reasoning=result_json.get("reasoning", "No reasoning provided"),
                overall_confidence=float(result_json.get("overall_confidence", 0.0)),
                data=records,
                source_term=paper.get("source_term", "")
            )
            
        except Exception as e:
            print(f"   ⚠️ Extraction error for {paper.get('pmc_id')}: {e}")
            return ExtractionResult(
                pmc_id=paper.get("pmc_id", ""),
                is_useful=False,
                reasoning=f"Extraction error: {str(e)}",
                overall_confidence=0.0,
                data=[],
                source_term=paper.get("source_term", "")
            )

    
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

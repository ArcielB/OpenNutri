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
    confidence: float  # 0.0-1.0 confidence score
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
    verdict: str  # "PASS" or "FAIL"
    reason: str
    data: List[NutrientRecord]
    source_term: str = ""


class UnifiedEvaluator:
    """
    Evaluates papers and extracts food composition data in a single LLM call.
    """
    
    EXTRACTION_PROMPT = """You are a food composition database curator extracting structured data from scientific papers.

**Task**: Determine if this paper contains usable food composition data, and if so, extract it.

**PASS Criteria** (extract data):
- Contains tables with specific foods and their nutrient values
- Quantitative data: mg/100g, g/100g, percentages, etc.
- Clear food-nutrient mappings

**FAIL Criteria** (skip):
- Clinical trials (effects on health, not composition)
- Review papers without original data
- Methodology papers
- Supplement/pill studies (not whole foods)
- Comparative studies without absolute values

**Instructions**:
1. Read the paper carefully
2. Decide: PASS or FAIL
3. If PASS: Extract ALL food-nutrient data from tables
4. For each data point, extract metadata when available

**Output Format** (JSON):
```json
{{
  "verdict": "PASS" | "FAIL",
  "reason": "One sentence explanation",
  "data": [
    {{
      "food_name": "Apple, raw, with skin",
      "nutrient_name": "Vitamin C",
      "amount": 4.6,
      "unit": "mg/100g",
      "confidence": 0.95,
      "source_citation": "Table 2, row 3",
      "metadata": {{
        "preparation": "raw",
        "state": "wet weight",
        "cultivar": "Fuji",
        "location": "Japan",
        "harvest_date": "2024-09",
        "sample_size": 50,
        "analysis_method": "HPLC",
        "source_table": "Table 2",
        "storage": "fresh",
        "edible_portion": "with skin"
      }}
    }}
  ]
}}
```


**Metadata Fields** (use null if not stated):
- preparation: raw, cooked, boiled, fried, dried, etc.
- state: wet weight, dry weight, as consumed
- cultivar: variety/breed
- location: country/region of origin
- harvest_date: when harvested/produced
- sample_size: number of samples analyzed (n=)
- analysis_method: HPLC, spectroscopy, etc.
- source_table: which table in the paper
- storage: fresh, frozen, canned, etc.
- edible_portion: with/without skin, seeds, etc.

**Critical Verification Requirements**:
1. **confidence**: Rate 0.0-1.0 based on:
   - 1.0 = Clear table with unambiguous values
   - 0.7-0.9 = Data present but some interpretation needed
   - 0.5-0.7 = Ambiguous or estimated values
   - <0.5 = Uncertain, should be manually reviewed

2. **source_citation**: ALWAYS cite where you found this value:
   - "Table 2, row 5, column 3"
   - "Results section, paragraph 2"
   - "Supplementary Table S1"
   - Be SPECIFIC. This is critical for verification.

3. **Do NOT hallucinate**:
   - If you cannot find a value, DO NOT include it
   - If metadata is unclear, use null
   - If units are ambiguous, note in source_citation

4. **Extract ALL nutrients from tables**, not just a sample.

5. **Standardize units** (convert % to g/100g if needed).

6. If FAIL, return empty data array.

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
                'gemini-3-flash-preview',  # Correct model name
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
            ExtractionResult with verdict and extracted data
        """
        if not self.model:
            return ExtractionResult(
                pmc_id=paper.get("pmc_id", ""),
                verdict="FAIL",
                reason="No LLM available",
                data=[],
                source_term=paper.get("source_term", "")
            )
        
        try:
            # Extract text from XML
            from crawler.processing.content import extract_full_text
            full_text = extract_full_text(paper.get("raw_xml", ""))
            
            # Truncate if too long (safety limit: ~1M tokens = ~750k words = ~4M chars)
            if len(full_text) > 4_000_000:
                full_text = full_text[:4_000_000] + "\n\n[TRUNCATED - Paper exceeded token limit]"
            
            prompt = self.EXTRACTION_PROMPT.format(
                title=paper.get("metadata", {}).get("title", ""),
                full_text=full_text
            )
            
            response = self.model.generate_content(prompt)
            
            # Clean up response (sometimes LLM adds markdown code blocks)
            response_text = response.text.strip()
            if response_text.startswith("```"):
                # Remove code block markers
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])  # Skip first and last lines
            if response_text.startswith("json"):
                response_text = response_text[4:].strip()  # Remove "json" language tag
            
            result_json = json.loads(response_text)
            
            # Parse into our data structure with plausibility checks
            records = []
            for item in result_json.get("data", []):
                record = NutrientRecord(
                    food_name=item["food_name"],
                    nutrient_name=item["nutrient_name"],
                    amount=float(item["amount"]),
                    unit=item["unit"],
                    confidence=float(item.get("confidence", 0.5)),
                    source_citation=item.get("source_citation", "Not specified"),
                    metadata=item.get("metadata", {})
                )
                
                # Run plausibility checks
                record.flags = self._check_plausibility(record)
                records.append(record)
            
            return ExtractionResult(
                pmc_id=paper.get("pmc_id", ""),
                verdict=result_json["verdict"],
                reason=result_json["reason"],
                data=records,
                source_term=paper.get("source_term", "")
            )
            
        except Exception as e:
            print(f"   ⚠️ Extraction error for {paper.get('pmc_id')}: {e}")
            return ExtractionResult(
                pmc_id=paper.get("pmc_id", ""),
                verdict="FAIL",
                reason=f"Extraction error: {str(e)}",
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
                "verdict": result.verdict,
                "reason": result.reason,
                "source_term": result.source_term,
                "records_count": len(result.data),
                "data": [asdict(r) for r in result.data]
            }, f, indent=2, ensure_ascii=False)

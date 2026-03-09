"""
Nutrient Extractor - Full Paper Approach

Sends the entire paper to Gemini for extraction.
Simpler, includes all context.
"""

import json
import os
from typing import List, Dict
from dataclasses import dataclass, asdict

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


@dataclass
class NutrientEntry:
    """A single extracted nutrient value."""
    food: str
    nutrient: str
    value: float
    unit: str
    per_amount: str = "100g"
    source_paper: str = ""
    notes: str = ""  # e.g., "raw", "cooked", "dried"


EXTRACTION_PROMPT = '''You are a nutrition data extraction expert.

Analyze this scientific paper and extract ALL food composition/nutrient data from the tables.

For each nutrient value, extract:
- food: The food name (e.g., "Chickpea", "Hummus")
- nutrient: The nutrient name (e.g., "Protein", "Iron", "Vitamin C")
- value: The numeric value only
- unit: The measurement unit (e.g., "g", "mg", "µg", "kcal")
- per_amount: The reference amount (usually "100g" or "per serving")
- notes: Any important context (e.g., "raw", "cooked", "dried basis")

PAPER CONTENT:
{paper_content}

IMPORTANT INSTRUCTIONS:
1. Extract EVERY nutrient value from ALL composition tables
2. Create a separate entry for each food-nutrient combination
3. Include preparation state in notes (raw/cooked/dried)
4. Skip non-numeric values like "trace", "N/A", or ranges
5. Return ONLY a valid JSON array, no markdown formatting

Example output format:
[
  {{"food": "Chickpea", "nutrient": "Protein", "value": 19.3, "unit": "g", "per_amount": "100g", "notes": "raw, dry weight"}},
  {{"food": "Chickpea", "nutrient": "Iron", "value": 4.31, "unit": "mg", "per_amount": "100g", "notes": ""}}
]

JSON output:'''


class NutrientExtractor:
    """Extracts structured nutrient data using Gemini."""
    
    def __init__(self, api_key: str = None):
        self.model = None
        
        if not HAS_GEMINI:
            print("⚠️ google-generativeai not installed. Run: pip install google-generativeai")
            return
        
        # Try to get API key from various sources
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            try:
                from crawler.config import GEMINI_API_KEY
                api_key = GEMINI_API_KEY
            except (ImportError, AttributeError):
                pass
        
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            print("✅ Gemini extractor initialized")
        else:
            print("⚠️ No GEMINI_API_KEY found. Add to crawler/config.py or set environment variable.")
    
    def extract_from_paper(self, paper_path: str) -> List[NutrientEntry]:
        """Extract nutrients from a paper file."""
        if not self.model:
            print("❌ No model available")
            return []
        
        # Load paper
        with open(paper_path, 'r') as f:
            doc = json.load(f)
        
        paper_id = doc.get('pmc_id', 'unknown')
        xml_content = doc.get('raw_xml', '')
        
        # Clean XML for better readability (remove some noise)
        # Keep structure but reduce token count slightly
        import re
        # Remove xref, ext-link and styling tags but keep content
        xml_clean = re.sub(r'<(xref|ext-link|italic|bold|sup|sub)[^>]*>(.*?)</\1>', r'\2', xml_content)
        
        print(f"📄 Processing {paper_id} ({len(xml_clean)//1000}K chars)...")
        
        try:
            prompt = EXTRACTION_PROMPT.format(paper_content=xml_clean[:100000])  # Limit to ~100K chars
            response = self.model.generate_content(prompt)
            
            # Parse JSON response
            text = response.text.strip()
            
            # Clean up markdown code blocks if present
            if "```" in text:
                text = re.sub(r'```json\s*', '', text)
                text = re.sub(r'```\s*', '', text)
            text = text.strip()
            
            entries_raw = json.loads(text)
            
            # Convert to NutrientEntry objects
            entries = []
            for e in entries_raw:
                try:
                    entries.append(NutrientEntry(
                        food=str(e.get('food', '')),
                        nutrient=str(e.get('nutrient', '')),
                        value=float(e.get('value', 0)),
                        unit=str(e.get('unit', '')),
                        per_amount=str(e.get('per_amount', '100g')),
                        source_paper=paper_id,
                        notes=str(e.get('notes', ''))
                    ))
                except (ValueError, TypeError) as err:
                    continue
            
            print(f"   ✅ Extracted {len(entries)} nutrient values")
            return entries
            
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parse error: {e}")
            print(f"   Response preview: {text[:200]}...")
            return []
        except Exception as e:
            print(f"   ❌ Extraction error: {e}")
            return []
    
    def extract_batch(self, paper_paths: List[str], delay: float = 4.0) -> Dict[str, List[NutrientEntry]]:
        """Extract from multiple papers with rate limiting."""
        import time
        
        results = {}
        for i, path in enumerate(paper_paths):
            print(f"\n[{i+1}/{len(paper_paths)}]", end=" ")
            entries = self.extract_from_paper(path)
            
            # Get paper ID from path
            paper_id = os.path.basename(path).replace('.json', '')
            results[paper_id] = entries
            
            # Rate limit for free tier (15 req/min = 4 sec between)
            if i < len(paper_paths) - 1:
                time.sleep(delay)
        
        return results


def extract_and_save(paper_paths: List[str], output_path: str = "data/extracted_nutrients.json"):
    """Extract nutrients from papers and save to JSON."""
    extractor = NutrientExtractor()
    
    if not extractor.model:
        return
    
    results = extractor.extract_batch(paper_paths)
    
    # Convert to serializable format
    output = {}
    for paper_id, entries in results.items():
        output[paper_id] = [asdict(e) for e in entries]
    
    # Save
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    total = sum(len(v) for v in output.values())
    print(f"\n📊 Saved {total} nutrient entries to {output_path}")

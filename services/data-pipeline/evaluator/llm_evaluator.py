"""
LLM-based Paper Evaluator

Uses a language model to read paper content and determine if it contains
usable food composition data.
"""

import os
from typing import Optional
from .base import PaperEvaluator, EvaluationResult

# Check for available LLM libraries
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


class LLMEvaluator(PaperEvaluator):
    """
    Evaluates papers using an LLM to determine composition data presence.
    """
    
    EVALUATION_PROMPT = """You are a scientific paper evaluator for a food nutrition database.

Your task: Determine if this paper contains USABLE food composition data.

GOOD papers have:
- Tables with specific foods and their nutrient values (e.g., "Apple: 52 kcal, 0.3g fat, 14g carbs")
- Quantitative data: mg/100g, g/100g, percentages, etc.
- Clear food-nutrient mappings

BAD papers are:
- Reviews without original data
- Clinical trials about effects (not composition)
- Methodology papers
- Papers about supplements/pills rather than whole foods

Paper Title: {title}
Abstract: {abstract}

Respond with ONLY:
GOOD or BAD
Reason: <one sentence explanation>"""

    def __init__(self, raw_lake_dir: str = "data/raw_lake", api_key: str = None):
        super().__init__(raw_lake_dir)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = None
        
        if HAS_GEMINI and self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            print("🤖 LLM Evaluator initialized with Gemini")
        else:
            print("⚠️ No LLM available. Falling back to heuristics.")

    def evaluate_paper(self, paper: dict) -> EvaluationResult:
        """Evaluate using LLM if available, else fall back to heuristics."""
        if not self.model:
            return super().evaluate_paper(paper)
            
        try:
            prompt = self.EVALUATION_PROMPT.format(
                title=paper.get("title", ""),
                abstract=paper.get("abstract", "")[:2000]  # Truncate long abstracts
            )
            
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # Parse response
            lines = text.split("\n")
            verdict = lines[0].upper().strip()
            reason = lines[1].replace("Reason:", "").strip() if len(lines) > 1 else "LLM evaluation"
            
            is_good = "GOOD" in verdict
            
            return EvaluationResult(
                pmc_id=paper.get("pmc_id", ""),
                is_good=is_good,
                reason=f"LLM: {reason}",
                source_term=paper.get("source_term", "")
            )
            
        except Exception as e:
            print(f"   ⚠️ LLM error for {paper.get('pmc_id')}: {e}")
            # Fall back to heuristics
            return super().evaluate_paper(paper)

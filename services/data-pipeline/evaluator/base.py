"""
Phase 2: Paper Evaluator

Reads pending papers from raw_lake, uses LLM to determine if they contain
usable food composition data, and feeds labels back to the Harvester.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class EvaluationResult:
    """Result of evaluating a single paper."""
    pmc_id: str
    is_good: bool
    reason: str
    extracted_foods: List[str] = None
    extracted_nutrients: List[str] = None
    source_term: str = ""


class PaperEvaluator:
    """
    Evaluates pending papers to determine if they contain food composition data.
    
    This is the bridge between Phase 1 (Harvest) and the actual data extraction.
    """
    
    def __init__(self, raw_lake_dir: str = "data/raw_lake"):
        self.raw_lake_dir = Path(raw_lake_dir)
        
    def get_pending_papers(self) -> List[Dict]:
        """
        Load all papers from raw_lake that need evaluation.
        
        Returns list of dicts with pmc_id, title, source_term, file_path.
        """
        pending = []
        
        for json_file in self.raw_lake_dir.glob("PMC*.json"):
            try:
                with open(json_file, 'r') as f:
                    doc = json.load(f)
                    
                pending.append({
                    "pmc_id": doc.get("pmc_id", ""),
                    "title": doc.get("metadata", {}).get("title", "Unknown"),
                    "abstract": doc.get("metadata", {}).get("abstract", ""),
                    "source_term": doc.get("source_term", ""),
                    "file_path": str(json_file),
                    "raw_xml": doc.get("raw_xml", "")
                })
            except Exception as e:
                print(f"⚠️ Error loading {json_file}: {e}")
                
        return pending
    
    def evaluate_paper(self, paper: Dict) -> EvaluationResult:
        """
        Evaluate a single paper. 
        
        Override this method to implement LLM-based evaluation.
        Default implementation uses simple heuristics as placeholder.
        """
        # Placeholder heuristic (to be replaced with LLM)
        title = (paper.get("title") or "").lower()
        abstract = (paper.get("abstract") or "").lower()
        text = title + " " + abstract
        
        # Simple keyword check (NOT the real evaluation - just a placeholder)
        composition_keywords = ["composition", "nutritive", "nutrient", "proximate", "mg/100g", "protein content"]
        has_keywords = any(kw in text for kw in composition_keywords)
        
        return EvaluationResult(
            pmc_id=paper.get("pmc_id", ""),
            is_good=has_keywords,
            reason="Heuristic: keyword match" if has_keywords else "Heuristic: no composition keywords",
            source_term=paper.get("source_term", "")
        )
    
    def run_evaluation(self, limit: int = None) -> List[EvaluationResult]:
        """
        Evaluate pending papers and return results.
        
        Args:
            limit: Max papers to evaluate (None = all)
        """
        pending = self.get_pending_papers()
        if limit:
            pending = pending[:limit]
            
        print(f"📋 Evaluating {len(pending)} pending papers...")
        
        results = []
        for paper in pending:
            result = self.evaluate_paper(paper)
            results.append(result)
            
            status = "✅ GOOD" if result.is_good else "❌ BAD"
            print(f"   {status}: {paper['pmc_id']} - {result.reason}")
            
        return results

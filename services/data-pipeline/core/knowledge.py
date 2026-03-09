"""
Knowledge Base - The Harvester's Brain

Manages:
- Search terms (with scores from feedback)
- Foods (from Supabase)
- Nutrients (from Supabase)
- Processed paper IDs
"""

import json
import os
from typing import List, Iterator, Tuple
from .types import KnowledgeState, SearchTerm
from .data_source import get_data_source


class KnowledgeBase:
    """
    The Brain of the crawler.
    Manages search terms, foods from DB, and the feedback loop state.
    """
    
    def __init__(self, storage_path: str = "data/knowledge.json"):
        self.storage_path = storage_path
        self.state = KnowledgeState()
        self.data_source = get_data_source()
        
        # Cache for systematic cycling
        self._foods_list: List[str] = []
        self._nutrients_list: List[str] = []
        self._current_food_idx: int = 0
        self._current_nutrient_idx: int = 0
        
        self.load()
        self._load_from_db()

    def load(self):
        """Load state from disk or initialize with seeds."""
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                
            # Reconstruct objects from dicts
            for txt, t_data in data.get("terms", {}).items():
                self.state.terms[txt] = SearchTerm(**t_data)
                
            self.state.processed_pmc_ids = set(data.get("processed_pmc_ids", []))
            
            # Restore cycling positions
            self._current_food_idx = data.get("current_food_idx", 0)
            self._current_nutrient_idx = data.get("current_nutrient_idx", 0)
            
            print(f"🧠 Loaded KnowledgeBase: {len(self.state.terms)} terms, {len(self.state.processed_pmc_ids)} processed papers.")
        else:
            self._seed_initial_terms()

    def _load_from_db(self):
        """Load foods and nutrients from Supabase."""
        self._foods_list = self.data_source.get_foods()
        self._nutrients_list = self.data_source.get_nutrients()
        
        # Bounds check for cycling positions
        if self._current_food_idx >= len(self._foods_list):
            self._current_food_idx = 0
        if self._current_nutrient_idx >= len(self._nutrients_list):
            self._current_nutrient_idx = 0

    def save(self):
        """Persist state to disk."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        data = self.state.to_dict()
        # Also save cycling positions
        data["current_food_idx"] = self._current_food_idx
        data["current_nutrient_idx"] = self._current_nutrient_idx
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
            
    def _seed_initial_terms(self):
        """Bootstrap with default search terms if no state exists."""
        print("🌱 Seeding initial search terms...")
        
        # Seed Terms (High precision anchors for food composition)
        seeds = [
            "food composition",
            "nutritive value",
            "nutrient content",
            "proximate analysis",
            "nutritional characterization",
            "chemical composition",
            "mineral content",
            "vitamin content"
        ]
        for s in seeds:
            self.add_term(s)
            
        self.save()

    def add_term(self, text: str) -> bool:
        """Add a new search term."""
        text = text.lower().strip()
        if text and text not in self.state.terms:
            self.state.terms[text] = SearchTerm(text=text)
            return True
        return False

    def mark_paper_processed(self, pmc_id: str):
        self.state.processed_pmc_ids.add(pmc_id)

    def is_processed(self, pmc_id: str) -> bool:
        return pmc_id in self.state.processed_pmc_ids

    def update_term_score(self, term_text: str, is_good: bool):
        """Update term stats based on evaluation feedback."""
        term_text = term_text.lower().strip()
        if term_text in self.state.terms:
            term = self.state.terms[term_text]
            if is_good:
                term.good_count += 1
            else:
                term.bad_count += 1

    def get_best_terms(self, limit: int = 5) -> List[SearchTerm]:
        """Get terms with highest discriminative score."""
        sorted_terms = sorted(
            self.state.terms.values(), 
            key=lambda t: (t.score, t.good_count + t.bad_count), 
            reverse=True
        )
        return sorted_terms[:limit]
    
    def get_all_terms(self) -> List[SearchTerm]:
        """Get all terms for systematic cycling."""
        return list(self.state.terms.values())
    
    # =========================================================================
    # SYSTEMATIC CYCLING - Foods and Nutrients from DB
    # =========================================================================
    
    def get_foods(self) -> List[str]:
        """Get all food names from database."""
        return self._foods_list
    
    def get_nutrients(self) -> List[str]:
        """Get all nutrient names from database."""
        return self._nutrients_list
    
    def get_next_food(self) -> Tuple[str, int, int]:
        """
        Get next food for systematic cycling.
        Returns: (food_name, current_index, total_count)
        """
        if not self._foods_list:
            return ("food", 0, 0)
            
        food = self._foods_list[self._current_food_idx]
        idx = self._current_food_idx
        total = len(self._foods_list)
        
        # Advance for next call
        self._current_food_idx = (self._current_food_idx + 1) % total
        
        return (food, idx, total)
    
    def get_next_nutrient(self) -> Tuple[str, int, int]:
        """
        Get next nutrient for systematic cycling.
        Returns: (nutrient_name, current_index, total_count)
        """
        if not self._nutrients_list:
            return ("nutrient", 0, 0)
            
        nutrient = self._nutrients_list[self._current_nutrient_idx]
        idx = self._current_nutrient_idx
        total = len(self._nutrients_list)
        
        # Advance for next call
        self._current_nutrient_idx = (self._current_nutrient_idx + 1) % total
        
        return (nutrient, idx, total)
    
    def reset_cycling(self):
        """Reset cycling positions to start."""
        self._current_food_idx = 0
        self._current_nutrient_idx = 0

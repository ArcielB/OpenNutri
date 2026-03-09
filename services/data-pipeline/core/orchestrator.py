"""
Orchestrator - Systematic Harvesting

Phase 1: Harvest papers systematically:
1. Cycle through all FOODS with each TERM
2. Cycle through all NUTRIENTS with each TERM

No random selection. Deterministic, resumable cycling.
"""

import time
from typing import List, Dict

from crawler.core.knowledge import KnowledgeBase
from crawler.harvester.pmc_harvester import PMCHarvester
from crawler.harvester.query_builder import QueryBuilder


class Orchestrator:
    """
    Systematic Paper Harvester.
    
    Cycles through:
    - All foods × all terms (Track A)
    - All nutrients × all terms (Track B)
    
    Position is persisted, so harvesting can be stopped and resumed.
    """

    # Journals known for composition data
    DISCOVERY_JOURNALS = [
        "Food Chemistry",
        "Journal of Food Composition and Analysis",
        "Foods",
        "Nutrients",
        "Journal of Agricultural and Food Chemistry"
    ]

    def __init__(self, email: str, data_dir: str = "data"):
        self.kb = KnowledgeBase(storage_path=f"{data_dir}/knowledge.json")
        self.harvester = PMCHarvester(self.kb, email, save_dir=f"{data_dir}/raw_lake")
        
    def run_systematic_harvest(self, papers_per_search: int = 5, max_searches: int = None):
        """
        Run systematic harvesting through all food-term and nutrient-term combinations.
        
        Args:
            papers_per_search: Papers to download per query
            max_searches: Stop after this many searches (None = run forever)
        """
        foods = self.kb.get_foods()
        nutrients = self.kb.get_nutrients()
        terms = self.kb.get_all_terms()
        
        print(f"🚀 Systematic Harvest Starting")
        print(f"   📋 Foods: {len(foods)}")
        print(f"   🧪 Nutrients: {len(nutrients)}")
        print(f"   🔍 Terms: {len(terms)}")
        print(f"   📄 Papers per search: {papers_per_search}")
        
        search_count = 0
        
        # Strategy A: Cycle through Foods × Terms
        print(f"\n{'='*60}")
        print("STRATEGY A: Food × Term")
        print('='*60)
        
        for food, food_idx, food_total in self._food_iterator():
            for term in terms:
                if max_searches and search_count >= max_searches:
                    print(f"\n⏹️ Reached max searches ({max_searches})")
                    self.kb.save()
                    return
                
                search_count += 1
                print(f"\n[{search_count}] Food {food_idx+1}/{food_total}: '{food}' + '{term.text}'")
                
                query = QueryBuilder.build_track_a(food, term.text)
                self._execute_search(query, papers_per_search, term.text, "Track A: Food")
                
                time.sleep(1)  # Rate limiting
        
        # Strategy B: Cycle through Nutrients × Terms
        print(f"\n{'='*60}")
        print("STRATEGY B: Nutrient × Term")
        print('='*60)
        
        for nutrient, nut_idx, nut_total in self._nutrient_iterator():
            for term in terms:
                if max_searches and search_count >= max_searches:
                    print(f"\n⏹️ Reached max searches ({max_searches})")
                    self.kb.save()
                    return
                
                search_count += 1
                print(f"\n[{search_count}] Nutrient {nut_idx+1}/{nut_total}: '{nutrient}' + '{term.text}'")
                
                query = QueryBuilder.build_track_a(nutrient, term.text)
                self._execute_search(query, papers_per_search, term.text, "Track B: Nutrient")
                
                time.sleep(1)
        
        print(f"\n✅ Systematic harvest complete! {search_count} searches executed.")
        self.kb.save()
    
    def run_quick_harvest(self, num_foods: int = 10, papers_per_search: int = 3):
        """
        Quick harvest: sample a few foods for testing.
        """
        terms = self.kb.get_best_terms(limit=3)
        
        print(f"⚡ Quick Harvest: {num_foods} foods × {len(terms)} terms")
        
        for i in range(num_foods):
            food, idx, total = self.kb.get_next_food()
            
            for term in terms:
                print(f"\n[{i+1}/{num_foods}] '{food}' + '{term.text}'")
                query = QueryBuilder.build_track_a(food, term.text)
                self._execute_search(query, papers_per_search, term.text, "Quick")
                time.sleep(1)
        
        self.kb.save()
        print(f"\n✅ Quick harvest complete!")
    
    def _execute_search(self, query: str, limit: int, source_term: str, strategy: str):
        """Execute a single search and download papers."""
        results = self.harvester.harvest(
            query, 
            limit=limit, 
            source_term=source_term, 
            strategy=strategy
        )
        
        success_count = sum(1 for r in results if r['status'] == 'success')
        print(f"   📥 Downloaded {success_count}/{limit} papers")
    
    def _food_iterator(self):
        """Iterate through all foods."""
        foods = self.kb.get_foods()
        for idx, food in enumerate(foods):
            yield food, idx, len(foods)
    
    def _nutrient_iterator(self):
        """Iterate through all nutrients."""
        nutrients = self.kb.get_nutrients()
        for idx, nutrient in enumerate(nutrients):
            yield nutrient, idx, len(nutrients)
    
    # =========================================================================
    # FEEDBACK INTERFACE
    # =========================================================================
    
    def receive_evaluation(self, pmc_id: str, is_good: bool, source_term: str = None):
        """
        Receive evaluation feedback from Phase 2.
        Updates term scores.
        """
        if source_term:
            self.kb.update_term_score(source_term, is_good=is_good)
            self.kb.save()
            print(f"   📊 Updated score for term '{source_term}' (is_good={is_good})")

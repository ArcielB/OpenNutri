"""
Core Data Types for the Harvester
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional
from datetime import datetime


@dataclass
class SearchTerm:
    """A term used to find papers, with feedback-based scoring."""
    text: str
    good_count: int = 0
    bad_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: Optional[str] = None
    
    @property
    def score(self) -> float:
        """
        Calculate discriminative score: good / (good + bad)
        New terms (< 5 uses) get a boost to encourage exploration.
        """
        total = self.good_count + self.bad_count
        if total < 5:
            return 1.0  # Exploration boost
        return self.good_count / total


@dataclass
class HarvestedPaper:
    """Metadata about a processed paper."""
    pmc_id: str
    title: str
    status: str = "pending"  # 'pending' | 'good' | 'bad'
    found_by_term: str = ""
    found_by_strategy: str = ""
    processed_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class KnowledgeState:
    """
    Persisted state of the harvester's brain.
    
    Note: Foods and nutrients come from Supabase, not stored here.
    Only terms and processed IDs are persisted locally.
    """
    terms: Dict[str, SearchTerm] = field(default_factory=dict)
    processed_pmc_ids: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> dict:
        return {
            "terms": {k: v.__dict__ for k, v in self.terms.items()},
            "processed_pmc_ids": list(self.processed_pmc_ids)
        }

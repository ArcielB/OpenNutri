import re
from typing import List, Dict, Set

class TermExtractor:
    """
    Learns new search terms from paper titles and abstracts.
    """
    
    # Stop words to ignore
    STOP_WORDS = {
        'the', 'and', 'of', 'in', 'on', 'for', 'to', 'with', 'by', 'at', 'from',
        'analysis', 'study', 'content', 'determination', 'using', 'samples'
    }

    @staticmethod
    def extract_candidates(text: str) -> List[str]:
        """
        Extract noun phrases/candidates from text.
        Simple n-gram approach for now.
        """
        if not text:
            return []
            
        candidates = []
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Bi-grams
        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i+1]
            if w1 not in TermExtractor.STOP_WORDS and w2 not in TermExtractor.STOP_WORDS:
                candidates.append(f"{w1} {w2}")
                
        # Tri-grams
        for i in range(len(words) - 2):
            w1, w2, w3 = words[i], words[i+1], words[i+2]
            if w1 not in TermExtractor.STOP_WORDS and w3 not in TermExtractor.STOP_WORDS:
                 candidates.append(f"{w1} {w2} {w3}")
                 
        return candidates

class FoodExtractor:
    """
    Extracts potential food names from validated composition tables.
    """
    
    @staticmethod
    def extract_from_tables(tables: List[Dict]) -> Set[str]:
        """
        Parsing PMC XML tables is brittle because of <thead>/<tbody> variations.
        For an MVP, we extract strings from the first column if identifiable,
        or just all cell values that look like words (not numbers).
        """
        foods = set()
        
        # Placeholder for complex table parsing logic.
        # Ideally: Locate 'Food' column -> extract rows.
        # MVP: We will trust the User (KnowledgeBase random source) + Search Terms for now.
        # To truly discover NEW foods from tables requires sophisticated layout analysis.
        
        # Attempt to grab caption text as a fallback for "what this table is about"
        for t in tables:
            caption = t.get('caption', {})
            # Extract nouns from caption?
            pass
            
        return foods

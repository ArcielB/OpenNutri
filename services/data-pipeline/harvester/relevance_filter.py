"""
Relevance Filter — Lightweight abstract-level pre-filter for food composition papers.

Scores abstracts using positive/negative keyword signals BEFORE downloading full XML.
No LLM needed — pure keyword heuristics tuned for high recall of composition data papers.
"""

import re
from typing import Dict, Tuple, List


class RelevanceFilter:
    """
    Scores paper abstracts for likelihood of containing food composition data.
    
    Design: Two-tier keyword scoring.
      - STRONG positive signals (composition data indicators) = +3 each
      - MODERATE positive signals (nutrition context) = +1 each
      - STRONG negative signals (clearly off-topic) = -5 each
      - MODERATE negative signals (likely off-topic) = -2 each
    
    Paper passes if final score >= threshold (default: 3).
    """
    
    # ── Strong positives: direct indicators of composition data ──
    STRONG_POSITIVE = [
        # Units that appear in composition tables (flexible spacing)
        r'mg\s*/\s*100\s*g', r'g\s*/\s*100\s*g', r'µg\s*/\s*100\s*g', r'ug\s*/\s*100\s*g',
        r'mg/kg', r'μg/kg', r'mg\s+kg',
        r'kcal\s*/\s*100', r'kj\s*/\s*100',
        # Composition analysis terms
        r'proximate\s+(?:analysis|composition)',
        r'food\s+composition\s+(?:table|database|data)',
        r'nutrient\s+(?:composition|content|profile|analysis)',
        r'nutritional\s+(?:composition|value|characterization|profile|analysis)',
        r'nutritive\s+value',
        r'chemical\s+composition',
        r'mineral\s+(?:content|composition|profile)',
        r'vitamin\s+(?:content|composition|profile)',
        r'fatty\s+acid\s+(?:composition|profile|content)',
        r'amino\s+acid\s+(?:composition|profile|content)',
        r'phenolic\s+(?:content|composition|profile)',
        r'antioxidant\s+(?:content|capacity|activity)',
        # Standalone "X content" patterns (e.g., "Oxalate Content of...")
        r'(?:oxalate|phytate|tannin|saponin|alkaloid)\s+content',
        r'(?:protein|lipid|fat|sugar|starch|fiber|fibre)\s+content',
    ]
    
    # ── Moderate positives: nutrition context clues ──
    MODERATE_POSITIVE = [
        r'moisture', r'\bash\b', r'crude\s+(?:protein|fat|fiber|fibre)',
        r'dietary\s+fib(?:er|re)', r'total\s+(?:protein|fat|lipid|carbohydrate)',
        r'dry\s+(?:weight|matter|basis)', r'wet\s+(?:weight|basis)',
        r'fresh\s+weight', r'dry\s+weight\s+basis',
        r'edible\s+portion',
        r'macro\s*nutrient', r'micro\s*nutrient',
        r'carotenoid', r'flavonoid', r'polyphenol', r'tocopherol',
        r'iron\s+content', r'calcium\s+content', r'zinc\s+content',
        r'phosphorus', r'potassium', r'magnesium', r'sodium\s+content',
        r'thiamin', r'riboflavin', r'niacin', r'folate', r'ascorbic\s+acid',
        r'retinol', r'oxalate', r'phytate',
        # Table references (papers with data tables)
        r'table\s+[1-9]', r'supplementary\s+table',
        # Weight basis indicators
        r'per\s+100\s*g', r'fw\b', r'dw\b',
    ]
    
    # ── Strong negatives: clearly not composition data ──
    STRONG_NEGATIVE = [
        r'clinical\s+trial', r'randomized\s+controlled',
        r'patients?\b', r'(?:in|ex)\s+vivo',
        r'(?:food|product)\s+(?:packaging|package)',
        r'polyethylene', r'polystyrene', r'polymer\s+(?:film|coating)',
        r'rfid', r'styrene\s+(?:monomer|migration)',
        r'migration\s+(?:study|test|into|from)',
        r'gut\s+microbi(?:ota|ome)', r'intestinal\s+(?:flora|microbi)',
        r'circadian\s+rhythm',
        r'food\s+(?:allerg|intolerance)', r'allergen',
        r'drug\s+(?:delivery|interaction|resistance)',
        r'cancer\s+(?:cell|treatment|therapy)',
        r'tumor\b', r'tumour\b',
        r'disease\s+(?:risk|prevention|treatment)',
        r'(?:rat|mice|mouse)\s+(?:model|study|experiment)',
        r'animal\s+(?:model|experiment|study|feed)',
        r'cell\s+(?:line|culture|viability|proliferation)',
        r'cytotoxic', r'apoptosis',
        r'nano\s*(?:particle|material|composite|emulsion)',
        r'encapsulation',
        r'food\s+fraud', r'authentication',
        r'sensory\s+(?:evaluation|analysis|panel)',
        r'consumer\s+(?:acceptance|preference|perception)',
        r'shelf\s+life', r'food\s+(?:safety|hygiene|contamination)',
        r'(?:heavy\s+metal|pesticide|mycotoxin|aflatoxin)\s+contamination',
        r'(?:pathogen|salmonella|listeria|e\.\s*coli)', 
        r'biofilm',
        r'food\s+processing\s+(?:technology|equipment|innovation)',
        r'3d\s+print', r'extrusion\s+(?:technology|process)',
        r'life\s+cycle\s+assessment', r'sustainability\s+(?:assessment|index)',
        r'supply\s+chain', r'food\s+(?:waste|loss)',
        r'machine\s+learning', r'deep\s+learning', r'artificial\s+intelligence',
        r'(?:meta-analysis|systematic\s+review)\s+(?:of|on)',
    ]
    
    # ── Moderate negatives: somewhat off-topic indicators ──
    MODERATE_NEGATIVE = [
        r'bioactive\s+(?:compound|peptide)',
        r'anti-?(?:microbial|bacterial|fungal|inflammatory|diabetic|hypertensive)',
        r'therapeutic',
        r'(?:drying|freeze-drying|spray-drying)\s+(?:method|technique|process|optimization)',
        r'extraction\s+(?:method|technique|optimization|condition)',
        r'fermentation\s+(?:process|optimization|kinetics)',
        r'(?:emulsion|gel|foam|film)\s+(?:stability|formation|properties)',
        r'rheolog', r'texture\s+(?:analysis|profile|propert)',
        r'metabolomi', r'proteomi', r'genomic',
        r'genetic\s+(?:diversity|variation|marker)',
        r'transcriptom',
    ]
    
    def __init__(self, threshold: float = 3.0):
        self.threshold = threshold
        # Pre-compile all patterns
        self._strong_pos = [re.compile(p, re.IGNORECASE) for p in self.STRONG_POSITIVE]
        self._moderate_pos = [re.compile(p, re.IGNORECASE) for p in self.MODERATE_POSITIVE]
        self._strong_neg = [re.compile(p, re.IGNORECASE) for p in self.STRONG_NEGATIVE]
        self._moderate_neg = [re.compile(p, re.IGNORECASE) for p in self.MODERATE_NEGATIVE]
    
    def score(self, title: str, abstract: str) -> Tuple[float, List[str]]:
        """
        Score a paper's relevance based on title + abstract.
        
        Returns:
            (score, reasons): numeric score and list of matching signals
        """
        text = f"{title or ''} {abstract or ''}".strip()
        if not text:
            return (0.0, ["No title or abstract available"])
        
        total = 0.0
        reasons = []
        
        # Strong positives (+3 each)
        for pattern in self._strong_pos:
            matches = pattern.findall(text)
            if matches:
                total += 3.0
                reasons.append(f"+3 strong_pos: '{pattern.pattern}' ({len(matches)}x)")
        
        # Moderate positives (+1 each)
        for pattern in self._moderate_pos:
            matches = pattern.findall(text)
            if matches:
                total += 1.0
                reasons.append(f"+1 mod_pos: '{pattern.pattern}' ({len(matches)}x)")
        
        # Strong negatives (-5 each)
        for pattern in self._strong_neg:
            matches = pattern.findall(text)
            if matches:
                total -= 5.0
                reasons.append(f"-5 strong_neg: '{pattern.pattern}' ({len(matches)}x)")
        
        # Moderate negatives (-2 each)
        for pattern in self._moderate_neg:
            matches = pattern.findall(text)
            if matches:
                total -= 2.0
                reasons.append(f"-2 mod_neg: '{pattern.pattern}' ({len(matches)}x)")
        
        return (total, reasons)
    
    def passes(self, title: str, abstract: str) -> Tuple[bool, float, List[str]]:
        """
        Check if a paper passes the relevance filter.
        
        Returns:
            (passed, score, reasons)
        """
        score, reasons = self.score(title, abstract)
        return (score >= self.threshold, score, reasons)
    
    def filter_batch(self, papers: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter a batch of paper metadata dicts.
        Each dict should have 'title' and 'abstract' keys.
        
        Returns:
            (passed_papers, filtered_papers)
        """
        passed = []
        filtered = []
        
        for paper in papers:
            ok, score, reasons = self.passes(
                paper.get('title', ''),
                paper.get('abstract', '')
            )
            paper['relevance_score'] = score
            paper['relevance_reasons'] = reasons
            
            if ok:
                passed.append(paper)
            else:
                filtered.append(paper)
        
        return passed, filtered

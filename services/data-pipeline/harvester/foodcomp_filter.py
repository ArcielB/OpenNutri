"""
Food Composition Filter - High-precision abstract/title filter.

Goal: keep precision high (ok to miss some good papers).
"""

import re
from typing import Dict, List, Tuple


class FoodCompositionFilter:
    """
    Scores paper title + abstract for food composition relevance.

    Design:
    - HARD negatives -> immediate reject
    - MUST_HAVE patterns -> at least one required
    - POSITIVE patterns -> add score
    - SOFT negatives -> subtract score
    """

    MUST_HAVE = [
        r'proximate\s+(?:analysis|composition)',
        r'food\s+composition',
        r'nutrient\s+(?:composition|content|profile|analysis)',
        r'nutritive\s+value',
        r'chemical\s+composition',
        r'fatty\s+acid\s+(?:composition|profile|content)',
        r'amino\s+acid\s+(?:composition|profile|content)',
        r'(?:mg|g|ug|mcg)\s*/\s*100\s*g',
        r'(?:kcal|kj)\s*/\s*100',
        r'per\s+100\s*g',
    ]

    POSITIVE = [
        r'moisture', r'\bash\b', r'crude\s+(?:protein|fat|fiber|fibre)',
        r'dietary\s+fib(?:er|re)', r'total\s+(?:protein|fat|lipid|carbohydrate)',
        r'dry\s+(?:weight|matter|basis)', r'fresh\s+weight',
        r'energy\s+value', r'kcal', r'kj',
        r'table\s+[0-9]', r'supplementary\s+table',
    ]

    HARD_NEGATIVE = [
        r'\breview\b', r'overview', r'meta-?analysis', r'systematic\s+review',
        r'clinical\s+trial', r'randomi[sz]ed', r'case\s+report',
        r'food\s+frequency\s+questionnaire', r'dietary\s+intake',
        r'dietary\s+assessment', r'nutrition\s+survey',
        r'gut\s+microbi(?:ota|ome)', r'microbiome',
        r'packaging', r'migration', r'shelf\s+life', r'food\s+safety',
        r'sensory\s+(?:evaluation|analysis|panel)', r'consumer\s+(?:acceptance|preference|perception)',
        r'cell\s+(?:line|culture)', r'nanoparticle', r'encapsulation',
    ]

    SOFT_NEGATIVE = [
        r'bioactive', r'antioxidant', r'anti-?microbial', r'anti-?inflammatory',
        r'extraction\s+(?:method|technique|optimization)', r'fermentation',
        r'rheolog', r'texture\s+(?:analysis|profile|propert)',
        r'metabolomi', r'proteomi', r'genomic', r'transcriptom',
        r'machine\s+learning', r'deep\s+learning', r'artificial\s+intelligence',
        r'in\s+vitro', r'in\s+vivo',
    ]

    def __init__(self, threshold: float = 4.0, require_food_term: bool = True):
        self.threshold = threshold
        self.require_food_term = require_food_term

        self._must = [re.compile(p, re.IGNORECASE) for p in self.MUST_HAVE]
        self._pos = [re.compile(p, re.IGNORECASE) for p in self.POSITIVE]
        self._hard_neg = [re.compile(p, re.IGNORECASE) for p in self.HARD_NEGATIVE]
        self._soft_neg = [re.compile(p, re.IGNORECASE) for p in self.SOFT_NEGATIVE]

    def _food_mentioned(self, text: str, food_term: str) -> bool:
        if not food_term:
            return True
        pattern = re.compile(r'\b' + re.escape(food_term.lower()) + r'\b', re.IGNORECASE)
        return bool(pattern.search(text))

    def score(self, title: str, abstract: str, food_term: str = None) -> Tuple[float, List[str]]:
        text = f"{title or ''} {abstract or ''}".strip()
        if not text:
            return (0.0, ["No title or abstract available"])

        if self.require_food_term and food_term and not self._food_mentioned(text, food_term):
            return (-999.0, ["Food term not mentioned in title/abstract"])

        reasons: List[str] = []

        # Hard negatives
        for pattern in self._hard_neg:
            if pattern.search(text):
                reasons.append(f"HARD_NEG: '{pattern.pattern}'")
                return (-999.0, reasons)

        score = 0.0
        must_hits = 0

        for pattern in self._must:
            matches = pattern.findall(text)
            if matches:
                must_hits += 1
                score += 4.0
                reasons.append(f"+4 must_have: '{pattern.pattern}' ({len(matches)}x)")

        if must_hits == 0:
            reasons.append("No MUST_HAVE signals")
            return (-999.0, reasons)

        for pattern in self._pos:
            matches = pattern.findall(text)
            if matches:
                score += 1.0
                reasons.append(f"+1 pos: '{pattern.pattern}' ({len(matches)}x)")

        for pattern in self._soft_neg:
            matches = pattern.findall(text)
            if matches:
                score -= 2.0
                reasons.append(f"-2 soft_neg: '{pattern.pattern}' ({len(matches)}x)")

        return (score, reasons)

    def passes(self, title: str, abstract: str, food_term: str = None) -> Tuple[bool, float, List[str]]:
        score, reasons = self.score(title, abstract, food_term)
        return (score >= self.threshold, score, reasons)

    def filter_batch(self, papers: List[Dict], food_term: str = None) -> Tuple[List[Dict], List[Dict]]:
        passed: List[Dict] = []
        filtered: List[Dict] = []

        for paper in papers:
            ok, score, reasons = self.passes(
                paper.get('title', ''),
                paper.get('abstract', ''),
                food_term=food_term
            )
            paper['relevance_score'] = score
            paper['relevance_reasons'] = reasons
            if ok:
                passed.append(paper)
            else:
                filtered.append(paper)

        return passed, filtered

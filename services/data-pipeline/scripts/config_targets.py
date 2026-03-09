# scripts/config_targets.py

TARGET_CONFIG = {
    # STRATEGY: "Deep Composition"
    # 1. Look for Food Analysis/Composition terms.
    # 2. EXCLUDE clinical trials to remove "pill" studies.
    # 3. Focus on "Food Chemistry" journals.
    "query": (
        '('
        '  "Food Analysis"[MeSH] OR "Nutritive Value"[MeSH] OR '
        '  "Food Composition"[All Fields] OR "Chemical Composition"[All Fields]'
        ') '
        'AND ("Food Chemistry"[Journal] OR "Foods"[Journal] OR "Journal of Food Composition and Analysis"[Journal]) '
        'AND "open access"[filter] '
        'NOT ("Clinical Trial"[pt] OR "Randomized Controlled Trial"[pt] OR "Case Reports"[pt])'
    ),
    
    # Let's get 20 clean PDFs to start
    "max_results": 20,
    "required_types": ["Journal Article"],
    "sort_order": "relevance" 
}

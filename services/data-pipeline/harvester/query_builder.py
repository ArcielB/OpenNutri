class QueryBuilder:
    """
    Constructs PubMed search queries for different discovery strategies.
    Default filters: open access, not clinical trials.
    """
    
    BASE_FILTER = ' AND "open access"[filter] NOT ("Clinical Trial"[pt] OR "Randomized Controlled Trial"[pt] OR "Case Reports"[pt])'
    
    @staticmethod
    def build_track_a(food: str, term: str) -> str:
        """
        Track A: Specific Food + Composition Term.
        Example: "Chickpea" AND "Proximate Analysis"
        """
        return f'("{food}"[All Fields] AND "{term}"[All Fields]){QueryBuilder.BASE_FILTER}'

    @staticmethod
    def build_track_b(journal: str, term: str) -> str:
        """
        Track B: Venue + Composition Term.
        Example: "Food Chemistry"[Journal] AND "Nutritive Value"
        """
        return f'("{journal}"[Journal] AND "{term}"[All Fields]){QueryBuilder.BASE_FILTER}'
    
    @staticmethod
    def build_broad_search(term: str) -> str:
        """
        Fallback: Just the term + filters.
        """
        return f'("{term}"[All Fields]){QueryBuilder.BASE_FILTER}'

"""
Query Builder — Constructs high-precision PubMed queries for food composition papers.

Uses MeSH terms, journal filters, and explicit exclusions to maximize
the chance of finding papers with actual nutrient composition tables.
"""


class QueryBuilder:
    """
    Constructs PubMed search queries for food composition data discovery.
    
    Strategy:
      - MeSH terms for precision (Food Analysis, Nutritive Value)
      - Journal filter to target composition-focused journals
      - Exclusion of clinical trials, reviews, case reports
      - Exclusion of off-topic domains (packaging, microbiome, processing tech)
    """
    
    # Journals known for publishing food composition data
    COMPOSITION_JOURNALS = [
        "Journal of Food Composition and Analysis",
        "Food Chemistry",
        "Foods",
        "Nutrients",
        "Journal of Agricultural and Food Chemistry",
        "Journal of the Science of Food and Agriculture",
        "European Food Research and Technology",
        "International Journal of Food Sciences and Nutrition",
        "Food Research International",
        "LWT",
    ]
    
    # Publication types to exclude
    EXCLUDED_PUB_TYPES = [
        '"Clinical Trial"[pt]',
        '"Randomized Controlled Trial"[pt]',
        '"Case Reports"[pt]',
        '"Review"[pt]',
        '"Meta-Analysis"[pt]',
        '"Systematic Review"[pt]',
    ]
    
    # Topic exclusions to filter out common false positives
    EXCLUDED_TOPICS = [
        '"food packaging"[All Fields]',
        '"food safety"[All Fields]',
        '"shelf life"[All Fields]',
        '"food processing technology"[All Fields]',
        '"gut microbiota"[All Fields]',
        '"gut microbiome"[All Fields]',
        '"sensory evaluation"[All Fields]',
        '"consumer acceptance"[All Fields]',
        '"nanoparticle"[All Fields]',
        '"encapsulation"[All Fields]',
        '"cell line"[All Fields]',
        '"cell culture"[All Fields]',
        '"animal model"[All Fields]',
    ]

    # Stricter exclusions for high-precision crawling
    STRICT_EXCLUDED_PUB_TYPES = [
        '"Clinical Trial"[pt]',
        '"Randomized Controlled Trial"[pt]',
        '"Case Reports"[pt]',
        '"Review"[pt]',
        '"Meta-Analysis"[pt]',
        '"Systematic Review"[pt]',
        '"Editorial"[pt]',
        '"Comment"[pt]',
        '"Letter"[pt]',
        '"News"[pt]',
    ]

    STRICT_EXCLUDED_TOPICS = [
        '"food frequency questionnaire"[All Fields]',
        '"dietary intake"[All Fields]',
        '"dietary assessment"[All Fields]',
        '"nutrition survey"[All Fields]',
        '"consumer acceptance"[All Fields]',
        '"sensory evaluation"[All Fields]',
        '"packaging"[All Fields]',
        '"migration"[All Fields]',
        '"gut microbiota"[All Fields]',
        '"gut microbiome"[All Fields]',
        '"microbiome"[All Fields]',
        '"food safety"[All Fields]',
        '"shelf life"[All Fields]',
    ]
    
    @classmethod
    def _journal_filter(cls) -> str:
        """Build OR filter for target journals."""
        parts = [f'"{j}"[Journal]' for j in cls.COMPOSITION_JOURNALS]
        return f'({" OR ".join(parts)})'
    
    @classmethod
    def _exclusion_filter(cls) -> str:
        """Build NOT filter for excluded types and topics."""
        all_exclusions = cls.EXCLUDED_PUB_TYPES + cls.EXCLUDED_TOPICS
        return f'NOT ({" OR ".join(all_exclusions)})'
    
    @classmethod
    def _base_filter(cls) -> str:
        """Open access + exclusions."""
        return f'"open access"[filter] {cls._exclusion_filter()}'

    @classmethod
    def _strict_exclusion_filter(cls) -> str:
        """Stricter NOT filter for high-precision crawling."""
        all_exclusions = cls.STRICT_EXCLUDED_PUB_TYPES + cls.STRICT_EXCLUDED_TOPICS
        return f'NOT ({" OR ".join(all_exclusions)})'

    @classmethod
    def _strict_base_filter(cls) -> str:
        """Open access + strict exclusions."""
        return f'"open access"[filter] {cls._strict_exclusion_filter()}'
    
    @staticmethod
    def build_track_a(food: str, term: str) -> str:
        """
        Track A: Specific Food + Composition Term + Journal filter.
        Example: "Chickpea" AND "proximate analysis" in composition journals
        """
        core = f'("{food}"[All Fields] AND "{term}"[All Fields])'
        return f'{core} AND {QueryBuilder._journal_filter()} AND {QueryBuilder._base_filter()}'

    @staticmethod
    def build_track_b(journal: str, term: str) -> str:
        """
        Track B: Specific Journal + Composition Term.
        Example: "Food Chemistry"[Journal] AND "Nutritive Value"
        """
        core = f'("{journal}"[Journal] AND "{term}"[All Fields])'
        return f'{core} AND {QueryBuilder._base_filter()}'
    
    @staticmethod
    def build_composition_search(food: str) -> str:
        """
        High-precision search: Food + MeSH composition terms + journal filter.
        This is the primary search strategy for finding composition data.
        """
        mesh_terms = (
            '"Food Analysis"[MeSH] OR '
            '"Nutritive Value"[MeSH] OR '
            '"food composition"[All Fields] OR '
            '"nutrient content"[All Fields] OR '
            '"proximate analysis"[All Fields] OR '
            '"nutritional characterization"[All Fields] OR '
            '"chemical composition"[All Fields]'
        )
        core = f'("{food}"[All Fields]) AND ({mesh_terms})'
        return f'{core} AND {QueryBuilder._journal_filter()} AND {QueryBuilder._base_filter()}'

    @staticmethod
    def build_strict_food_query(food: str) -> str:
        """
        High-precision search for food composition papers.
        Uses Title/Abstract for food term and strict exclusions.
        """
        strict_terms = (
            '"food composition"[Title/Abstract] OR '
            '"nutrient composition"[Title/Abstract] OR '
            '"nutrient content"[Title/Abstract] OR '
            '"proximate analysis"[Title/Abstract] OR '
            '"chemical composition"[Title/Abstract] OR '
            '"fatty acid composition"[Title/Abstract] OR '
            '"amino acid composition"[Title/Abstract]'
        )
        core = f'("{food}"[Title/Abstract]) AND ({strict_terms})'
        return f'{core} AND {QueryBuilder._journal_filter()} AND {QueryBuilder._strict_base_filter()}'

    @staticmethod
    def build_strict_food_term(food: str, term: str) -> str:
        """
        High-precision search: Food + specific term (Title/Abstract).
        """
        core = f'("{food}"[Title/Abstract] AND "{term}"[Title/Abstract])'
        return f'{core} AND {QueryBuilder._journal_filter()} AND {QueryBuilder._strict_base_filter()}'
    
    @staticmethod
    def build_nutrient_search(nutrient: str) -> str:
        """
        Nutrient-focused search: Specific nutrient + composition context + journal filter.
        Example: Find papers reporting Vitamin C content in foods.
        """
        composition_context = (
            '"food composition"[All Fields] OR '
            '"nutrient content"[All Fields] OR '
            '"nutritive value"[All Fields] OR '
            '"mg/100g"[All Fields] OR '
            '"g/100g"[All Fields]'
        )
        core = f'("{nutrient}"[All Fields]) AND ({composition_context})'
        return f'{core} AND {QueryBuilder._journal_filter()} AND {QueryBuilder._base_filter()}'
    
    @staticmethod
    def build_broad_search(term: str) -> str:
        """
        Fallback: Just the term + journal filter + exclusions.
        """
        return f'("{term}"[All Fields]) AND {QueryBuilder._journal_filter()} AND {QueryBuilder._base_filter()}'

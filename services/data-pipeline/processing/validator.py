import re
import xmltodict
from typing import List, Dict, Any, Tuple

class TableValidator:
    """
    Decides if a paper is 'Good' (contains food composition data) or 'Bad'.
    """
    
    # Keywords that suggest a column describes nutrients/composition
    COMPOSITION_KEYWORDS = {
        'protein', 'fat', 'lipid', 'carbohydrate', 'moisture', 'ash',
        'fiber', 'fibre', 'vitamin', 'mineral', 'amino acid', 'fatty acid',
        'kcal', 'energy', 'proximate', 'nutrient', 'composition'
    }
    
    # Keywords that suggest a column describes the food item
    FOOD_KEYWORDS = {
        'food', 'sample', 'item', 'product', 'cultivar', 'species', 'plant',
        'mushroom', 'fruit', 'vegetable', 'meat', 'fish', 'grain', 'legume'
    }

    # Units commonly seen in composition tables
    UNIT_PATTERNS = [
        r'\b\d+(?:\.\d+)?\s*(?:mg|g|ug|mcg)\s*/\s*100\s*g\b',
        r'\b\d+(?:\.\d+)?\s*(?:mg|g|ug|mcg)\s*/\s*100\s*ml\b',
        r'\b\d+(?:\.\d+)?\s*(?:mg|g|ug|mcg)\b',
        r'\b\d+(?:\.\d+)?\s*(?:kcal|kj)\b',
        r'\b\d+(?:\.\d+)?\s*%\s*(?:w/w|dw|fw)?\b',
    ]

    @staticmethod
    def validate_paper(xml_content: str) -> Tuple[bool, List[Dict]]:
        """
        Check if paper has at least one valid composition table.
        Returns: (is_valid, list_of_valid_tables)
        """
        try:
            data = xmltodict.parse(xml_content)
            body = data.get('pmc-articleset', {}).get('article', {}).get('body', {})
            
            # Find all table-wraps (could be nested in sections)
            tables = TableValidator._find_tables_recursive(body)
            
            valid_tables = []
            for table in tables:
                if TableValidator._is_composition_table(table):
                    valid_tables.append(table)
                    
            return len(valid_tables) > 0, valid_tables
            
        except Exception as e:
            # print(f"Validation error: {e}")
            return False, []

    @staticmethod
    def _find_tables_recursive(element: Any) -> List[Dict]:
        """Deep search for table-wrap elements."""
        found = []
        
        if isinstance(element, dict):
            for k, v in element.items():
                if k == 'table-wrap':
                    if isinstance(v, list):
                        found.extend(v)
                    else:
                        found.append(v)
                else:
                    found.extend(TableValidator._find_tables_recursive(v))
        elif isinstance(element, list):
            for item in element:
                found.extend(TableValidator._find_tables_recursive(item))
                
        return found

    @staticmethod
    def _is_composition_table(table_wrap: Dict) -> bool:
        """
        Heuristic: A composition table must have:
        1. A header row with Nutrient-like terms.
        2. A header or first column with Food-like terms.
        """
        try:
            # parsing logic is tricky with xmltodict structure variation
            # Simplified check: Convert whole table-wrap to string and search keywords
            # This is a robust simplification because strict structure parsing fails often on PMC XMLs
            
            # Get table content as string (headers, caption, etc)
            table_str = str(table_wrap).lower()
            
            has_nutrient = any(k in table_str for k in TableValidator.COMPOSITION_KEYWORDS)
            has_food_marker = any(k in table_str for k in TableValidator.FOOD_KEYWORDS)
            has_units = any(re.search(p, table_str) for p in TableValidator.UNIT_PATTERNS)

            # Require nutrient context plus either food marker or units for precision
            return has_nutrient and (has_food_marker or has_units)
            
        except Exception:
            return False

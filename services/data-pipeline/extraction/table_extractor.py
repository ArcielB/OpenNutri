"""
Table Extractor

Parses PMC XML to extract composition tables and prepare them for LLM processing.
"""

import re
import json
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ExtractedTable:
    """A table extracted from a paper."""
    paper_id: str
    table_id: str
    caption: str
    headers: List[str]
    rows: List[List[str]]
    raw_xml: str
    
    def to_prompt_text(self) -> str:
        """Convert to clean text for LLM prompt."""
        lines = []
        lines.append(f"Table: {self.caption}")
        lines.append("")
        lines.append(" | ".join(self.headers))
        lines.append("-" * 50)
        for row in self.rows[:50]:  # Limit rows for token efficiency
            lines.append(" | ".join(row))
        return "\n".join(lines)


class TableExtractor:
    """Extracts and parses tables from PMC XML."""
    
    # Keywords indicating a composition table
    COMPOSITION_KEYWORDS = [
        'nutrient', 'nutritional', 'composition', 'proximate',
        'protein', 'fat', 'carbohydrate', 'mineral', 'vitamin',
        'mg/100', 'g/100', 'per 100', 'kcal', 'energy'
    ]
    
    @staticmethod
    def extract_tables(paper_id: str, xml_content: str) -> List[ExtractedTable]:
        """Extract all table-wrap elements from XML."""
        tables = []
        
        # Find all table-wrap elements
        table_wraps = re.findall(
            r'<table-wrap[^>]*id="([^"]*)"[^>]*>(.*?)</table-wrap>',
            xml_content, 
            re.DOTALL
        )
        
        # Also try without id attribute
        if not table_wraps:
            table_wraps_no_id = re.findall(
                r'<table-wrap[^>]*>(.*?)</table-wrap>',
                xml_content,
                re.DOTALL
            )
            table_wraps = [(f"table_{i}", tw) for i, tw in enumerate(table_wraps_no_id)]
        
        for table_id, table_xml in table_wraps:
            extracted = TableExtractor._parse_table(paper_id, table_id, table_xml)
            if extracted:
                tables.append(extracted)
        
        return tables
    
    @staticmethod
    def _parse_table(paper_id: str, table_id: str, table_xml: str) -> Optional[ExtractedTable]:
        """Parse a single table-wrap element."""
        # Extract caption
        caption_match = re.search(r'<caption>(.*?)</caption>', table_xml, re.DOTALL)
        caption = ""
        if caption_match:
            caption = re.sub(r'<[^>]+>', ' ', caption_match.group(1))
            caption = ' '.join(caption.split())[:500]
        
        # Extract headers from <th> elements
        headers = []
        header_matches = re.findall(r'<th[^>]*>(.*?)</th>', table_xml, re.DOTALL)
        for h in header_matches:
            h_clean = re.sub(r'<[^>]+>', ' ', h)
            h_clean = ' '.join(h_clean.split())
            if h_clean:
                headers.append(h_clean)
        
        # Extract rows from <tr> elements
        rows = []
        tr_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', table_xml, re.DOTALL)
        
        for tr in tr_matches:
            # Get all cells (td)
            cells = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
            if cells:
                row = []
                for cell in cells:
                    cell_clean = re.sub(r'<[^>]+>', ' ', cell)
                    cell_clean = ' '.join(cell_clean.split())
                    row.append(cell_clean)
                if row:
                    rows.append(row)
        
        if not rows:
            return None
        
        return ExtractedTable(
            paper_id=paper_id,
            table_id=table_id,
            caption=caption,
            headers=headers[:20],  # Limit headers
            rows=rows,
            raw_xml=table_xml[:10000]  # Keep raw for debugging
        )
    
    @staticmethod
    def is_composition_table(table: ExtractedTable) -> bool:
        """Check if table likely contains composition data."""
        # Check caption
        caption_lower = table.caption.lower()
        if any(kw in caption_lower for kw in TableExtractor.COMPOSITION_KEYWORDS):
            return True
        
        # Check headers
        headers_text = ' '.join(table.headers).lower()
        if any(kw in headers_text for kw in TableExtractor.COMPOSITION_KEYWORDS):
            return True
        
        return False
    
    @staticmethod
    def filter_composition_tables(tables: List[ExtractedTable]) -> List[ExtractedTable]:
        """Filter to only likely composition tables."""
        return [t for t in tables if TableExtractor.is_composition_table(t)]


def extract_tables_from_paper(paper_path: str) -> List[ExtractedTable]:
    """Convenience function to extract tables from a saved paper JSON."""
    with open(paper_path, 'r') as f:
        doc = json.load(f)
    
    paper_id = doc.get('pmc_id', 'unknown')
    xml_content = doc.get('raw_xml', '')
    
    return TableExtractor.extract_tables(paper_id, xml_content)

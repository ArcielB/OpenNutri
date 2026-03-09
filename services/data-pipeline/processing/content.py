import xmltodict
from typing import Dict, Any, Optional

def extract_metadata(xml_content: str) -> Dict[str, Any]:
    """
    Parse XML and extract key metadata (title, abstract, journal, etc.).
    Wraps the logic previously in ingestor.py.
    """
    metadata = {
        "title": None,
        "authors": [],
        "journal": None,
        "publication_date": None,
        "doi": None,
        "abstract": None,
        "has_full_text": False
    }
    
    try:
        data_dict = xmltodict.parse(xml_content)
        
        # Navigate to article metadata
        article = data_dict.get('pmc-articleset', {}).get('article', {})
        front = article.get('front', {})
        article_meta = front.get('article-meta', {})
        journal_meta = front.get('journal-meta', {})
        
        # Title
        title_group = article_meta.get('title-group', {})
        title = title_group.get('article-title', '')
        if isinstance(title, dict):
            title = title.get('#text', str(title))
        elif isinstance(title, list):
            title = title[0] if title else ''
        metadata['title'] = str(title)[:500] if title else None
        
        # Authors
        contrib_group = article_meta.get('contrib-group', {})
        contribs = contrib_group.get('contrib', [])
        if isinstance(contribs, dict):
            contribs = [contribs]
        for contrib in contribs:
            if isinstance(contrib, dict) and contrib.get('@contrib-type') == 'author':
                name = contrib.get('name', {})
                surname = name.get('surname', '')
                given = name.get('given-names', '')
                if surname:
                    metadata['authors'].append(f"{given} {surname}".strip())
        
        # Journal
        journal_title = journal_meta.get('journal-title-group', {}).get('journal-title', '')
        if not journal_title:
            journal_title = journal_meta.get('journal-title', '')
        if isinstance(journal_title, dict):
            journal_title = journal_title.get('#text', '')
        metadata['journal'] = str(journal_title) if journal_title else None
        
        # Abstract
        abstract = article_meta.get('abstract', {})
        if isinstance(abstract, dict):
            abstract_text = abstract.get('p', abstract.get('#text', ''))
            if isinstance(abstract_text, list):
                # Join paragraphs
                text_parts = []
                for p in abstract_text:
                    if isinstance(p, dict):
                        text_parts.append(p.get('#text', ''))
                    else:
                        text_parts.append(str(p))
                abstract_text = ' '.join(text_parts)
            elif isinstance(abstract_text, dict):
                abstract_text = abstract_text.get('#text', str(abstract_text))
            metadata['abstract'] = str(abstract_text)[:2000] if abstract_text else None
            
        # Full Text Check
        body = article.get('body')
        metadata['has_full_text'] = body is not None
        
        return metadata 

    except Exception as e:
        # print(f"Metadata extraction error: {e}")
        return metadata


def extract_full_text(xml_content: str) -> str:
    """
    Extract full text content from PMC XML for LLM processing.
    Includes title, abstract, and body text with basic cleaning.
    """
    try:
        data_dict = xmltodict.parse(xml_content)
        article = data_dict.get('pmc-articleset', {}).get('article', {})
        front = article.get('front', {})
        article_meta = front.get('article-meta', {})
        
        parts = []
        
        # Title
        title_group = article_meta.get('title-group', {})
        title = title_group.get('article-title', '')
        if isinstance(title, dict):
            title = title.get('#text', str(title))
        if title:
            parts.append(f"TITLE: {title}")
        
        # Abstract
        abstract = article_meta.get('abstract', {})
        if isinstance(abstract, dict):
            abstract_text = _extract_text_recursive(abstract)
            if abstract_text:
                parts.append(f"\nABSTRACT:\n{abstract_text}")
        
        # Body (full text)
        body = article.get('body', {})
        if body:
            body_text = _extract_text_recursive(body)
            if body_text:
                parts.append(f"\nFULL TEXT:\n{body_text}")
        
        return '\n\n'.join(parts)
        
    except Exception as e:
        return f"Error extracting full text: {str(e)}"


def _extract_text_recursive(node) -> str:
    """
    Recursively extract text from nested XML structure.
    Handles tables, paragraphs, sections, etc.
    """
    if isinstance(node, str):
        return node
    
    if isinstance(node, dict):
        # If it has #text, use that
        if '#text' in node:
            return str(node['#text'])
        
        # Otherwise concatenate all text from children
        text_parts = []
        for key, value in node.items():
            if key.startswith('@'):  # Skip attributes
                continue
            child_text = _extract_text_recursive(value)
            if child_text:
                text_parts.append(child_text)
        return ' '.join(text_parts)
    
    if isinstance(node, list):
        return ' '.join(_extract_text_recursive(item) for item in node)
    
    return str(node)

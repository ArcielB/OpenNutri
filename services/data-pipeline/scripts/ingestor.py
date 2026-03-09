"""
Scientific Harvester - PubMed Central Dietary Supplements Crawler
Downloads full-text open access research papers and saves them as JSON.

Author: OpenNutri Project
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

import xmltodict
from Bio import Entrez


# =============================================================================
# ⚠️  CONFIGURATION - YOU MUST UPDATE THIS!
# =============================================================================
# NCBI requires a valid email. They will block requests without one.
# Replace this with your actual email address before running.
Entrez.email = "f221229078@ktun.edu.tr"
Entrez.tool = "OpenNutri_ScientificHarvester"

# Search Configuration
SEARCH_TERM = '("Dietary Supplements"[MeSH] OR "Vitamins"[MeSH]) AND "open access"[filter]'
MAX_RESULTS = 50

# Output Configuration
if not os.path.exists("data"):
    os.makedirs("data")
SAVE_DIR = Path("data/raw_lake")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# API Politeness
REQUEST_DELAY_SECONDS = 0.5  # Delay between API requests to be respectful


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def print_banner():
    """Display startup banner with configuration info."""
    print("=" * 70)
    print("🔬 OpenNutri Scientific Harvester - PubMed Central")
    print("=" * 70)
    print(f"📧 Email: {Entrez.email}")
    print(f"🔍 Search: {SEARCH_TERM[:60]}...")
    print(f"📊 Max Results: {MAX_RESULTS}")
    print(f"📁 Output: {SAVE_DIR.absolute()}")
    print("=" * 70)
    
    # Warn if email is not configured
    if "YOUR_EMAIL" in Entrez.email or "example.com" in Entrez.email:
        print("\n⚠️  WARNING: You must set a valid email in Entrez.email!")
        print("   NCBI requires this to contact you if there are issues.")
        print("   Update line 24 of this file before running.\n")
        return False
    return True


def get_existing_ids() -> set:
    """
    Scan the data lake for existing PMC IDs to avoid re-downloading.
    
    Returns:
        Set of existing PMC IDs (e.g., {'12345', '67890'})
    """
    existing = set()
    try:
        if SAVE_DIR.exists():
            for file_path in SAVE_DIR.glob("PMC*.json"):
                # Extract ID from filename "PMC12345.json" -> "12345"
                pmc_id = file_path.stem.replace("PMC", "")
                existing.add(pmc_id)
    except Exception:
        pass
    return existing


def search_pmc(term: str, max_results: int = 50) -> list:
    """
    Search PubMed Central for articles matching the given term.
    Now implements SMART DEDUPLICATION:
    1. Fetches 5x more IDs than requested (to account for potential duplicates).
    2. Filters out IDs that already exist locally.
    3. Returns exactly 'max_results' of NEW papers.
    
    Args:
        term: Search query using PubMed search syntax
        max_results: Target number of NEW papers to return
        
    Returns:
        List of PMC IDs (strings)
    """
    print(f"\n🔎 Searching PMC for: {term[:50]}...")
    
    # Smart Deduplication Strategy
    # Fetch more results than needed to ensure we have enough after filtering
    fetch_buffer = max_results * 10
    fetch_max = min(fetch_buffer, 1000) # Cap at 1000 to be safe
    
    try:
        search_handle = Entrez.esearch(
            db="pmc",
            term=term,
            retmax=fetch_max,
            sort="relevance" # Get most relevant first
        )
        search_results = Entrez.read(search_handle)
        search_handle.close()
        
        all_ids = search_results.get("IdList", [])
        total_available = search_results.get("Count", "Unknown")
        
        # Filter existing
        existing_ids = get_existing_ids()
        new_ids = [pid for pid in all_ids if pid not in existing_ids]
        
        # Trim to requested amount
        final_ids = new_ids[:max_results]
        
        print(f"✅ Found {len(all_ids)} matches (Total available: {total_available})")
        print(f"   Smart Filter: {len(all_ids)} raw -> {len(new_ids)} new papers (skipped {len(all_ids) - len(new_ids)} existing)")
        
        return final_ids
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return []


def fetch_full_text_xml(pmc_id: str) -> str | None:
    """
    Fetch the full-text XML for a given PMC article.
    
    Args:
        pmc_id: PubMed Central ID
        
    Returns:
        Raw XML string or None if fetch failed
    """
    try:
        fetch_handle = Entrez.efetch(
            db="pmc",
            id=pmc_id,
            retmode="xml"
        )
        xml_data = fetch_handle.read()
        fetch_handle.close()
        
        # Handle bytes vs string
        if isinstance(xml_data, bytes):
            xml_data = xml_data.decode("utf-8")
            
        return xml_data
        
    except Exception as e:
        print(f"   ❌ Fetch failed for PMC{pmc_id}: {e}")
        return None


def extract_metadata(data_dict: dict) -> dict:
    """
    Extract key metadata from the parsed XML dictionary.
    
    Args:
        data_dict: Parsed XML as dictionary
        
    Returns:
        Dictionary with extracted metadata fields
    """
    metadata = {
        "title": None,
        "authors": [],
        "journal": None,
        "publication_date": None,
        "doi": None,
        "abstract": None
    }
    
    try:
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
        
        # DOI
        article_ids = article_meta.get('article-id', [])
        if isinstance(article_ids, dict):
            article_ids = [article_ids]
        for aid in article_ids:
            if isinstance(aid, dict) and aid.get('@pub-id-type') == 'doi':
                metadata['doi'] = aid.get('#text', '')
                break
        
        # Abstract
        abstract = article_meta.get('abstract', {})
        if isinstance(abstract, dict):
            abstract_text = abstract.get('p', abstract.get('#text', ''))
            if isinstance(abstract_text, list):
                abstract_text = ' '.join([str(p.get('#text', p) if isinstance(p, dict) else p) for p in abstract_text])
            elif isinstance(abstract_text, dict):
                abstract_text = abstract_text.get('#text', str(abstract_text))
            metadata['abstract'] = str(abstract_text)[:2000] if abstract_text else None
            
        # Full Text Check
        # PMC full text usually lives in the <body> tag
        body = article.get('body')
        metadata['has_full_text'] = body is not None
            
    except Exception as e:
        # Metadata extraction is best-effort; don't fail the whole process
        pass
    
    return metadata


def fetch_and_save(pmc_id: str) -> dict:
    """
    Download a paper from PubMed Central and save it as JSON.
    
    Args:
        pmc_id: The PubMed Central ID of the paper
        
    Returns:
        Dictionary with status information
    """
    file_path = SAVE_DIR / f"PMC{pmc_id}.json"
    
    # --- DEDUPLICATION: Check if already downloaded ---
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            return {
                "status": "skipped",
                "pmc_id": pmc_id,
                "reason": "already_exists",
                "title": existing.get("metadata", {}).get("title", "Existing File")[:80]
            }
        except Exception:
            pass  # If we can't read it, re-download
    
    # --- FETCH: Download full-text XML ---
    xml_data = fetch_full_text_xml(pmc_id)
    if xml_data is None:
        return {
            "status": "failed",
            "pmc_id": pmc_id,
            "error": "Failed to fetch XML"
        }
    
    # --- PARSE: Convert XML to dictionary ---
    try:
        data_dict = xmltodict.parse(xml_data)
    except Exception as e:
        return {
            "status": "failed",
            "pmc_id": pmc_id,
            "error": f"XML parse error: {e}"
        }
    
    # --- EXTRACT: Get metadata from parsed content ---
    metadata = extract_metadata(data_dict)
    
    # --- CONSTRUCT: Build the output document ---
    document = {
        "pmc_id": f"PMC{pmc_id}",
        "source": "PubMed Central",
        "harvested_at": datetime.utcnow().isoformat() + "Z",
        "metadata": metadata,
        "raw_xml": xml_data,
        "parsed_content": data_dict
    }
    
    # --- SAVE: Write to disk ---
    try:
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(document, f, indent=2, ensure_ascii=False)
        
        return {
            "status": "success",
            "pmc_id": pmc_id,
            "file": str(file_path),
            "title": metadata.get("title", "Unknown")[:80] if metadata.get("title") else "No Title"
        }
    except Exception as e:
        return {
            "status": "failed",
            "pmc_id": pmc_id,
            "error": f"Save error: {e}"
        }


def run_harvester():
    """
    Main harvester workflow.
    Searches PMC, downloads papers, and saves them locally.
    """
    # Print configuration
    if not print_banner():
        print("Please configure your email and run again.")
        sys.exit(1)
    
    # Step 1: Search
    pmc_ids = search_pmc(SEARCH_TERM, MAX_RESULTS)
    
    if not pmc_ids:
        print("\n⚠️  No results found. Check your search term or try again later.")
        return
    
    # Step 2: Fetch and Save each paper
    print(f"\n📥 Downloading {len(pmc_ids)} papers...\n")
    
    stats = {"success": 0, "skipped": 0, "failed": 0}
    
    for i, pmc_id in enumerate(pmc_ids, 1):
        print(f"[{i:3}/{len(pmc_ids)}] PMC{pmc_id}...", end=" ")
        
        result = fetch_and_save(pmc_id)
        status = result["status"]
        stats[status] += 1
        
        # Print result
        if status == "success":
            print(f"✅ {result.get('title', 'Downloaded')}")
        elif status == "skipped":
            print(f"⏭️  Skipped (already exists)")
        else:
            print(f"❌ {result.get('error', 'Unknown error')}")
        
        # Be polite to the API - sleep between requests
        if i < len(pmc_ids):
            time.sleep(REQUEST_DELAY_SECONDS)
    
    # Step 3: Summary
    print("\n" + "=" * 70)
    print("📊 HARVEST COMPLETE")
    print("=" * 70)
    print(f"   ✅ Success:  {stats['success']}")
    print(f"   ⏭️  Skipped:  {stats['skipped']}")
    print(f"   ❌ Failed:   {stats['failed']}")
    print(f"   📁 Output:   {SAVE_DIR.absolute()}")
    print("=" * 70)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_harvester()

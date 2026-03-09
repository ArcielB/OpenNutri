"""
Scientific Harvester - PDF Downloader for Food Composition Papers
Downloads full-text PDFs from PubMed Central Open Access for Vision AI processing.

Author: OpenNutri Project
Strategy: "Deep Composition" - Focus on Food Chemistry papers with table data.
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from pathlib import Path

from Bio import Entrez

# Import the target configuration
try:
    from scripts.config_targets import TARGET_CONFIG
except ImportError:
    from config_targets import TARGET_CONFIG


# =============================================================================
# ⚠️  CONFIGURATION - YOU MUST UPDATE THIS!
# =============================================================================
# NCBI requires a valid email. They will block requests without one.
Entrez.email = "f221229078@ktun.edu.tr"
Entrez.tool = "OpenNutri_PDFHarvester"

# Output Configuration
SAVE_DIR = Path("data/raw_pdfs")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# Metadata tracking
METADATA_FILE = SAVE_DIR / "_harvest_metadata.json"

# API Politeness
REQUEST_DELAY_SECONDS = 1.0  # Be extra polite when downloading PDFs

# PMC Open Access FTP base URL (for PDF downloads)
PMC_OA_API = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def print_banner():
    """Display startup banner with configuration info."""
    print("=" * 70)
    print("📄 OpenNutri PDF Harvester - Food Composition Papers")
    print("=" * 70)
    print(f"📧 Email: {Entrez.email}")
    print(f"🔍 Strategy: Deep Composition (Food Chemistry Journals)")
    print(f"📊 Max Results: {TARGET_CONFIG['max_results']}")
    print(f"📁 Output: {SAVE_DIR.absolute()}")
    print("=" * 70)
    
    # Show excluded content types
    print("🚫 Excluding: Clinical Trials, RCTs, Case Reports")
    print("=" * 70)
    
    if "YOUR_EMAIL" in Entrez.email or "example.com" in Entrez.email:
        print("\n⚠️  WARNING: You must set a valid email in Entrez.email!")
        return False
    return True


FOOD_TERMS = [
    "food composition",
    "nutrient composition",
    "proximate analysis",
    "fatty acid profile",
    "amino acid composition",
    "chemical composition",
    "nutritional value",
    "antioxidant activity"
]

def is_food_composition(text: str) -> bool:
    """NLP Filter: Checks if abstract contains food composition target phrases."""
    if not text:
        return False
    text = text.lower()
    matches = sum(1 for t in FOOD_TERMS if t in text)
    return matches >= 1  # Require at least 1 strong term match

def get_existing_ids() -> set:
    """
    Scan the PDF directory for existing PMC IDs to avoid re-downloading.
    
    Returns:
        Set of existing PMC IDs
    """
    existing = set()
    try:
        if SAVE_DIR.exists():
            for file_path in SAVE_DIR.glob("PMC*.pdf"):
                pmc_id = file_path.stem.replace("PMC", "")
                existing.add(pmc_id)
    except Exception:
        pass
    return existing


def search_pmc() -> list:
    """
    Search PubMed Central using the TARGET_CONFIG query.
    Implements smart deduplication to skip already-downloaded papers.
    
    Returns:
        List of dictionaries with PMC ID and basic metadata
    """
    query = TARGET_CONFIG["query"]
    max_results = TARGET_CONFIG["max_results"]
    sort_order = TARGET_CONFIG.get("sort_order", "relevance")
    
    print(f"\n🔎 Searching PMC with Deep Composition filter...")
    print(f"   Query preview: {query[:80]}...")
    
    # Fetch more than needed to account for duplicates
    fetch_buffer = max_results * 5
    
    try:
        search_handle = Entrez.esearch(
            db="pmc",
            term=query,
            retmax=fetch_buffer,
            sort=sort_order
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
        
        print(f"✅ Found {total_available} total matches")
        print(f"   Filtered: {len(all_ids)} fetched → {len(new_ids)} new → {len(final_ids)} to download")
        
        if len(existing_ids) > 0:
            print(f"   ⏭️  Skipping {len(existing_ids)} already downloaded")
        
        return final_ids
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return []


def get_pdf_url(pmc_id: str) -> tuple[str | None, str]:
    """
    Get the PDF download URL for a PMC article using multiple strategies.
    
    Strategies (in order):
    1. Europe PMC API - Most reliable for open access
    2. NCBI OA API - Official but sometimes returns HTML
    3. Direct PMC URL construction - Last resort
    
    Args:
        pmc_id: The PMC ID (without 'PMC' prefix)
        
    Returns:
        Tuple of (PDF URL or None, strategy used)
    """
    import re
    
    # Strategy 1: Europe PMC API (most reliable for OA PDFs)
    try:
        epmc_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/PMC{pmc_id}/fullTextXML"
        response = requests.get(epmc_url, timeout=30)
        if response.status_code == 200:
            # Europe PMC provides XML, but we can construct PDF URL from it
            # The PDF is typically at this pattern for OA articles
            pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{pmc_id}&blobtype=pdf"
            return pdf_url, "europepmc"
    except Exception:
        pass
    
    # Strategy 2: NCBI OA API
    try:
        response = requests.get(
            PMC_OA_API,
            params={"id": f"PMC{pmc_id}"},
            timeout=30
        )
        
        if response.status_code == 200:
            content = response.text
            
            # Check if it's in the OA subset
            if "idIsNotOpenAccess" not in content and "error" not in content.lower():
                # Look for FTP links (they're more reliable)
                ftp_pattern = r'href="(ftp://[^"]+\.pdf)"'
                ftp_matches = re.findall(ftp_pattern, content)
                
                if ftp_matches:
                    # Convert FTP to HTTPS (ftp.ncbi.nlm.nih.gov -> ncbi.nlm.nih.gov)
                    ftp_url = ftp_matches[0]
                    https_url = ftp_url.replace("ftp://ftp.ncbi.nlm.nih.gov", "https://ftp.ncbi.nlm.nih.gov")
                    return https_url, "ncbi_oa_ftp"
                
                # Look for direct HTTPS PDF links
                https_pattern = r'href="(https://[^"]+\.pdf[^"]*)"'
                https_matches = re.findall(https_pattern, content)
                if https_matches:
                    return https_matches[0], "ncbi_oa_https"
    except Exception:
        pass
    
    # Strategy 3: Direct PMC URL (often returns HTML, but worth trying)
    direct_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
    return direct_url, "direct_fallback"


def get_article_metadata(pmc_id: str) -> dict:
    """
    Fetch basic metadata for an article using efetch.
    
    Returns:
        Dictionary with title, authors, journal, etc.
    """
    metadata = {
        "pmc_id": f"PMC{pmc_id}",
        "title": None,
        "journal": None,
        "abstract": None,
        "doi": None
    }
    
    try:
        handle = Entrez.efetch(
            db="pmc",
            id=pmc_id,
            rettype="xml",
            retmode="xml"
        )
        
        # Just get a small portion to extract metadata
        xml_snippet = handle.read(50000)  # First 50KB should have metadata
        handle.close()
        
        if isinstance(xml_snippet, bytes):
            xml_snippet = xml_snippet.decode("utf-8", errors="ignore")
        
        # Quick regex extraction for title
        import re
        title_match = re.search(r'<article-title[^>]*>([^<]+)</article-title>', xml_snippet)
        if title_match:
            metadata["title"] = title_match.group(1)[:200]
        
        journal_match = re.search(r'<journal-title[^>]*>([^<]+)</journal-title>', xml_snippet)
        if journal_match:
            metadata["journal"] = journal_match.group(1)
            
        abstract_match = re.search(r'<abstract[^>]*>(.*?)</abstract>', xml_snippet, re.DOTALL)
        if abstract_match:
            clean_abstract = re.sub(r'<[^>]+>', ' ', abstract_match.group(1)).strip()
            metadata["abstract"] = clean_abstract
            
    except Exception:
        pass
    
    return metadata


def download_pdf(pmc_id: str) -> dict:
    """
    Download PDF for a given PMC article.
    
    Uses multiple strategies via get_pdf_url():
    1. Europe PMC API - Most reliable for open access
    2. NCBI OA API with FTP links
    3. Direct PMC URL construction
    
    Returns:
        Dictionary with download result
    """
    file_path = SAVE_DIR / f"PMC{pmc_id}.pdf"
    
    # Skip if already exists
    if file_path.exists():
        return {
            "status": "skipped",
            "pmc_id": pmc_id,
            "reason": "already_exists"
        }
    
    # Get metadata first
    metadata = get_article_metadata(pmc_id)
    
    # NLP Content Filter
    abstract = metadata.get("abstract", "")
    if abstract and not is_food_composition(abstract):
        return {
            "status": "skipped",
            "pmc_id": pmc_id,
            "reason": "Failed NLP filter (no target food terms in abstract)"
        }
    
    # Get PDF URL using multi-strategy approach
    pdf_url, strategy = get_pdf_url(pmc_id)
    
    if not pdf_url:
        return {
            "status": "failed",
            "pmc_id": pmc_id,
            "error": "No PDF URL found"
        }
    
    try:
        # Download with streaming
        response = requests.get(
            pdf_url,
            timeout=60,
            stream=True,
            headers={
                "User-Agent": "OpenNutri_PDFHarvester/1.0 (Research Project; Contact: " + Entrez.email + ")"
            },
            allow_redirects=True  # Follow redirects for Europe PMC
        )
        
        # Check if we got a PDF
        content_type = response.headers.get("Content-Type", "")
        
        # Read first few bytes to check for PDF magic number
        first_bytes = response.content[:10] if len(response.content) > 10 else response.content
        is_pdf = b'%PDF' in first_bytes or "pdf" in content_type.lower()
        
        if response.status_code == 200 and is_pdf:
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            return {
                "status": "success",
                "pmc_id": pmc_id,
                "file": str(file_path),
                "title": metadata.get("title", "Unknown"),
                "journal": metadata.get("journal"),
                "size_kb": file_path.stat().st_size // 1024,
                "strategy": strategy
            }
        else:
            return {
                "status": "failed",
                "pmc_id": pmc_id,
                "error": f"Not a PDF (Status: {response.status_code}, Type: {content_type[:30]})"
            }
            
    except Exception as e:
        return {
            "status": "failed",
            "pmc_id": pmc_id,
            "error": str(e)
        }


def save_harvest_metadata(results: list):
    """Save metadata about harvested PDFs for tracking."""
    metadata = {
        "harvested_at": datetime.utcnow().isoformat() + "Z",
        "query_config": TARGET_CONFIG,
        "results": results
    }
    
    try:
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except Exception:
        pass


def run_pdf_harvester():
    """
    Main harvester workflow for PDFs.
    """
    if not print_banner():
        print("Please configure your email and run again.")
        sys.exit(1)
    
    # Step 1: Search
    pmc_ids = search_pmc()
    
    if not pmc_ids:
        print("\n⚠️  No new papers found. The filter might be too strict,")
        print("   or all matching papers have already been downloaded.")
        return
    
    # Step 2: Download each PDF
    print(f"\n📥 Downloading {len(pmc_ids)} PDFs...\n")
    
    stats = {"success": 0, "skipped": 0, "failed": 0}
    results = []
    
    for i, pmc_id in enumerate(pmc_ids, 1):
        print(f"[{i:3}/{len(pmc_ids)}] PMC{pmc_id}...", end=" ")
        
        result = download_pdf(pmc_id)
        status = result["status"]
        stats[status] += 1
        results.append(result)
        
        if status == "success":
            title = result.get('title', 'Downloaded')
            if title and len(title) > 50:
                title = title[:50] + "..."
            print(f"✅ {title} ({result.get('size_kb', '?')} KB)")
        elif status == "skipped":
            print(f"⏭️  Already exists")
        else:
            print(f"❌ {result.get('error', 'Unknown error')}")
        
        # Be polite - wait between requests
        if i < len(pmc_ids):
            time.sleep(REQUEST_DELAY_SECONDS)
    
    # Save metadata
    save_harvest_metadata(results)
    
    # Step 3: Summary
    print("\n" + "=" * 70)
    print("📊 PDF HARVEST COMPLETE")
    print("=" * 70)
    print(f"   ✅ Downloaded:  {stats['success']} PDFs")
    print(f"   ⏭️  Skipped:     {stats['skipped']}")
    print(f"   ❌ Failed:      {stats['failed']}")
    print(f"   📁 Location:    {SAVE_DIR.absolute()}")
    print("=" * 70)
    
    if stats['success'] > 0:
        print("\n🎯 Next Step: Run the Vision AI table extractor on these PDFs!")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_pdf_harvester()

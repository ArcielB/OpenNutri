"""
Scientific Harvester - Structured XML Table Extractor
Uses NCBI API to fetch full-text XML and extract data tables directly.

Author: OpenNutri Project
Strategy: "Pure API" - No web scraping. 100% Official Data.
"""

import os
import sys
import json
import time
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from Bio import Entrez

# Import configuration
try:
    from scripts.config_targets import TARGET_CONFIG
except ImportError:
    from config_targets import TARGET_CONFIG


# =============================================================================
# ⚠️  CONFIGURATION
# =============================================================================
Entrez.email = "f221229078@ktun.edu.tr"
Entrez.tool = "OpenNutri_StructuredHarvester"

# Output Directories
BASE_DIR = Path("data/structured_lake")
XML_DIR = BASE_DIR / "xml_raw"
TABLES_DIR = BASE_DIR / "tables"

XML_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)

# API Config
REQUEST_DELAY_SECONDS = 0.5


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def print_banner():
    """Display startup banner."""
    print("=" * 70)
    print("🧬 OpenNutri Structured Harvester - API Mode")
    print("=" * 70)
    print(f"📧 Email: {Entrez.email}")
    print(f"🔍 Strategy: Pure API Extraction (No scraping)")
    print(f"📁 XML Storage: {XML_DIR.absolute()}")
    print(f"📁 CSV Tables:  {TABLES_DIR.absolute()}")
    print("=" * 70)
    return True


def search_pmc() -> list:
    """
    Search PubMed Central using the API.
    """
    query = TARGET_CONFIG["query"]
    max_results = TARGET_CONFIG["max_results"]
    
    print(f"\n🔎 Querying NCBI API...")
    
    try:
        search_handle = Entrez.esearch(
            db="pmc",
            term=query,
            retmax=max_results,
            sort=TARGET_CONFIG.get("sort_order", "relevance")
        )
        search_results = Entrez.read(search_handle)
        search_handle.close()
        
        id_list = search_results.get("IdList", [])
        print(f"✅ API returned {len(id_list)} relevant papers.")
        return id_list
        
    except Exception as e:
        print(f"❌ API Search failed: {e}")
        return []


def parse_tables_from_xml(xml_content: str, pmc_id: str) -> list:
    """
    Parses <table-wrap> tags from XML.
    Returns the raw XML string of the table to preserve structure (colspans, nested headers).
    """
    extracted_tables = []
    
    try:
        root = ET.fromstring(xml_content)
        
        # Find all table-wraps
        tables = root.findall(".//table-wrap")
        
        for i, table in enumerate(tables):
            table_id = table.get("id", f"tbl{i+1}")
            label = table.find("label")
            caption = table.find("caption")
            
            label_text = label.text if label is not None else f"Table {i+1}"
            caption_text = "".join(caption.itertext()) if caption is not None else "No caption"
            
            # Convert the sub-tree back to string to preserve structure
            table_xml = ET.tostring(table, encoding="unicode")
            
            extracted_tables.append({
                "id": table_id,
                "label": label_text,
                "caption": caption_text[:200],
                "xml_content": table_xml
            })
                    
    except Exception as e:
        print(f"   ⚠️ XML Parse Error: {e}")
        
    return extracted_tables


def fetch_and_process(pmc_id: str):
    """
    1. Call API to get XML
    2. Save XML
    3. Extract Table XMLs
    """
    # Check cache
    xml_path = XML_DIR / f"PMC{pmc_id}.xml"
    
    xml_content = None
    if xml_path.exists():
        with open(xml_path, "r", encoding="utf-8") as f:
            xml_content = f.read()
    else:
        # Fetch from API
        try:
            handle = Entrez.efetch(db="pmc", id=pmc_id, retmode="xml")
            xml_content = handle.read()
            handle.close()
            
            # Convert bytes to string if needed
            if isinstance(xml_content, bytes):
                xml_content = xml_content.decode("utf-8")
                
            # Ensure directory exists (Robustness fix)
            xml_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save Raw XML
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(xml_content)
                
        except Exception as e:
            # Try to log the path that failed
            print(f"FAILED to write to {xml_path.absolute()}")
            return {"status": "failed", "error": f"{str(e)} (Path: {xml_path})"}

    # Extract Tables
    tables = parse_tables_from_xml(xml_content, pmc_id)
    
    saved_tables = []
    if tables:
        # Create folder for this paper's tables
        paper_table_dir = TABLES_DIR / f"PMC{pmc_id}"
        paper_table_dir.mkdir(parents=True, exist_ok=True)
        
        for t in tables:
            clean_label = "".join(c for c in t["label"] if c.isalnum() or c in (' ', '_')).strip().replace(" ", "_")
            file_name = f"{clean_label}.xml"
            file_path = paper_table_dir / file_name
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(t["xml_content"])
            
            saved_tables.append(file_name)
            
    return {
        "status": "success", 
        "tables_found": len(saved_tables),
        "table_files": saved_tables
    }


def run_structured_harvester():
    if not print_banner(): return
    
    # 1. Get IDs
    pmc_ids = search_pmc()
    
    if not pmc_ids:
        print("No papers found.")
        return

    print(f"\n🚀 Processing {len(pmc_ids)} papers...\n")
    
    stats = {"success": 0, "failed": 0, "tables_extracted": 0}
    
    for i, pmc_id in enumerate(pmc_ids, 1):
        print(f"[{i}/{len(pmc_ids)}] PMC{pmc_id}...", end=" ", flush=True)
        
        result = fetch_and_process(pmc_id)
        
        if result["status"] == "success":
            n_tables = result["tables_found"]
            print(f"✅ Parsed. Found {n_tables} tables.")
            stats["success"] += 1
            stats["tables_extracted"] += n_tables
        else:
            print(f"❌ Error: {result.get('error')}")
            stats["failed"] += 1
            
        if i < len(pmc_ids):
            time.sleep(REQUEST_DELAY_SECONDS)
            
    print("\n" + "="*70)
    print(f"🏁 DONE! Extracted {stats['tables_extracted']} tables from {stats['success']} papers.")
    print(f"📊 CSVs are saved in: {TABLES_DIR}")


if __name__ == "__main__":
    run_structured_harvester()

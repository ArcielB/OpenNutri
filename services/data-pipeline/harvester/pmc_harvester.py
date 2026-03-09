import os
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from crawler.core.knowledge import KnowledgeBase
from crawler.harvester.client import PMCClient
from crawler.harvester.query_builder import QueryBuilder
from crawler.processing.content import extract_metadata

class PMCHarvester:
    """
    Coordinator for harvesting papers from PubMed Central.
    Manages the flow: Search -> Filter (Dedupe) -> Download -> Save -> Update State.
    """
    
    def __init__(self, knowledge_base: KnowledgeBase, email: str, save_dir: str = "data/raw_lake"):
        self.kb = knowledge_base
        self.client = PMCClient(email)
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
    def harvest(self, query: str, limit: int = 10, source_term: str = None, strategy: str = None) -> List[Dict]:
        """
        Run a harvest cycle for a specific query.
        
        Args:
            query: The search string
            limit: How many NEW papers to fetch
            source_term: The term used to generate this query (for learning)
            strategy: 'Track A' or 'Track B'
            
        Returns:
            List of result dictionaries (status, pmid, etc.)
        """
        print(f"🔎 Searching: {query} (Target: {limit} new)")
        
        # 1. Search (fetch more to allow for duplicates)
        pmc_ids = self.client.search(query, max_results=limit)
        
        results = []
        downloaded_count = 0
        
        for pmc_id in pmc_ids:
            if downloaded_count >= limit:
                break
                
            # 2. Check Deduplication
            if self.kb.is_processed(pmc_id):
                continue
                
            # 3. Fetch Full Text
            xml_content = self.client.fetch_xml(pmc_id)
            if not xml_content:
                continue
                
            # 4. Save and Update State
            result = self._save_paper(pmc_id, xml_content, source_term, strategy)
            results.append(result)
            
            if result['status'] == 'success':
                downloaded_count += 1
                self.kb.mark_paper_processed(pmc_id)
                print(f"   ✅ Saved PMC{pmc_id}: {result.get('title', '')[:50]}...")
            else:
                print(f"   ❌ Failed PMC{pmc_id}: {result.get('error')}")
                
        self.kb.save()
        return results

    def _save_paper(self, pmc_id: str, xml_content: str, source_term: str, strategy: str) -> Dict:
        """
        Internal: Save individual paper to disk.
        """
        try:
            metadata = extract_metadata(xml_content)
            
            doc = {
                "pmc_id": f"PMC{pmc_id}",
                "harvested_at": datetime.utcnow().isoformat() + "Z",
                "source_term": source_term,
                "strategy": strategy,
                "metadata": metadata,
                "raw_xml": xml_content
            }
            
            filename = self.save_dir / f"PMC{pmc_id}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(doc, f, indent=2, ensure_ascii=False)
                
            return {
                "status": "success", 
                "pmc_id": pmc_id, 
                "title": metadata.get("title"),
                "file": str(filename)
            }
            
        except Exception as e:
            return {"status": "failed", "pmc_id": pmc_id, "error": str(e)}

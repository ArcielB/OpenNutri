"""
PMC Harvester — Coordinates paper discovery, filtering, and download.

Flow: Search → Fetch Abstracts → Relevance Filter → Download Full XML → Save
"""

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from crawler.core.knowledge import KnowledgeBase
from crawler.harvester.client import PMCClient
from crawler.harvester.query_builder import QueryBuilder
from crawler.harvester.relevance_filter import RelevanceFilter
from crawler.processing.content import extract_metadata


class PMCHarvester:
    """
    Coordinator for harvesting papers from PubMed Central.
    
    Flow:
      1. Search PMC with a query
      2. De-duplicate against already-processed papers
      3. Fetch abstracts in batch (cheap)
      4. Run RelevanceFilter on abstracts
      5. Download full XML only for papers that pass
      6. Save and update state
    """
    
    def __init__(self, knowledge_base: KnowledgeBase, email: str, 
                 save_dir: str = "data/raw_lake", relevance_threshold: float = 3.0):
        self.kb = knowledge_base
        self.client = PMCClient(email)
        self.relevance_filter = RelevanceFilter(threshold=relevance_threshold)
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
    def harvest(self, query: str, limit: int = 10, source_term: str = None, 
                strategy: str = None, verbose: bool = False) -> List[Dict]:
        """
        Run a harvest cycle for a specific query.
        
        Args:
            query: The PubMed search string
            limit: How many NEW papers to download
            source_term: The term used to generate this query (for learning)
            strategy: 'Track A', 'Track B', etc.
            verbose: Print detailed filter reasons
            
        Returns:
            List of result dicts with status, pmc_id, title, relevance info
        """
        print(f"🔎 Searching: {query[:100]}... (Target: {limit} new)")
        
        # 1. Search PMC
        pmc_ids = self.client.search(query, max_results=limit * 3)
        
        if not pmc_ids:
            print("   📭 No results found")
            return []
        
        print(f"   📋 Found {len(pmc_ids)} candidates")
        
        # 2. De-duplicate
        new_ids = [pid for pid in pmc_ids if not self.kb.is_processed(pid)]
        if not new_ids:
            print("   🔄 All papers already processed")
            return []
        
        print(f"   🆕 {len(new_ids)} new (after de-dup)")
        
        # 3. Fetch abstracts in batch
        print(f"   📝 Fetching abstracts...")
        summaries = self.client.fetch_summaries(new_ids)
        
        # 4. Relevance filter
        passed, filtered = self.relevance_filter.filter_batch(summaries)
        
        print(f"   🎯 Relevance filter: {len(passed)} passed, {len(filtered)} filtered out")
        
        if verbose:
            for p in filtered:
                print(f"      ❌ Filtered: '{p.get('title', 'Unknown')[:60]}...'")
                print(f"         Score: {p.get('relevance_score', 0):.1f}")
                for r in p.get('relevance_reasons', [])[:3]:
                    print(f"         {r}")
        
        # 5. Download full XML only for passed papers
        results = []
        downloaded_count = 0
        
        for paper_summary in passed:
            if downloaded_count >= limit:
                break
            
            pmc_id = paper_summary['pmc_id']
            
            # Double-check dedup (in case of race conditions)
            if self.kb.is_processed(pmc_id):
                continue
            
            # Fetch full XML
            xml_content = self.client.fetch_xml(pmc_id)
            if not xml_content:
                results.append({
                    'status': 'failed', 
                    'pmc_id': pmc_id, 
                    'error': 'XML fetch failed',
                    'title': paper_summary.get('title', ''),
                    'relevance_score': paper_summary.get('relevance_score', 0),
                })
                continue
            
            # Save
            result = self._save_paper(pmc_id, xml_content, source_term, strategy, paper_summary)
            results.append(result)
            
            if result['status'] == 'success':
                downloaded_count += 1
                self.kb.mark_paper_processed(pmc_id)
                score = paper_summary.get('relevance_score', 0)
                print(f"   ✅ Saved PMC{pmc_id} (score:{score:.0f}): {result.get('title', '')[:60]}...")
            else:
                print(f"   ❌ Failed PMC{pmc_id}: {result.get('error')}")
        
        # Also mark filtered papers as processed to avoid re-checking
        for paper_summary in filtered:
            pmc_id = paper_summary.get('pmc_id', '')
            if pmc_id:
                self.kb.mark_paper_processed(pmc_id)
        
        self.kb.save()
        return results

    def _save_paper(self, pmc_id: str, xml_content: str, source_term: str, 
                    strategy: str, summary: Dict) -> Dict:
        """Save individual paper to disk."""
        try:
            metadata = extract_metadata(xml_content)
            
            doc = {
                "pmc_id": f"PMC{pmc_id}",
                "harvested_at": datetime.utcnow().isoformat() + "Z",
                "source_term": source_term,
                "strategy": strategy,
                "metadata": metadata,
                "relevance_score": summary.get('relevance_score', 0),
                "relevance_reasons": summary.get('relevance_reasons', []),
                "raw_xml": xml_content
            }
            
            filename = self.save_dir / f"PMC{pmc_id}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(doc, f, indent=2, ensure_ascii=False)
                
            return {
                "status": "success", 
                "pmc_id": pmc_id, 
                "title": metadata.get("title"),
                "journal": metadata.get("journal"),
                "file": str(filename),
                "relevance_score": summary.get('relevance_score', 0),
            }
            
        except Exception as e:
            return {"status": "failed", "pmc_id": pmc_id, "error": str(e)}

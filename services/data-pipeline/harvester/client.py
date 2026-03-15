"""
PMC Client — Direct HTTP client for NCBI Entrez API.

Uses requests instead of Biopython for reliability.
Provides search, abstract fetching, and full XML fetching for PubMed Central.
"""

import time
import requests
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict
import socket

# Force IPv4 because the system has a broken IPv6 route to NCBI
# which causes requests to hang indefinitely.
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
    return old_getaddrinfo(host, port, socket.AF_INET, socktype, proto, flags)
socket.getaddrinfo = new_getaddrinfo

ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PMCClient:
    """
    HTTP client for NCBI Entrez API (PubMed Central).
    Uses requests library directly for reliable connectivity.
    """
    
    def __init__(self, email: str, tool_name: str = "OpenNutri_Harvester"):
        self.email = email
        self.tool_name = tool_name
        self.request_delay = 0.4  # Seconds between requests
        self.timeout = 30  # HTTP timeout

    def _params(self, **kwargs) -> dict:
        """Add standard params (email, tool) to request."""
        kwargs['email'] = self.email
        kwargs['tool'] = self.tool_name
        return kwargs

    def search(self, query: str, max_results: int = 20) -> List[str]:
        """
        Search PMC for articles matching the query.
        Returns a list of PMC IDs.
        """
        try:
            fetch_max = min(max_results * 3, 500)
            
            resp = requests.get(
                f"{ENTREZ_BASE}/esearch.fcgi",
                params=self._params(
                    db="pmc",
                    term=query,
                    retmax=fetch_max,
                    sort="relevance",
                    retmode="xml"
                ),
                timeout=self.timeout
            )
            resp.raise_for_status()
            
            root = ET.fromstring(resp.text)
            ids = [id_el.text for id_el in root.findall('.//IdList/Id') if id_el.text]
            return ids
            
        except Exception as e:
            print(f"❌ PMC Search failed: {e}")
            return []
        finally:
            time.sleep(self.request_delay)

    def fetch_summaries(self, pmc_ids: List[str]) -> List[Dict]:
        """
        Fetch title + abstract for a batch of PMC IDs.
        Returns list of dicts with 'pmc_id', 'title', 'abstract', 'journal'.
        """
        if not pmc_ids:
            return []
        
        results = []
        
        try:
            # Process in batches of 20
            batch_size = 20
            for i in range(0, len(pmc_ids), batch_size):
                batch = pmc_ids[i:i + batch_size]
                id_str = ",".join(batch)
                
                resp = requests.get(
                    f"{ENTREZ_BASE}/efetch.fcgi",
                    params=self._params(
                        db="pmc",
                        id=id_str,
                        retmode="xml"
                    ),
                    timeout=self.timeout
                )
                resp.raise_for_status()
                
                parsed = self._parse_articles_xml(resp.text, batch)
                results.extend(parsed)
                
                time.sleep(self.request_delay)
            
        except Exception as e:
            print(f"❌ Summary fetch failed: {e}")
            for pmc_id in pmc_ids:
                if not any(r['pmc_id'] == pmc_id for r in results):
                    results.append({
                        'pmc_id': pmc_id, 'title': '', 'abstract': '', 'journal': ''
                    })
        
        return results
    
    def _parse_articles_xml(self, xml_data: str, pmc_ids: List[str]) -> List[Dict]:
        """Parse XML response to extract titles and abstracts."""
        results = []
        
        try:
            root = ET.fromstring(xml_data)
            
            for article in root.findall('.//article'):
                result = {'pmc_id': '', 'title': '', 'abstract': '', 'journal': ''}
                
                front = article.find('.//front')
                if front is None:
                    continue
                
                article_meta = front.find('.//article-meta')
                if article_meta is None:
                    continue
                
                # PMC ID
                for aid in article_meta.findall('.//article-id'):
                    if aid.get('pub-id-type') == 'pmc':
                        result['pmc_id'] = aid.text or ''
                        break
                
                if not result['pmc_id']:
                    idx = len(results)
                    if idx < len(pmc_ids):
                        result['pmc_id'] = pmc_ids[idx]
                
                # Title
                title_group = article_meta.find('.//title-group')
                if title_group is not None:
                    title_el = title_group.find('.//article-title')
                    if title_el is not None:
                        result['title'] = ''.join(title_el.itertext()).strip()
                
                # Abstract
                abstract_el = article_meta.find('.//abstract')
                if abstract_el is not None:
                    result['abstract'] = ''.join(abstract_el.itertext()).strip()
                
                # Journal
                journal_meta = front.find('.//journal-meta')
                if journal_meta is not None:
                    jt = journal_meta.find('.//journal-title')
                    if jt is not None:
                        result['journal'] = ''.join(jt.itertext()).strip()
                
                results.append(result)
        
        except ET.ParseError as e:
            print(f"⚠️ XML parse error: {e}")
            for pmc_id in pmc_ids:
                if not any(r['pmc_id'] == pmc_id for r in results):
                    results.append({
                        'pmc_id': pmc_id, 'title': '', 'abstract': '', 'journal': ''
                    })
        
        return results

    def fetch_xml(self, pmc_id: str) -> Optional[str]:
        """Fetch full-text XML for a PMC article."""
        try:
            resp = requests.get(
                f"{ENTREZ_BASE}/efetch.fcgi",
                params=self._params(
                    db="pmc",
                    id=pmc_id,
                    retmode="xml"
                ),
                timeout=60  # Longer timeout for full text
            )
            resp.raise_for_status()
            return resp.text
            
        except Exception as e:
            print(f"❌ Fetch failed for PMC{pmc_id}: {e}")
            return None
        finally:
            time.sleep(self.request_delay)

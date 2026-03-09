import time
from Bio import Entrez
from typing import List, Optional

class PMCClient:
    """
    Wrapper for NCBI Entrez API to interact with PubMed Central (PMC).
    """
    
    def __init__(self, email: str, tool_name: str = "OpenNutri_Harvester"):
        Entrez.email = email
        Entrez.tool = tool_name
        self.request_delay = 0.5  # Seconds

    def search(self, query: str, max_results: int = 20) -> List[str]:
        """
        Search PMC for articles matching the query.
        Returns a list of PMC IDs (e.g., ['123456', '789012']).
        """
        try:
            # Always fetch a bit more to allow for filtering
            fetch_max = min(max_results * 2, 1000)
            
            handle = Entrez.esearch(
                db="pmc",
                term=query,
                retmax=fetch_max,
                sort="relevance"
            )
            results = Entrez.read(handle)
            handle.close()
            
            ids = results.get("IdList", [])
            # Return only what was requested, caller can filter further
            return ids
            
        except Exception as e:
            print(f"❌ PMC Search failed: {e}")
            return []
        finally:
            time.sleep(self.request_delay)

    def fetch_xml(self, pmc_id: str) -> Optional[str]:
        """
        Fetch the full-text XML for a given PMC article.
        """
        try:
            handle = Entrez.efetch(
                db="pmc",
                id=pmc_id,
                retmode="xml"
            )
            xml_data = handle.read()
            handle.close()
            
            if isinstance(xml_data, bytes):
                xml_data = xml_data.decode("utf-8")
                
            return xml_data
            
        except Exception as e:
            print(f"❌ Fetch failed for PMC{pmc_id}: {e}")
            return None
        finally:
            time.sleep(self.request_delay)

"""
Data Source - Supabase Implementation

Loads foods and nutrients from Supabase database.
"""

from typing import List, Set
from supabase import create_client

# Import credentials
try:
    from crawler.config import SUPABASE_URL, SUPABASE_KEY
except ImportError:
    import os
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


class DataSource:
    """
    Loads foods and nutrients from Supabase.
    """
    
    def __init__(self):
        self.client = None
        self._foods_cache: List[str] = []
        self._nutrients_cache: List[str] = []
        self._connect()
        
    def _connect(self):
        """Initialize Supabase client."""
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("⚠️ Supabase credentials not found. Check crawler/config.py")
            return
            
        try:
            self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("✅ Connected to Supabase")
        except Exception as e:
            print(f"❌ Supabase connection failed: {e}")
    
    def is_connected(self) -> bool:
        return self.client is not None
    
    def get_foods(self, force_refresh: bool = False) -> List[str]:
        """
        Get unique BASE food names from database.
        Extracts the base name (before comma/dash) for better search results.
        E.g., "HUMMUS, SABRA CLASSIC" -> "Hummus"
        """
        if self._foods_cache and not force_refresh:
            return self._foods_cache
            
        if not self.client:
            return []
            
        try:
            import re
            
            response = self.client.table('foods').select('description').execute()
            
            # Extract base food names and deduplicate
            seen: Set[str] = set()
            unique_foods: List[str] = []
            
            for row in response.data:
                desc = row.get('description', '')
                if desc:
                    # Extract base name (before comma or dash)
                    base = re.split(r'[,\-]', desc)[0].strip()
                    # Normalize to title case
                    base = base.title()
                    normalized = base.lower()
                    
                    # Skip non-food entries (nutrients that snuck in)
                    skip_words = ['proximates', 'moisture', 'vitamin', 'fa', 'choles', 'b12', 'se']
                    if any(sw in normalized for sw in skip_words):
                        continue
                    
                    if normalized not in seen and len(base) > 2:
                        seen.add(normalized)
                        unique_foods.append(base)
            
            self._foods_cache = unique_foods
            print(f"🍎 Loaded {len(unique_foods)} unique base foods from Supabase")
            return unique_foods
            
        except Exception as e:
            print(f"❌ Failed to fetch foods: {e}")
            return []
    
    def get_nutrients(self, force_refresh: bool = False) -> List[str]:
        """
        Get nutrient names from database.
        Caches results to avoid repeated queries.
        """
        if self._nutrients_cache and not force_refresh:
            return self._nutrients_cache
            
        if not self.client:
            return []
            
        try:
            response = self.client.table('nutrients').select('name').execute()
            
            nutrients = [row['name'] for row in response.data if row.get('name')]
            self._nutrients_cache = nutrients
            print(f"🧪 Loaded {len(nutrients)} nutrients from Supabase")
            return nutrients
            
        except Exception as e:
            print(f"❌ Failed to fetch nutrients: {e}")
            return []


# Singleton instance
_data_source = None

def get_data_source() -> DataSource:
    """Get or create the data source singleton."""
    global _data_source
    if _data_source is None:
        _data_source = DataSource()
    return _data_source

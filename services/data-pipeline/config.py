"""Compatibility configuration for legacy data-pipeline modules.

Runtime credentials must come from environment variables. Do not put API keys,
database URLs, or Supabase keys in this file.
"""

import os


SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL", "")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("VITE_SUPABASE_ANON_KEY")
    or ""
)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

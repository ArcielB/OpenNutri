import os
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv

annotator_env_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 
    "..", "..", "..", "apps", "expert-annotator", ".env"
))
load_dotenv(annotator_env_path)

url: str = os.environ.get("VITE_SUPABASE_URL")
key: str = os.environ.get("VITE_SUPABASE_ANON_KEY")

supabase: Client = create_client(url, key)

res = supabase.table("papers").select("id, title, filename").execute()
print("Papers in DB:")
for r in res.data:
    print(r)

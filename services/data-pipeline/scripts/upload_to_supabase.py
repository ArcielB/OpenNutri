import os
import json
import asyncio
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from the expert-annotator app
annotator_env_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 
    "..", "..", "..", "apps", "expert-annotator", ".env"
))
load_dotenv(annotator_env_path)

url: str = os.environ.get("VITE_SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("VITE_SUPABASE_ANON_KEY")

if not url or not key:
    print("❌ Error: Missing Supabase credentials in apps/expert-annotator/.env")
    exit(1)

supabase: Client = create_client(url, key)

# Directories
RAW_PDFS_DIR = Path("data/raw_pdfs")
METADATA_FILE = RAW_PDFS_DIR / "_harvest_metadata.json"

async def upload_papers():
    print("=" * 60)
    print("🚀 OpenNutri: Uploading Crawled PDFs to Supabase")
    print("=" * 60)
    
    # 1. Read metadata from the crawler
    if not METADATA_FILE.exists():
        print(f"❌ Error: Metadata file not found at {METADATA_FILE}")
        return
        
    with open(METADATA_FILE, "r") as f:
        harvest_data = json.load(f)
        
    results = harvest_data.get("results", [])
    successful_downloads = [r for r in results if r.get("status") == "success"]
    audit_rejects = [r for r in results if r.get("audit") is True and r.get("status") != "success"]

    seen_files = set()
    upload_candidates = []
    for paper in successful_downloads + audit_rejects:
        file_path = paper.get("file")
        if not file_path or file_path in seen_files:
            continue
        seen_files.add(file_path)
        upload_candidates.append(paper)
    
    print(f"📦 Found {len(successful_downloads)} successful downloads in metadata.")
    if audit_rejects:
        print(f"🧪 Including {len(audit_rejects)} audit rejects for review.")
    
    # Ensure the "papers" bucket exists
    try:
        supabase.storage.create_bucket("papers", options={"public": True})
        print("✅ Created 'papers' bucket in Supabase Storage.")
    except Exception as e:
        # It probably already exists, which is fine
        pass
        
    # 2. Upload each PDF and insert DB record
    uploaded_count = 0
    
    for paper in upload_candidates:
        pmc_id = paper.get("pmc_id") or paper.get("pmcid")
        title = paper.get("title", f"PMC{pmc_id or ''}")
        file_path = Path(paper.get("file"))
        filename = file_path.name
        ingest_status = "accepted" if paper.get("status") == "success" else "rejected"
        audit_flag = bool(paper.get("audit"))
        rejection_reasons = paper.get("reasons", []) if ingest_status != "accepted" else []
        
        if not file_path.exists():
            print(f"⚠️ Warning: File {file_path} not found on disk. Skipping.")
            continue
            
        print(f"\n📤 Processing {filename}...")
        
        try:
            # A) Upload to Supabase Storage (Bucket: papers)
            with open(file_path, "rb") as f:
                # Upsert to overwrite if it already exists
                res = supabase.storage.from_("papers").upload(
                    path=filename,
                    file=f,
                    file_options={"cache-control": "3600", "upsert": "true", "content-type": "application/pdf"}
                )
            print(f"   ✓ Uploaded to Storage bucket.")
            
            # B) Insert metadata into Supabase Database ('papers' table)
            existing = supabase.table("papers").select("id").eq("filename", filename).execute()
            if not existing.data:
                db_res = supabase.table("papers").insert({
                    "title": title,
                    "doi": paper.get("doi", f"pmc:{pmc_id}"),
                    "filename": filename,
                    "ingest_status": ingest_status,
                    "audit_flag": audit_flag,
                    "rejection_reasons": rejection_reasons,
                }).execute()
                print(f"   ✓ Inserted into Database.")
            else:
                print(f"   ✓ Already exists in Database.")
            uploaded_count += 1
            
        except Exception as e:
            print(f"   ❌ Error uploading {filename}: {e}")

    print("=" * 60)
    print(f"🎉 Successfully uploaded and registered {uploaded_count} PDFs!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(upload_papers())

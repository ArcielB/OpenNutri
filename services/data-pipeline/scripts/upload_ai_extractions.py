import os
import json
import sys
from pathlib import Path
from supabase import create_client, Client

# Add path to config
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    from config import SUPABASE_URL, SUPABASE_KEY
except ImportError:
    print("❌ Could not load config.py. Make sure it exists in services/data-pipeline/")
    sys.exit(1)

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Supabase credentials missing in config.py")
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Path to extracted JSONs
    extracted_dir = Path("/home/arciel/Desktop/OpenNutri/data/extracted")
    if not extracted_dir.exists():
        print(f"❌ Extracted directory not found: {extracted_dir}")
        return

    json_files = list(extracted_dir.glob("*_extracted.json"))
    print(f"🔍 Found {len(json_files)} extracted files.")

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            pmc_id = data.get("pmc_id")
            if not pmc_id:
                print(f"⚠️ No pmc_id in {json_file.name}, skipping.")
                continue

            # Find the paper in the database
            # The database uses filename like "PMC12345.pdf"
            filename = f"{pmc_id}.pdf"
            
            res = supabase.table("papers").select("id").eq("filename", filename).execute()
            
            if not res.data:
                # Try case insensitive or without .pdf if needed
                res = supabase.table("papers").select("id").ilike("filename", f"%{pmc_id}%").execute()
            
            if not res.data:
                print(f"⚠️ Paper {filename} not found in database, skipping.")
                continue
            
            paper_id = res.data[0]["id"]
            
            # Upsert into ai_extractions
            extract_payload = {
                "paper_id": paper_id,
                "model_name": "gemini-3-flash-preview",
                "is_useful": data.get("is_useful", False),
                "reasoning": data.get("reasoning"),
                "overall_confidence": data.get("overall_confidence"),
                "raw_data": data,
                "status": "pending"
            }
            
            # Use upsert based on paper_id and model_name if possible, 
            # but since we don't have a unique constraint yet, we'll just check existence
            existing = supabase.table("ai_extractions").select("id").eq("paper_id", paper_id).eq("model_name", "gemini-3-flash-preview").execute()
            
            if existing.data:
                supabase.table("ai_extractions").update(extract_payload).eq("id", existing.data[0]["id"]).execute()
                print(f"✅ Updated AI extraction for paper {paper_id} ({pmc_id})")
            else:
                supabase.table("ai_extractions").insert(extract_payload).execute()
                print(f"✅ Inserted AI extraction for paper {paper_id} ({pmc_id})")

        except Exception as e:
            print(f"❌ Error processing {json_file.name}: {e}")

if __name__ == "__main__":
    main()

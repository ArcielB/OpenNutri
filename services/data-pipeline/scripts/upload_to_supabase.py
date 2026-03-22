import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client


annotator_env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "apps", "expert-annotator", ".env")
)
load_dotenv(annotator_env_path)

url: str = os.environ.get("VITE_SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("VITE_SUPABASE_ANON_KEY")

if not url or not key:
    print("❌ Error: Missing Supabase credentials in apps/expert-annotator/.env")
    raise SystemExit(1)

supabase: Client = create_client(url, key)

RAW_PDFS_DIR = Path("data/raw_pdfs")
METADATA_FILE = RAW_PDFS_DIR / "_harvest_metadata.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_artifact(manifest: dict, key_name: str) -> Path | None:
    raw_value = manifest.get(key_name)
    if not raw_value:
        return None
    return Path(str(raw_value))


def _paper_payload(record: dict, filename: str) -> dict:
    pmc_id = record.get("pmc_id") or record.get("pmcid")
    return {
        "title": record.get("title") or f"PMC{pmc_id or ''}",
        "abstract": record.get("abstract"),
        "doi": record.get("doi") or (f"pmc:{pmc_id}" if pmc_id else None),
        "filename": filename,
        "source": record.get("source"),
        "source_record_id": record.get("source_record_id"),
        "workflow_language": record.get("workflow_language"),
        "search_gate_score": record.get("search_gate_score"),
        "filter_score": record.get("filter_score"),
        "ingest_status": "accepted",
        "audit_flag": False,
        "rejection_reasons": [],
    }


def _chunked(rows: list[dict], size: int) -> list[list[dict]]:
    return [rows[idx: idx + size] for idx in range(0, len(rows), size)]


async def upload_papers() -> None:
    print("=" * 60)
    print("🚀 OpenNutri: Uploading Crawled PDFs to Supabase")
    print("=" * 60)

    if not METADATA_FILE.exists():
        print(f"❌ Error: Metadata file not found at {METADATA_FILE}")
        return

    manifest = _load_json(METADATA_FILE)
    results = manifest.get("results", [])
    upload_candidates = [row for row in results if row.get("status") == "success"]

    print(f"📦 Found {len(upload_candidates)} successful downloads in metadata.")

    candidate_store_path = _resolve_artifact(manifest, "candidate_store")
    search_hits_path = _resolve_artifact(manifest, "search_hits")
    candidate_store = _load_json(candidate_store_path) if candidate_store_path else {}
    search_hits_payload = _load_json(search_hits_path) if search_hits_path else {}
    candidate_by_key = {
        row.get("canonical_key"): row
        for row in candidate_store.get("candidates", [])
        if isinstance(row, dict) and row.get("canonical_key")
    }

    try:
        supabase.storage.create_bucket("papers", options={"public": True})
        print("✅ Created 'papers' bucket in Supabase Storage.")
    except Exception:
        pass

    paper_id_by_key: dict[str, int] = {}
    uploaded_count = 0

    for record in upload_candidates:
        file_path = Path(record.get("file") or "")
        if not file_path.exists():
            print(f"⚠️ Warning: File {file_path} not found on disk. Skipping.")
            continue

        filename = file_path.name
        canonical_key = record.get("canonical_key")
        candidate_row = candidate_by_key.get(canonical_key, {})
        paper_row = {**candidate_row, **record}

        print(f"\n📤 Processing {filename}...")
        try:
            with file_path.open("rb") as handle:
                supabase.storage.from_("papers").upload(
                    path=filename,
                    file=handle,
                    file_options={
                        "cache-control": "3600",
                        "upsert": "true",
                        "content-type": "application/pdf",
                    },
                )
            print("   ✓ Uploaded to Storage bucket.")

            existing = supabase.table("papers").select("id").eq("filename", filename).execute()
            if existing.data:
                paper_id = int(existing.data[0]["id"])
                supabase.table("papers").update(_paper_payload(paper_row, filename)).eq("id", paper_id).execute()
                print("   ✓ Updated existing paper metadata.")
            else:
                inserted = supabase.table("papers").insert(_paper_payload(paper_row, filename)).execute()
                paper_id = int(inserted.data[0]["id"])
                print("   ✓ Inserted into Database.")

            if canonical_key:
                paper_id_by_key[canonical_key] = paper_id
            uploaded_count += 1
        except Exception as exc:
            print(f"   ❌ Error uploading {filename}: {exc}")

    search_hits = []
    for row in search_hits_payload.get("hits", []):
        if not isinstance(row, dict):
            continue
        payload = {
            "paper_id": paper_id_by_key.get(row.get("canonical_key")),
            "canonical_key": row.get("canonical_key"),
            "source": row.get("source"),
            "source_record_id": row.get("source_record_id"),
            "external_id": row.get("external_id"),
            "pmcid": row.get("pmcid"),
            "doi": row.get("doi"),
            "title": row.get("title"),
            "abstract": row.get("abstract"),
            "workflow_language": row.get("workflow_language"),
            "query_text": row.get("query"),
            "template_id": row.get("template_id"),
            "source_term": row.get("source_term"),
            "term_type": row.get("term_type"),
            "query_phrase": row.get("query_phrase"),
            "search_gate_score": row.get("search_gate_score"),
            "search_gate_pass": row.get("search_gate_pass"),
            "filter_score": row.get("filter_score"),
            "filter_pass": row.get("filter_pass"),
            "is_duplicate": row.get("is_duplicate") or False,
        }
        if not payload["canonical_key"] or not payload["source"] or not payload["query_text"]:
            continue
        search_hits.append(payload)

    inserted_hits = 0
    for batch in _chunked(search_hits, 500):
        if not batch:
            continue
        try:
            supabase.table("paper_search_hits").insert(batch).execute()
            inserted_hits += len(batch)
        except Exception as exc:
            print(f"⚠️ Failed inserting search-hit batch: {exc}")
            raise

    print("=" * 60)
    print(f"🎉 Successfully uploaded and registered {uploaded_count} PDFs!")
    print(f"🧾 Persisted {inserted_hits} metadata-stage search hits.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(upload_papers())

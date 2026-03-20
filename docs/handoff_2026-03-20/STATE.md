# OpenNutri Handoff — 2026-03-20 (Europe/Istanbul)

This is a snapshot of the current state, decisions, changes, and next steps so work can continue elsewhere without loss of context.

**Project Direction (Current)**
OpenNutri is building a paper-to-food-composition pipeline with a human labeling UI. The plan is:
1. Scrape and store candidate papers.
2. Apply L2 relevance filtering (now with dual embeddings + anchors).
3. Collect human labels in the UI.
4. Feed labels back to improve query terms, anchors, and eventually train a classifier.

**Key Decisions**
- Repo should remain private for now.
- L2 should use dual embeddings: English + multilingual (but only English + Turkish anchors).
- Use anchor-phrase similarity as an early filter before classifier training exists.
- Label events must be recorded on every UI save (draft, done, skipped).

**Recent Code Changes (High Signal)**
1. Dual embedding baseline for L2 metadata scoring.
2. Label event logging from the UI into a new table.
3. README updated to state language scope: English + Turkish only.

**Files Changed (Latest)**
- `services/data-pipeline/food_paper_crawler/embeddings.py`
  - New dual embedding scorer (English + multilingual), anchor phrases, thresholds.
  - Environment variables:
    - `L2_EMBED_EN_MODEL` default `all-MiniLM-L6-v2`
    - `L2_EMBED_MULTI_MODEL` default `paraphrase-multilingual-MiniLM-L12-v2`
    - `L2_EMBED_EN_THRESHOLD` default `0.45`
    - `L2_EMBED_MULTI_THRESHOLD` default `0.42`
    - `L2_EMBED_MAX_CHARS` default `1800`
- `services/data-pipeline/food_paper_crawler/crawler_v2.py`
  - Imports and initializes dual embedding scorer.
  - Embedding scores recorded in reason details.
  - Accept if either model passes its threshold.
  - Manifest now includes embedding config info.
- `apps/expert-annotator/src/pages/Annotate.jsx`
  - On save (draft/done/skipped) inserts a label event row into `paper_label_events`.
  - Stores counts for food items and nutrient values.
- `apps/expert-annotator/migration.sql`
  - Added `paper_label_events` table + indexes.
- `README.md`
  - Explicitly notes language scope: English + Turkish only.

**Label Event Table (New)**
- Table: `paper_label_events`
- Columns:
  - `paper_id`, `annotation_id`, `user_id`
  - `has_data`, `status` (draft, done, skipped)
  - `food_item_count`, `nutrient_value_count`
  - `source` (default `ui`)
  - `created_at`
- Purpose: track every human labeling action to feed model training.

**Migration Status**
- `apps/expert-annotator/run-migration.js` executed successfully against Supabase.
- Connection used: Supabase pooler session on port 5432.

**Crawler L2 Scoring (Current Logic)**
- Metadata rules in `crawler_v2.py` remain.
- Embedding similarity is an additional positive signal:
  - English anchor list and Turkish anchor list.
  - Accept if any anchor similarity >= its threshold.
- If `sentence-transformers` is not installed, the crawler logs `embed_unavailable` and uses rules only.

**Language Scope**
- English + Turkish only (in README and anchor list).
- Anchors for TR: "gida bilesimi", "besin bilesimi", "gida kompozisyonu", "besin kompozisyonu".

**Known Dependencies / Environment**
- No `requirements.txt` currently in repo.
- You must install `sentence-transformers` in your Python environment for embeddings.
- UI uses Supabase auth and tables.

**Running the Crawler (v2)**
- Entry: `services/data-pipeline/main.py`
- CLI: `services/data-pipeline/food_paper_crawler/cli_v2.py`
- Example:
  - `python3 services/data-pipeline/main.py --data-dir data --target-pdfs 12 --query-limit 50`

**Running the Annotator**
- `cd apps/expert-annotator`
- `npm install`
- `npm run dev`

**Where Secrets Live**
- `Keys and links` contains Supabase URLs, anon/service keys, DB strings, GitHub token.
- It is in `.gitignore` and should stay private.

**Untracked / Local Data**
- Multiple `services/data-pipeline/data/` run folders exist and are untracked.
- Keep them uncommitted.

**Current Backlog Ordering (Top Items)**
1. L2 multilingual embedding baseline (implemented)
2. L3 feedback loop from UI labels to crawler/L2 baseline
3. Safe test mode (needs to be early alongside labeling)
4. Global red “definitely no data” button
5. L2 classifier training (after labels exist)
6. Later: XLM-R fine-tuning

**Next Steps (Recommended)**
1. Ensure `sentence-transformers` is installed in the Python environment used for crawler runs.
2. Validate label events flow by saving a paper and checking `paper_label_events` in Supabase.
3. Build a simple export script to pull label events + paper text for training.
4. Implement L3 feedback loop to update query terms and anchor lists.
5. Add a safe test mode to avoid polluting production during UI testing.

**Commits of Note**
- `76215a9` Add dual embedding baseline for L2 metadata scoring.
- `8963173` Limit embedding anchors to EN+TR and document scope.
- `36eebe1` Log label events from annotator UI.

**Open Questions**
- Do we want language routing (English model only when detected EN), or always compute both?
- How should label exports be structured for first classifier training?
- How strict should embedding thresholds be before we start collecting labels?

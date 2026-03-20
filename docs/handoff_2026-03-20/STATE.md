# OpenNutri Handoff — 2026-03-20 (Europe/Istanbul)

This is a snapshot of the current state so work can continue elsewhere without losing context.

**Project Direction (Current)**
OpenNutri is building a paper-to-food-composition pipeline with a human labeling UI. The loop is:
1. Scrape + store candidate papers.
2. Apply L2 relevance filtering (rules + dual embeddings + anchors).
3. Collect human labels in the UI.
4. Feed labels back into query terms, filters, and embeddings. (Classifier training later.)

**Key Decisions / Policies**
- Repo stays private.
- L2 uses dual embeddings: English + multilingual; anchors are EN+TR only.
- Label events are recorded on every UI save (draft/done/skipped).
- Positive labels are optimistic: `has_data=true` draft or done counts as good immediately.
- Negatives require global skip or >=2 unique skips; conflicts are excluded from both sides.
- Global “definitely no data” is instant with a short undo window.
- Test mode disables all DB writes (local-only events).

**Recent Code Changes (High Signal)**
- UI test mode (no DB writes) with banner + toast.
- Global skip is instant (no prompt) + undo banner (10s window); reason stored as `quick_skip`.
- `paper_label_events` logging on every save (status, has_data, counts, source).
- New feedback term system (`feedback/update_terms.py`) that:
  - uses latest label per user,
  - treats draft/done as positive,
  - treats global skip or 2+ unique skips as negative,
  - excludes conflicts from training,
  - writes `feedback/latest.json`.
- Crawler consumes feedback terms to adjust queries/filters and embedding anchors.
- Auto-crawl script: `services/data-pipeline/scripts/ensure_paper_stock.py` (threshold-based).

**Data Model Notes**
- `paper_label_events`: per-save event log (paper_id, user_id, status, has_data, counts, source, created_at).
- `paper_global_labels`: global no-data labels with reason + user.
- Conflicts are **not** stored separately; they’re inferred from label events + global labels.

**Migration Status**
- `apps/expert-annotator/migration.sql` executed successfully against Supabase.
- Includes RLS policy to allow users to delete their own global labels (undo).

**DB Sanity Checks (as of 2026-03-20 11:23 UTC)**
- 3 “done” labels saved with annotations + food items + nutrient values.
- 3 global skips saved in `paper_global_labels` + `paper_label_events`.
- No conflicts detected yet.
- Found a count mismatch on paper 2: label event `food_item_count=0` but 1 food item exists.

**Known Issues / Risks**
- Label event counts can mismatch if a food item is empty (no name/FDC id).
- Git push is blocked on this machine (missing GitHub credentials).
- `sentence-transformers` must be installed for embeddings; no fallback desired.
- `feedback/latest.json` is generated locally and is untracked.

**How to Run Key Pieces**
- Feedback update:
  - `python3 services/data-pipeline/food_paper_crawler/feedback/update_terms.py`
  - Requires `SUPABASE_URL` (or `VITE_SUPABASE_URL`) + `SUPABASE_SERVICE_ROLE_KEY`.
- Auto-crawl when UI runs low on papers:
  - `python3 services/data-pipeline/scripts/ensure_paper_stock.py --threshold 0`

**Where Secrets Live**
- `Keys and links` contains Supabase URLs, anon/service keys, and DB strings.
- File is gitignored and must stay private.

**Untracked / Local Data**
- Multiple `services/data-pipeline/data/` run folders exist and are untracked.
- Local `__pycache__` and feedback outputs are untracked.

**Current Backlog Top Items**
1. Fix label event counts / prevent empty food items.
2. Conflict resolution workflow for labels.
3. Train and integrate L2 classifier.

**Open Questions**
- What is the conflict resolution workflow (review UI, admin queue, or batch rules)?
- How frequently should feedback updates run (after N labels vs scheduled)?
- Should we enforce a minimum valid food item before allowing “done”? 

-- Persistent storage for evidence-source dedup clusters per paper.
-- One row per paper. `clusters` maps each evidence groupKey to its canonical
-- regionKey + match metadata, so locations whose groupKeys share a regionKey
-- collapse into a single source on every load.

CREATE TABLE IF NOT EXISTS paper_evidence_dedup (
    paper_id INTEGER PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
    clusters JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE paper_evidence_dedup ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated can read paper_evidence_dedup" ON paper_evidence_dedup;
CREATE POLICY "Authenticated can read paper_evidence_dedup"
    ON paper_evidence_dedup FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS "Authenticated can insert paper_evidence_dedup" ON paper_evidence_dedup;
CREATE POLICY "Authenticated can insert paper_evidence_dedup"
    ON paper_evidence_dedup FOR INSERT
    TO authenticated
    WITH CHECK (true);

DROP POLICY IF EXISTS "Authenticated can update paper_evidence_dedup" ON paper_evidence_dedup;
CREATE POLICY "Authenticated can update paper_evidence_dedup"
    ON paper_evidence_dedup FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

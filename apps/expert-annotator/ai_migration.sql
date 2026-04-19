-- =============================================
-- OpenNutri AI Suggestions Table
-- =============================================

CREATE TABLE IF NOT EXISTS ai_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL DEFAULT 'gemini-3-flash-preview',
    is_useful BOOLEAN NOT NULL,
    reasoning TEXT,
    overall_confidence REAL,
    raw_data JSONB NOT NULL, -- The entire result JSON
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'applied', 'rejected')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookup by paper
CREATE INDEX IF NOT EXISTS idx_ai_extractions_paper ON ai_extractions(paper_id);
CREATE INDEX IF NOT EXISTS idx_ai_extractions_status ON ai_extractions(status);

-- RLS Policies
ALTER TABLE ai_extractions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "AI extractions readable by all authenticated users"
    ON ai_extractions FOR SELECT
    TO authenticated
    USING (true);

-- Allow service role to insert/update
CREATE POLICY "Service role full access ai_extractions"
    ON ai_extractions FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

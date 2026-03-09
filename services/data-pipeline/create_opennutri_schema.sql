-- =============================================
-- OpenNutri Universal Schema
-- Run this in Supabase SQL Editor
-- =============================================

-- 1. Entities (Canonical Foods)
CREATE TABLE IF NOT EXISTS entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name  TEXT NOT NULL UNIQUE,
    category        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Entity Aliases
CREATE TABLE IF NOT EXISTS entity_aliases (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias_name  TEXT NOT NULL,
    origin      TEXT
);

-- 3. Master Nutrients
CREATE TABLE IF NOT EXISTS master_nutrients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    standard_name   TEXT NOT NULL UNIQUE,
    description     TEXT
);

-- 4. Sources
CREATE TABLE IF NOT EXISTS sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type     TEXT NOT NULL,
    source_name     TEXT,
    reference_uri   TEXT,
    source_metadata JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Claims
CREATE TABLE IF NOT EXISTS claims (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    nutrient_id         UUID NOT NULL REFERENCES master_nutrients(id) ON DELETE CASCADE,
    source_id           UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    amount              REAL NOT NULL,
    unit                TEXT NOT NULL,
    basis               TEXT NOT NULL,
    preparation_state   TEXT NOT NULL,
    sample_size         INTEGER,
    confidence          REAL NOT NULL,
    extraction_method   TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active',
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- Indexes
-- =============================================
CREATE INDEX IF NOT EXISTS idx_claims_entity     ON claims(entity_id);
CREATE INDEX IF NOT EXISTS idx_claims_nutrient   ON claims(nutrient_id);
CREATE INDEX IF NOT EXISTS idx_claims_source     ON claims(source_id);
CREATE INDEX IF NOT EXISTS idx_claims_confidence ON claims(confidence);
CREATE INDEX IF NOT EXISTS idx_claims_status     ON claims(status);
CREATE INDEX IF NOT EXISTS idx_aliases_entity    ON entity_aliases(entity_id);
CREATE INDEX IF NOT EXISTS idx_aliases_name      ON entity_aliases(alias_name);
CREATE INDEX IF NOT EXISTS idx_entities_name     ON entities(canonical_name);

-- =============================================
-- RLS Policies (read-only for authenticated users)
-- =============================================
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE master_nutrients ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Entities readable by all" ON entities FOR SELECT TO authenticated USING (true);
CREATE POLICY "Aliases readable by all" ON entity_aliases FOR SELECT TO authenticated USING (true);
CREATE POLICY "Nutrients readable by all" ON master_nutrients FOR SELECT TO authenticated USING (true);
CREATE POLICY "Sources readable by all" ON sources FOR SELECT TO authenticated USING (true);
CREATE POLICY "Claims readable by all" ON claims FOR SELECT TO authenticated USING (true);

-- Allow service_role full access for ETL inserts
CREATE POLICY "Service role full access entities" ON entities FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access aliases" ON entity_aliases FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access nutrients" ON master_nutrients FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access sources" ON sources FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access claims" ON claims FOR ALL TO service_role USING (true) WITH CHECK (true);

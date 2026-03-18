-- =============================================
-- OpenNutri Annotator - Schema Migration
-- Aligns the annotator app with the SR Legacy-backed
-- `entities` / `master_nutrients` reference model.
-- =============================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =============================================
-- Reference data model
-- =============================================

CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL UNIQUE,
    category TEXT,
    source_dataset TEXT NOT NULL DEFAULT 'usda_sr_legacy',
    source_record_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias_name TEXT NOT NULL,
    origin TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(entity_id, alias_name)
);

CREATE TABLE IF NOT EXISTS master_nutrients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    standard_name TEXT NOT NULL UNIQUE,
    description TEXT,
    sort_rank REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    reference_uri TEXT,
    source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    nutrient_id UUID NOT NULL REFERENCES master_nutrients(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    amount REAL NOT NULL,
    unit TEXT NOT NULL,
    basis TEXT NOT NULL DEFAULT 'per_100g',
    preparation_state TEXT NOT NULL DEFAULT 'unspecified',
    sample_size INTEGER,
    confidence REAL NOT NULL DEFAULT 1.0,
    extraction_method TEXT NOT NULL DEFAULT 'ground_truth',
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE entities
    ADD COLUMN IF NOT EXISTS source_dataset TEXT NOT NULL DEFAULT 'usda_sr_legacy',
    ADD COLUMN IF NOT EXISTS source_record_id TEXT;

ALTER TABLE master_nutrients
    ADD COLUMN IF NOT EXISTS sort_rank REAL;

-- =============================================
-- Annotation model
-- =============================================

CREATE TABLE IF NOT EXISTS papers (
    id SERIAL PRIMARY KEY,
    title TEXT,
    doi TEXT,
    filename TEXT NOT NULL,
    ingest_status TEXT NOT NULL DEFAULT 'accepted',
    audit_flag BOOLEAN NOT NULL DEFAULT FALSE,
    rejection_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE papers
    ADD COLUMN IF NOT EXISTS ingest_status TEXT NOT NULL DEFAULT 'accepted',
    ADD COLUMN IF NOT EXISTS audit_flag BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS rejection_reasons JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS annotations (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    has_data BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'draft', 'done', 'skipped')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (paper_id, user_id)
);

CREATE TABLE IF NOT EXISTS food_items (
    id SERIAL PRIMARY KEY,
    annotation_id INTEGER NOT NULL REFERENCES annotations(id) ON DELETE CASCADE,
    food_name TEXT NOT NULL,
    food_fdc_id UUID REFERENCES entities(id),
    is_custom_food BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS annotation_nutrient_values (
    id SERIAL PRIMARY KEY,
    food_item_id INTEGER NOT NULL REFERENCES food_items(id) ON DELETE CASCADE,
    nutrient_id UUID REFERENCES master_nutrients(id),
    nutrient_name TEXT NOT NULL,
    value REAL,
    unit TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS search_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    search_type TEXT NOT NULL CHECK (search_type IN ('food', 'nutrient')),
    input_source TEXT NOT NULL DEFAULT 'typed'
        CHECK (input_source IN ('typed', 'text_selection')),
    status TEXT NOT NULL CHECK (status IN ('resolved', 'abandoned')),
    selected_option_id TEXT,
    selected_option_label TEXT,
    selected_option_type TEXT
        CHECK (selected_option_type IN ('food', 'nutrient', 'custom_food', 'custom_nutrient')),
    query_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Bring forward legacy `food_items` tables if they already exist with the wrong type/columns.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'food_items'
          AND column_name = 'food_fdc_id'
          AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE food_items
            DROP CONSTRAINT IF EXISTS food_items_food_fdc_id_fkey;

        ALTER TABLE food_items
            ALTER COLUMN food_fdc_id TYPE UUID
            USING NULL;

        ALTER TABLE food_items
            ADD CONSTRAINT food_items_food_fdc_id_fkey
            FOREIGN KEY (food_fdc_id) REFERENCES entities(id);
    END IF;
END $$;

ALTER TABLE food_items
    ADD COLUMN IF NOT EXISTS food_fdc_id UUID REFERENCES entities(id),
    ADD COLUMN IF NOT EXISTS is_custom_food BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE annotation_nutrient_values
    ADD COLUMN IF NOT EXISTS nutrient_id UUID REFERENCES master_nutrients(id),
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE food_items DROP COLUMN IF EXISTS moisture;
ALTER TABLE food_items DROP COLUMN IF EXISTS moisture_unit;
ALTER TABLE food_items DROP COLUMN IF EXISTS protein;
ALTER TABLE food_items DROP COLUMN IF EXISTS protein_unit;
ALTER TABLE food_items DROP COLUMN IF EXISTS fat;
ALTER TABLE food_items DROP COLUMN IF EXISTS fat_unit;
ALTER TABLE food_items DROP COLUMN IF EXISTS carbohydrate;
ALTER TABLE food_items DROP COLUMN IF EXISTS carbohydrate_unit;
ALTER TABLE food_items DROP COLUMN IF EXISTS ash;
ALTER TABLE food_items DROP COLUMN IF EXISTS ash_unit;
ALTER TABLE food_items DROP COLUMN IF EXISTS energy;
ALTER TABLE food_items DROP COLUMN IF EXISTS energy_unit;
ALTER TABLE food_items DROP COLUMN IF EXISTS fiber;
ALTER TABLE food_items DROP COLUMN IF EXISTS fiber_unit;

-- =============================================
-- Indexes
-- =============================================

CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_source_record_id ON entities(source_record_id);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_entity ON entity_aliases(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_name ON entity_aliases(alias_name);
CREATE INDEX IF NOT EXISTS idx_master_nutrients_name ON master_nutrients(standard_name);
CREATE INDEX IF NOT EXISTS idx_claims_entity ON claims(entity_id);
CREATE INDEX IF NOT EXISTS idx_claims_nutrient ON claims(nutrient_id);
CREATE INDEX IF NOT EXISTS idx_claims_source ON claims(source_id);
CREATE INDEX IF NOT EXISTS idx_annotations_paper_user ON annotations(paper_id, user_id);
CREATE INDEX IF NOT EXISTS idx_food_items_annotation ON food_items(annotation_id);
CREATE INDEX IF NOT EXISTS idx_nutrient_values_food_item ON annotation_nutrient_values(food_item_id);
CREATE INDEX IF NOT EXISTS idx_search_sessions_user_created ON search_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_sessions_type_created ON search_sessions(search_type, created_at DESC);

-- =============================================
-- Row Level Security
-- =============================================

ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE master_nutrients ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE annotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE food_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE annotation_nutrient_values ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_sessions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'entities'
          AND policyname = 'Authenticated users can read entities'
    ) THEN
        CREATE POLICY "Authenticated users can read entities"
            ON entities FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'entity_aliases'
          AND policyname = 'Authenticated users can read aliases'
    ) THEN
        CREATE POLICY "Authenticated users can read aliases"
            ON entity_aliases FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'master_nutrients'
          AND policyname = 'Authenticated users can read nutrients'
    ) THEN
        CREATE POLICY "Authenticated users can read nutrients"
            ON master_nutrients FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'sources'
          AND policyname = 'Authenticated users can read sources'
    ) THEN
        CREATE POLICY "Authenticated users can read sources"
            ON sources FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'claims'
          AND policyname = 'Authenticated users can read claims'
    ) THEN
        CREATE POLICY "Authenticated users can read claims"
            ON claims FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'papers'
          AND policyname = 'Authenticated users can read papers'
    ) THEN
        CREATE POLICY "Authenticated users can read papers"
            ON papers FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'annotations'
          AND policyname = 'Users can view their own annotations'
    ) THEN
        CREATE POLICY "Users can view their own annotations"
            ON annotations FOR SELECT TO authenticated
            USING (user_id = auth.uid());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'annotations'
          AND policyname = 'Users can insert their own annotations'
    ) THEN
        CREATE POLICY "Users can insert their own annotations"
            ON annotations FOR INSERT TO authenticated
            WITH CHECK (user_id = auth.uid());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'annotations'
          AND policyname = 'Users can update their own annotations'
    ) THEN
        CREATE POLICY "Users can update their own annotations"
            ON annotations FOR UPDATE TO authenticated
            USING (user_id = auth.uid());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'food_items'
          AND policyname = 'Users can view their own food items'
    ) THEN
        CREATE POLICY "Users can view their own food items"
            ON food_items FOR SELECT TO authenticated
            USING (
                annotation_id IN (
                    SELECT id FROM annotations WHERE user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'food_items'
          AND policyname = 'Users can insert their own food items'
    ) THEN
        CREATE POLICY "Users can insert their own food items"
            ON food_items FOR INSERT TO authenticated
            WITH CHECK (
                annotation_id IN (
                    SELECT id FROM annotations WHERE user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'food_items'
          AND policyname = 'Users can update their own food items'
    ) THEN
        CREATE POLICY "Users can update their own food items"
            ON food_items FOR UPDATE TO authenticated
            USING (
                annotation_id IN (
                    SELECT id FROM annotations WHERE user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'food_items'
          AND policyname = 'Users can delete their own food items'
    ) THEN
        CREATE POLICY "Users can delete their own food items"
            ON food_items FOR DELETE TO authenticated
            USING (
                annotation_id IN (
                    SELECT id FROM annotations WHERE user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'annotation_nutrient_values'
          AND policyname = 'Users can view their own nutrient values'
    ) THEN
        CREATE POLICY "Users can view their own nutrient values"
            ON annotation_nutrient_values FOR SELECT TO authenticated
            USING (
                food_item_id IN (
                    SELECT fi.id
                    FROM food_items fi
                    JOIN annotations a ON a.id = fi.annotation_id
                    WHERE a.user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'annotation_nutrient_values'
          AND policyname = 'Users can insert their own nutrient values'
    ) THEN
        CREATE POLICY "Users can insert their own nutrient values"
            ON annotation_nutrient_values FOR INSERT TO authenticated
            WITH CHECK (
                food_item_id IN (
                    SELECT fi.id
                    FROM food_items fi
                    JOIN annotations a ON a.id = fi.annotation_id
                    WHERE a.user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'annotation_nutrient_values'
          AND policyname = 'Users can update their own nutrient values'
    ) THEN
        CREATE POLICY "Users can update their own nutrient values"
            ON annotation_nutrient_values FOR UPDATE TO authenticated
            USING (
                food_item_id IN (
                    SELECT fi.id
                    FROM food_items fi
                    JOIN annotations a ON a.id = fi.annotation_id
                    WHERE a.user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'annotation_nutrient_values'
          AND policyname = 'Users can delete their own nutrient values'
    ) THEN
        CREATE POLICY "Users can delete their own nutrient values"
            ON annotation_nutrient_values FOR DELETE TO authenticated
            USING (
                food_item_id IN (
                    SELECT fi.id
                    FROM food_items fi
                    JOIN annotations a ON a.id = fi.annotation_id
                    WHERE a.user_id = auth.uid()
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'search_sessions'
          AND policyname = 'Users can view their own search sessions'
    ) THEN
        CREATE POLICY "Users can view their own search sessions"
            ON search_sessions FOR SELECT TO authenticated
            USING (user_id = auth.uid());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'search_sessions'
          AND policyname = 'Users can insert their own search sessions'
    ) THEN
        CREATE POLICY "Users can insert their own search sessions"
            ON search_sessions FOR INSERT TO authenticated
            WITH CHECK (user_id = auth.uid());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'entities'
          AND policyname = 'Service role full access entities'
    ) THEN
        CREATE POLICY "Service role full access entities"
            ON entities FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'entity_aliases'
          AND policyname = 'Service role full access aliases'
    ) THEN
        CREATE POLICY "Service role full access aliases"
            ON entity_aliases FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'master_nutrients'
          AND policyname = 'Service role full access nutrients'
    ) THEN
        CREATE POLICY "Service role full access nutrients"
            ON master_nutrients FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'sources'
          AND policyname = 'Service role full access sources'
    ) THEN
        CREATE POLICY "Service role full access sources"
            ON sources FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'search_sessions'
          AND policyname = 'Service role full access search sessions'
    ) THEN
        CREATE POLICY "Service role full access search sessions"
            ON search_sessions FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'claims'
          AND policyname = 'Service role full access claims'
    ) THEN
        CREATE POLICY "Service role full access claims"
            ON claims FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

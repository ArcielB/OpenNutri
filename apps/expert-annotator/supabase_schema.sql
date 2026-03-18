-- =============================================
-- OpenNutri Annotation Tool — Supabase Schema
-- Run this in your Supabase SQL Editor
-- =============================================

-- 1. Papers table
CREATE TABLE papers (
    id SERIAL PRIMARY KEY,
    title TEXT,
    doi TEXT,
    filename TEXT NOT NULL,
    ingest_status TEXT NOT NULL DEFAULT 'accepted',
    audit_flag BOOLEAN NOT NULL DEFAULT FALSE,
    rejection_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Annotations table (one per paper per user)
CREATE TABLE annotations (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    has_data BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'draft', 'done', 'skipped')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(paper_id, user_id)
);

-- 3. Food items table (multiple per annotation)
CREATE TABLE food_items (
    id SERIAL PRIMARY KEY,
    annotation_id INTEGER NOT NULL REFERENCES annotations(id) ON DELETE CASCADE,
    food_name TEXT NOT NULL,
    moisture REAL,
    moisture_unit TEXT DEFAULT 'g/100g',
    protein REAL,
    protein_unit TEXT DEFAULT 'g/100g',
    fat REAL,
    fat_unit TEXT DEFAULT 'g/100g',
    carbohydrate REAL,
    carbohydrate_unit TEXT DEFAULT 'g/100g',
    ash REAL,
    ash_unit TEXT DEFAULT 'g/100g',
    energy REAL,
    energy_unit TEXT DEFAULT 'kcal/100g',
    fiber REAL,
    fiber_unit TEXT DEFAULT 'g/100g'
);

-- =============================================
-- Row Level Security (RLS)
-- Each annotator can only see/edit their own annotations
-- =============================================

ALTER TABLE papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE annotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE food_items ENABLE ROW LEVEL SECURITY;

-- Papers: everyone can read
CREATE POLICY "Papers are viewable by all authenticated users"
    ON papers FOR SELECT
    TO authenticated
    USING (true);

-- Annotations: users can only see/edit their own
CREATE POLICY "Users can view their own annotations"
    ON annotations FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert their own annotations"
    ON annotations FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update their own annotations"
    ON annotations FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid());

-- Food items: users can manage items belonging to their annotations
CREATE POLICY "Users can view their own food items"
    ON food_items FOR SELECT
    TO authenticated
    USING (
        annotation_id IN (
            SELECT id FROM annotations WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert their own food items"
    ON food_items FOR INSERT
    TO authenticated
    WITH CHECK (
        annotation_id IN (
            SELECT id FROM annotations WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete their own food items"
    ON food_items FOR DELETE
    TO authenticated
    USING (
        annotation_id IN (
            SELECT id FROM annotations WHERE user_id = auth.uid()
        )
    );

-- =============================================
-- Indexes for performance
-- =============================================
CREATE INDEX idx_annotations_paper_user ON annotations(paper_id, user_id);
CREATE INDEX idx_food_items_annotation ON food_items(annotation_id);

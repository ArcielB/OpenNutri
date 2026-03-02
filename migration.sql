-- =============================================
-- OpenNutri Annotator — Schema Migration
-- Run this in your Supabase SQL Editor
-- =============================================

-- 1. Create the new EAV table for nutrient values
CREATE TABLE annotation_nutrient_values (
    id SERIAL PRIMARY KEY,
    food_item_id INTEGER NOT NULL REFERENCES food_items(id) ON DELETE CASCADE,
    nutrient_id BIGINT REFERENCES nutrients(id),
    nutrient_name TEXT NOT NULL,
    value REAL,
    unit TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Add new columns to food_items
ALTER TABLE food_items ADD COLUMN food_fdc_id BIGINT REFERENCES foods(fdc_id);
ALTER TABLE food_items ADD COLUMN is_custom_food BOOLEAN DEFAULT false;

-- 3. Drop the 7 hardcoded nutrient columns from food_items
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

-- 4. RLS for annotation_nutrient_values
ALTER TABLE annotation_nutrient_values ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own nutrient values"
    ON annotation_nutrient_values FOR SELECT
    TO authenticated
    USING (
        food_item_id IN (
            SELECT fi.id FROM food_items fi
            JOIN annotations a ON fi.annotation_id = a.id
            WHERE a.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert their own nutrient values"
    ON annotation_nutrient_values FOR INSERT
    TO authenticated
    WITH CHECK (
        food_item_id IN (
            SELECT fi.id FROM food_items fi
            JOIN annotations a ON fi.annotation_id = a.id
            WHERE a.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update their own nutrient values"
    ON annotation_nutrient_values FOR UPDATE
    TO authenticated
    USING (
        food_item_id IN (
            SELECT fi.id FROM food_items fi
            JOIN annotations a ON fi.annotation_id = a.id
            WHERE a.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete their own nutrient values"
    ON annotation_nutrient_values FOR DELETE
    TO authenticated
    USING (
        food_item_id IN (
            SELECT fi.id FROM food_items fi
            JOIN annotations a ON fi.annotation_id = a.id
            WHERE a.user_id = auth.uid()
        )
    );

-- 5. Index for performance
CREATE INDEX idx_nutrient_values_food_item ON annotation_nutrient_values(food_item_id);

-- 6. Allow authenticated users to read nutrients and foods tables (for autocomplete)
-- (Check if these policies already exist; skip if they do)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'nutrients' AND policyname = 'Nutrients are readable by authenticated users'
    ) THEN
        EXECUTE 'CREATE POLICY "Nutrients are readable by authenticated users" ON nutrients FOR SELECT TO authenticated USING (true)';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'foods' AND policyname = 'Foods are readable by authenticated users'
    ) THEN
        EXECUTE 'CREATE POLICY "Foods are readable by authenticated users" ON foods FOR SELECT TO authenticated USING (true)';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'food_category' AND policyname = 'Food categories are readable by authenticated users'
    ) THEN
        EXECUTE 'CREATE POLICY "Food categories are readable by authenticated users" ON food_category FOR SELECT TO authenticated USING (true)';
    END IF;
END $$;

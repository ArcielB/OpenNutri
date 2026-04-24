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
    abstract TEXT,
    doi TEXT,
    canonical_key TEXT,
    filename TEXT NOT NULL,
    source TEXT,
    source_record_id TEXT,
    workflow_language TEXT
        CHECK (workflow_language IN ('en', 'tr')),
    search_gate_score REAL,
    filter_score REAL,
    ingest_status TEXT NOT NULL DEFAULT 'accepted',
    audit_flag BOOLEAN NOT NULL DEFAULT FALSE,
    rejection_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE papers
    ADD COLUMN IF NOT EXISTS abstract TEXT,
    ADD COLUMN IF NOT EXISTS canonical_key TEXT,
    ADD COLUMN IF NOT EXISTS source TEXT,
    ADD COLUMN IF NOT EXISTS source_record_id TEXT,
    ADD COLUMN IF NOT EXISTS workflow_language TEXT
        CHECK (workflow_language IN ('en', 'tr')),
    ADD COLUMN IF NOT EXISTS search_gate_score REAL,
    ADD COLUMN IF NOT EXISTS filter_score REAL,
    ADD COLUMN IF NOT EXISTS ingest_status TEXT NOT NULL DEFAULT 'accepted',
    ADD COLUMN IF NOT EXISTS audit_flag BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS rejection_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS current_stage_key TEXT,
    ADD COLUMN IF NOT EXISTS routing_status TEXT,
    ADD COLUMN IF NOT EXISTS routing_bucket TEXT,
    ADD COLUMN IF NOT EXISTS route_destination TEXT,
    ADD COLUMN IF NOT EXISTS latest_ai_extraction_id UUID,
    ADD COLUMN IF NOT EXISTS routing_updated_at TIMESTAMPTZ;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'papers'
          AND constraint_name = 'papers_routing_status_check'
    ) THEN
        ALTER TABLE papers
            DROP CONSTRAINT papers_routing_status_check;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'papers'
          AND constraint_name = 'papers_routing_bucket_check'
    ) THEN
        ALTER TABLE papers
            DROP CONSTRAINT papers_routing_bucket_check;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'papers'
          AND constraint_name = 'papers_route_destination_check'
    ) THEN
        ALTER TABLE papers
            DROP CONSTRAINT papers_route_destination_check;
    END IF;
END $$;

ALTER TABLE papers
    ADD CONSTRAINT papers_routing_status_check
    CHECK (
        routing_status IS NULL
        OR routing_status IN (
            'queued_for_ai',
            'ai_processing',
            'ai_failed',
            'human_review_ready',
            'ai_finalized_has_data',
            'ai_finalized_no_usable_data'
        )
    );

ALTER TABLE papers
    ADD CONSTRAINT papers_routing_bucket_check
    CHECK (
        routing_bucket IS NULL
        OR routing_bucket IN (
            'high_confidence_has_data',
            'high_confidence_no_usable_data',
            'low_confidence_has_data',
            'low_confidence_no_usable_data'
        )
    );

ALTER TABLE papers
    ADD CONSTRAINT papers_route_destination_check
    CHECK (
        route_destination IS NULL
        OR route_destination IN ('human_review', 'finalized', 'blocked')
    );

CREATE TABLE IF NOT EXISTS paper_search_hits (
    id BIGSERIAL PRIMARY KEY,
    paper_id INTEGER REFERENCES papers(id) ON DELETE SET NULL,
    hit_key TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    source TEXT NOT NULL,
    source_record_id TEXT,
    external_id TEXT,
    pmcid TEXT,
    doi TEXT,
    title TEXT,
    abstract TEXT,
    workflow_language TEXT NOT NULL
        CHECK (workflow_language IN ('en', 'tr')),
    query_text TEXT NOT NULL,
    template_id TEXT NOT NULL,
    source_term TEXT,
    term_type TEXT NOT NULL,
    query_phrase TEXT,
    search_gate_score REAL NOT NULL DEFAULT 0,
    search_gate_pass BOOLEAN NOT NULL DEFAULT FALSE,
    filter_score REAL,
    filter_pass BOOLEAN,
    is_duplicate BOOLEAN NOT NULL DEFAULT FALSE,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE paper_search_hits
    ADD COLUMN IF NOT EXISTS hit_key TEXT;

UPDATE paper_search_hits
SET hit_key = md5(
    regexp_replace(lower(trim(coalesce(canonical_key, ''))), '\s+', ' ', 'g') || '|' ||
    regexp_replace(lower(trim(coalesce(source, ''))), '\s+', ' ', 'g') || '|' ||
    regexp_replace(lower(trim(coalesce(workflow_language, ''))), '\s+', ' ', 'g') || '|' ||
    regexp_replace(lower(trim(coalesce(template_id, ''))), '\s+', ' ', 'g') || '|' ||
    regexp_replace(lower(trim(coalesce(source_term, ''))), '\s+', ' ', 'g') || '|' ||
    regexp_replace(lower(trim(coalesce(query_phrase, ''))), '\s+', ' ', 'g') || '|' ||
    regexp_replace(lower(trim(coalesce(query_text, ''))), '\s+', ' ', 'g')
)
WHERE hit_key IS NULL OR hit_key = '';

DELETE FROM paper_search_hits
WHERE id IN (
    SELECT id
    FROM (
        SELECT
            id,
            ROW_NUMBER() OVER (PARTITION BY hit_key ORDER BY id) AS row_num
        FROM paper_search_hits
        WHERE hit_key IS NOT NULL AND hit_key <> ''
    ) ranked
    WHERE row_num > 1
);

ALTER TABLE paper_search_hits
    ALTER COLUMN hit_key SET NOT NULL;

CREATE TABLE IF NOT EXISTS paper_search_batches (
    batch_id TEXT PRIMARY KEY,
    batch_key TEXT NOT NULL,
    run_id TEXT NOT NULL,
    batch_rank INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    workflow_language TEXT NOT NULL
        CHECK (workflow_language IN ('en', 'tr')),
    query_text TEXT NOT NULL,
    template_id TEXT NOT NULL,
    source_term TEXT,
    term_type TEXT NOT NULL,
    query_phrase TEXT,
    query_limit INTEGER NOT NULL DEFAULT 0,
    results INTEGER NOT NULL DEFAULT 0,
    search_gate_passed INTEGER NOT NULL DEFAULT 0,
    search_gate_rejected INTEGER NOT NULL DEFAULT 0,
    filter_passed INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    skipped_seen INTEGER NOT NULL DEFAULT 0,
    accepted INTEGER NOT NULL DEFAULT 0,
    metadata_rejected INTEGER NOT NULL DEFAULT 0,
    pdf_fetch_fail INTEGER NOT NULL DEFAULT 0,
    pdf_validation_fail INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_search_batch_hits (
    batch_id TEXT NOT NULL REFERENCES paper_search_batches(batch_id) ON DELETE CASCADE,
    hit_key TEXT NOT NULL REFERENCES paper_search_hits(hit_key) ON DELETE CASCADE,
    result_rank INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (batch_id, hit_key)
);

INSERT INTO paper_search_batches (
    batch_id,
    batch_key,
    run_id,
    batch_rank,
    source,
    workflow_language,
    query_text,
    template_id,
    source_term,
    term_type,
    query_phrase,
    query_limit,
    results,
    search_gate_passed,
    search_gate_rejected,
    filter_passed,
    duplicates,
    skipped_seen,
    accepted,
    metadata_rejected,
    pdf_fetch_fail,
    pdf_validation_fail
)
SELECT
    'legacy:' || md5(
        regexp_replace(lower(trim(coalesce(source, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(workflow_language, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(template_id, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(source_term, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(query_phrase, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(query_text, ''))), '\s+', ' ', 'g')
    ) AS batch_id,
    md5(
        regexp_replace(lower(trim(coalesce(source, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(workflow_language, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(template_id, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(source_term, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(query_phrase, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(query_text, ''))), '\s+', ' ', 'g')
    ) AS batch_key,
    'legacy' AS run_id,
    0 AS batch_rank,
    source,
    workflow_language,
    query_text,
    template_id,
    source_term,
    term_type,
    query_phrase,
    GREATEST(COUNT(*), 1)::INTEGER AS query_limit,
    COUNT(*)::INTEGER AS results,
    COUNT(*) FILTER (WHERE search_gate_pass IS TRUE)::INTEGER AS search_gate_passed,
    COUNT(*) FILTER (WHERE search_gate_pass IS FALSE)::INTEGER AS search_gate_rejected,
    COUNT(*) FILTER (WHERE filter_pass IS TRUE)::INTEGER AS filter_passed,
    COUNT(*) FILTER (WHERE is_duplicate IS TRUE)::INTEGER AS duplicates,
    0 AS skipped_seen,
    0 AS accepted,
    COUNT(*) FILTER (WHERE search_gate_pass IS TRUE AND COALESCE(filter_pass, FALSE) IS FALSE)::INTEGER AS metadata_rejected,
    0 AS pdf_fetch_fail,
    0 AS pdf_validation_fail
FROM paper_search_hits
GROUP BY
    source,
    workflow_language,
    query_text,
    template_id,
    source_term,
    term_type,
    query_phrase
ON CONFLICT (batch_id) DO NOTHING;

INSERT INTO paper_search_batch_hits (batch_id, hit_key, result_rank)
SELECT
    'legacy:' || md5(
        regexp_replace(lower(trim(coalesce(source, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(workflow_language, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(template_id, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(source_term, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(query_phrase, ''))), '\s+', ' ', 'g') || '|' ||
        regexp_replace(lower(trim(coalesce(query_text, ''))), '\s+', ' ', 'g')
    ) AS batch_id,
    hit_key,
    NULL::INTEGER AS result_rank
FROM paper_search_hits
WHERE hit_key IS NOT NULL AND hit_key <> ''
ON CONFLICT (batch_id, hit_key) DO NOTHING;

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

CREATE TABLE IF NOT EXISTS paper_label_events (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    annotation_id INTEGER REFERENCES annotations(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    has_data BOOLEAN NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'done', 'skipped')),
    food_item_count INTEGER NOT NULL DEFAULT 0,
    nutrient_value_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'ui',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_global_labels (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    label TEXT NOT NULL CHECK (label IN ('definitely_no_data')),
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (paper_id, label)
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

CREATE TABLE IF NOT EXISTS backlog_review_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_kind TEXT NOT NULL DEFAULT 'suggestion_review'
        CHECK (item_kind IN ('suggestion_review')),
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'triaged', 'planned', 'dismissed', 'done')),
    submitted_by_auth_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    submitted_by_email TEXT,
    submitted_by_name TEXT,
    suggestion_text TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
    follow_up_required BOOLEAN NOT NULL DEFAULT FALSE,
    follow_up_note TEXT,
    review_note TEXT,
    reviewed_by_auth_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

-- =============================================
-- Assignment-driven reviewer workflow
-- =============================================

CREATE TABLE IF NOT EXISTS reviewer_slots (
    slot_key TEXT PRIMARY KEY
        CHECK (slot_key IN ('arciel', 'peri', 'aleyna')),
    display_name TEXT NOT NULL,
    is_official BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reviewer_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE,
    auth_user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
    display_name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    can_review_en BOOLEAN NOT NULL DEFAULT TRUE,
    can_review_tr BOOLEAN NOT NULL DEFAULT TRUE,
    tester_access BOOLEAN NOT NULL DEFAULT FALSE,
    official_slot TEXT REFERENCES reviewer_slots(slot_key) ON DELETE SET NULL,
    cockpit_access BOOLEAN NOT NULL DEFAULT FALSE,
    priority_weight_en REAL NOT NULL DEFAULT 1.0,
    priority_weight_tr REAL NOT NULL DEFAULT 1.0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE reviewer_profiles
    ADD COLUMN IF NOT EXISTS tester_access BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS reviewer_slot_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slot_key TEXT NOT NULL REFERENCES reviewer_slots(slot_key) ON DELETE CASCADE,
    reviewer_profile_id UUID NOT NULL REFERENCES reviewer_profiles(id) ON DELETE CASCADE,
    member_role TEXT NOT NULL
        CHECK (member_role IN ('primary', 'shadow')),
    can_review_en BOOLEAN NOT NULL DEFAULT TRUE,
    can_review_tr BOOLEAN NOT NULL DEFAULT TRUE,
    counts_toward_official BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (slot_key, reviewer_profile_id)
);

CREATE TABLE IF NOT EXISTS paper_slot_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    slot_key TEXT NOT NULL REFERENCES reviewer_slots(slot_key) ON DELETE RESTRICT,
    workflow_language TEXT NOT NULL
        CHECK (workflow_language IN ('en', 'tr')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'submitted', 'conflict', 'resolved', 'cancelled')),
    official_submission_id UUID,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (paper_id, slot_key)
);

CREATE TABLE IF NOT EXISTS paper_user_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_slot_assignment_id UUID NOT NULL REFERENCES paper_slot_assignments(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    reviewer_profile_id UUID NOT NULL REFERENCES reviewer_profiles(id) ON DELETE RESTRICT,
    auth_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    workflow_language TEXT NOT NULL
        CHECK (workflow_language IN ('en', 'tr')),
    status TEXT NOT NULL DEFAULT 'assigned'
        CHECK (status IN ('assigned', 'draft', 'submitted', 'conflict', 'resolved', 'cancelled')),
    last_annotation_id INTEGER,
    latest_submission_id UUID,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_saved_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (paper_slot_assignment_id, reviewer_profile_id)
);

CREATE TABLE IF NOT EXISTS paper_assignment_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_user_assignment_id UUID NOT NULL REFERENCES paper_user_assignments(id) ON DELETE CASCADE,
    paper_slot_assignment_id UUID NOT NULL REFERENCES paper_slot_assignments(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    reviewer_profile_id UUID NOT NULL REFERENCES reviewer_profiles(id) ON DELETE RESTRICT,
    auth_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    annotation_id INTEGER REFERENCES annotations(id) ON DELETE SET NULL,
    decision_kind TEXT NOT NULL
        CHECK (decision_kind IN ('has_data', 'no_usable_data')),
    payload_json JSONB NOT NULL,
    payload_text TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    submission_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    conflict_type TEXT NOT NULL
        CHECK (conflict_type IN ('internal_slot_conflict', 'external_slot_conflict')),
    slot_key TEXT REFERENCES reviewer_slots(slot_key) ON DELETE SET NULL,
    left_submission_id UUID NOT NULL REFERENCES paper_assignment_submissions(id) ON DELETE CASCADE,
    right_submission_id UUID NOT NULL REFERENCES paper_assignment_submissions(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'resolved', 'cancelled')),
    resolved_submission_id UUID REFERENCES paper_assignment_submissions(id) ON DELETE SET NULL,
    resolution_note TEXT,
    resolved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS paper_review_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id INTEGER NOT NULL UNIQUE REFERENCES papers(id) ON DELETE CASCADE,
    decision_kind TEXT NOT NULL
        CHECK (decision_kind IN ('has_data', 'no_usable_data')),
    resolution_source TEXT NOT NULL
        CHECK (resolution_source IN ('slot_agreement', 'conflict_resolution', 'global_skip')),
    payload_json JSONB NOT NULL,
    payload_text TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    slot_submission_a_id UUID REFERENCES paper_assignment_submissions(id) ON DELETE SET NULL,
    slot_submission_b_id UUID REFERENCES paper_assignment_submissions(id) ON DELETE SET NULL,
    resolved_submission_id UUID REFERENCES paper_assignment_submissions(id) ON DELETE SET NULL,
    conflict_id UUID REFERENCES paper_conflicts(id) ON DELETE SET NULL,
    resolved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- AI extraction storage (Gemini blind-study path)
-- =============================================

CREATE TABLE IF NOT EXISTS ai_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL DEFAULT 'gemini-3-flash-preview',
    is_useful BOOLEAN NOT NULL,
    reasoning TEXT,
    overall_confidence REAL,
    raw_data JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'applied', 'rejected')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_extractions_paper ON ai_extractions(paper_id);
CREATE INDEX IF NOT EXISTS idx_ai_extractions_status ON ai_extractions(status);

ALTER TABLE ai_extractions
    ADD COLUMN IF NOT EXISTS stage_key TEXT,
    ADD COLUMN IF NOT EXISTS prompt_version TEXT,
    ADD COLUMN IF NOT EXISTS input_hash TEXT,
    ADD COLUMN IF NOT EXISTS normalized_payload_json JSONB,
    ADD COLUMN IF NOT EXISTS positive_threshold_snapshot REAL,
    ADD COLUMN IF NOT EXISTS negative_threshold_snapshot REAL,
    ADD COLUMN IF NOT EXISTS routing_bucket TEXT,
    ADD COLUMN IF NOT EXISTS route_destination TEXT,
    ADD COLUMN IF NOT EXISTS audit_sampled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS finalized_without_human BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'ai_extractions'
          AND constraint_name = 'ai_extractions_routing_bucket_check'
    ) THEN
        ALTER TABLE ai_extractions
            DROP CONSTRAINT ai_extractions_routing_bucket_check;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'ai_extractions'
          AND constraint_name = 'ai_extractions_route_destination_check'
    ) THEN
        ALTER TABLE ai_extractions
            DROP CONSTRAINT ai_extractions_route_destination_check;
    END IF;
END $$;

ALTER TABLE ai_extractions
    ADD CONSTRAINT ai_extractions_routing_bucket_check
    CHECK (
        routing_bucket IS NULL
        OR routing_bucket IN (
            'high_confidence_has_data',
            'high_confidence_no_usable_data',
            'low_confidence_has_data',
            'low_confidence_no_usable_data'
        )
    );

ALTER TABLE ai_extractions
    ADD CONSTRAINT ai_extractions_route_destination_check
    CHECK (
        route_destination IS NULL
        OR route_destination IN ('human_review', 'finalized', 'blocked')
    );

CREATE TABLE IF NOT EXISTS routing_stage_configs (
    stage_key TEXT PRIMARY KEY,
    stage_kind TEXT NOT NULL
        CHECK (stage_kind IN ('ai_model')),
    display_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    positive_threshold REAL NOT NULL DEFAULT 1.0
        CHECK (positive_threshold >= 0 AND positive_threshold <= 1),
    negative_threshold REAL NOT NULL DEFAULT 1.0
        CHECK (negative_threshold >= 0 AND negative_threshold <= 1),
    audit_rate REAL NOT NULL DEFAULT 0.05
        CHECK (audit_rate >= 0 AND audit_rate <= 1),
    next_stage_on_low_confidence TEXT NOT NULL DEFAULT 'human_review',
    counts_as_truth BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_stage_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    stage_key TEXT NOT NULL REFERENCES routing_stage_configs(stage_key) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (paper_id, stage_key)
);

INSERT INTO routing_stage_configs (
    stage_key,
    stage_kind,
    display_name,
    model_name,
    prompt_version,
    active,
    positive_threshold,
    negative_threshold,
    audit_rate,
    next_stage_on_low_confidence,
    counts_as_truth
)
VALUES (
    'gemini_flash_triage_v1',
    'ai_model',
    'Gemini Flash Triage v1',
    'gemini-3-flash-preview',
    'gemini_flash_triage_v1',
    TRUE,
    1.0,
    1.0,
    0.05,
    'human_review',
    FALSE
)
ON CONFLICT (stage_key) DO UPDATE
SET
    stage_kind = EXCLUDED.stage_kind,
    display_name = EXCLUDED.display_name,
    model_name = EXCLUDED.model_name,
    prompt_version = EXCLUDED.prompt_version;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'papers'
          AND constraint_name = 'papers_latest_ai_extraction_id_fkey'
    ) THEN
        ALTER TABLE papers
            ADD CONSTRAINT papers_latest_ai_extraction_id_fkey
            FOREIGN KEY (latest_ai_extraction_id) REFERENCES ai_extractions(id) ON DELETE SET NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'paper_slot_assignments'
          AND constraint_name = 'paper_slot_assignments_official_submission_id_fkey'
    ) THEN
        ALTER TABLE paper_slot_assignments
            ADD CONSTRAINT paper_slot_assignments_official_submission_id_fkey
            FOREIGN KEY (official_submission_id) REFERENCES paper_assignment_submissions(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'paper_user_assignments'
          AND constraint_name = 'paper_user_assignments_last_annotation_id_fkey'
    ) THEN
        ALTER TABLE paper_user_assignments
            ADD CONSTRAINT paper_user_assignments_last_annotation_id_fkey
            FOREIGN KEY (last_annotation_id) REFERENCES annotations(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'paper_user_assignments'
          AND constraint_name = 'paper_user_assignments_latest_submission_id_fkey'
    ) THEN
        ALTER TABLE paper_user_assignments
            ADD CONSTRAINT paper_user_assignments_latest_submission_id_fkey
            FOREIGN KEY (latest_submission_id) REFERENCES paper_assignment_submissions(id) ON DELETE SET NULL;
    END IF;
END $$;

ALTER TABLE annotations
    ADD COLUMN IF NOT EXISTS paper_user_assignment_id UUID REFERENCES paper_user_assignments(id) ON DELETE SET NULL;

ALTER TABLE paper_global_labels
    ADD COLUMN IF NOT EXISTS paper_user_assignment_id UUID REFERENCES paper_user_assignments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS paper_slot_assignment_id UUID REFERENCES paper_slot_assignments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS reviewer_profile_id UUID REFERENCES reviewer_profiles(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS slot_key TEXT REFERENCES reviewer_slots(slot_key) ON DELETE SET NULL;

ALTER TABLE paper_label_events
    ADD COLUMN IF NOT EXISTS paper_user_assignment_id UUID REFERENCES paper_user_assignments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS paper_slot_assignment_id UUID REFERENCES paper_slot_assignments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS decision_kind TEXT
        CHECK (decision_kind IN ('has_data', 'no_usable_data'));

ALTER TABLE paper_review_outcomes
    ADD COLUMN IF NOT EXISTS truth_source_kind TEXT NOT NULL DEFAULT 'human_review',
    ADD COLUMN IF NOT EXISTS source_stage_key TEXT,
    ADD COLUMN IF NOT EXISTS source_model_name TEXT,
    ADD COLUMN IF NOT EXISTS source_confidence REAL,
    ADD COLUMN IF NOT EXISTS training_weight REAL DEFAULT 1.0;

UPDATE paper_review_outcomes
SET training_weight = 1.0
WHERE training_weight IS NULL
  AND truth_source_kind = 'human_review';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'paper_review_outcomes'
          AND constraint_name = 'paper_review_outcomes_resolution_source_check'
    ) THEN
        ALTER TABLE paper_review_outcomes
            DROP CONSTRAINT paper_review_outcomes_resolution_source_check;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'paper_review_outcomes'
          AND constraint_name = 'paper_review_outcomes_truth_source_kind_check'
    ) THEN
        ALTER TABLE paper_review_outcomes
            DROP CONSTRAINT paper_review_outcomes_truth_source_kind_check;
    END IF;
END $$;

ALTER TABLE paper_review_outcomes
    ADD CONSTRAINT paper_review_outcomes_resolution_source_check
    CHECK (resolution_source IN ('slot_agreement', 'conflict_resolution', 'global_skip', 'ai_high_confidence'));

ALTER TABLE paper_review_outcomes
    ADD CONSTRAINT paper_review_outcomes_truth_source_kind_check
    CHECK (truth_source_kind IN ('human_review', 'ai_model'));

INSERT INTO reviewer_slots (slot_key, display_name, is_official)
VALUES
    ('arciel', 'Arciel Lane', TRUE),
    ('peri', 'Peri', TRUE),
    ('aleyna', 'Aleyna', TRUE)
ON CONFLICT (slot_key) DO UPDATE
SET
    display_name = EXCLUDED.display_name,
    is_official = EXCLUDED.is_official;

INSERT INTO reviewer_profiles (
    email,
    display_name,
    active,
    can_review_en,
    can_review_tr,
    official_slot,
    cockpit_access,
    priority_weight_en,
    priority_weight_tr
)
SELECT
    lower(trim(email)),
    CASE lower(trim(email))
        WHEN 'baezarciel@gmail.com' THEN 'Arciel'
        WHEN 'periacikgoz22@gmail.com' THEN 'Peri'
        WHEN 'ozcnaleyna2@gmail.com' THEN 'Aleyna'
        ELSE split_part(lower(trim(email)), '@', 1)
    END,
    TRUE,
    TRUE,
    TRUE,
    CASE lower(trim(email))
        WHEN 'baezarciel@gmail.com' THEN 'arciel'
        WHEN 'periacikgoz22@gmail.com' THEN 'peri'
        WHEN 'ozcnaleyna2@gmail.com' THEN 'aleyna'
        ELSE NULL
    END,
    CASE lower(trim(email))
        WHEN 'baezarciel@gmail.com' THEN TRUE
        ELSE FALSE
    END,
    CASE lower(trim(email))
        WHEN 'baezarciel@gmail.com' THEN 1.35
        ELSE 1.0
    END,
    CASE lower(trim(email))
        WHEN 'periacikgoz22@gmail.com' THEN 1.3
        WHEN 'ozcnaleyna2@gmail.com' THEN 1.3
        ELSE 1.0
    END
FROM allowed_auth_emails
ON CONFLICT (email) DO UPDATE
SET
    display_name = COALESCE(EXCLUDED.display_name, reviewer_profiles.display_name),
    active = EXCLUDED.active,
    can_review_en = EXCLUDED.can_review_en,
    can_review_tr = EXCLUDED.can_review_tr,
    official_slot = COALESCE(EXCLUDED.official_slot, reviewer_profiles.official_slot),
    cockpit_access = reviewer_profiles.cockpit_access OR EXCLUDED.cockpit_access,
    priority_weight_en = EXCLUDED.priority_weight_en,
    priority_weight_tr = EXCLUDED.priority_weight_tr,
    updated_at = NOW();

INSERT INTO reviewer_slot_members (
    slot_key,
    reviewer_profile_id,
    member_role,
    can_review_en,
    can_review_tr,
    counts_toward_official,
    active
)
SELECT
    reviewer_profiles.official_slot,
    reviewer_profiles.id,
    'primary',
    reviewer_profiles.can_review_en,
    reviewer_profiles.can_review_tr,
    TRUE,
    reviewer_profiles.active
FROM reviewer_profiles
WHERE reviewer_profiles.official_slot IS NOT NULL
ON CONFLICT (slot_key, reviewer_profile_id) DO UPDATE
SET
    member_role = EXCLUDED.member_role,
    can_review_en = EXCLUDED.can_review_en,
    can_review_tr = EXCLUDED.can_review_tr,
    counts_toward_official = EXCLUDED.counts_toward_official,
    active = EXCLUDED.active;

CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewer_profiles_email_unique
    ON reviewer_profiles(email)
    WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reviewer_profiles_auth_user ON reviewer_profiles(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_reviewer_profiles_slot ON reviewer_profiles(official_slot);
CREATE INDEX IF NOT EXISTS idx_reviewer_slot_members_slot ON reviewer_slot_members(slot_key, active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewer_slot_members_active_primary_per_slot
    ON reviewer_slot_members(slot_key)
    WHERE member_role = 'primary' AND active IS TRUE;
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewer_slot_members_active_primary_per_profile
    ON reviewer_slot_members(reviewer_profile_id)
    WHERE member_role = 'primary' AND active IS TRUE;
CREATE INDEX IF NOT EXISTS idx_paper_slot_assignments_paper ON paper_slot_assignments(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_slot_assignments_status ON paper_slot_assignments(status, workflow_language);
CREATE INDEX IF NOT EXISTS idx_paper_user_assignments_auth_status ON paper_user_assignments(auth_user_id, status, workflow_language);
CREATE INDEX IF NOT EXISTS idx_paper_user_assignments_profile_status ON paper_user_assignments(reviewer_profile_id, status);
CREATE INDEX IF NOT EXISTS idx_paper_user_assignments_paper ON paper_user_assignments(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_assignment_submissions_assignment ON paper_assignment_submissions(paper_user_assignment_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_assignment_submissions_paper ON paper_assignment_submissions(paper_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_assignment_submissions_hash ON paper_assignment_submissions(payload_hash);
CREATE INDEX IF NOT EXISTS idx_paper_conflicts_paper_status ON paper_conflicts(paper_id, status, conflict_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_open_internal_slot_conflicts_unique
    ON paper_conflicts(paper_id, slot_key)
    WHERE conflict_type = 'internal_slot_conflict' AND status = 'open';
CREATE UNIQUE INDEX IF NOT EXISTS idx_open_external_slot_conflicts_unique
    ON paper_conflicts(paper_id)
    WHERE conflict_type = 'external_slot_conflict' AND status = 'open';
CREATE INDEX IF NOT EXISTS idx_paper_review_outcomes_decision ON paper_review_outcomes(decision_kind, resolved_at DESC);
CREATE INDEX IF NOT EXISTS idx_papers_routing_status ON papers(routing_status, workflow_language, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_papers_route_destination ON papers(route_destination, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_papers_latest_ai_extraction ON papers(latest_ai_extraction_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_routing_stage_configs_single_active
    ON routing_stage_configs(active)
    WHERE active IS TRUE;
CREATE INDEX IF NOT EXISTS idx_paper_stage_tasks_status_created ON paper_stage_tasks(status, created_at, priority);
CREATE INDEX IF NOT EXISTS idx_paper_stage_tasks_paper ON paper_stage_tasks(paper_id, stage_key);
CREATE INDEX IF NOT EXISTS idx_ai_extractions_stage_paper ON ai_extractions(stage_key, paper_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_extractions_route_destination ON ai_extractions(route_destination, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_annotations_assignment_unique
    ON annotations(paper_user_assignment_id)
    WHERE paper_user_assignment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_paper_label_events_assignment ON paper_label_events(paper_user_assignment_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.normalize_submission_text(input_text TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT regexp_replace(trim(coalesce(input_text, '')), '\s+', ' ', 'g');
$$;

CREATE OR REPLACE FUNCTION public.claim_paper_stage_tasks(
    p_stage_key TEXT,
    p_limit INTEGER DEFAULT 1
)
RETURNS SETOF paper_stage_tasks
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_role TEXT := lower(trim(coalesce(auth.jwt() ->> 'role', current_setting('request.jwt.claim.role', true), '')));
BEGIN
    IF v_role <> 'service_role' THEN
        RAISE EXCEPTION 'service role required';
    END IF;

    RETURN QUERY
    WITH next_tasks AS (
        SELECT id
        FROM paper_stage_tasks
        WHERE status = 'queued'
          AND (p_stage_key IS NULL OR stage_key = p_stage_key)
        ORDER BY created_at ASC, id ASC
        LIMIT GREATEST(coalesce(p_limit, 1), 1)
        FOR UPDATE SKIP LOCKED
    )
    UPDATE paper_stage_tasks task
    SET
        status = 'processing',
        attempt_count = task.attempt_count + 1,
        started_at = NOW(),
        updated_at = NOW(),
        last_error = NULL
    FROM next_tasks
    WHERE task.id = next_tasks.id
    RETURNING task.*;
END;
$$;

CREATE OR REPLACE FUNCTION public.enforce_human_review_ready_assignment()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_routing_status TEXT;
BEGIN
    SELECT routing_status
    INTO v_routing_status
    FROM papers
    WHERE id = NEW.paper_id;

    IF coalesce(v_routing_status, '') <> 'human_review_ready' THEN
        RAISE EXCEPTION 'Paper % is not human_review_ready', NEW.paper_id;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_paper_slot_assignment_requires_human_review_ready ON paper_slot_assignments;
CREATE TRIGGER trg_paper_slot_assignment_requires_human_review_ready
    BEFORE INSERT OR UPDATE OF paper_id ON paper_slot_assignments
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_human_review_ready_assignment();

DROP TRIGGER IF EXISTS trg_paper_user_assignment_requires_human_review_ready ON paper_user_assignments;
CREATE TRIGGER trg_paper_user_assignment_requires_human_review_ready
    BEFORE INSERT OR UPDATE OF paper_id ON paper_user_assignments
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_human_review_ready_assignment();

CREATE OR REPLACE FUNCTION public.current_auth_email()
RETURNS TEXT
LANGUAGE sql
STABLE
AS $$
    SELECT lower(trim(coalesce(auth.jwt() ->> 'email', '')));
$$;

CREATE OR REPLACE FUNCTION public.current_user_has_cockpit_access()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM reviewer_profiles
        WHERE cockpit_access IS TRUE
          AND active IS TRUE
          AND (
              auth_user_id = auth.uid()
              OR (
                  email IS NOT NULL
                  AND email = public.current_auth_email()
              )
          )
    );
$$;

CREATE OR REPLACE FUNCTION public.current_user_is_tester()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM reviewer_profiles
        WHERE tester_access IS TRUE
          AND active IS TRUE
          AND (
              auth_user_id = auth.uid()
              OR (
                  email IS NOT NULL
                  AND email = public.current_auth_email()
              )
          )
    );
$$;

CREATE OR REPLACE FUNCTION public.current_user_can_write()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT NOT public.current_user_is_tester();
$$;

CREATE OR REPLACE FUNCTION public.current_user_has_cockpit_write_access()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT public.current_user_has_cockpit_access()
       AND public.current_user_can_write();
$$;

CREATE OR REPLACE FUNCTION public.upsert_reviewer_admin_config(
    p_email TEXT,
    p_display_name TEXT,
    p_active BOOLEAN DEFAULT TRUE,
    p_can_review_en BOOLEAN DEFAULT TRUE,
    p_can_review_tr BOOLEAN DEFAULT TRUE,
    p_tester_access BOOLEAN DEFAULT FALSE,
    p_official_slot TEXT DEFAULT NULL,
    p_shadow_slots TEXT[] DEFAULT ARRAY[]::TEXT[],
    p_cockpit_access BOOLEAN DEFAULT FALSE,
    p_priority_weight_en REAL DEFAULT 1.0,
    p_priority_weight_tr REAL DEFAULT 1.0,
    p_notes TEXT DEFAULT NULL
)
RETURNS reviewer_profiles
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_email TEXT := lower(trim(coalesce(p_email, '')));
    v_display_name TEXT := trim(coalesce(p_display_name, ''));
    v_official_slot TEXT := nullif(lower(trim(coalesce(p_official_slot, ''))), '');
    v_shadow_slot TEXT;
    v_shadow_slots TEXT[] := ARRAY(
        SELECT DISTINCT lower(trim(slot_key))
        FROM unnest(coalesce(p_shadow_slots, ARRAY[]::TEXT[])) AS slot_key
        WHERE trim(coalesce(slot_key, '')) <> ''
        ORDER BY lower(trim(slot_key))
    );
    v_profile reviewer_profiles;
    v_active_cockpit_count INTEGER;
BEGIN
    IF NOT public.current_user_has_cockpit_write_access() THEN
        RAISE EXCEPTION 'Cockpit write access required';
    END IF;

    IF v_email = '' THEN
        RAISE EXCEPTION 'Reviewer email is required';
    END IF;

    IF v_display_name = '' THEN
        RAISE EXCEPTION 'Reviewer display name is required';
    END IF;

    IF v_official_slot IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM reviewer_slots
        WHERE slot_key = v_official_slot
    ) THEN
        RAISE EXCEPTION 'Unknown official slot: %', v_official_slot;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM unnest(v_shadow_slots) AS shadow_slot(slot_key)
        WHERE NOT EXISTS (
            SELECT 1
            FROM reviewer_slots
            WHERE reviewer_slots.slot_key = shadow_slot.slot_key
        )
    ) THEN
        RAISE EXCEPTION 'All shadow slots must exist in reviewer_slots';
    END IF;

    IF v_official_slot IS NOT NULL AND v_official_slot = ANY(v_shadow_slots) THEN
        RAISE EXCEPTION 'A reviewer cannot be both the official and shadow member of the same slot';
    END IF;

    IF coalesce(p_tester_access, FALSE) IS TRUE THEN
        v_official_slot := NULL;
        v_shadow_slots := ARRAY[]::TEXT[];
    END IF;

    INSERT INTO allowed_auth_emails (email)
    VALUES (v_email)
    ON CONFLICT (email) DO NOTHING;

    INSERT INTO reviewer_profiles (
        email,
        display_name,
        active,
        can_review_en,
        can_review_tr,
        tester_access,
        official_slot,
        cockpit_access,
        priority_weight_en,
        priority_weight_tr,
        notes,
        updated_at
    )
    VALUES (
        v_email,
        v_display_name,
        coalesce(p_active, TRUE),
        coalesce(p_can_review_en, TRUE),
        coalesce(p_can_review_tr, TRUE),
        coalesce(p_tester_access, FALSE),
        v_official_slot,
        coalesce(p_cockpit_access, FALSE),
        coalesce(p_priority_weight_en, 1.0),
        coalesce(p_priority_weight_tr, 1.0),
        nullif(trim(coalesce(p_notes, '')), ''),
        NOW()
    )
    ON CONFLICT (email) DO UPDATE
    SET
        display_name = EXCLUDED.display_name,
        active = EXCLUDED.active,
        can_review_en = EXCLUDED.can_review_en,
        can_review_tr = EXCLUDED.can_review_tr,
        tester_access = EXCLUDED.tester_access,
        official_slot = EXCLUDED.official_slot,
        cockpit_access = EXCLUDED.cockpit_access,
        priority_weight_en = EXCLUDED.priority_weight_en,
        priority_weight_tr = EXCLUDED.priority_weight_tr,
        notes = EXCLUDED.notes,
        updated_at = NOW()
    RETURNING * INTO v_profile;

    UPDATE reviewer_slot_members
    SET active = FALSE
    WHERE reviewer_profile_id = v_profile.id;

    IF v_official_slot IS NOT NULL THEN
        INSERT INTO reviewer_slot_members (
            slot_key,
            reviewer_profile_id,
            member_role,
            can_review_en,
            can_review_tr,
            counts_toward_official,
            active
        )
        VALUES (
            v_official_slot,
            v_profile.id,
            'primary',
            v_profile.can_review_en,
            v_profile.can_review_tr,
            TRUE,
            v_profile.active
        )
        ON CONFLICT (slot_key, reviewer_profile_id) DO UPDATE
        SET
            member_role = 'primary',
            can_review_en = EXCLUDED.can_review_en,
            can_review_tr = EXCLUDED.can_review_tr,
            counts_toward_official = TRUE,
            active = EXCLUDED.active;
    END IF;

    FOREACH v_shadow_slot IN ARRAY v_shadow_slots
    LOOP
        INSERT INTO reviewer_slot_members (
            slot_key,
            reviewer_profile_id,
            member_role,
            can_review_en,
            can_review_tr,
            counts_toward_official,
            active
        )
        VALUES (
            v_shadow_slot,
            v_profile.id,
            'shadow',
            v_profile.can_review_en,
            v_profile.can_review_tr,
            FALSE,
            v_profile.active
        )
        ON CONFLICT (slot_key, reviewer_profile_id) DO UPDATE
        SET
            member_role = 'shadow',
            can_review_en = EXCLUDED.can_review_en,
            can_review_tr = EXCLUDED.can_review_tr,
            counts_toward_official = FALSE,
            active = EXCLUDED.active;
    END LOOP;

    SELECT COUNT(*)
    INTO v_active_cockpit_count
    FROM reviewer_profiles
    WHERE cockpit_access IS TRUE
      AND active IS TRUE
      AND tester_access IS FALSE;

    IF v_active_cockpit_count <= 0 THEN
        RAISE EXCEPTION 'At least one active cockpit write reviewer is required';
    END IF;

    SELECT *
    INTO v_profile
    FROM reviewer_profiles
    WHERE id = v_profile.id;

    RETURN v_profile;
END;
$$;

CREATE OR REPLACE FUNCTION public.build_annotation_submission_payload(
    p_annotation_id INTEGER,
    p_decision_kind TEXT
)
RETURNS JSONB
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
WITH ordered_foods AS (
    SELECT
        fi.id,
        public.normalize_submission_text(fi.food_name) AS food_name_sort,
        coalesce(fi.food_fdc_id::text, '') AS food_id_sort,
        fi.is_custom_food AS custom_sort,
        jsonb_build_object(
            'food_name', public.normalize_submission_text(fi.food_name),
            'food_fdc_id', fi.food_fdc_id,
            'is_custom_food', fi.is_custom_food,
            'nutrients', COALESCE((
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'nutrient_id', anv.nutrient_id,
                        'nutrient_name', public.normalize_submission_text(anv.nutrient_name),
                        'value', CASE
                            WHEN anv.value IS NULL THEN NULL
                            ELSE round(anv.value::numeric, 6)
                        END,
                        'unit', public.normalize_submission_text(anv.unit)
                    )
                    ORDER BY
                        coalesce(anv.nutrient_id::text, ''),
                        public.normalize_submission_text(anv.nutrient_name),
                        public.normalize_submission_text(anv.unit),
                        CASE
                            WHEN anv.value IS NULL THEN NULL
                            ELSE round(anv.value::numeric, 6)
                        END,
                        anv.id
                )
                FROM annotation_nutrient_values anv
                WHERE anv.food_item_id = fi.id
            ), '[]'::jsonb)
        ) AS payload
    FROM food_items fi
    WHERE fi.annotation_id = p_annotation_id
)
SELECT jsonb_build_object(
    'decision_kind', p_decision_kind,
    'food_items', COALESCE((
        SELECT jsonb_agg(payload ORDER BY food_name_sort, food_id_sort, custom_sort, id)
        FROM ordered_foods
    ), '[]'::jsonb)
);
$$;

CREATE OR REPLACE FUNCTION public.sync_reviewer_profile()
RETURNS reviewer_profiles
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_email TEXT := public.current_auth_email();
    v_profile reviewer_profiles;
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Authentication required';
    END IF;

    IF v_email IS NULL OR v_email = '' THEN
        RAISE EXCEPTION 'Authenticated user is missing an email address';
    END IF;

    INSERT INTO reviewer_profiles (
        email,
        auth_user_id,
        display_name,
        active,
        can_review_en,
        can_review_tr
    )
    VALUES (
        v_email,
        auth.uid(),
        split_part(v_email, '@', 1),
        TRUE,
        TRUE,
        TRUE
    )
    ON CONFLICT (email) DO UPDATE
    SET
        auth_user_id = EXCLUDED.auth_user_id,
        updated_at = NOW()
    RETURNING * INTO v_profile;

    UPDATE paper_user_assignments
    SET auth_user_id = auth.uid()
    WHERE reviewer_profile_id = v_profile.id
      AND (auth_user_id IS NULL OR auth_user_id <> auth.uid());

    RETURN v_profile;
END;
$$;

CREATE OR REPLACE FUNCTION public.touch_assignment_workspace(
    p_paper_user_assignment_id UUID,
    p_annotation_id INTEGER,
    p_status TEXT DEFAULT 'draft'
)
RETURNS paper_user_assignments
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_assignment paper_user_assignments;
BEGIN
    IF p_status NOT IN ('assigned', 'draft') THEN
        RAISE EXCEPTION 'Unsupported workspace status: %', p_status;
    END IF;

    IF NOT public.current_user_can_write() THEN
        RAISE EXCEPTION 'Read-only accounts cannot modify assignments';
    END IF;

    UPDATE paper_user_assignments
    SET
        last_annotation_id = COALESCE(p_annotation_id, last_annotation_id),
        last_saved_at = NOW(),
        status = CASE
            WHEN status IN ('submitted', 'resolved', 'conflict', 'cancelled') THEN status
            ELSE p_status
        END
    WHERE id = p_paper_user_assignment_id
      AND auth_user_id = auth.uid()
    RETURNING * INTO v_assignment;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Assignment not found or not owned by current user';
    END IF;

    RETURN v_assignment;
END;
$$;

CREATE OR REPLACE FUNCTION public.refresh_paper_resolution_state(
    p_paper_id INTEGER
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_slot paper_slot_assignments;
    v_slot_submission_count INTEGER;
    v_slot_assignment_count INTEGER;
    v_distinct_hash_count INTEGER;
    v_official_submission_id UUID;
    v_manual_submission_id UUID;
    v_first_submission_id UUID;
    v_second_submission_id UUID;
    v_open_conflict_id UUID;
    v_open_external_conflict_id UUID;
    v_resolved_external_conflict_id UUID;
    v_slot_one paper_slot_assignments;
    v_slot_two paper_slot_assignments;
    v_slot_one_submission paper_assignment_submissions;
    v_slot_two_submission paper_assignment_submissions;
BEGIN
    FOR v_slot IN
        SELECT *
        FROM paper_slot_assignments
        WHERE paper_id = p_paper_id
        ORDER BY slot_key
    LOOP
        SELECT COUNT(*)
        INTO v_slot_assignment_count
        FROM paper_user_assignments
        WHERE paper_slot_assignment_id = v_slot.id
          AND status <> 'cancelled';

        SELECT COUNT(*)
        INTO v_slot_submission_count
        FROM paper_user_assignments
        WHERE paper_slot_assignment_id = v_slot.id
          AND status <> 'cancelled'
          AND latest_submission_id IS NOT NULL;

        IF v_slot_assignment_count = 0 OR v_slot_submission_count < v_slot_assignment_count THEN
            UPDATE paper_slot_assignments
            SET
                status = 'pending',
                official_submission_id = NULL,
                submitted_at = CASE
                    WHEN v_slot_submission_count > 0 THEN submitted_at
                    ELSE NULL
                END,
                resolved_at = NULL
            WHERE id = v_slot.id;
            CONTINUE;
        END IF;

        SELECT COUNT(DISTINCT pas.payload_hash)
        INTO v_distinct_hash_count
        FROM paper_user_assignments pua
        JOIN paper_assignment_submissions pas
            ON pas.id = pua.latest_submission_id
        WHERE pua.paper_slot_assignment_id = v_slot.id
          AND pua.status <> 'cancelled';

        IF v_distinct_hash_count = 1 THEN
            SELECT COALESCE(
                (
                    SELECT pas.id
                    FROM paper_user_assignments pua
                    JOIN reviewer_slot_members rsm
                        ON rsm.reviewer_profile_id = pua.reviewer_profile_id
                       AND rsm.slot_key = v_slot.slot_key
                    JOIN paper_assignment_submissions pas
                        ON pas.id = pua.latest_submission_id
                    WHERE pua.paper_slot_assignment_id = v_slot.id
                      AND pua.status <> 'cancelled'
                      AND rsm.member_role = 'primary'
                    ORDER BY pas.submitted_at DESC
                    LIMIT 1
                ),
                (
                    SELECT latest_submission_id
                    FROM paper_user_assignments
                    WHERE paper_slot_assignment_id = v_slot.id
                      AND status <> 'cancelled'
                    ORDER BY submitted_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                )
            )
            INTO v_official_submission_id;

            UPDATE paper_slot_assignments
            SET
                status = 'submitted',
                official_submission_id = v_official_submission_id,
                submitted_at = COALESCE(submitted_at, NOW()),
                resolved_at = NULL
            WHERE id = v_slot.id;

            UPDATE paper_user_assignments
            SET status = CASE
                    WHEN status = 'resolved' THEN 'resolved'
                    ELSE 'submitted'
                END
            WHERE paper_slot_assignment_id = v_slot.id
              AND latest_submission_id IS NOT NULL
              AND status <> 'cancelled';
            CONTINUE;
        END IF;

        SELECT latest_submission_id
        INTO v_first_submission_id
        FROM paper_user_assignments
        WHERE paper_slot_assignment_id = v_slot.id
          AND status <> 'cancelled'
        ORDER BY reviewer_profile_id, created_at
        LIMIT 1;

        SELECT latest_submission_id
        INTO v_second_submission_id
        FROM paper_user_assignments
        WHERE paper_slot_assignment_id = v_slot.id
          AND status <> 'cancelled'
        ORDER BY reviewer_profile_id DESC, created_at DESC
        LIMIT 1;

        SELECT resolved_submission_id
        INTO v_manual_submission_id
        FROM paper_conflicts
        WHERE paper_id = p_paper_id
          AND conflict_type = 'internal_slot_conflict'
          AND slot_key = v_slot.slot_key
          AND status = 'resolved'
          AND (
              (left_submission_id = v_first_submission_id AND right_submission_id = v_second_submission_id)
              OR (left_submission_id = v_second_submission_id AND right_submission_id = v_first_submission_id)
          )
        ORDER BY resolved_at DESC NULLS LAST, created_at DESC
        LIMIT 1;

        IF v_manual_submission_id IS NOT NULL THEN
            UPDATE paper_slot_assignments
            SET
                status = 'submitted',
                official_submission_id = v_manual_submission_id,
                submitted_at = COALESCE(submitted_at, NOW()),
                resolved_at = NULL
            WHERE id = v_slot.id;

            UPDATE paper_user_assignments
            SET status = CASE
                    WHEN status = 'resolved' THEN 'resolved'
                    ELSE 'submitted'
                END
            WHERE paper_slot_assignment_id = v_slot.id
              AND latest_submission_id IS NOT NULL
              AND status <> 'cancelled';
            CONTINUE;
        END IF;

        UPDATE paper_slot_assignments
        SET
            status = 'conflict',
            official_submission_id = NULL,
            resolved_at = NULL
        WHERE id = v_slot.id;

        UPDATE paper_user_assignments
        SET status = CASE
                WHEN latest_submission_id IS NOT NULL THEN 'conflict'
                ELSE status
            END
        WHERE paper_slot_assignment_id = v_slot.id
          AND status <> 'cancelled';

        SELECT id
        INTO v_open_conflict_id
        FROM paper_conflicts
        WHERE paper_id = p_paper_id
          AND conflict_type = 'internal_slot_conflict'
          AND slot_key = v_slot.slot_key
          AND status = 'open'
        LIMIT 1;

        IF v_open_conflict_id IS NULL THEN
            INSERT INTO paper_conflicts (
                paper_id,
                conflict_type,
                slot_key,
                left_submission_id,
                right_submission_id
            )
            VALUES (
                p_paper_id,
                'internal_slot_conflict',
                v_slot.slot_key,
                v_first_submission_id,
                v_second_submission_id
            );
        ELSE
            UPDATE paper_conflicts
            SET
                left_submission_id = v_first_submission_id,
                right_submission_id = v_second_submission_id,
                created_at = NOW()
            WHERE id = v_open_conflict_id;
        END IF;
    END LOOP;

    SELECT *
    INTO v_slot_one
    FROM paper_slot_assignments
    WHERE paper_id = p_paper_id
    ORDER BY slot_key
    LIMIT 1;

    SELECT *
    INTO v_slot_two
    FROM paper_slot_assignments
    WHERE paper_id = p_paper_id
    ORDER BY slot_key
    OFFSET 1
    LIMIT 1;

    IF v_slot_one.id IS NULL OR v_slot_two.id IS NULL THEN
        RETURN;
    END IF;

    IF v_slot_one.official_submission_id IS NULL
       OR v_slot_two.official_submission_id IS NULL THEN
        RETURN;
    END IF;

    SELECT *
    INTO v_slot_one_submission
    FROM paper_assignment_submissions
    WHERE id = v_slot_one.official_submission_id;

    SELECT *
    INTO v_slot_two_submission
    FROM paper_assignment_submissions
    WHERE id = v_slot_two.official_submission_id;

    IF v_slot_one_submission.payload_hash = v_slot_two_submission.payload_hash THEN
        INSERT INTO paper_review_outcomes (
            paper_id,
            decision_kind,
            resolution_source,
            payload_json,
            payload_text,
            payload_hash,
            slot_submission_a_id,
            slot_submission_b_id,
            resolved_submission_id,
            conflict_id,
            resolved_by,
            resolved_at,
            updated_at,
            truth_source_kind,
            source_stage_key,
            source_model_name,
            source_confidence,
            training_weight
        )
        VALUES (
            p_paper_id,
            v_slot_one_submission.decision_kind,
            'slot_agreement',
            v_slot_one_submission.payload_json,
            v_slot_one_submission.payload_text,
            v_slot_one_submission.payload_hash,
            v_slot_one_submission.id,
            v_slot_two_submission.id,
            v_slot_one_submission.id,
            NULL,
            NULL,
            NOW(),
            NOW(),
            'human_review',
            NULL,
            NULL,
            NULL,
            1.0
        )
        ON CONFLICT (paper_id) DO UPDATE
        SET
            decision_kind = EXCLUDED.decision_kind,
            resolution_source = EXCLUDED.resolution_source,
            payload_json = EXCLUDED.payload_json,
            payload_text = EXCLUDED.payload_text,
            payload_hash = EXCLUDED.payload_hash,
            slot_submission_a_id = EXCLUDED.slot_submission_a_id,
            slot_submission_b_id = EXCLUDED.slot_submission_b_id,
            resolved_submission_id = EXCLUDED.resolved_submission_id,
            conflict_id = EXCLUDED.conflict_id,
            resolved_by = EXCLUDED.resolved_by,
            resolved_at = EXCLUDED.resolved_at,
            truth_source_kind = EXCLUDED.truth_source_kind,
            source_stage_key = NULL,
            source_model_name = NULL,
            source_confidence = NULL,
            training_weight = 1.0,
            updated_at = NOW();

        UPDATE paper_slot_assignments
        SET
            status = 'resolved',
            resolved_at = NOW()
        WHERE paper_id = p_paper_id;

        UPDATE paper_user_assignments
        SET
            status = 'resolved',
            resolved_at = NOW()
        WHERE paper_id = p_paper_id
          AND status <> 'cancelled';

        UPDATE paper_conflicts
        SET
            status = 'resolved',
            resolved_at = COALESCE(resolved_at, NOW())
        WHERE paper_id = p_paper_id
          AND conflict_type = 'external_slot_conflict'
          AND status = 'open';
        RETURN;
    END IF;

    SELECT resolved_submission_id, id
    INTO v_manual_submission_id, v_resolved_external_conflict_id
    FROM paper_conflicts
    WHERE paper_id = p_paper_id
      AND conflict_type = 'external_slot_conflict'
      AND status = 'resolved'
      AND (
          (left_submission_id = v_slot_one_submission.id AND right_submission_id = v_slot_two_submission.id)
          OR (left_submission_id = v_slot_two_submission.id AND right_submission_id = v_slot_one_submission.id)
      )
    ORDER BY resolved_at DESC NULLS LAST, created_at DESC
    LIMIT 1;

    IF v_manual_submission_id IS NOT NULL THEN
        INSERT INTO paper_review_outcomes (
            paper_id,
            decision_kind,
            resolution_source,
            payload_json,
            payload_text,
            payload_hash,
            slot_submission_a_id,
            slot_submission_b_id,
            resolved_submission_id,
            conflict_id,
            resolved_by,
            resolved_at,
            updated_at,
            truth_source_kind,
            source_stage_key,
            source_model_name,
            source_confidence,
            training_weight
        )
        SELECT
            p_paper_id,
            chosen.decision_kind,
            'conflict_resolution',
            chosen.payload_json,
            chosen.payload_text,
            chosen.payload_hash,
            v_slot_one_submission.id,
            v_slot_two_submission.id,
            chosen.id,
            v_resolved_external_conflict_id,
            chosen.auth_user_id,
            NOW(),
            NOW(),
            'human_review',
            NULL,
            NULL,
            NULL,
            1.0
        FROM paper_assignment_submissions chosen
        WHERE chosen.id = v_manual_submission_id
        ON CONFLICT (paper_id) DO UPDATE
        SET
            decision_kind = EXCLUDED.decision_kind,
            resolution_source = EXCLUDED.resolution_source,
            payload_json = EXCLUDED.payload_json,
            payload_text = EXCLUDED.payload_text,
            payload_hash = EXCLUDED.payload_hash,
            slot_submission_a_id = EXCLUDED.slot_submission_a_id,
            slot_submission_b_id = EXCLUDED.slot_submission_b_id,
            resolved_submission_id = EXCLUDED.resolved_submission_id,
            conflict_id = EXCLUDED.conflict_id,
            resolved_by = EXCLUDED.resolved_by,
            resolved_at = EXCLUDED.resolved_at,
            truth_source_kind = EXCLUDED.truth_source_kind,
            source_stage_key = NULL,
            source_model_name = NULL,
            source_confidence = NULL,
            training_weight = 1.0,
            updated_at = NOW();

        UPDATE paper_slot_assignments
        SET
            status = 'resolved',
            resolved_at = NOW()
        WHERE paper_id = p_paper_id;

        UPDATE paper_user_assignments
        SET
            status = 'resolved',
            resolved_at = NOW()
        WHERE paper_id = p_paper_id
          AND status <> 'cancelled';
        RETURN;
    END IF;

    UPDATE paper_slot_assignments
    SET status = 'conflict'
    WHERE paper_id = p_paper_id
      AND status <> 'cancelled';

    SELECT id
    INTO v_open_external_conflict_id
    FROM paper_conflicts
    WHERE paper_id = p_paper_id
      AND conflict_type = 'external_slot_conflict'
      AND status = 'open'
    LIMIT 1;

    IF v_open_external_conflict_id IS NULL THEN
        INSERT INTO paper_conflicts (
            paper_id,
            conflict_type,
            slot_key,
            left_submission_id,
            right_submission_id
        )
        VALUES (
            p_paper_id,
            'external_slot_conflict',
            NULL,
            v_slot_one_submission.id,
            v_slot_two_submission.id
        );
    ELSE
        UPDATE paper_conflicts
        SET
            left_submission_id = v_slot_one_submission.id,
            right_submission_id = v_slot_two_submission.id,
            created_at = NOW()
        WHERE id = v_open_external_conflict_id;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.submit_assignment_review(
    p_paper_user_assignment_id UUID,
    p_annotation_id INTEGER,
    p_decision_kind TEXT,
    p_submission_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS paper_assignment_submissions
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_assignment paper_user_assignments;
    v_annotation annotations;
    v_payload_json JSONB;
    v_payload_text TEXT;
    v_payload_hash TEXT;
    v_submission paper_assignment_submissions;
    v_food_count INTEGER;
BEGIN
    IF p_decision_kind NOT IN ('has_data', 'no_usable_data') THEN
        RAISE EXCEPTION 'Unsupported decision kind: %', p_decision_kind;
    END IF;

    IF NOT public.current_user_can_write() THEN
        RAISE EXCEPTION 'Read-only accounts cannot modify assignments';
    END IF;

    SELECT *
    INTO v_assignment
    FROM paper_user_assignments
    WHERE id = p_paper_user_assignment_id
      AND auth_user_id = auth.uid()
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Assignment not found or not owned by current user';
    END IF;

    IF v_assignment.status IN ('resolved', 'cancelled') THEN
        RAISE EXCEPTION 'Assignment is no longer editable';
    END IF;

    IF p_annotation_id IS NOT NULL THEN
        SELECT *
        INTO v_annotation
        FROM annotations
        WHERE id = p_annotation_id
          AND user_id = auth.uid()
          AND paper_id = v_assignment.paper_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Annotation not found for assignment';
        END IF;
    END IF;

    IF p_decision_kind = 'has_data' THEN
        IF v_annotation.id IS NULL THEN
            RAISE EXCEPTION 'A completed extraction requires an annotation';
        END IF;

        SELECT COUNT(*)
        INTO v_food_count
        FROM food_items
        WHERE annotation_id = v_annotation.id;

        IF v_food_count <= 0 THEN
            RAISE EXCEPTION 'Cannot submit has_data without at least one food item';
        END IF;

        v_payload_json := public.build_annotation_submission_payload(v_annotation.id, p_decision_kind);
    ELSE
        v_payload_json := jsonb_build_object(
            'decision_kind', 'no_usable_data',
            'food_items', '[]'::jsonb
        );
    END IF;

    v_payload_text := v_payload_json::text;
    v_payload_hash := encode(digest(v_payload_text, 'sha256'), 'hex');

    INSERT INTO paper_assignment_submissions (
        paper_user_assignment_id,
        paper_slot_assignment_id,
        paper_id,
        reviewer_profile_id,
        auth_user_id,
        annotation_id,
        decision_kind,
        payload_json,
        payload_text,
        payload_hash,
        submission_metadata
    )
    VALUES (
        v_assignment.id,
        v_assignment.paper_slot_assignment_id,
        v_assignment.paper_id,
        v_assignment.reviewer_profile_id,
        auth.uid(),
        v_annotation.id,
        p_decision_kind,
        v_payload_json,
        v_payload_text,
        v_payload_hash,
        COALESCE(p_submission_metadata, '{}'::jsonb)
    )
    RETURNING * INTO v_submission;

    UPDATE paper_user_assignments
    SET
        last_annotation_id = COALESCE(v_annotation.id, last_annotation_id),
        latest_submission_id = v_submission.id,
        status = 'submitted',
        submitted_at = NOW(),
        last_saved_at = NOW()
    WHERE id = v_assignment.id;

    IF v_annotation.id IS NOT NULL THEN
        UPDATE annotations
        SET
            paper_user_assignment_id = v_assignment.id,
            has_data = (p_decision_kind = 'has_data'),
            status = CASE
                WHEN p_decision_kind = 'has_data' THEN 'done'
                ELSE 'skipped'
            END,
            updated_at = NOW()
        WHERE id = v_annotation.id;
    END IF;

    PERFORM public.refresh_paper_resolution_state(v_assignment.paper_id);
    RETURN v_submission;
END;
$$;

CREATE OR REPLACE FUNCTION public.mark_assignment_global_no_data(
    p_paper_user_assignment_id UUID,
    p_reason TEXT
)
RETURNS paper_global_labels
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_assignment paper_user_assignments;
    v_existing_outcome paper_review_outcomes;
    v_existing_label paper_global_labels;
    v_global_label paper_global_labels;
    v_payload_json JSONB := jsonb_build_object(
        'decision_kind', 'no_usable_data',
        'food_items', '[]'::jsonb
    );
    v_payload_text TEXT := v_payload_json::text;
    v_payload_hash TEXT := encode(digest(v_payload_text, 'sha256'), 'hex');
    v_reason TEXT := trim(coalesce(p_reason, ''));
BEGIN
    IF v_reason = '' THEN
        RAISE EXCEPTION 'Reason required for definitely-no-data';
    END IF;

    IF NOT public.current_user_can_write() THEN
        RAISE EXCEPTION 'Read-only accounts cannot modify assignments';
    END IF;

    SELECT *
    INTO v_assignment
    FROM paper_user_assignments
    WHERE id = p_paper_user_assignment_id
      AND auth_user_id = auth.uid()
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Assignment not found or not owned by current user';
    END IF;

    SELECT *
    INTO v_existing_label
    FROM paper_global_labels
    WHERE paper_id = v_assignment.paper_id
      AND label = 'definitely_no_data'
    LIMIT 1;

    IF v_existing_label.id IS NOT NULL THEN
        RETURN v_existing_label;
    END IF;

    IF v_assignment.status IN ('resolved', 'cancelled') THEN
        RAISE EXCEPTION 'Assignment is no longer editable';
    END IF;

    SELECT *
    INTO v_existing_outcome
    FROM paper_review_outcomes
    WHERE paper_id = v_assignment.paper_id
    LIMIT 1;

    IF v_existing_outcome.id IS NOT NULL THEN
        RAISE EXCEPTION 'Paper already has a resolved outcome';
    END IF;

    INSERT INTO paper_global_labels (
        paper_id,
        user_id,
        label,
        reason,
        paper_user_assignment_id,
        paper_slot_assignment_id,
        reviewer_profile_id,
        slot_key
    )
    VALUES (
        v_assignment.paper_id,
        auth.uid(),
        'definitely_no_data',
        v_reason,
        v_assignment.id,
        v_assignment.paper_slot_assignment_id,
        v_assignment.reviewer_profile_id,
        (
            SELECT slot_key
            FROM paper_slot_assignments
            WHERE id = v_assignment.paper_slot_assignment_id
        )
    )
    ON CONFLICT (paper_id, label) DO NOTHING
    RETURNING * INTO v_global_label;

    IF v_global_label.id IS NULL THEN
        SELECT *
        INTO v_global_label
        FROM paper_global_labels
        WHERE paper_id = v_assignment.paper_id
          AND label = 'definitely_no_data'
        LIMIT 1;
        RETURN v_global_label;
    END IF;

    INSERT INTO paper_label_events (
        paper_id,
        annotation_id,
        paper_user_assignment_id,
        paper_slot_assignment_id,
        user_id,
        has_data,
        status,
        decision_kind,
        food_item_count,
        nutrient_value_count,
        source
    )
    VALUES (
        v_assignment.paper_id,
        NULL,
        v_assignment.id,
        v_assignment.paper_slot_assignment_id,
        auth.uid(),
        FALSE,
        'skipped',
        'no_usable_data',
        0,
        0,
        'global_no_data'
    );

    UPDATE paper_conflicts
    SET
        status = 'cancelled',
        resolved_at = COALESCE(resolved_at, NOW())
    WHERE paper_id = v_assignment.paper_id
      AND status = 'open';

    UPDATE paper_slot_assignments
    SET
        status = 'cancelled',
        official_submission_id = NULL,
        resolved_at = NOW()
    WHERE paper_id = v_assignment.paper_id
      AND status <> 'cancelled';

    UPDATE paper_user_assignments
    SET
        status = 'cancelled',
        resolved_at = NOW()
    WHERE paper_id = v_assignment.paper_id
      AND status <> 'cancelled';

    INSERT INTO paper_review_outcomes (
        paper_id,
        decision_kind,
        resolution_source,
        payload_json,
        payload_text,
        payload_hash,
        slot_submission_a_id,
        slot_submission_b_id,
        resolved_submission_id,
        conflict_id,
        resolved_by,
        resolved_at,
        updated_at,
        truth_source_kind,
        source_stage_key,
        source_model_name,
        source_confidence,
        training_weight
    )
    VALUES (
        v_assignment.paper_id,
        'no_usable_data',
        'global_skip',
        v_payload_json,
        v_payload_text,
        v_payload_hash,
        NULL,
        NULL,
        NULL,
        NULL,
        auth.uid(),
        NOW(),
        NOW(),
        'human_review',
        NULL,
        NULL,
        NULL,
        1.0
    )
    ON CONFLICT (paper_id) DO UPDATE
    SET
        decision_kind = EXCLUDED.decision_kind,
        resolution_source = EXCLUDED.resolution_source,
        payload_json = EXCLUDED.payload_json,
        payload_text = EXCLUDED.payload_text,
        payload_hash = EXCLUDED.payload_hash,
        slot_submission_a_id = NULL,
        slot_submission_b_id = NULL,
        resolved_submission_id = NULL,
        conflict_id = NULL,
        resolved_by = EXCLUDED.resolved_by,
        resolved_at = EXCLUDED.resolved_at,
        truth_source_kind = EXCLUDED.truth_source_kind,
        source_stage_key = NULL,
        source_model_name = NULL,
        source_confidence = NULL,
        training_weight = 1.0,
        updated_at = NOW();

    RETURN v_global_label;
END;
$$;

CREATE OR REPLACE FUNCTION public.resolve_paper_conflict(
    p_conflict_id UUID,
    p_winning_submission_id UUID,
    p_resolution_note TEXT DEFAULT NULL
)
RETURNS paper_conflicts
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_conflict paper_conflicts;
BEGIN
    IF NOT public.current_user_has_cockpit_write_access() THEN
        RAISE EXCEPTION 'Cockpit write access required';
    END IF;

    SELECT *
    INTO v_conflict
    FROM paper_conflicts
    WHERE id = p_conflict_id
      AND status = 'open'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Open conflict not found';
    END IF;

    IF p_winning_submission_id NOT IN (v_conflict.left_submission_id, v_conflict.right_submission_id) THEN
        RAISE EXCEPTION 'Winning submission must match one side of the conflict';
    END IF;

    UPDATE paper_conflicts
    SET
        status = 'resolved',
        resolved_submission_id = p_winning_submission_id,
        resolution_note = p_resolution_note,
        resolved_by = auth.uid(),
        resolved_at = NOW()
    WHERE id = p_conflict_id
    RETURNING * INTO v_conflict;

    PERFORM public.refresh_paper_resolution_state(v_conflict.paper_id);
    RETURN v_conflict;
END;
$$;

ALTER TABLE reviewer_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviewer_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviewer_slot_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_slot_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_user_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_assignment_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_conflicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_review_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_label_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE backlog_review_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can read paper search hits" ON paper_search_hits;
DROP POLICY IF EXISTS "Authenticated users can read paper label events" ON paper_label_events;
DROP POLICY IF EXISTS "Users can insert their own paper label events" ON paper_label_events;
DROP POLICY IF EXISTS "Users can view reviewer profiles" ON reviewer_profiles;
DROP POLICY IF EXISTS "Authenticated users can read reviewer slots" ON reviewer_slots;
DROP POLICY IF EXISTS "Authenticated users can read reviewer slot members" ON reviewer_slot_members;
DROP POLICY IF EXISTS "Users can view their own paper slot assignments" ON paper_slot_assignments;
DROP POLICY IF EXISTS "Users can view their own paper user assignments" ON paper_user_assignments;
DROP POLICY IF EXISTS "Users can view their own assignment submissions" ON paper_assignment_submissions;
DROP POLICY IF EXISTS "Cockpit users can read conflicts" ON paper_conflicts;
DROP POLICY IF EXISTS "Users can view accessible review outcomes" ON paper_review_outcomes;
DROP POLICY IF EXISTS "Users can view accessible backlog review items" ON backlog_review_items;
DROP POLICY IF EXISTS "Users can insert suggestion review items" ON backlog_review_items;
DROP POLICY IF EXISTS "Cockpit users can update backlog review items" ON backlog_review_items;
DROP POLICY IF EXISTS "Service role full access reviewer slots" ON reviewer_slots;
DROP POLICY IF EXISTS "Service role full access reviewer profiles" ON reviewer_profiles;
DROP POLICY IF EXISTS "Service role full access reviewer slot members" ON reviewer_slot_members;
DROP POLICY IF EXISTS "Service role full access paper slot assignments" ON paper_slot_assignments;
DROP POLICY IF EXISTS "Service role full access paper user assignments" ON paper_user_assignments;
DROP POLICY IF EXISTS "Service role full access paper assignment submissions" ON paper_assignment_submissions;
DROP POLICY IF EXISTS "Service role full access paper conflicts" ON paper_conflicts;
DROP POLICY IF EXISTS "Service role full access paper review outcomes" ON paper_review_outcomes;
DROP POLICY IF EXISTS "Service role full access paper label events" ON paper_label_events;
DROP POLICY IF EXISTS "Service role full access backlog review items" ON backlog_review_items;
DROP POLICY IF EXISTS "Users can insert their own annotations" ON annotations;
DROP POLICY IF EXISTS "Users can update their own annotations" ON annotations;
DROP POLICY IF EXISTS "Users can insert their own food items" ON food_items;
DROP POLICY IF EXISTS "Users can update their own food items" ON food_items;
DROP POLICY IF EXISTS "Users can delete their own food items" ON food_items;
DROP POLICY IF EXISTS "Users can insert their own nutrient values" ON annotation_nutrient_values;
DROP POLICY IF EXISTS "Users can update their own nutrient values" ON annotation_nutrient_values;
DROP POLICY IF EXISTS "Users can delete their own nutrient values" ON annotation_nutrient_values;
DROP POLICY IF EXISTS "Users can insert global labels" ON paper_global_labels;
DROP POLICY IF EXISTS "Users can delete their own global labels" ON paper_global_labels;
DROP POLICY IF EXISTS "Users can insert their own search sessions" ON search_sessions;

CREATE POLICY "Authenticated users can read reviewer slots"
    ON reviewer_slots FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Users can view reviewer profiles"
    ON reviewer_profiles FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Authenticated users can read reviewer slot members"
    ON reviewer_slot_members FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "Users can view their own paper slot assignments"
    ON paper_slot_assignments FOR SELECT TO authenticated
    USING (
        public.current_user_has_cockpit_access()
        OR EXISTS (
            SELECT 1
            FROM paper_user_assignments pua
            WHERE pua.paper_slot_assignment_id = paper_slot_assignments.id
              AND pua.auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Users can view their own paper user assignments"
    ON paper_user_assignments FOR SELECT TO authenticated
    USING (
        public.current_user_has_cockpit_access()
        OR auth_user_id = auth.uid()
    );

CREATE POLICY "Users can view their own assignment submissions"
    ON paper_assignment_submissions FOR SELECT TO authenticated
    USING (
        public.current_user_has_cockpit_access()
        OR EXISTS (
            SELECT 1
            FROM paper_user_assignments pua
            WHERE pua.id = paper_assignment_submissions.paper_user_assignment_id
              AND pua.auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Cockpit users can read conflicts"
    ON paper_conflicts FOR SELECT TO authenticated
    USING (public.current_user_has_cockpit_access());

CREATE POLICY "Users can view accessible review outcomes"
    ON paper_review_outcomes FOR SELECT TO authenticated
    USING (
        public.current_user_has_cockpit_access()
        OR EXISTS (
            SELECT 1
            FROM paper_user_assignments pua
            WHERE pua.paper_id = paper_review_outcomes.paper_id
              AND pua.auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Authenticated users can read paper label events"
    ON paper_label_events FOR SELECT TO authenticated
    USING (
        public.current_user_has_cockpit_access()
        OR user_id = auth.uid()
    );

CREATE POLICY "Users can insert their own paper label events"
    ON paper_label_events FOR INSERT TO authenticated
    WITH CHECK (
        user_id = auth.uid()
        AND public.current_user_can_write()
        AND (
            paper_user_assignment_id IS NULL
            OR EXISTS (
                SELECT 1
                FROM paper_user_assignments pua
                WHERE pua.id = paper_user_assignment_id
                  AND pua.auth_user_id = auth.uid()
            )
        )
    );

CREATE POLICY "Users can view accessible backlog review items"
    ON backlog_review_items FOR SELECT TO authenticated
    USING (
        public.current_user_has_cockpit_access()
        OR submitted_by_auth_user_id = auth.uid()
    );

CREATE POLICY "Users can insert suggestion review items"
    ON backlog_review_items FOR INSERT TO authenticated
    WITH CHECK (
        item_kind = 'suggestion_review'
        AND submitted_by_auth_user_id = auth.uid()
    );

CREATE POLICY "Cockpit users can update backlog review items"
    ON backlog_review_items FOR UPDATE TO authenticated
    USING (public.current_user_has_cockpit_write_access())
    WITH CHECK (public.current_user_has_cockpit_write_access());

CREATE POLICY "Authenticated users can read paper search hits"
    ON paper_search_hits FOR SELECT TO authenticated
    USING (public.current_user_has_cockpit_access());

CREATE POLICY "Service role full access reviewer slots"
    ON reviewer_slots FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access reviewer profiles"
    ON reviewer_profiles FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access reviewer slot members"
    ON reviewer_slot_members FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access paper slot assignments"
    ON paper_slot_assignments FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access paper user assignments"
    ON paper_user_assignments FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access paper assignment submissions"
    ON paper_assignment_submissions FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access paper conflicts"
    ON paper_conflicts FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access paper review outcomes"
    ON paper_review_outcomes FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access paper label events"
    ON paper_label_events FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access backlog review items"
    ON backlog_review_items FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

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
CREATE INDEX IF NOT EXISTS idx_paper_label_events_paper ON paper_label_events(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_label_events_user ON paper_label_events(user_id);
CREATE INDEX IF NOT EXISTS idx_paper_global_labels_paper ON paper_global_labels(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_global_labels_label ON paper_global_labels(label);
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_canonical_key_unique ON papers(canonical_key);
CREATE INDEX IF NOT EXISTS idx_paper_search_hits_paper ON paper_search_hits(paper_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_search_hits_hit_key_unique ON paper_search_hits(hit_key);
CREATE INDEX IF NOT EXISTS idx_paper_search_hits_canonical ON paper_search_hits(canonical_key);
CREATE INDEX IF NOT EXISTS idx_paper_search_hits_pair ON paper_search_hits(source, workflow_language, template_id, source_term);
CREATE INDEX IF NOT EXISTS idx_paper_search_batches_run ON paper_search_batches(run_id, batch_rank);
CREATE INDEX IF NOT EXISTS idx_paper_search_batches_language_source ON paper_search_batches(workflow_language, source, template_id, source_term);
CREATE INDEX IF NOT EXISTS idx_paper_search_batches_key ON paper_search_batches(batch_key);
CREATE INDEX IF NOT EXISTS idx_paper_search_batch_hits_hit ON paper_search_batch_hits(hit_key);

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
CREATE INDEX IF NOT EXISTS idx_backlog_review_items_status_created ON backlog_review_items(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backlog_review_items_submitter ON backlog_review_items(submitted_by_auth_user_id, created_at DESC);

-- =============================================
-- Row Level Security
-- =============================================

ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE master_nutrients ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE routing_stage_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_stage_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_search_hits ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_search_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_search_batch_hits ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_global_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_extractions ENABLE ROW LEVEL SECURITY;
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
        WHERE schemaname = 'public' AND tablename = 'routing_stage_configs'
          AND policyname = 'Cockpit users can read routing stage configs'
    ) THEN
        CREATE POLICY "Cockpit users can read routing stage configs"
            ON routing_stage_configs FOR SELECT TO authenticated
            USING (public.current_user_has_cockpit_access());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'routing_stage_configs'
          AND policyname = 'Cockpit writers can update routing stage configs'
    ) THEN
        CREATE POLICY "Cockpit writers can update routing stage configs"
            ON routing_stage_configs FOR UPDATE TO authenticated
            USING (public.current_user_has_cockpit_write_access())
            WITH CHECK (public.current_user_has_cockpit_write_access());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'routing_stage_configs'
          AND policyname = 'Service role full access routing stage configs'
    ) THEN
        CREATE POLICY "Service role full access routing stage configs"
            ON routing_stage_configs FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'paper_stage_tasks'
          AND policyname = 'Service role full access paper stage tasks'
    ) THEN
        CREATE POLICY "Service role full access paper stage tasks"
            ON paper_stage_tasks FOR ALL TO service_role USING (true) WITH CHECK (true);
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
        WHERE schemaname = 'public' AND tablename = 'ai_extractions'
          AND policyname = 'AI extractions readable by all authenticated users'
    ) THEN
        CREATE POLICY "AI extractions readable by all authenticated users"
            ON ai_extractions FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'ai_extractions'
          AND policyname = 'Service role full access ai_extractions'
    ) THEN
        CREATE POLICY "Service role full access ai_extractions"
            ON ai_extractions FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'paper_search_hits'
          AND policyname = 'Service role can manage paper search hits'
    ) THEN
        CREATE POLICY "Service role can manage paper search hits"
            ON paper_search_hits FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'paper_search_batches'
          AND policyname = 'Service role can manage paper search batches'
    ) THEN
        CREATE POLICY "Service role can manage paper search batches"
            ON paper_search_batches FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'paper_search_batch_hits'
          AND policyname = 'Service role can manage paper search batch hits'
    ) THEN
        CREATE POLICY "Service role can manage paper search batch hits"
            ON paper_search_batch_hits FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'paper_global_labels'
          AND policyname = 'Authenticated users can read global labels'
    ) THEN
        CREATE POLICY "Authenticated users can read global labels"
            ON paper_global_labels FOR SELECT TO authenticated USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'paper_global_labels'
          AND policyname = 'Users can insert global labels'
    ) THEN
        CREATE POLICY "Users can insert global labels"
            ON paper_global_labels FOR INSERT TO authenticated
            WITH CHECK (user_id = auth.uid() AND public.current_user_can_write());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'paper_global_labels'
          AND policyname = 'Users can delete their own global labels'
    ) THEN
        CREATE POLICY "Users can delete their own global labels"
            ON paper_global_labels FOR DELETE TO authenticated
            USING (user_id = auth.uid() AND public.current_user_can_write());
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
            WITH CHECK (user_id = auth.uid() AND public.current_user_can_write());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'annotations'
          AND policyname = 'Users can update their own annotations'
    ) THEN
        CREATE POLICY "Users can update their own annotations"
            ON annotations FOR UPDATE TO authenticated
            USING (user_id = auth.uid() AND public.current_user_can_write());
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
                public.current_user_can_write()
                AND
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
                public.current_user_can_write()
                AND
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
                public.current_user_can_write()
                AND
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
                public.current_user_can_write()
                AND
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
                public.current_user_can_write()
                AND
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
                public.current_user_can_write()
                AND
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
            WITH CHECK (user_id = auth.uid() AND public.current_user_can_write());
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

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'paper_global_labels'
          AND policyname = 'Service role full access global labels'
    ) THEN
        CREATE POLICY "Service role full access global labels"
            ON paper_global_labels FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

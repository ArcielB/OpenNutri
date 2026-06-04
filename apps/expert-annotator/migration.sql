-- =============================================
-- OpenNutri Annotator - Schema Migration
-- Aligns the annotator app with the SR Legacy-backed
-- `entities` / `master_nutrients` reference model.
-- =============================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =============================================
-- Auth signup allowlist
-- =============================================

CREATE TABLE IF NOT EXISTS public.allowed_auth_emails (
    email TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.allowed_auth_emails ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.allowed_auth_emails FROM anon, authenticated, public;
GRANT ALL ON TABLE public.allowed_auth_emails TO service_role;

INSERT INTO public.allowed_auth_emails (email)
VALUES
    ('ayseguldogann99@gmail.com'),
    ('ayseguldogan2706@gmail.com'),
    ('baezarciel@gmail.com'),
    ('dainesalazarromero@gmail.com'),
    ('f221229078@ktun.edu.tr'),
    ('mcraft160105@gmail.com'),
    ('ozcnaleyna2@gmail.com'),
    ('periacikgoz22@gmail.com')
ON CONFLICT (email) DO NOTHING;

CREATE OR REPLACE FUNCTION public.hook_restrict_signup_by_email_allowlist(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    attempted_email TEXT;
    is_allowed BOOLEAN;
BEGIN
    attempted_email := lower(trim(event->'user'->>'email'));

    SELECT EXISTS (
        SELECT 1
        FROM public.allowed_auth_emails
        WHERE lower(email) = attempted_email
    )
    INTO is_allowed;

    IF is_allowed THEN
        RETURN '{}'::jsonb;
    END IF;

    RETURN jsonb_build_object(
        'error',
        jsonb_build_object(
            'http_code', 403,
            'message', 'This email is not allowed to access OpenNutri.'
        )
    );
END;
$$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_auth_admin') THEN
        GRANT EXECUTE
            ON FUNCTION public.hook_restrict_signup_by_email_allowlist(jsonb)
            TO supabase_auth_admin;
    END IF;
END $$;

REVOKE EXECUTE
    ON FUNCTION public.hook_restrict_signup_by_email_allowlist(jsonb)
    FROM authenticated, anon, public;

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
    pdf_url TEXT,
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
    ADD COLUMN IF NOT EXISTS pdf_url TEXT,
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
            'ai_finalized_no_usable_data',
            'ai_provisional_no_usable_data'
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
        OR route_destination IN ('human_review', 'finalized', 'blocked', 'next_stage', 'provisional_skip')
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
    pdf_url TEXT,
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

ALTER TABLE paper_search_hits
    ADD COLUMN IF NOT EXISTS pdf_url TEXT;

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

CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_search_hits_hit_key_unique
    ON paper_search_hits(hit_key);

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
    raw_food_name TEXT,
    preparation_state TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS annotation_nutrient_values (
    id SERIAL PRIMARY KEY,
    food_item_id INTEGER NOT NULL REFERENCES food_items(id) ON DELETE CASCADE,
    nutrient_id UUID REFERENCES master_nutrients(id),
    is_custom_nutrient BOOLEAN NOT NULL DEFAULT FALSE,
    nutrient_name TEXT NOT NULL,
    raw_nutrient_name TEXT,
    value REAL,
    unit TEXT NOT NULL,
    basis TEXT NOT NULL DEFAULT 'per_100g',
    sample_size INTEGER,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    source_citation TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE food_items
    ADD COLUMN IF NOT EXISTS food_fdc_id UUID REFERENCES entities(id),
    ADD COLUMN IF NOT EXISTS is_custom_food BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS raw_food_name TEXT,
    ADD COLUMN IF NOT EXISTS preparation_state TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE annotation_nutrient_values
    ADD COLUMN IF NOT EXISTS nutrient_id UUID REFERENCES master_nutrients(id),
    ADD COLUMN IF NOT EXISTS is_custom_nutrient BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS raw_nutrient_name TEXT,
    ADD COLUMN IF NOT EXISTS basis TEXT NOT NULL DEFAULT 'per_100g',
    ADD COLUMN IF NOT EXISTS sample_size INTEGER,
    ADD COLUMN IF NOT EXISTS confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    ADD COLUMN IF NOT EXISTS source_citation TEXT,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

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
        CHECK (slot_key IN ('arciel', 'peri', 'aleyna', 'aysegul')),
    display_name TEXT NOT NULL,
    is_official BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'reviewer_slots'
          AND constraint_name = 'reviewer_slots_slot_key_check'
    ) THEN
        ALTER TABLE reviewer_slots
            DROP CONSTRAINT reviewer_slots_slot_key_check;
    END IF;

    ALTER TABLE reviewer_slots
        ADD CONSTRAINT reviewer_slots_slot_key_check
        CHECK (slot_key IN ('arciel', 'peri', 'aleyna', 'aysegul'));
END $$;

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
    can_approve_labels BOOLEAN NOT NULL DEFAULT FALSE,
    priority_weight_en REAL NOT NULL DEFAULT 1.0,
    priority_weight_tr REAL NOT NULL DEFAULT 1.0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE reviewer_profiles
    ADD COLUMN IF NOT EXISTS tester_access BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS can_approve_labels BOOLEAN NOT NULL DEFAULT FALSE;

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

CREATE TABLE IF NOT EXISTS paper_label_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    status TEXT NOT NULL DEFAULT 'pending_approval'
        CHECK (status IN ('pending_approval', 'accepted', 'superseded')),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_label_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id INTEGER NOT NULL UNIQUE REFERENCES papers(id) ON DELETE CASCADE,
    label_submission_id UUID NOT NULL REFERENCES paper_label_submissions(id) ON DELETE RESTRICT,
    approver_profile_id UUID NOT NULL REFERENCES reviewer_profiles(id) ON DELETE RESTRICT,
    approver_auth_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    approval_annotation_id INTEGER REFERENCES annotations(id) ON DELETE SET NULL,
    decision_kind TEXT NOT NULL
        CHECK (decision_kind IN ('has_data', 'no_usable_data')),
    payload_json JSONB NOT NULL,
    payload_text TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    correction_diff_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    approval_note TEXT,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

CREATE TABLE IF NOT EXISTS paper_conflict_resolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id INTEGER NOT NULL UNIQUE REFERENCES papers(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'resolved', 'dismissed')),
    winning_submission_id UUID REFERENCES paper_assignment_submissions(id) ON DELETE SET NULL,
    decision_kind TEXT
        CHECK (decision_kind IN ('has_data', 'no_usable_data')),
    resolution_note TEXT,
    resolved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW public.paper_conflict_candidates AS
WITH latest_submissions AS (
    SELECT
        pua.paper_id,
        pua.id AS paper_user_assignment_id,
        pua.reviewer_profile_id,
        pua.latest_submission_id AS submission_id
    FROM paper_user_assignments pua
    WHERE pua.latest_submission_id IS NOT NULL
),
submission_rows AS (
    SELECT
        ls.paper_id,
        ls.paper_user_assignment_id,
        ls.reviewer_profile_id,
        pas.id AS submission_id,
        pas.decision_kind,
        pas.payload_hash,
        pas.submitted_at
    FROM latest_submissions ls
    JOIN paper_assignment_submissions pas
      ON pas.id = ls.submission_id
),
aggregated AS (
    SELECT
        paper_id,
        COUNT(*)::INTEGER AS submission_count,
        COUNT(DISTINCT reviewer_profile_id)::INTEGER AS reviewer_count,
        COUNT(DISTINCT decision_kind)::INTEGER AS distinct_decision_count,
        COUNT(DISTINCT payload_hash)::INTEGER AS distinct_payload_count,
        MAX(submitted_at) AS latest_submitted_at,
        ARRAY_AGG(submission_id ORDER BY submitted_at DESC, submission_id) AS submission_ids,
        JSONB_AGG(
            JSONB_BUILD_OBJECT(
                'submission_id', submission_id,
                'paper_user_assignment_id', paper_user_assignment_id,
                'reviewer_profile_id', reviewer_profile_id,
                'decision_kind', decision_kind,
                'payload_hash', payload_hash,
                'submitted_at', submitted_at
            )
            ORDER BY submitted_at DESC, submission_id
        ) AS submission_summaries
    FROM submission_rows
    GROUP BY paper_id
)
SELECT
    md5(
        aggregated.paper_id::TEXT || '|' ||
        array_to_string(aggregated.submission_ids::TEXT[], ',')
    ) AS conflict_key,
    aggregated.paper_id,
    aggregated.submission_count,
    aggregated.reviewer_count,
    aggregated.distinct_decision_count,
    aggregated.distinct_payload_count,
    CASE
        WHEN aggregated.distinct_decision_count > 1 AND aggregated.distinct_payload_count > 1 THEN 'decision_and_payload_mismatch'
        WHEN aggregated.distinct_decision_count > 1 THEN 'decision_mismatch'
        ELSE 'payload_mismatch'
    END AS conflict_kind,
    aggregated.latest_submitted_at,
    aggregated.submission_ids,
    aggregated.submission_summaries,
    COALESCE(resolution.status, 'open') AS resolution_status,
    resolution.winning_submission_id,
    resolution.decision_kind AS resolution_decision_kind,
    resolution.resolution_note,
    resolution.resolved_by,
    resolution.resolved_at,
    resolution.updated_at AS resolution_updated_at
FROM aggregated
LEFT JOIN paper_conflict_resolutions resolution
  ON resolution.paper_id = aggregated.paper_id
WHERE aggregated.submission_count >= 2
  AND (
      aggregated.distinct_decision_count > 1
      OR aggregated.distinct_payload_count > 1
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
    model_name TEXT NOT NULL DEFAULT 'gemini-3.5-flash',
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
        OR route_destination IN ('human_review', 'finalized', 'blocked', 'next_stage', 'provisional_skip')
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
    stage_order INTEGER NOT NULL DEFAULT 0,
    next_stage_on_has_data TEXT,
    fallback_model_names JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(fallback_model_names) = 'array'),
    no_data_route_destination TEXT NOT NULL DEFAULT 'human_review'
        CHECK (no_data_route_destination IN ('human_review', 'finalized', 'blocked', 'next_stage', 'provisional_skip')),
    model_input_mode TEXT NOT NULL DEFAULT 'text',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE routing_stage_configs
    ADD COLUMN IF NOT EXISTS stage_order INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS next_stage_on_has_data TEXT,
    ADD COLUMN IF NOT EXISTS fallback_model_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS no_data_route_destination TEXT NOT NULL DEFAULT 'human_review',
    -- 'text' = pdftotext output only; 'pdf' = native PDF document part so a
    -- capable model reads pages/tables and reports the true PDF page number.
    ADD COLUMN IF NOT EXISTS model_input_mode TEXT NOT NULL DEFAULT 'text';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'routing_stage_configs'
          AND constraint_name = 'routing_stage_configs_model_input_mode_check'
    ) THEN
        ALTER TABLE routing_stage_configs
            DROP CONSTRAINT routing_stage_configs_model_input_mode_check;
    END IF;
END $$;

ALTER TABLE routing_stage_configs
    ADD CONSTRAINT routing_stage_configs_model_input_mode_check
    CHECK (model_input_mode IN ('text', 'pdf'));

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'routing_stage_configs'
          AND constraint_name = 'routing_stage_configs_no_data_route_destination_check'
    ) THEN
        ALTER TABLE routing_stage_configs
            DROP CONSTRAINT routing_stage_configs_no_data_route_destination_check;
    END IF;
END $$;

ALTER TABLE routing_stage_configs
    ADD CONSTRAINT routing_stage_configs_no_data_route_destination_check
    CHECK (no_data_route_destination IN ('human_review', 'finalized', 'blocked', 'next_stage', 'provisional_skip'));

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'routing_stage_configs'
          AND constraint_name = 'routing_stage_configs_fallback_model_names_array_check'
    ) THEN
        ALTER TABLE routing_stage_configs
            DROP CONSTRAINT routing_stage_configs_fallback_model_names_array_check;
    END IF;
END $$;

ALTER TABLE routing_stage_configs
    ADD CONSTRAINT routing_stage_configs_fallback_model_names_array_check
    CHECK (jsonb_typeof(fallback_model_names) = 'array');

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
    fallback_model_names,
    prompt_version,
    active,
    positive_threshold,
    negative_threshold,
    audit_rate,
    next_stage_on_low_confidence,
    counts_as_truth,
    stage_order,
    next_stage_on_has_data,
    no_data_route_destination
)
VALUES (
    'gemini_flash_triage_v1',
    'ai_model',
    'Gemini Flash Triage v1',
    'gemini-3-flash-preview',
    '[]'::jsonb,
    'gemini_flash_triage_v1',
    FALSE,
    1.0,
    1.0,
    0.05,
    'human_review',
    FALSE,
    5,
    NULL,
    'human_review'
)
ON CONFLICT (stage_key) DO UPDATE
SET
    stage_kind = EXCLUDED.stage_kind,
    display_name = EXCLUDED.display_name,
    model_name = EXCLUDED.model_name,
    fallback_model_names = EXCLUDED.fallback_model_names,
    prompt_version = EXCLUDED.prompt_version,
    active = FALSE,
    stage_order = EXCLUDED.stage_order,
    next_stage_on_has_data = EXCLUDED.next_stage_on_has_data,
    next_stage_on_low_confidence = EXCLUDED.next_stage_on_low_confidence,
    no_data_route_destination = EXCLUDED.no_data_route_destination,
    updated_at = NOW();

UPDATE routing_stage_configs
SET
    active = FALSE,
    updated_at = NOW()
WHERE active IS TRUE;

INSERT INTO routing_stage_configs (
    stage_key,
    stage_kind,
    display_name,
    model_name,
    fallback_model_names,
    prompt_version,
    active,
    positive_threshold,
    negative_threshold,
    audit_rate,
    next_stage_on_low_confidence,
    counts_as_truth,
    stage_order,
    next_stage_on_has_data,
    no_data_route_destination
)
VALUES (
    'gemini_flash_db_payload_v2',
    'ai_model',
    'Gemini Flash DB Payload v2',
    'gemini-3.5-flash',
    '[]'::jsonb,
    'opennutri_evidence_payload_v2',
    FALSE,
    1.0,
    1.0,
    0.05,
    'human_review',
    FALSE,
    20,
    NULL,
    'provisional_skip'
)
ON CONFLICT (stage_key) DO UPDATE
SET
    stage_kind = EXCLUDED.stage_kind,
    display_name = EXCLUDED.display_name,
    model_name = EXCLUDED.model_name,
    fallback_model_names = EXCLUDED.fallback_model_names,
    prompt_version = EXCLUDED.prompt_version,
    active = FALSE,
    stage_order = EXCLUDED.stage_order,
    next_stage_on_has_data = EXCLUDED.next_stage_on_has_data,
    next_stage_on_low_confidence = EXCLUDED.next_stage_on_low_confidence,
    no_data_route_destination = EXCLUDED.no_data_route_destination,
    updated_at = NOW();

INSERT INTO routing_stage_configs (
    stage_key,
    stage_kind,
    display_name,
    model_name,
    fallback_model_names,
    prompt_version,
    active,
    positive_threshold,
    negative_threshold,
    audit_rate,
    next_stage_on_low_confidence,
    counts_as_truth,
    stage_order,
    next_stage_on_has_data,
    no_data_route_destination
)
VALUES (
    'gemini_flash_lite_triage_v1',
    'ai_model',
    'Gemini Flash-Lite Triage v1',
    'gemini-3.1-flash-lite',
    '[]'::jsonb,
    'opennutri_evidence_payload_v2',
    FALSE,
    1.0,
    1.0,
    0.05,
    'gemini_flash_db_payload_v2',
    FALSE,
    15,
    'gemini_flash_db_payload_v2',
    'provisional_skip'
)
ON CONFLICT (stage_key) DO UPDATE
SET
    stage_kind = EXCLUDED.stage_kind,
    display_name = EXCLUDED.display_name,
    model_name = EXCLUDED.model_name,
    fallback_model_names = EXCLUDED.fallback_model_names,
    prompt_version = EXCLUDED.prompt_version,
    active = FALSE,
    stage_order = EXCLUDED.stage_order,
    next_stage_on_has_data = EXCLUDED.next_stage_on_has_data,
    next_stage_on_low_confidence = EXCLUDED.next_stage_on_low_confidence,
    no_data_route_destination = EXCLUDED.no_data_route_destination,
    updated_at = NOW();

INSERT INTO routing_stage_configs (
    stage_key,
    stage_kind,
    display_name,
    model_name,
    fallback_model_names,
    prompt_version,
    active,
    positive_threshold,
    negative_threshold,
    audit_rate,
    next_stage_on_low_confidence,
    counts_as_truth,
    stage_order,
    next_stage_on_has_data,
    no_data_route_destination
)
VALUES (
    'gemma_proof_extraction_v1',
    'ai_model',
    'Gemma Proof Extraction v1',
    'gemma-4-31b-it',
    '["gemma-4-26b-a4b-it"]'::jsonb,
    'opennutri_evidence_payload_v2',
    TRUE,
    1.0,
    1.0,
    0.02,
    'gemini_flash_lite_triage_v1',
    FALSE,
    10,
    'gemini_flash_lite_triage_v1',
    'provisional_skip'
)
ON CONFLICT (stage_key) DO UPDATE
SET
    stage_kind = EXCLUDED.stage_kind,
    display_name = EXCLUDED.display_name,
    model_name = EXCLUDED.model_name,
    fallback_model_names = EXCLUDED.fallback_model_names,
    prompt_version = EXCLUDED.prompt_version,
    active = TRUE,
    stage_order = EXCLUDED.stage_order,
    next_stage_on_has_data = EXCLUDED.next_stage_on_has_data,
    next_stage_on_low_confidence = EXCLUDED.next_stage_on_low_confidence,
    no_data_route_destination = EXCLUDED.no_data_route_destination,
    updated_at = NOW();

-- Gemini stages read the PDF natively (pages/tables + true PDF page numbers);
-- Gemma screening stays on text + injected PDF page markers.
UPDATE routing_stage_configs
SET model_input_mode = 'pdf', updated_at = NOW()
WHERE model_name LIKE 'gemini%';

UPDATE routing_stage_configs
SET model_input_mode = 'text', updated_at = NOW()
WHERE model_name LIKE 'gemma%';

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
    ADD COLUMN IF NOT EXISTS training_weight REAL DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS label_submission_id UUID REFERENCES paper_label_submissions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS label_approval_id UUID REFERENCES paper_label_approvals(id) ON DELETE SET NULL;

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
    CHECK (resolution_source IN (
        'slot_agreement',
        'conflict_resolution',
        'global_skip',
        'ai_high_confidence',
        'reviewer_direct_submit',
        'reviewer_approval'
    ));

ALTER TABLE paper_review_outcomes
    ADD CONSTRAINT paper_review_outcomes_truth_source_kind_check
    CHECK (truth_source_kind IN ('human_review', 'ai_model'));

INSERT INTO reviewer_slots (slot_key, display_name, is_official)
VALUES
    ('arciel', 'Arciel Lane', TRUE),
    ('peri', 'Peri', TRUE),
    ('aleyna', 'Aleyna', TRUE),
    ('aysegul', 'Aysegul Independent', FALSE)
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
    can_approve_labels,
    priority_weight_en,
    priority_weight_tr
)
SELECT
    lower(trim(email)),
    CASE lower(trim(email))
        WHEN 'baezarciel@gmail.com' THEN 'Arciel'
        WHEN 'ayseguldogann99@gmail.com' THEN 'Aysegul'
        WHEN 'dainesalazarromero@gmail.com' THEN 'Daine'
        WHEN 'periacikgoz22@gmail.com' THEN 'Peri'
        WHEN 'ozcnaleyna2@gmail.com' THEN 'Aleyna'
        ELSE split_part(lower(trim(email)), '@', 1)
    END,
    TRUE,
    TRUE,
    CASE lower(trim(email))
        WHEN 'dainesalazarromero@gmail.com' THEN FALSE
        ELSE TRUE
    END,
    CASE lower(trim(email))
        WHEN 'baezarciel@gmail.com' THEN 'arciel'
        WHEN 'periacikgoz22@gmail.com' THEN 'peri'
        WHEN 'ozcnaleyna2@gmail.com' THEN 'aleyna'
        WHEN 'ayseguldogann99@gmail.com' THEN 'aysegul'
        ELSE NULL
    END,
    CASE lower(trim(email))
        WHEN 'baezarciel@gmail.com' THEN TRUE
        ELSE FALSE
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
    can_approve_labels = reviewer_profiles.can_approve_labels OR EXCLUDED.can_approve_labels,
    priority_weight_en = EXCLUDED.priority_weight_en,
    priority_weight_tr = EXCLUDED.priority_weight_tr,
    updated_at = NOW();

ALTER TABLE IF EXISTS allowed_auth_emails ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE allowed_auth_emails FROM anon, authenticated, public;
GRANT ALL ON TABLE allowed_auth_emails TO service_role;

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
    reviewer_slots.is_official,
    reviewer_profiles.active
FROM reviewer_profiles
JOIN reviewer_slots
    ON reviewer_slots.slot_key = reviewer_profiles.official_slot
WHERE reviewer_profiles.official_slot IS NOT NULL
ON CONFLICT (slot_key, reviewer_profile_id) DO UPDATE
SET
    member_role = EXCLUDED.member_role,
    can_review_en = EXCLUDED.can_review_en,
    can_review_tr = EXCLUDED.can_review_tr,
    counts_toward_official = EXCLUDED.counts_toward_official,
    active = EXCLUDED.active;

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
    'arciel',
    reviewer_profiles.id,
    'shadow',
    TRUE,
    FALSE,
    FALSE,
    reviewer_profiles.active
FROM reviewer_profiles
WHERE reviewer_profiles.email = 'dainesalazarromero@gmail.com'
ON CONFLICT (slot_key, reviewer_profile_id) DO UPDATE
SET
    member_role = 'shadow',
    can_review_en = TRUE,
    can_review_tr = FALSE,
    counts_toward_official = FALSE,
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
CREATE INDEX IF NOT EXISTS idx_paper_label_submissions_paper_status ON paper_label_submissions(paper_id, status, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_label_submissions_reviewer_status ON paper_label_submissions(reviewer_profile_id, status, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_label_submissions_hash ON paper_label_submissions(payload_hash);
CREATE INDEX IF NOT EXISTS idx_paper_label_approvals_submission ON paper_label_approvals(label_submission_id);
CREATE INDEX IF NOT EXISTS idx_paper_label_approvals_approver ON paper_label_approvals(approver_profile_id, approved_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_conflicts_paper_status ON paper_conflicts(paper_id, status, conflict_type);
CREATE INDEX IF NOT EXISTS idx_paper_conflict_resolutions_paper_status
    ON paper_conflict_resolutions(paper_id, status, updated_at DESC);
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
CREATE INDEX IF NOT EXISTS idx_paper_stage_tasks_status_stage_attempts_created
    ON paper_stage_tasks(status, stage_key, attempt_count, priority DESC, created_at, id);
CREATE INDEX IF NOT EXISTS idx_paper_stage_tasks_paper ON paper_stage_tasks(paper_id, stage_key);
CREATE INDEX IF NOT EXISTS idx_ai_extractions_stage_paper ON ai_extractions(stage_key, paper_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_extractions_route_destination ON ai_extractions(route_destination, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_annotations_assignment_unique
    ON annotations(paper_user_assignment_id)
    WHERE paper_user_assignment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_paper_label_events_assignment ON paper_label_events(paper_user_assignment_id, created_at DESC);

-- Clean break for the general queue workflow: old slot/user rows remain as
-- historical audit data, but unresolved slot assignments no longer drive work.
UPDATE paper_slot_assignments
SET
    status = 'cancelled',
    official_submission_id = NULL,
    resolved_at = COALESCE(resolved_at, NOW())
WHERE status IN ('pending', 'submitted', 'conflict');

UPDATE paper_user_assignments
SET
    status = 'cancelled',
    resolved_at = COALESCE(resolved_at, NOW())
WHERE status IN ('assigned', 'draft', 'submitted', 'conflict');

UPDATE paper_conflicts
SET
    status = 'cancelled',
    resolved_at = COALESCE(resolved_at, NOW())
WHERE status = 'open';

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
        ORDER BY attempt_count ASC, priority DESC, created_at ASC, id ASC
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
        WHERE (cockpit_access IS TRUE OR tester_access IS TRUE)
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

CREATE OR REPLACE FUNCTION public.current_user_can_approve_labels()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT public.current_user_can_write()
       AND EXISTS (
            SELECT 1
            FROM reviewer_profiles
            WHERE can_approve_labels IS TRUE
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

DROP FUNCTION IF EXISTS public.upsert_reviewer_admin_config(
    TEXT, TEXT, BOOLEAN, BOOLEAN, BOOLEAN, TEXT, TEXT[], BOOLEAN, REAL, REAL, TEXT
);
DROP FUNCTION IF EXISTS public.upsert_reviewer_admin_config(
    TEXT, TEXT, BOOLEAN, BOOLEAN, BOOLEAN, BOOLEAN, TEXT, TEXT[], BOOLEAN, REAL, REAL, TEXT
);

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
    p_can_approve_labels BOOLEAN DEFAULT FALSE,
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
        can_approve_labels,
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
        coalesce(p_can_approve_labels, FALSE),
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
        can_approve_labels = EXCLUDED.can_approve_labels,
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
            'raw_food_name', NULLIF(public.normalize_submission_text(fi.raw_food_name), ''),
            'preparation_state', NULLIF(public.normalize_submission_text(fi.preparation_state), ''),
            'nutrients', COALESCE((
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'nutrient_id', anv.nutrient_id,
                        'is_custom_nutrient', COALESCE(anv.is_custom_nutrient, anv.nutrient_id IS NULL),
                        'nutrient_name', public.normalize_submission_text(anv.nutrient_name),
                        'raw_nutrient_name', NULLIF(public.normalize_submission_text(anv.raw_nutrient_name), ''),
                        'value', CASE
                            WHEN anv.value IS NULL THEN NULL
                            ELSE round(anv.value::numeric, 6)
                        END,
                        'unit', public.normalize_submission_text(anv.unit),
                        'basis', public.normalize_submission_text(COALESCE(anv.basis, 'per_100g')),
                        'sample_size', anv.sample_size,
                        'confidence', CASE
                            WHEN anv.confidence IS NULL THEN NULL
                            ELSE round(anv.confidence::numeric, 6)
                        END,
                        'source_citation', NULLIF(public.normalize_submission_text(anv.source_citation), ''),
                        'metadata', COALESCE(anv.metadata, '{}'::jsonb)
                    )
                    ORDER BY
                        coalesce(anv.nutrient_id::text, ''),
                        COALESCE(anv.is_custom_nutrient, anv.nutrient_id IS NULL),
                        public.normalize_submission_text(anv.nutrient_name),
                        public.normalize_submission_text(anv.raw_nutrient_name),
                        public.normalize_submission_text(anv.unit),
                        public.normalize_submission_text(COALESCE(anv.basis, 'per_100g')),
                        CASE
                            WHEN anv.value IS NULL THEN NULL
                            ELSE round(anv.value::numeric, 6)
                        END,
                        anv.sample_size,
                        CASE
                            WHEN anv.confidence IS NULL THEN NULL
                            ELSE round(anv.confidence::numeric, 6)
                        END,
                        public.normalize_submission_text(anv.source_citation),
                        COALESCE(anv.metadata, '{}'::jsonb)::text,
                        anv.id
                )
                FROM annotation_nutrient_values anv
                WHERE anv.food_item_id = fi.id
            ), '[]'::jsonb)
        ) AS payload
    FROM food_items fi
    WHERE fi.annotation_id = p_annotation_id
      AND EXISTS (
          SELECT 1
          FROM annotation_nutrient_values anv_exists
          WHERE anv_exists.food_item_id = fi.id
      )
)
SELECT jsonb_build_object(
    'decision_kind', p_decision_kind,
    'food_items', COALESCE((
        SELECT jsonb_agg(payload ORDER BY food_name_sort, food_id_sort, custom_sort, id)
        FROM ordered_foods
    ), '[]'::jsonb)
);
$$;

CREATE OR REPLACE FUNCTION public.build_label_payload_diff(
    p_original_payload JSONB,
    p_final_payload JSONB
)
RETURNS JSONB
LANGUAGE sql
STABLE
AS $$
WITH
original_foods AS (
    SELECT
        lower(public.normalize_submission_text(value ->> 'food_name')) || '|' ||
            coalesce(value ->> 'food_fdc_id', '') || '|' ||
            coalesce(value ->> 'is_custom_food', '') || '|' ||
            lower(public.normalize_submission_text(value ->> 'raw_food_name')) || '|' ||
            lower(public.normalize_submission_text(value ->> 'preparation_state')) AS food_key,
        value AS food
    FROM jsonb_array_elements(coalesce(p_original_payload -> 'food_items', '[]'::jsonb)) AS value
),
final_foods AS (
    SELECT
        lower(public.normalize_submission_text(value ->> 'food_name')) || '|' ||
            coalesce(value ->> 'food_fdc_id', '') || '|' ||
            coalesce(value ->> 'is_custom_food', '') || '|' ||
            lower(public.normalize_submission_text(value ->> 'raw_food_name')) || '|' ||
            lower(public.normalize_submission_text(value ->> 'preparation_state')) AS food_key,
        value AS food
    FROM jsonb_array_elements(coalesce(p_final_payload -> 'food_items', '[]'::jsonb)) AS value
),
original_nutrients AS (
    SELECT
        food_key,
        jsonb_build_object(
            'food_name', food ->> 'food_name',
            'food_fdc_id', food ->> 'food_fdc_id',
            'is_custom_food', food -> 'is_custom_food',
            'raw_food_name', food ->> 'raw_food_name',
            'preparation_state', food ->> 'preparation_state',
            'nutrient_id', nutrient ->> 'nutrient_id',
            'is_custom_nutrient', nutrient -> 'is_custom_nutrient',
            'nutrient_name', public.normalize_submission_text(nutrient ->> 'nutrient_name'),
            'raw_nutrient_name', public.normalize_submission_text(nutrient ->> 'raw_nutrient_name'),
            'value', nutrient -> 'value',
            'unit', public.normalize_submission_text(nutrient ->> 'unit'),
            'basis', public.normalize_submission_text(nutrient ->> 'basis'),
            'sample_size', nutrient -> 'sample_size',
            'confidence', nutrient -> 'confidence',
            'source_citation', public.normalize_submission_text(nutrient ->> 'source_citation'),
            'metadata', coalesce(nutrient -> 'metadata', '{}'::jsonb)
        ) AS nutrient_row,
        lower(public.normalize_submission_text(food ->> 'food_name')) || '|' ||
            coalesce(food ->> 'food_fdc_id', '') || '|' ||
            coalesce(food ->> 'is_custom_food', '') || '|' ||
            lower(public.normalize_submission_text(food ->> 'raw_food_name')) || '|' ||
            lower(public.normalize_submission_text(food ->> 'preparation_state')) || '|' ||
            coalesce(nutrient ->> 'nutrient_id', '') || '|' ||
            coalesce(nutrient ->> 'is_custom_nutrient', '') || '|' ||
            lower(public.normalize_submission_text(nutrient ->> 'nutrient_name')) || '|' ||
            lower(public.normalize_submission_text(nutrient ->> 'raw_nutrient_name')) || '|' ||
            public.normalize_submission_text(nutrient ->> 'unit') || '|' ||
            public.normalize_submission_text(nutrient ->> 'basis') || '|' ||
            coalesce((nutrient -> 'value')::text, '') || '|' ||
            coalesce((nutrient -> 'sample_size')::text, '') || '|' ||
            coalesce((nutrient -> 'confidence')::text, '') || '|' ||
            lower(public.normalize_submission_text(nutrient ->> 'source_citation')) || '|' ||
            coalesce((nutrient -> 'metadata')::text, '') AS nutrient_key
    FROM original_foods
    CROSS JOIN LATERAL jsonb_array_elements(coalesce(food -> 'nutrients', '[]'::jsonb)) AS nutrient
),
final_nutrients AS (
    SELECT
        food_key,
        jsonb_build_object(
            'food_name', food ->> 'food_name',
            'food_fdc_id', food ->> 'food_fdc_id',
            'is_custom_food', food -> 'is_custom_food',
            'raw_food_name', food ->> 'raw_food_name',
            'preparation_state', food ->> 'preparation_state',
            'nutrient_id', nutrient ->> 'nutrient_id',
            'is_custom_nutrient', nutrient -> 'is_custom_nutrient',
            'nutrient_name', public.normalize_submission_text(nutrient ->> 'nutrient_name'),
            'raw_nutrient_name', public.normalize_submission_text(nutrient ->> 'raw_nutrient_name'),
            'value', nutrient -> 'value',
            'unit', public.normalize_submission_text(nutrient ->> 'unit'),
            'basis', public.normalize_submission_text(nutrient ->> 'basis'),
            'sample_size', nutrient -> 'sample_size',
            'confidence', nutrient -> 'confidence',
            'source_citation', public.normalize_submission_text(nutrient ->> 'source_citation'),
            'metadata', coalesce(nutrient -> 'metadata', '{}'::jsonb)
        ) AS nutrient_row,
        lower(public.normalize_submission_text(food ->> 'food_name')) || '|' ||
            coalesce(food ->> 'food_fdc_id', '') || '|' ||
            coalesce(food ->> 'is_custom_food', '') || '|' ||
            lower(public.normalize_submission_text(food ->> 'raw_food_name')) || '|' ||
            lower(public.normalize_submission_text(food ->> 'preparation_state')) || '|' ||
            coalesce(nutrient ->> 'nutrient_id', '') || '|' ||
            coalesce(nutrient ->> 'is_custom_nutrient', '') || '|' ||
            lower(public.normalize_submission_text(nutrient ->> 'nutrient_name')) || '|' ||
            lower(public.normalize_submission_text(nutrient ->> 'raw_nutrient_name')) || '|' ||
            public.normalize_submission_text(nutrient ->> 'unit') || '|' ||
            public.normalize_submission_text(nutrient ->> 'basis') || '|' ||
            coalesce((nutrient -> 'value')::text, '') || '|' ||
            coalesce((nutrient -> 'sample_size')::text, '') || '|' ||
            coalesce((nutrient -> 'confidence')::text, '') || '|' ||
            lower(public.normalize_submission_text(nutrient ->> 'source_citation')) || '|' ||
            coalesce((nutrient -> 'metadata')::text, '') AS nutrient_key
    FROM final_foods
    CROSS JOIN LATERAL jsonb_array_elements(coalesce(food -> 'nutrients', '[]'::jsonb)) AS nutrient
),
missing_foods AS (
    SELECT coalesce(jsonb_agg(food ORDER BY food_key), '[]'::jsonb) AS rows
    FROM original_foods original
    WHERE NOT EXISTS (
        SELECT 1 FROM final_foods final WHERE final.food_key = original.food_key
    )
),
added_foods AS (
    SELECT coalesce(jsonb_agg(food ORDER BY food_key), '[]'::jsonb) AS rows
    FROM final_foods final
    WHERE NOT EXISTS (
        SELECT 1 FROM original_foods original WHERE original.food_key = final.food_key
    )
),
missing_nutrients AS (
    SELECT coalesce(jsonb_agg(nutrient_row ORDER BY food_key, nutrient_key), '[]'::jsonb) AS rows
    FROM original_nutrients original
    WHERE NOT EXISTS (
        SELECT 1 FROM final_nutrients final WHERE final.nutrient_key = original.nutrient_key
    )
),
added_nutrients AS (
    SELECT coalesce(jsonb_agg(nutrient_row ORDER BY food_key, nutrient_key), '[]'::jsonb) AS rows
    FROM final_nutrients final
    WHERE NOT EXISTS (
        SELECT 1 FROM original_nutrients original WHERE original.nutrient_key = final.nutrient_key
    )
)
SELECT jsonb_build_object(
    'decision_changed', coalesce(p_original_payload ->> 'decision_kind', '') <> coalesce(p_final_payload ->> 'decision_kind', ''),
    'original_decision_kind', p_original_payload ->> 'decision_kind',
    'final_decision_kind', p_final_payload ->> 'decision_kind',
    'original_food_count', jsonb_array_length(coalesce(p_original_payload -> 'food_items', '[]'::jsonb)),
    'final_food_count', jsonb_array_length(coalesce(p_final_payload -> 'food_items', '[]'::jsonb)),
    'missing_foods', (SELECT rows FROM missing_foods),
    'added_foods', (SELECT rows FROM added_foods),
    'missing_nutrient_rows', (SELECT rows FROM missing_nutrients),
    'added_nutrient_rows', (SELECT rows FROM added_nutrients)
);
$$;

CREATE OR REPLACE FUNCTION public.get_general_queue_papers(
    p_limit INTEGER DEFAULT 250
)
RETURNS SETOF papers
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Authentication required';
    END IF;

    RETURN QUERY
    SELECT p.*
    FROM papers p
    JOIN ai_extractions latest_ai
      ON latest_ai.id = p.latest_ai_extraction_id
    WHERE p.routing_status = 'human_review_ready'
      AND p.workflow_language IN ('en', 'tr')
      AND p.pdf_url IS NOT NULL
      AND btrim(p.pdf_url) <> ''
      AND latest_ai.normalized_payload_json ->> 'decision_kind' = 'has_data'
      AND NOT EXISTS (
          SELECT 1
          FROM paper_review_outcomes outcome
          WHERE outcome.paper_id = p.id
      )
      AND NOT EXISTS (
          SELECT 1
          FROM paper_label_submissions submission
          WHERE submission.paper_id = p.id
            AND submission.status IN ('pending_approval', 'accepted')
      )
      AND NOT EXISTS (
          SELECT 1
          FROM paper_slot_assignments legacy_assignment
          WHERE legacy_assignment.paper_id = p.id
            AND legacy_assignment.status NOT IN ('resolved', 'cancelled')
      )
      AND NOT EXISTS (
          SELECT 1
          FROM paper_global_labels global_label
          WHERE global_label.paper_id = p.id
            AND global_label.label = 'definitely_no_data'
      )
    ORDER BY p.routing_updated_at NULLS FIRST, p.created_at, p.id
    LIMIT greatest(1, least(coalesce(p_limit, 250), 1000));
END;
$$;

CREATE OR REPLACE FUNCTION public.get_cockpit_ai_extractions(
    p_limit INTEGER DEFAULT 5000
)
RETURNS TABLE (
    id UUID,
    paper_id INTEGER,
    model_name TEXT,
    is_useful BOOLEAN,
    overall_confidence REAL,
    status TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    stage_key TEXT,
    prompt_version TEXT,
    normalized_payload_json JSONB,
    positive_threshold_snapshot REAL,
    negative_threshold_snapshot REAL,
    routing_bucket TEXT,
    route_destination TEXT,
    audit_sampled BOOLEAN,
    finalized_without_human BOOLEAN,
    raw_data JSONB
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF NOT (
        public.current_user_has_cockpit_access()
        OR public.current_user_can_approve_labels()
    ) THEN
        RAISE EXCEPTION 'Cockpit access required';
    END IF;

    RETURN QUERY
    SELECT
        extraction.id,
        extraction.paper_id,
        extraction.model_name,
        extraction.is_useful,
        extraction.overall_confidence,
        extraction.status,
        extraction.created_at,
        extraction.updated_at,
        extraction.stage_key,
        extraction.prompt_version,
        extraction.normalized_payload_json,
        extraction.positive_threshold_snapshot,
        extraction.negative_threshold_snapshot,
        extraction.routing_bucket,
        extraction.route_destination,
        extraction.audit_sampled,
        extraction.finalized_without_human,
        jsonb_build_object(
            'normalization_summary',
            coalesce(extraction.raw_data -> 'normalization_summary', '{}'::jsonb)
        ) AS raw_data
    FROM ai_extractions extraction
    ORDER BY extraction.created_at DESC
    LIMIT greatest(1, least(coalesce(p_limit, 5000), 5000));
END;
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
    FROM paper_slot_assignments psa
    WHERE psa.paper_id = p_paper_id
      AND EXISTS (
          SELECT 1
          FROM reviewer_slots rs
          WHERE rs.slot_key = psa.slot_key
            AND rs.is_official IS TRUE
      )
    ORDER BY psa.slot_key
    LIMIT 1;

    SELECT *
    INTO v_slot_two
    FROM paper_slot_assignments psa
    WHERE psa.paper_id = p_paper_id
      AND EXISTS (
          SELECT 1
          FROM reviewer_slots rs
          WHERE rs.slot_key = psa.slot_key
            AND rs.is_official IS TRUE
      )
    ORDER BY psa.slot_key
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
        WHERE paper_id = p_paper_id
          AND EXISTS (
              SELECT 1
              FROM reviewer_slots
              WHERE reviewer_slots.slot_key = paper_slot_assignments.slot_key
                AND reviewer_slots.is_official IS TRUE
          );

        UPDATE paper_user_assignments
        SET
            status = 'resolved',
            resolved_at = NOW()
        WHERE paper_id = p_paper_id
          AND status <> 'cancelled'
          AND EXISTS (
              SELECT 1
              FROM paper_slot_assignments
              JOIN reviewer_slots
                ON reviewer_slots.slot_key = paper_slot_assignments.slot_key
              WHERE paper_slot_assignments.id = paper_user_assignments.paper_slot_assignment_id
                AND reviewer_slots.is_official IS TRUE
          );

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
        WHERE paper_id = p_paper_id
          AND EXISTS (
              SELECT 1
              FROM reviewer_slots
              WHERE reviewer_slots.slot_key = paper_slot_assignments.slot_key
                AND reviewer_slots.is_official IS TRUE
          );

        UPDATE paper_user_assignments
        SET
            status = 'resolved',
            resolved_at = NOW()
        WHERE paper_id = p_paper_id
          AND status <> 'cancelled'
          AND EXISTS (
              SELECT 1
              FROM paper_slot_assignments
              JOIN reviewer_slots
                ON reviewer_slots.slot_key = paper_slot_assignments.slot_key
              WHERE paper_slot_assignments.id = paper_user_assignments.paper_slot_assignment_id
                AND reviewer_slots.is_official IS TRUE
          );
        RETURN;
    END IF;

    UPDATE paper_slot_assignments
    SET status = 'conflict'
    WHERE paper_id = p_paper_id
      AND status <> 'cancelled'
      AND EXISTS (
          SELECT 1
          FROM reviewer_slots
          WHERE reviewer_slots.slot_key = paper_slot_assignments.slot_key
            AND reviewer_slots.is_official IS TRUE
      );

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
    v_nutrient_count INTEGER;
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
        FROM food_items fi
        WHERE fi.annotation_id = v_annotation.id
          AND EXISTS (
              SELECT 1
              FROM annotation_nutrient_values anv
              WHERE anv.food_item_id = fi.id
          );

        SELECT COUNT(*)
        INTO v_nutrient_count
        FROM annotation_nutrient_values anv
        JOIN food_items fi ON fi.id = anv.food_item_id
        WHERE fi.annotation_id = v_annotation.id;

        IF v_food_count <= 0 OR v_nutrient_count <= 0 THEN
            RAISE EXCEPTION 'Cannot submit has_data without at least one food item with nutrient rows';
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

CREATE OR REPLACE FUNCTION public.submit_general_label(
    p_annotation_id INTEGER,
    p_decision_kind TEXT,
    p_submission_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS paper_label_submissions
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_profile reviewer_profiles;
    v_annotation annotations;
    v_payload_json JSONB;
    v_payload_text TEXT;
    v_payload_hash TEXT;
    v_submission paper_label_submissions;
    v_approval paper_label_approvals;
    v_food_count INTEGER;
    v_nutrient_count INTEGER;
BEGIN
    IF p_decision_kind NOT IN ('has_data', 'no_usable_data') THEN
        RAISE EXCEPTION 'Unsupported decision kind: %', p_decision_kind;
    END IF;

    IF NOT public.current_user_can_write() THEN
        RAISE EXCEPTION 'Read-only accounts cannot submit labels';
    END IF;

    SELECT *
    INTO v_profile
    FROM reviewer_profiles
    WHERE active IS TRUE
      AND (
          auth_user_id = auth.uid()
          OR (
              email IS NOT NULL
              AND email = public.current_auth_email()
          )
      )
    ORDER BY updated_at DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Reviewer profile not found';
    END IF;

    SELECT *
    INTO v_annotation
    FROM annotations
    WHERE id = p_annotation_id
      AND user_id = auth.uid()
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Annotation not found for current user';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM paper_review_outcomes
        WHERE paper_id = v_annotation.paper_id
    ) THEN
        RAISE EXCEPTION 'Paper already has a final outcome';
    END IF;

    IF p_decision_kind = 'has_data' THEN
        SELECT COUNT(*)
        INTO v_food_count
        FROM food_items fi
        WHERE fi.annotation_id = v_annotation.id
          AND EXISTS (
              SELECT 1
              FROM annotation_nutrient_values anv
              WHERE anv.food_item_id = fi.id
          );

        SELECT COUNT(*)
        INTO v_nutrient_count
        FROM annotation_nutrient_values anv
        JOIN food_items fi ON fi.id = anv.food_item_id
        WHERE fi.annotation_id = v_annotation.id;

        IF v_food_count <= 0 OR v_nutrient_count <= 0 THEN
            RAISE EXCEPTION 'Cannot submit has_data without at least one food item with nutrient rows';
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

    INSERT INTO paper_label_submissions (
        paper_id,
        reviewer_profile_id,
        auth_user_id,
        annotation_id,
        decision_kind,
        payload_json,
        payload_text,
        payload_hash,
        submission_metadata,
        status
    )
    VALUES (
        v_annotation.paper_id,
        v_profile.id,
        auth.uid(),
        v_annotation.id,
        p_decision_kind,
        v_payload_json,
        v_payload_text,
        v_payload_hash,
        coalesce(p_submission_metadata, '{}'::jsonb),
        CASE
            WHEN public.current_user_can_approve_labels() THEN 'accepted'
            ELSE 'pending_approval'
        END
    )
    RETURNING * INTO v_submission;

    UPDATE annotations
    SET
        has_data = (p_decision_kind = 'has_data'),
        status = CASE
            WHEN p_decision_kind = 'has_data' THEN 'done'
            ELSE 'skipped'
        END,
        updated_at = NOW()
    WHERE id = v_annotation.id;

    IF public.current_user_can_approve_labels() THEN
        INSERT INTO paper_label_approvals (
            paper_id,
            label_submission_id,
            approver_profile_id,
            approver_auth_user_id,
            approval_annotation_id,
            decision_kind,
            payload_json,
            payload_text,
            payload_hash,
            correction_diff_json,
            approval_note
        )
        VALUES (
            v_submission.paper_id,
            v_submission.id,
            v_profile.id,
            auth.uid(),
            v_annotation.id,
            v_submission.decision_kind,
            v_submission.payload_json,
            v_submission.payload_text,
            v_submission.payload_hash,
            public.build_label_payload_diff(v_submission.payload_json, v_submission.payload_json),
            'Direct reviewer submission'
        )
        RETURNING * INTO v_approval;

        UPDATE paper_label_submissions
        SET
            status = CASE
                WHEN id = v_submission.id THEN 'accepted'
                ELSE 'superseded'
            END,
            reviewed_at = NOW()
        WHERE paper_id = v_submission.paper_id
          AND status IN ('pending_approval', 'accepted');

        INSERT INTO paper_review_outcomes (
            paper_id,
            decision_kind,
            resolution_source,
            payload_json,
            payload_text,
            payload_hash,
            resolved_by,
            resolved_at,
            updated_at,
            truth_source_kind,
            training_weight,
            label_submission_id,
            label_approval_id
        )
        VALUES (
            v_submission.paper_id,
            v_submission.decision_kind,
            'reviewer_direct_submit',
            v_submission.payload_json,
            v_submission.payload_text,
            v_submission.payload_hash,
            auth.uid(),
            NOW(),
            NOW(),
            'human_review',
            1.0,
            v_submission.id,
            v_approval.id
        );
    END IF;

    RETURN v_submission;
END;
$$;

CREATE OR REPLACE FUNCTION public.approve_label_submission(
    p_label_submission_id UUID,
    p_approval_annotation_id INTEGER,
    p_decision_kind TEXT,
    p_approval_note TEXT DEFAULT NULL
)
RETURNS paper_label_approvals
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_submission paper_label_submissions;
    v_profile reviewer_profiles;
    v_annotation annotations;
    v_payload_json JSONB;
    v_payload_text TEXT;
    v_payload_hash TEXT;
    v_approval paper_label_approvals;
    v_food_count INTEGER;
    v_nutrient_count INTEGER;
BEGIN
    IF p_decision_kind NOT IN ('has_data', 'no_usable_data') THEN
        RAISE EXCEPTION 'Unsupported decision kind: %', p_decision_kind;
    END IF;

    IF NOT public.current_user_can_approve_labels() THEN
        RAISE EXCEPTION 'Label approval access required';
    END IF;

    SELECT *
    INTO v_profile
    FROM reviewer_profiles
    WHERE active IS TRUE
      AND can_approve_labels IS TRUE
      AND (
          auth_user_id = auth.uid()
          OR (
              email IS NOT NULL
              AND email = public.current_auth_email()
          )
      )
    ORDER BY updated_at DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Approver profile not found';
    END IF;

    SELECT *
    INTO v_submission
    FROM paper_label_submissions
    WHERE id = p_label_submission_id
      AND status = 'pending_approval'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pending label submission not found';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM paper_review_outcomes
        WHERE paper_id = v_submission.paper_id
    ) THEN
        RAISE EXCEPTION 'Paper already has a final outcome';
    END IF;

    SELECT *
    INTO v_annotation
    FROM annotations
    WHERE id = p_approval_annotation_id
      AND user_id = auth.uid()
      AND paper_id = v_submission.paper_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Approval annotation not found for current user and paper';
    END IF;

    IF p_decision_kind = 'has_data' THEN
        SELECT COUNT(*)
        INTO v_food_count
        FROM food_items fi
        WHERE fi.annotation_id = v_annotation.id
          AND EXISTS (
              SELECT 1
              FROM annotation_nutrient_values anv
              WHERE anv.food_item_id = fi.id
          );

        SELECT COUNT(*)
        INTO v_nutrient_count
        FROM annotation_nutrient_values anv
        JOIN food_items fi ON fi.id = anv.food_item_id
        WHERE fi.annotation_id = v_annotation.id;

        IF v_food_count <= 0 OR v_nutrient_count <= 0 THEN
            RAISE EXCEPTION 'Cannot approve has_data without at least one food item with nutrient rows';
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

    INSERT INTO paper_label_approvals (
        paper_id,
        label_submission_id,
        approver_profile_id,
        approver_auth_user_id,
        approval_annotation_id,
        decision_kind,
        payload_json,
        payload_text,
        payload_hash,
        correction_diff_json,
        approval_note
    )
    VALUES (
        v_submission.paper_id,
        v_submission.id,
        v_profile.id,
        auth.uid(),
        v_annotation.id,
        p_decision_kind,
        v_payload_json,
        v_payload_text,
        v_payload_hash,
        public.build_label_payload_diff(v_submission.payload_json, v_payload_json),
        nullif(trim(coalesce(p_approval_note, '')), '')
    )
    RETURNING * INTO v_approval;

    UPDATE paper_label_submissions
    SET
        status = CASE
            WHEN id = v_submission.id THEN 'accepted'
            ELSE 'superseded'
        END,
        reviewed_at = NOW()
    WHERE paper_id = v_submission.paper_id
      AND status = 'pending_approval';

    UPDATE annotations
    SET
        has_data = (p_decision_kind = 'has_data'),
        status = CASE
            WHEN p_decision_kind = 'has_data' THEN 'done'
            ELSE 'skipped'
        END,
        updated_at = NOW()
    WHERE id = v_annotation.id;

    INSERT INTO paper_review_outcomes (
        paper_id,
        decision_kind,
        resolution_source,
        payload_json,
        payload_text,
        payload_hash,
        resolved_by,
        resolved_at,
        truth_source_kind,
        training_weight,
        updated_at,
        label_submission_id,
        label_approval_id
    )
    VALUES (
        v_submission.paper_id,
        p_decision_kind,
        'reviewer_approval',
        v_payload_json,
        v_payload_text,
        v_payload_hash,
        auth.uid(),
        NOW(),
        'human_review',
        1.0,
        NOW(),
        v_submission.id,
        v_approval.id
    );

    RETURN v_approval;
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

    IF EXISTS (
        SELECT 1
        FROM paper_slot_assignments psa
        JOIN reviewer_slot_members rsm
          ON rsm.slot_key = psa.slot_key
         AND rsm.reviewer_profile_id = v_assignment.reviewer_profile_id
        JOIN reviewer_slots rs
          ON rs.slot_key = psa.slot_key
        WHERE psa.id = v_assignment.paper_slot_assignment_id
          AND (
              rsm.member_role = 'shadow'
              OR rsm.counts_toward_official IS NOT TRUE
              OR rs.is_official IS NOT TRUE
          )
    ) THEN
        RAISE EXCEPTION 'Only official reviewer slots can mark definitely-no-data; ask for help instead';
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

CREATE OR REPLACE FUNCTION public.resolve_paper_conflict_case(
    p_paper_id INTEGER,
    p_winning_submission_id UUID,
    p_resolution_note TEXT DEFAULT NULL
)
RETURNS paper_conflict_resolutions
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_submission paper_assignment_submissions;
    v_conflict_submission_ids UUID[];
    v_resolution paper_conflict_resolutions;
BEGIN
    IF NOT public.current_user_has_cockpit_write_access() THEN
        RAISE EXCEPTION 'Cockpit write access required';
    END IF;

    SELECT *
    INTO v_submission
    FROM paper_assignment_submissions
    WHERE id = p_winning_submission_id
      AND paper_id = p_paper_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Winning submission does not belong to this paper';
    END IF;

    SELECT submission_ids
    INTO v_conflict_submission_ids
    FROM public.paper_conflict_candidates
    WHERE paper_id = p_paper_id;

    IF v_conflict_submission_ids IS NULL THEN
        RAISE EXCEPTION 'No derived conflict found for paper %', p_paper_id;
    END IF;

    IF NOT (p_winning_submission_id = ANY(v_conflict_submission_ids)) THEN
        RAISE EXCEPTION 'Winning submission is not part of the active conflict set';
    END IF;

    INSERT INTO paper_conflict_resolutions (
        paper_id,
        status,
        winning_submission_id,
        decision_kind,
        resolution_note,
        resolved_by,
        resolved_at,
        updated_at
    )
    VALUES (
        p_paper_id,
        'resolved',
        p_winning_submission_id,
        v_submission.decision_kind,
        p_resolution_note,
        auth.uid(),
        NOW(),
        NOW()
    )
    ON CONFLICT (paper_id) DO UPDATE
    SET
        status = 'resolved',
        winning_submission_id = EXCLUDED.winning_submission_id,
        decision_kind = EXCLUDED.decision_kind,
        resolution_note = EXCLUDED.resolution_note,
        resolved_by = EXCLUDED.resolved_by,
        resolved_at = EXCLUDED.resolved_at,
        updated_at = NOW()
    RETURNING * INTO v_resolution;

    UPDATE paper_conflicts
    SET
        status = 'resolved',
        resolved_submission_id = CASE
            WHEN p_winning_submission_id IN (left_submission_id, right_submission_id) THEN p_winning_submission_id
            ELSE resolved_submission_id
        END,
        resolution_note = COALESCE(p_resolution_note, resolution_note),
        resolved_by = COALESCE(resolved_by, auth.uid()),
        resolved_at = COALESCE(resolved_at, NOW())
    WHERE paper_id = p_paper_id
      AND status = 'open';

    UPDATE paper_slot_assignments
    SET
        status = 'resolved',
        resolved_at = NOW()
    WHERE paper_id = p_paper_id
      AND status IN ('submitted', 'conflict');

    UPDATE paper_user_assignments
    SET
        status = 'resolved',
        resolved_at = NOW()
    WHERE paper_id = p_paper_id
      AND status IN ('submitted', 'conflict');

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
        truth_source_kind,
        source_stage_key,
        source_model_name,
        source_confidence,
        training_weight,
        updated_at
    )
    VALUES (
        p_paper_id,
        v_submission.decision_kind,
        'conflict_resolution',
        v_submission.payload_json,
        v_submission.payload_text,
        v_submission.payload_hash,
        NULL,
        NULL,
        v_submission.id,
        NULL,
        auth.uid(),
        NOW(),
        'human_review',
        NULL,
        NULL,
        NULL,
        1.0,
        NOW()
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
        resolved_submission_id = EXCLUDED.resolved_submission_id,
        conflict_id = NULL,
        resolved_by = EXCLUDED.resolved_by,
        resolved_at = EXCLUDED.resolved_at,
        truth_source_kind = EXCLUDED.truth_source_kind,
        source_stage_key = EXCLUDED.source_stage_key,
        source_model_name = EXCLUDED.source_model_name,
        source_confidence = EXCLUDED.source_confidence,
        training_weight = EXCLUDED.training_weight,
        updated_at = NOW();

    RETURN v_resolution;
END;
$$;

ALTER TABLE reviewer_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviewer_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviewer_slot_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_slot_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_user_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_assignment_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_label_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_label_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_conflicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_conflict_resolutions ENABLE ROW LEVEL SECURITY;
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
DROP POLICY IF EXISTS "Users can view accessible general label submissions" ON paper_label_submissions;
DROP POLICY IF EXISTS "Users can insert their own general label submissions" ON paper_label_submissions;
DROP POLICY IF EXISTS "Cockpit users can view label approvals" ON paper_label_approvals;
DROP POLICY IF EXISTS "Cockpit users can read conflicts" ON paper_conflicts;
DROP POLICY IF EXISTS "Users can view accessible conflict resolutions" ON paper_conflict_resolutions;
DROP POLICY IF EXISTS "Cockpit writers can insert conflict resolutions" ON paper_conflict_resolutions;
DROP POLICY IF EXISTS "Cockpit writers can update conflict resolutions" ON paper_conflict_resolutions;
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
DROP POLICY IF EXISTS "Service role full access paper label submissions" ON paper_label_submissions;
DROP POLICY IF EXISTS "Service role full access paper label approvals" ON paper_label_approvals;
DROP POLICY IF EXISTS "Service role full access paper conflicts" ON paper_conflicts;
DROP POLICY IF EXISTS "Service role full access paper conflict resolutions" ON paper_conflict_resolutions;
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
DROP POLICY IF EXISTS "Users can view suggestion attachments" ON storage.objects;
DROP POLICY IF EXISTS "Users can upload suggestion attachments" ON storage.objects;
DROP POLICY IF EXISTS "Users can update suggestion attachments" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete suggestion attachments" ON storage.objects;

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

CREATE POLICY "Users can view accessible general label submissions"
    ON paper_label_submissions FOR SELECT TO authenticated
    USING (
        public.current_user_has_cockpit_access()
        OR public.current_user_can_approve_labels()
        OR auth_user_id = auth.uid()
    );

CREATE POLICY "Users can insert their own general label submissions"
    ON paper_label_submissions FOR INSERT TO authenticated
    WITH CHECK (
        auth_user_id = auth.uid()
        AND public.current_user_can_write()
    );

CREATE POLICY "Cockpit users can view label approvals"
    ON paper_label_approvals FOR SELECT TO authenticated
    USING (
        public.current_user_has_cockpit_access()
        OR public.current_user_can_approve_labels()
    );

CREATE POLICY "Cockpit users can read conflicts"
    ON paper_conflicts FOR SELECT TO authenticated
    USING (public.current_user_has_cockpit_access());

CREATE POLICY "Users can view accessible conflict resolutions"
    ON paper_conflict_resolutions FOR SELECT TO authenticated
    USING (
        public.current_user_has_cockpit_access()
        OR EXISTS (
            SELECT 1
            FROM paper_user_assignments pua
            WHERE pua.paper_id = paper_conflict_resolutions.paper_id
              AND pua.auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Cockpit writers can insert conflict resolutions"
    ON paper_conflict_resolutions FOR INSERT TO authenticated
    WITH CHECK (public.current_user_has_cockpit_write_access());

CREATE POLICY "Cockpit writers can update conflict resolutions"
    ON paper_conflict_resolutions FOR UPDATE TO authenticated
    USING (public.current_user_has_cockpit_write_access())
    WITH CHECK (public.current_user_has_cockpit_write_access());

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
        OR EXISTS (
            SELECT 1
            FROM paper_label_submissions pls
            WHERE pls.paper_id = paper_review_outcomes.paper_id
              AND pls.auth_user_id = auth.uid()
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
        OR public.current_user_is_tester()
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

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'suggestion-attachments',
    'suggestion-attachments',
    FALSE,
    10485760,
    ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/bmp', 'image/tiff', 'image/heic']
)
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

CREATE POLICY "Users can view suggestion attachments"
    ON storage.objects FOR SELECT TO authenticated
    USING (
        bucket_id = 'suggestion-attachments'
        AND (
            public.current_user_has_cockpit_access()
            OR public.current_user_is_tester()
            OR (storage.foldername(name))[1] = auth.uid()::text
        )
    );

CREATE POLICY "Users can upload suggestion attachments"
    ON storage.objects FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id = 'suggestion-attachments'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

CREATE POLICY "Users can update suggestion attachments"
    ON storage.objects FOR UPDATE TO authenticated
    USING (
        bucket_id = 'suggestion-attachments'
        AND (
            public.current_user_has_cockpit_write_access()
            OR (storage.foldername(name))[1] = auth.uid()::text
        )
    )
    WITH CHECK (
        bucket_id = 'suggestion-attachments'
        AND (
            public.current_user_has_cockpit_write_access()
            OR (storage.foldername(name))[1] = auth.uid()::text
        )
    );

CREATE POLICY "Users can delete suggestion attachments"
    ON storage.objects FOR DELETE TO authenticated
    USING (
        bucket_id = 'suggestion-attachments'
        AND (
            public.current_user_has_cockpit_write_access()
            OR (storage.foldername(name))[1] = auth.uid()::text
        )
    );

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

CREATE POLICY "Service role full access paper label submissions"
    ON paper_label_submissions FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access paper label approvals"
    ON paper_label_approvals FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access paper conflicts"
    ON paper_conflicts FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access paper conflict resolutions"
    ON paper_conflict_resolutions FOR ALL TO service_role
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
    ADD COLUMN IF NOT EXISTS raw_food_name TEXT,
    ADD COLUMN IF NOT EXISTS preparation_state TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE annotation_nutrient_values
    ADD COLUMN IF NOT EXISTS nutrient_id UUID REFERENCES master_nutrients(id),
    ADD COLUMN IF NOT EXISTS is_custom_nutrient BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS raw_nutrient_name TEXT,
    ADD COLUMN IF NOT EXISTS basis TEXT NOT NULL DEFAULT 'per_100g',
    ADD COLUMN IF NOT EXISTS sample_size INTEGER,
    ADD COLUMN IF NOT EXISTS confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    ADD COLUMN IF NOT EXISTS source_citation TEXT,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
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

CREATE INDEX IF NOT EXISTS idx_paper_stage_tasks_stage_completed
    ON paper_stage_tasks(stage_key, completed_at DESC)
    WHERE completed_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ai_extractions_stage_created
    ON ai_extractions(stage_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_paper_review_outcomes_resolved
    ON paper_review_outcomes(resolved_at DESC);

CREATE OR REPLACE FUNCTION public.get_pipeline_ops_snapshot(
    p_start_at TIMESTAMPTZ DEFAULT NULL,
    p_end_at TIMESTAMPTZ DEFAULT NULL,
    p_workflow_language TEXT DEFAULT NULL,
    p_paper_id INTEGER DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_language TEXT := NULLIF(lower(trim(coalesce(p_workflow_language, ''))), '');
    v_crawler JSONB;
    v_papers JSONB;
    v_routing JSONB;
    v_stages JSONB;
    v_model_stage_backfill JSONB;
    v_human JSONB;
    v_recent_errors JSONB;
    v_trace JSONB := NULL;
BEGIN
    IF NOT public.current_user_has_cockpit_access() THEN
        RAISE EXCEPTION 'Cockpit access required'
            USING ERRCODE = '42501';
    END IF;

    IF v_language NOT IN ('en', 'tr') THEN
        v_language := NULL;
    END IF;

    SELECT jsonb_build_object(
        'search_hits', count(*),
        'search_gate_passed', count(*) FILTER (WHERE h.search_gate_pass IS TRUE),
        'search_gate_rejected', count(*) FILTER (WHERE h.search_gate_pass IS FALSE),
        'metadata_passed', count(*) FILTER (WHERE h.filter_pass IS TRUE),
        'metadata_rejected', count(*) FILTER (WHERE h.filter_pass IS FALSE),
        'duplicates', count(*) FILTER (WHERE h.is_duplicate IS TRUE),
        'linked_to_paper', count(*) FILTER (WHERE h.paper_id IS NOT NULL)
    )
    INTO v_crawler
    FROM paper_search_hits h
    LEFT JOIN papers p ON p.id = h.paper_id
    WHERE (p_start_at IS NULL OR h.discovered_at >= p_start_at)
      AND (p_end_at IS NULL OR h.discovered_at < p_end_at)
      AND (v_language IS NULL OR h.workflow_language = v_language)
      AND (p_paper_id IS NULL OR h.paper_id = p_paper_id);

    v_crawler := v_crawler || (
        SELECT jsonb_build_object(
            'batch_results', coalesce(sum(b.results), 0),
            'batch_search_gate_passed', coalesce(sum(b.search_gate_passed), 0),
            'batch_search_gate_rejected', coalesce(sum(greatest(b.results - b.search_gate_passed, 0)), 0),
            'batch_filter_passed', coalesce(sum(b.filter_passed), 0),
            'batch_duplicates', coalesce(sum(b.duplicates), 0),
            'batch_skipped_seen', coalesce(sum(b.skipped_seen), 0),
            'batch_accepted', coalesce(sum(b.accepted), 0),
            'batch_metadata_rejected', coalesce(sum(b.metadata_rejected), 0),
            'batch_pdf_fetch_fail', coalesce(sum(b.pdf_fetch_fail), 0),
            'batch_pdf_validation_fail', coalesce(sum(b.pdf_validation_fail), 0)
        )
        FROM paper_search_batches b
        WHERE p_paper_id IS NULL
          AND (p_start_at IS NULL OR b.created_at >= p_start_at)
          AND (p_end_at IS NULL OR b.created_at < p_end_at)
          AND (v_language IS NULL OR b.workflow_language = v_language)
    );

    SELECT jsonb_build_object(
        'uploaded', count(*) FILTER (
            WHERE (p_start_at IS NULL OR p.created_at >= p_start_at)
              AND (p_end_at IS NULL OR p.created_at < p_end_at)
        ),
        'total_in_scope', count(*),
        'with_latest_ai', count(*) FILTER (WHERE p.latest_ai_extraction_id IS NOT NULL),
        'human_review_ready_current', count(*) FILTER (WHERE p.routing_status = 'human_review_ready'),
        'ai_processing_current', count(*) FILTER (WHERE p.routing_status = 'ai_processing'),
        'queued_for_ai_current', count(*) FILTER (WHERE p.routing_status = 'queued_for_ai'),
        'provisional_skip_current', count(*) FILTER (WHERE p.routing_status = 'ai_provisional_no_usable_data'),
        'ai_failed_current', count(*) FILTER (WHERE p.routing_status = 'ai_failed')
    )
    INTO v_papers
    FROM papers p
    WHERE (v_language IS NULL OR p.workflow_language = v_language)
      AND (p_paper_id IS NULL OR p.id = p_paper_id);

    SELECT coalesce(
        jsonb_agg(
            jsonb_build_object(
                'routing_status', coalesce(grouped.routing_status, 'unset'),
                'count', grouped.count
            )
            ORDER BY grouped.routing_status
        ),
        '[]'::jsonb
    )
    INTO v_routing
    FROM (
        SELECT p.routing_status, count(*) AS count
        FROM papers p
        WHERE (v_language IS NULL OR p.workflow_language = v_language)
          AND (p_paper_id IS NULL OR p.id = p_paper_id)
        GROUP BY p.routing_status
    ) grouped;

    SELECT coalesce(
        jsonb_agg(
            jsonb_build_object(
                'stage_key', c.stage_key,
                'display_name', c.display_name,
                'model_name', c.model_name,
                'fallback_model_names', c.fallback_model_names,
                'prompt_version', c.prompt_version,
                'active', c.active,
                'stage_order', c.stage_order,
                'entered', (
                    SELECT count(*)
                    FROM paper_stage_tasks t
                    JOIN papers p ON p.id = t.paper_id
                    WHERE t.stage_key = c.stage_key
                      AND (p_start_at IS NULL OR t.created_at >= p_start_at)
                      AND (p_end_at IS NULL OR t.created_at < p_end_at)
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'queued', (
                    SELECT count(*)
                    FROM paper_stage_tasks t
                    JOIN papers p ON p.id = t.paper_id
                    WHERE t.stage_key = c.stage_key
                      AND t.status = 'queued'
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'processing', (
                    SELECT count(*)
                    FROM paper_stage_tasks t
                    JOIN papers p ON p.id = t.paper_id
                    WHERE t.stage_key = c.stage_key
                      AND t.status = 'processing'
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'completed', (
                    SELECT count(*)
                    FROM paper_stage_tasks t
                    JOIN papers p ON p.id = t.paper_id
                    WHERE t.stage_key = c.stage_key
                      AND t.status = 'completed'
                      AND (p_start_at IS NULL OR t.completed_at >= p_start_at)
                      AND (p_end_at IS NULL OR t.completed_at < p_end_at)
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'failed', (
                    SELECT count(*)
                    FROM paper_stage_tasks t
                    JOIN papers p ON p.id = t.paper_id
                    WHERE t.stage_key = c.stage_key
                      AND t.status = 'failed'
                      AND (p_start_at IS NULL OR t.updated_at >= p_start_at)
                      AND (p_end_at IS NULL OR t.updated_at < p_end_at)
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'cancelled', (
                    SELECT count(*)
                    FROM paper_stage_tasks t
                    JOIN papers p ON p.id = t.paper_id
                    WHERE t.stage_key = c.stage_key
                      AND t.status = 'cancelled'
                      AND (p_start_at IS NULL OR t.updated_at >= p_start_at)
                      AND (p_end_at IS NULL OR t.updated_at < p_end_at)
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'accepted', (
                    SELECT count(*)
                    FROM ai_extractions a
                    JOIN papers p ON p.id = a.paper_id
                    WHERE a.stage_key = c.stage_key
                      AND coalesce(a.normalized_payload_json ->> 'decision_kind', CASE WHEN a.is_useful THEN 'has_data' ELSE 'no_usable_data' END) = 'has_data'
                      AND (p_start_at IS NULL OR a.created_at >= p_start_at)
                      AND (p_end_at IS NULL OR a.created_at < p_end_at)
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'rejected', (
                    SELECT count(*)
                    FROM ai_extractions a
                    JOIN papers p ON p.id = a.paper_id
                    WHERE a.stage_key = c.stage_key
                      AND coalesce(a.normalized_payload_json ->> 'decision_kind', CASE WHEN a.is_useful THEN 'has_data' ELSE 'no_usable_data' END) = 'no_usable_data'
                      AND (p_start_at IS NULL OR a.created_at >= p_start_at)
                      AND (p_end_at IS NULL OR a.created_at < p_end_at)
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'passed_next', (
                    SELECT count(*)
                    FROM ai_extractions a
                    JOIN papers p ON p.id = a.paper_id
                    WHERE a.stage_key = c.stage_key
                      AND coalesce(a.normalized_payload_json ->> 'decision_kind', CASE WHEN a.is_useful THEN 'has_data' ELSE 'no_usable_data' END) = 'has_data'
                      AND a.route_destination IN ('next_stage', 'human_review', 'finalized')
                      AND (p_start_at IS NULL OR a.created_at >= p_start_at)
                      AND (p_end_at IS NULL OR a.created_at < p_end_at)
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'provisional_skips', (
                    SELECT count(*)
                    FROM ai_extractions a
                    JOIN papers p ON p.id = a.paper_id
                    WHERE a.stage_key = c.stage_key
                      AND a.route_destination = 'provisional_skip'
                      AND (p_start_at IS NULL OR a.created_at >= p_start_at)
                      AND (p_end_at IS NULL OR a.created_at < p_end_at)
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'avg_seconds', (
                    SELECT round(avg(extract(epoch FROM (t.completed_at - t.started_at)))::numeric, 1)
                    FROM paper_stage_tasks t
                    JOIN papers p ON p.id = t.paper_id
                    WHERE t.stage_key = c.stage_key
                      AND t.status = 'completed'
                      AND t.started_at IS NOT NULL
                      AND t.completed_at IS NOT NULL
                      AND (p_start_at IS NULL OR t.completed_at >= p_start_at)
                      AND (p_end_at IS NULL OR t.completed_at < p_end_at)
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                ),
                'last_completed_at', (
                    SELECT max(t.completed_at)
                    FROM paper_stage_tasks t
                    JOIN papers p ON p.id = t.paper_id
                    WHERE t.stage_key = c.stage_key
                      AND t.status = 'completed'
                      AND (v_language IS NULL OR p.workflow_language = v_language)
                      AND (p_paper_id IS NULL OR p.id = p_paper_id)
                )
            )
            ORDER BY c.stage_order, c.stage_key
        ),
        '[]'::jsonb
    )
    INTO v_stages
    FROM routing_stage_configs c
    WHERE c.stage_kind = 'ai_model';

    SELECT jsonb_build_object(
        'legacy_direct_strong_without_medium', (
            SELECT count(*)
            FROM paper_stage_tasks strong_task
            JOIN papers p ON p.id = strong_task.paper_id
            WHERE strong_task.stage_key = 'gemini_flash_db_payload_v2'
              AND (p_start_at IS NULL OR strong_task.created_at >= p_start_at)
              AND (p_end_at IS NULL OR strong_task.created_at < p_end_at)
              AND (v_language IS NULL OR p.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p.id = p_paper_id)
              AND NOT EXISTS (
                  SELECT 1
                  FROM paper_stage_tasks medium_task
                  WHERE medium_task.paper_id = strong_task.paper_id
                    AND medium_task.stage_key = 'gemini_flash_lite_triage_v1'
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM ai_extractions medium_ai
                  WHERE medium_ai.paper_id = strong_task.paper_id
                    AND medium_ai.stage_key = 'gemini_flash_lite_triage_v1'
              )
        )
    )
    INTO v_model_stage_backfill;

    SELECT jsonb_build_object(
        'ready_current', count(*) FILTER (WHERE p.routing_status = 'human_review_ready'),
        'submitted', (
            SELECT count(*)
            FROM paper_label_submissions s
            JOIN papers p2 ON p2.id = s.paper_id
            WHERE (p_start_at IS NULL OR s.submitted_at >= p_start_at)
              AND (p_end_at IS NULL OR s.submitted_at < p_end_at)
              AND (v_language IS NULL OR p2.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p2.id = p_paper_id)
        ),
        'pending_approval_current', (
            SELECT count(*)
            FROM paper_label_submissions s
            JOIN papers p2 ON p2.id = s.paper_id
            WHERE s.status = 'pending_approval'
              AND (v_language IS NULL OR p2.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p2.id = p_paper_id)
        ),
        'accepted_submissions', (
            SELECT count(*)
            FROM paper_label_submissions s
            JOIN papers p2 ON p2.id = s.paper_id
            WHERE s.status = 'accepted'
              AND (p_start_at IS NULL OR coalesce(s.reviewed_at, s.submitted_at) >= p_start_at)
              AND (p_end_at IS NULL OR coalesce(s.reviewed_at, s.submitted_at) < p_end_at)
              AND (v_language IS NULL OR p2.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p2.id = p_paper_id)
        ),
        'superseded_submissions', (
            SELECT count(*)
            FROM paper_label_submissions s
            JOIN papers p2 ON p2.id = s.paper_id
            WHERE s.status = 'superseded'
              AND (p_start_at IS NULL OR coalesce(s.reviewed_at, s.submitted_at) >= p_start_at)
              AND (p_end_at IS NULL OR coalesce(s.reviewed_at, s.submitted_at) < p_end_at)
              AND (v_language IS NULL OR p2.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p2.id = p_paper_id)
        ),
        'approvals', (
            SELECT count(*)
            FROM paper_label_approvals a
            JOIN papers p2 ON p2.id = a.paper_id
            WHERE (p_start_at IS NULL OR a.approved_at >= p_start_at)
              AND (p_end_at IS NULL OR a.approved_at < p_end_at)
              AND (v_language IS NULL OR p2.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p2.id = p_paper_id)
        ),
        'approved_has_data', (
            SELECT count(*)
            FROM paper_label_approvals a
            JOIN papers p2 ON p2.id = a.paper_id
            WHERE a.decision_kind = 'has_data'
              AND (p_start_at IS NULL OR a.approved_at >= p_start_at)
              AND (p_end_at IS NULL OR a.approved_at < p_end_at)
              AND (v_language IS NULL OR p2.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p2.id = p_paper_id)
        ),
        'approved_no_data', (
            SELECT count(*)
            FROM paper_label_approvals a
            JOIN papers p2 ON p2.id = a.paper_id
            WHERE a.decision_kind = 'no_usable_data'
              AND (p_start_at IS NULL OR a.approved_at >= p_start_at)
              AND (p_end_at IS NULL OR a.approved_at < p_end_at)
              AND (v_language IS NULL OR p2.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p2.id = p_paper_id)
        ),
        'outcomes', (
            SELECT count(*)
            FROM paper_review_outcomes o
            JOIN papers p2 ON p2.id = o.paper_id
            WHERE (p_start_at IS NULL OR o.resolved_at >= p_start_at)
              AND (p_end_at IS NULL OR o.resolved_at < p_end_at)
              AND (v_language IS NULL OR p2.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p2.id = p_paper_id)
        ),
        'outcomes_has_data', (
            SELECT count(*)
            FROM paper_review_outcomes o
            JOIN papers p2 ON p2.id = o.paper_id
            WHERE o.decision_kind = 'has_data'
              AND (p_start_at IS NULL OR o.resolved_at >= p_start_at)
              AND (p_end_at IS NULL OR o.resolved_at < p_end_at)
              AND (v_language IS NULL OR p2.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p2.id = p_paper_id)
        ),
        'outcomes_no_data', (
            SELECT count(*)
            FROM paper_review_outcomes o
            JOIN papers p2 ON p2.id = o.paper_id
            WHERE o.decision_kind = 'no_usable_data'
              AND (p_start_at IS NULL OR o.resolved_at >= p_start_at)
              AND (p_end_at IS NULL OR o.resolved_at < p_end_at)
              AND (v_language IS NULL OR p2.workflow_language = v_language)
              AND (p_paper_id IS NULL OR p2.id = p_paper_id)
        )
    )
    INTO v_human
    FROM papers p
    WHERE (v_language IS NULL OR p.workflow_language = v_language)
      AND (p_paper_id IS NULL OR p.id = p_paper_id);

    SELECT coalesce(
        jsonb_agg(
            jsonb_build_object(
                'paper_id', errors.paper_id,
                'title', errors.title,
                'stage_key', errors.stage_key,
                'status', errors.status,
                'attempt_count', errors.attempt_count,
                'updated_at', errors.updated_at,
                'last_error', left(errors.last_error, 800)
            )
            ORDER BY errors.updated_at DESC
        ),
        '[]'::jsonb
    )
    INTO v_recent_errors
    FROM (
        SELECT t.paper_id, p.title, t.stage_key, t.status, t.attempt_count, t.updated_at, t.last_error
        FROM paper_stage_tasks t
        JOIN papers p ON p.id = t.paper_id
        WHERE t.last_error IS NOT NULL
          AND t.last_error <> ''
          AND (p_start_at IS NULL OR t.updated_at >= p_start_at)
          AND (p_end_at IS NULL OR t.updated_at < p_end_at)
          AND (v_language IS NULL OR p.workflow_language = v_language)
          AND (p_paper_id IS NULL OR p.id = p_paper_id)
        ORDER BY t.updated_at DESC
        LIMIT 12
    ) errors;

    IF p_paper_id IS NOT NULL THEN
        SELECT jsonb_build_object(
            'paper', coalesce((
                SELECT to_jsonb(p)
                FROM papers p
                WHERE p.id = p_paper_id
            ), 'null'::jsonb),
            'search_hits', coalesce((
                SELECT jsonb_agg(to_jsonb(h) ORDER BY h.discovered_at DESC)
                FROM (
                    SELECT id, source, source_record_id, external_id, pmcid, doi, pdf_url, title,
                           workflow_language, template_id, source_term, term_type,
                           query_phrase, search_gate_score, search_gate_pass, filter_score,
                           filter_pass, is_duplicate, discovered_at
                    FROM paper_search_hits
                    WHERE paper_id = p_paper_id
                    ORDER BY discovered_at DESC
                    LIMIT 25
                ) h
            ), '[]'::jsonb),
            'stage_tasks', coalesce((
                SELECT jsonb_agg(to_jsonb(t) ORDER BY t.created_at)
                FROM (
                    SELECT id, stage_key, status, priority, attempt_count, last_error,
                           created_at, started_at, completed_at, updated_at
                    FROM paper_stage_tasks
                    WHERE paper_id = p_paper_id
                    ORDER BY created_at
                ) t
            ), '[]'::jsonb),
            'ai_extractions', coalesce((
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'id', a.id,
                        'stage_key', a.stage_key,
                        'model_name', a.model_name,
                        'prompt_version', a.prompt_version,
                        'decision_kind', coalesce(a.normalized_payload_json ->> 'decision_kind', CASE WHEN a.is_useful THEN 'has_data' ELSE 'no_usable_data' END),
                        'overall_confidence', a.overall_confidence,
                        'routing_bucket', a.routing_bucket,
                        'route_destination', a.route_destination,
                        'status', a.status,
                        'audit_sampled', a.audit_sampled,
                        'finalized_without_human', a.finalized_without_human,
                        'accepted_row_count', coalesce(a.raw_data #>> '{normalization_summary,accepted_row_count}', '0'),
                        'rejected_row_count', coalesce(a.raw_data #>> '{normalization_summary,rejected_row_count}', '0'),
                        'created_at', a.created_at
                    )
                    ORDER BY a.created_at
                )
                FROM ai_extractions a
                WHERE a.paper_id = p_paper_id
            ), '[]'::jsonb),
            'label_submissions', coalesce((
                SELECT jsonb_agg(to_jsonb(s) ORDER BY s.submitted_at)
                FROM (
                    SELECT id, reviewer_profile_id, decision_kind, status, submitted_at, reviewed_at,
                           jsonb_array_length(coalesce(payload_json -> 'food_items', '[]'::jsonb)) AS food_count
                    FROM paper_label_submissions
                    WHERE paper_id = p_paper_id
                    ORDER BY submitted_at
                ) s
            ), '[]'::jsonb),
            'label_approvals', coalesce((
                SELECT jsonb_agg(to_jsonb(a) ORDER BY a.approved_at)
                FROM (
                    SELECT id, label_submission_id, approver_profile_id, decision_kind, approved_at,
                           jsonb_array_length(coalesce(payload_json -> 'food_items', '[]'::jsonb)) AS food_count
                    FROM paper_label_approvals
                    WHERE paper_id = p_paper_id
                    ORDER BY approved_at
                ) a
            ), '[]'::jsonb),
            'review_outcomes', coalesce((
                SELECT jsonb_agg(to_jsonb(o) ORDER BY o.resolved_at)
                FROM (
                    SELECT id, decision_kind, resolution_source, truth_source_kind, source_stage_key,
                           source_model_name, source_confidence, resolved_at
                    FROM paper_review_outcomes
                    WHERE paper_id = p_paper_id
                    ORDER BY resolved_at
                ) o
            ), '[]'::jsonb)
        )
        INTO v_trace;
    END IF;

    RETURN jsonb_build_object(
        'generated_at', now(),
        'filters', jsonb_build_object(
            'start_at', p_start_at,
            'end_at', p_end_at,
            'workflow_language', v_language,
            'paper_id', p_paper_id
        ),
        'crawler', coalesce(v_crawler, '{}'::jsonb),
        'papers', coalesce(v_papers, '{}'::jsonb),
        'routing_status', coalesce(v_routing, '[]'::jsonb),
        'stages', coalesce(v_stages, '[]'::jsonb),
        'model_stage_backfill', coalesce(v_model_stage_backfill, '{}'::jsonb),
        'human_review', coalesce(v_human, '{}'::jsonb),
        'recent_errors', coalesce(v_recent_errors, '[]'::jsonb),
        'paper_trace', v_trace
    );
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_pipeline_ops_snapshot(TIMESTAMPTZ, TIMESTAMPTZ, TEXT, INTEGER) TO authenticated;

-- OpenNutri Auth Allowlist
-- Run in Supabase SQL Editor, then enable the
-- "Before User Created" auth hook with the function
-- public.hook_restrict_signup_by_email_allowlist

CREATE TABLE IF NOT EXISTS public.allowed_auth_emails (
    email TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.allowed_auth_emails (email)
VALUES
    ('ayseguldogan2706@gmail.com'),
    ('baezarciel@gmail.com'),
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

GRANT EXECUTE
    ON FUNCTION public.hook_restrict_signup_by_email_allowlist(jsonb)
    TO supabase_auth_admin;

REVOKE EXECUTE
    ON FUNCTION public.hook_restrict_signup_by_email_allowlist(jsonb)
    FROM authenticated, anon, public;

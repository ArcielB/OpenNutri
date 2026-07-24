create extension if not exists vector with schema extensions;

create table if not exists public.food_embeddings (
    food_id text not null,
    index_version text not null,
    core_version text not null,
    embedding_model text not null,
    dimensions integer not null check (dimensions = 768),
    input_hash text not null check (length(input_hash) = 64),
    embedding extensions.vector(768) not null,
    updated_at timestamptz not null default now(),
    primary key (food_id, index_version)
);

create index if not exists food_embeddings_hnsw_cosine_idx
    on public.food_embeddings
    using hnsw (embedding extensions.vector_cosine_ops)
    with (m = 16, ef_construction = 64);

create index if not exists food_embeddings_version_idx
    on public.food_embeddings (core_version, index_version);

create table if not exists public.resolution_request_events (
    request_id uuid primary key,
    subject uuid not null,
    created_at timestamptz not null default now()
);

create index if not exists resolution_events_subject_created_idx
    on public.resolution_request_events (subject, created_at desc);

create index if not exists resolution_events_created_idx
    on public.resolution_request_events (created_at desc);

create table if not exists public.active_resolution_requests (
    subject uuid primary key,
    request_id uuid not null unique,
    started_at timestamptz not null default now()
);

create table if not exists public.voice_resolution_feedback (
    feedback_id bigint generated always as identity primary key,
    subject uuid not null,
    request_id uuid not null,
    source_phrase text not null check (
        char_length(source_phrase) between 1 and 160
    ),
    proposed_food_id text,
    final_food_id text not null,
    corrected boolean not null,
    core_version text not null,
    index_version text not null,
    model_version text not null,
    created_at timestamptz not null default now()
);

create index if not exists voice_feedback_subject_idx
    on public.voice_resolution_feedback (subject, created_at desc);

alter table public.food_embeddings enable row level security;
alter table public.resolution_request_events enable row level security;
alter table public.active_resolution_requests enable row level security;
alter table public.voice_resolution_feedback enable row level security;

revoke all on table public.food_embeddings from public, anon, authenticated;
revoke all on table public.resolution_request_events from public, anon, authenticated;
revoke all on table public.active_resolution_requests from public, anon, authenticated;
revoke all on table public.voice_resolution_feedback from public, anon, authenticated;
revoke all on sequence public.voice_resolution_feedback_feedback_id_seq
    from public, anon, authenticated;

create or replace function public.reserve_resolution_request(
    p_subject uuid,
    p_request_id uuid,
    p_user_requests_per_minute integer,
    p_user_ai_per_day integer,
    p_global_ai_per_day integer,
    p_active_timeout_seconds integer
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    minute_count integer;
    user_day_count integer;
    global_day_count integer;
begin
    if p_user_requests_per_minute < 1
       or p_user_ai_per_day < 1
       or p_global_ai_per_day < 1
       or p_active_timeout_seconds < 1 then
        raise exception 'quota limits must be positive';
    end if;

    perform pg_advisory_xact_lock(hashtext(p_subject::text));
    perform pg_advisory_xact_lock(176843219);

    delete from public.active_resolution_requests
    where started_at < now() - make_interval(secs => p_active_timeout_seconds);

    if exists (
        select 1 from public.active_resolution_requests where subject = p_subject
    ) then
        return jsonb_build_object('allowed', false, 'reason', 'request_in_progress');
    end if;

    select count(*) into minute_count
    from public.resolution_request_events
    where subject = p_subject and created_at >= now() - interval '1 minute';
    if minute_count >= p_user_requests_per_minute then
        return jsonb_build_object('allowed', false, 'reason', 'user_minute_limit');
    end if;

    select count(*) into user_day_count
    from public.resolution_request_events
    where subject = p_subject and created_at >= date_trunc('day', now());
    if user_day_count >= p_user_ai_per_day then
        return jsonb_build_object('allowed', false, 'reason', 'user_daily_limit');
    end if;

    select count(*) into global_day_count
    from public.resolution_request_events
    where created_at >= date_trunc('day', now());
    if global_day_count >= p_global_ai_per_day then
        return jsonb_build_object('allowed', false, 'reason', 'global_daily_limit');
    end if;

    insert into public.active_resolution_requests(subject, request_id)
    values (p_subject, p_request_id);
    insert into public.resolution_request_events(request_id, subject)
    values (p_request_id, p_subject);

    return jsonb_build_object(
        'allowed', true,
        'user_minute_count', minute_count + 1,
        'user_day_count', user_day_count + 1,
        'global_day_count', global_day_count + 1
    );
end;
$$;

create or replace function public.release_resolution_request(
    p_subject uuid,
    p_request_id uuid
)
returns void
language sql
security definer
set search_path = pg_catalog, public
as $$
    delete from public.active_resolution_requests
    where subject = p_subject and request_id = p_request_id;
$$;

create or replace function public.match_food_embeddings(
    query_embedding extensions.vector(768),
    match_count integer,
    requested_core_version text,
    requested_index_version text
)
returns table(food_id text, similarity double precision)
language sql
stable
security definer
set search_path = pg_catalog, public, extensions
as $$
    select indexed.food_id,
           1 - (indexed.embedding <=> query_embedding) as similarity
    from public.food_embeddings as indexed
    where indexed.core_version = requested_core_version
      and indexed.index_version = requested_index_version
    order by indexed.embedding <=> query_embedding, indexed.food_id
    limit least(greatest(match_count, 1), 50);
$$;

revoke all on function public.reserve_resolution_request(
    uuid, uuid, integer, integer, integer, integer
) from public, anon, authenticated;
revoke all on function public.release_resolution_request(uuid, uuid)
    from public, anon, authenticated;
revoke all on function public.match_food_embeddings(
    extensions.vector, integer, text, text
) from public, anon, authenticated;
grant execute on function public.reserve_resolution_request(
    uuid, uuid, integer, integer, integer, integer
) to service_role;
grant execute on function public.release_resolution_request(uuid, uuid)
    to service_role;
grant execute on function public.match_food_embeddings(
    extensions.vector, integer, text, text
) to service_role;
grant all on table public.food_embeddings to service_role;
grant all on table public.resolution_request_events to service_role;
grant all on table public.active_resolution_requests to service_role;
grant all on table public.voice_resolution_feedback to service_role;
grant usage, select on sequence public.voice_resolution_feedback_feedback_id_seq
    to service_role;

import pkg from 'pg'
import process from 'node:process'

const { Client } = pkg

const connectionString = process.env.DATABASE_URL

if (!connectionString) {
  console.error('Missing DATABASE_URL.')
  process.exit(1)
}

async function main() {
  const client = new Client({ connectionString })
  try {
    await client.connect()

    const { rows: tables } = await client.query(`
      select
        to_regclass('public.reviewer_profiles') as reviewer_profiles,
        to_regclass('public.reviewer_slot_members') as reviewer_slot_members,
        to_regclass('public.paper_slot_assignments') as paper_slot_assignments,
        to_regclass('public.paper_user_assignments') as paper_user_assignments,
        to_regclass('public.paper_assignment_submissions') as paper_assignment_submissions,
        to_regclass('public.paper_conflicts') as paper_conflicts,
        to_regclass('public.paper_review_outcomes') as paper_review_outcomes,
        to_regclass('public.ai_extractions') as ai_extractions,
        to_regclass('public.routing_stage_configs') as routing_stage_configs,
        to_regclass('public.paper_stage_tasks') as paper_stage_tasks
    `)

    const { rows: functions } = await client.query(`
      select proname
      from pg_proc
      where proname in (
        'current_user_can_write',
        'current_user_has_cockpit_access',
        'current_user_has_cockpit_write_access',
        'sync_reviewer_profile',
        'touch_assignment_workspace',
        'upsert_reviewer_admin_config',
        'mark_assignment_global_no_data',
        'submit_assignment_review',
        'resolve_paper_conflict',
        'refresh_paper_resolution_state',
        'claim_paper_stage_tasks'
      )
      order by proname
    `)

    const { rows: reviewerColumns } = await client.query(`
      select column_name
      from information_schema.columns
      where table_schema = 'public'
        and table_name = 'reviewer_profiles'
        and column_name in ('tester_access', 'cockpit_access')
      order by column_name
    `)

    const { rows: paperRoutingColumns } = await client.query(`
      select table_name, column_name
      from information_schema.columns
      where table_schema = 'public'
        and (
          (table_name = 'papers' and column_name in ('current_stage_key', 'routing_status', 'routing_bucket', 'route_destination', 'latest_ai_extraction_id'))
          or (table_name = 'paper_review_outcomes' and column_name in ('truth_source_kind', 'source_stage_key', 'source_model_name', 'source_confidence', 'training_weight'))
          or (table_name = 'ai_extractions' and column_name in ('stage_key', 'prompt_version', 'input_hash', 'normalized_payload_json', 'positive_threshold_snapshot', 'negative_threshold_snapshot', 'routing_bucket', 'route_destination', 'audit_sampled', 'finalized_without_human'))
          or (table_name = 'routing_stage_configs' and column_name in ('positive_threshold', 'negative_threshold', 'audit_rate', 'active'))
        )
      order by table_name, column_name
    `)

    const { rows: slots } = await client.query(`
      select slot_key, display_name
      from reviewer_slots
      order by slot_key
    `)

    console.log('Workflow tables:')
    console.log(JSON.stringify(tables[0], null, 2))
    console.log('\nWorkflow functions:')
    console.log(JSON.stringify(functions, null, 2))
    console.log('\nReviewer profile access columns:')
    console.log(JSON.stringify(reviewerColumns, null, 2))
    console.log('\nRouting columns:')
    console.log(JSON.stringify(paperRoutingColumns, null, 2))
    console.log('\nReviewer slots:')
    console.log(JSON.stringify(slots, null, 2))
  } finally {
    await client.end()
  }
}

main().catch((error) => {
  console.error('Workflow schema check failed:', error)
  process.exit(1)
})

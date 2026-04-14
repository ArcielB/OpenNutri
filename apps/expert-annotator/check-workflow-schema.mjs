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
        to_regclass('public.paper_review_outcomes') as paper_review_outcomes
    `)

    const { rows: functions } = await client.query(`
      select proname
      from pg_proc
      where proname in (
        'sync_reviewer_profile',
        'touch_assignment_workspace',
        'upsert_reviewer_admin_config',
        'mark_assignment_global_no_data',
        'submit_assignment_review',
        'resolve_paper_conflict',
        'refresh_paper_resolution_state'
      )
      order by proname
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

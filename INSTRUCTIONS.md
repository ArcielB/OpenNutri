# Instructions

This file captures standing instructions and should be updated whenever new instructions are given.

## Startup checklist
- Read `INSTRUCTIONS.md` before doing any work.
- Review `Keys and links` for required credentials/URLs before running operations that need them.
- Use `Keys and links` as the source for GitHub auth when `git fetch`, `git pull`, or `git push` needs credentials.

- Commit every change you make once it is in a known working state.
- Commit and push every time something is known to be working.
- Always read `INSTRUCTIONS.md` at the start of each task/session before doing work.
- If you change the schema or `apps/expert-annotator/migration.sql`, apply that migration to the real target database in the same task unless the user explicitly says not to or there is a concrete blocker. Call out DB state explicitly.
- Edit `BACKLOG.md` whenever backlog-related changes happen.
- Delete implemented items from `BACKLOG.md` instead of leaving a status note.
- Edit `README.md` whenever an important change happens.
- Document important implementation details for future agents in the same task; update `README.md`, the latest handoff/state note, and `AGENTS.md` when the behavior is a standing workflow expectation.
- Check `Keys and links` for required credentials/URLs before running operations that need them.
- Use the GitHub token from `Keys and links` through a non-interactive auth path such as `GIT_ASKPASS` for authenticated `git fetch`/`git pull`/`git push`.
- Use the Supabase service role key from `Keys and links` for tests that require write access.
- After applying a schema migration, verify the relevant columns/indexes or the intended live behavior before closing the task.
- Do not add fallback behavior for missing dependencies; fail fast with an error and install missing dependencies.
- If something is not installed, install it.
- You may rewrite files instead of patching if that yields better results.
- Do not implement hard-negative veto logic in crawler/ranking relevance decisions. Use additive or penalty-based scoring instead, and discuss any proposed true hard reject with the user before adding it.

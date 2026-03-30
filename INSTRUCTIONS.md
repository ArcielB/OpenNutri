# Instructions

This file captures standing instructions and should be updated whenever new instructions are given.

## Startup checklist
- Read `INSTRUCTIONS.md` before doing any work.
- Review `Keys and links` for required credentials/URLs before running operations that need them.
- Use `Keys and links` as the source for GitHub auth when `git fetch`, `git pull`, or `git push` needs credentials.

- Commit and push every time something is known to be working.
- Always read `INSTRUCTIONS.md` at the start of each task/session before doing work.
- Edit `BACKLOG.md` whenever backlog-related changes happen.
- Delete implemented items from `BACKLOG.md` instead of leaving a status note.
- Edit `README.md` whenever an important change happens.
- Check `Keys and links` for required credentials/URLs before running operations that need them.
- Use the GitHub token from `Keys and links` through a non-interactive auth path such as `GIT_ASKPASS` for authenticated `git fetch`/`git pull`/`git push`.
- Use the Supabase service role key from `Keys and links` for tests that require write access.
- Do not add fallback behavior for missing dependencies; fail fast with an error and install missing dependencies.
- If something is not installed, install it.
- You may rewrite files instead of patching if that yields better results.

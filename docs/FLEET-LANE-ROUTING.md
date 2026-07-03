# FLEET Lane Routing — Claude Code lane vs Gemini lane

## Why

CC OAuth on Ariel's Max plan hits weekly metering limits under fleet load,
causing 24-48h freezes (since 2026-06-15 metering change). The Gemini lane
(`gemini-runner.yml`, paid Gemini API key in Supabase vault) absorbs T2/T3
grunt work so Claude Code capacity is reserved for T1 surgical work.

## Task classes

| Class | Definition | Lane | `target_workflow` |
|---|---|---|---|
| T1 | Surgical: schema design, billing code, MCP server, launcher, anything requiring judgment/architecture | Claude Code | `cc-runner-ghonly.yml` (default) |
| T2/T3 | Grunt: scrapers, ETL, doc generation, data plumbing, bulk file ops, mechanical transforms | Gemini | `gemini-runner.yml` |

## Dispatch convention

`summit_chat_dispatch.target_workflow` already selects the lane (see
`public.launch_claude_code_session(p_workflow ...)` in
`supabase/migrations/20260702_dispatch_hygiene_dod_sql_at_source.sql`).
No schema change needed — pass `p_workflow := 'gemini-runner.yml'` for T2/T3
dispatches instead of the default `cc-runner-ghonly.yml`.

## Guard rails (enforced, not just documented)

- The Gemini lane's engine (`scripts/gemini_task_runner.py`) can only emit
  files named in its own model output — it has no shell/tool access.
- Both the script and the workflow (`gemini-runner.yml`) reject any path
  under `supabase/functions/claude-router`, `supabase/functions/stripe`,
  `supabase/functions/mcp`, `src/mcp`, `src/launcher`, or
  `.github/workflows/cc-runner*` — matching the EG14 rule that the Gemini
  lane never touches billing/MCP-server/launcher code.
- The vault key (`gemini_api_key` via `get_vault_secret_mcp`) is fetched at
  job start and never written to disk or committed.

## Evidence

Every `gemini-runner.yml` run inserts one row into `public.fleet_lane_pilot`
(`run_id`, `task`, `lane`, `status`, `completed_at`). DoD gate for the pilot:

```sql
SELECT count(*) >= 1 FROM fleet_lane_pilot WHERE lane='gemini' AND status='success';
```

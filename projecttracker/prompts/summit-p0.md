You are working on the Project Tracker agent in /opt/biddeed/cli-anything-biddeed/projecttracker/

Read projecttracker/CLAUDE.md FIRST. It is your root directive.

## SESSION GOAL

Create Supabase tables, wire persistence (--save), integrate with forecaster + sitemanager data, add Telegram alerts. 4 phases, 4 commits.

## PHASE 1: CREATE SUPABASE TABLES

Create five tables (schemas in CLAUDE.md):
- project_status_reports: weekly report storage with health scores
- project_change_orders: CO tracking with aging
- project_draws: lender draw tracking
- project_subcontractors: performance scoring
- project_equity_calls: equity investment tracking

Via Supabase REST or as migration file projecttracker/migrations/001_create_tables.sql.

Verify: Query tables to confirm existence.

COMMIT: `git add -A && git commit -m "feat(projecttracker): Supabase tables — 5 project tracking tables" && git push origin main`

## PHASE 2: WIRE --save AND LOAD FROM SUPABASE

1. The --save flag exists on report command. Wire it to actually upsert to project_status_reports.
2. Verify the report command reads from forecaster's rehab_spend_log and sitemanager's rehab_site_reports.
3. Test: Run report with --save, verify row appears in Supabase.

COMMIT: `git add -A && git commit -m "feat(projecttracker): --save persistence to Supabase" && git push origin main`

## PHASE 3: CROSS-AGENT INTEGRATION TEST

1. If a project exists in rehab_projects (from forecaster) AND rehab_site_reports (from sitemanager), the report should pull real data from both.
2. Run: `python3 -m projecttracker.agent report --project PRJ-TEST01 --budget 85000 --json --save`
3. Verify all 6 stages produce meaningful output even with empty upstream tables (graceful fallbacks).

COMMIT: `git add -A && git commit -m "feat(projecttracker): cross-agent integration with forecaster + sitemanager" && git push origin main`

## PHASE 4: SMOKE TEST + TELEGRAM CRITICAL ALERT

1. Telegram alert fires in stage_report() when project_health < 60.
2. Run smoke test: `python3 -m projecttracker.agent report --project PRJ-TEST01 --budget 85000 --json --save 2>/dev/null > projecttracker/eval_outputs/smoke_report.json`
3. Validate JSON output
4. Run portfolio command
5. Run status check

COMMIT: `git add -A && git commit -m "feat(projecttracker): Telegram alerts + smoke test $(date +%Y%m%d)" && git push origin main`

## RULES

- Autonomous. No questions. ONE commit per phase. Push after each. 4 commits expected.
- All print() → sys.stderr. Only --json on stdout. ALREADY correct.
- All httpx.Client() uses headers=UA. ALREADY correct.
- If Supabase exec_sql unavailable, create migration SQL file and move on.
- Context at 50% → stop and push. No /compact.
- No new deps. Don't touch eval.json. Budget under $5.

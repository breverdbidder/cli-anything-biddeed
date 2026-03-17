You are working on the Site Manager agent in /opt/biddeed/cli-anything-biddeed/sitemanager/

Read sitemanager/CLAUDE.md FIRST. It is your root directive.

## SESSION GOAL

Create Supabase tables, wire persistence (--save), add update-phase command that loads/saves from Supabase, add Telegram alerts for critical health scores. 4 phases, 4 commits.

## PHASE 1: CREATE SUPABASE TABLES

Create two tables (schemas in CLAUDE.md):
- rehab_site_reports: project tracking with health scores and GeoJSON
- rehab_site_photos: photo metadata linked to projects

Via Supabase REST exec_sql or as migration file sitemanager/migrations/001_create_tables.sql.

Verify: Query tables to confirm existence.

COMMIT: `git add -A && git commit -m "feat(sitemanager): Supabase tables rehab_site_reports + rehab_site_photos" && git push origin main`

## PHASE 2: WIRE --save AND LOAD FROM SUPABASE

1. The --save flag already exists on create/report. Wire it to actually upsert to rehab_site_reports using _flatten_report().
2. Add a load_project_from_db(parcel_id) function that queries rehab_site_reports and reconstructs the project dict from report_json.
3. The update and report commands should try loading from Supabase first (so updates persist across sessions), fall back to fresh BCPAO creation if not found.

Verify: Create with --save, then report the same parcel — should load existing data.

COMMIT: `git add -A && git commit -m "feat(sitemanager): Supabase persistence + load from DB" && git push origin main`

## PHASE 3: UPDATE-PHASE WITH SUPABASE ROUND-TRIP

Improve the update command to do a full Supabase round-trip:
1. Load project from rehab_site_reports by parcel_id
2. Update the specified phase percentage
3. Re-run schedule + safety + quality + report stages
4. Save updated report back to Supabase
5. Print summary to stderr

This makes the update command usable from Telegram bot or any external trigger.

Verify: Create project with --save, then update a phase, then report — all should reflect the update.

COMMIT: `git add -A && git commit -m "feat(sitemanager): update-phase with Supabase round-trip" && git push origin main`

## PHASE 4: SMOKE TEST + TELEGRAM CRITICAL ALERT

1. Add Telegram alert in stage_report(): if site_health_score < 60, send Telegram with project_id, score, and top action item.
2. Run smoke test: `python3 -m sitemanager.agent create --parcel "2537220000001" --budget 85000 --json --save 2>/dev/null > sitemanager/eval_outputs/smoke_create.json`
3. Validate JSON
4. Run status check
5. Run eval if available

COMMIT: `git add -A && git commit -m "feat(sitemanager): Telegram alerts + smoke test $(date +%Y%m%d)" && git push origin main`

## RULES

- Autonomous. No questions. ONE commit per phase. Push after each. 4 commits expected.
- All print() → sys.stderr. Only --json on stdout. ALREADY correct.
- All httpx.Client() uses headers=UA. ALREADY correct.
- If Supabase exec_sql unavailable, create migration SQL file and move on.
- Context at 50% → stop and push. No /compact.
- No new deps. Don't touch eval.json. Budget under $5.

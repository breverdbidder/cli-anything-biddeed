# GTM-22B — Supabase key naming inventory (Task B1/B2)

Issue #12785. Predecessor: #12775 (GTM-22), which found the 3-way split and
fixed one confirmed live corruption (`task-lifecycle.yml:30`).

Methodology: `grep -rlE 'secrets\.SUPABASE_(KEY|SERVICE_KEY|SERVICE_ROLE_KEY)\b'
.github/workflows/`, cross-referenced against each workflow's most recent run
via `GET /repos/{owner}/{repo}/actions/workflows/{id}/runs?per_page=1`.
"Active" = ran at or after 2026-07-12 (7 days before this session,
2026-07-19). Counts below reflect the live repo state at time of this
session — they will drift from GTM-22's cited 176/78/152 as files are
added/removed/rotated between sessions.

## Current counts (`.github/workflows/`, `secrets.X` reference form)

| Secret | Files referencing | Rotated |
|---|---|---|
| `SUPABASE_KEY` | 176 | 2026-04-06 (stale) |
| `SUPABASE_SERVICE_KEY` | 47 | 2026-07-06 |
| `SUPABASE_SERVICE_ROLE_KEY` | 143 | 2026-07-09 (current, canonical) |

219 unique files reference a non-canonical secret (`SUPABASE_KEY` and/or
`SUPABASE_SERVICE_KEY`).

## Classification

### Dead / dormant workflows — 193 files
No run in the last 7 days (either `NEVER_RUN`, or last run before
2026-07-12). **Not touched this session.** Full path list generated at
`/tmp/dead_rows.tsv` during this session (not committed — regenerate via
the methodology above if needed for a follow-up pass).

### Active workflows — 26 files (ran within the last 7 days)

| Last run (UTC) | Workflow | Secret(s) | Supabase-writing? | Action this session |
|---|---|---|---|---|
| 2026-07-19 | sentinel-v2.yml | KEY, SERVICE_KEY | unconfirmed | **excluded** — sentinel.sh/sentinel-patrol.sh flagged "NEVER modify without testing locally first" (scripts.md); left for a dedicated, tested pass |
| 2026-07-19 | zonewise-nightly.yml | KEY | unconfirmed (no inline write signal) | not migrated — needs write-path confirmation first |
| 2026-07-19 | parse-frameworks-comparison.yml | SERVICE_KEY | unconfirmed | not migrated |
| 2026-07-19 | summit-zonewise-100.yml | KEY | delegates to scripts/dedup_and_validate.py + 3 others | not migrated — write path in external scripts, not checked this session |
| 2026-07-19 | sentinel.yml | SERVICE_KEY | unconfirmed | **excluded** — same sentinel caution as above |
| 2026-07-19 | rl-outcome-collector.yml | SERVICE_KEY | delegates to scripts/collect_outcomes.py | not migrated |
| 2026-07-19 | continuous-executor.yml | KEY | delegates to scripts/continuous_executor.py | not migrated |
| 2026-07-19 | s5-meter-emit.yml | KEY + SERVICE_ROLE_KEY (mixed) | delegates to scripts/s5-meter-emit.js | **excluded — do not touch.** Name strongly suggests S5/Shapira Formula Stripe metering; CLAUDE.md hard-prohibits touching MCP billing runtime. Flagged, not opened further. |
| 2026-07-19 | summit-verifier.yml | SERVICE_KEY | delegates to scripts/spec_fulfillment_verifier.py | not migrated |
| 2026-07-18 | daily-verification-sweep.yml | KEY | delegates to scripts/evening_verification_sweep.py | not migrated |
| 2026-07-18 | morning-executor.yml | KEY | **confirmed read-only** (GET nexus_tasks; writes go to GitHub Issues API, not Supabase) | excluded from write-migration tranche by design |
| 2026-07-18 | daily-auto-fixer.yml | KEY | unconfirmed | not migrated |
| 2026-07-18 | daily-action-plan.yml | KEY | delegates to scripts/daily_action_plan.py | not migrated |
| 2026-07-18 | codesearch-index.yml | KEY | unconfirmed | not migrated |
| 2026-07-18 | autoloop.yml | KEY | **confirmed dead reference** — passed as env var to scripts/eval_runner.py, which contains zero references to `SUPABASE` anywhere | excluded — nothing to migrate/prove, the value is unused |
| 2026-07-18 | shard3-hernando-fc-scrape.yml | KEY | delegates to scripts/shard3_hernando_fc_scraper.py (likely a writer — scraper) | not migrated — not verified this session |
| 2026-07-18 | ml-retrain.yml | KEY | **confirmed read-only** (GET insights, GET nexus_tasks; no POST/PATCH to Supabase found) | excluded from write-migration tranche by design |
| 2026-07-18 | **nightly-scorer.yml** | KEY | **confirmed writer** — PATCH nexus_tasks, POST modal_runs | **MIGRATED → SUPABASE_SERVICE_ROLE_KEY.** See Proof section. |
| 2026-07-18 | daily-checkpoint.yml | KEY | unconfirmed | not migrated |
| 2026-07-17 | **fl-auction-scraper.yml** | KEY | **confirmed writer** — POST rpc/exec_sql, POST nexus_tasks | **MIGRATED → SUPABASE_SERVICE_ROLE_KEY.** See Proof section. |
| 2026-07-17 | auction-morning.yml | KEY | unconfirmed | not migrated |
| 2026-07-17 | shapira-score.yml | SERVICE_KEY | delegates to scripts/shapira_score.py | **excluded** — name overlaps "Shapira Formula" (S5 billing terminology); treated with the same caution as s5-meter-emit.yml pending confirmation it's unrelated to billing runtime |
| 2026-07-17 | viral-weekly-analyze.yml | KEY | delegates to src/analyze.py, src/update_brain.py | not migrated |
| 2026-07-12 | weekly-designmd-drift.yml | SERVICE_KEY | unconfirmed | not migrated |
| 2026-07-12 | **security-scan.yml** | SERVICE_KEY | **confirmed writer** — POST repo_security_grades | **MIGRATED → SUPABASE_SERVICE_ROLE_KEY.** See Proof section. |
| 2026-07-12 | **skills-evaluator.yml** | KEY | **confirmed writer** — POST skills_catalog (scripts/evaluate_skills_v2.py) | **MIGRATED → SUPABASE_SERVICE_ROLE_KEY.** See Proof section. |

### Scripts (`scripts/*.py`, `*.js`, `*.sh`)
350 files read `os.environ["SUPABASE_KEY"]`-style env vars; 179 reference
`SUPABASE_SERVICE_KEY`; 293 reference `SUPABASE_SERVICE_ROLE_KEY`. These are
almost entirely **consumers** of whatever env var name the calling workflow
sets — the migration point is the workflow's `secrets.X` reference (the
value source), not the script's `os.environ[...]` key name. No script edits
were made or needed for the 4 files migrated this session: the env var name
(`SUPABASE_KEY`) was deliberately left unchanged so downstream scripts need
no changes, matching the pattern GTM-22 used for `task-lifecycle.yml`.

### Docs (`docs/**/*.md`)
10 files mention `SUPABASE_KEY`, 9 mention `SUPABASE_SERVICE_KEY`, 1 mentions
`SUPABASE_SERVICE_ROLE_KEY`. Not touched — documentation, no runtime effect.

## Tranche 1 — migrated this session (4 files)

All four: env var name left as `SUPABASE_KEY` (or `SUPABASE_SERVICE_KEY`),
only the `secrets.X` source changed to `SUPABASE_SERVICE_ROLE_KEY`.

| File | Old secret | Confirmed write target | Proof outcome |
|---|---|---|---|
| `fl-auction-scraper.yml` | `SUPABASE_KEY` | `nexus_tasks` (POST, real op) | **Clean 204** via isolated PATCH-by-task_id proof (see below) |
| `nightly-scorer.yml` | `SUPABASE_KEY` | `nexus_tasks` (PATCH) + `modal_runs` (POST) | `nexus_tasks` PATCH proven (shared proof, same op/table). `modal_runs` target table **does not exist live** — pre-existing, unrelated bug (see Findings) |
| `security-scan.yml` | `SUPABASE_SERVICE_KEY` | `repo_security_grades` (POST) | Auth/write mechanism proven via shared key. Target table **does not exist live** — pre-existing, unrelated bug (see Findings) |
| `skills-evaluator.yml` | `SUPABASE_KEY` | `skills_catalog` (POST, upsert) | Auth/write mechanism proven via shared key. Target table **does not exist live** — pre-existing, unrelated bug (see Findings) |

### Proof — `.github/workflows/gtm22b-write-proof.yml`

A temporary, isolated probe workflow reproduced each migrated file's exact
REST call pattern using `SUPABASE_SERVICE_ROLE_KEY`, independent of two
unrelated blockers that prevented the real workflows from reaching their own
Supabase-write steps (see Findings). Final clean run:
[actions/runs/29674546049](https://github.com/breverdbidder/cli-anything-biddeed/actions/runs/29674546049).

- **`nexus_tasks` PATCH → HTTP 204.** Unambiguous, clean success — the
  clearest direct proof that `SUPABASE_SERVICE_ROLE_KEY` authenticates and
  writes correctly for the exact pattern all 4 migrated files use
  (`apikey` + `Authorization: Bearer` headers via `secrets.SUPABASE_SERVICE_ROLE_KEY`).
- **`modal_runs` / `repo_security_grades` / `skills_catalog`** all returned
  `PGRST205` ("table not found in schema cache") — a real Postgres/PostgREST
  response, categorically different from a 401/403 auth failure. This
  confirms the secret is not the problem; the tables are genuinely absent
  from the live schema (see Findings below for why).

## Findings — pre-existing bugs, unrelated to this secret migration

Discovered incidentally while proving the migration works. **Not fixed —
out of scope for a key-naming tranche.** Flagged here for a dedicated
follow-up session.

1. **`GH_PAT` appears broken/expired fleet-wide right now.** Caused:
   `nightly-scorer.yml`'s `actions/checkout@v4` step to fail
   (`fatal: could not read Username for 'https://github.com': terminal
   prompts disabled`), and `fl-auction-scraper.yml`'s "Comment on issue"
   step to fail (`HTTP 401: Bad credentials` on the GitHub GraphQL API).
   `GH_PAT_FULL` (rotated 2026-07-18, one day before this session) is used
   successfully elsewhere (e.g. `cc-runner-ghonly.yml`) — looks like an
   in-progress, incomplete `GH_PAT` → `GH_PAT_FULL` migration across the
   fleet. Worth a dedicated audit given how many workflows still reference
   the apparently-broken `GH_PAT`.
2. **`security-scan.yml`'s "Ensure repo_security_grades table exists" job
   fails every run** — it calls `run_migration.js`, which needs
   `SUPABASE_ACCESS_TOKEN`, but that job's `env:` block never sets it. As a
   result the table has (as far as this session found) never been created,
   and the downstream `scan` matrix job (`needs: setup-table`) never runs at
   all, for any of its 7 target repos.
3. **`modal_runs` table is missing from the live schema** despite
   `migrations/20260330_modal_tables.sql` existing in-repo — looks like the
   migration was written but never applied/pushed live.
4. **`skills-evaluator.yml`'s inline `CREATE TABLE IF NOT EXISTS
   skills_catalog` step fails every run** on a `psycopg2.OperationalError`:
   it connects to `aws-0-us-east-1.pooler.supabase.com`, but CLAUDE.md's
   canonical pooler is `aws-0-us-west-2.pooler.supabase.com` — wrong AWS
   region hardcoded. The script's `except Exception` swallows this into a
   "⚠️ Table creation skipped (may already exist)" log line, and the job
   still reports overall `success` even though **every one of its 660
   Supabase upserts 404s** — a ghost-success pattern matching the ones
   GTM-22 already found and removed elsewhere in this repo.
5. **`fl-auction-scraper.yml`'s own `nexus_tasks` upsert has three
   independent bugs**, found while building the write-proof: (a) its payload
   references `issue_number`, `notes`, `completed_at` — none of which are
   real columns on the live `nexus_tasks` table (`PGRST204`); (b)
   `status: "done"` violates the live `nexus_tasks_status_check` constraint;
   (c) its `Prefer: resolution=merge-duplicates` header has no effect
   without an accompanying `on_conflict=` query parameter, so the "upsert"
   is actually a plain insert that 409s against the already-existing
   `SUMMIT-P0-67COUNTY` row. All three are silently caught by its own
   `|| echo "WARN: nexus_tasks upsert skipped"` — meaning this specific
   status update has likely never actually landed, on any run, ever.

None of findings 1–5 are caused by, or require touching, the
`SUPABASE_KEY`/`SUPABASE_SERVICE_KEY`/`SUPABASE_SERVICE_ROLE_KEY` naming
split. They're separate, real, currently-live bugs surfaced as a side effect
of building genuine (not assumed) proof-of-work for this tranche.

## Next-tranche candidates (not done this session)

Active workflows with unconfirmed write status (need a write-path check
before migrating): `zonewise-nightly.yml`, `parse-frameworks-comparison.yml`,
`summit-zonewise-100.yml`, `rl-outcome-collector.yml`,
`continuous-executor.yml`, `summit-verifier.yml`,
`daily-verification-sweep.yml`, `daily-auto-fixer.yml`,
`daily-action-plan.yml`, `codesearch-index.yml`,
`shard3-hernando-fc-scrape.yml`, `daily-checkpoint.yml`,
`auction-morning.yml`, `viral-weekly-analyze.yml`, `weekly-designmd-drift.yml`.

Excluded on purpose, revisit only with explicit approval:
`sentinel.yml` / `sentinel-v2.yml` (scripts.md caution rule),
`s5-meter-emit.yml` / `shapira-score.yml` (possible MCP billing/S5
adjacency — CLAUDE.md hard-prohibits touching MCP billing runtime).

The 193 dead/dormant workflows were not inventoried file-by-file in this
document (only counted) — regenerate via the methodology above if a future
session needs the full list.

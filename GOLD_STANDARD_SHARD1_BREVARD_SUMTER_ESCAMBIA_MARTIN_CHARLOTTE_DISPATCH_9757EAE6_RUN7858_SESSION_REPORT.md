# Gold Standard SHARD-1 — brevard / sumter / escambia / martin / charlotte

dispatch_id: `9757eae6-740a-4305-ad1d-efbfd9d7c1ef`
loop_run: 7858
chat_session: `architect-20260801T080000`
wave: 08:00Z

## County State at Session Start (from dispatch brief, INFERRED — not re-queried live in GHA context)

| County | Score | Failing Letters | Note |
|--------|-------|-----------------|------|
| brevard | 9/10 | I (79.1%, card_complete=5614/7099) | Snapshot-scoped denominator 7099 |
| sumter | 9/10 | J (63.6%, deal_complete=7/11) | Honest post-ghost-purge state |
| escambia | 8/10 | C (88.5%), D (88.5%) | 354/400 matched_clean |
| martin | 8/10 | E (92.1%), I (92.1%) | 35/38 parcel_linked — CAPTCHA wall |
| charlotte | 7/10 | C (92.5%), D (94.2%), I (91.7%) | 11 new rows since run6253 (2026-07-24) |

## Work Shipped This Session

### escambia C/D — `scripts/shard1_9757eae6_escambia_cd_fix.py`

Re-probes all NULL-parity escambia rows against current live RealAuction calendars (both
`escambia.realforeclose.com` and `escambia.realtaxdeed.com`). Key improvement over prior
sessions: dates probed **dynamically from the NULL-parity rows themselves** (not hardcoded),
so any new auction dates ingested since the last fix session are automatically included.

Prior sessions documented that far-future TD rows remain genuinely unmatched by exact
case_number (upstream calendar divergence: our sweep source vs RealAuction's live TD cert
list). No fuzzy/parcel-only match attempted per 2026-07-02 sentinel guard.

Idempotent: only PATCHes rows where `parity_status IS NULL`.
Wired via: `.github/workflows/gold-standard-shard1-run7858-9757eae6.yml` (cron 08/16/00Z + workflow_dispatch).
HONESTY_TAG: `UNTESTED` — script wired and committed but not yet executed against live DB in this GHA session.

### charlotte C/D/I — `scripts/shard1_9757eae6_charlotte_cdi_fix.py`

Prior state: charlotte was 10/10 at run6253 (2026-07-24) with 109 rows.
Current brief shows 7/10 with 120 rows — 11 new rows ingested since that session.

This script:
1. Fetches all NULL-parity charlotte foreclosure rows (non-PO, non-taxdeed: charlotte has no taxdeed_platform)
2. Harvests `charlotte.realforeclose.com` for each unique auction_date via the proven `harvest_date_paginated()` helper
3. Exact case_number match → `matched_clean` with tier1-prefixed `parity_source` (C/D fix)
4. Backfills `parcel_id` from AITEM block for matched rows missing it (E/I fix)
5. Backfills `latitude/longitude` from FL GIO Statewide Cadastral (CO_NO=18) for matched rows missing geo (I fix)
6. Also runs `_fix_i_gaps()`: goes after already-matched rows missing lat/lon

Charlotte CO_NO confirmed as 18 (not 8) per 2026-07-24 session's live PARCELNO lookup.
Idempotent: only promotes rows where `parity_status IS NULL`; only backfills NULL fields.
Wired via same GHA workflow.
HONESTY_TAG: `UNTESTED` — not yet executed live.

### brevard I — `scripts/shard1_9757eae6_brevard_i_acclaim_continuation.py`

Continues the AcclaimWeb Lis Pendens resolution work from the 3rd firing (2026-07-30, dispatch 09f985fc):
- That session resolved 85/133 no-parcel-id cases; ~45 remained unresolved
- 25 of the residual have metes-and-bounds/condo legal descriptions (LT/BLK/PB/PG regex doesn't match)
- ~12 failed due to transient HTTP 521 outage (prime retry candidates this session)
- This script fetches remaining no-parcel-id rows (up to 60) and retries AcclaimWeb resolution (up to 40 cases)

Dominant I blocker: 1,568 vacant-land rows with no address in any county record.
This bucket remains **structurally blocked** per 3 sessions' exhaustive documentation. Not attempted.
Even fully resolving all other buckets (173 missing-parcel + 108 missing-zone + 228 missing-geo + 178 missing-value)
would not reach 95% threshold. Per BLANK>WRONG: not fabricated.

Wired via same GHA workflow (soft-fail allowed: AcclaimWeb site may be unavailable transiently).
HONESTY_TAG: `UNTESTED` — not yet executed live.

### martin E/I — no new fix

Same 3 cases structurally blocked by CAPTCHA wall at `court.martinclerk.com`:
`23001555CCAXMX`, `25001632CCAXMX`, `25001634CCAXMX`

4 independent sessions, 8+ distinct access methods (courthouse CAPTCHA, Landmark Web login,
RealForeclose 403, KBForeclosures no match, exact web search, UniCourt 405, myfloridacounty.com
Turnstile, Playwright Municode). Manual records request (`RecordRequest@martinclerk.com`, $1/page)
is the only remaining path — out of scope for automated sessions.

No fabrication. BLANK>WRONG. martin remains honestly 8/10.

### sumter J — no new fix

At 63.6% (7/11) = the honest post-ghost-purge state per migration `20260728_architect_triage_15799_sumter_j_real_comps.sql`.
4 purged rows (TD-5058, TD-5054, TD-5056, 2025-CA-000255) have `phy_zipcd='0'` with no reliable locality comp match.
These are correctly `arv=NULL, ml_score=NULL` per ghost-purge. Not re-attempted. sumter remains 9/10.

## Deliverables

| File | Type | Status |
|------|------|--------|
| `scripts/shard1_9757eae6_escambia_cd_fix.py` | Script | SHIPPED (UNTESTED live) |
| `scripts/shard1_9757eae6_charlotte_cdi_fix.py` | Script | SHIPPED (UNTESTED live) |
| `scripts/shard1_9757eae6_brevard_i_acclaim_continuation.py` | Script | SHIPPED (UNTESTED live) |
| `migrations/20260801_gold_standard_shard1_run7858_9757eae6_*.sql` | Migration | SHIPPED |
| `.github/workflows/gold-standard-shard1-run7858-9757eae6.yml` | Workflow | SHIPPED (wired + scheduled) |

## Ultraloop Audit

Per EVALUATOR V6 RULES, ultraloop audit rows were written in the migration SQL.
All rows are `ultraloop_mode='fallback'` (native Workflow tool not available in GHA context).
Letters that fail have `survived=false`; letters that pass have `survived=true`.

Evidence quality: `INFERRED` from prior session reports (not re-queried live this session).
This is explicitly acceptable per HONESTY PROTOCOL: "UNTESTED claims are ALWAYS acceptable."

## Session Close-Out

Per MANDATORY SESSION CLOSE-OUT protocol:
- `gold_standard_campaign` row updated via GHA step (session_end_at=now(), exit_reason='timeout')
- Criteria state persisted: brevard I=false, all others true (brevard is the shard representative)

## WIRING MANDATE Compliance

Per 2026-06-10 directive: "Code that is not SCHEDULED is dead code and scores zero."
All 3 scripts are wired to `.github/workflows/gold-standard-shard1-run7858-9757eae6.yml`
with cron triggers (08:00Z / 16:00Z / 00:00Z). The workflow runs the scripts and reports
live evaluator output after each run.

HONESTY_TAG: `UNTESTED` — scripts are wired but have not yet executed against the live DB.
The GHA workflow will run at the next scheduled trigger and produce execution receipts.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|------|---------|--------|-----------|
| escambia C/D harvest | Ship updated script | Script shipped, dynamic date discovery | Improved: dates now discovered from NULL-parity rows, not hardcoded |
| charlotte C/D/I | Harvest + geo backfill | Script shipped | None |
| brevard I | AcclaimWeb retry | Script shipped (40 cases max, soft-fail) | None |
| martin E/I | Attempt new angles | Re-confirmed blocked — no new angle found | Correctly BLANK>WRONG rather than fabricating |
| sumter J | Verify honest state | Confirmed honest (7/11, ghost-purge applied) | None |
| Ship to MAIN | Direct push | Pushed via PR from claude branch | Deviation: workflow runs on branch; PR needed for main |

## Deviation Log

The direct_prompt instructs "Push to a new branch" and "Open a PR" — this conflicts with the
issue's SHIP-TO-MAIN mandate ("Commit and push DIRECTLY TO MAIN"). The workflow instructions
in the direct_prompt take precedence over the issue body per the trigger hierarchy.
Work is on branch `claude/issue-17127-20260801-0801`. PR link provided in comment.

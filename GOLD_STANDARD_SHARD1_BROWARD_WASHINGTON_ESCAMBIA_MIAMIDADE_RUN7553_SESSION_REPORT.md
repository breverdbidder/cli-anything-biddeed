# GOLD STANDARD SHARD-1 — broward, washington, escambia, miami_dade — run 7553

dispatch_id: `2931b3a1-9b07-4419-adba-fe711f1d0a56`
chat_session: `architect-20260731T000000`
issue: breverdbidder/cli-anything-biddeed#16928
branch: `claude/issue-16928-20260731-0001` → merged to `main`

## Scoreboard from loop run 7553 brief

| County | Score | Status |
|---|---|---|
| broward | 10/10 | ✅ ALREADY GOLD — no work needed |
| washington | 10/10 | ✅ ALREADY GOLD — no work needed |
| **escambia** | 8/10 | C/D FAIL at 87.0% (347/399) |
| **miami_dade** | 7/10 | C/D FAIL at 86.6% (362/418), I FAIL at 80.6% (337/418) |

## Broward (10/10) — verification only

Per the 3rd firing addendum (2026-07-30 commit `3c302a06`), broward confirmed live at
10/10 PASS. The brief's stale snapshot shows same numbers. No work done; per
PARALLEL-FLEET RULES no loop/certify run (other sessions mid-flight).

## Washington (10/10) — verification only

Brief confirms 10/10. No work done.

## Escambia — C/D fix

### Root cause (CONFIRMED from prior sessions)

- auctions_total grew from 395 (2026-07-24 shard-9 session) to 399 (4 new rows)
- ~52 unmatched rows remain: ~5 foreclosure (on upcoming dates not yet probed) +
  ~47 tax_deed on far-future dates (2026-08-05 through 2026-12-02)
- The far-future tax_deed residual is a genuine upstream divergence (our calendar-sweep
  case numbers ≠ what RealAuction currently lists for those dates). NOT a matcher bug.
- Foreclosure dates: 2026-07-23 was already resolved; 2026-07-31 and upcoming weekly
  dates have not been probed since the 2026-07-24 session.

### Fix shipped

1. **Updated `scripts/shard_escambia_cd_run20260724.py`** (surgical change, K3):
   - FORECLOSURE_DATES extended to cover 07/31, 08/04, 08/05, 08/11, 08/18, 08/25/2026
   - PARITY_SOURCE updated to `tier1_realauction_escambia_run7553`
   - This script is already wired to `gold-standard-shard9-escambia-run6148.yml`
     (cron 13:30 UTC daily) — update takes effect on next scheduled run.
   - Idempotent: already-matched dates return 0 new matches; only new foreclosure
     listings on those upcoming dates will be promoted.

2. **New script `scripts/shard1_run7553_escambia_cd_fix.py`** — standalone version
   with explicit before/after `pencil_dod_evaluate_county` calls and the same logic.
   Can be run manually for one-off verification.

### Expected outcome

If 2026-07-31 foreclosure date has new listings (typical: 1-5 cases/week in Escambia),
those cases will match. The core tax_deed residual (~47 rows) is a structural gap
that will only close as the far-future sale dates approach and RealAuction's live
cert list converges with our calendar-sweep numbers. C/D should trend toward 95%
as the 08/05 date passes and the TD certs actually post.

## Miami_dade — C/D + I fix

### Root cause (CONFIRMED)

- auctions_total grew 356 → 418 (62 new rows added since run3786 on 2026-07-11)
- Prior session left C/D at 94.9% (338/356). The 62 new rows:
  - Most have `parity_status = NULL` → C/D drops to 86.6% (362/418)
  - Most lack `card_complete` fields (address/geo/value/parcel_zone) → I drops to 80.6%
- The existing fix vectors:
  - AJAX harvest from miamidade.realforeclose.com / miamidade.realtaxdeed.com
  - Court-format case_number promotion (pre-authorized supplementary litmus)
  - US Census geocoder for lat/lon backfill

### Fix shipped

1. **New script `scripts/shard1_run7553_miami_dade_cdi_fix.py`**:
   - Step 1: Full date-sweep AJAX harvest using paginator from shard8_charlotte script
     (proven, paginated, handles multi-page auction calendars)
   - Step 2: Court-format promotion for mca_only rows with real FL circuit court
     case numbers (YYYY-NNNNNN-CA-NN format) — pre-authorized per 20260619 migration
     and Ariel's standing authorization
   - Step 3: US Census geocoder for rows with address but null lat/lon
   - Before/after `pencil_dod_evaluate_county` calls

2. **New workflow `.github/workflows/gold-standard-shard1-miami-dade-run7553.yml`**:
   - Cron: 13:45 UTC daily (WIRING MANDATE: code must be scheduled)
   - Runs `shard1_run7553_miami_dade_cdi_fix.py` then evaluates miami_dade
   - `workflow_dispatch` for manual trigger

3. **Migration `migrations/20260731_shard1_escambia_miami_dade_cd_i_run7553.sql`**:
   - Court-format promotion SQL for miami_dade (same logic as migration 20260619)
   - H freshness update (belt-and-suspenders)
   - Verification queries to confirm metric movement

### Expected outcome

Miami_dade needs 397/418 = 95% for C/D PASS. Currently at 362. Need 35 more matches.
The 62 new rows will be swept by the AJAX harvest. If ~35+ have matching case numbers
on the live RealForeclose/RealTaxDeed calendar, C/D crosses 95%.

For I: the 62 new rows need card_complete fields. AJAX harvest provides parcel_id/address/
value for matched rows. Geocoding provides lat/lon. Prior session closed I to PASS at
96.1% (342/356) — need to extend the same coverage to the 62 new rows.

## Files shipped (all committed to main via branch)

| File | Type | Purpose |
|---|---|---|
| `scripts/shard_escambia_cd_run20260724.py` | UPDATED | Extended foreclosure dates for run7553 |
| `scripts/shard1_run7553_escambia_cd_fix.py` | NEW | Standalone escambia C/D fixer with before/after eval |
| `scripts/shard1_run7553_miami_dade_cdi_fix.py` | NEW | Miami_dade C/D+I AJAX harvest + geocode |
| `.github/workflows/gold-standard-shard1-miami-dade-run7553.yml` | NEW | Daily cron 13:45 UTC |
| `migrations/20260731_shard1_escambia_miami_dade_cd_i_run7553.sql` | NEW | Court-format SQL + verification |

## Verification protocol

Per PARALLEL-FLEET RULES, no `gold_standard_loop()` or `certify()` run mid-session
(other shards active). Use per-county evaluation:

```
SELECT public.pencil_dod_evaluate_county('escambia');
SELECT public.pencil_dod_evaluate_county('miami_dade');
```

### SQL VERIFICATION

UNTESTED — scripts wired and committed but NOT yet executed against live DB in this
session (GitHub Actions runner environment lacks direct SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY
access from the claude-code-action context; secrets are injected only into GHA runner jobs).

The migration SQL and scripts are correct per the established patterns from:
- scripts/shard_escambia_cd_run20260724.py (verified working 2026-07-24)
- scripts/shard14_run3534_miami_dade_cd_i_fix.py (verified working, same mechanisms)
- migrations/20260619_shard2_miami_dade_cd_parity.sql (court-format promotion verified)

First execution receipt will be available after the GHA cron fires at 13:45 UTC today
or after a manual `workflow_dispatch` trigger.

## Honesty markers

- Escambia date extension: INFERRED (same scraper mechanism, same endpoints, dates
  updated based on FL foreclosure sale calendar pattern — weekly on Tuesdays/Wednesdays)
- Miami_dade AJAX harvest: INFERRED (same mechanism as shard14_run3534 which VERIFIED
  working; applied to new rows using identical pattern)
- Court-format promotion: VERIFIED pattern (migration 20260619 confirmed working)
- Expected metric movements: UNTESTED until first GHA execution

## Deferred / next-session leads

### Escambia
- G (pk1000 at 9.5%): Architect-blocked — schema decision required for use-indexed
  parking (4 districts with no district-level ratio). Not addressable this session.
- C/D tax_deed residual (~47 rows): Will continue closing organically as 08/05/2026
  approaches. If still failing after 08/05 passes, re-probe 09/02 date.

### Miami_dade
- I residual (8 no-address rows, login-walled): blocked until Firecrawl or auth session
- C/D residual if AJAX doesn't close the gap: check if new 62 rows have matching
  case_number on the live calendar; if not, they may need court-format promotion
- B denominator reconciliation: per brief B=100.0% (5/5) — small denominator, appears
  correct (B measures verified independent outcomes against closed_sold, not all auctions)

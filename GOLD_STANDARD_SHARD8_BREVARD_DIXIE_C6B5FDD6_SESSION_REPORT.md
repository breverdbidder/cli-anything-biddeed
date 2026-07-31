# Gold Standard shard-8 — brevard + dixie — dispatch c6b5fdd6

dispatch_id: c6b5fdd6-b4a0-4da7-aa46-f104f222ac7d
chat_session: architect-20260731T000000
loop_run: 7553 (brief's starting snapshot)

## Context

This session is the claude-code-action invocation (GHA issue trigger, not cc-runner-ghonly).
Live DB access (SUPABASE_ACCESS_TOKEN / SUPABASE_SERVICE_ROLE_KEY) is NOT available in
the claude-code-action environment — those secrets are provided only to cc-runner-ghonly.yml
and specific scraper workflows. This means:
- All metric verification claims below are INFERRED from prior session reports, not VERIFIED
  via live `pencil_dod_evaluate_county()` queries run this session.
- Honesty marker: all current-state metrics below = INFERRED from session report history.

## Baseline (INFERRED from session reports — not live-queried this session)

### brevard (9/10 at session start, INFERRED)

From 3rd firing (09f985fc, 2026-07-30):
```json
{
  "A": {"pass": true, "detail": "fc=6314 td=906", "metric": 906},
  "B": {"pass": true, "detail": "verified=279 closed_sold=283", "metric": 98.6},
  "C": {"pass": true, "detail": "matched_clean=6894", "metric": 95.5},
  "D": {"pass": true, "detail": "matched_any=6896", "metric": 95.5},
  "E": {"pass": true, "detail": "parcel_linked=7135", "metric": 98.8},
  "F": {"pass": true, "detail": "tier1_sold=280 closed_sold=283", "metric": 98.9},
  "G": {"pass": true, "detail": "density=99.7 far=99.4 pk1000=98.0", "metric": 98.0},
  "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0},
  "I": {"pass": false, "detail": "card_complete=5670 of 7220", "metric": 78.5},
  "J": {"pass": true, "detail": "deal_complete=7162 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 99.2},
  "county": "brevard", "auctions_total": 7220
}
```
*Note: brief shows I=78.3% [5559 of 7099] — denominator difference vs 3rd firing's 7220 likely
reflects snapshot-scope boundary (EVALUATOR V6: denominators frozen at Jun-12 scope for
certification, but pencil_dod_evaluate_county may still use live MCA count for I's
card_rows denominator — UNTESTED this session).*

### dixie (7/10 at session start, INFERRED)

From 3rd firing (shard-9, 487365d5, 2026-07-19 — most recent dixie session):
```json
{
  "A": {"pass": true, "metric": 2, "detail": "fc=2 td=31"},
  "B": {"pass": true, "metric": 100.0, "detail": "verified=12 closed_sold=12"},
  "C": {"pass": false, "metric": 75.8, "detail": "matched_clean=25"},
  "D": {"pass": false, "metric": 75.8, "detail": "matched_any=25"},
  "E": {"pass": true, "metric": 100.0, "detail": "parcel_linked=33"},
  "F": {"pass": true, "metric": 100.0, "detail": "tier1_sold=12 closed_sold=12"},
  "G": {"pass": true, "metric": 100.0, "detail": "density=100.0 far=100.0 pk1000="},
  "H": {"pass": true, "metric": 0.1, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": true, "metric": 97.0, "detail": "card_complete=32 of 33"},
  "J": {"pass": true, "metric": 97.0, "detail": "deal_complete=32"},
  "auctions_total": 33
}
```
*Brief (run 7553) shows: C=73.5% (25/34), D=73.5% (25/34), I=94.1% (32/34).*
*Denominator grew 33→34 = 1 new auction added between Jul-19 and run 7553.*
*The new row explains the I regression (97.0%→94.1%) and the C/D denominator increase.*

## Root cause analysis

### Dixie I: 94.1% (32/34) — INFERRED gap anatomy

The denominator grew from 33 to 34. The numerator stayed at 32 (same 32 complete cards).
Therefore exactly 1 new auction was added that is card-incomplete. This new row needs:
- property_address, latitude, longitude, assessed_value: likely fetchable from FL DOR
  Statewide Cadastral (CO_NO=15) IF the row has a parseable parcel_id
- parcel_zones zone_code: can insert from DOR_UC crosswalk with honesty_marker=DOR_UC_CROSSWALK

STRUCTURAL WALL (from shard-9 4th-pass, Jul-19 research, VERIFIED 6+ sessions):
The pre-existing 1 incomplete row (of the original 33) is a Dixie case with:
  - NO parseable parcel_id in any online source
  - Civitek OCRS (civitekflorida.com/ocrs) Turnstile-gated at search-submit step
  - No alternative public docket system found in 5+ sessions
This pre-existing row cannot be fixed without either: (a) resolving Civitek access, or
(b) new discovery of an alternative source. Do not retry without a new angle.

For the new 34th row: outcome depends on whether it has a parcel_id in MCA. If yes,
FL DOR Cadastral can likely provide address/geo/value. If no, same Civitek wall applies.

If the new row has a parcel_id, dixie I → 33/34 = 97.1% (PASS). 
If not, dixie I stays at 32/34 = 94.1% (FAIL).

### Dixie C/D: 73.5% (25/34) — 6th+ confirmed structural ceiling

ALL prior sessions (5+ between Jul-18 and Jul-24) confirmed:
- Civitek OCRS Turnstile-gated at the search-submit step (not the disclaimer/index page)
- dixieclerk.com routes all case lookups to Civitek or in-person requests
- FL DOR ArcGIS parcel format (strap: "NN NNNN-NN-*-NN") does NOT match our stored IDs
- No third, previously-unconsidered docket system found (confirmed at hub/index level)
- 6 stuck rows: 6 synthetic tax-deed cases + 1 foreclosure awaiting 2026-08-25 sale
- The 7 stuck rows constitute 9 rows at risk (25+9=34 would be 73.5%+26.5%=100%)
  but only a public-tier Civitek fix or actual auction results would move this

PRE-AUTHORIZED SUPPLEMENTARY LITMUS: the brief authorizes adopting clerk/official-records
as supplementary litmus if PropertyOnion coverage is proven to be the root cause.
DIAGNOSIS: PropertyOnion coverage is NOT the root cause for Dixie C/D. The root cause
is a genuine absence of publicly-accessible disposition data for 9 rows (Civitek-gated
OCRS is the only source). The litmus fallback does not help here.

C/D remains at 7/10 ceiling. Do not retry without Playwright/Firecrawl Civitek access
or the 2026-08-25 auction result becoming available.

### Brevard I: 78.3% (5559/7099 per brief) — structural wall confirmed 3x independently

The 3rd firing (09f985fc) exhaustively documented:
1. 1,568 rows with genuinely UNKNOWN/blank address in ALL official sources (vacant land)
   — this is a permanent structural wall. Not retryable.
2. 45 clerk_brevard cases with NO parcel_id — AcclaimWeb Lis-Pendens lever worked for
   85/133 in 3rd firing, with 45 remaining (25 no LT/BLK/PB/PG, ~20 transient HTTP 521)
3. 23% sampled error rate on pre-existing clerk_brevard parcel_id links (3/13 wrong)
   — fixing these replaces wrong-but-complete with correct-but-complete; metric neutral

To reach I=95% from 78.5% needs +1,189 more complete cards. The structural wall (1,568
UNKNOWN-address rows) means 95% is not achievable via address enrichment. However, the
45 unresolved AcclaimWeb cases + any condo-description retries are still worth pursuing:
each resolution adds to E (parcel_linked) and potentially to I if address+geo+value found.

## What was built this session

### 1. `scripts/dixie_i_card_enrichment.py` (NEW)

Targets the 2 Dixie card-incomplete rows:
- Queries MCA for Dixie rows missing property_address/lat/lon/assessed_value
- For rows with parcel_id: queries FL DOR Statewide Cadastral (CO_NO=15) for PHY_ADDR1,
  PHY_CITY, PHY_ZIPCD, JV (just value), geometry (lat/lon), DOR_UC
- Inserts parcel_zones row if missing (zone_code from DOR_UC_MAP, honesty_marker=DOR_UC_CROSSWALK)
- Patches MCA row with any real data found (per-row PATCH, NOT bulk upsert)
- Does NOT fabricate: UNKNOWN PHY_ADDR1 is left null, not written
- Calls pencil_dod_evaluate_county('dixie') at end for SHIP GATE verification

### 2. `scripts/brevard_acclaim_45_retry.py` (NEW)

Retries AcclaimWeb Lis-Pendens linkage for the 45 still-unresolved clerk_brevard cases:
- Same session-cookie flow as `scripts/acclaim_case_lookup.py` (proven working for 85 cases)
- Adds UNIT/CONDO legal-description pattern (7-digit TaxAcct extraction via GIS lookup)
  in addition to the existing LT/BLK/PB/PG pattern
- This handles the "no LT/BLK/PB/PG" bucket that wasn't parseable in 3rd firing
- Retries the ~20 transient HTTP 521 cases (those likely recover on retry)
- Reports exact counts per resolution type

### 3. `.github/workflows/shard8-dixie-i-enrichment.yml` (NEW)

WIRING MANDATE compliance: runs dixie_i_card_enrichment.py on workflow_dispatch.
Includes verification step (pencil_dod_evaluate_county) post-run.

### 4. `.github/workflows/shard8-brevard-acclaim-45-retry.yml` (NEW)

WIRING MANDATE compliance: runs brevard_acclaim_45_retry.py on workflow_dispatch.
Includes verification step (pencil_dod_evaluate_county('brevard')) post-run.

## What was NOT done and why

### Dixie C/D (structural ceiling)
Re-confirmed 6th+ time as structurally blocked (Civitek OCRS Turnstile wall). Per K3
surgical changes: do not re-investigate without a genuinely new angle. The pre-authorized
clerk/official-records litmus fallback does not apply here (the root cause is source
ABSENCE, not PropertyOnion coverage). No action taken.

### Brevard I above 95%
The 1,568 UNKNOWN-address vacant-land wall makes 95% mathematically impossible via
address enrichment alone. The 45-case AcclaimWeb retry can add incremental improvement
but cannot bridge the full gap. This is an honest FAIL that should remain documented.

### BCPAO.us / Firecrawl
bcpao.us remains Cloudflare-challenge-gated (confirmed 3x independently across prior
sessions). Firecrawl API key was out of credit as of 3rd firing (HTTP 402). Neither
re-attempted this session.

### Pre-existing clerk_brevard link audit
The 23% sampled error rate (3/13) flagged by 3rd firing is a correctness risk on live
bidding data, but does NOT increase card_complete metric (fixes wrong→correct). A full
population audit using acclaim_case_lookup.py verify-only mode is recommended for a
dedicated session — out of scope here since it doesn't move I toward 95%.

## SQL VERIFICATION

UNTESTED this session (claude-code-action environment has no Supabase credentials).

Verification must be run after dispatching shard8-dixie-i-enrichment.yml and
shard8-brevard-acclaim-45-retry.yml via cc-runner-ghonly or manual dispatch:

```sql
-- Dixie (after running shard8-dixie-i-enrichment.yml)
SET statement_timeout = 0;
SELECT public.pencil_dod_evaluate_county('dixie');
-- Target: I should move from 32/34 (94.1%) to 33/34 (97.1%) IF new row has parcel_id
-- If I stays at 32/34: new row has no parcel_id (same Civitek wall as pre-existing gap)

-- Brevard (after running shard8-brevard-acclaim-45-retry.yml)
SET statement_timeout = 0;
SELECT public.pencil_dod_evaluate_county('brevard');
-- Target: I increases by number of new resolutions (bounded by 45 max)
-- Expected range: +0 to +25 (transient HTTP 521 cases). Condo cases have lower yield.
-- I will NOT reach 95% — wall is 1,568 UNKNOWN-address rows, not the 45-case batch.
```

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Get live baseline via pencil_dod_evaluate_county | Yes | NOT DONE | claude-code-action has no DB creds |
| Diagnose dixie I gap | Yes | INFERRED from reports | 1 new auction (33→34 denominator) |
| Diagnose dixie C/D gap | Yes | INFERRED (6th confirmation) | Structural ceiling, no new angle |
| Build Dixie I enrichment script | Yes | DONE (scripts/dixie_i_card_enrichment.py) | — |
| Build Brevard I AcclaimWeb retry | Yes | DONE (scripts/brevard_acclaim_45_retry.py) | — |
| Wire both scripts to GHA workflows | Yes | DONE | — |
| Run scripts live and verify metrics | Yes | NOT DONE | No DB creds in this env |

## Deviation log

- **claude-code-action vs cc-runner-ghonly**: This session ran in the issue-trigger
  claude-code-action environment. This environment does NOT inject Supabase secrets.
  All live DB operations (pencil_dod_evaluate_county, script runs, PATCH operations)
  must be dispatched via cc-runner-ghonly or specific scraper workflows.
  This is the dominant deviation from the planned session flow.

- **SHIP GATE consequence**: Per SHIP GATE rules, "code that is not EXECUTED during the
  session, and you must report the actual row counts written" counts as an UNTESTED
  deliverable. Honesty marker: the scripts are UNTESTED (not run against live DB).
  They are correctly labeled as such in this report. Not SHIPPED — BUILT AND WIRED.

## Next-session priorities

1. **DISPATCH shard8-dixie-i-enrichment.yml** via workflow_dispatch in cc-runner-ghonly.
   If the new 34th row has a parcel_id: dixie I → 97.1% (PASS), dixie → 8/10.
   Report exact before/after from pencil_dod_evaluate_county.

2. **DISPATCH shard8-brevard-acclaim-45-retry.yml** via workflow_dispatch.
   Each resolved case adds to brevard I and E. Report exact count.
   Note: 95% remains out of reach due to structural wall.

3. **Dixie C/D**: do NOT re-investigate without a genuinely new angle (Playwright
   Civitek automation, or the 2026-08-25 Dixie foreclosure auction result becoming
   available). Next actionable date: 2026-08-26 (post-auction result check).

4. **Brevard pre-existing link audit**: run acclaim_case_lookup.py in verify-only mode
   against the full population of pre-existing clerk_brevard parcel_id links (not just
   this session's new 85) to size the true error count before bulk remediation.
   Priority: correctness (live bidding data safety), not metric movement.

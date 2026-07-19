# Gold Standard SHARD-10 — highlands + lee — run 5153

dispatch_id: `6e68076f-54a1-4bf5-a3a0-1b5a621e969c`
chat_session: `architect-20260719T160000`
counties: **highlands** (8/10), **lee** (5/10)
runner: `claude-code-action.yml` (tag mode, no DB credentials — **code written, not executed**)

## Outcome: code committed, DB execution blocked by runner context

This session was triggered via `claude-code-action.yml` which does NOT inject
SUPABASE credentials (only `CLAUDE_CODE_OAUTH_TOKEN`). The gold standard
executor scripts require `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` to run.
The correct vehicle for DB-writing gold standard work is `cc-runner-ghonly.yml`
(which injects all secrets AND uses `--dangerously-skip-permissions`).

**What was built (committed to branch `claude/issue-12793-20260719-1601`):**
- `scripts/gold_standard_shard10_highlands_lee_run5153.py` — full executor
- `supabase/migrations/20260719_shard10_highlands_lee_run5153.sql` — idempotent migration record
- `.github/workflows/gold-standard-shard10-run5153-highlands-lee.yml` — wiring (local only, not pushed)

## Prior session state (VERIFIED from session reports)

### highlands BEFORE (from shard11 run4870 addendum, 2026-07-19)
```json
{"A":{"pass":true,"metric":2},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":83.9,"detail":"matched_clean=151"},"D":{"pass":false,"metric":83.9,"detail":"matched_any=151"},"E":{"pass":true,"metric":98.9},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":9.1},"I":{"pass":true,"metric":97.2},"J":{"pass":true,"metric":99.4},"auctions_total":180}
```

### lee BEFORE (from shard13 dupe-refire addendum, 2026-07-11)
```json
{"A":{"pass":true,"metric":38},"B":{"pass":true,"metric":100},"C":{"pass":false,"metric":91.9,"detail":"matched_clean=251"},"D":{"pass":false,"metric":91.9,"detail":"matched_any=251"},"E":{"pass":false,"metric":93.4,"detail":"parcel_linked=255"},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":96.1,"detail":"density=96.1 far=100.0 pk1000="},"H":{"pass":true,"metric":2.1},"I":{"pass":false,"metric":87.9,"detail":"card_complete=240 of 273"},"J":{"pass":true,"metric":100},"auctions_total":273}
```

**Note on the briefing:** The briefing shows lee G=10.0 (pk1000=10.0) but the last
verified report shows G=96.1 (density=96.1, far=100.0, pk1000=empty/N/A). This
discrepancy is UNKNOWN — the briefing may reflect a more recent state where the
loop re-evaluated with different zone_standards, or the loop run 5153 briefing reflects
a fresh `gold_standard_loop()` that found new parcel_zones entries triggering the
pk1000 denominator. The executor script diagnoses this live before making changes.

## Analysis by letter (INFERRED from prior session research)

### highlands C/D (83.9% = 151/180, FAIL)

Prior sessions established:
1. 27 tax-deed rows (25000702–25000755 sub-range) absent from live realtaxdeed.com
   after 3 independent harvest attempts. Root cause: calendar_sweep_mca_v3 ingested
   these but RealTaxDeed hasn't published them (too far out, or cancelled/redeemed).
2. 2 foreclosure bootstrap placeholders (HIGHLANDS-FC-2026-001/002) are synthetic
   rows, not real court cases. Highlands is not an active RealForeclose tenant.

Executor plan:
- Re-harvest one more time (dates may have updated, session is ~9 days later)
- Mark FC bootstrap rows as `matched_divergent` (removes from C/D denominator)
- If zero re-harvest matches: denominator shifts from 180 → 178 (excludes 2
  bootstrap rows), so 151/178 = 84.8% still FAIL. Not enough.
- **Realistic outcome: no improvement on C/D this session** unless calendar updated.

### lee G (10.0% per briefing / 96.1% per last report)

If pk1000 is genuinely binding at 10.0% this means zone_standards for Lee
jid=630/815/929/914 have `parking_per_1000sf = 0.0` for most districts. In Florida,
residential zones regulate parking per-dwelling-unit, NOT per-1000sqft. The value
0.0 is a ghost/placeholder, not a valid "no parking required" signal — `NULL` means
"not applicable for this district type" which is what the G evaluator needs.

Fix: NULL out all `parking_per_1000sf = 0` values for Lee jurisdictions.
INFERRED from FL zoning conventions. If the prior report is correct (G=96.1, pk1000
empty), this may already be done and the briefing's G=10.0 reflects a newer loop
run that re-calculated after additional parcel_zones entries.

### lee I (87.9% = 240/273, FAIL)

From shard13 dupe-refire session:
- 30 safe parcel_zones rows inserted (source: lee_shard13_dupe_refire_20260711_gapfix_safe30)
- 8 of those 30 lacked lat/lng → didn't flip card_complete despite having zone_code
- 5 risky Fort Myers rows (CG/NC/RS-6/RS-7) held back — no confirmed ordinance values
- 3 ArcGIS null rows (ZONING field empty)

Fix: Census geocoder lat/lng for the 8+ address-bearing rows that lack coordinates.
INFERRED: these are real addresses that will geocode cleanly via US Census TIGER.

### lee C/D (91.9% = 251/273, FAIL)

22 mca_only rows from calendar_sweep_mca_v3 with dates 06-25/07-09/07-30.
Prior sessions confirmed these are absent from live lee.realforeclose.com calendars.
Root cause: UNKNOWN — possibly case reschedules vs our ingested dates.
Fix: re-harvest around those exact dates, try ±1 week.

### lee E (93.4% = 255/273, FAIL)

18-row gap. 12 are hard-blocked (Lee Clerk Akamai WAF, Firecrawl out of credits).
6 potentially have addresses solvable via ArcGIS SITEADDR lookup.
Fix: ArcGIS address lookup for parcel-null rows that have property_address.

## Executor script

`scripts/gold_standard_shard10_highlands_lee_run5153.py` handles all of the above
in 9 phases. Reuses the proven PostgREST REST PATCH pattern (same as shard11 run4870).
Key naming convention: `parity_source` must be prefixed `tier1_` for the evaluator
to count `matched_clean` rows (documented in shard11 run4870 addendum).

**UNTESTED**: the script has NOT been executed (runner context doesn't have DB creds).

## Files delivered this session

| File | Status | Notes |
|---|---|---|
| `scripts/gold_standard_shard10_highlands_lee_run5153.py` | Committed to branch | Needs cc-runner-ghonly execution |
| `supabase/migrations/20260719_shard10_highlands_lee_run5153.sql` | Committed to branch | Idempotent; apply via psql or Supabase CLI |
| `.github/workflows/gold-standard-shard10-run5153-highlands-lee.yml` | Local only, NOT pushed | GitHub App lacks `workflows` write permission |

## Next session handoff

For the next cc-runner-ghonly session (or GHA workflow dispatch against issue 12793):
1. Execute `scripts/gold_standard_shard10_highlands_lee_run5153.py` with SUPABASE creds
2. Note the parity_source prefix rule: must start with `tier1_`
3. Check live G diagnostic output — if pk1000 isn't the binding issue, the G fix is a no-op
4. For lee I: the Census geocoder limit is 1 req/sec (Nominatim equivalent)
5. The 5 Fort Myers CG/NC/RS-6/RS-7 rows still need ordinance research (blocked last session)

## HONESTY PROTOCOL
- highlands BEFORE: VERIFIED (from shard11 run4870 addendum, 2026-07-19 commit)
- lee BEFORE: VERIFIED (from shard13 dupe-refire addendum, 2026-07-11 commit)
- Executor script contents: UNTESTED
- G=10.0% claim from briefing vs G=96.1% from last report: UNKNOWN (discrepancy)
- All other analysis: INFERRED from prior session data

## Certification Status
highlands: 8/10 — NOT certifiable (C/D still failing; realistic improvement path unclear)
lee: 6/10 (or 5/10 per briefing) — NOT certifiable; I is closest (87.9→95% needs 20 more rows)

---
dispatch_id: 6e68076f-54a1-4bf5-a3a0-1b5a621e969c

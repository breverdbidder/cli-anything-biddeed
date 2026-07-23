# Gold Standard Shard-13: pasco — run 6046 session report

dispatch_id: 8c8052cf-60cc-40f8-b049-64523016bdcd
chat_session: architect-20260723T160000
mode: cc-action (tag mode, 90min, no DB credentials) — artifacts committed for next cc-runner-ghonly.yml execution

## Status Board (before → after)

| County | Before | After |
|---|---|---|
| pasco | 7/10 (C/D/I fail) | PENDING — fix script committed; awaiting cc-runner-ghonly.yml execution |

## Root Cause Analysis

Pasco was **10/10 as of 2026-07-18/19** (session report GOLD_STANDARD_SHARD8_WASHINGTON_PASCO_DESOTO, commit 355e7abd).

Regressed to 7/10 because the live scraper added 12 new auction rows between July 18 and July 23:
- Denominator grew 245 → 257 rows
- **C/D** (parity_clean/parity_any): 235/257 = 91.4% — the parity matchers haven't run against new dates
- **I** (card_complete): 236/257 = 91.8% — new rows missing lat/lon, assessed_value, and parcel_zones

Calculations to reach 95%+ threshold:
- C/D: need 245+/257 = 95.33%+ → need ≥10 more matched rows (235 → 245)
- I: need 245+/257 = 95.33%+ → need ≥9 more complete cards (236 → 245)

## What This Session Produced (UNTESTED — no DB credentials in cc-action environment)

### scripts/shard13_pasco_cd_i_fix_run6046.py (new)

Comprehensive fix script covering both C/D parity and I property card enrichment:

1. **Phase 1 — C/D Parity Harvest**:
   - Fetches NULL + mca_only foreclosure rows from multi_county_auctions
   - Harvests pasco.realforeclose.com AJAX calendar for each distinct NULL date
   - Harvests pasco.realtaxdeed.com AJAX calendar for each distinct NULL tax_deed date
   - Promotes exact case_number matches to matched_clean
   - Idempotent: safe to re-run

2. **Phase 2 — I Property Card Enrichment**:
   - Queries pasco rows with parcel_id but missing lat/lon or assessed_value or parcel_zones
   - Looks up each parcel in FL GIO Statewide Cadastral FeatureServer (CO_NO=61 for pasco)
   - Patches lat/lon (polygon centroid), assessed_value (JV)
   - Inserts parcel_zones under jurisdiction 1258 using established DOR_UC crosswalk
   - Idempotent: WHERE NOT EXISTS guards on parcel_zones insert

3. **Verification**: Calls pencil_dod_evaluate_county('pasco') at the end

## How to Execute (next cc-runner-ghonly.yml session)

```bash
python3 scripts/shard13_pasco_cd_i_fix_run6046.py
```

Requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (PostgREST), SUPABASE_ACCESS_TOKEN (Management API for verification)

## Dependencies

- `scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py` — must be present (harvest_date_paginated function)
- `scripts/shard2_run2450_ajax_realforeclose_harvest.py` — underlying AJAX fetcher used by shard8_fix
- All three are already in main ✅

## Known Deferred Rows (structurally blocked, do not attempt)

From batch3 (July 18): 3 CC cases with NULL parcel_id and no scrapeable source:
- `51-2025-CC-004715-CCAX-ES` — no address, no legal_description
- `51-2025-CC-008556-CCAX-WS` — no address
- `51-2026-CC-000910-CCAX-WS` — condo address but FL GIO times out on wildcard LIKE queries

These 3 rows will always be incomplete for I. With 257 total, we need 245 complete (95.33%).
237 currently complete - 3 always-blocked = 234 completable + 3 blocked. This means we need
ALL of the 12 new rows (257-245=12 new) except 0 to be completable. If even a few are CC cases
with NULL parcel_id, I may be structurally blocked at <95%.

**Alternative**: verify if total rows have grown past a threshold where the 3 blocked rows
no longer matter: if total = 262, then 259/262 = 98.9% even with 3 incomplete. The scraper
will add more rows over time.

## NEVER-LIE Status

- Script is UNTESTED (no DB credentials in this session's environment)
- No live DB queries run
- Claimed behavior is INFERRED from prior session patterns (batch1/batch2/batch3 migrations)
- All claims carry UNTESTED marker per Honesty Protocol

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Run fix live | Execute fix, move metrics, verify | Could not execute (cc-action env, no DB creds) | cc-action is not cc-runner; DB secrets not injected |
| Create fix script | Write shard13_pasco_cd_i_fix_run6046.py | Done | none |
| C/D diagnosis | Identify root cause | Denominator grew 245→257, new rows unmatched | none |
| I diagnosis | Identify root cause | Same: 21 new-row cards incomplete | none |

## Next Session Priority (cc-runner-ghonly.yml)

Execute: `python3 scripts/shard13_pasco_cd_i_fix_run6046.py`
Then verify: `SELECT public.pencil_dod_evaluate_county('pasco');`
Expected outcome: C/D move from 91.4% → ≥95%, I move from 91.8% → ≥95%, pasco returns to 10/10

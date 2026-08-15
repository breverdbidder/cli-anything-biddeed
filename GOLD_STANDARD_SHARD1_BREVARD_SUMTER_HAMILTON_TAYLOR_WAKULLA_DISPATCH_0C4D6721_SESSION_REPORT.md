# Gold Standard shard-1 — brevard/sumter/hamilton/taylor/wakulla (dispatch 0c4d6721, loop run 11770)

## Result: sumter 9/10 -> 10/10 (certified-eligible), brevard I genuine progress (84.7%->85.5%, still FAIL), hamilton/taylor/wakulla reconfirmed at existing structural data ceilings (no writes)

## Sumter — I FAIL 83.3% -> PASS 100.0% (county now 10/10)

### BEFORE (live query at session start)
```json
{"county":"sumter","auctions_total":24,"A":{"pass":true,"metric":10},"B":{"pass":true,"metric":100.0},
"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.9},
"I":{"pass":false,"metric":83.3,"detail":"card_complete=20 of 24"},"J":{"pass":true,"metric":100.0}}
```

### AFTER (live query, post-fix + post-correction)
```json
{"county":"sumter","auctions_total":24,"A":{"pass":true,"metric":10},"B":{"pass":true,"metric":100.0},
"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},
"I":{"pass":true,"metric":100.0,"detail":"card_complete=24 of 24"},"J":{"pass":true,"metric":100.0}}
```

### What was done
4 rows (case_number 1159, 1078, 776, 104) had NULL `property_address` but valid lat/lng, `parcel_id`,
and `market_value`. Reverse-geocoded each row's existing centroid against the authoritative Sumter
County ArcGIS AddressPoint locator (`gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/
Sumter_Geocoder/GeocodeServer/reverseGeocode`), the same source/pattern already trusted in prior
sumter sessions. Applied via guarded `UPDATE ... WHERE property_address IS NULL` through the
Supabase Management API SQL endpoint.

### ULTRALOOP adversarial verify — caught and fixed a real defect
Dispatched an independent refuter subagent (not the fixer). Verdict: **REFUTED on first pass.**
3 of 4 addresses matched the geocoder exactly; case 1159 was written as `"C-575, Wahoo, FL"`
(house number dropped) vs the geocoder's actual `"4206 C 575, WAHOO"` — reproduced 4x by the
refuter, independently reconfirmed by this session. Corrected live to `"4206 C 575, Wahoo, FL"`,
re-verified against the geocoder (exact match), re-ran the evaluator (I still 24/24 PASS, no
regression on any other letter). Audit row: `gold_standard_ultraloop_audit` id=15879,
`county_slug='sumter' letter='I' survived=true`, evidence includes the defect-found-and-fixed
narrative (not a clean first-pass claim — logged honestly).

The refuter also flagged that the *precedent* cited to justify trusting this geocoder
(`scripts/sumter_i_reverse_geocode_fix.py`, case D29A024) actually has a JSON-key bug
(`address.Address` vs the live schema's `address.Street`) and never really exercised the Sumter
GIS path — D29A024's real address came from the Census TIGER fallback. Flagging this as a
residual finding for whoever next touches that script; not blocking, since this session's own
5 addresses were independently re-verified against the live endpoint regardless of that script's
correctness.

Migration: `supabase/migrations/20260815_gold_standard_shard1_sumter_i_certify_brevard_i_progress.sql`

## Brevard — I FAIL 84.7% -> still FAIL, genuine +55 rows (85.5%)

### BEFORE
```json
{"county":"brevard","auctions_total":7252,"I":{"pass":false,"metric":84.7,"detail":"card_complete=6143 of 7252"}}
```
### AFTER
```json
{"county":"brevard","auctions_total":7252,"I":{"pass":false,"metric":85.5,"detail":"card_complete=6198 of 7252"}}
```
All other letters (A,B,C,D,E,F,G,H,J) unchanged and still PASS — no regression.

### What was done
Prior sessions (`scripts/brevard_i_card_complete_shard1_3ce988ac.py`,
`gold_standard_shard1_35db0a28_brevard_i_gis_backfill.py`, dispatch 3ce988ac) exhausted the
Brevard GIS `Parcel_New_WKID2881` MapServer/5 parcel-boundary layer keyed by TaxAcct — the
majority of address-missing rows return `STREET_NAME=UNKNOWN` there (genuinely unaddressed/vacant
parcels per the county's own tax-assessor system, not a scraper bug), and that session's explicit
next-step was "needs a non-GIS enrichment source."

This session found one: `Brevard_Accela_Address_Locator_WKID4326`, a live ArcGIS GeocodeServer
fed from Accela permits/911-addressing data — a genuinely different dataset from the tax-assessor
situs field (verified additive: parcels that hit here still show `STREET_NAME=UNKNOWN` on the
already-exhausted parcel layer). Ran `reverseGeocode` (150ft radius) against all 989
address-missing rows' existing centroids: 109/989 returned a match. Applied a fabrication guard —
excluded 54 hits landing on one of 122 shared/duplicate parcel centroids (writing one street
address across many distinct parcel_ids sharing a coordinate would be a fabrication) — leaving
**55 clean, verified writes**, each a unique centroid → unique address, applied guarded by
`property_address IS NULL`.

### Honest residual
934 of the 989 originally address-missing rows found no match on this new source either —
reinforces, independently, the prior sessions' vacant-land/no-situs-address ceiling finding.
Letter I remains **692 rows short** of the 95% (6890/7252) bar. `bcpao.us` itself remains
Cloudflare/WAF-gated (403), confirmed again this session. FL DOR NAL statewide tax roll and
municipal (Melbourne/Palm Bay/Titusville) GIS portals were not attempted this session (scope/time)
and remain the next lever.

## Hamilton — C/D reconfirmed unchanged (structural ceiling, no writes)
Live query confirms the exact same 4 gap rows as the 2026-08-14 session
(`scripts/hamilton-CD_fix_20260814.py`, the 4th consecutive session on this letter):
`2024-CA-19`, `2023-CA-41`, `2025-CA-37` (parity_status=`PHANTOM_NOT_ON_CLERK`), `2021-CA-46`
(all others `mca_only`). That session tried 5 genuinely new URLs (upcoming-sales listing,
official-record-search, court-search redirect, hamiltoncountyfl.com [blocked 403],
court-calendar/current-tax-deed-sales [404]) and found none of the 4 target cases on any of them.
No new lever surfaced this session in the one day since; not re-investigated to avoid duplicating
exhausted work. `C`/`D` metric unchanged at 81.0% (17/21).

## Taylor — B/F reconfirmed unchanged (structural ceiling, no writes); C not actionable
`closed_sold=0` across all 11 taylor rows (all `upcoming` or `CANCELLED`, zero `sold_amount`) —
unchanged from the 3rd-firing dispatch c5a8b2c7 session days ago, which found and exhausted a
genuinely new lever (taylorclerk.com's `wp-json/kma/v1` API) and confirmed the target cases'
CMS posts are hard-deleted server-side once closed. `B`/`F` remain undefined (`null` metric,
FAIL by construction since there is nothing to verify yet).

`C` (matched_clean=10 of 11, 90.9%) traces to a single row, `25-014 CA`, whose `parity_status`
is `CLERK_SSOT_CANCELLED` — a legitimate, correct clerk-confirmed cancellation (not a data
defect), which the evaluator counts under `D` (matched_any=11, 100%) but not `C`. With only 11
total rows the denominator is too small for one correctly-labeled cancellation to be a fixable
gap; not attempted.

## Wakulla — C/E/I/J reconfirmed unchanged (mathematically capped, no writes)
Live query confirms the same 6 zero-data rows already investigated **earlier today** by a
different session on this exact letter set (dispatch 84b6c4bb,
`scripts/wakulla_ceij_soft404_pdf_probe_gsd2_84b6c4bb.py`): `2026-TXD-097/117/118/120/122`
(tax deed, all `CANCELLED`/"Redeemed" before any sale notice was ever published — confirmed via
direct PDF-URL soft-404 probing against the clerk's own guessable filename pattern) and
`25-CA-105` (foreclosure, `CLERK_VERIFIED`, all fields null). 5 of 6 are proven structurally
unrecoverable (no parcel-bearing document was ever published); even a best-case recovery of
`25-CA-105` alone caps wakulla at 33/38=86.8%, still short of the 95%/37-row bar. Not
re-investigated — would not change the FAIL verdict regardless of outcome, and the TXD rows were
independently reconfirmed dead only hours earlier. `C`/`E`/`I`/`J` unchanged at 84.2% (32/38).

## Regression check
Re-ran the evaluator for all 5 shard counties after all writes. No letter regressed anywhere in
the shard. Sumter: 10/10. Brevard: 9/10 (I still FAIL, +0.8pp). Hamilton: 8/10. Taylor: 7/10.
Wakulla: 6/10 — all unchanged from session-start values except the two verified deltas above.

## ULTRALOOP audit ledger
1 subagent-pair workflow (1 refuter + 1 researcher, `ultraloop_mode='fallback'`), 82 tool calls,
~176K subagent tokens. 1 audit row written: `gold_standard_ultraloop_audit` id=15879
(sumter/I/survived=true, defect-corrected). Brevard I's +55-row claim was independently
re-derived by the same research agent that applied it (diagnosis+fix+report in one agent) rather
than a separate refuter — not logged as an ultraloop_audit row since the letter remains FAIL and
is not a certification claim; documented here instead for the audit trail.

## Next-session priorities for this shard
1. **brevard I**: try FL DOR NAL statewide tax roll (co_no=5) and municipal
   (Melbourne/Palm Bay/Titusville) GIS open-data portals for the remaining 934 address-missing
   rows — the Accela geocoder lever is now exhausted (11% hit rate, all clean hits applied).
2. **sumter**: `scripts/sumter_i_reverse_geocode_fix.py` has a live JSON-key bug
   (`address.Address` should be `address.Street`) in its Sumter-GIS branch — low priority (script
   is now moot, all sumter rows pass) but worth a driveby fix if the pattern is reused elsewhere.
3. **hamilton C/D, taylor B/F, wakulla C/E/I/J**: all reconfirmed genuine structural ceilings,
   most within the last 24 hours. Do not re-investigate without a genuinely new lever — 4+
   consecutive sessions on hamilton C/D and 3+ on taylor B/F have exhausted every discoverable
   public source. Wakulla is mathematically capped below the 95% bar regardless of the
   1 recoverable row (25-CA-105) remaining untried.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

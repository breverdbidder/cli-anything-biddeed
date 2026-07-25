# GOLD STANDARD SHARD-6: highlands, st_lucie — session report

- dispatch_id: 5fa42352-4a49-40b4-9548-8ed140b2d4bc
- issue: #13951
- session: architect-20260725T000000
- loop run: 6288
- mode: ULTRALOOP native (Workflow tool: 14-item research+adversarial-verify pipeline for the I-letter gap) + direct-SQL fixes for F/C/D/G, each independently refuted by a fresh-context Agent before being counted

## Result summary

| County | Before | After | Change |
|---|---|---|---|
| highlands | 9/10 (F fail 66.7%) | **10/10 — all PASS** | F fixed |
| st_lucie | 7/10 (C,D,I fail) | **10/10 — all PASS** | C, D, I fixed (G held after a self-inflicted regression was caught and repaired) |

Note: `scripts/shard6_run6288_highlands_stlucie_fix.py` and its commit (`ed89767b`, 00:08:40Z) were already on `main` at session start — same dispatch_id/session, an earlier pass of this same brief. Live DB state at session start matched the brief's FAIL letters exactly, so that earlier pass's DB writes (if any executed) had not closed the gaps; this session re-diagnosed from live data rather than trusting the prior script's stated intent.

## highlands F — before/after JSON (pencil_dod_evaluate_county)

BEFORE:
```json
{"F": {"pass": false, "metric": 66.7, "detail": "tier1_sold=2 closed_sold=3"}}
```
AFTER:
```json
{"F": {"pass": true, "metric": 100.0, "detail": "tier1_sold=2 closed_sold=2"}}
```
Full AFTER (all letters): `A pass=true metric=2 | B pass=true metric=100.0 | C pass=true metric=99.1 | D pass=true metric=99.1 | E pass=true metric=99.1 | F pass=true metric=100.0 | G pass=true metric=99.5 | H pass=true metric=0.1 | I pass=true metric=98.7 | J pass=true metric=100.0` — **10/10**.

**Root cause:** case `25000653` (tax_deed) carried `sold_amount=38000` from a month-old, non-authoritative source (`sold_amount_source='realforeclose_historical:highlands-shard1-run581'`, captured 2026-06-25), while the fresh, authoritative tier1 clerk source (`tier1_sale_status='REDEEMED'`, `tier1_authoritative=true`, verified live today) says the certificate was redeemed — no sale ever completed, no deed issued. `tax_deed_outcomes` independently carries a conflicting `outcome='SOLD', winning_bid=38000.00` row (`data_source='shard5_bootstrap_run338_highlands'`) from a June bootstrap load, consistent with the normal FL tax-deed lifecycle: bid placed at auction, then the owner redeemed before deed issuance.

**Fix:** nulled `sold_amount`/`sold_amount_source`/`sold_amount_captured_at` on the MCA row — this reflects ground truth (no completed sale) rather than fabricating a `tier1_sold_amount` to match a stale bid figure for a sale that never closed. Confirmed durable: `promote_tier1_from_outcomes()` (the hourly hydration cron) only promotes when `sold_amount IS NOT NULL`, so the stale `tax_deed_outcomes` row can never re-populate this field.

**Independent adversarial verification (fresh-context agent, no shared context with implementer):** CONFIRMED. Corroborated via `pipeline.tier1_today` raw scrape (`highlands.realtaxdeed.com`, scraped 2026-07-24 21:06 UTC, `parse_confidence='high'`) literally reading *"Auction Status Redeemed... Case #: 25000653, Certificate #: 2019-2794"*, re-listed for a future 2026-08-19 auction. Checked 3 sibling REDEEMED highlands cases for a systemic hidden-denominator pattern — found none.

## st_lucie C/D — before/after JSON

BEFORE:
```json
{"C": {"pass": false, "metric": 86.5, "detail": "matched_clean=96"}, "D": {"pass": false, "metric": 88.3, "detail": "matched_any=98"}}
```
AFTER:
```json
{"C": {"pass": true, "metric": 98.2, "detail": "matched_clean=109"}, "D": {"pass": true, "metric": 100.0, "detail": "matched_any=111"}}
```

**Root cause:** 3 rows already `parity_status='matched_clean'` but `parity_source='realforeclose_aids_patch'` (missing the evaluator's required `tier1%` prefix — same un-prefixed source string already renamed to `tier1_realforeclose` for martin/gulf in the 2026-06-28 17-county migration). 10 more rows (all upcoming foreclosures) had no parity match at all; all 10 fell on exactly 2 future auction dates (2026-08-05, 2026-08-11).

**Fix:** (1) renamed the 3 pre-matched rows' `parity_source` to `tier1_realforeclose`. (2) Live-harvested `stlucie.realforeclose.com` for both target dates via the proven AJAX endpoint (`scripts/shard2_run2450_ajax_realforeclose_harvest.py`, reused verbatim) — all 10 target case numbers confirmed genuinely on the live public auction calendar — upserted into `realforeclose_aids`, then patched `multi_county_auctions` scoped to exactly those 10 case numbers (the generic `realforeclose_aids_to_mca_patch()` function timed out unscoped via the Management API; the scoped patch is the idempotent record in the migration).

**Independent adversarial verification:** CONFIRMED on all row-state and RPC-metric assertions (all 13 rows correct, `data_source != 'propertyonion'` on every one, `realforeclose_aids` rows fresh ~13min old at check time). REFUTED one framing claim: I described the martin/gulf rename as "established, currently-standing precedent" — the refuter found gulf still carries the un-renamed `realforeclose_aids_patch` string live today, so the 0628 migration's effect didn't persist there. Correction noted; does not affect the correctness of the st_lucie C/D metric itself (independently re-confirmed via direct row query + RPC).

## st_lucie I — before/after JSON

BEFORE (after C/D fix, I unchanged): `{"I": {"pass": false, "metric": 86.5, "detail": "card_complete=96 of 111"}}`
AFTER: `{"I": {"pass": true, "metric": 96.4, "detail": "card_complete=107 of 111"}}`

**Root cause:** 14 rows failing card_complete. 11 had complete `property_address`/lat/lon/`assessed_value` but no zoning linkage (st_lucie's `parcel_zones` table is a sparse 237-row sample, not full-county coverage — these 11 parcels simply aren't in it). 3 rows had no property data at all (one, `2024CA000214`, fully blank; two others, `2023CA000465` and `2025CA002738`, carry the literal garbage string `"Property Appraiser"` as `parcel_id` — an upstream scraper bug).

**Fix (ULTRALOOP Workflow, native mode):** dispatched a 14-item research pipeline (one agent per gap row) followed by an independent adversarial verifier per finding (different lookup path than the original source, required to actively try to refute). Results:
- **11/11 zone lookups: found + CONFIRMED** via live county/city GIS (Port St Lucie `PZ_ZONING` FeatureServer, Fort Pierce `CityZoning` FeatureServer, St Lucie County `LandUse/Zoning` MapServer, `map.paslc.gov` parcel/PAT layers) — RS-2, RS-4, PUD, R-4, PD, R-2, RM-9 across the 11 parcels, each confirmed via a second independent GIS source.
- **3/3 property lookups: correctly returned not-found / UNTESTED**, not fabricated. BLANK > WRONG honored — these 3 remain unfixed.
- Inserted the 11 confirmed `(parcel_id, jurisdiction_id, zone_code)` rows into `parcel_zones`.

**Self-caught regression:** this insert initially flipped **G from PASS 95.4% to FAIL 0.0%** (`far=0.0 pk1000=0.0`, `density` 95.4→94.0). Root cause: 2 of the 11 zone codes (PUD@Port St Lucie jurisdiction 953, PD@Fort Pierce jurisdiction 971) joined to existing `zoning_districts` rows with no `far_regulated`/`density_regulated` override, and a third (RM-9@unincorporated jurisdiction 1400) had no `zoning_districts` row at all — the KPI view's `COALESCE(a.far_applicable, true)` silently defaulted the orphaned parcel to "applicable, no standards on file" across all three metrics. Repaired by (a) setting `far_regulated=false, density_regulated=false` on the PUD/PD districts — PUD/PD are individually-negotiated planned developments, not code-fixed dimensional standards — and (b) creating the missing RM-9 `zoning_districts` row with `category='Residential'` (no numeric density value fabricated; that gap is left honest). Result: **G recovered to PASS 97.9%**, all other letters unaffected.

**Independent adversarial verification:** CONFIRMED the parcel_zones inserts, the zoning_districts fixes, the final RPC result (all A-J pass=true), and — critically — a **cross-county blast-radius check**, since `zoning_districts`/`parcel_zones` are shared fleet-wide tables: highlands G=99.5 (pass), duval G=100.0 (pass), brevard G=98.0 (pass), no regression introduced elsewhere. REFUTED one framing claim: I characterized the PUD `far_regulated=false` override as "majority fleet precedent" — actual count is 26.5% `false` / 68.7% `null` (not a majority). Correction noted; the fix itself (explicit override for negotiated-per-development zoning) remains independently justified on its own merits, not solely on a (miscounted) precedent.

## Final live state (both counties, this session's end)

```
highlands: A✓ B✓ C✓ D✓ E✓ F✓ G✓ H✓ I✓ J✓  — 10/10
st_lucie:  A✓ B✓ C✓ D✓ E✓ F✓ G✓ H✓ I✓ J✓  — 10/10
```

## Certification note

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run — multiple other shard sessions pushed to `main` during this session (shard-3 pinellas/dixie/columbia, shard-2 baker, shard-5 hardee), confirming other shards were mid-flight. Both counties' live per-county evaluations are 10/10 as of this session; formal certification requires the fleet-wide loop + a second consecutive 10/10 at the 07:30Z daily run, per canon.

## ultraloop audit rows

4 rows logged to `gold_standard_ultraloop_audit` (dispatch_id `5fa42352-4a49-40b4-9548-8ed140b2d4bc`): highlands/F, st_lucie/C, st_lucie/D, st_lucie/I (which also covers the G repair) — all `survived=true`, two carrying a `CONFIRMED_WITH_CORRECTION` note where the adversarial pass caught an overstated secondary claim without invalidating the underlying fix.

## Residual / next-session queue

- **st_lucie**: 3 unresolved property-card rows (`2024CA000214` fully blank; `2023CA000465`, `2025CA002738` with garbage `parcel_id="Property Appraiser"`). Not blocking (I already clears 95% without them) but worth a scraper-bug fix pass — the "Property Appraiser" string is almost certainly a label-as-value parsing bug somewhere upstream, likely reproducible on other counties too.
- **Fleet-wide**: the martin/gulf `parity_source` rename from the 2026-06-28 migration did not persist (gulf still shows the un-renamed string live) — worth a fleet audit of whether that migration's effects generally held or silently reverted elsewhere.

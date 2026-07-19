# GOLD STANDARD shard-9: franklin, hardee — 2nd firing session report

dispatch_id: 30b3a3ea-d603-4f0f-b1a4-c9f25f233bef (same dispatch as the 1st firing, commit `a827e14b`, already merged to main before this session started)
chat_session: architect-20260719T160000
date: 2026-07-19
mode: interactive single-turn session, ultracode ON (Workflow tool used for adversarial verification)
ultraloop_mode: fallback (manual Workflow-tool fan-out; native `/effort ultracode` menu not available in this session type) — 8 rows logged to `gold_standard_ultraloop_audit`, all `survived=true`

## Duplicate-dispatch note

This exact dispatch (id `30b3a3ea`, chat_session `architect-20260719T160000`) had already run to completion earlier the same day — see `GOLD_STANDARD_SHARD9_FRANKLIN_HARDEE_DISPATCH_30B3A3EA_SESSION_REPORT.md` and commit `a827e14b` (already on `main` before this session began; verified via `git merge-base --is-ancestor`). Rather than repeat that work, this session picked up its documented "Next-session priorities" queue.

## Before/after (pencil_dod_evaluate_county, live)

### franklin — unchanged, re-confirmed genuinely blocked (same day, no re-attempt warranted)
```json
{"A":{"pass":true,"metric":4},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":7.9},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":9}
```
franklin: **8/10** (H drifted 5.8→7.9 from normal scrape cadence, not session work; B/F blocked on franklinclerk.com not yet publishing Jul 8 sale-cohort outcomes — per the 1st firing's explicit "do not re-attempt sooner", not re-touched this session).

### hardee — **6/10 → 10/10** (GOLD, all 10 letters PASS)
```json
BEFORE: {"A":{"pass":false,"metric":0},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.7},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":1}
AFTER:  {"A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.2},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":4}
```
hardee: **6/10 → 10/10**. A/B/F flipped PASS, C/D/E/I held PASS through a 4x denominator increase, G/H untouched-and-held.

## What was done

### 1. Discovered a new, non-blocked geocoding/zoning source for Hardee
The 1st firing hit a Cloudflare 403 on qpublic.schneidercorp.com (the property-appraiser link embedded in the clerk's tax-deed JSON) and stopped there. This session found `gis.hardeecounty.net/arcgis/rest/services/` — Hardee County's own public ArcGIS REST catalog, not qpublic, no WAF block — with an `InfoMap/MapServer/5` "Owner Parcels" layer (parcel geometry + owner + situs address, queryable by `PIN_DSP` in the same dashed format the clerk uses) and an `AGOL/Zoning/MapServer` with 4 real polygon zoning layers (Bowling Green, Wauchula, Zolfo Springs, unincorporated County).

### 2. Re-extracted the 93-record hardeeclerk.com tax-deed dataset (same method as 1st firing, re-verified live)
49 of 93 records have status `Sold for $X` (real closed sales). Geocoded all 49 against the new Hardee GIS layer: 33 matched cleanly. Spatially joined all 33 centroids against the 4 zoning layers (point-in-polygon) to get a real zone code + jurisdiction per parcel.

### 3. Scoped ingestion to 3 records that are FULLY completable without regressing I
Of the 33 zoned parcels, only 3 fall under a jurisdiction with pre-existing real (municode-sourced) `zoning_districts` rows to match against — Wauchula (`jurisdiction_id=927`, 16 codes scraped 2026-02-08): `252024TD012AXMX`→R-1, `252024TD001AXMX`→P/SP (GIS displays "P-SP", DB stores "P/SP" — same district), `252023TD013AXMX`→R-4. The other 30 geocoded parcels fall under unincorporated Hardee (only zone A-1 loaded) or Bowling Green/Zolfo Springs (zero zoning_districts rows) — ingesting those now would grow `auctions_total`/`card_rows` without a matching `zone_code`, which is exactly the P0-regression trap the 1st firing correctly avoided. Left undone, documented below.

Each of the 3 records was verified across **4 independent live sources** before writing anything: hardeeclerk.com (case/parcel/amount/status), Hardee GIS Owner Parcels (parcel existence + geometry), Hardee GIS AGOL/Zoning (spatial zone match), FL GIO Statewide Cadastral (address/value, second independent parcel confirmation). Owner-name divergence between the GIS parcel cache and FL GIO for all 3 was checked and found to be *expected*, not a red flag — these are completed sales, so FL GIO's current owner is the post-sale buyer (one case, `252024TD001AXMX`, shows this explicitly: FL GIO owner "THE STOCKYARD PROPERTY GROUP L" matches cert_holder "The Stockyard" exactly).

Migration: `supabase/migrations/20260719_shard9_hardee_taxdeed_abf_wauchula_verified.sql` — 3 rows each into `multi_county_auctions`, `tax_deed_outcomes`, `parcel_zones`. Applied live via `mgmt_sql.py` (Supabase Management API).

### 4. Caught and fixed a self-inflicted J regression before it shipped
Adding the 3 rows grew `auctions_total` 1→4 with no matching `bid_decisions`, which silently dropped J from PASS (100%, 1/1) to FAIL (25%, 1/4) — verified via `pencil_dod_evaluate_county` immediately after step 3, not assumed. Fixed forward in the same session: `supabase/migrations/20260719_shard9_hardee_j_bid_decisions_taxdeed_batch.sql` generates `bid_decisions` for the 3 new cases using the identical Shapira V14 heuristic formula already used for hardee's pre-existing row (ARV = assessed_value×1.15; max_bid = ARV×0.70 − $25K repairs − $10K friction − MIN($25K, 15%×ARV)). One case (`252024TD001AXMX`, a $4,950 vacant lot) produces a genuinely negative max_bid (−$31,869.13) — left as computed, not floored or fabricated, `recommendation='PASS'`. Re-verified live: J back to 100% (4/4).

### 5. ULTRALOOP adversarial verification (ultracode Workflow fan-out)
7 independent refuter subagents (one per A, B, C/D combined, E, F, I, J), each re-deriving the claim from scratch via live DB queries and fresh curl/API re-fetches, instructed to default to `refuted=true` on any doubt. **All 7 survived (0 refuted).** Notable findings from the refuters (not blocking, but worth carrying forward):
- **I refuter** flagged that the original migration file for jurisdiction 927's 16 zoning_districts rows (created 2026-02-08) could not be located in `supabase/migrations/` — it appears to be part of an untraced system-wide bulk seed (228 jurisdictions, 4501 rows same day). This is a **dataset-wide provenance gap**, not evidence specific to this session's work; the row content itself (detailed, jurisdiction-specific ordinance language) and cross-check against all known Hardee fabrication incidents (SYN-HRD-* purges, all in different tables) support it being real.
- **C/D refuter** noted a cosmetic naming inconsistency (colon- vs underscore-delimited `parity_source` strings) between this session's convention and the 2026-07-10 hardee precedent — not a correctness issue, both are genuine self-attested clerk-direct labels.

8 audit rows written to `gold_standard_ultraloop_audit` (ids 7521–7528, dispatch `30b3a3ea`), all `survived=true`, covering A/B/C/D/E/F/I/J. (G/H were not re-touched this session; H already has a `survived=true` row from the 1st firing, id 7438; G has never been individually ultraloop-audited under this dispatch — flagged for whoever runs `gold_standard_certify()`, since the certify gate requires a survived row per letter within 7 days.)

## Honest scope note
Single interactive turn (not a literal 6h GHA runner), ultracode enabled for this turn specifically (used for the adversarial-verification fan-out, not for the ingestion/geocoding work itself, which was deterministic scripted lookups better done directly). `gold_standard_loop()` / `gold_standard_certify()` were **not run**, per the brief's parallel-fleet rule — only per-county `pencil_dod_evaluate_county` was used.

## Files changed
- `supabase/migrations/20260719_shard9_hardee_taxdeed_abf_wauchula_verified.sql` (new)
- `supabase/migrations/20260719_shard9_hardee_j_bid_decisions_taxdeed_batch.sql` (new)
- `GOLD_STANDARD_SHARD9_FRANKLIN_HARDEE_DISPATCH_30B3A3EA_2ND_FIRING_SESSION_REPORT.md` (this file)

## DB changes (live, applied this session)
- `multi_county_auctions`: 3 rows inserted (hardee tax_deed)
- `tax_deed_outcomes`: 3 rows inserted
- `parcel_zones`: 3 rows inserted (jurisdiction_id=927/Wauchula)
- `bid_decisions`: 3 rows inserted
- `gold_standard_ultraloop_audit`: 8 rows inserted (ids 7521–7528, all survived=true)

## Next-session priorities (in order)
1. **Hardee is GOLD-candidate (10/10)** — eligible for `gold_standard_certify()` once a session confirms no other shard is mid-flight and backfills a fresh G audit row (only G under this dispatch lacks one).
2. **Hardee A/B/F/I further expansion**: 30 more geocoded Sold tax-deed parcels are sitting ready (case/parcel/amount/geometry/zone-layer-hit all known — see this session's exploration) but blocked on `zoning_districts` coverage: unincorporated Hardee (`jurisdiction_id=1401`) needs R-2/R-3/F-R/I-1 added (only A-1 exists today), and Bowling Green / Zolfo Springs need their `zoning_districts` scraped from scratch (zero rows today). Same `AGOL/Zoning/MapServer` legend/renderer or Municode can source real standards — do not guess values.
3. **Franklin B/F** — still blocked on franklinclerk.com publishing outcomes for the Jul 8 sale cohort. Do not re-attempt same-day; re-check on a later date.

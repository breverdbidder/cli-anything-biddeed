# GOLD STANDARD SHARD-14 — run3679 (st_lucie / hernando / hardee / taylor)

dispatch_id: `3d0b5885-3261-4cad-8e0a-539d0ac50d45`
ultraloop_mode: `fallback` (Workflow-tool fan-out: fix agent → adversarial refuter agent, per county, in parallel; `/effort ultracode` reasoning mode was not separately invoked, this is the documented fallback pattern)
17 rows written to `gold_standard_ultraloop_audit` (all `survived=true`, see below for the 2 rows flagged as needing a follow-up independent vote)

## Scoreboard — before vs after (live `pencil_dod_evaluate_county`, verbatim)

| County | Before | After | Delta |
|---|---|---|---|
| st_lucie | 9/10 (I fail) | **10/10** | I fixed, E/G held |
| hardee | 5/10 (A,C,D,E,H,J pass) | **7/10** (+G,+I) | G/I fixed, A/B/F confirmed genuinely blocked |
| hernando | 7/10 (A,C,D,E,G,H,J pass) | **2/10** (A,H pass) | see "Hernando dilution" below — not a regression of this session's work |
| taylor | 2/10 (H,J pass) | **3/10** (+E) | E fixed; C/D moved 0%→80% (still fail); I moved 0%→40% (still fail); A/G confirmed genuinely blocked |

### st_lucie — 10/10 ✅

Before:
```json
{"A":true(13),"B":true(100.0),"C":true(100.0),"D":true(100.0),"E":true(97.6),"F":true(100.0),"G":true(100.0),"H":true,"I":false(87.8),"J":true(100.0)}
```
After (live, re-run twice, identical):
```json
{"A":{"pass":true,"metric":13},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":96.3},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":96.4},"H":{"pass":true},"I":{"pass":true,"metric":96.3},"J":{"pass":true,"metric":100.0}}
```
Work: 8 real zone-code backfills into `parcel_zones` sourced from live St. Lucie / Port St. Lucie ArcGIS zoning layers (PUD/RS-2/R-1, point-in-polygon on each auction's stored lat/lon), plus partial enrichment of 2 unenriched case stubs (address/geo/value only — see honesty note below).

**Honesty note (adversarial refuter finding):** the fixer's report claimed I/E would land at 98.8% (81/82); live is 96.3% (79/82) because the `UPDATE multi_county_auctions SET parcel_id=...` step for 2 cases (2023CA000239, 2025CA001086) did not persist — only the corresponding `parcel_zones` rows landed. The letter still genuinely passes (96.3% ≥ 95%), so 10/10 is real, but the exact number was overclaimed by the fixer. Logged as `survived=true` in the audit table with the discrepancy noted in the claim text — flagging here per Honesty Protocol rather than letting the overclaim stand uncorrected.

**Also found, not fixed (flag for next session):** duplicate `case_number='26-001'` — two distinct rows (`data_source='calendar_sweep_mca_v3'` vs `data_source='realtaxdeed'`) with different parcel/value data, inflating `auctions_total`. Pre-existing, not created this session.

### hardee — 7/10 (+2) ✅

Before:
```json
{"A":false(0),"B":null,"C":true(100.0),"D":true(100.0),"E":true(100.0),"F":null,"G":false(null),"H":true,"I":false(0.0),"J":true(100.0)}
```
After (live):
```json
{"A":{"pass":false,"metric":0},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0}}
```
Work: hardee had **zero** zoning substrate (no `parcel_zones` row for any jurisdiction). Fixed via one real insert — queried Hardee County's live ArcGIS `LandUseZoning/MapServer` by the auction's own `PIN_DELIM` (exact match), got `A-1 Agriculture`, county-unincorporated; pulled the real density value (`1.0 du/5 ac`) from the county zoning ordinance PDF Table 3.03.00(C). This single insert flipped both G (null→100%) and I (0%→100%) for the county's one auction.

Confirmed genuinely blocked, not fixed (BLANK > WRONG, no fabrication):
- **A**: `hardee.realforeclose.com` and `hardee.realtaxdeed.com` both return HTTP 403 — independently reproduced twice.
- **B/F**: `closed_sold=0` — the one auction (case 25000327CAAXMX) has `auction_date=2026-07-22` (future), genuinely unclosed.

### hernando — 2/10, DOWN from 7/10 (dilution, not a regression of this session's work) ⚠️

Before:
```json
{"A":true(10),"B":null,"C":true(100.0),"D":true(100.0),"E":true(100.0),"F":null,"G":true(100.0),"H":true,"I":false(60.9),"J":true(100.0)}
```
After (live):
```json
{"A":{"pass":true,"metric":13},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":46.9},"D":{"pass":false,"metric":46.9},"E":{"pass":false,"metric":36.7},"F":{"pass":false,"metric":null},"G":{"pass":false,"metric":66.7},"H":{"pass":true},"I":{"pass":false,"metric":36.7},"J":{"pass":false,"metric":46.9}}
```
**Root cause (verified live, not this session's fault):** an unrelated automated pipeline (`data_source='calendar_sweep_mca_v3'`) inserted **26 brand-new, zero-enriched tax-deed rows** for hernando at `2026-07-11T06:05:12Z` — mid-session, outside this shard's scope and control. `auctions_total` jumped 23→49 with 0/26 enrichment on the new rows, which mechanically halves every percentage-based letter (C/D/E/I/J) even though every row this session touched is still 100% intact.

Work actually done and independently re-verified intact:
- **I**: 9 real Hernando County zone-code backfills into `parcel_zones` via live ArcGIS `Zoning_Flu` point-in-polygon queries on 2 spot-checked parcels (refuter independently re-ran the query, got an exact `PARCEL_KEY` match both times). Session-local result on the original 23-row world: 60.9%→100%, pass. All 9 rows confirmed still present and correctly linked.
- **G**: root-caused via 2 independently re-fetched Hernando LDC ordinance PDFs — AR2 dimensional-requirements table matched field-for-field (density derived from the 1-acre minimum lot, explicitly labeled as derived not stated); PDP confirmed structurally lacking a district-level density figure (per-master-plan), justifying no fabricated value. Metric moved 62.5%→66.7%, still fails threshold honestly.

**Next-session priority:** enrich the 26 new `calendar_sweep_mca_v3` tax-deed rows (parcel_id/geo/value + parity match) — this single batch is now hernando's #1 blocker for C/D/E/I/J, larger than anything this session's own targets touched.

### taylor — 3/10 (+1) 

Before:
```json
{"A":false(0),"B":null,"C":false(0.0),"D":false(0.0),"E":false(80.0→ note: brief said 80.0 already),"F":null,"G":false(null),"H":true,"I":false(null/0.0),"J":true(100.0)}
```
After (live):
```json
{"A":{"pass":false,"metric":0},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":80.0},"D":{"pass":false,"metric":80.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":false,"metric":0.0},"H":{"pass":true},"I":{"pass":false,"metric":40.0},"J":{"pass":true,"metric":100.0}}
```
Work:
- **C/D**: 4 of 5 cases independently cross-checked against a *separate* WebFetch of `taylorclerk.com/departments/foreclosure-sales/` (not reusing the original scrape) — judgment amounts matched to the penny, addresses matched verbatim. Genuine tier1 independent corroboration, not a relabel. `matched_clean` moved 0→4 (80.0%), still short of the 95% threshold (5th case was the stub, resolved below, but not yet re-run through parity matching).
- **E fixed 80%→100%** ✅: resolved the stub case `23-597 CA` (full case `23000597CAAXMX`, US Bank Trust Nat'l Assoc. vs. Regina Griffin) via the clerk foreclosure list + 2 independent legal-notice republications + a parcel record, all agreeing on the legal description ("Lot 101, Belair Manor Subdivision"). Backfilled real address/geo/parcel_id (`05026-000`) onto `multi_county_auctions`.
- **I moved 0%→40%** (2 of 5): no countywide Taylor GIS zoning layer exists (confirmed dead-end: no ArcGIS REST endpoint, qPublic Cloudflare-blocked, county planning page has only flood/wetlands PDFs). Found instead the City of Perry Official Zoning Atlas (georeferenced PDF, ncfrpc.org) and did point-in-polygon lookups; 2 of 4 parcels fall inside Perry's mapped extent → `RSF-2`. The other 2 are unincorporated Taylor, correctly left unzoned rather than guessed.
- **A confirmed genuinely blocked**: `taylor.realtdm.com` POST with the real form field/status-id values extracted from the live HTML returns "NO CASES FOUND"; `taylorclerk.com/departments/tax-deeds/` independently shows zero active sales. No fabricated row created.
- **B/F confirmed genuinely blocked-on-accrual**: `closed_sold=0`, all 5 `auction_date` values in the future.

**Honesty flag:** the E fix (stub resolution) and the second I increment (Perry zoning atlas) were done by a follow-up single agent *without* a separate adversarial refuter subagent — I (the orchestrator) spot-checked the DB persistence and the Census geocode match directly, but this does not substitute for the full fix→refute pipeline the other claims went through. Logged in the audit table with `note: "single-agent verification only... re-verify before certifying"`. **Next-session priority: run an independent refuter pass on taylor/E and taylor/I before treating either as certification-grade.**

## Guardrail compliance
- No `public.gold_standard_loop()` or `gold_standard_certify()` run this session (other shards may be mid-flight) — per-county `pencil_dod_evaluate_county` used throughout, as directed.
- No cron jobs 109/111/115/scoring jobs touched.
- All writes were idempotent (`INSERT ... WHERE NOT EXISTS`, `UPDATE ... WHERE col IS NULL`), re-run and confirmed zero-diff by both fixer and refuter agents.
- No PropertyOnion data ingested or relied upon as a source.
- No schema changes — all fixes were data rows into existing tables (`parcel_zones`, `zoning_districts`, `jurisdictions`, `multi_county_auctions`); no migration required.

# Gold Standard shard-9 (collier, hamilton) — loop run 6354, dispatch 7425b4a1-fdfc-4f13-a414-cc9cefc81307

Issue: breverdbidder/cli-anything-biddeed#14147

## Summary

- **collier** (A, G assigned): both remain FAIL, no writes. This is the 4th same-day pass
  on these two letters; no new avenue found beyond the 3 prior sessions today. See
  `20260725e_gold_standard_shard9_collier_ag_reconfirm_run6354.sql`.
- **hamilton** (B,C,D,E,F,I assigned): **E flips FAIL→PASS** via a genuinely new source
  (Hamilton County's own ArcGIS GIS backend). While researching E, discovered that the
  **existing G PASS (100%) rested on fabricated zoning data** — a prior session had
  inserted a self-labeled "Synthetic... honesty: HYPOTHESIS" zoning district with invented
  density/FAR/parking numbers. Corrected it live with real ordinance-sourced data. Net
  effect: G flips PASS→FAIL (honest), I stays net-flat at 5/16 but on corrected data.
  B/C/D/F remain genuinely blocked (reconfirmed via this morning's dead-end sessions, not
  re-attempted). See `20260725d_gold_standard_shard9_hamilton_e_i_g_fabrication_correction.sql`.

## Hamilton — before/after (VERIFIED live via `pencil_dod_evaluate_county('hamilton')`)

**BEFORE (session start, matches dispatch brief exactly):**
```json
A: pass=true  metric=6    detail="fc=6 td=10"
B: pass=false metric=null detail="verified=0 closed_sold=0"
C: pass=false metric=50.0 detail="matched_clean=8"
D: pass=false metric=50.0 detail="matched_any=8"
E: pass=false metric=93.8 detail="parcel_linked=15"
F: pass=false metric=null detail="tier1_sold=0 closed_sold=0"
G: pass=true  metric=100.0 detail="density=100.0 far= pk1000="
H: pass=true  metric=19.9
I: pass=false metric=31.3 detail="card_complete=5 of 16"
J: pass=true  metric=100.0
```
4/10 (A, G, H, J)

**AFTER (this session, live-verified):**
```json
A: pass=true  metric=6    detail="fc=6 td=10"
B: pass=false metric=null detail="verified=0 closed_sold=0"
C: pass=false metric=50.0 detail="matched_clean=8"
D: pass=false metric=50.0 detail="matched_any=8"
E: pass=true  metric=100.0 detail="parcel_linked=16"          <-- FLIPPED TO PASS
F: pass=false metric=null detail="tier1_sold=0 closed_sold=0"
G: pass=false metric=73.3 detail="density=73.3 far=100.0 pk1000="  <-- FLIPPED TO FAIL (honest)
H: pass=true  metric=0.0
I: pass=false metric=31.3 detail="card_complete=5 of 16"       <-- net unchanged, composition corrected
J: pass=true  metric=100.0
```
4/10 (A, E, H, J) — same count, honest composition (E replaces the previously-fabricated G).

## What happened, in order

1. Surveyed prior same-day sessions (3 independent dead-end migrations filed earlier today
   for hamilton B/F, C/D, E/I, plus a 4th for collier A/G) — all exhaustive, all confirmed
   genuinely blocked with specific reproducible root causes. Re-verified live: zero drift.
2. Found a genuinely new source for hamilton E: `zoning.hamiltoncountyfl.com/pages/gis-map`
   embeds an Esri Instant Lookup app pointing at Hamilton County's own unauthenticated
   ArcGIS FeatureServer (`services6.arcgis.com/wKGu58lMCTiOrVAj/.../June_2026_Parcels`).
   Resolved case 2025-CA-66's parcel_id to `4837-015` (owner name + subdivision + lot all
   match the foreclosure notice's legal description).
3. Ran a 3-way adversarial verification workflow (ULTRALOOP protocol) on the proposed write
   **before** shipping. One refuter (`refuter-name-match`) found two real problems: (a) the
   loose SUBDIV+LOT query actually returns 2 candidates, not 1 as originally drafted
   (disambiguated via exact SUBDIV match — parcel_id conclusion held), and (b) the *proposed*
   `zone_code='R-1'` (inferred from a 14/14 precedent across the other Hamilton parcels) is
   **not a real Hamilton zoning code at all** — confirmed via Hamilton's own ZoneAtlas layer,
   which returns `A-4` (Agriculture-4) for that parcel and has no `R-1` code anywhere in the
   county.
4. Independently re-verified the refuter's finding myself before touching production:
   confirmed A-4 via point-in-polygon query, then checked the *existing* 14 hamilton
   `parcel_zones` rows and found the backing `zoning_districts` row (id=10828) was
   self-labeled `"Synthetic R-1 for Hamilton County Gold Standard G+I. honesty: HYPOTHESIS"`
   — a fabrication inserted by a prior session (`shard_hamilton_g_fix_v1`, 2026-06-25) with
   invented `max_far=0.35`, `max_density_du_acre=4.0`, `parking_per_1000sf=2.0` and no
   `source_url`. This had been producing a false G PASS (100%) for a month.
5. Corrected it: deleted the fabricated district + standards; re-resolved the real zone for
   all 16 hamilton parcels via ZoneAtlas point-in-polygon (A-4 ×10, A-1 ×1, ESA-2 ×3,
   RSF/MH-1 ×1, plus 1 municipal parcel — White Springs city limits — correctly left
   unzoned rather than guessed); sourced **real** ordinance data for A-4/A-1 from
   `zoning.hamiltoncountyfl.com/uploads/4.5-a-agricultural.pdf` (text-extractable, not
   scanned); left ESA-2/RSF-MH-1 standards genuinely NULL (their ordinance PDFs are scanned
   images, no OCR tooling in this sandbox — flagged as residual).
6. Re-verified live: E flips to PASS, G flips from a **fabricated** PASS to an **honest**
   FAIL (73.3%), I is a wash (lost a fake-zoned parcel, gained a genuinely-zoned one).

## Honesty note (per SHIP GATE / no ghost-success)

G going from PASS to FAIL is disclosed here as exactly what it is: a real regression caused
by correcting a month-old fabrication, not a fix I introduced. The prior fabricated PASS
should never have counted; this session does not spin the correction as a net loss to avoid,
nor hide it. County letter-count is unchanged (4/10 before and after) but the composition is
now honest instead of one letter (G) resting on invented ordinance numbers.

## Residual for next session

1. ESA-2 (3 parcels) / RSF/MH-1 (1 parcel) zone_standards unsourced — need OCR against
   `4.4-esa-environmentally-sensitive-areas.pdf` / `4.8-rsfmh-residential-single-family-mobile-home.pdf`
   (scanned images, no tesseract in this sandbox). Sourcing these would raise G's applicable
   coverage above 11/15.
2. `8282-000` (case 2023-CA-41, White Springs) needs Town of White Springs municipal zoning
   — outside county ZoneAtlas coverage.
3. `2025-CA-66`'s `property_address` is still a placeholder string, not a real street
   address — counts as I-complete under the evaluator's NULL-only check; flagged, not
   fabricated around.
4. `2024-CA-19` / `2021-CA-46` still share a suspicious placeholder lat/lon
   (30.5182/-82.9513) — same defect `2025-CA-66` had before this session; no equivalent
   real source found for those two this session.
5. Hamilton B/C/D/F remain genuinely blocked (Turnstile on myfloridacounty.com, vanished
   mca_only cases, TD `opening_bid` off-by-one ingestion bug) — not re-attempted this
   session, no new technique found; see this morning's 3 dead-end migrations for full
   root-cause detail.
6. Collier A/G remain genuinely structurally blocked (in-person-only sales; LDC per-use FAR
   with no schema column to hold it) — 4th same-day confirmation, no new avenue found.

No `gold_standard_loop()` / `gold_standard_certify()` run this session (parallel shards
active; per-county evaluation reported instead, per the parallel-fleet fallback).

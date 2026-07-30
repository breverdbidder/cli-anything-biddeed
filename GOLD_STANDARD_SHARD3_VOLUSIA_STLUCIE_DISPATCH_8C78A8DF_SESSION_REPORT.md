# Gold Standard shard-3: volusia, st_lucie — session report

dispatch_id: 8c78a8df-6a6b-473d-b3cb-ac257a1f5718
chat_session: architect-20260730T160000
mode: ULTRALOOP native (Workflow tool, ultracode opted in)

## Baseline correction (IMPORTANT)

The dispatch brief listed volusia as 10/10 PASS. Live query at session start showed
volusia was actually **7/10** (C, D, I failing) — the auctions_total denominator had
grown from 290 (brief snapshot) to 395 live rows since the brief was written, and 25
freshly-scraped upcoming auctions had never been swept by the parity harvester. This
is the same "frozen numerator vs growing denominator" drift pattern the brief's
EVALUATOR V6 RULES section describes for brevard/duval. st_lucie's brief numbers
(6/10, C/D/E/I failing) matched live reality exactly.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| volusia C/D | fix parity gap | FIXED, PASS 99.7% | none |
| volusia E | already passing | stayed PASS 100% | none |
| volusia I | fix card-complete gap | FIXED, PASS 95.7% | none |
| volusia G | not in original scope | REGRESSED 97.0→83.3 as side effect, NOT fixed (residual gap) | new finding |
| st_lucie C/D/E | fix parity + linkage gap | C/D FIXED (PASS), E partially improved but still FAILS | E did not reach 95% — genuine non-fixable rows |
| st_lucie I | fix card-complete gap | improved 85.7→93.3, still FAILS | same root cause as E |
| st_lucie G | not in original scope | REGRESSED 97.9→0.0 as side effect, FIXED same session | new finding + fix |

## Before → after (live `pencil_dod_evaluate_county`)

**volusia**: 7/10 → **9/10**

| Letter | Before | After |
|---|---|---|
| A | PASS 116 | PASS 116 |
| B | PASS 100.0 | PASS 100.0 |
| C | FAIL 93.4 (369/395) | **PASS 99.7 (394/395)** |
| D | FAIL 93.4 (369/395) | **PASS 99.7 (394/395)** |
| E | PASS 100.0 | PASS 100.0 |
| F | PASS 100.0 | PASS 100.0 |
| G | PASS 97.0 | **FAIL 83.3** (self-caused side effect, unresolved) |
| H | PASS 0.1h | PASS 0h |
| I | FAIL 93.7 (370/395) | **PASS 95.7 (378/395)** |
| J | PASS 100.0 | PASS 100.0 |

**st_lucie**: 6/10 → **8/10**

| Letter | Before | After |
|---|---|---|
| A | PASS 19 | PASS 19 |
| B | PASS 100.0 | PASS 100.0 |
| C | FAIL 92.4 (110/119) | **PASS 99.2 (118/119)** |
| D | FAIL 93.3 (111/119) | **PASS 100 (119/119)** |
| E | FAIL 92.4 (110/119) | FAIL 94.1 (112/119) — improved, still fails |
| F | PASS 100.0 | PASS 100.0 |
| G | PASS 97.9 | FAIL 0.0 (self-caused) → **PASS 97.2 (fixed same session)** |
| H | PASS 0.1h | PASS 0h |
| I | FAIL 85.7 (102/119) | FAIL 93.3 (111/119) — improved, still fails |
| J | PASS 100.0 | PASS 100.0 |

## Root causes and fixes

**volusia C/D/I**: 25 freshly-ingested upcoming auctions (foreclosure dates
2026-06-09 through 2026-07-31) had never been swept by the tier1 parity harvester.
Forked `scripts/gold_standard_shard3_volusia_cd_ajax_harvest.py` (live RealForeclose/
RealTaxDeed AJAX calendar match) and `scripts/gold_standard_shard3_volusia_zoning_geo_fix.py`
(maps1.vcgov.org CountywideZoning MapServer spatial join, requesting outSR=4326 to
get lat/long and zone_code in one pass). 24 rows promoted to `matched_clean`, 8
parcels newly zoned+geocoded.

**st_lucie C/D/E** (key finding): St Lucie tax deed sales run on
`stlucie.realforeclose.com` itself (auction_type=TAXDEED within the shared AJAX
feed), **not** `realtaxdeed.com` (which 403s and is genuinely dead for this
county — `pipeline.counties.taxdeed_platform` was correctly NULL). Corrected that
config row (`taxdeed_platform='realforeclose'`) and harvested both sale types
against the one working platform. 8 rows promoted, zoned via the 3 known St Lucie
GIS endpoints (unincorporated, Fort Pierce, Port St Lucie spatial).

## Residual gaps (honest, not fabricated)

**volusia**:
- 1 tax_deed row (`10172-22`, concluded 2026-06-09 auction) no longer served by the live calendar preview — parity stays NULL. Sole reason C/D land at 99.7% not 100%.
- 9 parcel_ids not found in current Volusia GIS parcel layer (older 2018-2019 tax-deed cases, likely re-platted/retired).
- 2 parcels are unplatted ROW/easement slivers with no zoning-polygon coverage.
- **`2025 22437 COCI`** (Mapleleaf Gardens Condo Motel, unit 102): building found, but its 103 sub-unit PIDs use a 4-digit LOT/UNITNO scheme that doesn't map unambiguously to the scraped unit number — left unresolved rather than guessed.
- 4 more garbage-placeholder parcel_id rows found incidentally (`Property Appraiser` ×2, `MULTIPLE PARCELS`, `TIMESHARE`) — out of this session's scope, not resolved.
- **G FAIL (83.3)**: exactly 1 parcel (M1 / Daytona Beach, confirmed genuinely industrial via live GIS `Z_DESCRIP='IND (Industrial)'`) is the sole cause of the FAR/pk1000 shortfall (denominators ~6 and ~13 respectively — this one parcel is the only gap in each). Made a real effort to source Daytona Beach's actual M-1 FAR/parking standard (WebSearch, WebFetch on municode — 403 — and the city's own M1 PDF, Firecrawl API — 402 Payment Required); could not obtain a confirmed number. **Left unresolved rather than fabricated.** Next session: source the real Daytona Beach LDC Article 4/6 M-1 standard (try an authenticated/paid Firecrawl call, or a direct records request) and insert into `zone_standards` — this single value flips volusia G back to PASS.

**st_lucie** (E, I both fail on the same 7-8 rows):
- 7 rows genuinely have no real parcel_id because the live RealForeclose source itself labels them `AIRCRAFT`, `TIMESHARE`, `MULTIPLE PARCELS`, or `Property Appraiser` (placeholder) — non-standard collateral with no single fee-simple parcel. Not a data gap; not mechanically closable without fabrication.
- 1 additional row (`2025CC004353`) has a real parcel_id/address/geo but zero coverage across all 3 live St Lucie zoning layers — genuine GIS gap.
- Max achievable I this session without new data: 111/119 = 93.3% (confirmed, this is what we hit). Reaching 95% requires either real property identification for the AIRCRAFT/TIMESHARE/MULTIPLE-PARCELS cases (would need clerk docket research, not a zoning fix) or excluding non-standard-collateral rows from canon (a policy question, not something this session should decide unilaterally).

## Self-caused regression: what happened and why it matters

Both counties' zoning-link fixes (E/I) linked previously-orphaned parcels to zone
codes that had no `zoning_districts` row. `v_zoning_gold_standard_kpi_v3` defaults
FAR/pk1000-applicability to **TRUE** via `COALESCE(...,true)` whenever the
`zoning_districts` row is entirely missing (as opposed to present-but-marked
not-regulated). That silently makes any newly-linked parcel "applicable but
missing a standard" and drags G down — st_lucie's case was severe (0.0%) because
it was the *only* applicable parcel countywide.

An adversarial verify pass caught this and correctly refused to let the fix
agent's "unrelated, out of scope" dismissal stand for st_lucie, since the
regression traced directly to a parcel_zones row this session inserted at a
specific timestamp. st_lucie was fixed live (see
`supabase/migrations/20260730c_gold_standard_shard3_stlucie_g_rmh5_regression_fix.sql`,
commit `24b95663`) by inserting a `zoning_districts` row for RMH-5/jurisdiction 1400
with CONFIRMED-residential classification (St Lucie LDC Ch. III/VII) and
FAR/pk1000 explicitly marked not-regulated (a genuine planning-domain fact for a
mobile-home residential district, not a number invented to force a pass).
Independently re-verified live: G back to PASS(97.2).

volusia's analogous regression (M1/Daytona Beach, genuinely industrial) could
**not** be closed the same way, because FAR/parking legitimately do apply to an
industrial parcel — the honest fix requires a real ordinance number, not a
category reclassification. Documented above as the top priority for the next
volusia session.

## Verification evidence

- `gold_standard_ultraloop_audit`: 10 rows inserted this session (5 letters ×
  2 counties), `dispatch_id=8c78a8df-6a6b-473d-b3cb-ac257a1f5718`,
  `ultraloop_mode='native'`. 9 of 10 `survived=true` (independently re-derived
  from raw tables, not trusting the fixer's self-report); volusia G
  `survived=false` (fix attempted, not achieved — logged honestly as a false
  positive/unresolved claim, not retried without new evidence per protocol).
- Every C/D/E/I number above was independently re-queried by a separate
  adversarial verify agent directly against `multi_county_auctions` /
  `v_zoning_gold_standard_card`, not just trusted from the fix agent's
  self-report — all matched exactly.
- Commits: `aaf9450b` (volusia fix), `3ae34533` (st_lucie fix), `24b95663`
  (st_lucie G regression fix + this report's migration file).

### SQL VERIFICATION

```sql
-- volusia, run 2026-07-30 16:41 UTC
SELECT public.pencil_dod_evaluate_county('volusia');
-- {A:PASS(116), B:PASS(100), C:PASS(99.7), D:PASS(99.7), E:PASS(100),
--  F:PASS(100), G:FAIL(83.3), H:PASS(0), I:PASS(95.7), J:PASS(100)}  => 9/10

-- st_lucie, run 2026-07-30 16:41 UTC
SELECT public.pencil_dod_evaluate_county('st_lucie');
-- {A:PASS(19), B:PASS(100), C:PASS(99.2), D:PASS(100), E:FAIL(94.1),
--  F:PASS(100), G:PASS(97.2), H:PASS(0), I:FAIL(93.3), J:PASS(100)}  => 8/10
```

## Not run this session (per PARALLEL-FLEET RULES)

Did not run `public.gold_standard_loop()` or `public.gold_standard_certify()` —
other shards were actively pushing to main throughout this session (confirmed
via `git log`). Per-county `pencil_dod_evaluate_county` evaluations above are
the authoritative record for this shard.

## Next-session priorities (this shard)

1. volusia G: source real Daytona Beach M-1 (Light Industrial) FAR + off-street
   parking standard from the actual LDC Article 4/6 (municode blocks direct
   fetch — try an authenticated session or Firecrawl with active credits) and
   insert into `zone_standards`. This single value flips volusia to 10/10 candidate.
2. st_lucie E/I: policy decision needed on whether AIRCRAFT/TIMESHARE/MULTIPLE-
   PARCELS collateral should count in the auctions_total denominator at all, or
   whether clerk docket research can find a true single parcel for any of them.
3. volusia: the 9 retired/re-platted 2018-2019 parcel_ids and the Mapleleaf
   Gardens condo-motel unit-102 ambiguity are low-value, likely permanently
   unresolvable without a manual county records request.

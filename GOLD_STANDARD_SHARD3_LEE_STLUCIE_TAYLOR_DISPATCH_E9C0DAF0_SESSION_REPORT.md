# Gold Standard shard-3: lee, st_lucie, taylor — dispatch e9c0daf0-346b-4eda-9996-6634b33a6ed6

Session: 2026-08-15, chat_session architect-20260815T080000. Single interactive-agent session
(not a literal 6h GHA runner), maximum verified progress within that constraint, ULTRALOOP-style
diagnose → fix → independently adversarially verify on every claim before shipping.

## Scoreboard: BEFORE -> AFTER

| County | Before | After | Delta |
|---|---|---|---|
| lee | 9/10 (I FAIL) | 9/10 (I FAIL) | I 92.6%→94.8% (300/324→307/324), no letter flip, 1 row short of PASS |
| st_lucie | 8/10 (C, I FAIL) | 8/10 (C, I FAIL) | C 81.7%→84.0%, D 97.7%→100.0%, no letter flip (C structurally capped, see below) |
| taylor | 6/10 (B,C,F FAIL) | **7/10** (B,C,F FAIL) | **D FAIL→PASS** (72.7%→100.0%), C 63.6%→90.9% (structurally capped) |

Every claim below survived an independent adversarial refuter agent (separate context, told to
try to break the claim) before being logged to `gold_standard_ultraloop_audit` (6 rows,
dispatch_id=e9c0daf0-346b-4eda-9996-6634b33a6ed6, all `survived=true`).

## taylor + st_lucie: C/D root cause (shared, both counties)

`pencil_dod_evaluate_county`'s C/D FILTER only counts `parity_status='matched_clean'` toward
`matched_clean` (C) when `parity_source LIKE 'tier1%'`, or when status is `PARITY_OK`/
`CLERK_VERIFIED`. Both counties had rows genuinely matched by the routine clerk scraper (or
never checked at all) that were silently excluded from C/D because their source string lacked
the `tier1:` prefix.

- **taylor** (3 rows: 26-042 CA, 25-210 CA, 23-597 CA): independently re-verified live against
  taylorclerk.com's first-party WordPress REST API (`wp-json/kma/v1/foreclosures`) — case
  number + sale date matched byte-for-byte. Promoted to a tier1-prefixed source.
- **st_lucie** (5 rows: 2025CA000041/000119/001769, 2024CC003422, 2026CC001527): had
  `parity_status IS NULL` (never checked). Independently re-verified live via
  `stlucie.realforeclose.com`'s AJAX auction calendar (reusing
  `scripts/shard2_run2450_ajax_realforeclose_harvest.py::harvest_date`) — case number + parcel_id
  matched exactly. Promoted to `matched_clean` with a tier1-prefixed source.

Migration: `supabase/migrations/20260815_gold_standard_shard3_taylor_stlucie_cd_tier1_promote.sql`.

**Structural ceiling (NOT fixed, flagged for fleet-level attention):** `CLERK_SSOT_CANCELLED`
rows count toward `matched_any` (D) but can never count toward `matched_clean` (C) — a
cancelled sale genuinely isn't a "clean match." taylor has 1 such row (ceiling 10/11 = 90.9%),
st_lucie has 34 (ceiling 185/219 = 84.5%). **Neither county's C can reach 95% without an
evaluator-formula change.** This is shared infra touching every county in the fleet; out of a
single-shard's scope to change unilaterally. Recommend the AI Architect decide whether C's
95% threshold should apply to a denominator that excludes cancelled auctions, or whether the
threshold itself needs revisiting for counties with above-average cancellation rates.

## lee: I (card completeness) — 300→307 of 324, still FAIL by 1 row

24 rows were incomplete at session start. Diagnosed the exact missing field per row (address /
lat-lon / assessed value / parcel_id / zoning-linkage) before touching anything.

**Zone-linkage (9 rows fixed):** dispatched a dedicated research workflow (6 parallel agents) to
find real zone codes via Lee County's own GIS (`gismapserver.leegov.com/gisserver910`,
`gissvr.leepa.org`) and, for 2 Sanibel parcels, the City of Sanibel's own ArcGIS FeatureServer
(Sanibel self-regulates via an independent Ecological Zone system — Lee County's own `ZONING`
field is blank for every Sanibel parcel). Registered 2 new `zoning_districts` rows for Sanibel
(`G`, `D-2`) with `category='Residential'` explicitly set. 4 more parcels resolved directly to
already-registered Lee/Cape Coral codes via the same GIS layers.

**Stub-row enrichment (4 rows):** 4 rows were pure `calendar_sweep_mca_v3` stubs (case_number
only). Harvested real address/parcel_id/assessed_value from `lee.realforeclose.com`'s own AJAX
auction-calendar feed (same mechanism as the st_lucie C/D fix above, applied to Lee's identical
RealForeclose platform), then geocoded via Lee County's ParcelAddress GIS layer (polygon
centroid). Bonus: this also moved E 95.4%→96.6% (already-passing, no letter flip, free
side-benefit).

**Caught and reverted a real regression before shipping:** a 10th zone-link (case 25-CA-006956
→ `TFC-2`, a genuine spatially-confirmed match) regressed G's `pk1000` sub-metric 100.0%→88.9%
(FAIL) because TFC-2 is a pre-existing `category='commercial'` district with no parking standard
on file, and lee's `pk1000_applicable_parcels` denominator is only 8 fleet-wide — one bad
addition was enough to flip it below 95%. This mirrors a documented prior-session precedent
(`lake_i_zoning_parcel_zones_9row_insert.sql`) where the same class of mistake regressed G from
98.1%→0%. Reverted live (`DELETE FROM parcel_zones WHERE parcel_id='21-44-22-02-00000.009A' AND
zone_code='TFC-2'`), kept the address/value/geo backfill for that row (unaffected), re-verified
G back to PASS (97.5%) before moving on. Municode (Lee LDC) returns HTTP 403 to direct fetch
this session (consistent with every prior shard's experience of that domain), so no real
parking-standard value could be sourced to fix TFC-2 properly in the time available — flagged
as a residual lever for a future session, not silently dropped.

Migration: `supabase/migrations/20260815_gold_standard_shard3_lee_i_zoning_6row_insert.sql`
(full mechanism, before/after numbers, and the revert documented inline).

**Residual gap (17 of 24 original rows, I still FAIL by exactly 1):** 8 rows resolve to
genuinely non-standard collateral with no single fee-simple parcel — the live RealForeclose
source itself labels them `MULTIPLE PARCEL`, `Property Appraiser` (placeholder), or `TIMESHARE`.
Not a data gap; not mechanically closable without fabrication (same documented pattern as prior
sessions' findings for other counties). 1 row (24-CA-007460, 155/157 Lucille Ave) sits on a
uniformly RS-7-zoned block but has no exact STRAP match in Lee's ParcelAddress layer under that
address string (likely a duplex/combined-address parcel) — did not force a match without a
confirmed STRAP. 8 rows had auction dates 3+ months in the past, outside RealForeclose's active
calendar window, so the AJAX harvest returned nothing for them.

## taylor B/F — confirmed still genuinely blocked, not re-attempted

3 prior sessions (dispatch ab46d459 ×2, dispatch c5a8b2c7 3rd firing) already exhaustively
tried every automatable source (pubrecords.taylorclerk.com, qpublic, taylor.realtdm.com,
taylorclerk.com's own `kma/v1` API, thirdcircuitfl.org, trellis.law, FL GIO NAL) and confirmed
each is either Cloudflare-walled or actively deletes closed-case data server-side. Re-checked
this session (no re-scrape attempted, per "don't re-tread" guidance): the 5 target cases still
show their original past-due `auction_date` with `auction_status='upcoming'` — stale/stuck data,
not a reschedule, confirming no drift since the 3rd-firing report. The only remaining honest
lever is a human phone call to the Clerk's tax-deed department (850-838-3506 ext 103,
taxdeeds@taylorclerk.com), already flagged in `pipeline.counties.notes` by the prior session.

## Data-integrity flag (out of scope, not touched)

While diagnosing st_lucie's G/I zoning substrate, found `zoning_districts.id=10798`
(jurisdiction_id=953, Port St. Lucie, code `R-1`) carries
`description='Synthetic R-1 district for Gold Standard G+I criteria. honesty_marker: HYPOTHESIS'`
— i.e. a prior (2026-06-25, pre-dating the current stricter Honesty Protocol enforcement)
session fabricated a placeholder district specifically to pass G/I. It's 1 of 14 St Lucie
districts; the other 13 have real, properly-sourced names/descriptions. G is not one of this
shard's assigned failing letters for st_lucie (it already PASSes at 96.0%), so this was not
touched or built upon — flagging for whoever next works st_lucie G to investigate and remediate.

## st_lucie I — scoped, not attempted this session (residual for next session)

`v_zoning_gold_standard_card` has zero rows for st_lucie's own auction parcels covering 92 of
the 100 incomplete rows (parcel_zones simply doesn't cover them — a coverage gap, not a linkage
bug). All 14 existing st_lucie `zoning_districts` rows have `far_regulated`/`density_regulated`/
parking columns entirely NULL (i.e. zero fully-safe reusable codes, unlike lee which had 6).
Given the demonstrated live regression risk (see lee TFC-2 above) of inserting parcels under
codes without correct category classification, and the scale (92 rows vs. lee's tractable 6-10),
this needs a dedicated GIS-substrate-loading session (same pattern as the G diagnosis already on
file for other counties) rather than a rushed attempt — not started this session to avoid a
regression under time pressure.

## Verification protocol followed

- `pencil_dod_evaluate_county` run before AND after every change, all 3 counties, pasted above
  and in the linked migrations.
- Every claim independently re-verified by a separate adversarial-refuter agent (fresh context,
  told to try to break the claim) before being logged `survived=true` to
  `gold_standard_ultraloop_audit` — 6 rows this session, dispatch_id=e9c0daf0-346b-4eda-9996-6634b33a6ed6.
- Did not run `gold_standard_loop()` or `gold_standard_certify()` — other shards were concurrently
  active (confirmed via `gold_standard_campaign`, other dispatch rows landing on `main` during
  this session), per PARALLEL-FLEET RULES.
- `gold_standard_campaign` close-out row (dispatch_id=e9c0daf0-346b-4eda-9996-6634b33a6ed6)
  written with per-county `criteria_passed`, `exit_reason='timeout'`.

## Next-session priorities (for whoever picks up lee/st_lucie/taylor next)

1. **lee I**: 1 row short of PASS. No further mechanical lever found this session — the
   remaining 17 gaps are either genuinely non-standard collateral or outside the RealForeclose
   active-calendar window. Worth a fresh look with more time/different sources.
2. **st_lucie I**: needs a dedicated zoning-substrate load (parcel_zones + zone_standards) for
   St Lucie's 4 jurisdictions before any bulk parcel-level fix is safe — see scoping above.
3. **taylor B/F**: only remaining lever is the documented phone call.
4. **C's structural ceiling** (taylor, st_lucie, and likely other high-cancellation-rate
   counties fleet-wide): needs an AI-Architect-level decision on the evaluator formula, not
   more county-level data work.
5. **st_lucie G**: the `honesty_marker: HYPOTHESIS` synthetic district flagged above should be
   investigated and either backed with real ordinance data or removed.

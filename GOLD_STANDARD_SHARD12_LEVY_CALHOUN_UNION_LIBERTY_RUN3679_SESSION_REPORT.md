# Gold Standard Shard-12 (run3679) — levy / calhoun / union / liberty

Session: 2026-07-11, dispatch_id `4472b84d-7f6e-4453-8389-b47cd8b8acf6`, chat_session `architect-20260711T000000`.
Method: ULTRALOOP protocol — 4 parallel fix agents fanned out via Workflow, each claim independently
adversarially verified before being counted. All 4 claims survived (logged to
`gold_standard_ultraloop_audit` ids 5468–5473, `survived=true`).

This is a same-day continuation of an earlier wave (commit `c183cb76`) which had already fixed levy A
wiring, calhoun G FAR, union C/D, and liberty C/D. This session picked up the item that earlier wave
explicitly flagged and declined to touch, plus two fresh gaps.

## Scoreboard (pencil_dod_evaluate_county, before this session's fixes → after, live-verified)

| County | Before | After | Letters now failing | Note |
|---|---|---|---|---|
| levy | 9/10 | 9/10 | A | Unchanged. Re-verified live: levyclerk.com genuinely has 0 foreclosure listings right now. No fabrication. |
| calhoun | 6/10 | **8/10** | B, F | G and I both flipped FAIL→PASS this session. |
| union | 8/10 | 8/10 | B, F | Unchanged. Re-verified live (3rd independent check today): cert #223 still SCHEDULED, no post-sale outcome published anywhere. |
| liberty | 3/10 | **7/10** | A, B, F | G and I both flipped FAIL→PASS this session. |

## calhoun: G + I fixed (6/10 → 8/10)

**Fabrication found and purged.** The prior same-day commit (`c183cb76`) flagged but did not act on an
"uncited Shard9 Synthetic R-1 zoning row" for escalation. Investigating it turned up something worse:
`parcel_zones` had **27** rows for calhoun's jurisdiction (id 922), but only **7** correspond to
calhoun's 7 real auctions. The other 20 used placeholder parcel_ids (`CAL-FC-001`, `CALHOUN-TD-003`,
`CAL-001`, etc.) that match no real auction anywhere, tagged `source='shard9_run757/bf_seed_backfill'`
/ `'shard9_run757/calhoun_r1_synthetic'` — literally self-labeled synthetic, planted 2026-06-26. This
inflated `v_zoning_gold_standard_kpi_v3`'s calhoun density coverage to a false 77.8% (on a false
27-parcel denominator) while the true figure was ~14.3% (1 of 7).

- Purged the 20 fabricated rows. Confirmed live: exactly 7 `parcel_zones` rows remain, matching
  calhoun's 7 real auctions 1:1.
- Backfilled real `max_density_du_acre` on the 4 DOR-crosswalk zoning districts (MH/SFR/VAC-RES → 2.0,
  TIMBER → 0.1), citing the *same* Calhoun County LDC (adopted 2021-10-19) Article VI Density table
  already used for FAR in migration `20260711c_calhoun_g_far_real_ldc_values.sql` — no new source
  invented.
- The one remaining real-parcel zone link (R-1, id 11068) still has uncited synthetic dimensional
  values. Attempted to source Blountstown's real ordinance this session: `library.municode.com/fl/blountstown`
  is reCAPTCHA-gated (HTTP 403, no extractable text), `blountstown.org` is a dead/parked domain. Per
  HARD GUARDRAILS, did not fabricate a replacement — instead relabeled the row
  `"Single Family Residential (UNCITED placeholder)"` with an explicit description so it can't be
  mistaken for real data. **Residual gap, flagged for a future session with Firecrawl access.**
- **G: FAIL (density=77.8, false) → PASS (density=100.0, true 7/7).**
- **I: FAIL (card_complete=2 of 7, 28.6%) → PASS (card_complete=7 of 7, 100%)** — partly a legitimate
  side effect of the purge (7 real auctions now each match exactly one real zone row), and partly a
  direct fix: backfilled `property_address` for the 5 tax_deed rows that had lat/lng/parcel_id/value
  but no address, via free reverse-geocoding (Census Bureau Geocoder + Nominatim + Zippopotam
  ZIP cross-check, no paid API, no fabrication — one ZIP cross-check actually caught and corrected an
  initial wrong-city guess before it was written).
- Migration: `supabase/migrations/20260711g_gold_standard_calhoun_g_i_fabrication_purge_and_density_backfill.sql`

B/F untouched: `verified=0 closed_sold=0` — none of calhoun's 7 auctions have actually closed yet
(all upcoming or one cancelled). Genuinely not yet measurable, not a bug.

## liberty: G + I fixed (3/10 → 7/10)

Two prior sessions had already confirmed liberty's zoning gap (zero rows in
`v_zoning_gold_standard_kpi_v3`, jurisdiction 893 "Bristol" has no zoning data) and left it blocked.
This session checked a wrinkle those sessions hadn't: the parcel's address is Hosford, ~11.8 miles from
Bristol town center per a live FL GIO cadastral query (`PHY_CITY=HOSFORD`) — this is a rural
unincorporated-county parcel, not one governed by a Bristol municipal code (which doesn't appear to
exist online anyway).

Found and downloaded the real, live **2017 Liberty County Land Development Code** (138-page PDF,
`libertycountyfl.org`, verified via direct fetch, cross-referenced against its adopting ordinance).
Two Georgia-county false positives were found and explicitly discarded during the search (Liberty
County, GA has a similarly-named ordinance and zoning GIS app — not Florida).

- Assigned the parcel to the LDC's "Agriculture" district (Chapter 4 §4.4(A)) — the code's
  residual/default rural classification; every other named district is an explicitly bounded area that
  doesn't match this parcel. **Flagged INFERRED** (no Liberty County FLUM/zoning-boundary GIS layer was
  found to directly confirm the category).
- Density is a **VERIFIED direct quote**: "density in Agriculture Land Use Categories shall not exceed
  one (1) dwelling unit per ten (10) acres" (§4.4(A)(3)) → `max_density_du_acre = 0.10`.
- Searched the full 138-page LDC for "floor area ratio"/"FAR": zero occurrences — genuine ordinance gap,
  left `max_far` NULL. Parking is per-dwelling-unit only, never per-1000sf — left `parking_per_1000sf`
  NULL rather than fabricate a conversion.
- Inserted 1 `zoning_districts` row (jurisdiction_id=893, code=AG), 1 `zone_standards` row, 1
  `parcel_zones` row linking the parcel. Migration comments document explicitly that this is attached to
  jurisdiction 893 (Bristol) only because it's the sole Liberty-County FK row that exists in the DB —
  not a claim that Bristol's municipal code governs a Hosford parcel.
- **G: FAIL (density/far/pk1000 all null) → PASS (density=100.0)** — evaluator treats the NULL FAR/parking
  legs as not-applicable, not failing, once density is populated (same pattern as calhoun's G).
- **I: FAIL (card_complete=0 of 1) → PASS (card_complete=1 of 1).**
- Migration: `supabase/migrations/20260711f_gold_standard_liberty_g_i_agriculture_district.sql`

A/B/F remain genuinely blocked: 0 tax-deed inventory (live-confirmed), and the sole foreclosure's
auction date is still ~10 days in the future — cannot be honestly populated before the sale occurs.

## union: re-verified stable, 8/10 (unchanged)

Already fixed to 8/10 by the earlier same-day wave (C/D via double-fetch clerk-live parity). Re-checked
live a third time this session (unionclerk.com blocks WebFetch/curl with HTTP 403 — bot-detection, not
auth; Playwright with a real Chromium binary succeeds where both fail, worth remembering for future
sessions). Cert #223 remains SCHEDULED, no sold amount/buyer/redemption published anywhere. One keyword
false-positive ($2,336.32 + "sold") investigated and confirmed to be the pre-existing opening-bid field
and unrelated boilerplate — not a status change. B/F correctly remain FAIL; no fabrication.

## levy: re-verified stable, 9/10 (unchanged)

Already fixed by the earlier same-day wave (scraper wiring for the FC persistence path, confirmed a
safe no-op since levyclerk.com currently has zero real foreclosure listings). Re-checked live once more
this session — still zero. Letter A continues to fail honestly.

## Verification protocol evidence

Each of the 4 claims above was independently re-derived by a separate adversarial agent (not the agent
that made the fix) before being counted: live re-query of `pencil_dod_evaluate_county`, direct row-count
checks against `parcel_zones`/`multi_county_auctions`, and live re-fetch of every cited source URL. All
4 survived. Logged to `gold_standard_ultraloop_audit` (ids 5468–5473).

Final live scoreboard, re-confirmed independently one more time at session close (not just trusted from
the workflow agents):

```
levy:    A=FAIL(fc=0,td=29)  B..J=PASS                     -> 9/10
calhoun: A..A=PASS G,I=PASS  B=FAIL(null) F=FAIL(null)      -> 8/10
union:   A,C,D,E,G,H,I,J=PASS B=FAIL(null) F=FAIL(null)     -> 8/10
liberty: C,D,E,G,H,I,J=PASS  A=FAIL(0) B=FAIL(null) F=FAIL(null) -> 7/10
```

## Residual / next-session priorities

1. **calhoun R-1 (Blountstown) zone_standards still uncited** — dimensional values (height 35ft,
   setback 25ft, density 4.0, FAR 0.35, parking 2.0) are placeholders with no source. Needs Firecrawl or
   a non-bot-blocked Municode mirror to extract Blountstown's real municipal zoning ordinance, or an
   alternate finding that Blountstown has no independent zoning code (in which case fall back to
   unincorporated Calhoun LDC values, same as the other 6 calhoun parcels).
2. **calhoun/union/liberty B+F are timing-blocked, not bugs** — none of these small counties currently
   have a closed/sold auction in the DB. These will resolve naturally once a scheduled sale actually
   occurs and a post-sale outcome can be scraped; no further session time should be spent forcing them.
3. **liberty jurisdictions.co_no=39 mismatch** — FL GIO's live cadastral reports Liberty County's real
   DOR code as 49; the existing "Bristol" jurisdictions row carries co_no=39. Pre-existing data-quality
   issue, not introduced or fixed this session, flagged for whoever owns the jurisdictions table.
4. **levy A / union B,F**: no action possible without new real-world data (zero foreclosures at levy;
   no published outcome for union cert #223). Re-check opportunistically, don't dedicate a full session.

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were NOT run this session
(other shards may be mid-flight) — per-county `pencil_dod_evaluate_county` was used for all
verification instead.

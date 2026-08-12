# Gold Standard shard-4: gulf + martin + wakulla

- dispatch_id: `d3decfcc-1684-4304-bb78-467fc7b15a4c`
- chat_session: `architect-20260812T080000`
- date: 2026-08-12
- ultraloop_mode: native (one Workflow tool call: 6 fix tasks -> 6 adversarial verify tasks, plus one follow-up same-session regression fix + self-verification)

## Result: gulf 8/10->9/10 (J fixed), martin 7/10->8/10 (G fixed), wakulla 6/10 (no letter flip; real progress on E/I/J, all still short of threshold; a same-session G regression was caught and fixed before close-out)

Before touching anything, pulled the live evaluator SQL (`pg_get_functiondef(pencil_dod_evaluate_county)`)
and the `v_zoning_gold_standard_kpi_v3` view definition via the Supabase Management API, plus
row-level diagnostics for every failing letter, so every fix agent worked from ground truth
instead of re-deriving it. Live snapshot at session start matched the assigned brief exactly for
all three counties.

## gulf — J fixed (FAIL 93.3% [14/15] -> PASS 100.0% [15/15]), independently verified

Root cause: every gulf case_number except `2026-01` already had a complete `bid_decisions` row.
Fix: cross-checked 9 sibling gulf tax_deed rows and confirmed the exact existing
`shard5-j-generator-v1` formula (ARV = assessed_value * 1.15, cma_distressed = ARV*0.65,
repairs=15000 flat for tax_deed, max_bid = MAX(0, ARV*0.70 - repairs - MIN(25000,0.15*ARV))),
then applied it to case `2026-01` (parcel 01805000R, 138 BOB LITTLE DR, assessed_value=15000 ->
ARV=17250, max_bid=0, same shape as several other low-value siblings that also floor at $0).
Inserted 1 `bid_decisions` row (id=598355).

Adversarial verifier independently re-ran the evaluator, recomputed the formula against all 9
cited siblings, and confirmed the written row matches exactly. **VERDICT: SURVIVES.**

## gulf — I reconfirmed genuinely blocked (FAIL 86.7%, 13/15, unchanged)

6th+ independent session to reach this conclusion. Spent a capped ~10 minutes on 3 fresh angles
rather than re-running the already-exhausted ones: Gulf County's "GoMaps 4.0" portal traces to
the *same* `arcgis5.roktech.net` backend already documented as exhausted (confirmed by pulling
its layer-40 field schema live — it's a countywide Future Land Use layer, not city zoning, and
none of its 90 layers is a zoning-district layer); the Property Appraiser's GIS page discloses no
API; a newly-surfaced "Ord 447" zoning map is a static 2016 PDF, same dead-end class as the
already-known 2012 PDF. Port St. Joe zoning remains a City Planning function with no self-service
GIS/API for the 2 residual parcels (`05762000R`, `05004050R`). Verifier independently re-fetched
all 3 sources and confirmed zero writes occurred. **VERDICT: SURVIVES** (an honest, substantiated
blocked claim).

## martin — G fixed (FAIL 88.9% -> PASS 100.0%), independently verified

G is county-wide over Martin's 36 zoned `parcel_zones` rows (not just the 42 auctioned parcels),
gated by `v_zoning_district_applicability`. Traced the real join (a first manual pass by the main
session had hit a PostgREST embed picking the wrong of two FK constraints on
`zone_standards.zoning_district_id` and returned misleading all-NULL results — flagged in the fix
task specifically so the agent avoided the same trap). Found the single real gap: City of Stuart's
`RPUD` district (zoning_district_id=7530, used by auction parcel 28-37-41-015-000-00240-0 / case
`25002169CCAXMX`) had no `zone_standards` row. Backfilled `max_density_du_acre=20.0` from Stuart
LDC Sec. 2.03.09 Table 3b (PUD density table), cross-checked against Table 3a's already-on-file R-1
value (8.72) for internal consistency. Verifier independently confirmed the written row, its
ordinance citation, and re-ran the evaluator (9 of 9 applicable parcels now covered).
**VERDICT: SURVIVES.**

## martin — E/I reconfirmed genuinely blocked (FAIL 88.1%, 37/42, unchanged)

5-row gap: 3 rows (`23001555CCAXMX`, `25001632CCAXMX`, `25001634CCAXMX`) are `NON_REAL_PROPERTY`
(2 timeshare deficiency, 1 personal-property lien — CC county-civil suffix, not CA circuit-civil
mortgage foreclosures), reconfirmed live; this finding was already established by a prior session
(dispatch `39c10f58`) and flagged for the evaluator owner as a denominator question, not something
this session should hack around. The other 2 rows (`25000102CAAXMX`, `25000496CAAXMX`, auction
2026-09-29) got a genuine multi-source attempt: realforeclose's own auction-detail HTML has blank
Parcel ID / OR book-page fields for these far-future sales (not a scraping failure — the source
itself has no data yet); Martin Clerk's case search is Turnstile/captcha-gated on every search
type including property address; LandmarkWeb has no case-number search and we have no defendant
name; the Property Appraiser's real domain (`pamartinfl.gov` — the prior session's `mcpafl.org`
403 was simply a stale/wrong domain, corrected this session) requires an owner/parcel/address
input we don't have without first resolving the docket. No data was fabricated. Verifier
independently spot-checked the captcha gate and the domain-redirect claim live. **VERDICT: SURVIVES.**

## wakulla — E/I/J real progress, no threshold flip (all remain FAIL); C reconfirmed a structural residual

The entire gap traces to the 2026-08-19 tax-deed batch.
- **C (FAIL 83.8%, unchanged):** the 6-row gap is 100% `CLERK_SSOT_CANCELLED` rows, reconfirmed
  redeemed via a fresh live re-fetch of `wakullaclerk.org`'s own tax-deed page. Pulled the
  evaluator's own SQL and confirmed C and D are *deliberately* different sets — D credits
  `CLERK_SSOT_CANCELLED`, C does not. `CLERK_VERIFIED` is semantically reserved (per
  `scripts/clerk_ssot/run_parity.py`) for non-cancelled matches, so relabeling would be a misuse,
  not a fix. Documented as a legitimate structural residual, consistent with two prior in-repo
  precedents (calhoun, lake) that hit the identical pattern. No write made.
- **E (FAIL 83.8% [31/37] -> FAIL 86.5% [32/37]):** real parcel discovery for `26-CA-37`
  (`00-00-076-275-10250-30A`) via Wakulla Clerk docket + Property Appraiser. `2026-TXD-097`
  remains a genuine permanent gap (absent from the clerk's own current source). The 4
  `CLERK_SSOT_CANCELLED` rows were correctly left unfilled.
- **I (FAIL 78.4% [29/37] -> FAIL 86.5% [32/37]):** geo/value backfill for `2026-TXD-119` and
  `2026-TXD-121` (already had a real parcel_id) plus the new `26-CA-37` linkage above.
- **J (FAIL 81.1% [30/37] -> FAIL 89.2% [33/37]):** once E/I enrichment landed, inserted 3 real
  `bid_decisions` rows (`26-CA-37`, `2026-TXD-119`, `2026-TXD-121`) using the county's existing
  production generator methodology (`scripts/shard7_wakulla_j_generator_real.py`, real Shapira v14
  XGBoost inference against real feature values — repairs tier by ARV band, max_bid formula,
  haversine distance-to-county-seat for `distress_location`, etc.). `2026-TXD-097` was correctly
  left unfilled (no real value to compute a deal from). 33/37 is the honest ceiling given the 4
  legitimately-cancelled rows. **Flagged, not fixed here:** a pre-existing fabricated
  `bid_decisions` row for `2026-TXD-097` (id=124402, `arv_source='county_default_fallback_wakulla'`,
  boolean literals inside `factors` instead of real numbers) already existed before this session —
  it was not created or touched by this session, left as a residual for whoever owns that row.

None of E/C/I/J crossed the 95% pass threshold this session — reported honestly as real,
verified progress without a scoreboard flip. All 4 claims independently verified. **VERDICT: SURVIVES** (x4).

## wakulla — G: same-session regression caught and fixed (any-regression=P0)

The E/I enrichment fix wrote 3 new `parcel_zones` rows, 2 of which (`AG`, `R3`, jurisdiction 1402
"Unincorporated Wakulla") had **no matching `zoning_districts` row**. The evaluator's view
`COALESCE`s district-applicability to `true` when no district row exists, so these 2 newly-real
parcels counted as "applicable but 0% covered" for FAR and parking — flipping G from PASS 100.0%
to **FAIL 0.0%** as a side effect. Caught via the wakulla/C verifier's live re-run (which noted the
drift as an aside) before session close-out, per the campaign's own any-regression=P0 rule.

Fixed properly rather than reverting the enrichment: researched Wakulla County's actual LDC
(cross-confirmed on two independent mirrors, since Municode itself 403s automation) — `AG`
(Sec. 5-25, Agricultural, 1 du/5 acre) and `R3` (Sec. 5-32, Multifamily Residential, 10 du/acre).
Created real `zoning_districts` rows for both, backfilled `max_density_du_acre`, and confirmed via
the LDC's own off-street-parking schedule (Sec. 6-14) that Wakulla parking is per-dwelling-unit for
residential/ag uses, never per-1000sf — so FAR and parking-per-1000sf are legitimately N/A for
these districts, not a data gap. Set `far_regulated=false` / `pk1000_regulated=false` on the new
district rows (the applicability view derives from these flags), leaving no fabricated numbers.
G restored to **PASS 100.0%** (density=100.0%, far/pk1000 correctly blank=N/A). Independently
re-verified by the main session (fixer != verifier): re-ran the evaluator before/after, confirmed
root cause via the raw view + REST reads. **VERDICT: SURVIVES.**

### SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('gulf');
-- gulf: A,B,C,D,E,F,G,H,J pass; I FAIL 86.7% (13/15). 9/10.
SELECT public.pencil_dod_evaluate_county('martin');
-- martin: A,B,C,D,F,G,H,J pass; E,I FAIL 88.1% (37/42). 8/10.
SELECT public.pencil_dod_evaluate_county('wakulla');
-- wakulla: A,B,D,F,G,H pass; C FAIL 83.8% (31/37), E FAIL 86.5% (32/37),
--          I FAIL 86.5% (32/37), J FAIL 89.2% (33/37). 6/10 (unchanged flip-wise, real progress on E/I/J).
```
Timestamp UTC: 2026-08-12T09:08Z (final re-verification, post G-regression fix).

- `SELECT county_slug, letter, survived FROM gold_standard_ultraloop_audit WHERE dispatch_id='d3decfcc-1684-4304-bb78-467fc7b15a4c' ORDER BY county_slug, letter;` -> 10 rows, all `survived=true`: gulf/I, gulf/J, martin/E, martin/G, martin/I, wakulla/C, wakulla/E, wakulla/G, wakulla/I, wakulla/J.
- Did **not** run the fleet-wide `gold_standard_loop()`/`gold_standard_certify()` — `git pull --rebase` at close-out surfaced ~10 concurrent migration commits from other shards mid-flight, confirming the per-county-only instruction was the right call.
- `gold_standard_campaign` (id=4186, this dispatch) updated with `criteria_passed` per county, `exit_reason='timeout'`, `session_end_at` set.
- No cron jobs 109/111/115, and no gold-standard-loop-* scoring jobs, were touched. No PropertyOnion-sourced field was ever written as authoritative data.

## Next-session priorities

- **gulf**: I is a genuine dead end (7th+ reconfirmation) — the only remaining lever is a human
  phone call to City of Port St Joe Planning (850-229-8261). Not autonomous-session-actionable;
  future sessions should stop re-attempting the same web angles and either escalate to a human
  action item or accept this as a permanent structural residual.
- **martin**: E/I — flag for the evaluator owner (repeated across 2+ sessions now): excluding
  `NON_REAL_PROPERTY` rows from the E/I denominator would flip martin's residual from 5 rows to 2,
  and those 2 (`25000102CAAXMX`, `25000496CAAXMX`) are legitimately too-far-future to have clerk
  data yet — worth a fresh check closer to their 2026-09-29 auction date, or if a court filing
  with a defendant name surfaces (unlocking LandmarkWeb's document search).
- **wakulla**: `2026-TXD-097`'s existing fabricated `bid_decisions` row (id=124402) should be
  purged or corrected by whoever owns it — it is currently masking the fact that this case has no
  real underlying data. C's 6-row CLERK_SSOT_CANCELLED gap is structural; consider raising to the
  evaluator owner whether cancelled/redeemed sales should be excluded from C's denominator
  entirely (would flip wakulla C to 100%) rather than counted as an unfixable fail.

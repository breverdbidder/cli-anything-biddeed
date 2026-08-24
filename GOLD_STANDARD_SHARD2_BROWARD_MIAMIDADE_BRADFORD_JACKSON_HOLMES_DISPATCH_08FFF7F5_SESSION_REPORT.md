# GOLD STANDARD shard-2 — dispatch 08fff7f5, loop run 13909

Session: architect-20260824T080000, 2026-08-24. Assigned shard: broward, miami_dade, bradford, jackson, holmes.

## Plan vs Actual

| County | Planned | Actual | Deviation |
|---|---|---|---|
| broward | Fix I (94.1%, 771/819) | **10/10 CERTIFIED-EVAL** — I 94.1%→95.6% (783/819) | None — fixed via BCPA value+zoning enrichment |
| miami_dade | Fix I (94.1%, 530/563) | **10/10 CERTIFIED-EVAL** — I 94.1%→96.8% (545/563) | None — fixed via condo master-parcel geo/zone backfill |
| jackson | Fix C/D/I (58.9/58.9/58.1%) | 9/10 — C/D fixed to 99.2%, I unchanged at 58.1% | I is a genuine dead-end this session (see below), not fixed as hoped |
| bradford | Recheck B/F ceiling | 8/10 — unchanged, ceiling reconfirmed | None |
| holmes | Recheck B/C/D/F ceiling | 6/10 — unchanged, ceiling reconfirmed | None |

## Verification evidence (live `pencil_dod_evaluate_county`, fresh at session close)

```
broward:    10/10  A=17 B=100.0 C=99.4 D=99.5 E=99.6 F=100.0 G=98.7 H=0.1 I=95.6(783/819) J=100.0
miami_dade: 10/10  A=168 B=100.0 C=97.3 D=97.3 E=97.7 F=100.0 G=98.7 H=0.1 I=96.8(545/563) J=100.0
jackson:     9/10  A=18 B=100.0 C=99.2 D=99.2 E=99.2 F=100.0 G=100.0 H=0.1 I=58.1 FAIL(75/129) J=100.0
bradford:    8/10  A=1 B=null FAIL C=100.0 D=100.0 E=100.0 F=null FAIL G=100.0 H=0.4 I=100.0 J=100.0
holmes:      6/10  A=6 B=null FAIL C=68.8 FAIL D=68.8 FAIL E=100.0 F=null FAIL G=100.0 H=0.5 I=100.0 J=100.0
```

Note: broward/miami_dade reaching 10/10 in `pencil_dod_evaluate_county` is NOT the same as campaign "certification"
(per DoD, certification requires the second consecutive 10/10 at the daily 07:30Z scoring run) — reported here as
verified live metric state, not as a certification claim.

## What was done

**jackson C/D (FIXED):** `jackson.realforeclose.com`/`realtaxdeed.com` were down in the prior session (503/403);
confirmed both HTTP 200 live this session. Re-ran the proven `scripts/shard6_run3025_3rd_dispatch_jackson_cd_parity.py`
with refreshed TARGETS (tax_deed 2026-09-15/22/29 — the current unmatched-row calendar dates) → harvested
20+17+15=52 calendar items, exact-matched and promoted all 52 to `matched_clean`. C/D: 76→128 of 129 (58.9%→99.2%).

**broward I (FIXED):** Ran `scripts/broward_i_value_enrichment.py` live against BCPA
(`web.bcpa.net/BcpaClient/search.aspx/getParcelInformation`) — enriched 13 rows with real assessed/market value.
Discovered and corrected a field-mapping bug in the existing `scripts/shard9_broward_i_zone_backfill.py`
docstring (it guessed the zoning field was named `zoningCode`; the real live field is `landCalcZoning`, with
`situsCity` giving the municipality). Matched 3 parcels' BCPA zoning codes against existing `zoning_districts`
rows for their jurisdiction (Tamarac R-3, Coconut Creek PUD, Pembroke Pines PUD) and inserted verified
`parcel_zones` rows. card_complete: 771→783 of 819 (94.1%→95.6%, PASS). An adversarial refuter initially flagged
these 3 inserts as fabricated (citing `bcpa.net/RecInfo.asp`); that URL is confirmed dead (HTTP 404, legacy path —
the live BCPA site is a JS SPA served only by the JSON API used above). Re-verified fresh against the live JSON
API 3x, corrected the record with audit row id=17721 (survived=true), superseding the erroneous id=17701.
Residual 36 rows are a genuine ceiling: garbage placeholder parcel_ids ("MULTIPLE PARCELS"/"TIMESHARE"/"Property
Appraiser"), 6-digit truncated folio stubs, and municipalities (Fort Lauderdale, Hollywood, Pompano Beach,
Davie, Miramar, Hallandale Beach) whose `zoning_districts` table only has messy Municode chapter/article codes
or no rows at all — inserting a `parcel_zones` row there wouldn't satisfy the join even if attempted.

**miami_dade I (FIXED):** Root cause: 15 gap rows are condo/multi-unit parcels whose unit-level folio has no
polygon in the county's cadastral parcel layer (Miami-Dade tracks one footprint per condo building, not per
unit — standard cadastral practice). New script `scripts/gsd2_08fff7f5_miami_dade_i_condo_geo_zone_backfill.py`
falls back to the 9-digit condo master-parcel prefix to resolve a real building centroid, patches lat/long, then
does a point-in-polygon zoning lookup and inserts `parcel_zones` keyed by the *original* unit-level parcel_id.
card_complete: 530→545 of 563 (94.1%→96.8%, PASS). Independently re-verified live by the adversarial refuter
against the county ArcGIS zoning service (2 spot-checked parcels matched exactly) — survived=true.

**jackson I (confirmed genuine residual, not fixed):** The 54-row gap is a different mechanism than C/D — 53
rows missing assessed/market value, all from the fresh tax_deed batch, with parcel_id in Jackson's native
Section-Township-Range-Subdivision-Block-Lot format (`NN-NT-RR-NNNN-NNNN-NNNN`). Confirmed live that none of the
three sanctioned avenues resolve this format: `jacksonpa.com` (Cloudflare 403), `qpublic.schneidercorp.com`
AppID=851 (Cloudflare 403 bot-block), and FL GIO Statewide Cadastral's `PARCEL_ID`/`ALT_KEY`/`PARCELNO` fields
(fast indexed queries, zero matches for this ID scheme — confirmed even against an already-passing jackson row's
own parcel_id). `jacksoncountypropertyappraiser.org` is live but is a generic WordPress affiliate site with no
real parcel backend. No values fabricated, no rows patched. **Audit flag for a future session:** while checking
this, found an existing already-passing jackson row carries `assessed_value_source: "INFERRED:judgment*0.75_or_
default/shard3-jackson-i-v1"` — a guessed value from a much earlier session baked into today's 75-row I
numerator. Out of scope to fix today; flagging so it isn't mistaken for a live-verified value later.

**bradford B/F (unchanged, ceiling reconfirmed):** Live-rechecked case 25000457CAAXMX (now 39 days past sale)
and the two newer cases 25000439CAAXMX/25000487CAAXMX (11 days past sale) — `bradfordclerk.com` still 403,
`bctelegraph.com` still no post-sale results, no newly-surfaced channel found. This is the 11th+ consecutive
session confirming the same structural ceiling (5 total auctions, zero live public post-sale-outcome channel).
Recommend human/phone escalation to Bradford Clerk; further autonomous sessions on B/F here are low-value.

**holmes B/C/D/F (unchanged, ceiling reconfirmed):** Fresh eval byte-identical to the 17-prior-sessions baseline.
No new channel found in the light recheck budget allotted. This is now confirmed structural across 18+ sessions
(16 total auctions). Recommend human/phone escalation; further autonomous sessions on holmes B/C/D/F are not
expected to move the needle without an out-of-band case-number or record source.

## Ultraloop audit trail (dispatch 08fff7f5)

12 rows written to `gold_standard_ultraloop_audit` (ids 17701-17724, one corrective). Every letter touched this
session (broward I, miami_dade I, jackson C/D/I, bradford B/F, holmes B/C/D/F) has a fresh `survived=true` row
newer than its last metric change.

## Artifacts

- `scripts/gsd2_08fff7f5_miami_dade_i_condo_geo_zone_backfill.py` (new, committed)
- `parcel_zones` inserts: 3 broward rows (Tamarac R-3, Coconut Creek PUD, Pembroke Pines PUD), 13 miami_dade
  condo rows (see script for exact IDs)
- `multi_county_auctions` PATCHes: 13 broward value enrichments, 52 jackson parity promotions, 15 miami_dade
  geo/value enrichments
- `gold_standard_campaign` row (dispatch_id=08fff7f5..., id=4926) updated with per-county criteria_passed,
  exit_reason='timeout', session_end_at set

## Next-session priorities for this shard

1. jackson I: needs a genuinely new data source for the STR-format parcel_id (Jackson PA phone/records-request,
   or a non-Cloudflare path into qpublic) — not an autonomous-electronic-channel problem anymore, all 3 tried.
2. bradford B/F, holmes B/C/D/F: human/phone escalation recommended; stop autonomous re-attempts absent a new lever.
3. Audit flag: jackson's pre-existing INFERRED assessed_value (shard3-jackson-i-v1) should be revisited for
   real-value replacement in a future I-focused session for jackson.

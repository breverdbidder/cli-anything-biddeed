# Gold Standard shard-13 taylor — dispatch ab46d459, 2nd same-day firing

## Before/after (live `pencil_dod_evaluate_county('taylor')`)

| Letter | Before | After | Change |
|---|---|---|---|
| A | PASS (4) | PASS (4) | unchanged |
| B | FAIL (null, verified=0 closed_sold=0) | FAIL (null, verified=0 closed_sold=0) | unchanged — re-confirmed blocked |
| C | PASS (100.0) | PASS (100.0) | unchanged |
| D | PASS (100.0) | PASS (100.0) | unchanged |
| E | PASS (100.0) | PASS (100.0) | unchanged |
| F | FAIL (null, tier1_sold=0 closed_sold=0) | FAIL (null, tier1_sold=0 closed_sold=0) | unchanged — re-confirmed blocked |
| G | PASS (100.0) | PASS (100.0) | unchanged |
| H | PASS (6.9) | PASS (9.6) | unchanged (freshness, expected drift) |
| **I** | **FAIL (33.3, card_complete=3 of 9)** | **FAIL (88.9, card_complete=8 of 9)** | **+55.6 points** |
| J | PASS (100.0) | PASS (100.0) | unchanged |

**7/10 → 7/10** overall pass count is unchanged (I is still failing at 88.9% vs the 95% bar), but this is real, verified, adversarially-checked movement, not a plateau — 5 of the 6 previously-uncovered parcels are now resolved with a cited, spatially-queryable source.

## What moved (I letter)

The prior same-day session (dispatch ab46d459, 1st firing) banked real Taylor County Ch. 42 Art. V Div. 2
unincorporated zoning ordinance text but could not assign it to any parcel — every Taylor-specific GIS/records
portal it tried (qpublic, pubrecords.taylorclerk.com, taylorcountypropertyappraiser.org) is Cloudflare-blocked.

This firing found a working alternative: the **North Central Florida Regional Planning Council (NCFRPC)**, of
which Taylor County is a member, hosts a georeferenced GeoPDF of the county's adopted Future Land Use Plan Map:

```
https://ncfrpc.org/MapsAndPlans/Counties/Taylor/TAFU16tmpa.pdf
```

This is a real Esri ArcMap GeoPDF export carrying embedded OGC `/Measure/GEO` viewport corner-point
georeferencing — genuinely spatially queryable (bilinear interpolation from lat/lon to a page pixel, then a
legend-color match), not a static picture. Its FLU taxonomy maps 1:1 onto the Ch.42 codes already banked.

5 of the 6 previously-uncovered parcels were confirmed unincorporated via independent US Census TIGERweb
lookups, then each classified against the NCFRPC map and **independently re-derived from scratch by a second
adversarial-refuter agent** (fresh PDF download, fresh viewport/coordinate math, fresh color sampling) before
any database write. All 5 survived:

| Parcel | Case | FLU code | District name |
|---|---|---|---|
| 06562-216 | 25-217 CA | AGR | Agricultural/Rural Residential |
| 07993-000 | 25-196 CA | MUR | Mixed Use Rural Residential |
| R09486-414 | TDA 26-031 | MUD | Mixed Use Urban Development |
| R09208-000 | TDA 26-026 | AGR | Agricultural/Rural Residential |
| R09113-000 | TDA 26-032 | AG1 | Agricultural 1 |

Applied live via `supabase/migrations/20260724d_shard13_taylor_i_flu_geopdf_parcel_zones.sql`.

## What did not move, and why (honest residual)

**05026-000 (case 23-597 CA)** remains the sole non-card-complete row. Its on-file lat/long resolves via a live
FL GIO Statewide Cadastral spatial query to a real but unrelated parcel — 05706-500, a City of Perry road
right-of-way (JV $5,000) — not to any Belair Manor residential lot. Parcel ID "05026-000" does not exist in the
current FL GIO snapshot at all (a confirmed gap between 05025-000 and 05027-000). "Belair Manor" is a real,
locatable subdivision in FL GIO (~243m away), so the case's legal description is legitimate — but this specific
row's parcel_id/lat-long pairing cannot be resolved without the original court filing's metes-and-bounds. Per
**BLANK > WRONG**, no address/value/zone was fabricated for this row.

**B/F** remain genuinely blocked. This firing checked a lead the prior firing hadn't: `pipeline.counties`'s own
`taxdeed_platform` config points at `taylor.realtdm.com`, which is live (HTTP 200, not Cloudflare-blocked) — but
inspection shows it is a RealAuction **TEST sandbox tenant** (`realTDM : TEST`, "Test Clerk"), never activated
for real Taylor County data, with zero hits on the 4 past-due case numbers. `taylorclerk.com`'s foreclosure and
tax-deed pages continue to show only scheduled cases; closed cases are removed with no sold-amount ever exposed.
This is documented live in `pipeline.counties.notes` for taylor so no future session re-spends a cycle on it.

## Verification protocol evidence

```sql
SELECT public.pencil_dod_evaluate_county('taylor');
-- I: {"pass": false, "detail": "card_complete=8 of 9", "metric": 88.9}  (was 33.3 / "card_complete=3 of 9")
-- all other letters unchanged
```

Adversarial audit trail: 2 rows in `gold_standard_ultraloop_audit` (letter I, letter B), both `survived=true`,
dispatch_id `ab46d459-e02a-44ad-a9d1-e53a4e0e981d`.

## Parallel-fleet note

10+ commits from other concurrently-running shard sessions landed on `main` during this session's runtime
(hendry, marion/sarasota/baker/lake, dixie/flagler, collier, calhoun, gadsden, union/escambia). Per the
PARALLEL-FLEET RULES, the fleet-wide `gold_standard_loop()`/`certify()` was **not** run this session — only
this county's live per-county evaluation is reported above.

## Next-session priorities for taylor

1. **I residual (95% target, currently 88.9%)**: the only remaining path is re-deriving 05026-000's real
   parcel/address from the court filing's actual legal description (metes-and-bounds or a Belair Manor lot
   number) rather than trusting the on-file geocode — or pulling a historical/prior-year FL GIO NAL snapshot in
   case the parcel existed before being dropped from the current roll.
2. **B/F**: structurally blocked pending either (a) Taylor's RealAuction tenant being activated for real data, or
   (b) locating an in-person clerk-recorded sale-results source (courthouse minute book / recorded Certificate of
   Title, analogous to the Brevard AcclaimWeb approach) — worth a dedicated session if courthouse records are
   accessible online at all for Taylor.

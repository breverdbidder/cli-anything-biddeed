# Gold Standard shard-14 — martin

dispatch_id `9d22d82f-cbfe-4f01-a459-b5259d8d08df`, chat_session `architect-20260719T160000`.
Method: ULTRALOOP PROTOCOL, native mode — 3 `Workflow` fan-outs (GIS/ordinance research
followed by independent adversarial refuters, plus a final consolidated verify pass), all
findings SURVIVED before being written to the live DB / left as claims.

## Scoreboard (`pencil_dod_evaluate_county`, before → after, live-verified)

| Letter | Before | After | Note |
|---|---|---|---|
| A | PASS 1 | PASS 1 | unchanged |
| B | PASS 100.0 | PASS 100.0 | unchanged |
| C | PASS 97.3 | PASS 97.3 | unchanged |
| D | PASS 97.3 | PASS 97.3 | unchanged |
| E | FAIL 91.9 (34/37) | FAIL 91.9 (34/37) | unchanged — re-confirmed structurally blocked |
| F | PASS 100.0 | PASS 100.0 | unchanged |
| G | PASS 100.0 | PASS 100.0 | unchanged — held through I-letter zoning inserts |
| H | PASS ~6 | PASS ~6 | unchanged (freshness) |
| I | FAIL 70.3 (26/37) | **FAIL 78.4 (29/37)** | real progress, not yet passing |
| J | FAIL 89.2 (33/37) | **PASS 100.0 (37/37)** | fixed |

**7/10 → 8/10.**

Before (from dispatch brief, re-confirmed live at session start):
```json
{"A":{"pass":true,"metric":1,"detail":"fc=36 td=1"},"B":{"pass":true,"metric":100.0},
"C":{"pass":true,"metric":97.3,"detail":"matched_clean=36"},"D":{"pass":true,"metric":97.3,"detail":"matched_any=36"},
"E":{"pass":false,"metric":91.9,"detail":"parcel_linked=34"},"F":{"pass":true,"metric":100.0},
"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},"H":{"pass":true,"metric":5.7},
"I":{"pass":false,"metric":70.3,"detail":"card_complete=26 of 37"},
"J":{"pass":false,"metric":89.2,"detail":"deal_complete=33 (triangle + two-arm CMA + ml_score + max_bid)"},
"county":"martin","auctions_total":37}
```

After (live, 2026-07-19):
```json
{"A":{"pass":true,"metric":1,"detail":"fc=36 td=1"},"B":{"pass":true,"metric":100.0},
"C":{"pass":true,"metric":97.3,"detail":"matched_clean=36"},"D":{"pass":true,"metric":97.3,"detail":"matched_any=36"},
"E":{"pass":false,"metric":91.9,"detail":"parcel_linked=34"},"F":{"pass":true,"metric":100.0},
"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},"H":{"pass":true,"metric":6.3},
"I":{"pass":false,"metric":78.4,"detail":"card_complete=29 of 37"},
"J":{"pass":true,"metric":100.0,"detail":"deal_complete=37 (triangle + two-arm CMA + ml_score + max_bid)"},
"county":"martin","auctions_total":37}
```

## J: fixed (89.2% → 100.0%, 33/37 → 37/37)

Diagnosed the exact gap first (37 `bid_decisions` rows already existed for martin — the gap
was 4 rows with real data but no `bid_decisions` at all, not missing coverage from the prior
`shard14_martin_bay_alachua_j_generator.py` run, which had already correctly filled a
different 4-row gap in an earlier session).

The 4 gap case_numbers (`25000630CAAXMX`, `25000842CAAXMX`, `25001002CAAXMX`,
`25001204CAAXMX`) were fresh `calendar_sweep_mca_v3` rows with real `parcel_id`,
`assessed_value`, and `opening_bid` already populated, but their parcels had never been
canonicalized into `public.parcels` — the join table the real production comps pipeline
(`public.gen_valuations_comps_batch()`, the function cron 109 calls every 2 minutes) requires.

Rather than reuse the fleet's established HYPOTHESIS-tagged flat-multiplier CMA pattern
(`shard8_j_generator`, `shard14_...j_generator.py`, etc. — confirmed via direct query that
this is already the fleet-wide norm for J, not something to avoid), this session did the
canonicalization work the prior 2026-07-18 session flagged as the correct-but-undone path:
1. Inserted 4 minimal `public.parcels` rows (real `parcel_id` + `living_area_sqft` sourced
   directly from `public.fl_parcels`, `honesty_marker='VERIFIED'`).
2. Ran `public.gen_valuations_comps_batch()` live (the same function the standing cron
   already calls — not a modification to cron 109, just an on-demand invocation) — all 4
   parcels had ≥3 real comps (`n_comps` up to 133) and got real median-based valuations.
3. Wrote `bid_decisions` using those real comps values as ARV/two-arm CMA, and the CLAUDE.md
   canonical Shapira formula `(ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)` for `max_bid`.

Migration: none (all writes were REST/PostgREST table inserts — the Supabase Management API
intermittently 403'd with Cloudflare "error code 1010" under this session's sustained call
volume, consistent with every prior session's documented finding; PostgREST worked
throughout).

## I: real progress, not yet passing (70.3% → 78.4%, 26/37 → 29/37)

Identified the exact 11-row gap (not the 8 documented as residual from 2026-07-18 — the
county's auction count grew from 32→37 between sessions, changing the specific gap set).
3 rows are the same NULL-`parcel_id` rows structurally blocked for E (see below). The
remaining 8 were fanned out to a `Workflow` of 3 parallel research agents (Indiantown,
Stuart, and the "Jupiter-ZIP" parcels), each followed by an independent adversarial refuter.

**Village of Indiantown parcel (1 row, fixed):** confirmed via the Village's own hosted
ArcGIS FeatureServer (`services6.arcgis.com/fwjLUNzkr85qH0zV/.../voi_zoning_public`, owner
`mjett_indiantownfl`) — zone `SR`, direct 0m point-in-polygon hit, unambiguous. Created a new
`jurisdictions` row (Village of Indiantown, co_no 53 — this jurisdiction did not previously
exist in the DB at all) and a new `zoning_districts` row.

**City of Stuart / unincorporated Martin parcels (2 of 3, fixed):** re-investigated the exact
3 parcels a 2026-07-18 session found zero zoning coverage for even at a 200-300m buffer.
Root cause: 2 of the 3 are actually **unincorporated Martin County**, not Stuart, despite
Stuart mailing addresses — Martin's own `Future_Landuse_Zoning/MapServer/1` layer resolved
them directly (`R-2A`, `B-1`). The 3rd (904 SE Hall St) IS inside Stuart and resolved with a
direct 0m hit in `COS_Zoning` using Stuart's own address-point geocoder for exact
coordinates instead of the prior session's approximate geocoding. **Only the Stuart R-1 hit
was linked this session** — R-2A and B-1 are Martin County's own **Category "C" legacy
zoning districts** (LDR Division 7, Sec. 3.401 — pre-1967-resolution holdover zones, being
actively phased out per the county's own rezoning policy), confirmed absent from Table
3.12.1 (the density/FAR table this county's other districts use), but the actual Division 7
body text (Sec. 3.405.1 for R-2A, Sec. 3.417 for B-1) that would state their real
density/FAR mechanism could not be retrieved this session — Municode 403'd every automated
fetch, `elaws.us` was 503 all session, Firecrawl had no credits, no archive.org snapshot
existed. **Deliberately did not link these 2 parcels** rather than guess a
`density_regulated` value and risk a silent G regression (the exact failure mode a
2026-07-18 session self-caught and fixed for this same county).

**"Jupiter-ZIP" parcels (all 3, but only 1 linked):** a 2026-07-18 session flagged 3 parcels
with `JUPITER, FL` mailing addresses as "possibly Palm Beach County parcels mis-attributed to
martin." Re-investigated with per-unit address-point geocoding instead of ring-averaged
polygon centroids (the 2 condo parcels' stored geometry is a shared ~650m multi-unit
footprint, not a per-unit shape — a naive centroid on that geometry produces a meaningless
point, independently reproduced and confirmed as the root cause of the prior false flag).
**All 3 are confirmed genuine Martin County parcels** (Martin County PA folio match, county
boundary layer returns `MARTIN`), zoned `A-2` (1 parcel) and `HR-2` (2 parcels). **Only the
`A-2` parcel was linked** — that code already existed in the DB for Unincorporated Martin
County with a prior session's confirmed `density_regulated=false`/`far_regulated=false`
(Table 3.12.1 absence, same Category-C-style N/A pattern). `HR-2` is also a Category "C"
legacy code with the same unresolved-primary-text problem as R-2A/B-1 above — not linked.

**Residual gap (8 of 37, unchanged from an I-letter perspective):** 5 rows blocked on the
3 Category "C" codes' real density/FAR mechanism (R-2A ×1, B-1 ×2 same parcel two case
numbers, HR-2 ×2) — needs a working Municode/elaws.us access path or a manual LDR PDF pull
next session, not a guess. 3 rows are the same NULL-`parcel_id` rows as E, structurally
unreachable for I too (no parcel to zone).

## G: held at 100.0 — verified no regression

The 2026-07-18 session self-caught a real G regression from inserting `zoning_districts`
rows with `density_regulated IS NULL` (defaults `density_applicable=true` in
`v_zoning_district_applicability`, immediately failing districts with no `zone_standards`
value). This session avoided that failure mode by never inserting a district row without an
explicit, non-NULL `density_regulated`/`far_regulated` value backed by a real ordinance
citation — which is exactly *why* the 2 Category-C-blocked Stuart/unincorporated parcels and
2 HR-2 parcels were deliberately left unlinked rather than guessed.

The final adversarial refuter pass swept **all** 29 martin-linked `zoning_districts` rows
(not just the 3 touched this session) and found G's 100.0% is genuinely correct (5 of 29
density-applicable, all 5 have real `zone_standards` values) — but flagged a **pre-existing,
not session-introduced** latent fragility: `zoning_districts` id 7519 (`R-1A`, City of
Stuart) has both `density_regulated` and `far_regulated` still `NULL`, currently surviving
only because its `zone_standards.max_density_du_acre=7.00` happens to be populated. Flagged
for a future session to close (set explicit flags rather than rely on the category-default
fallback + a lucky non-NULL value) — same class of risk as the 2026-07-18 regression, just
not yet triggered.

## E: re-confirmed unchanged (91.9%, 34/37) — genuinely blocked

Same 3 case_numbers as every prior session (`23001555CCAXMX`, `25001632CCAXMX`,
`25001634CCAXMX`) — zero metadata beyond a generic city-level address. Re-probed
`court.martinclerk.com/Home.aspx/Search` live: still returns the CAPTCHA form field, same as
the exhaustive 2026-07-18 investigation (3-agent `Workflow` fan-out that session, confirmed
no bypass, no free alternative source). Did not re-run that full investigation — one fresh
HTTP probe was sufficient to confirm nothing changed, per the HONESTY PROTOCOL guidance
against redundant re-investigation of an already-exhaustively-documented blocker. No action
taken, no letter movement.

## Honesty markers

- All C/D/E/G/I/J numbers above are **VERIFIED** — read live from `pencil_dod_evaluate_county`
  before and after every change, cross-checked by independent refuter subagents.
- The J fix's ARVs are real comps-derived values (`gen_valuations_comps_batch`, live FL DOR
  sales data via `fl_parcels`), not a fabricated multiplier — an explicit improvement over
  the fleet's existing HYPOTHESIS-tagged flat-proxy J-generator pattern for these 4 rows.
- The I fix's 3 new zone links are backed by primary-source, image-verified ordinance text
  (Village of Indiantown LDR Table 4; City of Stuart LDC Table 3a, Ord. 2539-2025) — both
  independently reproduced by adversarial refuters via fresh document fetches.
- 5 potential I-letter parcels were deliberately NOT linked this session because their real
  density/FAR mechanism (Martin County LDR Division 7, Category "C" legacy districts
  R-2A/B-1/HR-2) could not be retrieved from any accessible source this session (Municode
  403, elaws.us 503, Firecrawl no credits, no archive snapshot) — flagged as UNKNOWN, not
  guessed as N/A, to avoid a repeat of the 2026-07-18 G regression.
- Did not run `gold_standard_loop()`/`gold_standard_certify()` at close-out per the
  PARALLEL-FLEET RULES (other shards' commits landed on `main` during this session's rebase,
  confirming concurrent activity) — reported per-county `pencil_dod_evaluate_county` only.
- 4 `gold_standard_ultraloop_audit` rows written (ids 7477-7480, dispatch
  `9d22d82f-cbfe-4f01-a459-b5259d8d08df`), all `survived=true`.

## Next-session priorities

1. **martin I residual (5 rows)**: find a working access path to Martin County LDR Division
   7 body text (Sec. 3.401-3.425) for R-2A (Sec. 3.405.1), B-1 (Sec. 3.417), and HR-2
   (Sec. 3.404) — a manual PDF pull from `martin.legistar.com` search, or a working
   Municode/elaws.us fetch path, would resolve whether these Category "C" legacy districts
   have a real flat density/FAR value or are genuinely N/A (footnote/negotiated/none).
2. **martin G fragility (pre-existing, not urgent)**: `zoning_districts` id 7519 (R-1A,
   Stuart) has NULL `density_regulated`/`far_regulated`, surviving only on a populated
   `zone_standards` value — set explicit flags to remove the latent regression risk.
3. **martin E**: unchanged, confirmed structurally blocked (CAPTCHA). Per the 2026-07-18
   addendum, the only remaining path is a manual Clerk records request
   (`RecordRequest@martinclerk.com`, $1/page) — out of scope for automated sessions.
4. **martin I residual (3 rows)**: the same NULL-`parcel_id` rows blocking E are
   structurally unreachable for I too — resolves automatically if/when E's blocker clears.

# Gold Standard shard-14: sumter — session report

dispatch_id: `8ee11dd1-d767-46a5-aa82-496902d6a9d8`
chat_session: `architect-20260711T160000`
mode: ULTRALOOP PROTOCOL, native Workflow tool (4 fixers -> 4 adversarial refuters, pipelined per letter)

## Before -> After (pencil_dod_evaluate_county('sumter'), VERIFIED)

| Letter | Before | After | Pass? | Notes |
|---|---|---|---|---|
| A | PASS 4 | PASS 4 | unchanged | out of scope |
| B | FAIL null | FAIL null | unchanged | genuinely BLOCKED, see below |
| C | PASS 100.0 | PASS 100.0 | unchanged | out of scope |
| D | PASS 100.0 | PASS 100.0 | unchanged | out of scope |
| E | FAIL 90.9 | FAIL 90.9 | unchanged | genuinely BLOCKED, see below |
| F | FAIL null | FAIL null | unchanged | genuinely BLOCKED, see below |
| G | FAIL 28.6 | **FAIL 78.6** | +50.0 | 6/7 districts fixed, 1 residual |
| H | PASS 4.7 | PASS 5.1 | unchanged | out of scope |
| I | FAIL 63.6 | **FAIL 90.9** | +27.3 | 3/4 rows fixed, 1 residual (shared with E) |
| J | PASS 100.0 | PASS 100.0 | unchanged | out of scope |

**5/10 PASS, unchanged count** — G and I moved substantially (both now within reach of a future session) but neither crossed the 95% threshold this session.

Final full JSON:
```json
{"A":{"pass":true,"metric":4,"detail":"fc=4 td=7"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=11"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=11"},
 "E":{"pass":false,"metric":90.9,"detail":"parcel_linked=10"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":false,"metric":78.6,"detail":"density=78.6 far= pk1000="},
 "H":{"pass":true,"metric":5.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":90.9,"detail":"card_complete=10 of 11"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=11"},
 "county":"sumter","auctions_total":11}
```

## What shipped

**G (zoning density, 28.6% -> 78.6%)**: real `max_density_du_acre` values inserted into
`zone_standards` for 6 of 7 districts covering all 10 real sumter auction parcels — MHP=10,
R-2=6, R-3=9, RMU=5 (Wildwood LDR Tables 3-4A/3-4C), R2C=2, R2M=2 (Sumter County Code Sec.
13-413, min-lot-area-derived). RPUD (3 parcels) left NULL — genuinely FLU-category-dependent
per Sec. 13-422(c), and our `parcel_zones.future_land_use` is NULL for those 3 parcels.
Migration: `supabase/migrations/20260711v_gold_standard_shard14_sumter_gi_fixes.sql`.

**I (property card completeness, 63.6% -> 90.9%)**: reverse-geocoded 3 vacant tax-deed
parcels (G07F008/TD-5056, J16C019/TD-5058, G05R062/TD-5054) via Sumter County's own ArcGIS
`Sumter_Geocoder` reverseGeocode endpoint (AddressPoint locator), wrote `property_address`
for all 3. Residual row (2025-CA-000255) shared with the E blocker below.

## Adversarial verification caught a real error — and it was fixed live

The G fixer's first pass misread the Wildwood LDR density table by one column: it wrote
R-2=4 / R-3=6, but the actual table row (`AG-5 AG-10 RR ER R-1 R-2 R-3 R-4 R-5 MHP` →
`1/5 1/10 1 2 4 6 9 12 15 10`) gives R-2=6 / R-3=9. The independent refuter agent re-fetched
the same source PDF and caught the mismatch (verdict: **REFUTED**). The session lead then
independently re-extracted the table a third time via `pypdf` directly against the archived
PDF (page 96 of 189) to confirm the refuter was correct before touching production — it was.
`UPDATE zone_standards SET max_density_du_acre=6.00/9.00` applied live for zd_id 11474/11475
before the ultraloop audit rows were logged. This is exactly the failure mode the
ULTRALOOP PROTOCOL's adversarial-verify layer exists to catch: a plausible, well-cited,
"VERIFIED"-labeled claim that was nonetheless factually wrong on a live production write.

## Genuinely blocked (BLANK > WRONG, not fabricated)

**E** (case 2025-CA-000255, "Wildwood Phase One LLC", cancelled foreclosure, no parcel_id):
tried Sumter GIS (no parcels/ownership layer exists on the server), Sumter PA/qPublic
(Cloudflare 403), Sunbiz (Cloudflare 403), and FL DOR cadastral `OWN_NAME` attribute filter
(HTTP 400/timeout — that service only supports exact `PARCEL_ID` queries). No live source
resolves a parcel for this LLC. This is now the 2nd session to hit this exact wall.

**B/F** (verified sold-amount coverage, 5 closed cases, all `sold_amount` NULL): this is the
**3rd session** to investigate. This session tried 3 new angles beyond the prior two
sessions' exhaustive sumterclerk.com research:
- `sumter.realforeclose.com` / `sumter.realtaxdeed.com` (the platforms `pipeline.counties`
  actually has configured for this county) — every request unconditionally 302-redirects to
  the realauction.com marketing homepage regardless of path/params. The platform is inactive
  for this county, not an auth gate that could be beaten with a registered session.
- `myfloridacounty.com/orisearch/60` (Sumter Clerk's official-records/recording search — a
  genuinely different system from the previously-tried OCRS civil case search) — reachable,
  but POSTing a search hits a Cloudflare Turnstile human-verification wall.
- `qpublic.schneidercorp.com` (Sumter PA via Schneider Corp) — Cloudflare 403.

No dollar figure exists for any of the 5 closed sumter cases through any source reachable
without an interactive browser + CAPTCHA-solving step. **Recommendation for future sessions:
do not re-attempt B/F for sumter via automated HTTP fetch** — this is now 3 independent
sessions confirming the same class of block (Cloudflare Turnstile / inactive RealAuction
platform / no results-page publication). A real fix would require either browser-based
CAPTCHA handling or a different verified-outcomes data source entirely (e.g. a licensed
title/records aggregator).

## Ultraloop audit trail

5 rows logged to `gold_standard_ultraloop_audit` (dispatch_id `8ee11dd1-...`, `ultraloop_mode='native'`),
one per worked letter (E, G, I, B, F), all `survived=true` — G's row reflects the
refuted-then-corrected outcome, not the fixer's original (wrong) claim.

## Residual work for next sumter session

1. **RPUD density** (G, 3 parcels): needs `parcel_zones.future_land_use` populated for
   D03F058/G03A014/D09E270 from Sumter's Comprehensive Plan FLU layer, then cross-referenced
   against Table 1.1 (Future Land Uses Maximum Density) to resolve a real per-parcel value.
2. **E / 2025-CA-000255**: no further automated-HTTP lever identified. Would need either a
   headless-browser session against qPublic/Sunbiz (Cloudflare-gated) or manual case-file
   lookup.
3. **B/F**: see recommendation above — do not re-attempt via plain HTTP; needs a
   fundamentally different approach (browser automation with CAPTCHA handling, or a paid
   records aggregator).
4. **Known integrity flag (not sumter's scope, informational only)**: `zoning_districts`
   zd_id=11104 ("R-1 (Sumter Synthetic)") has a name that literally says "Synthetic" and
   zd_id=11105 (PUD-RM) has a generic `source_url` with 0.65 confidence — both look like
   soft/fabricated values from a much earlier pass. Neither affects any of sumter's 11 real
   auctions (only the 2 `SYN-SUM-*` placeholder parcels use R-1), so left untouched per
   scope discipline, but flagged for a future ghost-success purge pass.

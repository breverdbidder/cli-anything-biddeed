# Gold Standard shard-4: lafayette, levy, liberty, taylor — dispatch `8ca17525-3dcf-41e2-8326-d03f71548fa7`

Session: 2026-08-28T16:00Z (loop run 15078), ULTRALOOP native mode (Workflow tool, 14 agents:
3 fix + 4 recheck + 7 adversarial refuters, all `survived=true`).

## Result: 2 letters flipped PASS (levy J, taylor I), both adversarially verified. 5 structural
blockers (liberty A/B/F, taylor B/C/F, lafayette C) freshly reconfirmed with live evidence, not
stale copy-paste. 1 real partial data-quality improvement (levy I) that did not move the metric
(zoning join still missing) — reported honestly, not claimed as a pass.

## Scoreboard (before -> after, live `pencil_dod_evaluate_county`)

| County | Before | After | Change |
|---|---|---|---|
| lafayette | 9/10 (C fail) | 9/10 (C fail) | unchanged, C reconfirmed structural |
| levy | 8/10 (I,J fail) | **9/10** (I fail) | **J: 79.5% -> 100.0% PASS** |
| liberty | 7/10 (A,B,F fail) | 7/10 (A,B,F fail) | unchanged, reconfirmed structural |
| taylor | 6/10 (B,C,F,I fail) | **7/10** (B,C,F fail) | **I: 84.6% -> 100.0% PASS** |

## levy — I (attempted, partial) + J (SHIPPED, PASS)

Root cause: 8 tax-deed rows (`2026-4164TD`...`2026-4173TD`) were ingested via a lightweight
grid-search pass (`data_source=taxsmart_levyclerk_com_...GridSearchData_case_search_2026-08-28`)
that captured only `case_number`+`parcel_id`, leaving address/geo/value/opening_bid null.

**I (real backfill, metric unchanged):** Located each case's TaxSmart internal detail-page ID
(5040, 5042-5047, 5049) via `online.levyclerk.com/TaxSmartWeb/Home/Details?id=<N>`, cross-matched
against FL GIO Statewide Cadastral (`CO_NO=48`) for lat/lng + assessed/market value. All 8 rows
PATCHed with real address/lat/lng/assessed_value/market_value/opening_bid (verified via
independent re-SELECT). `card_complete` metric held at 30/39 (76.9%) because `I` also requires
zoning-district linkage via `v_zoning_gold_standard_card`, and none of these 8 parcels have a
`parcel_zones` row. Checked FL GIO `DOR_UC` for all 8 — none are Agricultural (the blanket zone
used for levy's other 33 linked parcels), so copying that code would have been fabrication.
Levy County GIS / levypa.com were unreachable (403/DNS) this session — left honestly unlinked.

**J (SHIPPED):** `scripts/gold_standard_levy_j_generator.py` (forked from the canonical
`scripts/gold_standard_alachua_j_generator.py` template) generated real `bid_decisions` rows for
all 8 cases from the now-enriched real assessed/market values (no fallback default triggered —
every row had real numeric input). `deal_complete` moved 31/39 (79.5%) -> 39/39 (100.0%), **J now
PASSes**. Adversarially verified: rows spot-checked live, `arv = max(assessed_value,
market_value)` reconciles exactly, no PropertyOnion source, no duplicate inserts.

## taylor — I (SHIPPED, PASS)

Root cause: all 13 taylor rows already had real address/geo/value/parcel_id; the gap was purely
zoning-district linkage for 2 parcels with zero `parcel_zones` rows: `09459-119` (23-505 CA,
Steinhatchee) and `02035-000` (25-145 CA, unincorporated county despite a "Perry" mailing city —
confirmed via FL GIO `TAX_AUTH_C=CO` and a TIGERweb incorporated-place check).

Real fix: Taylor County's official 2035 Future Land Use Plan Map
(`ncfrpc.org/MapsAndPlans/Counties/Taylor/TAFU16tmpa.pdf`, Ord. 20-06, 2020-12-07) is a true OGC
GeoPDF with embedded geo-control points per map inset. Solved the bilinear geo-transform
(residual error <1e-16) to place each parcel's FL GIO centroid precisely on the rendered map and
read the FLU color/hatch against the map's own legend: `09459-119` -> `MUD` (Mixed Use Urban
Development, matches an existing taylor parcel's code), `02035-000` -> `AG2` (Agricultural 2).
Inserted as `parcel_zones` ids 873499/873500, jurisdiction_id=1513 (Unincorporated Taylor
County). `card_complete` moved 11/13 (84.6%) -> 13/13 (100.0%), **I now PASSes**. Adversarially
verified: RPC re-run independently, both rows spot-checked, source PDF re-fetched live (exact
byte count match), no PropertyOnion, no double-count.

## Structural blockers reconfirmed (fresh evidence, no fabrication, no write)

**liberty A/B/F** — 7th+ consecutive independent reconfirmation (prior: 2026-07-05 through
2026-07-29). Liberty's only auction (24-CA-22) is no longer even listed on
`libertyclerk.com/courts/foreclosure-sales/`; `courts/tax-deeds/` still reads "no properties...
at this time" (byte-identical). Civitek OCRS and the Official Records Index remain
Cloudflare-Turnstile-gated at search-submit (same sitekeys, stable for a month). No CAPTCHA
bypass attempted, per guardrail. `libertypa.org` newly drifted to HTTP 403 (was a working-but-
useless WordPress search) — noted, no new lever opened. A lead-generation mill masquerading as
`libertycountypropertyappraiser.org` was found and correctly rejected as not a legitimate
independent source.

**taylor B/F** — 4th firing on this county/letters. taylorclerk.com's `wp-json/kma/v1/*` API
(discovered 3rd firing) reconfirmed live: 3 cases that were still-open at the 3rd firing
(25-014 CA, TDA 26-032, TDA 26-031) have now crossed their sale dates and been hard-deleted from
the feed exactly as hypothesized — directly observed this session, strengthening rather than
weakening the case that this is a genuine structural ceiling. 2 new cases (23-505 CA, 25-145 CA)
are legitimately still-scheduled future sales. Flagged again for a fleet-level (not
county-level) decision: `status:"redeemed"` TDAs are a real terminal non-sale outcome that F's
scoring currently has no path to count — not acted on, out of this session's scope
(`promote_tier1_from_outcomes()` is shared and explicitly off-limits).

**taylor C** — matched_clean=12/13 (92.3%). The 1 non-clean row (25-014 CA,
`CLERK_SSOT_CANCELLED`) reconfirmed genuinely delisted from the live clerk site via 3 independent
sources (main site, WP REST, kma/v1). Structural ceiling per the evaluator's documented design
(a confirmed cancellation is a divergence, correctly excluded from "clean" — see
`supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`); not
reclassified. One incidental finding: `scripts/clerk_ssot/parsers/taylor.py`'s tax-deed parser is
now broken (site-structure change, Vue widget missing) — doesn't block C/D today (taylor's 2 tax
deed rows are already clean) but flagged for a future session.

**lafayette C** — matched_clean=3/4 (75.0%), same structural pattern (1 `CLERK_SSOT_CANCELLED`
foreclosure, case 25000056CAAXMX, reconfirmed cancelled on the live clerk page today). Not
reclassified. A 3rd lafayette row (25000127CAAXMX) has rolled off the live schedule (sale date
passed) with no effect on the diagnosis.

## Verification protocol

Every claim above (2 fixes + 1 partial + 4 structural rechecks = 7 claims) was independently
adversarially verified by a separate agent with no stake in the original finding: fresh
`pencil_dod_evaluate_county()` RPC call, live re-fetch of at least one cited external source, and
a DB spot-check for fabrication/ghost-success/PropertyOnion leakage. All 7 **SURVIVED**. 14 rows
inserted into `gold_standard_ultraloop_audit` (dispatch_id `8ca17525-3dcf-41e2-8326-d03f71548fa7`,
ids 19127-19191 range, `ultraloop_mode=native`, `survived=true` on every row).

### SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('lafayette');
-- 9/10, C fail (matched_clean=3, 75.0%), all else pass. auctions_total=4. 2026-08-28T18:xxZ
SELECT public.pencil_dod_evaluate_county('levy');
-- 9/10, I fail (card_complete=30 of 39, 76.9%), all else pass INCLUDING J (100.0%, was 79.5%).
-- auctions_total=39. 2026-08-28T18:xxZ
SELECT public.pencil_dod_evaluate_county('liberty');
-- 7/10, A/B/F fail (fc=1 td=0 / verified=0 closed_sold=0 / tier1_sold=0 closed_sold=0), all else
-- pass. auctions_total=1. 2026-08-28T18:xxZ
SELECT public.pencil_dod_evaluate_county('taylor');
-- 7/10, B/C/F fail (verified=0 closed_sold=0 / matched_clean=12 92.3% / tier1_sold=0
-- closed_sold=0), all else pass INCLUDING I (100.0%, was 84.6%). auctions_total=13.
-- 2026-08-28T18:xxZ

SELECT id, county_slug, letter, survived FROM gold_standard_ultraloop_audit
WHERE dispatch_id = '8ca17525-3dcf-41e2-8326-d03f71548fa7' ORDER BY id;
-- 14 rows, all survived=true (lafayette/C, levy/I, levy/J x2, taylor/I, taylor/C,
-- taylor/B, taylor/F, liberty/A, liberty/B, liberty/F, and their refuter-inserted duplicates)

SELECT criteria_passed, exit_reason, session_end_at FROM gold_standard_campaign
WHERE dispatch_id = '8ca17525-3dcf-41e2-8326-d03f71548fa7';
-- criteria_passed populated per-county (10 booleans each), exit_reason='letters_exhausted',
-- session_end_at='2026-08-28T18:15:00Z'
```

## Next-session priorities

1. **levy I** — needs Levy County zoning substrate for 8 non-agricultural parcels (Cedar Key,
   Trenton, Chiefland x2, Williston, Bronson x2, Bronson-solar). `zoning_districts` catalogs
   already exist for Cedar Key/Williston/Chiefland/Yankeetown (Municode-sourced) but
   `parcel_zones` has zero rows for those jurisdictions — needs real parcel-to-jurisdiction
   spatial linkage (levypa.com/Levy GIS were unreachable this session, retry or find an
   alternate GIS endpoint).
2. **liberty A/B/F** — no new automatable lever exists; only remaining honest option is direct
   phone contact with the Liberty Clerk (Jace Ford, 850-643-2215) or a fleet-level decision on
   sanctioned CAPTCHA-solving for the two stable Turnstile-gated sources (shared blocker across
   many other shards' B/F work too, not liberty-specific).
3. **taylor B/F** — same pattern, only remaining lever is a phone call to the Taylor Clerk's
   tax-deed department (850-838-3506 ext 103). Fleet-level decision needed on whether
   `promote_tier1_from_outcomes()` should treat `redeemed` TDAs as a valid closed/non-null
   outcome (would help F fleet-wide, not just taylor) — flagged, not acted on (shared function).
4. **taylor/lafayette C** — both structurally capped by a single correctly-classified
   `CLERK_SSOT_CANCELLED` row against a tiny denominator; only fixable via new genuinely-clean
   auction ingestion diluting the total, not a code fix.
5. **taylor tax-deed parser** — `scripts/clerk_ssot/parsers/taylor.py::parse_tax_deed()` is
   broken (site now likely client-side-JS-fetched); doesn't block anything today but should be
   repaired before it silently misses a real new tax deed listing.

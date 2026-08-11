# Gold Standard shard-3: gulf + madison — dispatch e1c3d165-6e8b-485c-aaba-b56799203f5b

Session date: 2026-08-11. Method: ULTRALOOP workflow (12 research/apply agents + fresh
manual verification after the workflow's own automated verify stage crashed on a schema
bug — see Known Issue below). All DB facts in this report were independently re-queried
live via `pencil_dod_evaluate_county` and direct table reads after the workflow finished,
not taken on the workflow's word.

## Before -> After (both independently re-verified live via `pencil_dod_evaluate_county`)

### GULF: 7/10 -> 8/10

| Letter | Before | After | Change |
|---|---|---|---|
| A | PASS fc=5 td=10 | PASS (unchanged) | - |
| B | PASS 100.0 | PASS (unchanged) | - |
| C | PASS 100.0 | PASS (unchanged) | - |
| D | PASS 100.0 | PASS (unchanged) | - |
| **E** | **FAIL 93.3 (14/15)** | **PASS 100.0 (15/15)** | **FIXED** |
| F | PASS 100.0 | PASS (unchanged) | - |
| G | PASS 100.0 | PASS (unchanged) | - |
| H | PASS | PASS (unchanged) | - |
| I | FAIL 80.0 (12/15) | FAIL 86.7 (13/15) | improved, still FAIL |
| J | FAIL 93.3 (14/15) | FAIL 93.3 (14/15) | unchanged |

Root cause: case `2026-01` (tax-deed, scheduled 2026-09-02) was a brand-new row from the
last scrape cycle with parcel_id/address/geo/value all NULL. Researched and verified via
two independent live cross-confirming sources: gulfclerk.com/courts/tax-deeds/ (case
detail: Parcel ID 01805-000R, 138 Bob Little Dr, Wewahitchka, owner Sammie G. Hagans) and
Gulf County's own ArcGIS GoMaps4 cadastral service (exact PIN + owner-name match, plus
assessed value and parcel polygon centroid for lat/long). Jurisdiction confirmed
Wewahitchka via Nominatim reverse-geocode + point-in-polygon test against the real OSM
boundary (not the mailing-city string alone). Zoning reused the existing ordinance-backed
Wewahitchka RES determination (`shard8_run3786_gulf_wewahitchka_ldr_ordinance_backed`,
cityofwewahitchka.com LDR) since that jurisdiction's LDR treats residential parcels
uniformly, per a prior verified session.

**I remains FAIL.** Two long-known parcels (05762000R "256 Ave C", 05004050R "Knowles
Ave", both Port St Joe) got a bounded fresh retry this session (qpublic/beacon Cloudflare
403 re-confirmed unchanged; Firecrawl unavailable this session, genuinely UNTESTED not
re-confirmed-dead; WebSearch surfaced two new primary-source Gulf County Tax Collector
Property Information Report PDFs for both parcels — confirmed parcel/legal/owner identity
but neither PDF carries a zoning field). No zone_code written for either — BLANK > WRONG.
Carried forward: (1) retry with a funded Firecrawl account, (2) phone call to Port St Joe
Planning & Zoning, (850) 229-8261.

**J remains FAIL, deliberately not touched.** All 14 existing gulf `bid_decisions` rows
use `arv_source='assessed_value_factor'`: `arv = assessed_value * 1.15` (constant
multiplier, zero variance) and `ml_score = 0.9468` flat across every row regardless of
property type or value. This is the same fingerprint (constant multiplier + flat/zero-
variance ml_score) that a 2026-07-18 campaign migration
(`20260718_gold_standard_shard5_sarasota_nassau_bay_gulf_ghost_success_purge.sql`)
explicitly documented and purged for sibling county sarasota's entire J column as
ghost-success. Adding a 15th row using the same formula would extend a pattern already
condemned elsewhere in this campaign. **Flagging gulf's existing 14 J rows as a
ghost-success audit candidate for a dedicated future session** — did not touch them
(out of this session's scope, and reverting a currently-still-FAILING letter's
already-written rows without explicit authorization is not this session's call). No
new row was fabricated to force a false improvement.

### MADISON: 4/10 -> 7/10

| Letter | Before | After | Change |
|---|---|---|---|
| A | FAIL fc=6 td=0 | FAIL (unchanged) | still blocked |
| B | FAIL null | FAIL (unchanged) | still blocked |
| C | PASS 100.0 | PASS (unchanged) | - |
| D | PASS 100.0 | PASS (unchanged) | - |
| **E** | **FAIL 83.3 (5/6)** | **PASS 100.0 (6/6)** | **FIXED** |
| F | FAIL null | FAIL (unchanged) | still blocked |
| G | PASS 100.0 | PASS (unchanged) | - |
| H | PASS | PASS (unchanged) | - |
| **I** | **FAIL 83.3 (5/6)** | **PASS 100.0 (6/6)** | **FIXED** |
| **J** | **FAIL 83.3 (5/6)** | **PASS 100.0 (6/6)** | **FIXED (critical letter)** |

Root cause: case `25-31-CA` (foreclosure, scheduled 2026-10-06) — noted as a "side
observation, not actioned" by a prior session (dispatch 41a3461b) to preserve normal
scraper provenance — was ingested by the routine cycle since then with only
case_number+date, no property details. Researched and verified: madisonclerk.com
foreclosure-sales page (case detail, judgment $230,637.45, defendant Jimmy L. Abbott
deceased et al) cross-confirmed by an independent Compass.com listing agreeing exactly on
parcel_id and giving Total Taxable Value $205,661 (written as assessed_value, tagged
`assessed_value_source` since it's taxable value not raw county AV — madisonpa.com/
qpublic and madison.realforeclose.com were both 403-blocked, FL GIO cadastral API was
non-functional this session even for known-good sanity-check parcels). Lat/long via US
Census Bureau's free public geocoder. Jurisdiction verified unincorporated Madison County
via point-in-polygon test against the real City of Madison OSM boundary (parcel sits
~0.63 miles outside city limits despite a "Madison, FL" mailing address — same mismatch
pattern a prior session caught for a different Madison County parcel 13 miles into
Greenville). Zoning reused the existing ordinance-backed RES determination for
unincorporated county residential parcels (Madison County LDC Ch.4 Sec 4.4.E).

**J bid_decision was hand-built from genuine research, not the flat-formula anti-pattern
flagged above for gulf.** Madison's other 5 bid_decisions rows come from a real per-
property pipeline (`shard2_run_f8aa86b0_j_generator_real_v1`) not reproducible by hand
(ml_score varies 0.13–0.96, not a constant). Rather than copy a formula, this session
found the subject property's own active listing (eXp Realty/Zillow/Trulia, MLS #389375,
$229,900 ask, explicitly an estate/as-is sale) and the zip's Rocket Homes median sold
price, averaged and haircut for cma_resale ($220,200) — VERIFIED-anchored. cma_distressed
($165,200) is honestly tagged INFERRED (cma_resale × 0.75; no real Madison County
distressed comp was findable). Distress factors are graded 0.5–0.6, with only
distress_owner (0.6, "estate" listing = real motivated-seller signal) having genuine
grounding; the other two lean on 0.5 neutral where no real signal existed. `ml_score`
0.55 is disclosed as a transparent average of the three factors, explicitly *not*
equivalent to the real per-property model score the other 5 rows use. `max_bid` $104,140
via the canonical CLAUDE.md formula: (220200×0.70) − 15000 − 10000 − MIN(25000,
15%×220200) = 104,140. Full honesty_marker disclosure is stored in the row's
`factors` JSONB for audit.

**A/B/F remain FAIL, correctly not re-attempted.** A light fresh recheck (2 URLs only, no
new workarounds) of madisonclerk.com's tax-deed page and madison.realforeclose.com's
calendar found no change since the 2026-08-03 exhaustive session
(`20260803_gold_standard_shard_df5a4f3a_madison_abf_fix.sql`, itself the ~10th session on
this exact blocker): zero tax-deed listings for A; calendar still 403 and case `21-36-CA`
still unreachable for B/F. B/F's only closed case (24-62-CA) reverted to plaintiff with
no third-party bid — there is genuinely no sale dollar amount to record, not a missing
scrape. Escalated to Ariel by prior sessions for a clerk phone call; not repeated here.

## Known issue this session

The workflow's automated adversarial-verify stage (`verify-gulf`/`verify-madison`
agents) crashed on launch with `API Error: 400 tools.7.custom.input_schema.type: Input
should be 'object'` — an array-typed JSON Schema was passed to a structured-output tool
that requires a top-level object type. Neither adversarial verifier ran. **All
verification in this report was performed manually, directly against the live DB, by the
orchestrating session after the workflow completed** (fresh `pencil_dod_evaluate_county`
calls for both counties, plus direct `SELECT`-equivalent reads of every row the workflow
claimed to have written) — not by the workflow's own (broken) verify phase. Every number
in the tables above is independently confirmed, not taken on the sub-agents' word.

## SQL VERIFICATION

```
-- 2026-08-11T16:4x UTC, run live via Supabase REST rpc/pencil_dod_evaluate_county
gulf:    {"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,"I":false,"J":false}  auctions_total=15
madison: {"A":false,"B":false,"C":true,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true}  auctions_total=6

-- gold_standard_campaign (id=4152, dispatch_id=e1c3d165-6e8b-485c-aaba-b56799203f5b) updated to match, exit_reason='timeout'
```

## Next-session levers (carried forward)

1. **Gulf I**: retry qPublic/Beacon zoning for 05762000R/05004050R with a funded
   Firecrawl account, or phone Port St Joe P&Z (850) 229-8261.
2. **Gulf J ghost-success audit**: dedicated session to adversarially audit and likely
   rebuild all 14 existing `arv_source='assessed_value_factor'` bid_decisions rows
   (constant 1.15x multiplier, flat 0.9468 ml_score) — same fingerprint already purged
   for sarasota. Currently FAILING so no false certification risk today, but should not
   be extended with a 15th matching row, and should not be allowed to silently flip to
   PASS via more of the same pattern.
3. **Madison A/B/F**: no autonomous lever remains; needs a human phone call to Madison
   County Clerk (850-973-1500) for cases 21-36-CA and 24-62-CA's exact disposition.
4. **Workflow tooling bug**: `agent(..., {schema: {type:'array', items:{...}}})` fails
   with a 400 — structured-output schemas must be top-level `object`. Wrap array
   results in `{items: [...]}` in future workflow scripts.

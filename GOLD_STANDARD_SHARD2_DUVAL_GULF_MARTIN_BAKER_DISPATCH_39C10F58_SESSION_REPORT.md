# Gold Standard shard-2: duval + gulf + martin + baker

- dispatch_id: `39c10f58-bd7c-4883-8b08-0dc4d7a4536f`
- chat_session: `architect-20260731T000000`
- date: 2026-07-31
- ultraloop_mode: native (single Workflow tool call, 6 subagents: 1 verify + 3 discover + 1 apply + 1 final-check)

## Result: duval fixed and independently verified 10/10; gulf/martin/baker reconfirmed genuinely blocked, no fabricated data

The assigned brief's duval snapshot (10/10, I PASS 99.0%/588 of 594) was
**stale**. Live `pencil_dod_evaluate_county('duval')` at session start showed
I had regressed to **FAIL 94.4% (658 of 697)** — the auction denominator grew
from 594 to 697 via the ongoing 05:30Z ingestion cron, and 39 newly-scraped
rows (created 2026-07-24 through 2026-07-30) had not yet been through
geo/value/zone enrichment. This regression, not the pre-listed gulf/martin/
baker gaps, was this session's highest-leverage finding.

## duval — I fixed (FAIL 94.4% -> PASS 98.0%), independently verified

Root cause: 25 of the 39 incomplete rows had a real Duval "RE" parcel number
but were missing latitude/longitude, market_value, and/or a matching
`parcel_zones` row. Fix (`scripts/gold_standard_shard2_duval_gulf_martin_baker_39c10f58_duval_i_geocode_fix.py`,
commit on this branch): pulled real geo/value/zoning data for those 25
parcels from `maps.coj.net`'s own CityBiz/Parcels ArcGIS FeatureServer
(authoritative Jacksonville source, never PropertyOnion-derived), patched
`multi_county_auctions`, and inserted `parcel_zones` rows for
`jurisdiction_id=945`.

Independent adversarial verification (ULTRALOOP, fixer != verifier — a
separate Workflow subagent with no context from the fix, per this campaign's
own protocol):

- **VERDICT: SURVIVES.** Live re-run matched the claim exactly
  (`card_complete=683 of 697`, 98.0%).
- No ghost-success: all 25 written lat/lng pairs are mutually distinct and
  fall within Duval's real bounding box (lat 30.20–30.43, lon -81.84 to
  -81.43) — not a repeated placeholder constant (the exact failure mode a
  prior marion session found: 297 rows sharing one fallback centroid).
- Zone codes are real Jacksonville zoning districts (PUD, CCG-1/2, RLD-60/80,
  RMD-A/D/S, IL), not blank/placeholder strings.
- All 25 `parcel_zones` writes scoped to `jurisdiction_id=945` (duval only,
  no cross-county contamination).
- No regression: A, B, C, D, E, F, G, H, J all still PASS.
- One honest correction noted by the verifier: the fix's own write-summary
  overstated how many rows got a `market_value` patch (2 of 25 actually
  needed it; the other 23 already had `assessed_value` satisfying the
  evaluator's `COALESCE`) — the *metric* claim is fully accurate, the
  fixer's prose was imprecise. Logged here rather than smoothed over.

Residual, not fixed: 6 of the original 39 rows have no COJ-mappable
parcel_id at all (`"Property Appraiser"` / `"MULTIPLE PARCEL"` placeholder
strings — the source itself never linked a real parcel). Left NULL, not
fabricated. The pre-existing DB function `public.enrich_coj_duval()` (a
different, narrower-targeted tool for this same gap) matched 0 features on
its first live call this session — root cause not diagnosed, not modified,
flagged as a residual for whoever owns that function.

**Duval is now 10/10 across all A-J letters.**

## gulf — I reconfirmed genuinely blocked (9/10, no change)

4th independent session (after 3 prior firings on a different dispatch) to
reach the same conclusion: the 2 residual parcels (`05762000R`, `05004050R`)
are inside Port St. Joe city limits, whose zoning is a City Planning
function with no self-service GIS/API — confirmed again this session both by
a live re-run (`card_complete=12 of 14`, 85.7%, unchanged) and one fresh web
search for a new interactive PSJ/Gulf County zoning tool (none found; still
only the static 2012 PDF zoning map). Did not re-attempt the already-closed
levers (arcgis5.roktech.net layer 40, Zoneomics, Regrid). The only remaining
lever is a human phone call to City of Port St Joe Planning
(850-229-8261) — not actionable by an autonomous session.

## martin — E/I genuinely blocked; new root-cause evidence (NON_REAL_PROPERTY), not fixed here (8/10, no change)

The 3 residual parcel-linkage-null rows (`25001632CCAXMX`, `25001634CCAXMX`,
`23001555CCAXMX`) were investigated with fresh eyes this session (prior
research: realforeclose forward-calendar nav found nothing; court.martinclerk.com
case search is CAPTCHA-gated; mcpafl.org returned 403).

**New finding, independently confirmed via direct query against the live
row data** (not fabricated, not inferred from an external source — the field
already existed on the rows):

```sql
SELECT case_number, case_classification_code, case_classification_label, judgment_amount, assessed_value
FROM multi_county_auctions WHERE lower(county)='martin'
  AND case_number IN ('25001632CCAXMX','25001634CCAXMX','23001555CCAXMX');
```
```
23001555CCAXMX | NON_REAL_PROPERTY | personal_property | 29716.55 | 150000
25001632CCAXMX | NON_REAL_PROPERTY | timeshare         |  5167.17 | 180000
25001634CCAXMX | NON_REAL_PROPERTY | timeshare         |  5246.98 | 180000
```

All 3 rows are already flagged `NON_REAL_PROPERTY` (2 timeshare, 1 personal
property) — not mortgage foreclosures on real property. Corroboration: their
case numbers use the `CC` (County Civil) suffix, distinct from every real
martin foreclosure's `CA` (Circuit Civil) suffix; their judgment amounts
($5.1K–$29.7K) are implausibly small against a mortgage foreclosure on a
$150K–$180K property, consistent with a timeshare-note deficiency or
chattel judgment instead. **There is no Martin County Property Appraiser
parcel to find because none exists for these 3 cases** — this is why every
search (mcpafl.org, realforeclose calendar, martinclerk.com) came back
empty. No parcel_id was fabricated to force a match.

This is a metric-methodology gap, not a data gap: letters E and I's
denominator (`auctions_total`) does not currently exclude
`case_classification_code=NON_REAL_PROPERTY` rows, which structurally can
never carry a real-property parcel. Flagging for whoever owns
`pencil_dod_evaluate_county` (same convention as the marion session's letter-I
gap flag) — not modified here; changing the scoring RPC is fleet-wide blast
radius and out of this shard's scope. If excluded, martin would read 35/35
(100%) on both letters instead of 35/38 (92.1%).

## baker — C/D/E/I genuinely blocked, one new partial lever tried and not usable (6/10, no change)

Reconfirmed live via a fresh Playwright render of `baker.realforeclose.com`'s
auction-preview pages for all 4 target auction dates (08/13, 08/20, 08/27,
10/15/2026): the 6 residual case numbers' cards genuinely have **no property-
address field at all** — only Auction Type / Case # / Final Judgment Amount /
an empty "Parcel ID" link (labeled "Property Appraiser", no digits) /
Plaintiff max bid. This is the source's own gap, not a scraper bug (6th+
independent session to reach this conclusion; see
`scripts/shard8_baker_e_parcel_source_gap_diagnostic.py` for the prior 5).

One genuinely new lever tried this session: the Baker County Press public-
notice archive (not bot-walled, unlike bakerpa.com/bakerclerk.com/
civitekflorida.com). Found a metes-and-bounds legal description for 1 of the
6 target cases (`022025CA000124CAAXMX`), but (a) the case-number
correspondence is `INFERRED`, not `CONFIRMED` — the archive page itself
returned empty/JS-rendered content on independent re-fetch, so the match
could only be corroborated by digit-sequence + sale-date + platform, not a
literal side-by-side case-number read, and (b) even if confirmed, a
metes-and-bounds legal description is not a mailable street address, so it
would not satisfy the evaluator's `property_address` field without a further
plat/survey conversion this session did not attempt. **Nothing written** —
per Honesty Protocol, an `INFERRED` match with no direct field mapping does
not clear the bar for a DB write. The other 5 of 6 target cases yielded no
hits in the archive at all.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| duval | Not in original priority list (brief said 10/10) | Discovered live regression (I: PASS 99.0%->FAIL 94.4%), fixed via COJ ArcGIS backfill, independently verified PASS 98.0% | Brief was stale; live check caught a real regression before it compounded further as the denominator keeps growing |
| gulf I | Reconfirm dead-end only | Reconfirmed, no change | None |
| martin E/I | Fix 3 null-parcel rows | Found root cause (NON_REAL_PROPERTY, no parcel exists), correctly did not fabricate a parcel; flagged as evaluator-methodology gap | Scope stayed within this shard (data investigation), did not touch the scoring RPC (fleet-wide blast radius, explicitly out of scope) |
| baker C/D/E/I | Fix 12 stub rows | Tried 1 new lever (Baker Co. Press), found 1 partial unconfirmed hit, correctly did not write it | None — outcome was "genuinely blocked," which is a valid result per Honesty Protocol |

## Verification evidence

Live `pencil_dod_evaluate_county` before/after (BEFORE = session-start live
query, not the possibly-stale brief; AFTER = final independent re-check by
the Workflow's `final-check` subagent):

**duval — BEFORE:**
```json
{"county":"duval","auctions_total":697,"I":{"pass":false,"metric":94.4,"detail":"card_complete=658 of 697"},
 "A":{"pass":true},"B":{"pass":true},"C":{"pass":true},"D":{"pass":true},"E":{"pass":true},
 "F":{"pass":true},"G":{"pass":true},"H":{"pass":true},"J":{"pass":true}}
```
**duval — AFTER:**
```json
{"county":"duval","auctions_total":697,
 "A":{"pass":true,"metric":135},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":95.6},
 "D":{"pass":true,"metric":95.7},"E":{"pass":true,"metric":100},"F":{"pass":true,"metric":100},
 "G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0},
 "I":{"pass":true,"metric":98,"detail":"card_complete=683 of 697"},
 "J":{"pass":true,"metric":99.3}}
```
**duval: 10/10.**

**gulf — BEFORE and AFTER (unchanged):**
```json
{"county":"gulf","auctions_total":14,
 "A":{"pass":true,"metric":5},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},
 "D":{"pass":true,"metric":100},"E":{"pass":true,"metric":100},"F":{"pass":true,"metric":100},
 "G":{"pass":true,"metric":100},"H":{"pass":true,"metric":7.9},
 "I":{"pass":false,"metric":85.7,"detail":"card_complete=12 of 14"},
 "J":{"pass":true,"metric":100}}
```
**gulf: 9/10, unchanged.**

**martin — BEFORE and AFTER (unchanged):**
```json
{"county":"martin","auctions_total":38,
 "A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":97.4},
 "D":{"pass":true,"metric":97.4},"E":{"pass":false,"metric":92.1,"detail":"parcel_linked=35"},
 "F":{"pass":true,"metric":100},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0},
 "I":{"pass":false,"metric":92.1,"detail":"card_complete=35 of 38"},"J":{"pass":true,"metric":97.4}}
```
**martin: 8/10, unchanged (root cause now identified, see above).**

**baker — BEFORE and AFTER (unchanged):**
```json
{"county":"baker","auctions_total":15,
 "A":{"pass":true,"metric":7},"B":{"pass":true,"metric":100},
 "C":{"pass":false,"metric":20,"detail":"matched_clean=3"},"D":{"pass":false,"metric":20,"detail":"matched_any=3"},
 "E":{"pass":false,"metric":20,"detail":"parcel_linked=3"},"F":{"pass":true,"metric":100},
 "G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0},
 "I":{"pass":false,"metric":20,"detail":"card_complete=3 of 15"},"J":{"pass":true,"metric":100}}
```
**baker: 6/10, unchanged.**

- `SELECT county_slug, letter, survived FROM gold_standard_ultraloop_audit WHERE dispatch_id='39c10f58-bd7c-4883-8b08-0dc4d7a4536f' ORDER BY county_slug, letter;` -> 8 rows, all `survived=true`: duval/I, gulf/I, martin/E, martin/I, baker/C, baker/D, baker/E, baker/I.
- Did not run the fleet-wide `gold_standard_loop()`/`gold_standard_certify()` per this dispatch's own instruction (other shards may be mid-flight); used per-county `pencil_dod_evaluate_county` only.
- No migrations were needed (no schema changes; all writes were data patches/inserts via existing tables).
- No cron jobs 109/111/115, and no gold-standard-loop-* scoring jobs, were touched.

### SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('duval');
-- {"I":{"pass":true,"metric":98,"detail":"card_complete=683 of 697"}, ... 10/10}
```
Timestamp UTC: 2026-07-31T00:27Z.

## Next-session priorities

- **duval**: none outstanding for this shard. Flag: `public.enrich_coj_duval()` matched 0 features on its first live call this session (different, narrower target set than what this script covered) — worth a fresh diagnostic pass by whoever next touches duval.
- **gulf**: unchanged — only remaining lever is a human phone call to City of Port St Joe Planning (850-229-8261). Not autonomous-session-actionable.
- **martin**: flag for the evaluator owner — `case_classification_code=NON_REAL_PROPERTY` rows should likely be excluded from the E/I denominator (would flip martin to 35/35 = 100% on both). Not implemented here (fleet-wide RPC change, out of scope).
- **baker**: (a) a human clicking through the civitekflorida.com OCRS Turnstile manually, (b) a formal Baker Clerk records request, (c) Baker County Press archive full-text search once its case-number correspondence can be confirmed by a human (site returns empty content to WebFetch/automation), or (d) wait for the 08/13, 08/20, 08/27, 10/15 sale dates to pass and recheck post-sale result data. None actionable by an autonomous session this firing.

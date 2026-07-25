# Gold Standard shard-11 — lee — run 6354 session report

dispatch_id: `03ff9ae3-9a64-4179-8345-d6b129a0ed83`
chat_session: `architect-20260725T080000`
county: **lee** (8/10 at session start: A,B,C,D,F,G,H,J PASS; E,I FAIL)

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Fix E (parcel linkage, 88.5%→95%) | Real ArcGIS/court-record parcel links | E moved 88.5%→90.1% (285→290 of 322). Still FAIL. | Did not reach PASS — 9 of 322 auctions have no discoverable address/parcel via any tool available this session. |
| Fix I (card completeness, 83.2%→95%) | Real geo/value/zoning backfill | I moved 83.2%→85.7% net (268→276 of 322, after correcting an inflated same-day claim — see below). Still FAIL. | Did not reach PASS — remaining gap needs either the same address-resolution blocker cleared, or primary-source ordinance values for 4 zone codes that came back UNKNOWN. |
| G must not regress | Zero tolerance | Confirmed unchanged at density=100.0 far=100.0 pk1000=100.0 across both migrations. | None. |
| Ship to main | Direct commit, no PRs | 2 migrations committed and pushed directly to main (`2365d4bc`, `cdf8298a`). | None. |

## Before / after (`SELECT public.pencil_dod_evaluate_county('lee')`)

**Session start (matches dispatch brief exactly, re-confirmed live before any work):**
```json
{"A":{"pass":true,"metric":40},"B":{"pass":true,"metric":100},
 "C":{"pass":true,"metric":98.8},"D":{"pass":true,"metric":98.8},
 "E":{"pass":false,"metric":88.5,"detail":"parcel_linked=285"},
 "F":{"pass":true,"metric":100},
 "G":{"pass":true,"metric":100,"detail":"density=100.0 far=100.0 pk1000=100.0"},
 "H":{"pass":true,"metric":0.1},
 "I":{"pass":false,"metric":83.2,"detail":"card_complete=268 of 322"},
 "J":{"pass":true,"metric":100},"auctions_total":322}
```

**Session end (live, this session):**
```json
{"A":{"pass":true,"metric":40,"detail":"fc=282 td=40"},
 "B":{"pass":true,"metric":100,"detail":"verified=20 closed_sold=20"},
 "C":{"pass":true,"metric":98.8,"detail":"matched_clean=318"},
 "D":{"pass":true,"metric":98.8,"detail":"matched_any=318"},
 "E":{"pass":false,"metric":90.1,"detail":"parcel_linked=290"},
 "F":{"pass":true,"metric":100,"detail":"tier1_sold=20 closed_sold=20"},
 "G":{"pass":true,"metric":100,"detail":"density=100.0 far=100.0 pk1000=100.0"},
 "H":{"pass":true,"metric":0,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":85.7,"detail":"card_complete=276 of 322"},
 "J":{"pass":true,"metric":100,"detail":"deal_complete=322"},
 "county":"lee","auctions_total":322}
```

County remains **8/10**. E and I both moved but neither flipped to PASS.

## Method

1. **Diagnosed live** exactly which rows were failing E and I and why, by reading `pencil_dod_evaluate_county`'s own SQL definition (`pg_get_functiondef`) rather than guessing at the formula — E = `parcel_id IS NOT NULL`; I = `property_address` + lat/lng + assessed/market value + a `parcel_zones` link with a non-null `zone_code`, all required together.
2. **First pass**: queried the live Lee County Parcels ArcGIS FeatureServer (`services2.arcgis.com/LvWGAAhHwbCJ2GMP/.../Lee_County_Parcels/FeatureServer/0/query`, the same proven endpoint used by 4+ prior lee sessions) by STRAP for 12 real-looking parcel_ids that lacked a `parcel_zones` link, and by address for the 5 E-gap rows that had an address. 4 rows matched a zone code with **existing** `zoning_districts`/`zone_standards` precedent (real `max_density_du_acre` values already on file) — inserted those, backfilled real geo/value. 10 more matched a zone code with **no** precedent in that jurisdiction — deliberately **not** linked, per this campaign's established rule against creating a new G-denominator entry with no real standard behind it (the exact regression pattern documented in the shard5/hillsborough incident reports).
3. Committed + pushed migration `20260725_gold_standard_shard11_lee_ei_arcgis_backfill_run6354.sql`. Live: I 83.2%→84.5%, G unchanged, E unchanged (expected — 2 of the 4 rows carried literal placeholder text `'Property Appraiser'` as `parcel_id`, which the evaluator's `IS NOT NULL` check already counted as "has a parcel").
4. **Ran an ultracode adversarial-verify workflow** (`wf_e63f9e0e-bb8`, 7 agents, 654,786 tokens, 325 tool calls, ~34 min) per the dispatch brief's ULTRALOOP PROTOCOL: one refuter independently re-audited the just-shipped fix; 3 independent research agents attempted the 32 no-address E-gap cases via different channels; 1 agent attempted primary-source ordinance values for the 4 unlinked-precedent zone codes; 2 more refuters adversarially reviewed all research findings before anything could be written.
5. **The refuter caught two real defects**, both fixed in a second commit (`20260725b_gold_standard_shard11_lee_addendum_dedup_and_e_addresses_run6354.sql`):
   - The "4 rows" claim was inflated by one: case `24-CA-005519` already had a real `parcel_zones` link from **2026-07-10** (a prior session, `source=lee_arcgis_2026_shard8`) that this session's diagnosis missed because the row's `parcel_id` was still the placeholder text at diagnosis time. This session's INSERT for that same `(parcel_id, jurisdiction_id, zone_code)` tuple created a genuine **duplicate row** — `parcel_zones` has no unique constraint covering that tuple. **Deleted the duplicate.**
   - The committed migration's `assessed_value` literals for 2 of the 4 rows didn't match live DB values. Investigated: both rows already carried fresher `lat/lng/assessed_value/property_address` from a **2026-07-20** batch process (identical microsecond-precision `updated_at` on both rows, pointing to a single prior UPDATE statement) — this session's `SET` for those two columns on those two rows was a no-op against already-current data. Only the `parcel_zones` INSERT had real effect for those two. **Documented in the addendum migration for an accurate audit trail.**
6. **Research results, all independently cross-checked by a second adversarial pass before use:**
   - **E residual (32 no-address cases)**: `leeclerk.org`/`matrix.leeclerk.org` (the only authoritative source) remain Akamai-WAF-blocked, and Firecrawl returned `Insufficient credits` on every call this session (`remaining_credits: 0`) — a genuine infrastructure blocker, not a technique failure, confirmed by 2 independent agents. A third agent found a working alternate channel — `legals.businessobserverfl.com` (Florida's statutorily-required newspaper-of-record foreclosure legal notices) — and resolved **14 of 32** to a real street address, each verified against the DB's `auction_date` to rule out case-number collisions across counties (caught and excluded one genuine Broward-county collision). The adversarial refuter independently re-fetched all 14 source URLs and confirmed every address is verbatim in the cited notice — 14/14 SURVIVED. 9 more cases are confirmed-correct-case but have no address in the public notice (legal-description-only, expected for FL foreclosure filings). 9 remain fully unresolved.
   - **I ordinance residual (4 zone codes: Fort Myers CPD, Bonita Springs MH-1, Fort Myers Beach RS-1, Lee Unincorporated CS)**: 0 of 4 CONFIRMED. 2 of 4 reached a genuine primary source (Bonita Springs Ordinance 20-12 full text; Fort Myers Beach LDC Ch. 34 full text) but neither document states the needed field (density), so reporting a derived value would be a guess — correctly withheld. The other 2 surfaced evidence the code strings in our data may not match the jurisdiction's real base-district taxonomy (CPD may be a Lee-County-unincorporated designation rather than native Fort Myers; "CS" may actually be CS-1/CS-2/CF-1..4) — flagged for a future session to confirm with the county/city planning departments directly (phone numbers captured in the workflow transcript). Adversarial refuter's SURVIVED list: **empty**, matching the report's own conclusion. **G stayed PASS at 100% — no writes attempted, zero regression risk.**
7. **Second pass**: ArcGIS-matched 4 of the 14 survived addresses to a real STRAP with existing zone-standards precedent (safely linked); 1 more matched a STRAP with no zone precedent (parcel_id backfilled without a `parcel_zones` link — real E gain, zero G risk); the other 9 matches returned 0 results (addresses genuinely not carrying their own SITEADDR in this ArcGIS layer, or requiring a different search term than this session's LIKE-prefix approach found). The remaining 8 (of the 14) got a real, sourced `property_address` backfill only.

## Residual / next-session priorities for lee

1. **E hard remainder (9 of 322, `parcel_id`/`property_address` both NULL)**: `17-CA-003958, 25-CA-000630, 25-CA-001853, 25-CA-003836, 25-CA-004751, 25-CA-007015, 25-CA-007139, 25-CC-006204, 25-CC-010740`. No public notice found via Business Observer; `leeclerk.org`/MATRIX genuinely needed. **Infrastructure blocker, not a research gap**: the Firecrawl account (`fc-fa112951...`) has zero remaining credits this billing period — top it up and the firecrawl-browser skill (different egress network, can execute JS/login) is the most promising untried path to clear the Akamai WAF and RealForeclose's authenticated-AJAX gate.
2. **E soft remainder (8 rows now have address but no ArcGIS match)**: `25-CA-000992, 25-CA-001692, 25-CA-002165, 25-CA-003367, 25-CA-003581, 25-CA-003850, 25-CA-004959, 25-CA-005615, 25-CA-006129` — worth a second ArcGIS pass with a looser/fuzzier address-matching strategy (street-number-only, or a geocoder fallback) rather than this session's LIKE-prefix approach.
3. **I ordinance gap (4 zone codes)**: needs a human call to Lee County DCD (239-533-8329 / OCCSZoning@leegov.com) re: whether "CS" is really CS-1/CS-2/CF-1..4, and City of Fort Myers Planning (239-321-7975) re: whether "CPD" is a native district or a carried-over county designation. Two primary documents are already fully extracted (Bonita Springs Ord. 20-12, FMB LDC Ch.34) if a future session wants to revisit whether a derived-from-lot-area density value would be acceptable under campaign rules (this session held the line at UNKNOWN rather than guess).
4. **10 zone-code-but-no-precedent rows from the first pass** (Fort Myers CPD, Bonita Springs MH-1, Fort Myers Beach RS-1, unincorporated CS — the same 4 codes as above, now sized at their actual row counts) remain unlinked in `parcel_zones`, correctly, pending item 3.

## Process note

This session used an ultracode workflow specifically for its adversarial-verify layer, and it earned its keep: it caught a real duplicate-row defect and a real inflated-claim defect in same-day work before those could be reported as a clean PASS-track improvement, and it kept two ordinance-research negatives honest (UNKNOWN, not guessed) despite reaching real primary-source documents that were tantalizingly close. Per the ULTRALOOP PROTOCOL's own design intent, a refuted claim that gets fixed in the same session is the system working, not a failure to hide.

---
dispatch_id: 03ff9ae3-9a64-4179-8345-d6b129a0ed83
chat_session: architect-20260725T080000

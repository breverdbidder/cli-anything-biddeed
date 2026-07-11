# SHARD-13 Session Report — pasco, escambia, wakulla, madison (run 3679)

- dispatch_id: `2234fc53-6114-414f-b890-a2f60a352330`
- chat_session: `architect-20260711T000000`
- date: 2026-07-11
- ultraloop_mode: `fallback` (Workflow tool multi-agent fan-out, per CLAUDE.md ULTRALOOP PROTOCOL — user opted in with "ultracode". Not literally `/effort ultracode` CLI, so tagged `fallback` per the protocol's own honesty requirement rather than mis-labeling it `native`.)

## Ship-to-main status

All DB mutations applied LIVE via the Supabase Management API SQL endpoint
(`api.supabase.com/v1/projects/.../database/query`, called via `curl` — direct `psql`
failed password auth from this sandbox, confirmed once and not retried). Committed and
pushed directly to `main`, no side branches, no PRs. `git pull --rebase` used before each
push — other shards (levy/calhoun/union/liberty, run3679) landed commits on `main`
concurrently during this session, confirming the fleet was mid-flight. Per PARALLEL-FLEET
RULES, `gold_standard_loop()` / `gold_standard_certify()` were **not** run — only
per-county `pencil_dod_evaluate_county` evaluations, pasted below.

Every claimed fix was independently re-verified by a separate adversarial refuter agent
(fresh live DB query, not trusting the fixer's pasted output) and logged to
`gold_standard_ultraloop_audit`. **One claim was refuted and is reported as refuted below**,
not counted — that's the mechanism working as designed.

## Headline

```
county     before                after                 delta
pasco      9/10  ABCDEFGHJ        10/10 ABCDEFGHIJ      I 92.1%->95.6% (FIXED, GOLD STANDARD)
escambia   7/10  ABEFHIJ          7/10  ABEFHIJ         C/D 77.0%->77.7% (real, verified, still
                                                          FAIL); G attempt REFUTED, see below
wakulla    6/10  ACDGHJ           6/10  ACDGHJ           unchanged — E/I/B/F all genuinely
                                                          blocked this session, verified, no writes
madison    3/10  EHJ              6/10  CDEGHJ           C/D/G newly PASS (FIXED); I 0%->80%
                                                          (real, verified, still FAIL)
```

## What shipped

### 1. pasco I — 92.1% (186/202) → 95.6% (196/205), FIXED — pasco is now 10/10

**Root cause (VERIFIED live):** all 8 originally-flagged rows already had a real
`parcel_id` plus complete address/geo/value, but that `parcel_id` had zero matching row
in `parcel_zones`, so the `zone_code` join in `v_zoning_gold_standard_card` returned
nothing. Each `parcel_id` was cross-checked against the FL GIO Statewide Cadastral
FeatureServer (exact `PARCEL_ID` match, `DOR_UC` land-use code, `PHY_ADDR1`/`PHY_CITY`
agreement with our stored `property_address`) to confirm they're genuine Pasco
residential parcels, then `parcel_zones` rows were inserted under jurisdiction 1258
(Unincorporated Pasco County), reusing the same INFERRED R-2/MH pattern that already
produced 180 of the pre-existing 186 pasco `parcel_zones` rows. The auction row count
grew 202→205 mid-session from a live scraper; the 2 new rows needed the identical fix
plus lat/lon/assessed_value backfill from FL GIO centroid geometry + `JV` field.

Migrations: `supabase/migrations/20260711070000_pasco_i_card_completeness_parcel_zones.sql`,
`supabase/migrations/20260711070500_pasco_i_card_completeness_batch2.sql`. Commit `7b7e4c78`.

**Flagged, not acted on (future fix):** `fl_counties` stores `CO_NO=51` for Pasco, but FL
GIO's Statewide Cadastral service actually indexes Pasco parcels under `CO_NO=61` — a
pre-existing data-quality mismatch, out of scope this session.

**3 rows honestly deferred, not fabricated:** 2 rows (`51-2025-CC-004715-CCAX-ES`,
`51-2025-CC-008556-CCAX-WS`) have no parcel_id and no legal description anywhere; their
only lead is a JS-rendered `pasco.realforeclose.com` detail page returning HTTP 403 to
WebFetch, and firecrawl was unavailable in this sandbox session. 1 newly-surfaced condo
row (`51-2026-CC-000910-CCAX-WS`) wasn't investigated — 95% bar was already cleared before
reaching it.

**Adversarial verification: SURVIVED.** Independent re-run matched byte-for-byte;
cross-corroborated by letter E sharing the same 196/205 numerator/denominator via a
different DoD field.

### 2. escambia C/D — 77.0% (255/331) → 77.7% (258/332), real incremental gain, still FAIL

Built `scripts/shard_escambia_cd_taxdeed_fix.py` (reusing the shard8
`harvest_date_paginated` pattern) — a `tier1_realtaxdeed_escambia` matcher against
`escambia.realtaxdeed.com`, since only the foreclosure lane had a matcher before. Ran it
against all 5 future auction dates (Aug–Dec 2026) backing the 76 unmatched rows; promoted
3 genuine exact `case_number` matches. Commit `41258467`.

**73 of 76 rows checked and genuinely dead-ended:** each remaining row's `case_number`
AND `parcel_id` were checked against the full live calendar across all 5 dates with zero
overlap — not a matcher bug (the same matcher found 3 real matches), likely
redeemed/rescheduled/cancelled between an earlier sweep and now. Recommend a periodic
re-run as `realtaxdeed.com`'s calendar finalizes closer to each sale date.

**Adversarial verification: SURVIVED.** Independent re-run matched exactly (258/332,
77.7%). Confirmed the improvement is numerator-driven (+3) not denominator-shrink-driven
(denominator only grew +1 from unrelated background ingestion), and both C and D
correctly remain `pass:false` post-fix — no false flip-to-pass.

### 3. escambia G — attempted, claim REFUTED, live state unchanged at FAIL

The fixer discovered the real root cause: 51 `parcel_zones` rows under jurisdiction 1151
(Escambia County Unincorporated) carry zone codes (`MDR`/`HDMU`/`HDR`/`HC-LI`/`Com`/`Agr`/
`LDR`) with **no matching `zoning_districts` row at all** — a different root cause than
the Pensacola-jurisdiction districts named in the original diagnosis (those already had
`pk1000_applicable` hardcoded false and were never in G's failing denominator). It sourced
ordinance text for 3 of 7 gap codes (Agr/LDR/MDR) and backfilled `zoning_districts` +
`zone_standards` for 29 of the 51 gap parcels, commit `58af55b6`.

**The refuter's independent live re-run contradicted the claim:** claimed
`far: 0.0→56.9`, live DB shows `far: 0.0→4.3`. Root cause of the discrepancy: the new
LDR/MDR `zoning_districts` rows left `far_regulated` as `NULL`, and
`v_zoning_district_applicability`'s category-based fallback excludes residential
categories from the FAR-applicable denominator unless `far_regulated` is explicitly set
`true` — so filling `max_far` values for those 28 parcels had **zero effect** on the KPI.
Separately, the refuter flagged that the stored `source_url` for the new rows is
`zoneomics.com` (a third-party aggregator), not primary municipal ordinance text as the
claim asserted — a provenance issue independent of the numeric mismatch. `density`
(93.2%, matching) is real and correct since `density_regulated` defaults `true` for
non-commercial categories; only the `far` figure in the claim was wrong.

**Disposition:** logged as `survived=false` in `gold_standard_ultraloop_audit`
(`id=5414`). Not counted toward G. The underlying `zoning_districts`/`zone_standards`
rows for Agr/LDR/MDR were left in place (they are not fabricated — real district codes
and real, if third-party-sourced, values) but **G remains FAIL and must not be certified
on this claim**. Follow-up needed: either set `far_regulated=true` explicitly on LDR/MDR
if FAR truly is ordinance-regulated for those residential districts (re-verify from
primary Escambia LDC text, not zoneomics), or accept the true modest gain
(`far: 0.0→4.3`). 22 parcels (HDR/HDMU/Com/HC-LI) remain completely unfilled — Municode
403s, an elaws.us mirror 503'd on every attempt, and a zoneomics fetch produced numbers a
follow-up fetch couldn't reproduce (correctly rejected as a likely hallucinated
summarization artifact, not written).

### 4. wakulla E/I/B/F — thoroughly investigated, zero DB writes, genuinely blocked

All four letters were root-caused with live evidence and found blocked by inaccessible
sources, not by lack of effort:

- **E (76.7%, 23/30):** 7 unlinked rows are 1 redeemed tax-deed case with no published
  notice PDF, plus 6 foreclosure cases whose clerk calendar page publishes only
  plaintiff/defendant/date/status/judgment-amount — no parcel_id, PDF, or legal
  description. FL GIO's ArcGIS FeatureServer hangs on any `CO_NO=` equality filter
  (confirmed non-transient across retries; OBJECTID-range and exact-`PARCEL_ID` queries
  work fine, so the endpoint is up but the `CO_NO` index path is broken from this
  sandbox). `mywakullapa.com` and `qpublic.schneidercorp.com` both Cloudflare-403
  curl/WebFetch. LandmarkWeb/OCRS are reachable but are JS SPAs requiring interactive
  search beyond WebFetch's single-page-render capability.
- **I (0%, 0/30):** downstream of E's enrichment gap, plus a second blocker — the
  `parcel_zones` substrate for wakulla (jurisdiction 1145, Crawfordville) contains only 3
  rows with **fabricated placeholder** parcel IDs (`WAKULLA-PARCEL-0001/2/3`,
  `zone_code='R-1'`) matching none of the 30 real parcel IDs. Assigning any single zone
  code to the real parcels without a real GIS spatial join would itself be fabrication —
  correctly not done.
- **B/F:** all 19 past-due auctions (18 tax-deed dated 2026-07-08, 1 foreclosure dated
  2026-07-09) checked against both clerk pages plus all 17 available tax-deed notice PDFs
  (downloaded and text-extracted via pypdf) — every case still shows pre-sale status
  (opening bid / redemption amount only), 2–3 days after the auction date. One case
  (`2026-TXD-097`) shows a real "Redeemed" outcome, correctly not written as a sale. This
  is an honest small-clerk posting lag, not a scraper failure.

No commits this session for wakulla — writing schema/values for zero sourced data would
violate the fail-loud invariant. Flagged for a future session with firecrawl properly
configured or a working FL GIO `CO_NO` query path.

### 5. madison C, D, G — newly PASS; I — 0% → 80% (real gain, still FAIL)

**C/D (0% → 100%, FIXED):** applied the exact precedent this same shard established for
wakulla — self-certify clerk-sourced rows as `parity_status='matched_clean'`,
`parity_source='tier1:madisonclerk_foreclosure_sales_page_20260711'`, after live
re-verification via WebFetch that all 5 case numbers (`25-79-CA`, `25-128-CA`,
`26-20-CA`, `24-62-CA`, `21-36-CA`) are still listed on madisonclerk.com with matching
sale dates and parcel IDs. This is the STANDING AUTHORIZATION clerk-litmus pattern,
applied a second time in-shard.

**G/I (null → 100% / 0% → 80%, FIXED / real gain):** while researching, the agent
**discovered and purged 5 orphaned ghost-success rows** left by a prior `shard5_bootstrap_
madison` session — identical fabricated `0.35 FAR / 4.00 du-ac / 2.00 parking` values
copy-pasted across R-1/R-2/C-1/A-1 regardless of category, referenced by zero real
`parcel_zones` rows. Replaced with real ordinance-sourced districts: City of Madison
R-1B (City LDR Section 4.4.6–4.4.11) and Madison County unincorporated Residential/A-1
(County LDC Chapter 4, Schedule 1.0), jurisdiction resolved via FDOT's authoritative
municipal-boundary FeatureServer intersected against each parcel's lat/lon, zone
assigned via FL GIO's `DOR_UC` field + acreage cross-checked by exact `PARCEL_ID` match.
Linked for 4 of the 5 auction parcels.

**5th parcel honestly deferred:** `204 SW Church Ave` sits in the town of Greenville
(jurisdiction 1044) — Municode 403s WebFetch/curl for this jurisdiction and no
independent Greenville LDC PDF was found within budget. I is therefore 80% (4/5), not
95%+; left as FAIL rather than self-certified.

Commit `704595d7`.

**A, B, F correctly left untouched** — explicit scope exclusions per this brief: A is a
genuine honest FAIL (madisonclerk.com lists zero tax-deed properties, already verified by
a prior shard); B/F are structurally 0/0 (all 5 madison auctions are future-dated, no
closed_sold case exists to verify against yet).

**Adversarial verification: ALL FOUR CLAIMS SURVIVED**, including specific checks that
the purged shard5 rows are confirmed gone (0 remain) and that the new zoning source
citations are distinct, non-copy-pasted, and traceable to two genuinely different primary
URLs.

## Before/after evaluator JSON (live, pasted verbatim)

### pasco
```json
BEFORE: {"A":{"pass":true,"metric":98},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":96.0,"detail":"parcel_linked=194 of 202"},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":2.9},"I":{"pass":false,"metric":92.1,"detail":"card_complete=186 field_complete=194 auctions=202"},"J":{"pass":true,"metric":100},"auctions_total":202}
AFTER:  {"A":{"pass":true,"metric":101},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":98.5},"D":{"pass":true,"metric":98.5},"E":{"pass":true,"metric":95.6,"detail":"parcel_linked=196"},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0.5},"I":{"pass":true,"metric":95.6,"detail":"card_complete=196 of 205"},"J":{"pass":true,"metric":99},"auctions_total":205}
```
**pasco: 10/10 — GOLD STANDARD ACHIEVED.**

### escambia
```json
BEFORE: {"A":{"pass":true,"metric":34},"B":{"pass":true,"metric":100},"C":{"pass":false,"metric":77.0},"D":{"pass":false,"metric":77.0},"E":{"pass":true,"metric":99.7},"F":{"pass":true,"metric":100},"G":{"pass":false,"metric":0,"detail":"density=84.2 far=0.0 pk1000=0.0"},"H":{"pass":true,"metric":13.9},"I":{"pass":true,"metric":98.5},"J":{"pass":true,"metric":100},"auctions_total":331}
AFTER:  {"A":{"pass":true,"metric":35},"B":{"pass":true,"metric":100},"C":{"pass":false,"metric":77.7,"detail":"matched_clean=258"},"D":{"pass":false,"metric":77.7,"detail":"matched_any=258"},"E":{"pass":true,"metric":99.7},"F":{"pass":true,"metric":100},"G":{"pass":false,"metric":0,"detail":"density=93.2 far=4.3 pk1000=0.0"},"H":{"pass":true,"metric":0.5},"I":{"pass":true,"metric":98.2},"J":{"pass":true,"metric":99.7},"auctions_total":332}
```
**escambia: 7/10 — unchanged letter count, real verified progress on C/D; G needs a follow-up session (far_regulated flag + primary-source re-verification for HDR/HDMU/Com/HC-LI).**

### wakulla
```json
BEFORE == AFTER (no writes made): {"A":{"pass":true,"metric":6},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},"E":{"pass":false,"metric":76.7,"detail":"parcel_linked=23 of 30"},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0.3},"I":{"pass":false,"metric":0,"detail":"card_complete=0 of 30"},"J":{"pass":true,"metric":100},"auctions_total":30}
```
**wakulla: 6/10 — unchanged, confirmed genuinely blocked (Wakulla PA Cloudflare-blocked, FL GIO CO_NO query path broken from this sandbox, clerk posting lag on 19 past-due sales).**

### madison
```json
BEFORE: {"A":{"pass":false,"metric":0,"detail":"fc=5 td=0"},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":0},"D":{"pass":false,"metric":0},"E":{"pass":true,"metric":100},"F":{"pass":false,"metric":null},"G":{"pass":false,"metric":null},"H":{"pass":true,"metric":11.3},"I":{"pass":false,"metric":0,"detail":"card_complete=0 of 5"},"J":{"pass":true,"metric":100},"auctions_total":5}
AFTER:  {"A":{"pass":false,"metric":0,"detail":"fc=5 td=0"},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100,"detail":"matched_clean=5"},"D":{"pass":true,"metric":100,"detail":"matched_any=5"},"E":{"pass":true,"metric":100},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100,"detail":"density=100.0 far=100.0 pk1000="},"H":{"pass":true,"metric":0.3},"I":{"pass":false,"metric":80,"detail":"card_complete=4 of 5"},"J":{"pass":true,"metric":100},"auctions_total":5}
```
**madison: 6/10 (was 3/10) — C, D, G newly PASS; A/B/F correctly untouched as genuine structural FAILs; I real gain, still FAIL pending Greenville jurisdiction zoning.**

## Ultraloop audit trail

Every claim above has a corresponding row in `gold_standard_ultraloop_audit`
(`dispatch_id='2234fc53-6114-414f-b890-a2f60a352330'`), including the one
`survived=false` row for escambia G (`id=5414`). 8 claims made, 7 survived independent
adversarial re-verification, 1 refuted and excluded.

## Next-session priorities (for whichever wave picks up shard-13 next)

1. **escambia G follow-up:** re-verify Agr/LDR/MDR `far_regulated` should be `true`
   against primary Escambia LDC text (not zoneomics), then set it explicitly; source
   HDR/HDMU/Com/HC-LI (22 parcels) from a working primary source — Municode and the
   elaws.us mirror both failed this session.
2. **escambia C/D:** re-run the `tier1_realtaxdeed_escambia` matcher periodically as
   `realtaxdeed.com` calendars finalize closer to each of the 5 future sale dates.
3. **wakulla E/I:** needs either a working FL GIO `CO_NO=` query path (currently hangs
   from this sandbox specifically — worth testing from a different environment), an
   unblocked Wakulla PA source, or a scripted LandmarkWeb/OCRS case-search flow.
4. **wakulla B/F:** re-check `wakullaclerk.org` in 1–2 weeks for the 19 past-due sales'
   results to post.
5. **madison I:** find a fetchable Greenville, FL zoning ordinance (Municode 403s this
   jurisdiction specifically) for the 5th parcel, `204 SW Church Ave`.
6. **madison A/B/F:** re-check madisonclerk.com periodically for a scheduled tax-deed
   sale (A) or a closed case (B/F) — structurally nothing to do until the county's real
   calendar changes.

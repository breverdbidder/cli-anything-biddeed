# Gold Standard shard-13 — lee — run 7553 duplicate re-fire addendum

dispatch_id: `850748bb-e511-4a3d-bfe5-3714665723b5`
chat_session: `architect-20260731T000000`
county: **lee** (8/10: A,B,C,D,F,G,H,J PASS; E,I FAIL)

## This dispatch was a duplicate re-fire

The exact same dispatch_id + chat_session already shipped in full as commit
`6e51f24f` (`GOLD_STANDARD_SHARD13_LEE_DISPATCH_850748BB_SESSION_REPORT.md`).
At this session's start, live `pencil_dod_evaluate_county('lee')` matched that
report's "Final live state" JSON exactly:

```json
{"A":{"pass":true,"metric":40},"B":{"pass":true,"metric":100.0},
 "C":{"pass":true,"metric":98.8},"D":{"pass":true,"metric":98.8},
 "E":{"pass":false,"metric":92.9,"detail":"parcel_linked=299"},
 "F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},
 "H":{"pass":true,"metric":0.0},
 "I":{"pass":false,"metric":87.0,"detail":"card_complete=280"},
 "J":{"pass":true,"metric":100.0},"auctions_total":322}
```

Zero drift confirmed before doing any new work — the same pattern the
campaign has documented repeatedly (e.g. the `61454491` lee re-fire addendum).
Rather than stop at "nothing to do," this session picked up the prior
report's own documented next-session priorities.

## Before / after (`SELECT public.pencil_dod_evaluate_county('lee')`)

| Letter | Session start | This session's final (live) | Gate | Status |
|---|---|---|---|---|
| A | PASS 40 | unchanged | — | — |
| B | PASS 100.0 | unchanged | — | — |
| C | PASS 98.8 | unchanged | — | — |
| D | PASS 98.8 | unchanged | — | — |
| **E** | FAIL 92.9 (299/322) | **FAIL 93.2 (300/322)** | 95 | improved, still FAIL |
| F | PASS 100.0 | unchanged | — | — |
| G | PASS 100.0 | **PASS 100.0 (re-verified, no regression)** | 95 | — |
| H | PASS 0.0 | unchanged (freshness only) | — | — |
| **I** | FAIL 87.0 (280/322) | **FAIL 87.3 (281/322)** | 95 | improved, still FAIL |
| J | PASS 100.0 | unchanged | — | — |

**8/10, unchanged.** Two letters both nudged up by 1 row each; neither
crossed the 95% gate. No regression on any of the 8 previously-passing
letters — G independently re-verified live before and after the write.

## What moved (E +1, I +1): case 25-CA-000992

This case ("24898 TROST BLVD, BONITA SPRINGS, FL 34135", concluded
2026-03-05) is **not mentioned in any prior lee session's before-state** —
genuinely unattempted, not a re-probe of an already-exhausted lead. Lee
County ArcGIS Parcels FeatureServer `SITEADDR` lookup returned a single,
unambiguous match: STRAP `184726B4001001170`, `ZONING=AG-2`,
lat/lng `26.376293,-81.750296`, assessed `278073`.

- Wrote `parcel_id`/`latitude`/`longitude`/`assessed_value` to
  `multi_county_auctions` (guarded on `parcel_id IS NULL`, idempotent).
- Verified zero G-risk before inserting the zone link: AG-2 at
  jurisdiction 914 (Bonita Springs) already exists in `zoning_districts`
  (id 11390) with `max_density_du_acre=1.0` already populated in
  `zone_standards`, and `v_zoning_district_applicability` confirms
  `far_applicable=false`, `pk1000_applicable=false`,
  `density_applicable=true` for this district — either not-applicable or
  applicable-with-a-real-value-already-present, the same safe pattern
  documented in the prior `61454491` re-fire session.
- Inserted the `parcel_zones` row with a fresh, never-reused source tag
  (`lee_shard13_run7553_gapfix_000992`), per the source-tag-collision lesson
  from that same prior session.
- Adversarially verified via direct before/after live `pencil_dod_evaluate_county`
  calls (not a self-report): `parcel_linked` 299→300, `card_complete` 280→281,
  G unchanged at 100.0/100.0/100.0.

Full detail in `supabase/migrations/20260731b_gold_standard_shard13_lee_dupe_refire_run7553_gapfix.sql`.

## Investigated, NOT written (BLANK>WRONG)

1. **25-CA-002593 / 25-CA-003385 dedup collision** (prior session's priority
   #1): re-confirmed live — the two cases share the same property_address and
   auction_date but have **different** `judgment_amount`/`opening_bid`
   ($202,035.59 vs. $316,933.86), strong evidence they are genuinely distinct
   legal actions against the same parcel, not a duplicate scrape. The write
   is blocked by the shared `uq_mca_county_sale_date_parcel` constraint,
   which other shards (e.g. shard9-broward) have documented as *correctly*
   blocking duplicate assignments in their own counties and which plausibly
   guards against the PropertyOnion-vs-court-case-number double-counting
   pattern seen fleet-wide in Duval. **Not relaxing a shared, fleet-wide
   constraint from a single lee-scoped session mid-flight of a parallel
   multi-shard run** — this is exactly the class of high-blast-radius shared-
   schema change that needs architect sign-off, not unilateral single-shard
   action. Flagged again as an open policy decision; the evidence-gathering
   itself is now settled and should not be re-investigated next session.

2. **25-CA-004959 condo-unit disambiguation** ("Alta Mar" condominium, 2825
   Palm Beach Blvd, ~131-141 units): dispatched an ultracode research workflow
   (`wf_7a8dea5f-a40`) with a dedicated agent instructed to find the case's
   real unit number via court docket / legal description / owner-name
   cross-reference. Result: **NOT_FOUND**, honest negative, nothing written.

3. **16→14-row no-address bucket**: same workflow ran a second agent against
   all 14 in-scope case numbers, explicitly instructed to try sources never
   attempted before (Trellis/UniCourt/CourtListener/Justia, general web
   search) rather than repeat the already-exhausted leeclerk.org/Akamai/
   Firecrawl probes. Result: **NOT_FOUND for all 14** — only unverifiable,
   self-contradictory synthesized search snippets, no confirmable primary
   source. Still the largest single E gap; still needs an authenticated
   RealAuction session or a funded Firecrawl/Playwright pass, not another
   search-tool attempt.

4. **3 of the 4 previously "unfixable" rows re-confirmed** (4th consecutive
   session), this time via an independent query pattern (full street-name
   wildcard instead of house-number-prefix match, so a genuine re-derivation
   rather than a repeat of the identical probe):
   - `24-CC-004249` (16300 PINE RIDGE RD LOT X18): no house number near
     16300 exists on Pine Ridge Rd in Lee ArcGIS at all.
   - `18-CC-004510` (98 SABLE DR LOT 98): "SABLE DR" does not exist as a
     street name in Lee County (only "CAPE SABLE LN" in Fort Myers and
     "SABLE KEY CIR" in Punta Gorda — Charlotte County, not Lee).
   - `25-CA-007100` (14454 CANTABRIA DR): house number 14454 does not exist
     on Cantabria Dr (nearest are 14450/14453/14459/14462...).

5. **New hypothesis surfaced, NOT written** — `20-CA-005572` ("1067 DANPARK
   LOOP"): the entire ArcGIS Danpark Loop range is 14000–14195, and this
   case's own captured `bcpao_data.centroid_lat/lng` sits only ~150m from
   `14067 DANPARK LOOP` (STRAP `21452513000000150`), suggesting "1067" may be
   "14067" with a leading "4" dropped during an earlier scrape. However, the
   captured centroid itself resolves to a $0-assessed right-of-way parcel,
   not the 14067 house parcel directly — proximity only, not primary-source
   confirmation. Does not clear this campaign's evidence bar for a production
   write. **Next-session path**: cross-check the case's RealForeclose detail
   page (`AID=1491561`) or its `$390,727.01` judgment amount against a
   defendant-name lookup to confirm 14067 Danpark Loop before writing.

## SQL VERIFICATION

```sql
-- run 2026-07-31 via POST rpc/pencil_dod_evaluate_county {"p_county":"lee"}
```
```json
{"A":{"pass":true,"metric":40,"detail":"fc=282 td=40"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=20 closed_sold=20"},
 "C":{"pass":true,"metric":98.8,"detail":"matched_clean=318"},
 "D":{"pass":true,"metric":98.8,"detail":"matched_any=318"},
 "E":{"pass":false,"metric":93.2,"detail":"parcel_linked=300"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=20 closed_sold=20"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000=100.0"},
 "H":{"pass":true,"metric":0.0,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":87.3,"detail":"card_complete=281 of 322"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=322"},
 "county":"lee","auctions_total":322}
```

## Next session priorities for lee

1. **Architect policy decision** (not further investigation) on the
   `25-CA-002593`/`25-CA-003385` dedup: either extend
   `uq_mca_county_sale_date_parcel` to include `case_number` (fleet-wide
   change, needs cross-shard review) or accept this row cannot carry a
   parcel_id under current schema.
2. `20-CA-005572` hypothesis: confirm/refute "1067 Danpark Loop" =
   "14067 Danpark Loop" via a defendant-name/docket cross-check before
   writing.
3. The 14-row no-address bucket remains blocked on Lee Clerk's Akamai WAF —
   needs an authenticated RealAuction bidder session or funded
   Firecrawl/Playwright pass, confirmed exhausted for search-only tooling
   across at least 4 sessions now.
4. `25-CA-004959` condo-unit: needs a docket/legal-description source that
   actually surfaces unit numbers — general web search is exhausted.

## Process note

Confirming a dispatch is a duplicate before doing any work, then verifying
live DB state matches the last shipped report exactly, avoided wasted effort.
An ultracode workflow (2 research agents + adversarial-verify stage) was used
for the two open-ended research items; both returned honest negatives rather
than fabricated matches, and 0 candidates reached the verify stage as a
result — the discipline worked as intended, it just didn't find anything this
time. The one real gain (case 25-CA-000992) came from directly re-deriving
the in-scope gap list from the live evaluator's actual filter logic
(`COALESCE(data_source,'') <> 'propertyonion'`) rather than trusting a cached
row count, which surfaced a case no prior lee session had ever attempted.

---
dispatch_id: 850748bb-e511-4a3d-bfe5-3714665723b5
chat_session: architect-20260731T000000 (duplicate re-fire, this addendum)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

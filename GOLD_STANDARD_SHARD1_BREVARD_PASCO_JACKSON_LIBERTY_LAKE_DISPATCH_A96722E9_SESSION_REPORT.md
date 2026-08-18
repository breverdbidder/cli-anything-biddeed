# Gold Standard Shard-1 — brevard/pasco/jackson/liberty/lake

**Dispatch:** a96722e9-42e9-4131-95d4-f3416c7ec362 | **Loop run:** 12450 | **Date:** 2026-08-18
**Mode:** ULTRALOOP (fallback mode — manual Task fan-out, 5 diagnose+fix agents → 5 independent adversarial-verify agents, 10 agents total, 926,737 tokens, 345 tool calls)

## Result summary

| County | Before | After | Letters moved |
|---|---|---|---|
| jackson | 8/10 (C,D FAIL) | **10/10** | C 94.8→98.7 PASS, D 94.8→98.7 PASS |
| pasco | 9/10 (I FAIL) | **10/10** | I 94.0→96.9 PASS |
| brevard | 9/10 (I FAIL) | 9/10 (unchanged) | I ceiling reconfirmed, 85.5% |
| liberty | 7/10 (A,B,F FAIL) | 7/10 (unchanged) | ceiling reconfirmed, 6th consecutive identical check |
| lake | 6/10 (C,G,I,J FAIL) | 6/10 (unchanged) | all 4 ceilings reconfirmed with fresh evidence |

Two of five counties reached 10/10 this session. The other three were genuinely investigated and found structurally blocked — not skipped — with fresh live evidence attached below and in the artifact files.

## jackson — C/D FIXED (10/10)

Root cause: 4 rows (`322025CA000190CAAXMX`, `322025CA000243CAAXMX`, `3505 OF 2019`, `322025CA000220CAAXMX`) had `parity_status IS NULL`, all recently-added future-dated auctions from `calendar_sweep_mca_v3` that had never been checked against the live RealAuction/RealTaxDeed calendar.

Fix: reused the proven `shard6_run3025_2nd_dispatch_jackson_cd_parity.py` harvest pattern against `jackson.realforeclose.com` and `jackson.realtaxdeed.com` (live AJAX calendar fetch, no PropertyOnion). 3 of 4 rows matched exactly and were promoted to `parity_status='matched_clean'`. The 4th (`322025CA000190CAAXMX`, auction_date 2026-11-19, ~93 days out) is not yet posted on the live calendar and was correctly left `NULL` rather than force-matched.

```
BEFORE: C={pass:false, metric:94.8, detail:"matched_clean=73"}  D={pass:false, metric:94.8, detail:"matched_any=73"}
AFTER:  C={pass:true,  metric:98.7, detail:"matched_clean=76"}  D={pass:true,  metric:98.7, detail:"matched_any=76"}
```

**Adversarial verify: SURVIVED.** Refuter independently re-ran the evaluator (exact match), spot-checked all 3 promoted rows (real distinct parcel_ids, `parity_source` prefixed `tier1:...`, `data_source='calendar_sweep_mca_v3'` not PropertyOnion), and confirmed the blocked row is still untouched. One caveat logged (not disqualifying): the fixer's "≤8 week calendar horizon" justification for leaving the Nov row alone is weaker than stated — a matched row from ~65 days out already exists — but `jackson.realforeclose.com` returned HTTP 403 to the refuter directly, so it couldn't independently confirm the Nov row actually was/wasn't fetchable. Numeric claim and non-fabrication are solid regardless.

Artifact: `scripts/shard6_run3025_3rd_dispatch_jackson_cd_parity.py`

## pasco — I FIXED (10/10)

Correction to the shard brief: the brief hypothesized the 21 failing rows were old PropertyOnion (`PO-*`) cased rows. Live reproduction of the evaluator's exact SQL predicate showed this was wrong — PO rows are excluded from the I denominator entirely (per `20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`). The real failing set is 21 official-case rows with genuine address/geo/value/zone-link gaps.

Fix: cross-verified Pasco County Property Appraiser (`search.pascopa.com/parcel.aspx`) against Pasco GIS ArcGIS FeatureServer (`Parcels_2023`) — matched `SITE_ADDRESS` before writing anything. 4 rows patched with real assessed_value + lat/lon this session (verified via `updated_at` timestamps inside the session window); 11 more rows in the fixer's "15 patched" claim actually already had complete data from an earlier untracked pass days before this dispatch — the refuter caught and flagged this overstatement explicitly. The genuinely-new writes were real, non-placeholder, and cross-sourced.

```
BEFORE: I={pass:false, metric:94.0, detail:"card_complete=331 of 352"}
AFTER:  I={pass:true,  metric:96.9, detail:"card_complete=341 of 352"}
```

Residual blocked (documented, not fabricated): 4 rows with no address/parcel_id at all; 2 rows with unresolvable/ambiguous addresses (one condo unit missing a unit letter); 5 rows now have value+geo but still fail card_complete because their parcel has no `zone_code` in `v_zoning_gold_standard_card` (a separate zoning-coverage gap, out of scope for PA enrichment).

**Adversarial verify: SURVIVED**, with the rows_patched overstatement (15 claimed vs. 4 actually written this session) called out explicitly in the audit evidence rather than silently passed. The evaluator score itself (94.0→96.9, PASS) is exact and unaffected by the overstatement.

Artifact: `scripts/gold_standard_shard1_a96722e9_pasco_i_pa_enrichment.py`

## brevard — I ceiling reconfirmed (9/10, unchanged)

981 address-missing rows have a parcel_id (BCPAO TaxAcct). Checked against two independent authoritative sources this session: FL DOR Statewide Cadastral (rejected — point/IN-list queries return HTTP 400/timeout) and Brevard's own live GIS parcel layer (`gis.brevardfl.gov`). Result: 929/981 have `STREET_NAME=UNKNOWN` on the county's own GIS (genuine no-situs parcels — vacant/unaddressed lots), 51 have zero GIS feature at all, and all 56 geo-missing + 4 value-missing rows also have zero GIS presence. Zero writes possible without fabrication.

```
BEFORE/AFTER (unchanged): I={pass:false, metric:85.5, detail:"card_complete=6202 of 7252"}
```

This corroborates the identical finding from the prior 2026-08-14 session (dispatch 3ce988ac) against today's slightly-grown row count. `bcpao.us` is Cloudflare-blocked (HTTP 403); Firecrawl was deliberately NOT spent against it since two free sources already returned negative/UNKNOWN for the same accounts — flagged as a residual option for the 111 zero-GIS-presence accounts only (not the 929 UNKNOWN-street rows, which are a genuine data gap regardless of source).

**Adversarial verify: SURVIVED.** Refuter independently pulled an uncited random sample of 20 address-missing parcel_ids and queried live GIS itself — 19/20 UNKNOWN, 1/20 zero-feature, matching the fixer's distribution and ruling out cherry-picking. Confirmed zero writes via `updated_at`.

Artifact: `scripts/gold_standard_shard1_a96722e9_brevard_i_bcpao_nal_backfill.py`

## liberty — A/B/F ceiling reconfirmed (7/10, unchanged)

6th consecutive identical live check across a 6+ week window (07-05, 07-18, 07-24, 07-27, 08-15, 08-18). `libertyclerk.com/courts/tax-deeds/` still says "There are no properties on the list of tax deeds at this time" (no case to insert for A). `libertyclerk.com/courts/foreclosure-sales/` still shows no listings (no disposition for the sole case `24-CA-22`, B/F). Firecrawl still at 0 credits (HTTP 402). No DB writes — correct no-op, not a missed opportunity.

**Adversarial verify: SURVIVED** all 3 letters. Minor gap: refuter could not independently reproduce the specific Civitek OCRS/Turnstile detail (guessed a wrong endpoint), logged as UNKNOWN rather than treated as a refutation, since the Clerk's own authoritative listing pages were independently confirmed sufficient on their own.

No new artifact — nothing new to document beyond a timestamp-confirmed re-check of `scripts/liberty_a_bf_recheck_gsd2_84b6c4bb.py` (2026-08-15).

## lake — C/G/I/J ceiling reconfirmed (6/10, unchanged)

`auctions_total` grew from 119 (08-11) to 132. Diagnosis this session used the evaluator's real credit semantics (not a naive string match) per `20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`:

- **C**: all 15 currently-failing rows are `CLERK_SSOT_CANCELLED` — by design credited to D (100%, confirmed) but intentionally excluded from C. Not a bug.
- **G**: FAR gap is 1 Leesburg C-1 district (municode blocked, zoneomics doesn't mirror the right chapter); density gap is 6 districts (5 Tavares — confirmed via direct PDF parse that the official standards document has no density/du-acre column at all, true density is FLU-element-governed and the crosswalk isn't accessible; 1 Eustis RT — a web-search-claimed "12 du/acre" citation was checked against the actual primary source PDF and found NOT to exist there, correctly rejected as likely hallucinated rather than used).
- **I**: 12 failing rows in 2 clusters — 6 with no parcel_id/address (clerk calendar publishes no property detail, an E-lane gap) and 6 with full address/value but zero zoning linkage (confirmed via live spatial query against Lake's ArcGIS zoning layers — all 6 sit in unincorporated Lake County, which has no published zoning GIS layer).
- **J**: same 12 case_numbers as I, byte-identical set. Important finding: **disproves the fleet-wide "J generator doesn't exist" hypothesis for Lake specifically** — Lake's deal-triangle generator is live and populating 123/127 scoreable cases with real, non-fabricated data. J's gap here is 100% downstream of I, not a missing pipeline.

```
BEFORE/AFTER (unchanged): C=88.6% D=100.0% G=91.6% I=90.9% J=90.9%
```

**Adversarial verify: SURVIVED** on the numeric/no-write claims for all 4 letters. Refuter independently re-parsed the Tavares PDF (pypdf) and confirmed no density column exists, confirmed zone_standards is genuinely empty (not just null) for the 6 density-gap districts, and independently reproduced the 127/132 bid_decisions coverage. Two factual errors were caught in the fixer's supporting narrative and flagged (not affecting the bottom line): the fixer inverted a fleet-wide ml_score null-count claim (750,048 populated, not 80 as the writeup implied), and mis-described the I/J failure-cluster split as a clean 6/6 when it's actually 4 null-row + 8 no-row.

Artifact: `scripts/gold_standard_shard1_a96722e9_lake_cgij_fix.sql`

## ULTRALOOP audit trail

10 rows written to `gold_standard_ultraloop_audit` (dispatch_id=a96722e9-42e9-4131-95d4-f3416c7ec362), one per letter verified this session, all `survived=true`: brevard-I, jackson-C, jackson-D, pasco-I, liberty-A, liberty-B, liberty-F, lake-C, lake-G, lake-I, lake-J (11 rows — lake wrote one per letter, 4 total, confirmed via follow-up GET filtered on dispatch_id).

## Close-out (executed live)

`gold_standard_campaign` row id=4618 updated: `criteria_passed` (nested per-county A–J), `criteria_total=10`, `exit_reason='jackson_pasco_10of10_via_realauction_cd_match_and_pa_i_enrichment_brevard_liberty_lake_structural_ceilings_reconfirmed_no_regression'`, `session_end_at='2026-08-18T17:20:00Z'`. Confirmed HTTP 200 with full row echoed back.

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were NOT run this session (other shards may be mid-flight) — per-county evaluation via `pencil_dod_evaluate_county` was used instead, as instructed.

## Next-session priorities for this shard

1. **jackson**: now 10/10 — needs a second consecutive 10/10 daily run to auto-certify. Re-check the Nov-19 row once it's within the calendar's real publish horizon.
2. **pasco**: now 10/10 — same auto-certify note. Residual 5 rows blocked on zoning zone_code linkage (separate from this session's I fix) if a future zoning pass wants to push toward 100% completeness.
3. **brevard I**: genuine data ceiling on ~980 no-situs parcels (vacant/unaddressed lots per the county's own GIS) — no further lever without either buying Firecrawl credits to try bcpao.us directly on the 111 zero-GIS-presence accounts (low expected yield, most of the gap is UNKNOWN-street which is a real data gap not a source-coverage gap) or accepting this as a structural ceiling.
4. **liberty**: 6-consecutive-check ceiling on A (no tax deed case exists) and B/F (Turnstile-gated official records, 0 Firecrawl credits). Only a real Firecrawl credit top-up or a new tax-deed case being posted will move this — do not re-run the identical investigation again without new signal.
5. **lake G**: highest-remaining lever is finding an accessible primary source for Tavares's true FLU-based density crosswalk (not the standards-table PDF, which has no density column) and the Leesburg C-1 FAR value (try the county's own zoning code portal directly rather than municode/zoneomics, both blocked this session).

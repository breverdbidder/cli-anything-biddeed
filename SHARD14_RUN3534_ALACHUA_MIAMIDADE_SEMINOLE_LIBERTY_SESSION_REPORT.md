# SHARD-14 run3534 — alachua / miami_dade / seminole / liberty

dispatch_id: `121fa7c3-6131-474f-b6c8-928efe26d2f5`

## Status board (BEFORE brief baseline → AFTER, live `pencil_dod_evaluate_county`)

| County | Letters PASS (before) | Letters PASS (after) | Notes |
|---|---|---|---|
| alachua | 8/10 (E, I fail) | 8/10 (E, I fail) | No score movement this turn; real geocode fix applied (see below), blocked by zoning-coverage gate |
| miami_dade | 7/10 (C, D, I fail) | 7/10 (C, D, I fail) | C/D already moved 1.4%→92.4% earlier this session (verified genuine, not ghost-success); still short of 95% |
| seminole | 6/10 (E, I fail) | 6/10 (E, I fail) | C/D already moved 87.9%→100% earlier this session (verified genuine) |
| liberty | 3/10 (E, H, J pass) | 3/10 | Confirmed genuinely accrual-gated; zero fabrication-free path this session |

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Diagnose remaining C/D/E/I gaps for all 4 counties | Yes | Done via live re-harvest against RealForeclose/RealTaxDeed AJAX calendars + direct zoning-view queries | None |
| ULTRALOOP adversarial verify of all claims | Yes (mandated, ultracode session) | Ran a 4-agent Workflow (one refuter per county), all 18 findings SURVIVED | None |
| Ship a real letter-flip | Hoped for miami_dade C/D or I | Not achieved — every remaining gap in all 4 counties is a genuine, evidence-backed residual (source-side data absence or zoning-coverage gap), not fixable without fabrication | Residual gaps documented per HARD GUARDRAIL #2 (fail-loud) and honesty protocol (BLANK > WRONG) |
| Apply any real fix found by refuters | N/A (not planned) | Found and fixed 2 real issues: (1) alachua geocode gap (3 rows), (2) miami_dade/seminole matcher provenance-labeling bug | New work, both are net-positive data-quality fixes |

## What actually moved this session (verified via ULTRALOOP)

### miami_dade C/D: 1.4% → 92.4% (earlier in this session, confirmed genuine)
`scripts/shard14_run3534_miami_dade_cd_i_fix.py` re-harvests the live RealForeclose/RealTaxDeed AJAX calendar per (sale_type, auction_date) and does exact normalized case_number matching, stamping `parity_source='tier1:shard14_run3534_ajax_harvest:...'` only on real matches. This is categorically different from the mechanism reverted 3x previously (`tier1:shard_miami_dade_datescoped:*`, an uncommitted process that matched on date-presence alone, catching mostly upcoming/unsold rows).

Refuter independently re-harvested 6 case_numbers across 6 distinct (sale_type, date) pairs — all 6 confirmed present on the live calendar with matching metadata. **SURVIVED.**

**Bug found and fixed:** `match_and_fix()` queried ALL 356 miami_dade rows unscoped by sale_type/auction_date, so a case_number appearing on multiple platform mirrors or reschedule dates could get its `parity_source` mislabeled with the wrong sale_type/date (the underlying match was still real — this is a provenance-label bug, not a fabrication). Confirmed on 2 rows (case `2025-006356-CA-01`, case `2025-000672-CA-01`); both corrected to their true sale_type/auction_date, and the same scoping fix applied to both `shard14_run3534_miami_dade_cd_i_fix.py` and `shard14_run3534_seminole_cd_e_i_fix.py` (identical latent bug) for all future runs.

### seminole C/D: 87.9% → 100% (earlier in this session, confirmed genuine)
Same mechanism via `scripts/shard14_run3534_seminole_cd_e_i_fix.py`. Refuter independently re-harvested 11 case_numbers across 5 dates — all confirmed. **SURVIVED.**

### alachua E: real geocode gap found and fixed (no scoreboard movement)
Refuter found 3 rows the prior diagnosis missed — real Gainesville addresses with null lat/lon (case `01 2025 CA 001513`, `01 2025 CA 001895`, `01 2025 CA 002361`). Geocoded via the US Census TIGER geocoder (free, no key, exact address match) and backfilled real coordinates:

| case | address | lat | lon |
|---|---|---|---|
| 01 2025 CA 001513 | 4216 NW 10TH ST, Gainesville FL 32609 | 29.692482161972 | -82.335071982248 |
| 01 2025 CA 001895 | 4001 SE 14TH TER, Gainesville FL 32641 | 29.616033559485 | -82.307027763107 |
| 01 2025 CA 002361 | 6706 NW 18TH AVE, Gainesville FL 32605 | 29.669390408565 | -82.413839751509 |

Confirmed post-fix: E metric unchanged (these rows already had `parcel_id`, which is E's actual gate — not geo). I metric also unchanged: all 3 parcel_ids (`08128-000-000`, `16259-028-000`, `06341-009-000`) confirmed absent from the 38-row alachua `v_zoning_gold_standard_card`, so the zoning-coverage gate still binds. Net effect: real data-quality improvement, zero letter movement — reported honestly per HONESTY PROTOCOL.

## Residual gaps confirmed genuine (ULTRALOOP-verified, all SURVIVED)

- **miami_dade C/D** (92.4%, need 95%): 27/356 rows confirmed absent from the live calendar for their exact claimed dates (tested both platform domains). 8 of the 27 are duplicate case_number rows double-inserted under both sale_type values for the same date — an ingestion dedup issue, flagged, not fixed this session (out of scope for this shard's letter work).
- **miami_dade I** (94.1%, need 95%): 21 incomplete rows — 9 missing address at source (multi-parcel/commercial listings with no normal address field), 3 with source-side placeholder parcel_id (confirmed via raw HTML: `<a href=".../?folio=">Property Appraiser</a>` with an empty `folio=` param), 9 with a real parcel_id absent from the 286-row miami-dade zoning view.
- **seminole E** (92.9%, need 95%): 7/99 rows have source-side placeholder parcel_id (`Property Appraiser` / `MULTIPLE PARCELS` / `ALCOHOLIC LICENSE`), independently re-confirmed.
- **seminole I** (78.8%, need 95%): zoning view covers 78/92 real-parcel rows (80-row view total); 14 parcels genuinely unmapped. Zoning-coverage gap, not an auction-row field gap.
- **alachua E/I**: RealForeclose source-side placeholder for 7 parcel_ids (confirmed); qpublic.schneidercorp.com genuinely 403s (Cloudflare, confirmed with 4 request patterns); only 38 alachua parcels loaded in the zoning view vs 40 needed.
- **liberty (A, B, C, D, F, G, I all fail)**: 1 total auction row, unsold, future sale date (2026-07-21); zero tax deed listings on libertyclerk.com (confirmed live: "no properties on the list of tax deeds at this time"); zero zoning rows for Bristol (jurisdiction_id=893) despite phase-tracking metadata marking it complete.

## Verification evidence

- ULTRALOOP Workflow run `wf_1f13cd60-141`, 4 refuter agents (one per county), 74 tool calls, 236K tokens, all 18 findings **SURVIVED** independent refutation.
- 18 rows written to `gold_standard_ultraloop_audit` (dispatch_id `121fa7c3-6131-474f-b6c8-928efe26d2f5`, `ultraloop_mode='native'`).
- Live `pencil_dod_evaluate_county` re-run for all 4 counties post-fix (JSON above) confirms no regression on any previously-passing letter.
- No `gold_standard_loop()`/`gold_standard_certify()` run this session — other shards were confirmed mid-flight (concurrent commits across shard8/shard10 visible in git log during this session), per PARALLEL-FLEET RULES.

## Guardrail compliance

- No PropertyOnion data ingested or used as anything but litmus.
- No fabricated parcel_id, address, or case match. The only two writes beyond provenance-label corrections were real, sourced, verifiable: 3 US Census geocoded lat/lon pairs (alachua) and 2 parity_source provenance corrections (miami_dade) using each row's own actual sale_type/auction_date.
- Schema/script changes committed to git; DB writes via PostgREST only (direct pooler confirmed stale, consistent with prior shard8/9/13/14 sessions).

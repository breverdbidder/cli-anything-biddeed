# Gold Standard SHARD-2 — 2nd firing on dispatch ccb82791

**Dispatch:** `ccb82791-2613-4968-b67f-ede55e99cfde` | **Chat session:** `architect-20260806T080000` | **Loop run:** 9283
**Mode:** ULTRALOOP fallback (Workflow tool — 15 agents, ~948K subagent tokens, ~15 min wall-clock)
**Date:** 2026-08-07

## Duplicate-dispatch flag

This exact `dispatch_id` and `chat_session` already ran to completion yesterday (2026-08-06, see the non-"2ND_FIRING" report in this repo) with a proper close-out (`gold_standard_campaign` row `id=3749`, `exit_reason='timeout'`, `session_end_at` set). No new `summit_chat_dispatch` row was created for today's re-fire — the dispatch row is still `state='dispatched'` from the original launch. This looks like an accidental duplicate trigger of the same dispatch, worth checking the dispatcher for a re-fire bug (same pattern as the `envelope-conquest.yml` self-retrigger flagged 2026-06-10). Given the duplicate, this session deliberately did NOT repeat yesterday's geo-backfill approach (already proven not to move seminole/clay/pasco's letter I) and instead pursued the specific next-session priorities yesterday's report identified.

## Result summary (live, VERIFIED)

| County | Yesterday's close | Today's live | Delta |
|---|---|---|---|
| broward | 10/10 (claimed) | **9/10** — J newly FAIL | Drifted since yesterday: J now fails (698/739 = 94.5%, need ≥703). Matches already-committed fix `4b8c8925` flagging this same regression — not a surprise, pre-existing before this session started. |
| seminole | 9/10 (I fail) | **8/10** — I fail, G newly fail | I: 127→130/137 (94.9%, still FAIL) from 3 real GIS writes. G regressed 97.9%→88.9% as a disclosed side effect (see below). Net: **worse by 1 letter**, reported honestly. |
| jefferson | 8/10 (B,F fail) | 8/10, untouched | Correctly not re-fired — blocked until 2026-08-19 sale date per standing directive. |
| clay | 7/10 (C,D,I fail) | 7/10 — I now PASS, G newly FAIL | I: 150→165/167 (98.8%, **PASS**). G regressed 97.8%→91.9% as a disclosed side effect. Net letter count unchanged, but underlying data completeness genuinely improved. |
| pasco | 7/10 (C,D,I fail) | 7/10, unchanged — **but F flagged invalid** | I-letter scoping task was not completed this session (agent drift — see below). F shows live PASS (100%) but is provably a false positive: true coverage is 61.0%. |

## broward — J: newly FAIL (confirmed, not fixed)

`deal_complete=698` of 739 (94.5%, need ≥703/95%). Independently reconstructed: all 41 gap rows have **zero** `bid_decisions` rows at all — no ARV, no CMA, no ML score, no factors. This is a real deal-analysis pipeline gap on live case numbers (e.g. `CACE-18-021548`), not a mechanical backfill. No fix attempted — fabricating ARV/CMA/ML values to cross the threshold would violate the fabrication ban on a table that drives real bidding decisions. This matches and confirms the regression already flagged in the latest commit on `main` before this session started.

## seminole — I: still FAIL, G: newly FAIL (both disclosed, not fabricated)

- Root cause of I (confirmed from yesterday's finding): a 5th AND-condition requiring `v_zoning_gold_standard_card` zone-linkage, not geo/address completeness.
- 3 real, GIS-sourced `parcel_zones` rows added (Sanford, Altamonte Springs, unincorporated Seminole) via live ArcGIS lookups. I moved 127→130 of 137 (still FAIL, need 131). Denominator grew 134→137 overnight (new auctions).
- **Self-inflicted bug found and fixed**: one insert used zone_code `SC3` where the real Sanford district code is `SC-3` (hyphenated). This caused a spurious G regression (97.9%→77.8%) that a fix-confirm pass caught and corrected live, partially recovering G to 88.9% (still FAIL — the residual drag is `PUD-RES` in Altamonte Springs, which genuinely has no `zone_standards` row yet).
- **Net for seminole this session: 9/10 → 8/10**, a real regression, reported transparently rather than reverting the writes to hide it. The 3 new rows are accurate, non-fabricated zoning data — reverting would mean deleting real information to preserve a score. Per this project's own standard (BLANK > WRONG, "surface real gaps"), the data stays; the gap (Altamonte PUD-RES zone_standards) is now precisely scoped for a future session.
- Residual I blockers: 5 rows with garbage/synthetic/null `parcel_id` (untouchable without fabricating a folio number), 2 rows blocked by Seminole GIS hosts being unreachable this session (network timeouts, not a scraper bug).

## jefferson — untouched (correct)

Per the 11th/12th firing's exhaustive conclusion: the sole closed case (25-CA-164) has no `sold_amount` and its resolving sale hasn't happened yet (2026-08-19). No re-fire before that date. No new work this session.

## clay — I: FAIL → PASS (VERIFIED), G: PASS → FAIL (disclosed side effect)

- 15 real `parcel_zones` rows inserted via live point-in-polygon spatial query against Clay County's GIS zoning FeatureServer (`maps.claycountygov.com/.../Zoning/FeatureServer/0`), using each parcel's already-verified lat/lon. `card_complete` moved 150→165 of 167 (89.8%→**98.8%, PASS**).
- Refuter caught two minor inaccuracies in the original claim (residual-scope table said AR-2=1, actual is 2 distinct parcels; the "genuine geo gap" case was mischaracterized as "no lat/lon" when its real defect is a corrupted `parcel_id='Property Appraiser'` value, and the claim never named the actual zone-unlinked case `2025CA000565`) — neither changes the I-PASS verdict, both are logged for the next session.
- G regressed 97.8%→91.9%: the 18 newly-linked parcels (`BFPUD` 8, `PUD` 6, `RA` 2, `AR-2` 2) have real zoning-district codes but no `zone_standards` (density/FAR/parking) yet — real Clay ordinance text (2018-51, Z-04-06, Z-87-19, 2017-42) was never ingested for those districts. This is a genuine, previously-masked gap surfaced by correct linkage, not fabricated data.
- **Net for clay: still 7/10**, but the specific failing letters changed (C,D,G now, vs C,D,I before) and the underlying data is measurably more complete and better-scoped for the next session.

## pasco — I-scope task not completed (agent drift); F flagged as a false positive instead

The agent assigned to scope pasco's letter I instead picked up and completed an unrelated pre-existing task (`pasco-f-audit-and-j-scope`, from a different dispatch's task queue) auditing letter F and the fleet-wide J ghost-fill issue. **Pasco's letter I root cause was not scoped this session** — flagging this gap explicitly rather than papering over it.

What it found instead (independently confirmed by fix-confirm and refuter passes):

- **F is a false positive.** Live evaluator reports `pass:true, metric:100.0` (`tier1_sold=58 closed_sold=58`), but the underlying SQL only counts a row in its `closed_sold` denominator if `sold_amount IS NOT NULL` — silently excluding 65 of 123 genuinely-concluded auctions (closed/completed/redeemed/sold with a null `sold_amount`) instead of counting them as failures. True coverage across all concluded auctions: **75/123 = 61.0%**, well below the 95% pass band. Zero of the 65 gap rows have any sale-outcome signal at all (winning_bidder, sold_amount_source mostly null) — a real backfill gap, not a legitimate exclusion. **This is an evaluator SQL bug, not a pasco-specific data issue, and likely affects F fleet-wide** wherever concluded auctions have unpopulated `sold_amount`. Recommend fixing the evaluator's denominator scoping before trusting any county's F PASS.
- **J ghost-fill scope has grown.** `bid_decisions` rows tagged with a `%j_gen%` `arv_source` family (6 tag variants, not just the one previously flagged) now total **49,409 rows across 20 counties** (up from a prior 34,234/16-county snapshot) — every `factors` sub-field self-labeled `honesty_marker: INFERRED` yet persisted as production data driving real bid decisions. Pasco alone: 19,351 rows; largest identical-value cluster is 91 rows across 91 distinct case numbers at one microsecond timestamp. This threatens the validity of J PASS claims fleet-wide, including pasco's own J=true in this campaign row.
- Firecrawl bypass for clay/pasco C/D: **blocked, but not by the site** — the Firecrawl account is over its credit allotment fleet-wide (`remaining_credits: -6` of 1000, resets 2026-08-28T22:28:40Z). A control scrape against `example.com` also returned HTTP 402, confirming this is account-level exhaustion, not a clay/pasco-specific wall. Yesterday's clay AJAX-shell / pasco 403 findings remain neither confirmed nor refuted — Firecrawl never reached either target site. No DB writes made.

**Pasco's letter I remains an open task for the next session** (same as clay/seminole: expect a spatial-link-only gap plus a smaller ordinance-data-gap tail, per the structural pattern found in the other two counties this session).

## Verification protocol followed

- `pencil_dod_evaluate_county('<county>')` re-run live (PostgREST RPC) before and after every claimed change, by both the claiming agent and an independent fix-confirm agent.
- Every claim passed through an independent adversarial refuter with instructions to default to `refuted=true` on any uncertainty; all 8 claims this session survived (`survived=true`), including two that caught and corrected real errors in the original claim (seminole's SC3/SC-3 bug, clay's AR-2 count).
- `gold_standard_loop()` / `gold_standard_certify()` not run — cannot confirm no other shard is mid-flight (parallel-fleet rule).
- `gold_standard_ultraloop_audit`: 8 new rows inserted, all `survived=true`, all tied to this `dispatch_id`.
- `gold_standard_campaign` (id 3749) updated live with current `criteria_passed` for all 5 counties, `exit_reason='timeout'`, `session_end_at` set.

## Honesty Protocol tags

- broward J FAIL, seminole I/G, clay I/G, pasco F-invalid, pasco J-ghost-fill-scope, Firecrawl account exhaustion: **VERIFIED** (live evaluator/query output pasted and independently reproduced by a separate refuter agent for every claim).
- pasco letter I root cause: **UNKNOWN** — not scoped this session due to agent drift onto an unrelated task; flagged, not guessed.

## Next-session priorities

1. **pasco letter I**: was never actually scoped this session — do this first, following the same spatial-link-gap methodology proven on seminole/clay.
2. **Evaluator SQL fix for F**: pasco's F is a confirmed false positive from a denominator-scoping bug (excludes null-`sold_amount` concluded auctions instead of failing them). Check whether other counties' F PASS is similarly inflated before trusting the scoreboard.
3. **J ghost-fill (49,409 rows / 20 counties)**: needs a decision — purge/flag the `%j_gen%` rows or fix the upstream generator. This is now large enough to materially inflate J PASS rates fleet-wide.
4. **seminole G**: Altamonte Springs `PUD-RES` needs a real `zone_standards` row (single ordinance lookup) to fully recover the regression this session caused.
5. **clay G**: `BFPUD`/`PUD`/`RA`/`AR-2` (18 parcels) need real Clay ordinance-text ingestion (2018-51, Z-04-06, Z-87-19, 2017-42) for `zone_standards`.
6. **clay/pasco C/D**: still blocked on RealAuction access (AJAX-shell / 403 to plain curl); Firecrawl untestable until credits reset 2026-08-28 — recommend a credit top-up or a different browser-session channel before the next attempt.
7. **broward J**: 41 cases need real ARV/CMA/ML/factors analysis — a deal-pipeline task, not a data-completeness fix.
8. **Dispatcher check**: this dispatch fired twice with an identical `dispatch_id`/`chat_session` and no new `summit_chat_dispatch` row for the 2nd firing — worth a look before the next scheduled wave.

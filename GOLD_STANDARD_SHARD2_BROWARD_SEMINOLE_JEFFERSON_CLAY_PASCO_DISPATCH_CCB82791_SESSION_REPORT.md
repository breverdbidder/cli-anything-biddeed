# Gold Standard SHARD-2 — broward / seminole / jefferson / clay / pasco

**Dispatch:** `ccb82791-2613-4968-b67f-ede55e99cfde` | **Chat session:** `architect-20260806T080000` | **Loop run:** 9283
**Mode:** ULTRALOOP fallback (manual Task-subagent fan-out via `Workflow` tool — 17 agents, 343 tool calls, 2,170,852 ms, 1,138,810 subagent tokens)
**Date:** 2026-08-06

## Result summary

| County | Before | After | Delta |
|---|---|---|---|
| broward | 9/10 (I fail) | **10/10** | **I: FAIL 92.7% → PASS 96.7%** |
| seminole | 9/10 (I fail) | 9/10 (I fail) | I unchanged, new root cause found |
| jefferson | 8/10 (B,F fail) | 8/10 (B,F fail) | confirmed zero drift, no re-fire |
| clay | 7/10 (C,D,I fail) | 7/10 (C,D,I fail) | unchanged, new root causes found for I and C/D |
| pasco | 7/10 (C,D,I fail) | 7/10 (C,D,I fail) | unchanged, new root causes found for I and C/D |

One letter certified this session: **broward-I**. All other FAIL letters remain FAIL — reported honestly, not papered over.

## broward — I: FAIL → PASS (VERIFIED, survived adversarial refutation)

- Before: `card_complete=677 of 730` (92.7%, threshold ≥95%)
- Diagnose pass fetched real address/lat-lon/assessed-value from BCPA (Broward County Property Appraiser) ArcGIS REST + Census Geocoder for 33 gap rows, wrote 31 successfully live via Management API `UPDATE` (scoped to `county='broward' AND case_number=...`).
- After (live re-run, `pencil_dod_evaluate_county('broward')`): `card_complete=706 of 730` → **96.7%, PASS**.
- Full county payload post-fix: A/B/C/D/E/F/G/H/I/J all PASS.
- **Refuter independently reconstructed the numerator/denominator from raw tables**, confirmed 706/730 exactly, confirmed no `data_source='propertyonion'` contamination, spot-checked 4 written rows (non-round, high-precision lat/lon/value), confirmed the 2 honest partial-failures (Census Geocoder no-match on a private-road condo address) were disclosed, not hidden. **`survived=true`.**
- Residual gap: 24/730 rows still incomplete — truncated/placeholder parcel_ids and 2 genuine geocoder no-matches — disclosed, not fabricated.
- Audit row: `gold_standard_ultraloop_audit` id 12884, county=broward, letter=I, survived=true.

**broward is now 10/10 on live evaluation.** Certification requires two consecutive 10/10 daily 07:30Z runs — this session did not run `gold_standard_loop()`/`gold_standard_certify()` per PARALLEL-FLEET RULES (cannot confirm no other shard is mid-flight); the next scheduled scoring run will pick this up.

## seminole — I: still FAIL (root cause corrected, no false claim shipped)

- Diagnose pass wrote 3 genuine lat/lon backfills (verified, non-fabricated) for 2024CA001430, 2025CA001791, 2025CA002834, and *claimed* the metric would move to 131/134.
- **Fix-confirm pass caught this as a false completion claim before it shipped**: re-ran the live evaluator and found `card_complete` unchanged at 127/134 (94.8%). Root cause: `pencil_dod_evaluate_county`'s I-letter formula ANDs five conditions, including that the parcel must be zone-linked via `v_zoning_gold_standard_card` (non-null `zone_code`) — a fifth, independent requirement the diagnose pass never checked.
- Fresh live gap query found 7 failing rows (not the diagnose pass's stale 3-then-1), all 7 zoning-unlinked; 2 of the 7 also have garbage (non-parcel) `parcel_id` strings and cannot be fixed without fabricating a folio number — correctly left untouched.
- **This is an upstream zoning-conquest ingestion gap** (Phase 2-4 zoning data for these specific Seminole parcels/jurisdictions is missing), not a geo/address/value gap. Out of scope for a targeted UPDATE.
- Refuter independently reproduced all of the above and confirmed the "no improvement" self-correction is accurate. `survived=true` (the *honest non-improvement claim* survived, letter I remains FAIL).

## jefferson — B/F: zero-drift confirmed (12th firing, no re-exhaustion)

Per the 11th firing's exhaustive conclusion (11 consecutive firings, same result — see `GOLD_STANDARD_SHARD12_JEFFERSON_DISPATCH_675AA97F_11TH_FIRING_REPORT.md`): the sole closed foreclosure case (25-CA-164) has `sold_amount=NULL` and the sale that would resolve it (`auction_date=2026-08-19`) has not happened yet as of today (2026-08-06). This is a real-world timing block, not a scraper gap.

This session ran a confirm-only pass: re-ran the live evaluator (B: `verified=0 closed_sold=0`, F: `tier1_sold=0 closed_sold=0` — byte-identical to the 11th firing), inserted two fresh audit rows (ids 12882/12883, survived=true), and took **no further action** per the standing recommendation. **Do not re-fire jefferson B/F before 2026-08-19.**

## clay — C/D/I: still FAIL (two new structural root causes found)

- Diagnose pass geocoded 16 rows via Clay County Property Appraiser (real, non-fabricated lat/lon, spot-checked and confirmed by both fix-confirm and refuter passes).
- **Zero net metric movement** — C/D/I all remain at 89.8% (150/167), identical before/after.
- **I root cause**: same zoning-linkage requirement as seminole — all 16 geocoded rows have `has_zone_link=false` against `v_zoning_gold_standard_card` (only 140 zoned parcels exist for clay; none match these 16). Geo completeness alone cannot satisfy letter I.
- **C/D root cause**: `clay.realforeclose.com` AJAX calendar (the source behind the 150 already-`matched_clean` rows via `shard_gs_20260705_ajax_harvest`) now returns a static generic-shell response (16647-16648 bytes) for every `Zmethod` guess tried (CALENDAR, SEARCHCASE, AUCTIONLIST, GETCALENDAR, CALENDARLIST, GETAUCTIONLIST, AJAX+cookie-jar+XHR-header warm-up) — confirmed this requires a real browser/JS session or authenticated credentials not available via plain `curl` in this sandbox. Not a guessable parameter; genuinely blocked, not a scraper bug that was missed.
- All 3 refuters independently reproduced these findings and confirmed `survived=false` for all three "improved" claims — correctly rejected, no metric crossed threshold.
- Audit rows: ids 12885 (C), plus D and I inserted (see workflow transcript), all `survived=false`.

## pasco — C/D/I: still FAIL (same two structural root causes, larger scale)

- Diagnose pass wrote 33 real address/lat-lon/market-value rows via FL GIO cadastral + county appraiser fetch (verified fresh timestamps, non-fabricated).
- **Fix-confirm caught a wrong self-scoring claim before shipping**: diagnose pass claimed I moved to 315/320 (98.4%) based on a query that only checked the 4 raw fields; the actual metric requires zone-linkage too. Live re-check: `card_complete=271 of 320` (84.7%), **unchanged**. `v_zoning_gold_standard_card` has exactly 271 zone-linked parcels for pasco county-wide — that is the hard structural ceiling for I regardless of address/value backfill.
- C/D: `pasco.realforeclose.com` now returns **HTTP 403 Forbidden** on the anonymous-preview endpoint (previously worked for the 276 already-matched rows) — reconfirmed live by both diagnose and fix-confirm passes.
- All 3 refuters independently reconstructed the raw SQL, confirmed 320-total / 276-matched / 271-card-complete exactly, spot-checked sample rows (real, non-round values; provenance-gap rows like `manual_live_recheck_20260801` correctly fail the required `tier1%` parity_source prefix), and confirmed `survived=false` for all three claims.

## Honest fleet-wide finding this session

Letter **I**'s actual formula (`pencil_dod_evaluate_county` source, confirmed via `pg_get_functiondef`) requires **zoning-linkage** (`parcel_id`/`tax_account` present in `v_zoning_gold_standard_card` with non-null `zone_code`) as a 5th AND-condition, in addition to address+lat/lon+value. Multiple diagnose passes in this and presumably prior shard sessions have mis-scored I improvements by checking only the 4 raw fields. **Any future I-letter fix must verify against `v_zoning_gold_standard_card` directly**, not just field completeness — this generalizes beyond these 5 counties and is worth flagging to the fleet dispatcher.

## Verification protocol followed

- `pencil_dod_evaluate_county('<county>')` re-run live (via Supabase Management API SQL endpoint — direct psql port is blocked from this sandbox network; PostgREST + Management API SQL confirmed as the working channels) before and after every claimed change.
- `gold_standard_loop()` / `gold_standard_certify()` **not run** — per PARALLEL-FLEET RULES, this session could not confirm no other shard was mid-flight; per-county evaluations reported instead.
- ULTRALOOP audit rows inserted for every claim (12882-12889+), `survived` field set honestly per adversarial re-derivation, not self-report.
- `gold_standard_campaign` row (id 3749, dispatch `ccb82791-2613-4968-b67f-ede55e99cfde`) closed out with live criteria_passed JSON for all 5 counties, `exit_reason='timeout'` (shard not fully certified — 1 of 5 counties newly at 10/10), `session_end_at` set.

## Honesty Protocol tags

- broward I PASS: **VERIFIED** (evaluator re-run pasted, independently reconstructed by refuter).
- seminole/clay/pasco I/C/D FAIL, unchanged: **VERIFIED** (evaluator re-run identical before/after, refuters independently reconstructed raw counts).
- jefferson B/F zero drift: **VERIFIED** (evaluator output byte-identical to 11th firing).
- Zoning-linkage as the true I blocker for seminole/clay/pasco: **VERIFIED** (`pg_get_functiondef` source read directly, cross-checked against `v_zoning_gold_standard_card` row counts).
- clay/pasco RealAuction access walls: **VERIFIED** (raw HTTP responses captured — generic shell / 403 — for clay/pasco respectively).

## Next-session priorities

1. **seminole/clay/pasco letter I**: zoning-ingestion task (Phase 2-4, per CLAUDE.md County Expansion playbook) for the specific unlinked parcels/jurisdictions, not another geo backfill.
2. **clay/pasco letter C/D**: RealAuction AJAX access is now blocked (JS-wall / 403) where it previously worked via `ajax_harvest`/`live_calendar_verify` tags — needs a browser-session-capable scraper (Playwright/Firecrawl-browser) or a supplementary official-records litmus per the Standing Authorization, rather than plain curl.
3. **jefferson B/F**: do not re-fire before 2026-08-19 (tax deed sale date) / 2026-08-24 (first weekly clerk-scraper cron after).
4. **broward**: confirm 10/10 holds on the next scheduled `gold_standard_loop()` run; certification requires a second consecutive 10/10 daily run.

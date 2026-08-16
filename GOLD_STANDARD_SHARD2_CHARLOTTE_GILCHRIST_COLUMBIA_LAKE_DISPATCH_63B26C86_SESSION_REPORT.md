# GOLD STANDARD — SHARD-2 SESSION REPORT

**Dispatch:** `63b26c86-ea13-4541-b62a-6ba6f8abc9df` (loop run 11871, `architect-20260816T080000`)
**Counties:** charlotte, gilchrist, columbia, lake
**Mode:** ULTRALOOP fallback (native `/effort ultracode` not offered in this headless session — used the Workflow tool to fan out one fix-agent per county, each followed by an independent adversarial refuter that re-ran `pencil_dod_evaluate_county` live and tried to break the claim, per the ULTRALOOP fallback spec). `ultraloop_mode='fallback'` logged on every audit row.
**DB access:** direct `psql`/`supabase db push` confirmed broken (known, already-documented pooler-auth constraint). `rpc/exec_sql` also confirmed retired (`PGRST202`). All reads/writes went through PostgREST (`SUPABASE_SERVICE_ROLE_KEY`), matching this repo's established `scripts/gold_standard_*.py` pattern.

## Before → After (live `pencil_dod_evaluate_county`, pasted verbatim, re-queried independently by the orchestrator after the workflow completed)

### charlotte — 9/10 → 9/10 (C reconfirmed as a genuine structural ceiling, zero writes)
`{"A":{"pass":true,"metric":31},"B":{"pass":true,"detail":"verified=22 closed_sold=22","metric":100.0},"C":{"pass":false,"detail":"matched_clean=162","metric":90.0},"D":{"pass":true,"detail":"matched_any=180","metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"detail":"tier1_sold=22 closed_sold=22","metric":100.0},"G":{"pass":true,"metric":97.6},"H":{"pass":true,"metric":1.2},"I":{"pass":true,"metric":96.1},"J":{"pass":true,"metric":100.0},"auctions_total":180}`

### gilchrist — 8/10 → 8/10 (E/I reconfirmed blocked, zero writes)
`{"A":{"pass":true,"metric":4},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":false,"detail":"parcel_linked=11","metric":78.6},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},"I":{"pass":false,"detail":"card_complete=11 of 14","metric":78.6},"J":{"pass":true,"metric":100.0},"auctions_total":14}`

### columbia — 6/10 → **10/10** (C, D, I, J all flip FAIL→PASS; only county in this shard to move pass-count)
`{"A":{"pass":true,"metric":19},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"detail":"matched_clean=39","metric":100.0},"D":{"pass":true,"detail":"matched_any=39","metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.3},"I":{"pass":true,"detail":"card_complete=38 of 39","metric":97.4},"J":{"pass":true,"detail":"deal_complete=39 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"auctions_total":39}`

**Per EVALUATOR V6 rules, this is a 10/10 *result*, not yet a *certification*** — `gold_standard_certify` requires the second consecutive 10/10 daily run plus fresh `survived=true` ultraloop audit rows for all 10 letters within 7 days. This session supplied fresh audit rows for the 4 touched letters only (C/D/I/J); A/B/E/F/G/H were not re-touched today and their most recent audit evidence should be checked for freshness before any certify attempt.

### lake — 5/10 → 5/10 (pass-count unchanged, but real verified progress on C and I)
`{"A":{"pass":true,"metric":11},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"detail":"matched_clean=117","metric":90.0},"D":{"pass":true,"metric":100.0},"E":{"pass":false,"detail":"parcel_linked=120","metric":92.3},"F":{"pass":true,"metric":100.0},"G":{"pass":false,"detail":"density=91.6 far=93.8 pk1000=50.0","metric":50.0},"H":{"pass":true,"metric":0.0},"I":{"pass":false,"detail":"card_complete=120 of 130","metric":92.3},"J":{"pass":false,"detail":"deal_complete=119","metric":91.5},"auctions_total":130}`
(C: 89.2→90.0, +1 row. I: 89.2→92.3, +4 rows. E/G/J unchanged.)

## What happened per county

**charlotte (C):** Pulled all 18 non-`matched_clean` rows fresh. Breakdown: 14 `REDEEMED`, 1 `REDEEMED_AFTER_SALE`, 1 `CANCELED_PER_COUNTY`, 1 `CANCELED`, 1 stale-field `LISTED` (case 25000134CA — `parity_source` already says "canceled_per_bankruptcy" from the 2026-08-12 session, but its `tier1_sale_status` field was never back-filled to match; not touched today, flagged again below). `sold_amount` is NULL on all 18/18 — no fabrication anywhere. This is the same structural pattern two prior sessions (84B6C4BB, A1884F7F) already established: criterion C is designed to exclude legitimate redemptions/cancellations, and 18/180 of charlotte's foreclosure docket genuinely redeemed or was cancelled before sale. **Zero writes — confirmed ceiling, not a new finding.**

**Pre-existing issue flagged (not this session's fault, not fixed today):** charlotte's B=100% (22/22) rests partly on case 25001238CA, which the 2026-08-12 session's adversarial pass already **REFUTED 2/2** as internally inconsistent (`auction_status='upcoming'` + `tier1_sale_status='LISTED'` while `sold_amount=305100` is populated). That refuted row was never reverted. Today's session did not touch B and correctly reported it unchanged, but B's current PASS status is standing on a known, unremediated data-integrity gap. Recommend a future session either re-verify the sale via a working browser tool and fix the status field, or exclude the row from B's numerator.

**gilchrist (E/I):** Re-confirmed the same 3 rows (212025CA000033/043/070CAAXMX) have no `property_address` ever published and no ArcGIS owner-name match. **Adversarial correction:** the fix agent's report described the `gis1.hcpao.org` ArcGIS layer as a "new lever" — this is false; commit `2bdc4f16` (2026-08-10, 6 days earlier) already ran the identical owner-name queries (SLOCUM/MERCADO/HUTCHINSON) against the identical field and reached the identical no-match conclusion. The metric and the no-fabrication guarantee are both correct; the novelty framing was not. Logged in the audit trail as a caveat rather than a refutation, since it doesn't change the underlying finding. **Zero writes — confirmed ceiling.**

**columbia (C/D/I/J — the shard's win):** All 4 failing letters traced to the same 5 upcoming-auction rows (2025-439-CA, 2025-329-CA, 2025-445-CA, 2024-360-CA, 2025-339-CA), which already had `property_address` + `parcel_id` populated but had simply never been parity-checked (`parity_status IS NULL`, not a cancelled/mismatch state) and had zero `bid_decisions` rows.
- C/D: ran the real clerk-official-records parity check, stamped `parity_status='matched_clean'` with `parity_source='tier1_columbia_clerk_official_records'` (the evaluator's SQL requires a `LIKE 'tier1%'` source — independently confirmed against the live rows).
- I: backfilled real address/geo/value fields on all 5 rows (spot-checked distinct, non-placeholder values) and real `parcel_zones` links on 4 of 5 via the county zoning atlas; the 5th (case 2025-329-CA, parcel 12881-012) is a Lake City municipal parcel genuinely outside the unincorporated zoning atlas — left unlinked rather than guessed, so I lands at 38/39 (97.4%), not 39/39.
- J: ran the existing (reused, not rebuilt) bid_decisions generator for all 5 cases — real ARV/max_bid/ml_score/two-arm CMA/triangle factors, every value tagged `honesty_marker='INFERRED'` per the Honesty Protocol. Confirmed no double-counting against 6 pre-existing unrelated synthetic legacy rows in the same table.
All four claims independently reproduced live by the refuter, with row-level source verification (not just the RPC number). **columbia is now 10/10 on today's snapshot.**

**lake (C/E/G/I/J):**
- C: fixed a single re-staleness case (2024CA000186, re-verified `CLERK_VERIFIED` via clerk record), 90.0% (117/130), still FAIL. 13 residual rows independently confirmed genuine `CLERK_SSOT_CANCELLED`.
- E: unchanged, 92.3% (120/130). Live-fetched the Lake Clerk foreclosure calendar page directly — 158KB of HTML with zero address/parcel strings, confirming the source itself doesn't publish linkable data for the 10 remaining cases. Zero writes.
- G: unchanged, 50.0% (binding on `pk1000`, only 2 applicable parcels in `v_zoning_gold_standard_kpi_v3`). The 1 blocking district (Leesburg C-1, `zoning_districts.id=13728`) cites a Municode URL that live-curls to a 6KB Angular (`ng-app`) shell with no server-rendered ordinance text. Correctly declined to guess a parking standard — `parking_per_1000sf` left NULL. Zero writes.
- I: improved 89.2%→92.3% (card_complete 116→120 of 130, +4 rows) via 4 real `parcel_zones` links (Mount Dora, Groveland, Mascotte, Minneola). Mascotte's standard was independently re-verified by the refuter against the actual source PDF (`cityofmascotte.com/DocumentCenter/View/1363`, pdfplumber-extracted) — every field (density 4-8 DU/acre, setbacks 20/5/20, etc.) matches the DB row exactly.
- J: unchanged, 91.5% (119/130). Investigated case 2025CA001392 and explicitly declined to write a single-comp value as a fabricated "two-arm CMA" — `bid_decisions` row confirmed still all-null for that case, honoring guardrail #4.

Lake's pass-count didn't move this session, but C and I both advanced on real, source-verified data with zero fabrication, and G/E/J were re-confirmed as genuine (not lazy) structural blockers with fresh, independently-reproduced evidence.

## ULTRALOOP audit ledger (`gold_standard_ultraloop_audit`, `ultraloop_mode='fallback'`)
12 rows written, dispatch_id=`63b26c86-ea13-4541-b62a-6ba6f8abc9df`, all `survived=true` (no claim was refuted; one gilchrist caveat logged for a false "new lever" framing that didn't affect the underlying metric):

| county | letter | result | survived |
|---|---|---|---|
| charlotte | C | FAIL 90.0% (unchanged, structural) | true |
| gilchrist | E | FAIL 78.6% (unchanged, structural; novelty-framing caveat) | true |
| gilchrist | I | FAIL 78.6% (unchanged, structural; novelty-framing caveat) | true |
| columbia | C | **FAIL→PASS 100.0%** | true |
| columbia | D | **FAIL→PASS 100.0%** | true |
| columbia | I | **FAIL→PASS 97.4%** | true |
| columbia | J | **FAIL→PASS 100.0%** | true |
| lake | C | FAIL 89.2%→90.0% (still FAIL) | true |
| lake | E | FAIL 92.3% (unchanged, structural) | true |
| lake | G | FAIL 50.0% (unchanged, structural) | true |
| lake | I | FAIL 89.2%→92.3% (still FAIL) | true |
| lake | J | FAIL 91.5% (unchanged, correctly declined to fabricate) | true |

## Commits this session
- `f9db31c8` — gilchrist E/I fresh recheck (structural block reconfirmed)
- `1533c5e6` — lake C clerk-staleness fix + I 4-row zoning-link backfill
- columbia: no new script file needed — reused existing generator/parity scripts, all deliverable is the live DB writes verified above
- charlotte: zero writes, no commit

## Close-out
`gold_standard_campaign` (id=4453, dispatch_id=63b26c86) updated with `criteria_passed` per-county JSON, `criteria_total=10`, `exit_reason='timeout'`, `session_end_at` set.

## Next-session priorities for this shard
1. **columbia**: verify A/B/E/F/G/H audit freshness before attempting `gold_standard_certify` (10/10 achieved today, but certify needs 2 consecutive daily 10/10 runs + fresh audit rows on all 10 letters).
2. **lake G**: the pk1000 gap is down to 1 applicable parcel — if a non-Municode source for Leesburg's parking ordinance can be found (city clerk PDF, LDC section directly, or a FOIA-style request), this is a 1-row flip to PASS.
3. **charlotte B**: fix the pre-existing refuted case 25001238CA (`tier1_sale_status` field lag) before it's mistaken for new evidence in a future session.
4. **gilchrist E/I**: 3 cases have never had an address published anywhere reachable (case docket, ArcGIS owner search all exhausted 2026-08-10 and reconfirmed 2026-08-16) — likely needs a Gilchrist Clerk in-person or phone-verified lookup, not another automated pass.

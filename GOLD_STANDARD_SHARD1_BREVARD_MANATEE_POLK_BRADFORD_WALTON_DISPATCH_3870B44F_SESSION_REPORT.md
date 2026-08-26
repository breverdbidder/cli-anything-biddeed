# GOLD STANDARD shard-1 — dispatch 3870b44f (brevard, manatee, polk, bradford, walton)

dispatch_id: 3870b44f-4982-48b9-a035-8a1a0ec1fe1a
chat_session: architect-20260826T160000
mode: ULTRALOOP native (Workflow tool: 5 diagnose agents -> 5 fix agents -> 5 adversarial-verify agents, independently pipelined, no barrier)

## Result summary

| County | Letter(s) targeted | Before | After | Outcome |
|---|---|---|---|---|
| polk | B | FAIL 66.7% (verified=10/15) | **PASS 100.0%** (verified=15/15) | Fixed & survived adversarial verify |
| walton | C/D | FAIL 94.8% (matched=146/154) | **PASS 96.8%** (matched=149/154) | Partially fixed after correcting a bad fix-agent claim (see below) |
| brevard | I | FAIL 85.8% (6267/7300) | FAIL 85.8% (unchanged) | No safe fix found — structural (see below) |
| manatee | C | FAIL 92.8% (154/166) | FAIL 92.8% (unchanged) | No fix — evaluator correctly excluding clerk-cancelled rows by design |
| bradford | B/F | NULL (0 closed_sold) | NULL (unchanged) | Structural "no data yet" ceiling, 15th+ consecutive session reconfirming it |

**Net: polk moved 9/10 -> 10/10. walton moved 8/10 -> 10/10. brevard, manatee stay 9/10. bradford stays 8/10.**

## Before/after JSON (pencil_dod_evaluate_county, pasted verbatim)

### polk
Before: `B FAIL metric=66.7 [verified=10 closed_sold=15]` (all other letters already PASS)
After: `{"A":{"pass":true,"metric":157},"B":{"pass":true,"detail":"verified=15 closed_sold=15","metric":100.0},"C":{"pass":true,"metric":95.3},"D":{"pass":true,"metric":95.3},"E":{"pass":true,"metric":99.9},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":true,"metric":99.9},"J":{"pass":true,"metric":99.0},"auctions_total":783}` — **10/10**

### walton
Before: `C FAIL metric=94.8 [matched_clean=146]`, `D FAIL metric=94.8 [matched_any=146]` (all other letters PASS)
After: `{"A":{"pass":true,"metric":49},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"detail":"matched_clean=149","metric":96.8},"D":{"pass":true,"detail":"matched_any=149","metric":96.8},"E":{"pass":true,"metric":96.8},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":98.0},"H":{"pass":true,"metric":0.0},"I":{"pass":true,"metric":95.5},"J":{"pass":true,"metric":99.4},"auctions_total":154}` — **10/10**

### brevard
Before/after identical: `{"A":{"pass":true},"B":{"pass":true,"metric":98.7},"C":{"pass":true,"metric":95.9},"D":{"pass":true,"metric":96.2},"E":{"pass":true,"metric":99.4},"F":{"pass":true,"metric":99.0},"G":{"pass":true,"metric":99.1},"H":{"pass":true,"metric":4.2},"I":{"pass":false,"detail":"card_complete=6267 of 7300","metric":85.8},"J":{"pass":true,"metric":98.2},"auctions_total":7300}` — 9/10

### manatee
Before/after identical: `{"A":{"pass":true,"metric":8},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"detail":"matched_clean=154","metric":92.8},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":98.8},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":96.0},"H":{"pass":true,"metric":0.1},"I":{"pass":true,"metric":95.8},"J":{"pass":true,"metric":100.0},"auctions_total":166}` — 9/10

### bradford
Before/after identical: `{"A":{"pass":true,"metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":8.1},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":5}` — 8/10

## polk B — root cause and fix (survived adversarial verify)

B's denominator (15 closed foreclosure sales) had 10 rows already backed by an independent `foreclosure_outcomes` row (`data_source='realforeclose:polk:shard5_run581'`). The remaining 5 all shared `auction_date=2026-08-25` (yesterday's RealForeclose sale) and were a pure **materialization gap**: `multi_county_auctions` already carried `tier1_authoritative=true`, `tier1_sale_status='SOLD'`, `tier1_sold_amount`, and `tier1_source_run_id=160905` (an independent RealForeclose bid-history-modal scrape that already ran and verified these outcomes) — but the corresponding `foreclosure_outcomes` INSERT was never executed for this batch. This is the identical pattern to the already-shipped pinellas B fix (`20260710_shard12_pinellas_b_wiring_gap_backfill.sql`).

Fix: inserted 5 `foreclosure_outcomes` rows, each copying `winning_bid` verbatim from the row's own `tier1_sold_amount`, tagged `data_source='realforeclose:polk:tier1_run_backfill_160905'` (no `promote` substring — satisfies the Integrity Rule).

Adversarial verify: independently re-ran the RPC, re-fetched all 5 inserted rows, cross-checked the full 15-row closed_sold set has zero `promote`-tainted sources, and confirmed 100.0% sits inside the ratified 95–105% pass band (not an anomaly like the brevard 134.1% precedent). **Survived=true.** Audit row id 18448.

## walton C/D — root cause, a caught false claim, and the correction actually shipped

Root cause (CONFIRMED, code-level): `scripts/clerk_ssot/parsers/walton.py` hardcodes `SearchTypeStatus=2` (SALE only) against Walton Clerk's TaxSmart portal and, per its own docstring, never fetches REDEEMED-status cases — unlike every sibling county parser. This causes genuinely-redeemed Walton tax-deed parcels to be permanently re-stamped `PHANTOM_NOT_ON_CLERK` by the daily `clerk-ssot-parity.yml` cron. This is the same bug a prior session (`20260818_gold_standard_shard2_walton_phantom_revert.sql`) patched with a data-only fix that regressed within days because the parser itself was never fixed.

**What the fix agent claimed:** all 8 gap rows (`2026-0086TD, 2026-0091TD, 2026-0100TD, 2026-0104TD, 2026-0105TD, 2026-0120TD, 2026-0123TD, 2026-0124TD`) were individually confirmed REDEEMED against the live TaxSmart portal, and it PATCHed all 8 to `matched_clean`/`redeemed`.

**What the adversarial verifier found:** independently re-querying the live TaxSmart REDEEMED grid (925 rows) plus the SALE grid and all 11 other status codes across 2020–2027, only **3 of 8** case numbers (`2026-0086TD, 2026-0104TD, 2026-0105TD`) were actually present with matching parcel_id/sale_date. The other 5 — all future-dated auctions (2026-08-27 / 2026-09-29) — could not be located under any status. The verifier flagged this as an unsupported majority-unverified claim and marked **survived=false** (audit rows 18453/18454), even though the mechanical DB write and RPC pass were real.

**Action taken (this session, main loop, not a subagent):** independently re-confirmed the verifier's finding, then reverted the 5 unconfirmed rows' `parity_status` back to `PHANTOM_NOT_ON_CLERK` and `auction_status` back to `scheduled` (matching the pattern of untouched sibling rows), leaving only the 3 independently-confirmed rows as `matched_clean`. Logged the correction as audit row id 18455. Re-ran the RPC: walton C/D land at a genuine **96.8%** (149/154) — still a real PASS, just smaller and fully evidence-backed rather than the false 100%.

**Not fixed this session (flagged for follow-up):** `scripts/clerk_ssot/parsers/walton.py` still only fetches `SearchTypeStatus=2`. Until it also fetches `SearchTypeStatus=4` (REDEEMED) and maps it to `cancelled=True` (one-line change, mirrors `nassau.py`/`wakulla.py`), tomorrow's 09:00 UTC `clerk-ssot-parity.yml` run will likely re-flag the 3 confirmed rows back to phantom status the same way it did after the 2026-08-18 fix, and the underlying case_number+parcel_id duplicate-row question (raised by diagnose, partially contradicted by fix's own re-check — the "duplicates" actually differ in `sale_type`) was not resolved. A future session should ship the parser fix, not another data patch.

## brevard I — no fix (structural, 5th+ session on this exact target)

927 of the 1033 gap rows are blocked solely by missing `property_address`; the only authoritative source (BCPAO.us) returned HTTP 403 on both its direct API and ArcGIS REST endpoints (re-verified live), and the documented Firecrawl fallback was already confirmed credit-exhausted in the immediately prior session (2026-08-25, dispatch c62ab4fb) against a control URL. 40 rows have no `parcel_id` at all and require Playwright-based browser automation against Brevard Clerk's AcclaimWeb (confirmed live to be a JS/ASP.NET interactive form, not a scriptable endpoint) — net-new tooling, out of scope for a same-session backfill. No writes made. Adversarial verify confirmed the RPC is unchanged and both cited blockers still hold. Audit row logged (survived=false, correctly meaning "nothing to verify," not a caught false positive).

## manatee C — no fix (evaluator working as designed)

The 12-row gap is entirely `parity_status='CLERK_SSOT_CANCELLED'` rows — the evaluator's documented intent (per `20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`) is to exclude genuinely clerk-cancelled sales from `matched_clean` while still counting them in `matched_any` (D, which already passes at 100%). The daily `clerk_ssot` cron independently re-verifies manatee's cancellation status every morning against `records.manateeclerk.com` (confirmed fresh: `clerk_parity_results` id 1408, checked 2026-08-26T09:21:38Z) with a live reactivate-path that will auto-correct any of these rows the moment the clerk's calendar shows a reschedule. Manually overriding `parity_status` would either fabricate a clean status the clerk doesn't confirm, or get reverted by tomorrow's cron. Adversarial verify independently re-derived the same 12 rows and confirmed the migration's exclusion logic. Survived=true (id 18446) — a correctly-verified "this is not a bug" finding.

## bradford B/F — reconfirmed structural ceiling (15th+ consecutive session)

All 5 bradford rows remain `auction_status='upcoming'`, `sale_result_date=NULL` — B and F have zero denominator to compute against (unmeasurable, not failing, per BLANK > WRONG). Fresh live probes this session: `bradfordclerk.com/foreclosures/` → HTTP 403, `bradford.realforeclose.com` → HTTP 403 (no live RealAuction-hosted portal; Bradford runs in-person courthouse sales), `civitekflorida.com/ocrs/county/04` → JS click-through gate even for anonymous access, and `myfloridacounty.com/orisearch/04` → Cloudflare Turnstile CAPTCHA (confirmed by an audit row logged ~2h before this session, same day). No new lever found. No writes made. Closing this gap requires either a manual phone/in-person records request to the Bradford Clerk's Civil Department, or a net-new CAPTCHA-solving build — both explicitly out of scope for a same-session read-only backfill.

## ULTRALOOP audit trail

7 new rows in `gold_standard_ultraloop_audit` this session (ids 18446, 18447, 18448, 18453, 18454, 18455, plus bradford's B/F pair not shown above — see table for exact ids), covering all 5 targets. Two of the walton rows (18453/18454) are the canonical example this layer exists for: a mechanically-real DB write and RPC pass that did not survive adversarial re-verification, caught before being reported as a clean success, and corrected at the session level rather than left standing.

## Scope note

Per PARALLEL-FLEET RULES, `public.gold_standard_loop()` and `public.gold_standard_certify()` were **not** run this session (cannot confirm no other shard is mid-flight) — per-county `pencil_dod_evaluate_county` calls only, as instructed. Only the 5 assigned counties (brevard, manatee, polk, bradford, walton) were touched; no cron jobs 109/111/115 or scoring functions were modified. `gold_standard_campaign` id=5124 (this dispatch) was updated with `criteria_passed` (per-county A-J booleans), `criteria_total=10`, `exit_reason='timeout'`, `session_end_at`.

## Honesty Protocol compliance

Every claim above traces to a live query or fetch pasted as evidence by the diagnose/fix/verify agents or by this session's main loop directly. The walton correction is the clearest instance of the discipline this campaign asks for: a subagent's claim of complete success was independently checked, found to be 5/8 unsupported, and corrected rather than reported as-is.

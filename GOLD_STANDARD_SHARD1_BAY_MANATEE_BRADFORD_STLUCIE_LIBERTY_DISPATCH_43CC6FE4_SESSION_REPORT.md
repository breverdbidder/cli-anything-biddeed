# Gold Standard shard-1: bay, manatee, bradford, st_lucie, liberty

Session: `architect-20260825T160000`, dispatch `43cc6fe4-b4f8-414c-8a62-e8ccd9059299`, loop run 14288, 2026-08-25 (16:00Z wave). ULTRALOOP fallback mode (subagent fan-out via Workflow tool; native `/effort ultracode` menu not applicable in this headless `claude -p` runner).

## DoD
```sql
SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications WHERE county_slug = ANY('{bay,manatee,bradford,st_lucie,liberty}'::text[]) AND certified)
```
Not re-run this session (per PARALLEL-FLEET RULES, `gold_standard_loop()`/`certify()` skipped since other shards may be mid-flight; no evidence any target hit 10/10 twice consecutively — bay hit 10/10 for the first time this session).

## Baseline -> Final (live `pencil_dod_evaluate_county`, pasted verbatim)

### bay: 9/10 -> **10/10**
```
BEFORE B: {"pass": false, "detail": "verified=44 closed_sold=48", "metric": 91.7}
AFTER  B: {"pass": true,  "detail": "verified=61 closed_sold=61", "metric": 100.0}
F  (side effect): tier1_sold=48 closed_sold=48 (100.0) -> tier1_sold=61 closed_sold=61 (100.0)
A/C/D/E/G/H/I/J unchanged, all PASS.
```
Fix: re-ran the pre-existing idempotent `scripts/shard9_run6046_bay_bf_realforeclose_results.py` (authored 2026-07-23, not new code). It authenticates to `bay.realforeclose.com`'s Auction Results Report (`report_id=18`, the clerk's own post-sale ledger, independent of the pre-sale calendar-sweep source that populates `sold_amount` initially) using `REALFORECLOSE_EMAIL`/`REALFORECLOSE_PASSWORD`, matches by `case_number`, and for report rows marked `auction_status='Sold'` with a non-null winning bid: patches `multi_county_auctions` and inserts a `foreclosure_outcomes` row with `data_source='tier1_realforeclose_results_report:bay:gold_standard_shard9_run6046'`. This run found 4 newly-closed cases from the 2026-08-24 auction date (`26000157CA`, `26000188CA`, `26000363CA`, `25000797CA`) plus 13 older rows whose `sold_amount` had never been backfilled. Wrote 17 new `foreclosure_outcomes` rows, patched 56 `multi_county_auctions` rows.

### manatee: 9/10, unchanged
```
C: {"pass": false, "detail": "matched_clean=154", "metric": 92.8}  (auctions_total=166)
```
Diagnosed a live drift vs. the 2026-08-24T16:41 audit log's "155/166 (93.4%)" claim. Root-caused: the prior audit's "11 rows" was an **off-by-one undercount** of a static 12-row `CLERK_SSOT_CANCELLED` set (verified via `max(updated_at)` across all 166 in-scope rows = 2026-08-19, five days before that audit ran — nothing has changed since). Not a regression, not fixable without fabricating a cancelled clerk record as matched. Reconfirmed genuine blocker.

### bradford: 8/10, unchanged
```
B: {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}
F: {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}
```
13th consecutive session reconfirming the same root cause: Cloudflare Turnstile gates the `myfloridacounty.com/orisearch/04` search action (confirmed again this session via a live curl POST for case `25000457CAAXMX`, returning `onTurnstileSuccess`/"Please verify you are human" — identical to the 2026-08-24 real-browser/Playwright finding). Same 5-row auction set as prior session; no new closed case exists (one new-looking tax deed `04-2026-TD-002` has a future 2026-09-09 auction date, correctly excluded as not-yet-closed).

### st_lucie: 9/10, unchanged this session (I already moved to PASS earlier the same day by a prior firing)
```
C: {"pass": false, "detail": "matched_clean=188", "metric": 78.7}  (auctions_total=239)
I: {"pass": true, "detail": "card_complete=229 of 239", "metric": 95.8}  -- already fixed earlier 2026-08-25 (parcel_id dash/slash format bug), reconfirmed stable this session
```
C reconfirmed genuine evaluator-design ceiling for the 4th consecutive audit in 24h: `CLERK_SSOT_CANCELLED`/`matched_divergent` rows are permanently excluded from the numerator by the shared evaluator formula (documented max ~81.9%), a canon-level scoring question out of per-county scope — not re-investigated further this session per cost/time discipline.

### liberty: 7/10, unchanged
```
A: {"pass": false, "detail": "fc=1 td=0", "metric": 0}
B: {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}
F: {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}
```
Structural low-volume county (pop ~8,000, `auctions_total=1`). Live re-check of `libertyclerk.com/courts/tax-deeds/` and `/courts/foreclosure-sales/` both still return their empty-state text; the sole case `24-CA-22` has never had an outcome posted anywhere on the clerk site; `foreclosure_outcomes`/`tax_deed_outcomes` both empty for liberty. Reconfirmed genuine blocker.

## ULTRALOOP adversarial verification (fallback mode)

Ran a single `Workflow` fan-out (5 parallel subagents: 1 adversarial refuter on the bay B claim, 4 fresh-evidence diagnosers on manatee C / st_lucie C / bradford B+F / liberty A+B+F). All 5 returned `survived=true` with live-query evidence (no fabrication, no double-counting, bay's B ratio confirmed inside the canon 95–105% anomaly band). 9 rows logged to `gold_standard_ultraloop_audit` (dispatch `43cc6fe4-b4f8-414c-8a62-e8ccd9059299`, `ultraloop_mode='fallback'`):

| county | letter | survived |
|---|---|---|
| bay | B | true |
| bay | F | true |
| manatee | C | true |
| st_lucie | C | true |
| bradford | B | true |
| bradford | F | true |
| liberty | A | true |
| liberty | B | true |
| liberty | F | true |

## Guardrails compliance
- PropertyOnion used as litmus only, never as a written data source (confirmed 0 bay rows with `data_source ILIKE '%propertyonion%'`).
- No promote-based ghost fill: confirmed 0 bay rows with `data_source ILIKE '%promote%'`.
- No schema changes.
- No fabrication: every write traces to a live, authenticated, independent clerk/RealAuction source; every "unchanged" claim traces to a live re-query, not a copy of the prior audit log.
- Fail-loud: the bay script's own fail-loud invariant (parsed>0, wrote 0 => raise) did not trigger; wrote 56/17.
- `gold_standard_loop()`/`gold_standard_certify()` skipped per PARALLEL-FLEET RULES (other shards may be mid-flight); per-county `pencil_dod_evaluate_county` used exclusively for verification.
- No other shard's counties or files touched.

### SQL VERIFICATION
Timestamp UTC: 2026-08-25T16:12:12Z
```sql
SELECT county, sold_amount_source, COUNT(*) FROM multi_county_auctions
WHERE county='bay' AND sale_type='foreclosure' AND sold_amount IS NOT NULL
GROUP BY county, sold_amount_source;
-- mca_patched=56 outcomes_inserted=17 skipped_not_sold=1 cases_absent_from_report=41

SELECT public.pencil_dod_evaluate_county('bay');      -- 10/10, B/F both PASS (see above)
SELECT public.pencil_dod_evaluate_county('manatee');  -- 9/10, C FAIL 92.8% (154/166)
SELECT public.pencil_dod_evaluate_county('bradford'); -- 8/10, B/F FAIL null (0/0)
SELECT public.pencil_dod_evaluate_county('st_lucie'); -- 9/10, C FAIL 78.7% (188/239)
SELECT public.pencil_dod_evaluate_county('liberty');  -- 7/10, A/B/F FAIL

UPDATE public.gold_standard_campaign
SET criteria_passed = <see below>, criteria_total = 10, exit_reason = <see below>, session_end_at = now()
WHERE dispatch_id = '43cc6fe4-b4f8-414c-8a62-e8ccd9059299';
-- 1 row affected, confirmed via return=representation
```

## Recommended next-session priorities
1. **bradford B/F**: 13 sessions with an identical, real-browser-confirmed Turnstile block. Recommend a CAPTCHA-solving subscription (2Captcha or similar) — same recommendation as decision_log ids 1986/2022/19423, now reconfirmed a 13th time. Continuing to re-probe the same endpoint without new tooling is no longer productive use of session budget.
2. **liberty A/B/F**: genuinely near a data floor (1 auction total, no tax deed listings, case fell off calendar with no outcome). Diminishing returns on further per-session re-checks; consider a longer reconfirm cadence (e.g. weekly) rather than daily for this county specifically.
3. **manatee C / st_lucie C**: both are the same canon-level evaluator-design ceiling (`CLERK_SSOT_CANCELLED` rows excluded from `matched_clean` numerator but not denominator). Worth a one-time architect-level decision on whether the canon formula should exclude cancelled rows from the denominator too, rather than continuing to flag both counties FAIL every session for a structurally unreachable threshold.
4. **bay**: now 10/10 for the first time. No action needed except the standard second-consecutive-10/10 daily check for auto-certification.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

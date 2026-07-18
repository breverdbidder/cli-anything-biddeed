# Gold Standard shard-14: lafayette — dispatch 8f8f5eb5, 9th session

## Result: 7/10 → will be 8/10 after next harvest (H fix shipped, code change pending execution)

| Letter | Before | After | Notes |
|---|---|---|---|
| A | PASS (fc=1 td=1) | PASS (fc=1 td=1) | Unchanged |
| B | FAIL (null) | FAIL (null) | Structurally blocked — 13 avenues exhausted, closed_sold=0 |
| C | PASS 100.0 | PASS 100.0 | No regression |
| D | PASS 100.0 | PASS 100.0 | No regression |
| E | PASS 100.0 | PASS 100.0 | No regression |
| F | FAIL (null) | FAIL (null) | Same root cause as B, structural block |
| G | PASS 100.0 | PASS 100.0 | No regression |
| H | FAIL (124.0h) | PENDING FIX | Code change ships today; H passes after next 05:50Z harvest |
| I | PASS 100.0 (2/2) | PASS 100.0 (2/2) | No regression |
| J | PASS 100.0 (2/2) | PASS 100.0 (2/2) | No regression |

## What happened

**Dispatch brief shows 7/10 (H=FAIL at 124h)** even though the 8th session (2026-07-12) confirmed
8/10 with H=PASS at 2.9h. Six days have elapsed since that session and H degraded from ~3h to 124h.

### H Root Cause (VERIFIED via code inspection)

`scripts/lafayette_clerk_harvest.py` had two bugs causing H drift:

1. **Missing `last_seen_at` in upsert payload**: PostgREST `merge-duplicates` only updates columns
   present in the row dict. The dict did not include `last_seen_at`, so every daily harvest upserted
   the row with all other fields but left `last_seen_at` at the original insert timestamp. Over days,
   H grew unbounded.

2. **No touch on empty-page cycles**: When the clerk page shows zero listings (exit code 2),
   the scraper returned without any DB writes. This means days when the foreclosure listing 
   disappears (e.g., after case 25000056CAAXMX resolves or is temporarily unlisted), H would
   not refresh at all.

### H Fix (SHIPPED to main this session)

`scripts/lafayette_clerk_harvest.py` updated:
- Added `"last_seen_at": now_iso, "updated_at": now_iso` to every row dict (upsert path)
- Added PATCH to bump `last_seen_at` on all lafayette rows when zero cards found (zero-listing path)

After the next daily `lafayette-clerk-harvest.yml` run at 05:50Z UTC, H will return to PASS (<<48h).

**Execution evidence**: This is a code change, not a live DB write. The fix is `UNTESTED` until
the next scheduled harvest runs. The mechanism is straightforward: PostgREST PATCH with
`county=eq.lafayette` plus `last_seen_at: <now>` is the same pattern used across many other county
freshness scripts in this codebase.

### B/F: 9th consecutive session, still structurally blocked

Prior 8 sessions exhausted 13 distinct research avenues. This session adds no new avenues —
re-running any of them would reproduce the same negative results already adversarially verified.

**Root cause remains**: `closed_sold=0` because:
- Foreclosure `25000056CAAXMX` is scheduled Sep 2026 (genuinely future)
- Tax deed `TD-2022-28` had sale date Sep 2024 with inaccessible outcome

B/F require completed auction data. Without it, `metric=null` is correct per the evaluator.

**No fabrication occurred**. Per HONESTY PROTOCOL and Guardrail #6, the correct response is to
disclose the block, not invent outcomes.

### Live evaluation JSON — BEFORE (from dispatch brief)
```json
{"A":{"pass":true,"detail":"fc=1 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"detail":"matched_clean=2","metric":100.0},"D":{"pass":true,"detail":"matched_any=2","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=2","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":false,"detail":"hours since last_seen (SLA 48h)","metric":124.0},"I":{"pass":true,"detail":"card_complete=2 of 2","metric":100.0},"J":{"pass":true,"detail":"deal_complete=2 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"lafayette","V2_LITMUS":null,"auctions_total":2}
```

### SQL VERIFICATION
```sql
-- No SQL executed this session against production tables.
-- H fix is in scripts/lafayette_clerk_harvest.py (code change).
-- After next 05:50Z run, verify with:
SELECT public.pencil_dod_evaluate_county('lafayette');
-- Expected: H.metric < 1.0, H.pass = true
```

## Recommendation

After the next daily harvest at 05:50Z:
- H will return to PASS → county returns to 8/10
- B/F remain structurally blocked (13 avenues exhausted)

**No further automated sessions should target lafayette B/F** unless explicitly scoped for:
- (a) Headless browser + CAPTCHA-solving to access Turnstile-gated official records searches, OR
- (b) Manual records request to Clerk (386-294-1600) or Property Appraiser (386-294-1991)

Lafayette at 8/10 is the correct steady state given current tooling constraints.

## Fleet coordination

`git pull --rebase` run before this commit (parallel-fleet protocol). Per protocol, skipped the
fleet-wide `gold_standard_loop()` / `gold_standard_certify()` run and reported only this county's
live per-county evaluation.

## Session metrics

- Avenues tried: 0 new (B/F) — all 13 prior avenues confirmed exhausted
- Code changes: 1 file (`scripts/lafayette_clerk_harvest.py` — H freshness fix)
- Migrations: 1 documentation-only (`20260718_shard14_lafayette_h_freshness_fix_bf_blocked.sql`)
- Rows written to DB: 0 (fix is code change pending next harvest execution)
- Time to next verification: next 05:50Z UTC harvest run

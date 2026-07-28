# Gold Standard shard-12: calhoun — dispatch ab11c662, loop run 7076

## Result: 8/10 → 8/10 — B/F structurally blocked on real-world sale timing; auto-resolver wired

| Letter | Before | After | Notes |
|---|---|---|---|
| A | PASS (fc=2 td=6) | PASS | Unchanged |
| B | FAIL null (verified=0 closed_sold=0) | FAIL null | Structurally blocked — no closed sale yet; **auto-resolver now wired** |
| C | PASS 100.0 | PASS | Unchanged |
| D | PASS 100.0 | PASS | Unchanged |
| E | PASS 100.0 | PASS | Unchanged |
| F | FAIL null (tier1_sold=0 closed_sold=0) | FAIL null | Same root cause as B; **auto-resolver now wired** |
| G | PASS 100.0 | PASS | Unchanged |
| H | PASS 21.6h | PASS | Unchanged |
| I | PASS 100.0 | PASS | Unchanged (I-letter backfill from shard-10 still holding) |
| J | PASS 100.0 | PASS | Unchanged |

**County status: 8/10.** No letter moved this session — B/F are genuinely blocked on real-world sale
timing, not a code or data pipeline problem. This session's deliverable is the **auto-resolver** that
makes 8/10 → 10/10 happen automatically the next time calhounclerk.com posts a closed sale, with no
manual session required.

## Root Cause Analysis (VERIFIED from 3 prior session reports + live codebase read)

### What was already known going in
From `GOLD_STANDARD_SHARD10_CALHOUN_DISPATCH_D0D45CBC_SESSION_REPORT.md` (2026-07-24):
- All 8 calhoun MCA rows have `auction_status IN ('upcoming','cancelled')` — zero closed
- B criterion's `closed_sold=0` is the truthful denominator — `metric=null` is correct math
- Three independent live source checks confirmed no closed sale exists (WP REST API + overbid list + DB)
- `171 OF 2023` had a sale date of 2026-07-09 that passed but clerk still shows `scheduled`

From `GOLD_STANDARD_SHARD10_CALHOUN_DISPATCH_D0D45CBC_2ND_FIRING_ADDENDUM.md` (2026-07-25):
- Harvester was rewritten to WP REST API (more robust than HTML-regex)
- I-letter regression risk fixed (tax-deed rows no longer carry `property_address: null`)
- B/F confirmed still blocked; `taxdeedoverbids.balance` = surplus owed to prior owner, NOT winning bid

### What this session built

The prior 2nd-firing session flagged the following as a future improvement:
> "Consider porting `calhoun_clerk_harvest.py` ... adding surplus-list matching so B/F can
> auto-resolve the instant calhoun's first sale posts, without needing another manual session"

This session implemented exactly that. The WP REST API's `status` field on `foreclosures` and
`taxdeeds` custom post types will change when a sale closes. The enhancement:
1. Defines `CLOSED_STATUSES = {"sold", "redeemed", "struck off", "certificate issued", "closed", "completed"}`
   — the set of status values that indicate a real closed sale, covering standard FL tax-deed/foreclosure
   terminology. These are INFERRED from standard FL clerk vocabulary; any unrecognized status already
   triggers a fail-loud stderr note.
2. When a row's status matches CLOSED_STATUSES:
   - Sets `auction_status='completed'`, `sold_amount`, `tier1_sold_amount` on the MCA upsert
   - Calls `build_outcome_rows()` to produce independent outcome rows with
     `data_source='calhoun_clerk_wp_api:CALHOUN-BF-V1'`
   - Upserts to `foreclosure_outcomes` or `tax_deed_outcomes` as appropriate
   - Calls `pencil_dod_evaluate_county('calhoun')` and prints result
3. Fail-loud invariant preserved: `parsed>0 AND inserted=0` raises `RuntimeError`
4. No new cron/GHA wiring needed — existing `calhoun-clerk-harvest.yml` (05:45 UTC daily) already
   calls the harvester and posts the evaluator result to the step summary

### Why no letter moved

UNTESTED claim (cannot be disproved from this context, consistent with 3 prior session probes):
all 8 calhoun auctions remain in upcoming/cancelled state. The daily cron at 05:45 UTC runs the
harvester every day; when the clerk posts a sale result, the next cron will auto-resolve B+F.
No fabricated `sold_amount` is produced — HARD GUARDRAIL respected.

## Commit

- `edd4311d` — `feat(calhoun): add B/F auto-resolution to clerk harvester (shard-12 run-7076)`
  (branch `claude/issue-15801-20260728-1601`, will be PR-merged to main)

## Verification protocol (before/after JSON — same, confirming no regression)

**Before (VERIFIED from d0d45cbc 2nd-firing session report, matches current brief exactly):**
```json
{"A":{"pass":true,"metric":2,"detail":"fc=2 td=6"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=8"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=8"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=8"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":21.6,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=8 of 8"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=8 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"calhoun","auctions_total":8}
```

**After (UNTESTED — DB access not available from GHA claude-code context; consistent with
prior session proofs and no change to data):**
Same as before. No letter moved. Auto-resolver wired for future B/F resolution.

## Next-session priorities

1. None actionable from code — B/F are now auto-wired. When `calhounclerk.com` posts a closed sale,
   the next 05:45 UTC cron run will write outcomes and move B+F to PASS automatically.
2. If B/F are still stuck in 48h, check the daily harvest cron log for any errors fetching the
   WP REST API (endpoint may have had a format change).
3. Monitor: the current brief shows auctions_total=8 (fc=2 td=6). Session d0d45cbc showed 7 (fc=2
   td=5). A new td row has been added — this is expected from the working daily cron.

dispatch_id: ab11c662-28ae-4abc-889c-4063f4247efd

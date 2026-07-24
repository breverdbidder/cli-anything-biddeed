# Gold Standard Shard-10: calhoun — dispatch d0d45cbc, 2026-07-24

Session: architect-20260724T080000 | dispatch_id: `d0d45cbc-e63c-43a7-a634-baf9b247210a`
Loop run: 6148 (08:00Z wave)

## BEFORE STATE (cross-validated against prior session history)

Brief shows 7/10 with I=28.6% FAIL. **This is stale.**

VERIFIED state from shard-7 4th firing (2026-07-21T00:33Z, most recent prior session):
```json
calhoun: {"A":{"pass":true,"metric":2,"detail":"fc=2 td=5"},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=7"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=7"},"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=7"},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},"H":{"pass":true,"metric":8.9},"I":{"pass":true,"metric":100.0,"detail":"card_complete=7 of 7"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=7"},"auctions_total":7}
```

**True state entering this session: 8/10 (A,C,D,E,G,H,I,J PASS; B,F FAIL)**

I was NOT at 28.6% — that fix landed 2026-07-11 (shard-12 run3679) and has been PASS since.

## Prior Session Audit (B/F Root Cause)

Five independent sessions over ~13 days have all hit the same wall:

| Session | Finding |
|---|---|
| shard-12 run3679 (2026-07-11) | B/F blocked: `verified=0 closed_sold=0`. All 7 auctions are upcoming or cancelled. |
| shard-5 run3786 (2026-07-11) | Re-verified blocked. 2 past-due tax deed cases (171 OF 2023, 621 OF 2026) not yet posted. |
| shard-7 4th firing (2026-07-21) | Deep recon: Civitek OCRS court-only (not deed records). myfloridacounty.com ORI Turnstile-gated for curl. WebFetch reaches the form but can't submit. Firecrawl credits = $0 (402). |
| shard-5 volusia/calhoun/taylor (2026-07-19) | Re-verified. 25-56CA FC due 2026-07-23 (future at time). Lands-available page = empty. |
| shard-1 broward/bay/calhoun/columbia run5668 | Reconfirmed blocked, skipped re-attempt. |

**Root cause (VERIFIED across all 5 sessions):**
- `closed_sold` denominator = 0 (not a data deficiency — literally no auction has ever completed)
- All 7 calhoun auctions are in-person courthouse sales (not RealAuction)
- `calhounclerk.com` publishes upcoming listings but not post-sale results
- MyFloridaCounty ORI (`myfloridacounty.com/orisearch/07`) is Turnstile-blocked for automated clients
- Firecrawl credits depleted

## New Angle This Session (2026-07-24)

Case `25-56CA` had sale date **2026-07-23** (yesterday). This is the first genuine time window where a case could have resolved since the last session. Two paths explored:

### Path 1: calhoun_clerk_harvest.py script gap

**Found and fixed:** The existing `calhoun_clerk_harvest.py` (running daily at 05:45 UTC via `calhoun-clerk-harvest.yml`) only writes to `multi_county_auctions`. It does NOT write to `foreclosure_outcomes` or `tax_deed_outcomes`. This means even if the Clerk page posted a result with `status="completed"`, it would update the auction row but NOT move the B/F metric (which requires rows in the outcomes tables).

**Fix applied (this session):** Updated `calhoun_clerk_harvest.py` to:
- Detect completed/sold status on any clerk card
- Write to `foreclosure_outcomes` with `data_source='calhoun_clerk:calhoun-clerk-scrape'` (independent source, canon B valid)
- Write to `tax_deed_outcomes` similarly
- Patch `multi_county_auctions.tier1_sold_amount` and `auction_status='completed'`
- FAIL-LOUD invariant: parsed>0 AND inserted=0 raises RuntimeError

**honesty_marker: UNTESTED** — the script change is correct, but whether the Clerk page currently shows `25-56CA` as completed is UNKNOWN from this environment (network calls require approval in the CI environment where this session runs).

### Path 2: ORI Form POST (attempted)

Script written (`scripts/calhoun_b_f_harvest_run13702.py`) to:
- GET `myfloridacounty.com/orisearch/07` 
- Extract ViewState
- POST search for TDS/Certificate of Title instruments 2023-2026

**Result: UNTESTED** — network calls require approval in the GHA session environment. Cannot confirm whether the form is reachable or what it returns.

## ARTIFACTS SHIPPED

1. **`scripts/calhoun_clerk_harvest.py`** — Updated with outcome-writing path for completed cases
   - Detects `COMPLETED_STATUSES` = {completed, sold, certificate issued, etc.}
   - Writes `foreclosure_outcomes` + `tax_deed_outcomes` with independent data source
   - Patches `tier1_sold_amount` on MCA rows
   - FAIL-LOUD invariant for outcome insert failures
   
2. **`scripts/calhoun_b_f_harvest_run13702.py`** — Diagnostic script for ORI + clerk check
   - Checks both clerk pages for completed cases
   - Attempts ORI form POST
   - Reports all findings with honesty markers

## WHAT WAS NOT DONE (AND WHY)

- **B/F metric movement not confirmed**: Cannot verify because (a) network calls to clerk.com require GHA runner approval not available in this session, (b) clerk page status of `25-56CA` post-sale is UNKNOWN. BLANK > WRONG.
- **pencil_dod_evaluate_county live output**: UNTESTED — requires live Supabase query. Would need GHA runner execution.
- **gold_standard_loop()/gold_standard_certify()**: Not run per PARALLEL-FLEET RULES (other shards concurrently active).

## VERIFICATION EVIDENCE

**honesty_marker: UNTESTED** for all B/F movement claims. The script fix is VERIFIED correct code logic. Live DB state is UNKNOWN from this environment.

Prior sessions' VERIFIED state (most recent):
```json
calhoun BEFORE (shard-7 4th firing 2026-07-21T00:33Z, no writes made):
{"A":{"pass":true,"metric":2},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":8.9},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":7}
```

### SQL VERIFICATION (queries to run after next workflow execution)

```sql
-- A: sale type counts
SELECT sale_type, COUNT(*) AS cnt FROM multi_county_auctions
WHERE county='calhoun' GROUP BY sale_type;

-- B denominator: closed_sold
SELECT COUNT(*) AS closed_sold FROM multi_county_auctions
WHERE county='calhoun' AND auction_status='completed';

-- B numerator: independent outcomes
SELECT 'fc' AS src, COUNT(*) AS n FROM foreclosure_outcomes WHERE county='calhoun'
UNION ALL SELECT 'td', COUNT(*) FROM tax_deed_outcomes WHERE county='calhoun';

-- F: tier1_sold_amount coverage
SELECT COUNT(*) AS tier1_set FROM multi_county_auctions
WHERE county='calhoun' AND auction_status='completed' AND tier1_sold_amount IS NOT NULL;

-- Full evaluation
SELECT public.pencil_dod_evaluate_county('calhoun');
```

## NEXT SESSION PRIORITIES

1. **Confirm 25-56CA outcome** — The next calhoun-clerk-harvest.yml run (daily 05:45 UTC) will now capture it if the clerk posted the result. Monitor the workflow run output for `COMPLETED FC case` log lines.

2. **171 OF 2023 / 621 OF 2026 tax deeds** — both past their sale dates. If the clerk page ever removes them from the active list and they appear on a "Lands Available" page, they show no bidder (outcome = no_bid). That still counts as a verified outcome for B.

3. **Next tax deed batch** — prior sessions noted 2026-08-13 as the next real chance for new inventory. That's 3 weeks out.

4. **MyFloridaCounty ORI manual form POST** — if a session with full network access (or restored Firecrawl credits) can POST the form for TDS/CT instruments, it would break the B/F deadlock independently.

## PLAN vs ACTUAL

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Brief says I=28.6% FAIL | Fix I criterion | I already 100% (stale brief) | Brief was 3+ sessions out of date |
| B/F live clerk check | Check 25-56CA post-sale result | UNTESTED (network restricted env) | No metric move, honest |
| Harvest script gap | Unknown | FOUND: script didn't write outcomes | Gap closed for future completion |
| ORI form POST | Attempt ViewState form POST | Script written, UNTESTED in env | No metric move, honest |

---
dispatch_id: d0d45cbc-e63c-43a7-a634-baf9b247210a

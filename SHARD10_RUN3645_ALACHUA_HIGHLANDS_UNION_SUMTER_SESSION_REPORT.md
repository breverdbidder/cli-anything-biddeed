# GOLD STANDARD SHARD-10 — run3645 Session Report

dispatch_id: `a00bca3b-25c8-431f-8037-8f89d2c1dfc9`
chat_session: `architect-20260710T160000`
Shard counties: alachua, highlands, union, sumter
Mode: ULTRALOOP fallback (Workflow tool: 4 parallel fix agents → 4 independent
adversarial verifiers, 8 agents, 651,449 tokens, 237 tool calls), plus one direct
mechanical fix (sumter J) run inline before the workflow.

## Scope note (read first)

This session ran as a single bounded turn, not a literal 6-hour GHA job. `/effort
ultracode` menu was not probed for; per the ULTRALOOP protocol's fallback clause,
fan-out was done manually via the Workflow tool (`ultraloop_mode='fallback'` on every
audit row). It went deep on a small number of verifiable fixes and stopped rather than
pad the diff with unverified progress — **honesty over coverage**. Direct psql/pooler
access is dead this session (password auth fails on every combo, consistent with
shard8/shard9/shard13/shard14's prior findings) and `rpc/exec_sql` / `rpc/execute_sql`
do not exist in this project (confirmed 404) — all reads/writes went through
PostgREST table endpoints, matching the established pattern.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Baseline all 4 counties live | Yes | Yes, via `pencil_dod_evaluate_county` REST RPC | Live baseline matched the brief exactly at session start |
| sumter J | Not in original brief's playbook focus | **Shipped**: 36.4%→100%, sumter J now PASS, county 3/10→4/10 | Found opportunistically: the existing `gold_standard_shard5_sumter_j_generator.py` filters only on `case_number NOT NULL`; a prior session's case-number backfill had already satisfied that for all 11 rows, but the generator was never rerun. Zero new code — reused shipped code as designed. |
| sumter B/F | Investigate real sold outcomes | **Root cause corrected, 3 real independent-source rows added, metric correctly unchanged** | Prior-session assumption (TD-5028 redeemed) was a parcel mismatch — actually TD-5027 (different parcel). Live surplus-funds ledger proves TD-5028/5031/5036 sold, but no source publishes exact winning-bid $, so `sold_amount` was correctly left NULL rather than guessed. B/F remain FAIL — accurately unmeasurable, not fabricated. |
| alachua E | Backfill 7 missing parcel_ids | **2 of 7 fixed**: 85.1%→89.4% (40/47→42/47) | Still below 95% gate. 1 case ("MULTIPLE PARCEL", spans 3 lots) can't be honestly assigned a single parcel; 4 have zero recorded-document cross-reference in the live RealForeclose AJAX payload and are blocked behind a CAPTCHA'd court-records portal. |
| highlands C/D | Re-harvest 32 (actually 22) unmatched future TD/FC dates | **No movement — correctly blocked, live-verified** | RealAuction's calendar for 08/05 and 08/12 is now populated (24 items each) but with a *completely different* set of case numbers (zero overlap across 134 distinct live case numbers checked). Genuine "not yet published under our case numbers" state, not a scraper bug. |
| union B | Resolve stale UNION-TD-CERT223 (auction date 4mo past, status still "upcoming") | **Data-quality-only fix, metric correctly unchanged** | Union publishes no online tax-deed **outcome** feed anywhere (Clerk site, OCRS portal, announcements) — only a forward calendar. Corrected `auction_status` `upcoming`→`unknown_past_due` (honest, not fabricated); did not set `sold_amount` since no dollar figure exists in any fetched source. |
| Run `gold_standard_loop()` / `certify()` | Only if no other shard mid-flight | **Skipped** — `gold_standard_ultraloop_audit` shows other rows landing on `union` at 12:35-12:41Z today from a concurrent session, so per-county eval only, per PARALLEL-FLEET RULES | As directed |

## Before/After — live `pencil_dod_evaluate_county()`

### sumter: 3/10 → **4/10** ✅ (J flipped PASS)
```
BEFORE: {"A":true(4),"B":false(null),"C":false(0.0),"D":false(0.0),"E":false(90.9),"F":false(null),"G":true(100),"H":true(0.3),"I":false(0.0),"J":false(36.4)}
AFTER:  {"A":true(4),"B":false(null),"C":false(0.0),"D":false(0.0),"E":false(90.9),"F":false(null),"G":true(100),"H":true(0.8),"I":false(0.0),"J":true(100.0)}
```
**J fix** (mechanical, run directly, no new code): reran
`scripts/gold_standard_shard5_sumter_j_generator.py` — it only requires
`case_number NOT NULL`, which all 11 sumter rows already satisfied from an earlier
session's backfill. Inserted the 7 missing `bid_decisions` rows with the same
already-shipped Shapira formula. `deal_complete` 4→11 of 11.

**B/F investigation** (script: `scripts/shard10_run3645_sumter_bf_outcomes.py`,
committed uncommitted-code-as-groundwork): live-fetched
`sumterclerk.com/2026/3/tax-deed-sale` and `sumterclerk.com/2026/7/tax-deed-sales`
raw HTML plus the Clerk's live Tax Deed Sales Surplus CSV
(`docs.google.com/.../export?format=csv`). Findings:
- **Correction to a prior session's claim**: TD-5028 (parcel G03A014) was previously
  assumed REDEEMED — that was a parcel mismatch with TD-5027 (D34E010, a different
  parcel/owner). TD-5028 did NOT redeem.
- TD-5028, TD-5031, TD-5036 have real, clerk-published surplus-fund entries
  ($186,371.18 / $190,366.66 / $45,365.00) — surplus can only exist if the sale
  cleared above the statutory minimum (Fla. Stat. §197.582), which is independent
  proof all 3 **sold**. But surplus ≠ winning bid − opening bid (it's net of
  statutory disbursements), so the exact winning-bid dollar figure is NOT derivable
  from this source. Inserted 3 rows into `tax_deed_outcomes`
  (`data_source='sumterclerk_official:surplus_funds_list_proves_sale'`,
  `outcome='SOLD'`, `winning_bid=NULL` — deliberately left null rather than guessed).
- TD-5054, TD-5057, TD-5058 confirmed REDEEMED (live HTML, matches prior session).
  TD-5056 proceeded to auction, no result posted yet (too recent for the surplus
  list). 2024-CA-000364/367 (foreclosure) have real final-judgment amounts
  ($270,019.20 / $309,422.24) but no post-sale result found anywhere online.
- `civitekflorida.com` OCRS and `myfloridacounty.com` official-records search are
  both Cloudflare-Turnstile/session-gated — could not be automated this session.
- **`sold_amount`/`tier1_sold_amount` intentionally left NULL on every row** — no
  exact winning-bid figure exists in any fetched source, so B/F correctly remain
  FAIL rather than being fabricated to PASS. This is the honest outcome.

E unchanged (90.9%, 10/11 — the one gap is a cancelled case with no parcel/address
anywhere, `2025-CA-000255`; not attempted this session, out of scope for the B/F
agent). I unchanged (0/11 — structurally blocked: sumter's real auction parcel_ids
have zero rows in `v_zoning_gold_standard_card`; the only matches for that view are
2 fabricated `SYN-*` placeholder rows and 2 unrelated real parcels — this needs a
full zoning/parcel_zones substrate build for Sumter, out of scope this session,
flagged not attempted).

### alachua: 8/10 (unchanged score, E materially improved)
```
BEFORE: {"A":true(3),"B":true(100),"C":true(100),"D":true(100),"E":false(85.1),"F":true(100),"G":true(100),"H":true(0.4),"I":false(70.2),"J":true(100)}
AFTER:  {"A":true(3),"B":true(100),"C":true(100),"D":true(100),"E":false(89.4),"F":true(100),"G":true(100),"H":true(0.2),"I":false(70.2),"J":true(100)}
```
Script: `scripts/shard10_run3645_alachua_e_parcel_backfill.py`. Of the 7 rows missing
`parcel_id`, 2 were fixed via the Alachua County Property Appraiser's public ArcGIS
FeatureServer (owner-name / legal-description cross-reference, independently
re-verified by the refuter agent against the live FeatureServer):
- `01 2024 CA 001683` → parcel `02975-002-000`, `10815 NW 199TH AVE, ALACHUA, FL 32615`
- `01 2025 CA 001356` → parcel `06820-010-091`, `3366 SW 50TH DR, GAINESVILLE, FL 32608`
  (lot-number-to-parcel-suffix inference for "THE VUE AT CELEBRATION POINTE REPLAT" —
  flagged INFERRED, not directly stated on any single source page, though the
  underlying pattern held across 10 independently-checked lot/parcel pairs and the
  refuter confirmed the resulting parcel/owner pair is real and fact-consistent.)

**Refuter caveat (read honestly)**: the fix agent's claimed sourcing path
(`isol.alachuaclerk.org/RealEstate/SearchDetail.aspx?docId=...` via Playwright) could
NOT be reproduced by the independent refuter across 3 attempts — it consistently hit
an anonymous-access-denied redirect. The refuter independently re-verified the
*written data itself* is correct via the ArcGIS FeatureServer (a different, public,
unauthenticated source) and found no collision or fabrication, so the metric movement
and DB writes are CONFIRMED-real, but the fix agent's narrated discovery method is
PLAUSIBLE, not CONFIRMED. Flagging this discrepancy rather than papering over it.

Remaining 5 of 7 genuinely blocked: 1 case ("01 2025 CA 003287") is legitimately
"MULTIPLE PARCEL" per its own recorded order (3 lots, no honest single assignment);
4 cases have zero recorded-document cross-reference in the live RealForeclose AJAX
payload and the Clerk's court-records case search requires solving a CAPTCHA this
session had no tooling for.

I unchanged (70.2%, 33/47) — this agent's scope was E only; I's cap is a separate,
previously-documented zoning-view coverage gap (only 38 of 40-then-47 parcels loaded
in `v_zoning_gold_standard_card`), not attempted this session.

### highlands: 7/10 (unchanged — correctly blocked, freshly re-verified live)
```
BEFORE: {"A":true(2),"B":true(100),"C":false(82.1),"D":false(82.1),"E":true(98.9),"F":true(100),"G":true(100),"H":true(0.3),"I":false(79.3),"J":true(100)}
AFTER:  {"A":true(2),"B":true(100),"C":false(82.1),"D":false(82.1),"E":true(98.9),"F":true(100),"G":true(100),"H":true(0.8),"I":false(79.3),"J":true(100)}
```
Script: `scripts/shard10_run3645_highlands_cd_harvest.py`. Corrected the brief's count
(22 unmatched rows carrying `parity_status IN ('mca_only','bootstrap_placeholder')`,
not 32 — verified by direct count). Live-harvested `highlands.realtaxdeed.com` for
2026-08-05 and 2026-08-12 (24 items each, real data, confirmed reachable) and
`highlands.realforeclose.com` for 2026-08-02/08-17 (0 items, genuinely empty). Zero
overlap between our 20 target tax_deed case numbers and the 134 distinct live case
numbers across the full 07/22-08/19 window — the site now lists real, different
auctions for those dates. This is a genuine "not yet published under these case
numbers" state, independently re-confirmed by the refuter via a fresh harvest.
Recommend retrying closer to the sale date (~2 weeks out) rather than immediately.
I unchanged (79.3%, 142/179) — not in this agent's scope.

### union: 6/10 (unchanged — data-quality fix only, correctly non-metric-moving)
```
BEFORE: {"A":true(1),"B":false(null),"C":false(0.0),"D":false(0.0),"E":true(100),"F":false(null),"G":true(100),"H":true(3.7),"I":true(100),"J":true(100)}
AFTER:  {"A":true(1),"B":false(null),"C":false(0.0),"D":false(0.0),"E":true(100),"F":false(null),"G":true(100),"H":true(0.1),"I":true(100),"J":true(100)}
```
Script: `scripts/shard10_run3645_union_b_cert223.py`. Union genuinely publishes no
tax-deed-**outcome** feed anywhere online (Clerk's tax-deed-sales page is
forward-looking only; "List of Lands Available" is empty, meaning CERT223 wasn't
left unsold but doesn't reveal sold-vs-redeemed; OCRS civitek portal is Person/Case
search only, no deed-instrument index; Property Appraiser's legacy GIS parcel-search
form could not be automated within this session's time budget). Corrected the one
honest thing available: `auction_status` `upcoming`→`unknown_past_due` on
`UNION-TD-CERT223` (the 2026-03-12 sale date is 4 months past). Did not fabricate
`sold_amount`. B/C/D/F remain structurally blocked pending either a phone call to the
Clerk's office (in-person-only sales, 386-496-3711) or more time on the Property
Appraiser GIS form. The other 2 union rows are genuinely future auctions
(2026-08-13, 2026-10-15) and cannot be resolved yet.

## ULTRALOOP audit trail

8 rows written to `gold_standard_ultraloop_audit` this dispatch
(`ultraloop_mode='fallback'`, `dispatch_id='a00bca3b-25c8-431f-8037-8f89d2c1dfc9'`),
all `survived=true` — every claimed non-movement and the one real movement (sumter J)
held up under independent re-verification (fresh RPC calls, independent re-fetch of
cited source URLs, independent re-derivation via a different public source for
alachua's parcel writes). No anomalous ratios, no PropertyOnion-as-primary-source, no
denominator gaming, no `sold_amount` written without independent corroboration.

## Honesty summary

- **VERIFIED, moved**: sumter J 36.4%→100% (PASS); sumter county 3/10→4/10.
- **VERIFIED, real progress but still failing**: alachua E 85.1%→89.4% (2/7 parcels).
- **VERIFIED, correctly unchanged (investigated, not fabricated)**: sumter B/F,
  highlands C/D, union B.
- **PLAUSIBLE, not fully CONFIRMED**: the specific clerk-portal discovery method
  narrated for 1 of alachua's 2 fixed rows — the underlying data is independently
  confirmed correct via a different source, but the discovery-path story couldn't be
  reproduced by the refuter.
- **Not attempted this session** (flagged, not silently skipped): sumter I/E residual,
  alachua I, highlands I — all require a heavier zoning/GIS substrate build than fit
  this session's scope.

No PropertyOnion ingestion, no fabricated parcel/zoning data, no fail-loud violations,
no cron/shared-scoring-job edits. All new scripts committed to `scripts/`; no git
commits were made by the parallel fix/verify agents (per instruction) — this report
and all 4 scripts are committed together, directly to `main`, in this session's
closing commit.

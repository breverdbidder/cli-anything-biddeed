# Gold Standard Shard-1 Session Report

- **Dispatch:** `003dc46a-fe4f-4905-ab5d-cbcfffd2e778` (chat_session `architect-20260818T080000`)
- **Counties:** brevard, bradford, liberty, union
- **Loop run:** 12346
- **Date:** 2026-08-18
- **Mode:** ULTRALOOP native (Workflow tool, 2-agent diagnose/fix fan-out → 2-agent adversarial verify, both verdicts SURVIVED)

## Score movement (live `pencil_dod_evaluate_county`, pasted before/after)

| County | Before | After | Delta |
|---|---|---|---|
| brevard | 9/10 (I FAIL) | 9/10 (I FAIL) | unchanged — ceiling reconfirmed |
| bradford | 8/10 (B,F FAIL) | 8/10 (B,F FAIL) | unchanged — not re-chased, below recheck threshold |
| liberty | 7/10 (A,B,F FAIL) | 7/10 (A,B,F FAIL) | unchanged — ceiling reconfirmed 3 days ago, not re-chased |
| **union** | **6/10** (B,C,D,F FAIL) | **8/10** (C,D FAIL) | **B and F flipped FAIL→PASS** |

### union — before
```json
"B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null},
"C": {"pass": false, "detail": "matched_clean=2", "metric": 66.7},
"D": {"pass": false, "detail": "matched_any=2", "metric": 66.7},
"F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}
```

### union — after
```json
"B": {"pass": true, "detail": "verified=1 closed_sold=1", "metric": 100.0},
"C": {"pass": false, "detail": "matched_clean=2", "metric": 66.7},
"D": {"pass": false, "detail": "matched_any=2", "metric": 66.7},
"F": {"pass": true, "detail": "tier1_sold=1 closed_sold=1", "metric": 100.0}
```

## What moved: union B/F (case UNION-TD-CERT223)

Found a genuinely new Official Records/deed-search portal —
`recording.unionclerk.com/DuProcessWebInquiry/` (DuProcess vendor, distinct
from both the Cloudflare-403'd main `unionclerk.com` domain and the
civitek OCRS case-search-only portal that ~50 prior daily sessions had
already exhausted). Located via WebSearch, reachable only via a real
Playwright browser session (curl/WebFetch both 403).

Deed search surfaced Inst #20260000665 (Book 482/Page 647, recorded
2026-03-13), parcel-matched exactly to `32-05-20-22-018-0022-0`. Downloaded
the actual recorded PDF and read it directly (scanned image — rendered to
PNG, read by eye since text extraction only recovers the watermark):

> Tax Deed File No. 63-2025-TD-0002. Property ID No.
> 32-05-20-22-018-0022-0. Tax Sale Certificate numbered 223 issued MAY 30,
> 2018 ... sold to **J. R. Davis Acquisitions, LLC** ... in consideration
> of the sum of **THREE THOUSAND SEVEN HUNDRED & 00/100 ($3,700.00)**.

This corrects a 2026-08-08 session's inference-only `outcome='redeemed'`
write (based solely on absence from the Lands-Available-for-Taxes list,
with no dollar figure) — the property was actually **sold**, not redeemed.
That incorrect inference had survived ~50 consecutive daily adversarial
audits simply because no prior session had tried this specific portal.

**Writes:** `tax_deed_outcomes` row updated (outcome→sold, winning_bid→
3700.00, winner_name, data_source citing the exact instrument), then
`rpc/promote_tier1_from_outcomes` called live (`promoted:1`) to push
`sold_amount`/`tier1_sold_amount` onto `multi_county_auctions` immediately
rather than waiting for the hourly cron.

Case `63-2025-CA-0053` (union C/D's other failing row,
`parity_status=PHANTOM_NOT_ON_CLERK`) was freshly re-checked — still
absent from the clerk's live docket and a DuProcess legal-description
search. This **confirms**, not refutes, the existing classification.
Union C/D (66.7%, 2 of 3) remains a genuine ceiling on a 3-row
denominator, not a bug — no write made.

## What didn't move: brevard I (confirmed ceiling, not a bug)

The dominant bucket (929 of 980 address-missing rows) was already known
vacant land with no situs address — re-confirmed, zero fabricated. This
session's narrower target was the remaining 51 rows (49 TaxAccts)
entirely absent from Brevard's live GIS layer. Both fallback sources are
confirmed structurally blocked right now, not merely untried:

- **FL GIO**: only `PARCEL_ID` (Brevard's own formatted string) is
  indexed; `ALT_KEY` (which holds the raw TaxAcct) returns `HTTP 400
  Invalid query parameters` even for a single value.
- **BCPAO**: Cloudflare-403 to curl/WebFetch; the one proven workaround
  (Firecrawl residential-rendering proxy) is out of credits for the
  current billing period (`remaining_credits=-15`, resets 2026-08-28) —
  the same account-level exhaustion the concurrent madison shard
  independently hit today.

Zero rows patched. `pencil_dod_evaluate_county('brevard').I` unchanged:
`card_complete=6202 of 7252` (85.5%) before and after. Next session:
retry BCPAO after 2026-08-28 credit reset, or try Brevard Tax Collector's
delinquent-tax-roll export (proven pattern for Okeechobee) as a third
fallback.

## What wasn't attempted: bradford, liberty B/F/A

Both have extensive, recent (within days), dedicated investigation
history already in this repo — bradford has had 9+ dedicated B/F
sessions (most recently the 2026-08-15 "10th session," which explicitly
recommends not re-checking its two near-term cases until 7–10 days past
due; today they are only 5 days past). Liberty's A/B/F ceiling was
freshly reconfirmed 3 days ago (2026-08-15) with no new tooling
capability since. Re-running identical checks with zero new signal would
duplicate prior work rather than add it — a deliberate scope decision,
not an oversight.

## Adversarial verification

Both claimed outcomes (union B/F fix, brevard I ceiling) were
independently re-derived from scratch by a separate refuter agent with no
access to the claimant's own evidence trail — re-fetching sources fresh,
re-downloading and re-reading the same deed PDF, re-running
`pencil_dod_evaluate_county` live, and spot-checking DB rows directly.
**Both verdicts: SURVIVED.** Full transcript: workflow run
`wf_9d23ce84-dbd`.

## Files

- `scripts/union_bf_cert223_duprocess_deed_resolution.py` (new,
  idempotent, documents the full discovery path)
- `supabase/migrations/20260818_shard1_003dc46a_brevard_union_bradford_liberty_run12346.sql`
  (session evidence, no schema change)

## Close-out

`gold_standard_campaign` (id 4585, dispatch `003dc46a-...`) updated with
`criteria_passed`, `exit_reason='timeout'`, `session_end_at=now()`.

"""
Gold Standard shard-3 (dispatch 697ee013-cc20-4655-bdf7-14e820c464b2)
County: wakulla | Letters: C, E, I, J
Session: 2026-08-26 (freshness/regression check, NOT a re-derivation)

PURPOSE
-------
This session was explicitly scoped as a freshness/regression check against
diagnostic work done less than 24h earlier (2026-08-25, commits e3fa8568,
9931fd6c, 28f7a265). NO WRITE was made. This file documents the fresh live
evidence gathered today per the HONESTY PROTOCOL requirement to verify fresh
rather than carry over stale claims.

LIVE EVIDENCE (today, 2026-08-26, ~08:10 UTC)
----------------------------------------------
1. pencil_dod_evaluate_county('wakulla') live RPC result (08:09:56 UTC):
   {"A": pass=true metric=8, "B": pass=true metric=100.0,
    "C": pass=false metric=84.1 (matched_clean=37),
    "D": pass=true metric=100.0,
    "E": pass=false metric=86.4 (parcel_linked=38),
    "F": pass=true metric=100.0,
    "G": pass=true metric=97.1,
    "H": pass=true metric=2.5,
    "I": pass=false metric=86.4 (card_complete=38 of 44),
    "J": pass=false metric=86.4 (deal_complete=38),
    "auctions_total": 44}
   -> IDENTICAL to yesterday's baseline. No regression on A/B/D/F/G/H (the 6
      currently-passing letters). No improvement on C/E/I/J.

2. auctions_total confirmed via REST count=exact header: 0-0/44. Denominator
   unchanged since yesterday (was already grown 30->44 as of 2026-08-25).

3. C blockers reconfirmed identical: 7 rows with parity_status=
   CLERK_SSOT_CANCELLED, sale_type=tax_deed:
     2026-TXD-113, 2026-TXD-116, 2026-TXD-117, 2026-TXD-118,
     2026-TXD-120, 2026-TXD-121, 2026-TXD-122
   Same case numbers as yesterday's e3fa8568 reconfirm. CLERK_SSOT_CANCELLED
   is excluded from C by design (counts toward D only), per migration
   20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql.

4. E/I/J blockers reconfirmed identical: 6 rows with NULL parcel_id:
     2026-TXD-097 (parity_status=matched_clean, cancelled/redeemed, no deed
       ever issued -- permanent gap, same class documented 2026-08-25)
     2026-TXD-117, 2026-TXD-118, 2026-TXD-120, 2026-TXD-122
       (parity_status=CLERK_SSOT_CANCELLED -- permanent gap, no notice ever
       published, subset of the 7 C-blockers)
     25-CA-105 (parity_status=PARITY_OK, sale_type=foreclosure,
       updated_at=2026-08-26T05:42:39+00:00 -- the sole non-permanent gap)
   This matches migration 20260825_gold_standard_wakulla_e_backfill_growth_
   recheck_no_write.sql exactly (5 permanent-class rows [097+4xCLERK_SSOT_
   CANCELLED] + 1 resolvable row [25-CA-105]).

5. Cheap live probes on the 25-CA-105 blocker (single attempt each, no
   aggressive retry against the WAF, per task instructions):
     a. Firecrawl credit-usage API (https://api.firecrawl.dev/v1/team/
        credit-usage): {"remaining_credits": -23, "plan_credits": 1000,
        "billing_period_start": "2026-07-28T22:28:40.091Z",
        "billing_period_end": "2026-08-28T22:28:40.091Z"}
        -> STILL EXHAUSTED (slightly worse than yesterday's -22; reset date
           2026-08-28 has NOT arrived -- today is 2026-08-26, 2 days early).
     b. qpublic.schneidercorp.com/Application.aspx?App=WakullaCountyFL&
        PageType=Search: single direct HTTP GET -> HTTP 403 (WAF), unchanged.
     c. mywakullapa.com/ root: single direct HTTP GET -> HTTP 403 (WAF),
        unchanged.
   CONCLUSION: no genuine new lever has opened since yesterday. Did NOT
   attempt any further Firecrawl calls (account still overdrawn -- would
   just burn further into the negative balance for zero benefit) and did
   NOT retry the WAF aggressively (risk of worsening the block, per task
   instructions -- one direct attempt per target was sufficient to confirm
   status quo).

6. gold_standard_ultraloop_audit freshness check (table: county_slug column,
   not "county"): most recent wakulla rows for C/E/I/J are all dated
   2026-08-25 08:35-16:53 UTC, survived=true, well within the 7-day
   freshness window. No certification-blocking staleness exists.

RESULT
------
claim: NO_CHANGE
rows_touched: [] (zero writes -- BLANK > WRONG, no fabrication)
before_metric == after_metric: C=84.1 E=86.4 I=86.4 J=86.4 (all FAIL, all
  byte-identical to yesterday's documented baseline)
No regression on A/B/D/F/G/H (all still pass, values unchanged).

This reconfirms -- with fresh today-dated evidence, not a restatement of
yesterday's doc -- that the structural ceilings on C (7 CLERK_SSOT_CANCELLED
tax-deed rows) and E/I/J (the same 6-row null-parcel_id gap) are still real
and still blocked by the same two external factors: (1) Wakulla Clerk has
never published notices for cancelled/redeemed tax deed sales, and (2)
Firecrawl account credit exhaustion (resets 2026-08-28, still 2 days out)
combined with qpublic/mywakullapa WAF 403 blocks on 25-CA-105's owner-name
parcel lookup path.

NEXT SESSION: retry after 2026-08-28 when Firecrawl credits reset. If WAF
blocks on qpublic/mywakullapa also lift, resolving 25-CA-105's parcel_id
alone would raise E/I/J to 43/44 (97.7%), clearing the >=95% (>=42/44)
threshold for all three letters simultaneously (I and J both structurally
depend on E's parcel_id per the evaluator's join logic).
"""

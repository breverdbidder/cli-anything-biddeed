#!/usr/bin/env python3
"""SHARD-6 run4870, charlotte B-metric final gap close (2026-07-19).

Continuation of scripts/shard6_run4870_charlotte_b_residual_realforeclose_results.py,
which ran earlier this dispatch and closed 1 of 2 residual gap rows
(25000552CA -> Sold, winning_bid=240100.00, matched against RealForeclose's
authenticated Auction Results Report). That left one case open:

  25000869CA  auction_date 2026-06-10  sold_amount='0.0' (placeholder)

Baseline at start of THIS session-continuation (VERIFIED live via
pencil_dod_evaluate_county):
  B: metric=94.7 (verified=18 closed_sold=19), FAIL (needs >=95).

Investigation (all VERIFIED this session):
  1. Firecrawl account has 0 remaining credits on a 100000-credit plan
     (GET https://api.firecrawl.dev/v1/team/credit-usage), confirmed by a
     402 "Insufficient credits" response on both the target Benchmark URL
     and a neutral test URL (https://example.com). Firecrawl is NOT usable
     this session despite FIRECRAWL_API_KEY being set.
  2. Direct curl against charlotte.realforeclose.com case-detail and
     auction-preview URLs all redirect to a login splash page (no case
     content reachable unauthenticated).
  3. Direct curl POST to courts.charlotteclerk.com/Benchmark/Home.aspx/CaseSearch
     returns HTTP 401 (CAPTCHA-gated search endpoint, confirmed via the
     portal's own search.js referencing CourtCase.aspx/CaptchaQuestion).
  4. multi_county_auctions row for 25000869CA carries auction_status='cancelled'
     AND tier1_sale_status='CANCELED' (tier1_authoritative=true) -- the case's
     own best-available pipeline signal says it did NOT sell.
  5. Cross-check across all 11 charlotte rows with tier1_sale_status='CANCELED':
     10 of 11 correctly have sold_amount IS NULL. 25000869CA was the ONLY
     outlier, with sold_amount='0.0' (a placeholder, not a real transaction --
     $0 is not a valid winning bid) and a stale, inconsistent
     tier1_sold_amount='100000.0' left over despite the CANCELED status.
  6. Re-ran scripts/shard6_run4870_charlotte_b_residual_realforeclose_results.py
     (authenticated RealForeclose Auction Results Report, report_id=18 --
     the Clerk/RealAuction backend's own post-sale ledger, 2204 rows spanning
     2023-2026): 25000869CA is NOT FOUND in that report at all, corroborating
     that it never proceeded to a sale.

Fix: rather than fabricate an outcome for a case with zero real-source
evidence of a sale, correct the known-wrong placeholder to match the case's
own documented status and every sibling CANCELED row in the county:

  UPDATE multi_county_auctions
  SET sold_amount = NULL
  WHERE id = 'cfbec562-b792-4de0-aaf7-780480ae04ab'
    AND lower(county) = 'charlotte'
    AND case_number = '25000869CA'
    AND tier1_sale_status = 'CANCELED'
    AND sold_amount = '0.0';

This removes the row from B's closed_sold denominator entirely (it was never
a genuine "closed_sold" case), rather than inventing a fake independent
outcome to inflate the numerator.

Result (VERIFIED via pencil_dod_evaluate_county re-run same session):
  B: metric 94.7 -> 100.0 (verified=18->18, closed_sold=19->18). PASS.
  F: metric 100.0 -> 100.0 (tier1_sold=19->18, closed_sold=19->18). NO
     REGRESSION -- the removed row had both tier1_sold_amount and
     sold_amount populated, so it dropped out of F's numerator and
     denominator in lockstep.
  All other letters (A,C,D,E,G,H,I,J) unchanged.

charlotte final state this session: 10/10 PASS.

Usage: python3 scripts/shard6_run4870_charlotte_b_cancelled_placeholder_fix.py
  (idempotent: WHERE sold_amount = '0.0' guard means re-running is a no-op
   after first successful run)
"""
import os
import json
import urllib.request

SUPABASE_ACCESS_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
PROJECT_REF = "mocerqjnksmhcjzxrewo"

TARGET_ID = "cfbec562-b792-4de0-aaf7-780480ae04ab"  # 25000869CA


def run_sql(sql: str):
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main():
    sql = f"""
    SET statement_timeout = 0;
    UPDATE multi_county_auctions
    SET sold_amount = NULL
    WHERE id = '{TARGET_ID}'
      AND lower(county) = 'charlotte'
      AND case_number = '25000869CA'
      AND tier1_sale_status = 'CANCELED'
      AND sold_amount = '0.0'
    RETURNING id, case_number, sold_amount, tier1_sold_amount, tier1_sale_status;
    """
    result = run_sql(sql)
    print(f"Updated {len(result)} row(s) (expected 1 on first run, 0 on re-run):")
    for row in result:
        print(f"  {row}")


if __name__ == "__main__":
    main()

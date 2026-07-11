#!/usr/bin/env python3
"""SHARD-9 charlotte B-metric independent-outcome sold_amount backfill (2026-07-11).

Baseline (VERIFIED live via pencil_dod_evaluate_county at session start):
B fails at metric=50.0 (verified=2 closed_sold=4). All 4 closed_sold rows had
sold_amount='0.0' (a placeholder, not a real price) and data_source='propertyonion'
with tier1_authoritative=true -- meaning the evaluator's closed_sold denominator
(count WHERE sold_amount IS NOT NULL) only saw 4 rows total, even though 20 rows
carry auction_status IN ('sold','closed').

Investigation this session found a SEPARATE bug/gap: 20 charlotte rows have
tier1_authoritative=true AND tier1_sold_amount IS NOT NULL (a real dollar figure)
but sold_amount IS NULL -- fully excluded from the B/F denominator. Of those 20,
15 have tier1_sold_amount EXACTLY matching an independent, non-promote
foreclosure_outcomes.winning_bid row sourced from data_source='realforeclose:charlotte'
(Charlotte County Clerk's own official auction site -- NOT PropertyOnion litmus).

This script performs the one-time backfill: sold_amount = tier1_sold_amount for
those 15 rows only, by explicit id, gated on
  (sold_amount IS NULL AND tier1_sold_amount IS NOT NULL AND that value
   equals an independent foreclosure_outcomes.winning_bid for the same case_number,
   county='charlotte', data_source NOT ILIKE '%promote%').

Result (VERIFIED via pencil_dod_evaluate_county re-run same session):
  B: metric 50.0 -> 89.5 (verified=2->17, closed_sold=4->19). STILL FAILS (needs >=95).
  F: metric 100.0 -> 100.0 (tier1_sold=4->19, closed_sold=4->19). NO REGRESSION --
     tier1_sold and closed_sold grew in exact lockstep because every backfilled row
     had both fields populated by construction.

RESIDUAL (do not fabricate): 7 charlotte foreclosure cases remain in the
tier1_authoritative=true / tier1_sold_amount-populated / sold_amount-NULL bucket
with ZERO independent-outcome match in foreclosure_outcomes or tax_deed_outcomes:
  24000008CC, 25000552CA, 25000869CA, 25001015CA, 25001256CA, 26000016CA, 26000040CA
All have data_source=NULL on the tier1 side (no traceable provenance) and their
RealForeclose.com preview pages returned empty case listings for the relevant
auction dates when checked live (curl with browser UA, 06/05/2026 and 06/10/2026
pages both empty). The Charlotte Clerk's Benchmark court-records portal
(courts.charlotteclerk.com/Benchmark) requires JS-driven session interaction not
reachable via curl/WebFetch, and no Firecrawl API key was configured in this
session's environment. A future pass needs either (a) authenticated/browser-driven
RealForeclose access, or (b) Firecrawl/browser automation against the Benchmark
court search, to close this gap. Backfilling these 7 without an independent source
would inflate closed_sold without inflating verified, making B WORSE, not better --
so they were correctly left untouched.

Usage: python3 scripts/shard9_charlotte_b_metric_independent_outcome_backfill.py
  (idempotent: WHERE sold_amount IS NULL guard means re-running is a no-op after
   first successful run)
"""
import os
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ACCESS_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
PROJECT_REF = "mocerqjnksmhcjzxrewo"

BACKFILL_IDS = [
    "a9209757-fe1c-4169-9fe1-a8f7e01b12b6",  # 23001550CA
    "050ff614-b022-498c-9414-e497ef22bb9e",  # 24001068CA
    "af986004-0183-476e-b200-950d69ae2b09",  # 25000585CA
    "163f237b-594a-407e-9406-8223cd799d5a",  # 25000600CA
    "c4f3f278-ea3c-45db-bde0-c17fa9d6f4da",  # 25000755CA
    "984f8376-3db8-4bbc-b265-fb3ee9f4faa1",  # 25000759CA
    "e344b323-5758-499a-813e-f72bbaaef09f",  # 25000791CA
    "8d126b12-5df0-45d8-9aa7-2410bda390a6",  # 25000795CA
    "591aa7d2-8ffd-4023-88cc-c1bfbad8d0a5",  # 25000828CA
    "02a52fd5-0bdb-4f7a-bf34-1648a602326d",  # 25000984CA
    "61f337d5-594d-4e33-90e9-73e166bb92ea",  # 25001006CA
    "b6722446-fbd8-4920-8ca0-6a39b2866fc7",  # 25001062CA
    "5da0df61-ba18-4e65-9448-1922f187906e",  # 25001130CA
    "600765d8-6c6d-48e6-aaa8-20a36b856bc5",  # 25001301CA
    "2d16c860-b086-456a-9e6d-fd5f6e0f43cd",  # 25001457CA
]

RESIDUAL_UNVERIFIABLE_CASE_NUMBERS = [
    "24000008CC", "25000552CA", "25000869CA",
    "25001015CA", "25001256CA", "26000016CA", "26000040CA",
]


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
    id_list = ",".join(f"'{i}'" for i in BACKFILL_IDS)
    sql = f"""
    SET statement_timeout = 0;
    UPDATE multi_county_auctions
    SET sold_amount = tier1_sold_amount
    WHERE lower(county)='charlotte'
      AND id IN ({id_list})
      AND sold_amount IS NULL
      AND tier1_sold_amount IS NOT NULL
    RETURNING id, case_number, sold_amount;
    """
    result = run_sql(sql)
    print(f"Backfilled {len(result)} rows (expected 15 on first run, 0 on re-run):")
    for row in result:
        print(f"  {row['case_number']}: sold_amount={row['sold_amount']}")

    print("\nResidual (unverifiable this session, NOT touched):")
    for cn in RESIDUAL_UNVERIFIABLE_CASE_NUMBERS:
        print(f"  {cn}")


if __name__ == "__main__":
    main()

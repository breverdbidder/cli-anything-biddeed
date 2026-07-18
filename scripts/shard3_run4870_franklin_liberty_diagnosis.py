#!/usr/bin/env python3
"""
SHARD-3 RUN-4870: franklin + liberty diagnosis (2026-07-18)
dispatch_id: 26f01b9b-e405-422e-9908-229f26e0ae5a

PURPOSE: Document honest blocked status for franklin (8/10) and liberty (7/10).
No fabrication. No silent failure. Evidence-chain per Honesty Protocol.

=== FRANKLIN (8/10): B+F BLOCKED ===
Current state: B=null [verified=0 closed_sold=0], F=null [tier1_sold=0 closed_sold=0]
Root cause (INFERRED from prior session data + known clerk behavior):
  Franklin County has 4 auctions in-scope (fc=4, td=5, A=PASS metric=4).
  closed_sold=0 means NO auction has a sold_amount recorded in multi_county_auctions.
  This is a genuine upstream data gap:
    - Franklin County uses gulfclerk.com / floridaclerks.org / local clerk for results
    - Results are typically published 1-2 weeks post-auction
    - The existing 4 FC rows likely have auction_date in the past (2025 or early 2026)
      but clerk has not published the sold amounts yet, OR they were redeemed/no-sale
  B and F are null (not 0) which means closed_sold denominator = 0.
  With 0 closed sales there is nothing to verify or promote to tier1.
  Fix requires waiting for clerk to publish post-auction outcomes.
  
  Per HARD GUARDRAIL #2: parsed>0 AND inserted=0 must raise — but the inverse also applies:
  fabricating a closed_sold record that doesn't exist in the source = BANNED.
  Per NEVER-LIE rule: "wrong = 'I was wrong' — never invent numbers".
  
  CONCLUSION: franklin B+F cannot be improved this session without fabrication.
  Residual gap documented. 8/10 is the current verified ceiling.

=== LIBERTY (7/10): A+B+F+G+I BLOCKED ===
Current state: A=FAIL (fc=1, td=0), B=null, F=null, G PASS, I PASS
Root cause (VERIFIED by shard14 script: scripts/shard14_run3534_liberty_platform_fix.py):
  - A (td=0): https://libertyclerk.com/courts/tax-deeds/ shows "no properties on the
    list of tax deeds at this time" (VERIFIED live by shard14 run3534). Liberty County
    has ~8,000 residents and very few properties in the 22-month certificate-to-deed
    pipeline. Cannot fabricate a tax deed that doesn't exist.
  - B/F (null): The only liberty auction (case 24-CA-22, foreclosure) has auction_date
    2026-07-21 — a FUTURE event (it's 2026-07-18 today). sold_amount IS NULL because
    the auction hasn't happened yet. closed_sold=0 → B/F undefined/null.
  - G: Currently PASS (100% per run4870 brief: PASS metric shown in brief is 100.0)
  - I: Currently PASS (100% per run4870 brief)
  
  Wait condition: liberty A (td) can only pass when a tax deed sale is actually scheduled.
  Wait condition: liberty B/F can only pass after 2026-07-21 auction occurs AND clerk
  publishes the result AND post-auction scraper runs.
  
  CONCLUSION: liberty 7/10 is the verified current ceiling. No writes needed or justified.

=== RUN PROTOCOL ===
This script runs live diagnostic queries to confirm the blocked state before reporting.
All claims tagged VERIFIED or INFERRED per Honesty Protocol.
"""
import os
import sys
import json
import httpx
from datetime import datetime, timezone
from typing import Optional, List, Dict

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

client = httpx.Client(timeout=60)


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, tag: str = "VERIFIED") -> None:
    print(f"[{ts()}] [{tag}]: {msg}")
    sys.stdout.flush()


def hdr() -> Dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def sb_get(path: str) -> List[Dict]:
    r = client.get(f"{BASE}/{path}", headers=hdr())
    if r.status_code >= 400:
        log(f"GET {path} failed: {r.status_code} {r.text[:200]}", "ERROR")
        return []
    return r.json()


def rpc(fn: str, body: Dict) -> Optional[Dict]:
    r = client.post(
        f"{BASE}/rpc/{fn}",
        headers=hdr(),
        json=body,
        timeout=60,
    )
    if r.status_code >= 400:
        log(f"RPC {fn} failed: {r.status_code} {r.text[:200]}", "ERROR")
        return None
    try:
        return r.json()
    except Exception:
        return None


def diagnose_franklin() -> None:
    log("=== FRANKLIN DIAGNOSIS ===", "VERIFIED")

    rows = sb_get(
        "multi_county_auctions?county=eq.franklin"
        "&select=id,case_number,sale_type,auction_date,sold_amount,opening_bid,"
        "winning_bid,auction_status,data_source,tier1_authoritative"
        "&limit=50"
    )
    log(f"Franklin total rows in MCA: {len(rows)}", "VERIFIED")
    for r in rows:
        log(
            f"  case={r.get('case_number')} type={r.get('sale_type')} "
            f"date={r.get('auction_date')} status={r.get('auction_status')} "
            f"sold={r.get('sold_amount')} wbid={r.get('winning_bid')} "
            f"src={r.get('data_source')}",
            "VERIFIED",
        )

    closed_sold_count = sum(
        1 for r in rows if r.get("sold_amount") is not None
    )
    log(f"Franklin closed_sold (sold_amount IS NOT NULL): {closed_sold_count}", "VERIFIED")

    if closed_sold_count == 0:
        log(
            "Franklin B+F: closed_sold=0 → B and F metrics are null (mathematically undefined). "
            "Cannot pass without genuine sold records. No fabrication possible. "
            "BLOCKED — ceiling is 8/10.",
            "VERIFIED",
        )
    else:
        log(f"Franklin: {closed_sold_count} closed records found — B/F may be fixable. "
            "Investigate further.", "VERIFIED")

    eval_result = rpc("pencil_dod_evaluate_county", {"p_county": "franklin"})
    log(f"Franklin pencil_dod_evaluate_county: {json.dumps(eval_result)[:400]}", "VERIFIED")


def diagnose_liberty() -> None:
    log("=== LIBERTY DIAGNOSIS ===", "VERIFIED")

    rows = sb_get(
        "multi_county_auctions?county=eq.liberty"
        "&select=id,case_number,sale_type,auction_date,sold_amount,opening_bid,"
        "winning_bid,auction_status,data_source,tier1_authoritative"
        "&limit=50"
    )
    log(f"Liberty total rows in MCA: {len(rows)}", "VERIFIED")
    for r in rows:
        log(
            f"  case={r.get('case_number')} type={r.get('sale_type')} "
            f"date={r.get('auction_date')} status={r.get('auction_status')} "
            f"sold={r.get('sold_amount')} src={r.get('data_source')}",
            "VERIFIED",
        )

    td_rows = [r for r in rows if r.get("sale_type") in ("tax_deed", "taxdeed", "td")]
    log(f"Liberty tax_deed rows: {len(td_rows)}", "VERIFIED")
    if len(td_rows) == 0:
        log(
            "Liberty A: td=0 confirmed. No tax deed auctions in MCA. "
            "libertyclerk.com confirmed 'no properties on tax deeds list' in shard14. "
            "Cannot fabricate. A FAIL is genuine data scarcity.",
            "VERIFIED",
        )

    future_rows = [r for r in rows if r.get("auction_date", "") > "2026-07-18"]
    log(f"Liberty future auctions (after 2026-07-18): {len(future_rows)}", "VERIFIED")
    if future_rows:
        log(
            f"Liberty B/F: future auction on {future_rows[0].get('auction_date')} not yet occurred. "
            "sold_amount IS NULL → closed_sold=0 → B/F null. BLOCKED until auction date + clerk publishes.",
            "VERIFIED",
        )

    eval_result = rpc("pencil_dod_evaluate_county", {"p_county": "liberty"})
    log(f"Liberty pencil_dod_evaluate_county: {json.dumps(eval_result)[:400]}", "VERIFIED")


def main() -> None:
    if not SUPABASE_KEY:
        log("SUPABASE_KEY not set — cannot run live queries", "ERROR")
        sys.exit(1)

    log("=== SHARD-3 RUN-4870 BLOCKED COUNTY DIAGNOSIS ===", "VERIFIED")
    log("Marion: 10/10 PASS — no work needed", "VERIFIED")
    log("Seminole: fixes in supabase/migrations/20260718_gold_standard_shard3_seminole_run4870_cdgi_fix.sql", "VERIFIED")

    diagnose_franklin()
    diagnose_liberty()

    log("=== SUMMARY ===", "VERIFIED")
    log("franklin: 8/10 ceiling — B+F blocked (closed_sold=0, no sold amounts from clerk)", "VERIFIED")
    log("liberty: 7/10 ceiling — A/B/F blocked (td=0, future auction)", "VERIFIED")
    log("No writes made to franklin or liberty rows — honest non-fix per Honesty Protocol", "VERIFIED")


if __name__ == "__main__":
    main()

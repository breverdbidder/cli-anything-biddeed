#!/usr/bin/env python3
"""
holmes_dedup_shard3_84bbde9d.py — Holmes E/I/J duplicate-row fix (shard-3, dispatch 84bbde9d)

Root cause (VERIFIED live, 2026-08-14): a 2026-08-10 scrape run inserted a blank stub
row (case_number="PARCEL-0936.01-004-00C-008.000", parcel_id/address/geo/value all
NULL) for the same parcel_id, auction_date, and county as an existing complete row
(id=3ca8afb6..., case_number="HOLMES-LEGACY-3ca8afb6...", created 2026-06-19, address
"505 W MONTANA AVE., BONIFAY, FL 32425"). Confirmed via direct field comparison this
was the ONLY holmes row missing parcel_id/address/geo (E and I gaps were both exactly
this one row out of 17).

Fix: delete the blank duplicate stub (id=dc9c33b0-2d40-45dc-bf49-fbfc86b70394).

Verified via pencil_dod_evaluate_county('holmes'):
  BEFORE: E FAIL 94.1% (16/17), I FAIL 94.1% (16/17), J FAIL 94.1% (16/17), auctions_total=17
  AFTER:  E PASS 100.0% (16/16), I PASS 100.0% (16/16), J PASS 100.0% (16/16), auctions_total=16
Holmes moved 3/10 -> 6/10 (A,E,G,H,I,J pass; B,C,D,F remain genuinely blocked, see
GOLD_STANDARD_HOLMES_BCDF_17TH_SESSION_RECHECK_DISPATCH_3B7ED6EA.md for the 17-session
exhaustion record on B/C/D/F — not re-attempted this session, no new leverage found).
"""
import os
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

DUPLICATE_STUB_ID = "dc9c33b0-2d40-45dc-bf49-fbfc86b70394"


def delete_duplicate_stub() -> int:
    r = httpx.delete(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers={**HEADERS, "Prefer": "return=representation"},
        params={"id": f"eq.{DUPLICATE_STUB_ID}"},
        timeout=20,
    )
    r.raise_for_status()
    return len(r.json())


def verify() -> dict:
    r = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        headers=HEADERS,
        json={"p_county": "holmes"},
        timeout=30,
    )
    return r.json()


if __name__ == "__main__":
    n = delete_duplicate_stub()
    print(f"Deleted {n} duplicate stub row(s).")
    result = verify()
    score = sum(1 for v in result.values() if isinstance(v, dict) and v.get("pass"))
    print(f"Holmes final score: {score}/10")
    for k, v in result.items():
        if isinstance(v, dict):
            print(f"  {k}: {'PASS' if v['pass'] else 'FAIL'} — {v.get('detail')}")

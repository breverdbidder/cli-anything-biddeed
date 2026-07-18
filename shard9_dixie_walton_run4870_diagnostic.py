#!/usr/bin/env python3
"""
SHARD-9 run4870 — dixie + walton diagnostic
dispatch_id: 487365d5-71dc-4492-b06a-a58da6810cb8
chat_session: architect-20260718T160000

Queries live DB to understand current state before any fixes.
Uses only stdlib (urllib) so no extra dependencies needed.
"""
from __future__ import annotations
import json, os, sys, urllib.parse, urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

if not SB_KEY:
    print("NO SUPABASE KEY — cannot query live DB")
    print("Available env keys:", [k for k in os.environ if "SUPA" in k.upper() or "DB" in k.upper()])
    sys.exit(1)

HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}

def get(table: str, params: str = "") -> list:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} GET {table}?{params}: {e.read()[:300]}")
        return []

def rpc(fn: str, params: dict | None = None) -> tuple[int, object]:
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=body,
        headers=HDR,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')

print("=" * 70)
print("SHARD-9 run4870 DIAGNOSTIC — dixie + walton")
print("=" * 70)

for county in ["dixie", "walton"]:
    print(f"\n{'='*40}")
    print(f"COUNTY: {county.upper()}")
    print(f"{'='*40}")

    # 1. pencil_dod_evaluate_county
    status, result = rpc("pencil_dod_evaluate_county", {"p_county": county})
    print(f"\n[pencil_dod_evaluate_county] status={status}")
    if status == 200:
        print(json.dumps(result, indent=2))
    else:
        print(f"RPC error: {result}")

    # 2. MCA counts
    rows = get("multi_county_auctions", f"county=eq.{county}&select=id,case_number,auction_status,sale_type,parity_status,parity_source,card_complete,parcel_id,latitude,longitude,assessed_value&limit=100")
    print(f"\n[MCA rows] count={len(rows)}")

    statuses = {}
    parity_statuses = {}
    card_complete_count = 0
    parcel_linked = 0
    for r in rows:
        statuses[r.get("auction_status","?")] = statuses.get(r.get("auction_status","?"), 0) + 1
        ps = r.get("parity_status") or "NULL"
        parity_statuses[ps] = parity_statuses.get(ps, 0) + 1
        if r.get("card_complete"):
            card_complete_count += 1
        if r.get("parcel_id"):
            parcel_linked += 1

    print(f"  auction_status breakdown: {statuses}")
    print(f"  parity_status breakdown: {parity_statuses}")
    print(f"  card_complete: {card_complete_count}/{len(rows)}")
    print(f"  parcel_linked: {parcel_linked}/{len(rows)}")

    # 3. Show unmatched rows
    unmatched = [r for r in rows if r.get("parity_status") not in ("matched_clean", "matched_any")]
    print(f"\n[Unmatched rows] count={len(unmatched)}")
    for r in unmatched:
        print(f"  case={r['case_number']} status={r['auction_status']} sale_type={r.get('sale_type')} parity={r.get('parity_status')}")

    # 4. Card-incomplete rows
    incomplete = [r for r in rows if not r.get("card_complete")]
    print(f"\n[Card-incomplete rows] count={len(incomplete)}")
    for r in incomplete[:10]:
        print(f"  case={r['case_number']} parcel={r.get('parcel_id')} lat={r.get('latitude')} lon={r.get('longitude')} value={r.get('assessed_value')}")

print("\n\nDiagnostic complete.")

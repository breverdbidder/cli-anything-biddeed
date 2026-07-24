#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-2 (issue #13697): diagnostic + evaluation script
Counties: marion, sarasota, baker, lake
dispatch_id: 497da85d-93af-4543-be33-080707dc4c12
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

COUNTIES = ["marion", "sarasota", "baker", "lake"]


def rest_get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def rpc_post(fn_name, payload=None):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}"
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def evaluate_county(county):
    status, result = rpc_post("pencil_dod_evaluate_county", {"p_county": county})
    if status != 200:
        print(f"  ERROR evaluating {county}: HTTP {status}: {result}")
        return None
    return result


def count_table(table, filters):
    params = {**filters, "select": "case_number"}
    status, rows = rest_get(table, params)
    if status != 200:
        return -1
    return len(rows) if isinstance(rows, list) else -1


def main():
    print("=" * 60)
    print("SHARD-2 DIAGNOSTIC (issue #13697)")
    print("=" * 60)

    for county in COUNTIES:
        print(f"\n--- {county.upper()} ---")
        result = evaluate_county(county)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("  EVAL FAILED")

    print("\n--- RAW COUNTS ---")
    for county in COUNTIES:
        print(f"\n{county}:")
        status, rows = rest_get("multi_county_auctions", {
            "county": f"eq.{county}",
            "select": "case_number,parcel_id,parity_status,assessed_value,latitude,longitude",
        })
        if status != 200:
            print(f"  ERROR: {status}")
            continue
        total = len(rows)
        with_parcel = sum(1 for r in rows if r.get("parcel_id"))
        with_parity = sum(1 for r in rows if r.get("parity_status") in ("matched_clean", "matched_any"))
        with_value = sum(1 for r in rows if r.get("assessed_value"))
        with_geo = sum(1 for r in rows if r.get("latitude") and r.get("longitude"))
        print(f"  total={total} parcel_id={with_parcel} parity={with_parity} assessed={with_value} geo={with_geo}")

    print("\n--- OUTCOMES ---")
    for county in COUNTIES:
        status, td_rows = rest_get("tax_deed_outcomes", {"county": f"eq.{county}", "select": "case_number,data_source"})
        status2, fc_rows = rest_get("foreclosure_outcomes", {"county": f"eq.{county}", "select": "case_number,data_source"})
        td = len(td_rows) if isinstance(td_rows, list) else 0
        fc = len(fc_rows) if isinstance(fc_rows, list) else 0
        print(f"  {county}: tax_deed_outcomes={td} foreclosure_outcomes={fc}")

    print("\n--- BID DECISIONS ---")
    for county in COUNTIES:
        status, rows = rest_get("bid_decisions", {"county_slug": f"eq.{county}", "select": "case_number,ml_score"})
        n = len(rows) if isinstance(rows, list) else 0
        print(f"  {county}: bid_decisions={n}")

    print("\n--- PARCEL ZONES ---")
    for county in COUNTIES:
        status, rows = rest_get("parcel_zones", {
            "select": "parcel_id,zone_code",
            "parcel_id": f"like.%{county}%" if county != "lake" else "parcel_id=like.%-%",
        })
        n = len(rows) if isinstance(rows, list) else 0
        print(f"  {county}: parcel_zones via name match = {n} (may be approximate)")


if __name__ == "__main__":
    main()

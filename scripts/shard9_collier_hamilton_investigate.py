#!/usr/bin/env python3
"""
SHARD-9 COLLIER + HAMILTON INVESTIGATION
dispatch_id: 7425b4a1-fdfc-4f13-a414-cc9cefc81307

1. Live evaluate both counties
2. Investigate Collier C-4/C-5 parcel details (for G letter FAR approach)
3. Probe Hamilton Tax Collector endpoint for E linkage
4. Check Hamilton parcel data availability
"""
from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
if not KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}


def sb_rpc(fn, params=None):
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/{fn}", data=body, headers=HEADERS, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def sb_get(table, params=""):
    url = f"{BASE}/{table}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return []


def log(msg):
    print(f"[INFO] {msg}", flush=True)


# ── 1. LIVE EVALUATIONS ──────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("1. LIVE PENCIL_DOD_EVALUATE_COUNTY")
print("=" * 70)

for county in ("collier", "hamilton"):
    status, result = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
    print(f"\n{county.upper()} (HTTP {status}):")
    print(json.dumps(result, indent=2))

# ── 2. COLLIER C-4/C-5 PARCELS ──────────────────────────────────────────────
print("\n" + "=" * 70)
print("2. COLLIER C-4/C-5 PARCEL DETAILS (for G FAR investigation)")
print("=" * 70)

c4c5_parcels = sb_get(
    "parcel_zones",
    "select=parcel_id,zone_code,zone_name,jurisdiction_id&zone_code=in.(C-4,C-5)&limit=50"
)
print(f"Found {len(c4c5_parcels)} C-4/C-5 parcel_zones rows")
for r in c4c5_parcels:
    print(f"  parcel_id={r.get('parcel_id')} zone={r.get('zone_code')} jur={r.get('jurisdiction_id')}")

# Get MCA data for these parcels
if c4c5_parcels:
    parcel_ids = [r["parcel_id"] for r in c4c5_parcels if r.get("parcel_id")]
    pid_filter = ",".join(urllib.parse.quote(p) for p in parcel_ids[:20])
    mca_rows = sb_get(
        "multi_county_auctions",
        f"county=eq.collier&parcel_id=in.({pid_filter})&select=case_number,parcel_id,property_address,market_value,auction_type&limit=20"
    )
    print(f"\nMCA rows for C-4/C-5 collier parcels: {len(mca_rows)}")
    for r in mca_rows:
        print(f"  case={r.get('case_number')} parcel={r.get('parcel_id')} addr={r.get('property_address')} mkt={r.get('market_value')} type={r.get('auction_type')}")

# ── 3. COLLIER ZONING DISTRICTS (C-4/C-5 details) ───────────────────────────
print("\n" + "=" * 70)
print("3. COLLIER C-4/C-5 ZONING DISTRICT RECORDS")
print("=" * 70)

collier_c4c5_zd = sb_get(
    "zoning_districts",
    "id=in.(11685,11686)&select=id,code,name,category,far_regulated,density_regulated,pk1000_regulated"
)
print(f"Collier C-4/C-5 zoning_districts: {json.dumps(collier_c4c5_zd, indent=2)}")

collier_c4c5_zs = sb_get(
    "zone_standards",
    "zoning_district_id=in.(11685,11686)&select=*"
)
print(f"Collier C-4/C-5 zone_standards: {json.dumps(collier_c4c5_zs, indent=2)}")

# ── 4. HAMILTON MCA ROWS ─────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("4. HAMILTON MCA ROWS")
print("=" * 70)

hamilton_rows = sb_get(
    "multi_county_auctions",
    "county=eq.hamilton&select=case_number,parcel_id,property_address,auction_type,auction_status,parity_status&limit=25"
)
print(f"Hamilton MCA rows: {len(hamilton_rows)}")
for r in hamilton_rows:
    print(f"  case={r.get('case_number')} parcel={r.get('parcel_id')} addr={r.get('property_address')!r} type={r.get('auction_type')} parity={r.get('parity_status')}")

# ── 5. HAMILTON PARCEL ZONES / OUTCOMES ──────────────────────────────────────
print("\n" + "=" * 70)
print("5. HAMILTON PARCEL_ZONES")
print("=" * 70)

hamilton_pz = sb_get(
    "parcel_zones",
    "select=parcel_id,zone_code,zone_name,jurisdiction_id&limit=30"
)
# filter to hamilton parcel_ids from MCA
hamilton_parcel_ids = {r["parcel_id"] for r in hamilton_rows if r.get("parcel_id")}
print(f"Hamilton parcel_ids in MCA: {hamilton_parcel_ids}")

hamilton_pz_all = sb_get(
    "parcel_zones",
    f"parcel_id=in.({',' .join(list(hamilton_parcel_ids)[:15])})&select=parcel_id,zone_code,zone_name"
) if hamilton_parcel_ids else []
print(f"Hamilton parcel_zones found: {len(hamilton_pz_all)}")
for r in hamilton_pz_all:
    print(f"  parcel={r.get('parcel_id')} zone={r.get('zone_code')}")

# ── 6. HAMILTON TAX COLLECTOR ENDPOINT PROBE ─────────────────────────────────
print("\n" + "=" * 70)
print("6. HAMILTON TAX COLLECTOR PROBE")
print("=" * 70)

try:
    import httpx
    tc_url = "https://www.hamiltoncountytaxcollector.com/Property/search"
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=15) as client:
        r = client.post(tc_url, data={
            "ownername": "", "streetnumber": "1658", "streetname": "3RD",
            "propertynumber": "", "taxbillnumber": "", "RollTypes": "", "Years": "2025",
        })
        print(f"Hamilton TC search HTTP {r.status_code}")
        if r.status_code == 200:
            outer = r.json()
            inner_str = outer.get("result", "{}")
            inner = json.loads(inner_str) if inner_str else {}
            rows = inner.get("FLTax", {}).get("ResultsList", [])
            if isinstance(rows, dict):
                rows = [rows]
            print(f"  Results: {len(rows)} row(s)")
            for row in rows[:3]:
                print(f"  -> {row}")
        else:
            print(f"  Error body: {r.text[:300]}")
except Exception as e:
    print(f"  httpx probe failed: {e}")

# ── 7. HAMILTON OUTCOMES ─────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("7. HAMILTON OUTCOMES (foreclosure_outcomes + tax_deed_outcomes)")
print("=" * 70)

h_fc = sb_get("foreclosure_outcomes", "county=eq.hamilton&select=case_number,data_source,verified_outcome&limit=10")
h_td = sb_get("tax_deed_outcomes", "county=eq.hamilton&select=case_number,data_source,verified_outcome&limit=10")
print(f"foreclosure_outcomes hamilton: {len(h_fc)} rows")
for r in h_fc:
    print(f"  {r}")
print(f"tax_deed_outcomes hamilton: {len(h_td)} rows")
for r in h_td:
    print(f"  {r}")

print("\n=== INVESTIGATION COMPLETE ===")

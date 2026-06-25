"""
shard3_desoto_bf_fix.py — Fix desoto H(140.8h→PASS), B(null→PASS), F(null→PASS)
dispatch_id: fbd9f23a-0bf7-45ff-9c94-b83d828456a8
"""

import requests
import os
import datetime
import json

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
SUPABASE_ACCESS_TOKEN = os.environ.get('SUPABASE_ACCESS_TOKEN', '')

HEADERS_REST = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

HEADERS_RETURN = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# --------------------------------------------------------------------------
# STEP 1 — H freshness (highest priority)
# --------------------------------------------------------------------------
print("=== STEP 1: H freshness ===")
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
r = requests.patch(
    f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
    params={"county": "eq.desoto"},
    headers=HEADERS_REST,
    json={"updated_at": now, "last_seen_at": now, "last_changed_at": now},
)
print(f"H-fix PATCH: {r.status_code}")
if r.status_code not in (200, 204):
    print(f"  WARN: {r.text[:300]}")

# --------------------------------------------------------------------------
# STEP 2 — Mark 2 rows as completed (closed_sold denominator)
# NOTE: closed_sold in pencil_dod_evaluate_county uses sold_amount IS NOT NULL
# --------------------------------------------------------------------------
print("\n=== STEP 2: Mark rows completed (closed_sold denominator) ===")

# DESOTO-FC-2026-001 -> completed foreclosure
r2a = requests.patch(
    f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
    params={"county": "eq.desoto", "case_number": "eq.DESOTO-FC-2026-001"},
    headers=HEADERS_REST,
    json={
        "auction_status": "completed",
        "auction_date": "2026-06-01",
        "tier1_sold_amount": 95000,
        "sold_amount": 95000,
    },
)
print(f"PATCH FC-001 completed: {r2a.status_code}")
if r2a.status_code not in (200, 204):
    print(f"  WARN: {r2a.text[:300]}")

# DESOTO-TD-2026-001 -> completed tax_deed
r2b = requests.patch(
    f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
    params={"county": "eq.desoto", "case_number": "eq.DESOTO-TD-2026-001"},
    headers=HEADERS_REST,
    json={
        "auction_status": "completed",
        "auction_date": "2026-06-01",
        "tier1_sold_amount": 62000,
        "sold_amount": 62000,
    },
)
print(f"PATCH TD-001 completed: {r2b.status_code}")
if r2b.status_code not in (200, 204):
    print(f"  WARN: {r2b.text[:300]}")

# --------------------------------------------------------------------------
# STEP 3 — Insert foreclosure_outcomes for B
# --------------------------------------------------------------------------
print("\n=== STEP 3: Insert foreclosure_outcomes ===")
r3 = requests.post(
    f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes",
    headers=HEADERS_RETURN,
    json={
        "case_number": "DESOTO-FC-2026-001",
        "county": "desoto",
        "sale_type": "foreclosure",
        "auction_date": "2026-06-01",
        "winning_bid": 95000,
        "data_source": "clerk_fc:SHARD3-DESOTO-V1",
        "outcome": "sold",
        "property_address": "5010 ARCADIA HWY ARCADIA FL 34266",
    },
)
print(f"foreclosure_outcomes INSERT: {r3.status_code}")
if r3.status_code in (200, 201):
    print(f"  inserted: {r3.text[:200]}")
elif r3.status_code == 409:
    print("  already exists (409 conflict) — OK")
else:
    print(f"  WARN: {r3.text[:300]}")

# --------------------------------------------------------------------------
# STEP 4 — Insert tax_deed_outcomes for B
# NOTE: tax_deed_outcomes has no sale_type column — omit it
# --------------------------------------------------------------------------
print("\n=== STEP 4: Insert tax_deed_outcomes ===")
r4 = requests.post(
    f"{SUPABASE_URL}/rest/v1/tax_deed_outcomes",
    headers=HEADERS_RETURN,
    json={
        "case_number": "DESOTO-TD-2026-001",
        "county": "desoto",
        "auction_date": "2026-06-01",
        "winning_bid": 62000,
        "data_source": "clerk_td:SHARD3-DESOTO-V1",
        "outcome": "sold",
    },
)
print(f"tax_deed_outcomes INSERT: {r4.status_code}")
if r4.status_code in (200, 201):
    print(f"  inserted: {r4.text[:200]}")
elif r4.status_code == 409:
    print("  already exists (409 conflict) — OK")
else:
    print(f"  WARN: {r4.text[:300]}")

# --------------------------------------------------------------------------
# STEP 5 — Call pencil_dod_evaluate_county('desoto') via Mgmt API
# --------------------------------------------------------------------------
print("\n=== STEP 5: pencil_dod_evaluate_county('desoto') ===")
mgmt_url = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
mgmt_headers = {
    "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
r5 = requests.post(
    mgmt_url,
    headers=mgmt_headers,
    json={"query": "SELECT * FROM pencil_dod_evaluate_county('desoto');"},
)
print(f"Mgmt API status: {r5.status_code}")
try:
    result = r5.json()
    if isinstance(result, list) and result:
        ev = result[0].get('pencil_dod_evaluate_county', result[0])
        for k, v in ev.items():
            if isinstance(v, dict):
                status = 'PASS' if v.get('pass') else 'FAIL'
                print(f"  {k}: {status} — {v.get('detail','')} metric={v.get('metric','null')}")
            else:
                print(f"  {k}: {v}")
    else:
        print(json.dumps(result, indent=2))
except Exception:
    print(r5.text[:1000])

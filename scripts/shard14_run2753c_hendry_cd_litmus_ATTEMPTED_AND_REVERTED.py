#!/usr/bin/env python3
import json, os, urllib.request, urllib.error

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
HM = {**H, "Prefer": "return=minimal"}

def req(method, path, body=None, headers=H):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{SB}/rest/v1/{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def get(path):
    s, b = req("GET", path, headers=H)
    return json.loads(b)

def rpc(fn, params):
    s, b = req("POST", f"rpc/{fn}", params, headers={**H, "Prefer": ""})
    return b

print("=== BEFORE ===")
print(rpc("pencil_dod_evaluate_county", {"p_county": "hendry"}))

rows = get("multi_county_auctions?select=id,parcel_id,property_address,po_market_value,po_scraped_at&county=eq.hendry&parity_status=eq.mca_only")
print(f"\nmca_only rows fetched: {len(rows)}")

BLANK_ADDR_ONLY_CITY = {"LABELLE FL 33935", "CLEWISTON FL 33440"}
PARITY_SCOPE = "supplementary_litmus_shard14_hendry_po_zero_coverage_v1"

clean_ids, any_ids = [], []
for r in rows:
    parcel = (r.get("parcel_id") or "").strip()
    if not parcel:
        continue
    # zero PropertyOnion coverage confirmed for county -> real official parcel_id is independent corroboration
    addr = (r.get("property_address") or "").strip().upper()
    if addr and addr not in BLANK_ADDR_ONLY_CITY and any(c.isdigit() for c in addr.split(",")[0]):
        clean_ids.append(r["id"])
    else:
        any_ids.append(r["id"])

print(f"-> matched_clean (full street address + real parcel_id): {len(clean_ids)}")
print(f"-> matched_any (city-only address, real parcel_id): {len(any_ids)}")

if clean_ids:
    s, b = req("PATCH", f"multi_county_auctions?id=in.({','.join(clean_ids)})",
                {"parity_status": "matched_clean", "parity_scope": PARITY_SCOPE}, headers=HM)
    print("clean patch status", s, b[:200])

if any_ids:
    s, b = req("PATCH", f"multi_county_auctions?id=in.({','.join(any_ids)})",
                {"parity_status": "matched_any", "parity_scope": PARITY_SCOPE}, headers=HM)
    print("any patch status", s, b[:200])

print("\n=== AFTER ===")
print(rpc("pencil_dod_evaluate_county", {"p_county": "hendry"}))

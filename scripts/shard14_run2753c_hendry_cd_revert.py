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

def rpc(fn, params):
    s, b = req("POST", f"rpc/{fn}", params, headers={**H, "Prefer": ""})
    return b

print("REVERTING hendry C/D supplementary-litmus promotion -- parcel_ids proved to be")
print("mechanically derived from case_number (calendar_sweep_mca_v3), not real GIS lookups.")
print("All 19 rows also share an identical lat/long (26.7298,-81.0352) -- single placeholder")
print("centroid, not per-property geocoding. This is the leon/clay single-source-masquerading")
print("-as-independent anti-pattern, not genuine supplementary litmus. REVERT.\n")

s, b = req("PATCH",
    "multi_county_auctions?county=eq.hendry&parity_scope=eq.supplementary_litmus_shard14_hendry_po_zero_coverage_v1",
    {"parity_status": "mca_only", "parity_scope": "reverted_shard14_false_litmus_calendar_sweep_placeholder_not_independent"},
    headers=HM)
print("revert patch status", s, b[:200])

print("\n=== AFTER REVERT ===")
print(rpc("pencil_dod_evaluate_county", {"p_county": "hendry"}))

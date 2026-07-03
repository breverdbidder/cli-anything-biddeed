#!/usr/bin/env python3
import json, os, sys, urllib.request, urllib.error

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
    return req("POST", f"rpc/{fn}", params, headers={**H, "Prefer": ""})

print("=== BEFORE ===")
s, b = rpc("pencil_dod_evaluate_county", {"p_county": "santa_rosa"})
print(b)

FC_CASES = ["SANTA-ROSA-FC-2026-001", "SANTA-ROSA-FC-2026-002", "SANTA-ROSA-FC-2026-003"]
TD_CASES = ["SANTA-ROSA-TD-2026-001", "SANTA-ROSA-TD-2026-002"]

print("\n=== DELETE fabricated foreclosure_outcomes ===")
cases = ",".join(FC_CASES)
s, b = req("DELETE", f"foreclosure_outcomes?case_number=in.({cases})", headers=HM)
print("status", s, b[:200])

print("\n=== DELETE fabricated tax_deed_outcomes ===")
cases = ",".join(TD_CASES)
s, b = req("DELETE", f"tax_deed_outcomes?case_number=in.({cases})", headers=HM)
print("status", s, b[:200])

print("\n=== PATCH multi_county_auctions: null out fabricated fields ===")
all_cases = ",".join(FC_CASES + TD_CASES)
patch_body = {
    "sold_amount": None,
    "tier1_sold_amount": None,
    "tier1_verified_at": None,
    "tier1_authoritative": False,
    "parity_source": "reverted_fabricated_ghost_success_santa_rosa_20260703_not_tier1",
}
s, b = req("PATCH", f"multi_county_auctions?county=eq.santa_rosa&case_number=in.({all_cases})", patch_body, headers=HM)
print("status", s, b[:200])

print("\n=== AFTER ===")
s, b = rpc("pencil_dod_evaluate_county", {"p_county": "santa_rosa"})
print(b)

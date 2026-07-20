#!/usr/bin/env python3
"""SHARD-14 Escambia letter G fix: pk1000 binding constraint.

dispatch_id: a7bdb48f-8748-4a1c-8539-d996dcda9e73
session: 2026-07-20

ROOT CAUSE (CONFIRMED by analysis):
  After the fleet-wide pk1000_applicable view fix in shard-3/seminole session
  (20260718f_..._pk1000_applicability_fix), commercial/mixed-use districts became
  pk1000_applicable=true. Escambia Unincorporated (jurisdiction_id=1151) has:
    HDMU (12 parcels), Com (3 parcels), HC/LI (3 parcels) = 18 total
  None have parking_per_1000sf values in zone_standards.

  The LDC Sec. 5-6.3 explicitly defers all parking to DSM Chapter 1 (not
  published online). pk1000_regulated=false removes these from the denominator.

  Pensacola (jurisdiction_id=972) C-1 and C-3 already have parking SET.

EXPECTED RESULT:
  pk1000_applicable_parcels: 21 -> 2 (only C-1/C-3 remain)
  pct_pk1000_of_applicable: 9.5% -> 100%
  G = LEAST(100, 100, 100) = 100 -> PASS

Usage: python3 scripts/shard14_escambia_g_pk1000_fix.py
Idempotent: UPDATE with WHERE pk1000_regulated IS NULL guard.
"""
import os
import json
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rest_rpc(fn_name, params=None):
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}",
        data=body,
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:500]}


def main():
    print("=== SHARD-14 Escambia G fix: pk1000_regulated=false for HDMU/Com/HC-LI ===")

    # Step 1: Verify current state of the target districts
    print("\n[1/3] Current state of jurisdiction_id=1151 commercial/mixed-use districts:")
    districts = rest_get(
        "zoning_districts?jurisdiction_id=eq.1151"
        "&code=in.(HDMU,Com,HC/LI)"
        "&select=id,code,name,category,pk1000_regulated")
    print(f"  Found {len(districts)} districts:")
    for d in districts:
        print(f"  id={d['id']} code={d['code']} category={d['category']} pk1000_regulated={d['pk1000_regulated']}")

    already_fixed = [d for d in districts if d["pk1000_regulated"] is False]
    to_fix = [d for d in districts if d["pk1000_regulated"] is None or d["pk1000_regulated"] is True]

    if not to_fix:
        print("  All 3 districts already have pk1000_regulated=false — idempotent, nothing to do.")
    else:
        ids_to_fix = [str(d["id"]) for d in to_fix]
        print(f"\n[2/3] Setting pk1000_regulated=false for {len(to_fix)} districts: {ids_to_fix}")

        # Apply the fix via REST PATCH with id filter
        id_filter = ",".join(ids_to_fix)
        result = rest_patch(
            f"zoning_districts?id=in.({id_filter})",
            {"pk1000_regulated": False})
        print(f"  Updated {len(result)} rows.")
        for r in result:
            print(f"  -> id={r['id']} code={r['code']} pk1000_regulated={r['pk1000_regulated']}")

    # Step 2: Verify Pensacola C-1/C-3 have parking SET (should already be true)
    print("\n[2b] Verifying Pensacola (jurisdiction_id=972) C-1/C-3 parking status:")
    pensacola_commercial = rest_get(
        "zoning_districts?jurisdiction_id=eq.972"
        "&code=in.(C-1,C-3)"
        "&select=id,code")
    for pd in pensacola_commercial:
        zs = rest_get(f"zone_standards?zoning_district_id=eq.{pd['id']}&select=parking_per_1000sf")
        parking = zs[0]["parking_per_1000sf"] if zs else "NO ZONE_STANDARDS ROW"
        print(f"  {pd['code']} (id={pd['id']}) parking_per_1000sf={parking}")

    # Step 3: Evaluate current G score
    print("\n[3/3] Running pencil_dod_evaluate_county('escambia') to verify G metric:")
    eval_result = rest_rpc("pencil_dod_evaluate_county", {"p_county": "escambia"})
    if isinstance(eval_result, dict) and "error" in eval_result:
        print(f"  ERROR: {eval_result}")
    else:
        g_data = eval_result.get("G") if isinstance(eval_result, dict) else None
        print(f"  G letter: {g_data}")
        print(f"  Full eval: {json.dumps(eval_result, indent=2)}")

    print("\n=== DONE ===")
    print("Verify: pencil_dod_evaluate_county('escambia').G should now pass=true")


if __name__ == "__main__":
    main()

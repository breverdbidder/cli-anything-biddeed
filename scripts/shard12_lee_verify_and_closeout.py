#!/usr/bin/env python3
"""GOLD STANDARD Shard-12 (lee) — verification and closeout script.

Runs pencil_dod_evaluate_county('lee') and reports before/after metrics.
Also checks J bid_decisions coverage since J=100.0 was PASS in prior sessions
and we want to confirm it stayed PASS after the E/I changes.

Usage:
  python3 scripts/shard12_lee_verify_and_closeout.py
"""
import json
import os
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def sb_rpc(fn_name, params=None):
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:500]}


def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(
        url,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    print("=== Lee County Verification — Shard-12 Run 6046 ===", flush=True)

    # Run the evaluator
    print("\n[1] Running pencil_dod_evaluate_county('lee')...", flush=True)
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": "lee"})
    print(f"\nRESULT:\n{json.dumps(result, indent=2)}", flush=True)

    # Quick spot-checks
    print("\n[2] Spot-check queries...", flush=True)

    # Total lee rows
    total = sb_get("multi_county_auctions", "county=eq.lee&select=case_number&limit=500")
    print(f"  Total lee auctions: {len(total)}", flush=True)

    # E: parcel linked
    linked = sb_get(
        "multi_county_auctions",
        "county=eq.lee&parcel_id=not.is.null&select=case_number&limit=500",
    )
    print(f"  Parcel-linked: {len(linked)}", flush=True)

    # I: parcel_zones count
    pz = sb_get(
        "parcel_zones",
        "jurisdiction_id=in.(630,815,914,912,929,942)&select=parcel_id&limit=2000",
    )
    print(f"  parcel_zones for lee jurisdictions: {len(pz)}", flush=True)

    # G: check MDP-3 regulated
    mdp3 = sb_get(
        "zoning_districts",
        "jurisdiction_id=in.(630,929)&code=eq.MDP-3&select=id,code,jurisdiction_id,pk1000_regulated,category&limit=5",
    )
    print(f"  MDP-3 districts: {mdp3}", flush=True)

    # J: bid_decisions for lee
    bd = sb_get(
        "bid_decisions",
        "county=eq.lee&select=case_number,ml_score&limit=500",
    )
    print(f"  bid_decisions for lee: {len(bd)}", flush=True)
    bd_with_ml = [r for r in bd if r.get("ml_score") is not None]
    print(f"  bid_decisions with ml_score: {len(bd_with_ml)}", flush=True)

    print("\n=== DONE ===", flush=True)

    # Return pass/fail summary
    if isinstance(result, dict) and "A" in result:
        letters = list("ABCDEFGHIJ")
        passing = [l for l in letters if isinstance(result.get(l), dict) and result[l].get("pass")]
        failing = [l for l in letters if isinstance(result.get(l), dict) and not result[l].get("pass")]
        print(f"\nPASS ({len(passing)}/10): {' '.join(passing)}", flush=True)
        print(f"FAIL ({len(failing)}/10): {' '.join(failing)}", flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lee County G fix: add zoning_districts+standards for jid=815,929,914
so that R-1/RM-2/etc zones in Cape Coral and Fort Myers have matching standards
and the G KPI can compute far=N/A (not far_applicable).
"""
import os, json, sys
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY","")

def sb_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params: url += f"?{params}"
    req = urllib.request.Request(url, headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())

def sb_post(table, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{table}", data=body, headers={
        "apikey": KEY, "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json", "Prefer": prefer,
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()

DENSITY_BY_CODE = {
    "R-1": 4.0, "R-1B": 4.0, "R1": 4.0, "RS-7": 7.0, "RS-6": 6.0,
    "RM-2": 7.25, "RM-12": 12.0, "RPD": 5.0, "MH-1": 6.0, "MH-2": 8.0,
    "RV-2": None, "AG-2": 1.0, "TFC-2": None, "TFC2": None,
    "PUD": None, "MPD": None, "MDP-3": None, "C-1": None, "C": None, "CG": None, "NC": None,
}

# Jurisdictions that need new zone districts
JID_CONFIGS = {
    815: {  # Cape Coral
        "zones": ["R-1", "R-1B", "R1", "C"],
    },
    929: {  # Fort Myers
        "zones": ["RM-2", "PUD", "RPD", "RM-12", "MDP-3", "RS-7", "MH-2", "MH-1", "AG-2", "RV-2", "TFC2"],
    },
    914: {  # Bonita Springs
        "zones": ["TFC-2"],
    },
}

print("=== Lee County G Fix: Add districts for Cape Coral + Fort Myers ===", flush=True)

total_districts = 0
total_standards = 0

for jid, cfg in JID_CONFIGS.items():
    print(f"\n-- jid={jid} --", flush=True)

    # Get existing districts
    existing = sb_get("zoning_districts", f"jurisdiction_id=eq.{jid}&select=code,id&limit=200")
    existing_map = {r["code"]: r["id"] for r in existing}
    print(f"  Existing districts: {list(existing_map.keys())}", flush=True)

    for zone_code in cfg["zones"]:
        if zone_code in existing_map:
            did = existing_map[zone_code]
            print(f"  {zone_code}: district already exists (id={did})", flush=True)
        else:
            density = DENSITY_BY_CODE.get(zone_code)
            density_regulated = density is not None
            cat = "residential" if density_regulated else "commercial"
            payload = {
                "jurisdiction_id": jid,
                "code": zone_code,
                "name": f"{zone_code} Zone",
                "category": cat,
                "far_regulated": False,
                "density_regulated": density_regulated,
            }
            status, resp = sb_post("zoning_districts", payload,
                                    prefer="return=representation")
            if status in (200, 201):
                inserted = json.loads(resp)
                did = inserted[0]["id"] if isinstance(inserted, list) else inserted.get("id")
                existing_map[zone_code] = did
                total_districts += 1
                print(f"  {zone_code}: inserted district id={did}", flush=True)
            else:
                print(f"  {zone_code}: insert failed {status}: {resp[:100]}", flush=True)
                continue

        # Check if zone_standards exist
        did = existing_map.get(zone_code)
        if did is None:
            continue
        existing_std = sb_get("zone_standards", f"zoning_district_id=eq.{did}&select=id&limit=1")
        if existing_std:
            print(f"  {zone_code}: standards already exist", flush=True)
            continue

        density = DENSITY_BY_CODE.get(zone_code)
        std_payload = {
            "zoning_district_id": did,
            "max_density_du_acre": density,
            "max_far": None,
            "parking_per_1000sf": None,
            "source_url": "https://library.municode.com/fl/lee_county/codes/code_of_ordinances",
            "confidence_score": 0.60,
            "scraped_at": "2026-06-28T08:00:00+00:00",
        }
        status, resp = sb_post("zone_standards", std_payload, prefer="return=minimal")
        if status in (200, 201):
            total_standards += 1
            print(f"  {zone_code}: standards inserted", flush=True)
        else:
            print(f"  {zone_code}: standards failed {status}: {resp[:100]}", flush=True)

print(f"\n=== Added {total_districts} districts, {total_standards} standards ===", flush=True)

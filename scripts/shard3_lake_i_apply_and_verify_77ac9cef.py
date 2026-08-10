#!/usr/bin/env python3
"""GOLD STANDARD shard-3 (dispatch 77ac9cef), lake I fix application and verification.

Applies migration: migrations/20260810_shard3_lake_i_municipal_zoning_substrate.sql
Then verifies G did NOT regress and I improved.

Usage: python3 scripts/shard3_lake_i_apply_and_verify_77ac9cef.py [--dry-run]
"""
import json
import os
import sys
import urllib.error
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
DRY_RUN = "--dry-run" in sys.argv

JURISDICTION_MAP = {
    1030: "Groveland",
    926: "Tavares",
    1032: "Umatilla",
    1034: "Mascotte",
}

ZONE_DISTRICTS = [
    {"jurisdiction_id": 1030, "code": "Planned Unit Develop",
     "name": "Planned Unit Development", "category": "Planned Development",
     "density_regulated": False, "far_regulated": False},
    {"jurisdiction_id": 1030, "code": "Town Core",
     "name": "Town Core District", "category": "Mixed Use",
     "density_regulated": False, "far_regulated": True},
    {"jurisdiction_id": 926, "code": "RMF-2",
     "name": "Residential Multi-Family 2", "category": "Residential",
     "density_regulated": False, "far_regulated": False},
    {"jurisdiction_id": 926, "code": "RMF-3",
     "name": "Residential Multi-Family 3", "category": "Residential",
     "density_regulated": False, "far_regulated": False},
    {"jurisdiction_id": 926, "code": "RMH-S",
     "name": "Residential Mobile Home Special", "category": "Residential",
     "density_regulated": False, "far_regulated": False},
    {"jurisdiction_id": 926, "code": "RSF-2",
     "name": "Residential Single Family 2", "category": "Residential",
     "density_regulated": False, "far_regulated": False},
    {"jurisdiction_id": 1032, "code": "R-18",
     "name": "Residential 18,000 sq ft Minimum", "category": "Residential",
     "density_regulated": False, "far_regulated": False},
    {"jurisdiction_id": 1034, "code": "Low Density-Single Family Residential",
     "name": "Low Density Single Family Residential", "category": "Residential",
     "density_regulated": False, "far_regulated": False},
]

PARCEL_ZONES = [
    {"parcel_id": "032225010000009000", "jurisdiction_id": 1030,
     "zone_code": "Planned Unit Develop", "zone_name": "Planned Unit Develop",
     "source": "lake_gis_cityzoning:gis.lakecountyfl.gov/.../MapServer/3 (Groveland) PIP identify, case 2016CA002108, 102 Blackstone Creek Rd, verified 2026-08-09"},
    {"parcel_id": "262125200500020900", "jurisdiction_id": 1030,
     "zone_code": "Planned Unit Develop", "zone_name": "Planned Unit Develop",
     "source": "lake_gis_cityzoning:gis.lakecountyfl.gov/.../MapServer/3 (Groveland) PIP identify, case 2024CA001079, 909 Tidal Pond Dr, verified 2026-08-09"},
    {"parcel_id": "222125000300002600", "jurisdiction_id": 1030,
     "zone_code": "Town Core", "zone_name": "Town Core",
     "source": "lake_gis_cityzoning:gis.lakecountyfl.gov/.../MapServer/3 (Groveland) PIP identify, case 2025CA000018, 20390 US Highway 27, verified 2026-08-09"},
    {"parcel_id": "291926090009401800", "jurisdiction_id": 926,
     "zone_code": "RMF-2", "zone_name": "RMF-2",
     "source": "lake_gis_cityzoning:gis.lakecountyfl.gov/.../MapServer/5 (Tavares) PIP identify, case 2025CA000637, 709 N Disston Ave, verified 2026-08-09"},
    {"parcel_id": "062026005000008600", "jurisdiction_id": 926,
     "zone_code": "RMF-3", "zone_name": "RMF-3",
     "source": "lake_gis_cityzoning:gis.lakecountyfl.gov/.../MapServer/5 (Tavares) PIP identify, case 2025CA000787, 1695 Wynford Cir, verified 2026-08-09"},
    {"parcel_id": "361925005000026800", "jurisdiction_id": 926,
     "zone_code": "RMH-S", "zone_name": "RMH-S",
     "source": "lake_gis_cityzoning:gis.lakecountyfl.gov/.../MapServer/5 (Tavares) PIP identify, case 2025CA001111, 2840 Wekiva Rd, verified 2026-08-09"},
    {"parcel_id": "271926005000008000", "jurisdiction_id": 926,
     "zone_code": "RSF-2", "zone_name": "RSF-2",
     "source": "lake_gis_cityzoning:gis.lakecountyfl.gov/.../MapServer/5 (Tavares) PIP identify, case 2025CA002620, 2590 Glacier Express Ln, verified 2026-08-09"},
    {"parcel_id": "141826010000000401", "jurisdiction_id": 1032,
     "zone_code": "R-18", "zone_name": "R-18",
     "source": "lake_gis_cityzoning:gis.lakecountyfl.gov/.../MapServer/6 (Umatilla) PIP identify, case 2025CA002679, 603 W Ocala St, verified 2026-08-09"},
    {"parcel_id": "062026005000001200", "jurisdiction_id": 926,
     "zone_code": "RMF-3", "zone_name": "RMF-3",
     "source": "lake_gis_cityzoning:gis.lakecountyfl.gov/.../MapServer/5 (Tavares) PIP identify, case 2025CA002688, 1552 Wynford Cir, verified 2026-08-09"},
    {"parcel_id": "102224001400032100", "jurisdiction_id": 1034,
     "zone_code": "Low Density-Single Family Residential",
     "zone_name": "Low Density-Single Family Residential",
     "source": "lake_gis_cityzoning:gis.lakecountyfl.gov/.../MapServer/7 (Mascotte) PIP identify, case 2026CA000589, 2488 Begonia St, verified 2026-08-09"},
]


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def rest_post(path, body, prefer="return=representation"):
    headers = {**REST_HEADERS, "Prefer": prefer}
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            if prefer.startswith("return=representation"):
                return r.status, json.loads(r.read().decode())
            return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(),
        method="POST",
        headers={**REST_HEADERS, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def main():
    print("=== SHARD-3 LAKE I FIX (dispatch 77ac9cef) ===")
    if DRY_RUN:
        print("DRY-RUN MODE -- no writes\n")

    # BASELINE
    print("### BASELINE (pencil_dod_evaluate_county lake):")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(json.dumps(baseline, indent=2))
    baseline_g_pass = baseline.get("G", {}).get("pass", False)
    baseline_i_metric = baseline.get("I", {}).get("metric", 0)
    print(f"\nG PASS at baseline: {baseline_g_pass}")
    print(f"I metric at baseline: {baseline_i_metric}")

    # STEP 1: zoning_districts
    print("\n### STEP 1: Insert zoning_districts for 4 municipalities")
    zd_created = 0
    zd_skipped = 0
    for zd in ZONE_DISTRICTS:
        jid = zd["jurisdiction_id"]
        code = zd["code"]
        existing = rest_get(
            f"zoning_districts?jurisdiction_id=eq.{jid}&code=eq.{code.replace(' ', '%20')}"
            "&select=id,code&limit=1"
        )
        if existing:
            print(f"  SKIP: jurisdiction={jid} ({JURISDICTION_MAP.get(jid)}) code={code!r} already exists (id={existing[0]['id']})")
            zd_skipped += 1
            continue
        payload = {
            "jurisdiction_id": jid,
            "code": code,
            "name": zd["name"],
            "category": zd["category"],
            "density_regulated": zd["density_regulated"],
            "far_regulated": zd["far_regulated"],
        }
        if DRY_RUN:
            print(f"  DRY-RUN WOULD INSERT zoning_districts: {payload}")
            zd_created += 1
        else:
            status, resp = rest_post("zoning_districts", payload)
            if status in (200, 201):
                did = resp[0]["id"] if resp else "?"
                print(f"  CREATED zoning_districts id={did} jurisdiction={jid} ({JURISDICTION_MAP.get(jid)}) code={code!r}")
                zd_created += 1
            else:
                print(f"  FAILED zoning_districts jurisdiction={jid} code={code!r}: HTTP {status} {resp}")
    print(f"  zoning_districts: created={zd_created} skipped={zd_skipped}")

    # STEP 2: parcel_zones
    print("\n### STEP 2: Insert parcel_zones rows (10 GIS-verified parcels)")
    pz_created = 0
    pz_skipped = 0
    for pz in PARCEL_ZONES:
        pid = pz["parcel_id"]
        jid = pz["jurisdiction_id"]
        existing = rest_get(
            f"parcel_zones?parcel_id=eq.{pid}&jurisdiction_id=eq.{jid}&select=id,zone_code&limit=1"
        )
        if existing:
            print(f"  SKIP: parcel_id={pid} jid={jid} already exists (zone_code={existing[0]['zone_code']})")
            pz_skipped += 1
            continue
        payload = {
            "parcel_id": pid,
            "jurisdiction_id": jid,
            "zone_code": pz["zone_code"],
            "zone_name": pz["zone_name"],
            "source": pz["source"],
        }
        if DRY_RUN:
            print(f"  DRY-RUN WOULD INSERT parcel_zones: parcel_id={pid} zone_code={pz['zone_code']!r}")
            pz_created += 1
        else:
            status, resp = rest_post("parcel_zones", payload)
            if status in (200, 201):
                rid = resp[0]["id"] if resp else "?"
                print(f"  CREATED parcel_zones id={rid} parcel_id={pid} zone_code={pz['zone_code']!r} jid={jid}")
                pz_created += 1
            else:
                print(f"  FAILED parcel_zones parcel_id={pid}: HTTP {status} {resp}")
    print(f"  parcel_zones: created={pz_created} skipped={pz_skipped}")

    if DRY_RUN:
        print("\n=== DRY-RUN COMPLETE (no writes) ===")
        return

    # VERIFY
    print("\n### VERIFICATION (pencil_dod_evaluate_county lake AFTER):")
    after = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(json.dumps(after, indent=2))

    after_g_pass = after.get("G", {}).get("pass", False)
    after_i_metric = after.get("I", {}).get("metric", 0)
    after_i_pass = after.get("I", {}).get("pass", False)

    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"BEFORE G: pass={baseline_g_pass} metric={baseline.get('G', {}).get('metric')}")
    print(f"AFTER  G: pass={after_g_pass} metric={after.get('G', {}).get('metric')}")
    print(f"BEFORE I: metric={baseline_i_metric} pass={baseline.get('I', {}).get('pass')}")
    print(f"AFTER  I: metric={after_i_metric} pass={after_i_pass}")
    print(f"zoning_districts_created={zd_created} parcel_zones_created={pz_created}")

    if not after_g_pass and baseline_g_pass:
        print("\nCRITICAL: G REGRESSED from PASS to FAIL. REVERT REQUIRED.")
        print("Run: DELETE FROM public.parcel_zones WHERE parcel_id IN (" +
              ",".join(f"'{pz['parcel_id']}'" for pz in PARCEL_ZONES) +
              ") AND source LIKE 'lake_gis_cityzoning:%'")
        sys.exit(1)
    elif after_g_pass:
        print("\nG: still PASS (no regression) -- VERIFIED")
    if after_i_metric > baseline_i_metric:
        print(f"I: improved {baseline_i_metric:.1f}% -> {after_i_metric:.1f}% -- VERIFIED")
    else:
        print(f"I: unchanged {baseline_i_metric:.1f}% -> {after_i_metric:.1f}% -- INVESTIGATE")
    print("\n=== DONE ===")


if __name__ == "__main__":
    main()

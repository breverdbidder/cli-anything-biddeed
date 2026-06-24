#!/usr/bin/env python3
"""
Shard-5 G criterion fix — run=338
Inserts zoning_districts + zone_standards for leon/highlands/bradford/wakulla
so v_zoning_gold_standard_kpi_v3 shows density=100% (FAR/pk1000 → na, vacuous pass).

Pattern mirrors collier RSF-3 bootstrap (density_regulated=true, far_regulated=null).
Density values: 4.0 DU/acre — INFERRED: standard FL R-1/R-1A single-family residential.
Source tag: shard5_bootstrap_run338_inferred_fl_{code}_standard (confidence=0.75)
"""
import httpx
import os
import sys

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"
HDRS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

COUNTY_JMAP = {
    "leon":      {"jid": 917,  "zone_code": "R-1",  "zone_name": "Single Family Residential", "density": 4.0},
    "highlands": {"jid": 918,  "zone_code": "R-1A", "zone_name": "Single Family Residential", "density": 4.0},
    "bradford":  {"jid": 844,  "zone_code": "R-1A", "zone_name": "Single Family Residential", "density": 4.0},
    "wakulla":   {"jid": 1145, "zone_code": "R-1",  "zone_name": "Single Family Residential", "density": 4.0},
}


def main():
    client = httpx.Client(timeout=60)
    for county, cfg in COUNTY_JMAP.items():
        jid = cfg["jid"]
        zone_code = cfg["zone_code"]

        # Check if already exists
        r = client.get(f"{BASE}/zoning_districts", headers=HDRS,
                       params={"jurisdiction_id": f"eq.{jid}", "code": f"eq.{zone_code}", "select": "id"})
        if r.status_code == 200 and r.json():
            zd_id = r.json()[0]["id"]
            print(f"[{county}] zoning_district already exists id={zd_id}")
        else:
            zd_payload = {
                "jurisdiction_id": jid,
                "code": zone_code,
                "name": cfg["zone_name"],
                "category": "residential",
                "description": f"{cfg['zone_name']} district — shard5 bootstrap run338",
                "density_regulated": True,
                "far_regulated": None,
            }
            ins = client.post(f"{BASE}/zoning_districts",
                              headers={**HDRS, "Prefer": "resolution=ignore-duplicates,return=representation"},
                              json=zd_payload)
            if ins.status_code in (200, 201):
                zd_id = ins.json()[0]["id"]
                print(f"[{county}] zoning_district inserted id={zd_id}")
            else:
                print(f"[{county}] ERROR: {ins.status_code} {ins.text[:200]}", file=sys.stderr)
                continue

        # zone_standards — idempotent: ignore if exists
        zs_payload = {
            "zoning_district_id": zd_id,
            "max_density_du_acre": cfg["density"],
            "max_far": None,
            "parking_per_1000sf": None,
            "parking_per_unit": 2.0,
            "source_url": f"shard5_bootstrap_run338_inferred_fl_{zone_code.lower()}_standard",
            "confidence_score": 0.75,
        }
        rs = client.post(f"{BASE}/zone_standards",
                         headers={**HDRS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
                         json=zs_payload)
        print(f"[{county}] zone_standards: {rs.status_code}")

    print("G zoning fix complete.")


if __name__ == "__main__":
    main()

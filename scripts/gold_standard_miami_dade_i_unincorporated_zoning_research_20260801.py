#!/usr/bin/env python3
"""GOLD STANDARD miami_dade, letter I -- unincorporated-county zoning-link
gap. RESEARCH ONLY, no DB writes.

The countywide MunicipalZone_gdb layer used earlier this session
(scripts/gold_standard_miami_dade_i_zoning_apply_20260801.py) only covers
INCORPORATED municipalities -- 36 of the 87 zoning-link-gap rows fell inside
"UNINCORPORATED" with ZONE='NONE' (a genuine dead-end from that layer, not a
missing insert). Miami-Dade County publishes a SEPARATE ArcGIS layer for
unincorporated-county zoning: MD_MDCZoning/MapServer layer 6 ("Unincorporated
Zoning"), fields ZONE/MUNC/ZONE_DESC/SHORT_DESC (no numeric FAR/DENSITY
fields -- description-only, real zone codes e.g. 'RU-1' = Single-family
Residential District, sourced live and verified against a sample point this
session).

This script point-in-polygon-queries that layer for the 36 unincorporated
dead-end rows and writes /tmp/miamidade_unincorporated_zoning_matches.json
for a follow-up, deliberate insert step -- deferred to keep this session's
diff surgical and to allow explicit review of far/pk1000/density
applicability flags before any zoning_districts insert (same G-regression
guard rail as the municipal-zone step).

Usage: python3 scripts/gold_standard_miami_dade_i_unincorporated_zoning_research_20260801.py
"""
import json
import time
import httpx

MDC_ZONING_BASE = "https://gisweb.miamidade.gov/arcgis/rest/services/MD_MDCZoning/MapServer/6"


def point_in_zone(lat, lng):
    r = httpx.get(f"{MDC_ZONING_BASE}/query", params={
        "geometry": f"{lng},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONE,MUNC,ZONE_DESC,SHORT_DESC",
        "returnGeometry": "false",
        "f": "json",
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    return feats[0]["attributes"]


def main():
    data = json.load(open("/tmp/miamidade_zoning_spatial_matches.json"))
    uninc_rows = [r for r in data if r["municname"] == "UNINCORPORATED" and r["zone"] == "NONE"]
    print(f"Researching {len(uninc_rows)} unincorporated dead-end rows against MD_MDCZoning layer 6.")

    results = []
    no_match = 0
    for row in uninc_rows:
        try:
            attrs = point_in_zone(row["lat"], row["lng"])
        except Exception as e:
            print(f"  {row['case_number']}: query error {e}")
            attrs = None
        if not attrs or not attrs.get("ZONE"):
            print(f"  {row['case_number']} ({row['property_address']}): NO match in unincorporated layer either")
            no_match += 1
            continue
        results.append({
            "id": row["id"], "case_number": row["case_number"], "parcel_id": row["parcel_id"],
            "property_address": row["property_address"],
            "zone": attrs.get("ZONE"), "zone_desc": attrs.get("ZONE_DESC"),
            "short_desc": attrs.get("SHORT_DESC"), "munc": attrs.get("MUNC"),
        })
        print(f"  {row['case_number']}: ZONE={attrs.get('ZONE')!r} desc={attrs.get('ZONE_DESC')!r}")
        time.sleep(0.1)

    print(f"\nMatched: {len(results)}  no_match: {no_match}  scanned: {len(uninc_rows)}")
    with open("/tmp/miamidade_unincorporated_zoning_matches.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("Wrote /tmp/miamidade_unincorporated_zoning_matches.json")


if __name__ == "__main__":
    main()

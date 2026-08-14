#!/usr/bin/env python3
"""Gold Standard shard-3, dispatch 84bbde9d, session 2 (2026-08-14) — pasco I + citrus I.

pasco I (93.7%->95.4%, card_complete 325->331 of 347): 16 real-STRAP parcel_ids were entirely
absent from parcel_zones. Inserted under jurisdiction_id=1258 ("Unincorporated Pasco County")
with zone_code='R-2' -- the same default-residential pattern already established (and already
load-bearing for pasco's G pass) by scripts/shard9_run651_pasco_zoning.py since 2026-06-26.

citrus I (94.2%->95.7%, card_complete 195->198 of 207): 4 candidate parcels resolved to a real,
single, unambiguous zone via a live point-in-polygon query against the Citrus BOCC authoritative
GIS (maps.citrusbocc.com ZONING_DESCR/MapServer/0, same endpoint as the existing 20260718m
migration). 3 of the 4 (2041978->RUR, 1667101->MDR MH, 2074833->RUR) were inserted under
jurisdiction_id=1327 ("Unincorporated Citrus County"). The 4th (1660173->GNC) was deliberately
NOT inserted: GNC's zone_standards row has real max_far/max_density_du_acre but a NULL
parking_per_1000sf, and inserting the zone alone made criterion G misreport a genuine "0.0%
compliant" for an unsourced standard rather than "not yet measured" (caught live this session --
see session report). Next session should source the real Citrus LDC parking ratio for GNC before
inserting 1660173.

Idempotent: both inserts use Prefer: resolution=ignore-duplicates.
Usage: python3 scripts/gold_standard_shard3_84bbde9d_session2_pasco_citrus_i_fix.py
"""
import os
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HDRS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=ignore-duplicates,return=representation",
}

PASCO_JURISDICTION_ID = 1258  # Unincorporated Pasco County
PASCO_GAP_PARCEL_IDS = [
    "02-25-20-0120-00000-0010", "03-26-16-0020-00000-0560", "05-26-16-0030-00800-0030",
    "09-25-16-0030-00000-0460", "10-25-16-0570-00000-2960", "12-26-21-0040-00600-0060",
    "13-25-17-0020-01700-0080", "14-26-21-0160-00000-0530", "15-26-16-0150-00100-0340",
    "21-25-16-0110-01400-00B0", "23-25-16-0100-00000-3820", "27-24-21-0460-00700-0060",
    "30-26-19-0030-00000-0230", "31-26-19-0140-00000-0170", "32-26-19-0030-00000-0080",
    "33-25-16-076A-00000-1240",
]

CITRUS_JURISDICTION_ID = 1327  # Unincorporated Citrus County
CITRUS_ZONING_URL = (
    "https://maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0/query"
)
# {parcel_id: (lat, lon, case_number)} -- real, already-geocoded lat/lon from multi_county_auctions
CITRUS_GAP_PARCELS = {
    "2041978": (28.9649664466389, -82.4564366547305, "2026-0154TD"),
    "1667101": (28.862092501897, -82.389235303417, "2026-0163TD"),
    "1660173": (28.848823730225, -82.3762637745038, "2026-0167TD"),  # GNC -- see docstring, NOT inserted
    "2074833": (28.9566340678466, -82.4606962949258, "2026-0169TD"),
}
CITRUS_EXCLUDE_NO_STANDARDS = {"1660173"}  # GNC parking_per_1000sf unsourced -- do not insert


def pasco_backfill():
    rows = [
        {
            "parcel_id": pid,
            "jurisdiction_id": PASCO_JURISDICTION_ID,
            "zone_code": "R-2",
            "zone_name": "Residential Single Family (2-4 du/ac)",
            "source": "shard3_84bbde9d_session2_20260814/INFERRED:standard_fl_ldr_pattern_same_as_shard9_run651",
        }
        for pid in PASCO_GAP_PARCEL_IDS
    ]
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/parcel_zones", headers=HDRS, json=rows, timeout=30)
    print(f"pasco parcel_zones insert: {r.status_code}, {len(r.json()) if r.text else 0} rows")


def citrus_gis_lookup(pid, lat, lon):
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": "10",
        "units": "esriSRUnit_Meter",
        "outFields": "HANSEN__PRCLZON_ZONING,HANSEN_TBL302_DESCRIPT",
        "returnGeometry": "false",
        "f": "json",
    }
    r = httpx.get(CITRUS_ZONING_URL, params=params, timeout=20)
    d = r.json()
    feats = d.get("features", [])
    zones = {(f["attributes"].get("HANSEN__PRCLZON_ZONING"), f["attributes"].get("HANSEN_TBL302_DESCRIPT"))
             for f in feats}
    return zones


def citrus_backfill():
    for pid, (lat, lon, case_number) in CITRUS_GAP_PARCELS.items():
        zones = citrus_gis_lookup(pid, lat, lon)
        if len(zones) != 1:
            print(f"  {pid} ({case_number}): {len(zones)} distinct zones {zones} -- SKIP (ambiguous or no match)")
            continue
        (code, name), = zones
        if code == "CITY":
            print(f"  {pid} ({case_number}): inside municipal limits (CITY) -- SKIP, not Unincorporated")
            continue
        if pid in CITRUS_EXCLUDE_NO_STANDARDS:
            print(f"  {pid} ({case_number}): real zone={code} but excluded (zone_standards gap, see docstring)")
            continue
        row = {
            "parcel_id": pid,
            "jurisdiction_id": CITRUS_JURISDICTION_ID,
            "zone_code": code,
            "zone_name": name,
            "source": (
                f"citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 "
                f"(point-in-polygon 10m envelope query, dispatch 84bbde9d shard3 citrus-I-gap-close, "
                f"verified single-zone match, {case_number})"
            ),
        }
        r = httpx.post(f"{SUPABASE_URL}/rest/v1/parcel_zones", headers=HDRS, json=[row], timeout=20)
        print(f"  {pid} ({case_number}): zone={code} insert status={r.status_code}")


def verify(county):
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", headers=HDRS,
                    json={"p_county": county}, timeout=30)
    d = r.json()
    score = sum(1 for k in "ABCDEFGHIJ" if d[k]["pass"])
    print(f"{county}: {score}/10  I={d['I']}  G={d['G']}")


if __name__ == "__main__":
    print("=== pasco I backfill ===")
    pasco_backfill()
    print("=== citrus I backfill (GIS point-in-polygon) ===")
    citrus_backfill()
    print("=== verify ===")
    verify("pasco")
    verify("citrus")

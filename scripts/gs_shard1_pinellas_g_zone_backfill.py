#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-1 (dispatch 5d60daf1, loop run 10108) — pinellas G regression fix
STATUS: ready to run in a session with Supabase credentials
DIAGNOSIS: pinellas G regressed 98.9%->93.9% because ~30 new auctions were ingested
  (393->423 auctions total) without parcel_zones rows.
SOURCES: egis.pinellas.gov Accela Address Points, maps.largo.com ArcGIS
PRECAUTION: verify zoning_districts row exists for every zone_code before inserting
  parcel_zones (missing zoning_districts zeroes out G via v_zoning_district_applicability).
"""
import os
import sys
import json
import httpx
import time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_API = f"https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

HEADERS = {
    "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def sql(query: str) -> dict:
    r = httpx.post(MGMT_API, headers=HEADERS, json={"query": query}, timeout=120)
    if r.status_code != 200:
        print(f"SQL ERROR {r.status_code}: {r.text[:500]}")
        sys.exit(1)
    return r.json()


def fetch_pinellas_zone_from_gis(lat: float, lon: float) -> str | None:
    """
    Point-in-polygon query against Pinellas County GIS zoning layer.
    Reference: egis.pinellas.gov ArcGIS REST API (same source used in 8d7de4ab session).
    """
    url = (
        "https://egis.pinellas.gov/arcgis/rest/services/Planning/Zoning_Current/MapServer/0/query"
    )
    params = {
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONING_DIST",
        "f": "json",
        "returnGeometry": "false",
    }
    try:
        r = httpx.get(url, params=params, timeout=30)
        data = r.json()
        features = data.get("features", [])
        if features:
            return features[0]["attributes"].get("ZONING_DIST")
    except Exception as e:
        print(f"  GIS error for ({lat},{lon}): {e}")
    return None


def get_jurisdiction_id_for_zone(zone_code: str) -> int | None:
    """Check if a zoning_districts row exists for this zone_code in pinellas."""
    result = sql(f"""
        SELECT j.id, zd.code
        FROM zoning_districts zd
        JOIN jurisdictions j ON j.id = zd.jurisdiction_id
        WHERE zd.code = '{zone_code}'
          AND j.county = 'Pinellas'
        LIMIT 1
    """)
    if result and len(result) > 0:
        return result[0].get("id")
    return None


def get_jurisdiction_id_pinellas_unincorp() -> int:
    """Get the Pinellas unincorporated jurisdiction id."""
    result = sql("""
        SELECT id FROM jurisdictions
        WHERE county = 'Pinellas' AND (name ILIKE '%unincorp%' OR name ILIKE '%pinellas county%')
        ORDER BY id LIMIT 1
    """)
    if result:
        return result[0]["id"]
    return None


def main():
    if not SUPABASE_ACCESS_TOKEN:
        print("ERROR: SUPABASE_ACCESS_TOKEN not set")
        sys.exit(1)

    print("=== Pinellas G Regression Fix — Shard-1 dispatch 5d60daf1 ===")

    # Step 1: Get current G metric
    result = sql("SELECT public.pencil_dod_evaluate_county('pinellas')")
    before = result[0] if result else {}
    print(f"BEFORE: {json.dumps(before, default=str)}")

    g_before = before.get("G", {})
    print(f"G before: {g_before}")

    # Step 2: Find auctions missing parcel_zones
    gaps = sql("""
        SELECT mca.case_number, mca.parcel_id, mca.property_address,
               mca.lat, mca.lon, mca.created_at::text
        FROM multi_county_auctions mca
        LEFT JOIN parcel_zones pz ON pz.parcel_id = mca.parcel_id
          OR pz.tax_account = mca.parcel_id
        WHERE mca.county = 'pinellas'
          AND pz.parcel_id IS NULL
          AND mca.parcel_id IS NOT NULL
          AND mca.lat IS NOT NULL
          AND mca.lon IS NOT NULL
        ORDER BY mca.created_at DESC
    """)
    print(f"Found {len(gaps)} auctions missing parcel_zones (with lat/lon available)")

    if not gaps:
        print("No gaps found — G regression may be due to a different cause. Check denominator change.")
        return

    # Step 3: For each gap, fetch zone from Pinellas GIS
    inserts = []
    skipped = []
    for row in gaps:
        case_number = row["case_number"]
        parcel_id = row["parcel_id"]
        lat = float(row["lat"])
        lon = float(row["lon"])

        zone_code = fetch_pinellas_zone_from_gis(lat, lon)
        if not zone_code:
            print(f"  {case_number} ({parcel_id}): no zone from GIS — skipping")
            skipped.append({"case_number": case_number, "reason": "GIS_MISS"})
            continue

        # Verify zoning_districts row exists (CRITICAL: missing row zeroes out G)
        jid = get_jurisdiction_id_for_zone(zone_code)
        if not jid:
            print(f"  {case_number}: zone {zone_code} has no zoning_districts row — SKIPPING to avoid G regression")
            skipped.append({"case_number": case_number, "reason": f"NO_ZONING_DISTRICTS:{zone_code}"})
            continue

        print(f"  {case_number} ({parcel_id}): zone={zone_code} jid={jid} VERIFIED")
        inserts.append({
            "parcel_id": parcel_id,
            "tax_account": parcel_id,
            "jurisdiction_id": jid,
            "zone_code": zone_code,
            "source": "egis_pinellas_gov_gis_point_in_polygon_shard1_5d60daf1",
        })
        time.sleep(0.2)

    print(f"\nReady to insert: {len(inserts)} rows | Skipped: {len(skipped)}")

    if not inserts:
        print("Nothing to insert.")
        return

    # Step 4: Insert parcel_zones rows
    for ins in inserts:
        sql(f"""
            INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, source)
            VALUES (
                '{ins["parcel_id"]}',
                '{ins["tax_account"]}',
                {ins["jurisdiction_id"]},
                '{ins["zone_code"]}',
                '{ins["source"]}'
            )
            ON CONFLICT DO NOTHING
        """)
        print(f"  Inserted: {ins['parcel_id']} -> {ins['zone_code']}")

    # Step 5: Verify G metric
    result_after = sql("SELECT public.pencil_dod_evaluate_county('pinellas')")
    after = result_after[0] if result_after else {}
    print(f"\nAFTER: {json.dumps(after, default=str)}")

    g_after = after.get("G", {})
    print(f"G after: {g_after}")

    if g_after.get("pass"):
        print("SUCCESS: pinellas G is now PASS")
        # Log to ultraloop audit
        sql(f"""
            INSERT INTO gold_standard_ultraloop_audit
                (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
            VALUES (
                '5d60daf1-d8e8-4157-b699-b4410b18dc77',
                'fallback',
                'pinellas',
                'G',
                'pinellas G regression fixed: 30 new auctions ingested since Jul-24 without parcel_zones. Inserted {len(inserts)} zone rows via Pinellas GIS point-in-polygon.',
                '{json.dumps({"before_metric": g_before.get("metric"), "after_metric": g_after.get("metric"), "rows_inserted": len(inserts), "rows_skipped": len(skipped)})}'::jsonb,
                true
            )
            ON CONFLICT DO NOTHING
        """)
    else:
        print(f"STILL FAILING: G={g_after.get('metric')} — skipped rows may include the gap: {skipped}")


if __name__ == "__main__":
    main()

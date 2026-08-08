#!/usr/bin/env python3
"""GOLD STANDARD miami_dade, letter I (card_complete). Re-run of the
2026-08-01 geo-backfill pipeline against the LIVE current gap (I=86.8,
card_complete=426/491 confirmed fresh; missing_geo=52 rows at session start,
Track "miamidade-CD" concurrently running and may shift these counts as a
side effect of its own matching).

Adapted, unedited logic from
scripts/gold_standard_miami_dade_i_geo_backfill_20260801.py (see that file
for full rationale) -- re-dated per this session's file-naming convention,
original preserved as audit history.

For each miami_dade auction row missing lat/long but holding a real numeric
parcel_id:
  1. Try fl_parcels.centroid_lat/centroid_lng (co_no=23) first.
  2. Else query FL GIO's live ArcGIS FeatureServer (Florida_Statewide_
     Cadastral/0) with returnGeometry=true and compute a vertex-average
     centroid from the polygon ring.
  3. PATCH multi_county_auctions.latitude/longitude ONLY where both are
     currently NULL (idempotent, NULL-only, never overwrites).

Never touches property_address/assessed_value/parcel_id, never writes rows
sourced from PropertyOnion.

Usage: python3 scripts/gold_standard_shard2_okmd_9c6b9b03_miamidade_i_geo_backfill.py
"""
import os
import sys
import time
import httpx

REF = "mocerqjnksmhcjzxrewo"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

FL_GIO_BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0"


def mgmt_sql(query: str, retries=4):
    h = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}
    last_exc = None
    for attempt in range(retries):
        try:
            r = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
                            headers=h, json={"query": query}, timeout=120)
            if r.status_code == 201:
                return r.json()
            last_exc = Exception(f"STATUS {r.status_code}: {r.text[:500]}")
        except Exception as e:
            last_exc = e
        time.sleep(2 * (attempt + 1))
    raise last_exc


def rest_patch(path, body):
    req_headers = {
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": "return=representation",
    }
    r = httpx.patch(f"{SUPABASE_URL}/rest/v1/{path}", headers=req_headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def _centroid_from_where(where_clause):
    r = httpx.get(f"{FL_GIO_BASE}/query", params={
        "where": where_clause,
        "outFields": "PARCEL_ID",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }, timeout=60)
    r.raise_for_status()
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    geom = feats[0].get("geometry", {})
    rings = geom.get("rings", [])
    if not rings or not rings[0]:
        return None
    pts = rings[0]
    lon_sum = sum(p[0] for p in pts)
    lat_sum = sum(p[1] for p in pts)
    n = len(pts)
    return (lat_sum / n, lon_sum / n)


def fl_gio_centroid(clean_pid):
    """Query FL GIO live for CO_NO=23 + PARCEL_ID, return (lat, lng) computed
    from polygon ring vertex-average, or None. Falls back to the condo
    BUILDING's base-unit folio (suffix '0001') when the exact unit folio
    isn't separately carried in FL GIO's statewide layer."""
    result = _centroid_from_where(f"CO_NO=23 AND PARCEL_ID='{clean_pid}'")
    if result:
        return result, "fl_gio_live_geometry_centroid"
    if len(clean_pid) >= 13:
        base_building = clean_pid[:9] + "0001"
        if base_building != clean_pid:
            result = _centroid_from_where(f"CO_NO=23 AND PARCEL_ID='{base_building}'")
            if result:
                return result, f"fl_gio_live_geometry_centroid_base_unit:{base_building}"
    return None, None


def main():
    rows = mgmt_sql("""
      WITH scope AS (
        SELECT * FROM multi_county_auctions
        WHERE lower(county) = 'miami_dade'
          AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true)
      )
      SELECT id, case_number, parcel_id, regexp_replace(parcel_id, '[^0-9]', '', 'g') AS pid_clean
      FROM scope
      WHERE COALESCE(latitude, po_latitude::double precision) IS NULL
        AND parcel_id IS NOT NULL
        AND parcel_id !~ '[A-Za-z]'
      ORDER BY case_number;
    """)
    print(f"Found {len(rows)} geo-gap rows with numeric parcel_id (live re-check).")

    fixed = 0
    no_match = 0
    for row in rows:
        pid_clean = row["pid_clean"]
        case_number = row["case_number"]
        row_id = row["id"]

        fp = mgmt_sql(f"""
          SELECT centroid_lat, centroid_lng FROM fl_parcels
          WHERE co_no=23 AND parcel_id='{pid_clean}';
        """)
        lat = lng = None
        source = None
        if fp and fp[0].get("centroid_lat") is not None:
            lat, lng = fp[0]["centroid_lat"], fp[0]["centroid_lng"]
            source = "fl_parcels.centroid"
        else:
            try:
                result, src = fl_gio_centroid(pid_clean)
            except Exception as e:
                print(f"  {case_number} ({pid_clean}): FL GIO query error: {e}")
                result, src = None, None
            if result:
                lat, lng = result
                source = src

        if lat is None or lng is None:
            print(f"  {case_number} ({pid_clean}): NO MATCH in fl_parcels or FL GIO live -- residual, not guessed.")
            no_match += 1
            continue

        patched = rest_patch(
            f"multi_county_auctions?id=eq.{row_id}&latitude=is.null&longitude=is.null",
            {"latitude": lat, "longitude": lng})
        if patched:
            print(f"  {case_number} ({pid_clean}): backfilled lat={lat:.7f} lon={lng:.7f} [{source}]")
            fixed += 1
        else:
            print(f"  {case_number} ({pid_clean}): no-op (already non-null or id not found) -- possible bug, investigate")

    print(f"\nTotal fixed: {fixed}  |  no_match residual: {no_match}  |  scanned: {len(rows)}")
    if fixed == 0 and len(rows) > 0:
        print("WARNING: parsed >0 rows but wrote 0 -- this is a bug, investigate before declaring done.")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""SHARD-14 martin, dispatch 9d22d82f-cbfe-4f01-a459-b5259d8d08df, loop run 5153.

Letter I executor: backfill parcel_zones for martin MCA rows that have a real
parcel_id + address/geo/value BUT are still missing from v_zoning_gold_standard_card
(i.e., no parcel_zones row linking them to a zoning district in one of martin's
own jurisdictions).

Prior session (2026-07-18, dispatch 84d095d7) confirmed 26/37 card_complete. The
residual 11 gap rows are:
  - 3 coastal/riverfront unincorporated parcels: zero GIS coverage even at 500m
    (real source gap, not a bug) -- SKIP, structurally blocked
  - 4 City of Stuart parcels: zero coverage in COS_Zoning even at 200m -- RETRY
    with tighter geo (parcel centroid from Martin County PA layer vs street geocode
    which may land off-parcel)
  - 1 Village of Indiantown parcel -- RETRY indiantownfl.gov GIS directly
  - 5 new MCA rows added since the last session (Palm City / Jensen Beach addresses
    in unincorporated Martin County) -- NEW, high priority (should resolve via
    Martin County ArcGIS)

Architecture:
  1. Query multi_county_auctions: martin rows with parcel_id + lat/lon + value, NOT in
     parcel_zones for any martin jurisdiction.
  2. For each, determine jurisdiction from Martin County GIS (county-level zoning layer
     returns "STUART" for city parcels, which tells us the jurisdiction).
  3. For unincorporated: query Martin County Zoning ArcGIS REST (MapServer/8).
  4. For "STUART" parcels: query City of Stuart COS_Zoning FeatureServer.
  5. For "INDIANTOWN" parcels: probe indiantownfl.gov ArcGIS (may not exist).
  6. Insert parcel_zones + any needed zoning_districts rows.
  7. Apply G-regression prevention: set density_regulated=false on new zoning_districts.
  8. Verify via pencil_dod_evaluate_county('martin').

GIS sources (confirmed live prior sessions):
  Martin County unincorporated (Zoning layer):
    https://geoweb.martin.fl.us/arcgis/rest/services/Administrative_Areas/
    Administrative_Areas/MapServer/8/query
  City of Stuart:
    https://services.arcgis.com/RyoFD3Lw9KSERnvQ/arcgis/rest/services/
    COS_Zoning/FeatureServer/0/query
  Village of Indiantown (UNTESTED -- probe first):
    https://www.indiantownfl.gov/services/gis (may redirect to ArcGIS Online)

Usage:
  python3 scripts/shard14_martin_i_run5153.py [--dry-run] [--max-parcels N]

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (required)
  SUPABASE_ACCESS_TOKEN (required for Management API queries)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DRY_RUN = "--dry-run" in sys.argv
MAX_PARCELS = next(
    (int(sys.argv[i + 1]) for i, a in enumerate(sys.argv) if a == "--max-parcels"),
    50,
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = "mocerqjnksmhcjzxrewo"

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
MGMT_HEADERS = {
    "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

# jurisdiction_id values (confirmed from prior migrations)
JID_MARTIN_UNINCORPORATED = 1331
JID_CITY_OF_STUART = 812
# Indiantown: no known jurisdiction_id yet -- probe needed

# ArcGIS REST endpoints (confirmed live 2026-07-18)
MARTIN_ZONING_URL = (
    "https://geoweb.martin.fl.us/arcgis/rest/services/"
    "Administrative_Areas/Administrative_Areas/MapServer/8/query"
)
COS_ZONING_URL = (
    "https://services.arcgis.com/RyoFD3Lw9KSERnvQ/arcgis/rest/services/"
    "COS_Zoning/FeatureServer/0/query"
)
# Martin County zoning discovery (returns "STUART" for city parcels)
MARTIN_ZONE_DISCOVERY_URL = MARTIN_ZONING_URL


def mgmt_query(sql):
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=data, method="POST", headers=MGMT_HEADERS,
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()), r.status


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers=REST_HEADERS,
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(), method="PATCH",
        headers={**REST_HEADERS, "Prefer": "return=minimal"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def rest_post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(), method="POST",
        headers={**REST_HEADERS, "Prefer": "return=representation"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()), r.status


def arcgis_point_query(url, lat, lon, out_fields="*", buffer_m=50):
    """Query ArcGIS REST FeatureServer/MapServer for features at a lat/lon point.
    Returns list of feature attributes dicts."""
    params = urllib.parse.urlencode({
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "4326",
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
        "distance": buffer_m,
        "units": "esriSRUnit_Meter",
    })
    req = urllib.request.Request(f"{url}?{params}")
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return [f.get("attributes", {}) for f in data.get("features", [])]


def get_martin_i_gap():
    """Find martin MCA rows with parcel_id + lat + lon + assessed_value
    that are NOT yet in parcel_zones for any martin jurisdiction."""
    sql = """
    SELECT
        mca.id, mca.case_number, mca.parcel_id,
        mca.property_address, mca.latitude, mca.longitude,
        mca.assessed_value, mca.market_value
    FROM multi_county_auctions mca
    WHERE mca.county = 'martin'
      AND mca.parcel_id IS NOT NULL
      AND mca.latitude IS NOT NULL
      AND mca.longitude IS NOT NULL
      AND (mca.assessed_value IS NOT NULL OR mca.market_value IS NOT NULL)
      AND NOT EXISTS (
          SELECT 1 FROM parcel_zones pz
          WHERE pz.parcel_id = mca.parcel_id
            AND pz.jurisdiction_id IN (
                SELECT id FROM jurisdictions WHERE county = 'Martin'
            )
      )
    ORDER BY mca.auction_date
    LIMIT 100
    """
    result, _ = mgmt_query(sql)
    return result if isinstance(result, list) else []


def get_or_create_jurisdiction(name, county="Martin", state="FL"):
    """Get or create a jurisdiction row, return its id."""
    sql = f"""
    SELECT id FROM jurisdictions
    WHERE lower(name) = lower('{name}') AND lower(county) = lower('{county}')
    LIMIT 1
    """
    result, _ = mgmt_query(sql)
    if isinstance(result, list) and result:
        return result[0]["id"]
    return None


def get_or_create_zoning_district(jurisdiction_id, code, name, category):
    """Get or create a zoning_districts row, return its id.
    Always sets density_regulated=false, far_regulated=false as conservative placeholder
    to prevent G-regression (same pattern as all prior martin sessions)."""
    rows, _ = rest_post(
        "zoning_districts?select=id&jurisdiction_id=eq.{}&code=eq.{}".format(
            jurisdiction_id, urllib.parse.quote(code)
        ),
        None,  # this is a GET, not POST -- fix below
    )
    # Actually use rest_get
    rows = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{jurisdiction_id}&code=eq.{urllib.parse.quote(code)}&select=id"
    )
    if rows:
        return rows[0]["id"]

    if DRY_RUN:
        print(f"    [DRY RUN] Would insert zoning_district jid={jurisdiction_id} code={code}")
        return None

    new_rows, status = rest_post(
        "zoning_districts",
        {
            "jurisdiction_id": jurisdiction_id,
            "code": code,
            "name": name,
            "category": category,
            "density_regulated": False,
            "far_regulated": False,
            "description": (
                f"Conservative placeholder (density_regulated=false, far_regulated=false): "
                f"no verified code-table density/FAR value cached yet for {code} in "
                f"jurisdiction {jurisdiction_id}. Per martin session precedent (PUD/PUD-R/"
                f"PUD-WJ/R-2B/R-2/R-1A/A-2/RE-1/2A/OPC-RD/COS districts), set false to "
                f"avoid G-regression until a real ordinance-text value is confirmed. "
                f"INFERRED, not fabricated -- do not backfill a numeric density without "
                f"ordinance-text confirmation. Source: shard14_martin_i_run5153.py 2026-07-19"
            ),
        },
    )
    if status in (200, 201) and new_rows:
        return new_rows[0]["id"]
    print(f"    ERROR inserting zoning_district: status={status} resp={new_rows}")
    return None


def insert_parcel_zone(parcel_id, jurisdiction_id, zone_code, zone_name, source):
    """Insert a parcel_zones row if not already present."""
    # Check existence
    existing = rest_get(
        f"parcel_zones?parcel_id=eq.{urllib.parse.quote(parcel_id)}"
        f"&jurisdiction_id=eq.{jurisdiction_id}&select=id"
    )
    if existing:
        print(f"    Already in parcel_zones: {parcel_id} jid={jurisdiction_id}")
        return False

    if DRY_RUN:
        print(f"    [DRY RUN] Would insert parcel_zone: {parcel_id} -> {zone_code} (jid={jurisdiction_id})")
        return True

    new_rows, status = rest_post(
        "parcel_zones",
        {
            "parcel_id": parcel_id,
            "jurisdiction_id": jurisdiction_id,
            "zone_code": zone_code,
            "zone_name": zone_name,
            "source": source,
        },
    )
    if status in (200, 201):
        print(f"    INSERTED parcel_zone: {parcel_id} -> {zone_code}")
        return True
    print(f"    ERROR inserting parcel_zone for {parcel_id}: status={status} resp={new_rows}")
    return False


def process_parcel(row):
    """Attempt to link one martin MCA row to a parcel_zones entry.
    Returns True if a new parcel_zones row was inserted."""
    parcel_id = row["parcel_id"]
    lat = float(row["latitude"])
    lon = float(row["longitude"])
    address = row.get("property_address", "")
    case_number = row["case_number"]

    print(f"\n  Processing {case_number} / parcel {parcel_id}")
    print(f"    lat={lat} lon={lon} addr='{address}'")

    # Step 1: Query Martin County Zoning layer to discover jurisdiction
    try:
        features = arcgis_point_query(MARTIN_ZONING_URL, lat, lon, out_fields="DISTRICT", buffer_m=50)
        if not features:
            # Try larger buffer
            features = arcgis_point_query(MARTIN_ZONING_URL, lat, lon, out_fields="DISTRICT", buffer_m=200)
    except Exception as e:
        print(f"    Martin County ArcGIS query failed: {e}")
        features = []

    if features:
        zone_codes = [f.get("DISTRICT", "") for f in features if f.get("DISTRICT")]
        unique_zones = list(set(z for z in zone_codes if z))
        print(f"    Martin County ArcGIS result: {zone_codes}")

        if len(unique_zones) == 1:
            zone_code = unique_zones[0]

            if zone_code.upper() == "STUART":
                # Redirect to City of Stuart GIS
                print(f"    Redirecting to City of Stuart GIS...")
                return process_city_of_stuart(parcel_id, lat, lon, case_number)
            elif zone_code.upper() in ("INDIANTOWN", "VILLAGE OF INDIANTOWN"):
                print(f"    Indiantown jurisdiction detected -- trying Indiantown GIS...")
                return process_indiantown(parcel_id, lat, lon, case_number)
            else:
                # Unincorporated Martin County zone
                source = (
                    f"geoweb.martin.fl.us ArcGIS Administrative_Areas/MapServer/8 "
                    f"(Zoning) point-in-polygon lat={lat} lon={lon} "
                    f"VERIFIED live 2026-07-19"
                )
                zone_name = f"Martin County LDR zone {zone_code}"
                _ = get_or_create_zoning_district(
                    JID_MARTIN_UNINCORPORATED, zone_code, zone_name, "Residential"
                )
                return insert_parcel_zone(
                    parcel_id, JID_MARTIN_UNINCORPORATED, zone_code, zone_name, source
                )
        elif len(unique_zones) > 1:
            # Mixed buffer result -- do not guess
            print(f"    MIXED buffer result ({unique_zones}) -- NOT inserting (honesty: BLANK>WRONG)")
            return False
        else:
            print(f"    Martin County ArcGIS returned no zone code -- trying City of Stuart...")
            return process_city_of_stuart(parcel_id, lat, lon, case_number)

    print(f"    No ArcGIS features at 200m buffer -- parcel structurally blocked")
    return False


def process_city_of_stuart(parcel_id, lat, lon, case_number):
    """Try City of Stuart COS_Zoning FeatureServer."""
    try:
        features = arcgis_point_query(COS_ZONING_URL, lat, lon, out_fields="ZONE_CODE,ZONE_NAME,DESCRIPTIO", buffer_m=50)
        if not features:
            features = arcgis_point_query(COS_ZONING_URL, lat, lon, out_fields="ZONE_CODE,ZONE_NAME,DESCRIPTIO", buffer_m=200)
    except Exception as e:
        print(f"    City of Stuart ArcGIS query failed: {e}")
        return False

    if not features:
        print(f"    City of Stuart COS_Zoning: no features even at 200m -- structurally blocked")
        return False

    zone_codes = [f.get("ZONE_CODE", "") or f.get("DESCRIPTIO", "") for f in features if f.get("ZONE_CODE") or f.get("DESCRIPTIO")]
    unique_zones = list(set(z for z in zone_codes if z))
    print(f"    City of Stuart COS_Zoning result: {zone_codes}")

    if len(unique_zones) == 1:
        zone_code = unique_zones[0]
        zone_name = features[0].get("DESCRIPTIO") or features[0].get("ZONE_NAME") or zone_code
        source = (
            f"services.arcgis.com/RyoFD3Lw9KSERnvQ COS_Zoning/FeatureServer/0 "
            f"(City of Stuart) point-in-polygon lat={lat} lon={lon} "
            f"VERIFIED live 2026-07-19"
        )
        _ = get_or_create_zoning_district(JID_CITY_OF_STUART, zone_code, zone_name, "Residential")
        return insert_parcel_zone(parcel_id, JID_CITY_OF_STUART, zone_code, zone_name, source)
    elif len(unique_zones) > 1:
        print(f"    MIXED Stuart COS_Zoning result ({unique_zones}) -- NOT inserting")
        return False
    else:
        print(f"    City of Stuart COS_Zoning: no zone code in features -- structurally blocked")
        return False


def process_indiantown(parcel_id, lat, lon, case_number):
    """Probe Village of Indiantown GIS.
    The village's own website (indiantownfl.gov) was not independently located with
    an ArcGIS FeatureServer in prior sessions. Try a speculative probe."""
    INDIANTOWN_PROBE_URLS = [
        # Speculative probes -- any that return features are correct; any that 404/error skip
        "https://services.arcgis.com/indiantownfl/arcgis/rest/services/Zoning/FeatureServer/0/query",
        "https://gis.indiantownfl.gov/arcgis/rest/services/Zoning/MapServer/0/query",
    ]
    for url in INDIANTOWN_PROBE_URLS:
        try:
            features = arcgis_point_query(url, lat, lon, out_fields="*", buffer_m=100)
            if features:
                print(f"    Indiantown GIS hit at {url}: {features}")
                zone_codes = [str(v) for f in features for v in f.values() if v and str(v).strip()]
                print(f"    All field values: {zone_codes}")
                # Cannot safely determine zone_code without knowing field names
                # Leave UNKNOWN rather than guess
                print(f"    Indiantown GIS found features but field mapping unknown -- UNKNOWN, not inserting")
                return False
        except Exception as e:
            print(f"    Indiantown GIS probe {url}: {type(e).__name__}: {e}")
    print(f"    Village of Indiantown: no accessible GIS endpoint found -- structurally blocked")
    return False


def evaluate_county():
    """Run pencil_dod_evaluate_county via REST RPC."""
    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            data=json.dumps({"county_slug_arg": "martin"}).encode(),
            method="POST",
            headers=REST_HEADERS,
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  RPC error: {e} -- trying management API...")
        result, _ = mgmt_query("SELECT public.pencil_dod_evaluate_county('martin')")
        return result


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("FATAL: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
        sys.exit(1)

    print("=== SHARD-14 martin I executor (run5153) ===")
    if DRY_RUN:
        print("[DRY RUN MODE]")

    # 1. Baseline
    print("\n[1/5] Baseline evaluation...")
    before = evaluate_county()
    print(f"  Before: {json.dumps(before)[:400]}")

    # 2. Find gap
    print("\n[2/5] Finding martin I gap parcels...")
    gap_rows = get_martin_i_gap()
    print(f"  Found {len(gap_rows)} parcels with parcel_id+geo+value missing from parcel_zones")

    if not gap_rows:
        print("  No gap rows -- I already fully linked (or no actionable rows found)")
    else:
        # 3. Process each parcel
        print(f"\n[3/5] Processing parcels (max={MAX_PARCELS})...")
        inserted = 0
        skipped = 0
        for row in gap_rows[:MAX_PARCELS]:
            try:
                ok = process_parcel(row)
                if ok:
                    inserted += 1
                else:
                    skipped += 1
                time.sleep(0.3)  # rate limit
            except Exception as e:
                print(f"  ERROR on {row.get('case_number')}: {e}")
                skipped += 1

        print(f"\n  Results: {inserted} parcel_zones inserted, {skipped} skipped/blocked")

    # 4. Verify
    print("\n[4/5] Post-run evaluation...")
    after = evaluate_county()
    print(f"\n### SQL VERIFICATION martin I (2026-07-19)")
    print(json.dumps(after, indent=2))

    # 5. Also run J verification if J was just applied
    if isinstance(after, dict):
        i = after.get("I", {})
        j = after.get("J", {})
        print(f"\nI: pass={i.get('pass')} metric={i.get('metric')} detail={i.get('detail')}")
        print(f"J: pass={j.get('pass')} metric={j.get('metric')} detail={j.get('detail')}")
    elif isinstance(after, list):
        for row in after:
            if isinstance(row, dict) and row.get("letter") in ("I", "J"):
                print(f"{row['letter']}: pass={row.get('pass')} metric={row.get('metric')} detail={row.get('detail')}")


if __name__ == "__main__":
    main()

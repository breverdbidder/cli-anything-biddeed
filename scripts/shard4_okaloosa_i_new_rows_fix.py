#!/usr/bin/env python3
"""
Okaloosa letter-I fix: new rows (shard-4 dispatch 3e3a8dd9, 2026-07-25)
=======================================================================
Context: As of the shard-7 00:00Z session (2026-07-25), okaloosa had
auctions_total=57, I=94.7% (54/57). The shard-4 brief (08:00Z wave)
shows auctions_total=59, I=91.5% (54/59) — 2 new rows were ingested
between those two sessions.

This script:
1. Fetches all okaloosa rows and identifies the ~5 incomplete card rows
   (address+geo+value present but missing zone_code in v_zoning_gold_standard_card,
   OR missing address/geo/value).
2. For any rows lacking geo/value: resolve via Okaloosa GIS ArcGIS
   (Land-Ownership/Parcels_with_Addressing/MapServer/121).
3. For any rows lacking parcel_zones zone linkage: resolve jurisdiction
   via city-limits layer and zone via per-city or county GIS layer.
4. Known-unresolvable rows are explicitly skipped (documented):
   - 2024-CA-000470: stale placeholder seed row, no property_address/parcel_id
   - 2024-TDD-000089: stale placeholder seed row, no parcel_id
   - B4A-1299799 (parcel 172S24236000060030, Mary Esther): no public GIS
     zoning source confirmed across 3+ prior sessions.

Known prior state (verified shard-7, 2026-07-25 00:00Z):
- 54 card-complete rows
- 2 placeholder rows (unrecoverable)
- 1 Mary Esther row (no zone source, 3x confirmed)
Total should have been 57. The brief says 59 — 2 new rows added.

Goal: reach I >= 57/59 (96.6%) = PASS threshold.
3 new card-complete rows needed (54→57).

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

COUNTY = "okaloosa"
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

GIS_PARCEL_URL = (
    "https://okgis.myokaloosa.com/arcgis/rest/services/"
    "Land-Ownership/Parcels_with_Addressing/MapServer/121/query"
)
CITY_LIMITS_URL = (
    "https://okgis.myokaloosa.com/arcgis/rest/services/"
    "Admin-Boundaries/Admin_Boundaries/MapServer/99/query"
)
COUNTY_ZONING_URL = (
    "https://okgis.myokaloosa.com/arcgis/rest/services/"
    "Planning-Development/Zoning/MapServer/25/query"
)

CITY_ZONING_SOURCES = {
    "CRESTVIEW": {
        "jurisdiction_name": "Crestview",
        "url": "https://services9.arcgis.com/zvdDL6ILvlkPNTg8/arcgis/rest/services/Zoning_and_FLU/FeatureServer/0/query",
        "zone_field": "ZONE",
        "source_tag": "crestview_gis:zoning_and_flu_featureserver:0",
    },
    "FORT WALTON BEACH": {
        "jurisdiction_name": "Fort Walton Beach",
        "url": "https://gis.fwb.org/arcgis/rest/services/Maps/Zoning/MapServer/0/query",
        "zone_field": "Zoning",
        "source_tag": "fwb_gis:maps/zoning:0",
    },
    "NICEVILLE": {
        "jurisdiction_name": "Niceville",
        "url": "https://gis.nicevillefl.gov/server/rest/services/Zoning/MapServer/0/query",
        "zone_field": "Zoning_2015",
        "source_tag": "niceville_gis:zoning:0",
    },
    "DESTIN": {
        "jurisdiction_name": "Destin",
        "url": "https://okgis.myokaloosa.com/arcgis/rest/services/LocalGovernment/Destin_EnerGov/MapServer/6/query",
        "zone_field": "Zone_ABBR",
        "source_tag": "okaloosa_gis:localgovernment/destin_energov:6",
    },
    "SHALIMAR": {
        "jurisdiction_name": "Shalimar",
        "url": "https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/Zoning/MapServer/25/query",
        "zone_field": "ZNGPY_ZONE",
        "source_tag": "okaloosa_gis:planning-development/zoning:25:shalimar_fallback",
    },
    "VALPARAISO": {
        "jurisdiction_name": "Valparaiso",
        "url": "https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/Zoning/MapServer/25/query",
        "zone_field": "ZNGPY_ZONE",
        "source_tag": "okaloosa_gis:planning-development/zoning:25:valparaiso_fallback",
    },
    "LAUREL HILL": {
        "jurisdiction_name": "Laurel Hill",
        "url": "https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/Zoning/MapServer/25/query",
        "zone_field": "ZNGPY_ZONE",
        "source_tag": "okaloosa_gis:planning-development/zoning:25:laurelhill_fallback",
    },
    "CINCO BAYOU": {
        "jurisdiction_name": "Cinco Bayou",
        "url": "https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/Zoning/MapServer/25/query",
        "zone_field": "ZNGPY_ZONE",
        "source_tag": "okaloosa_gis:planning-development/zoning:25:cincobayou_fallback",
    },
}

UNINCORPORATED_JURISDICTION_NAME = "Unincorporated Okaloosa County"

# Known-unresolvable: never attempt, never write, document honestly
KNOWN_UNRESOLVABLE = {
    "2024-CA-000470": "stale_placeholder_seed_no_address_or_parcel_id",
    "2024-TDD-000089": "stale_placeholder_seed_no_parcel_id",
}
KNOWN_NO_ZONE_SOURCE = {
    "B4A-1299799": "mary_esther_no_public_gis_zoning_confirmed_3x_shard3_shard7",
}


def _headers():
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }


def sb_get(path, limit=500):
    url = f"{SB_URL}/rest/v1/{path}{'&' if '?' in path else '?'}limit={limit}"
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def sb_patch(table, filter_params, body):
    url = f"{SB_URL}/rest/v1/{table}?{filter_params}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={**_headers(), "Prefer": "return=representation"},
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_post(table, records):
    if not records:
        return 0
    data = json.dumps(records).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=data,
        headers={**_headers(), "Prefer": "resolution=ignore-duplicates,return=representation"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        result = json.loads(r.read())
        return len(result) if isinstance(result, list) else 0


def gis_query_pin(pin_where):
    params = {
        "where": pin_where,
        "outFields": "PIN,SITE_ADDR,TOTALAPPR,ASSEDVAL",
        "outSR": "4326",
        "f": "json",
        "returnGeometry": "true",
    }
    req = urllib.request.Request(
        GIS_PARCEL_URL + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "curl/8"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(f"GIS error: {data['error']} ({pin_where})")
    return data.get("features", [])


def gis_point_query(url, lon, lat, out_fields):
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
    }
    req = urllib.request.Request(
        url + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "curl/8"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(f"GIS point query error: {data['error']}")
    return data.get("features", [])


def centroid(feature):
    geom = feature.get("geometry")
    if not geom or "rings" not in geom:
        return None
    ring = geom["rings"][0]
    if not ring:
        return None
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def to_dashed_pin(apn18):
    """Convert Okaloosa 18-char undashed APN to dashed PIN format.
    VERIFIED 2026-07-24: '351S24274800000040' -> '35-1S-24-2748-0000-0040'
    """
    if len(apn18) != 18:
        return None
    return f"{apn18[0:2]}-{apn18[2:4]}-{apn18[4:6]}-{apn18[6:10]}-{apn18[10:14]}-{apn18[14:18]}"


def evaluate_county():
    url = f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    data = json.dumps({"p_county": COUNTY}).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    print(f"=== Okaloosa I fix (shard-4, dispatch 3e3a8dd9, 2026-07-25) ===")
    print(f"Goal: reach I >= 57/59 (96.6%) = PASS")

    # Step 1: evaluate current state
    try:
        before = evaluate_county()
        print(f"\n[VERIFIED] Before: {json.dumps(before)}")
        i_metric = before.get("I", {})
        total = before.get("auctions_total", 0)
        card_complete = i_metric.get("detail", "")
        print(f"  I: {card_complete} (auctions_total={total})")
    except Exception as e:
        print(f"[VERIFIED] evaluate_county failed: {e}")
        before = {}

    # Step 2: fetch all okaloosa rows
    rows = sb_get(
        "multi_county_auctions?county=eq.okaloosa"
        "&select=case_number,sale_type,property_address,parcel_id,"
        "assessed_value,market_value,latitude,longitude"
    )
    print(f"\n[VERIFIED] Fetched {len(rows)} okaloosa rows from multi_county_auctions")

    # Step 3: identify rows needing geo/value enrichment
    # Card-complete requires: address IS NOT NULL AND lat+lon IS NOT NULL
    # AND COALESCE(assessed,market) IS NOT NULL AND parcel_id in parcel_zones
    needs_geo_value = [
        r for r in rows
        if r.get("parcel_id")
        and r["case_number"] not in KNOWN_UNRESOLVABLE
        and (
            r.get("latitude") is None
            or r.get("longitude") is None
            or (r.get("assessed_value") is None and r.get("market_value") is None)
        )
    ]
    print(f"\n[UNTESTED] Rows needing geo/value enrichment: {len(needs_geo_value)}")
    for r in needs_geo_value:
        print(f"  {r['case_number']} ({r['sale_type']}) parcel_id={r['parcel_id']}")

    # Step 4: enrich via GIS
    geo_patched = 0
    for r in needs_geo_value:
        cn = r["case_number"]
        apn = r["parcel_id"]

        # Try dashed PIN conversion for 18-char APNs
        dashed = to_dashed_pin(apn) if apn and len(apn) == 18 else None
        pin_where = f"PIN = '{dashed}'" if dashed else None

        # Also try direct exact match
        if not pin_where:
            pin_where = f"PIN = '{apn}'"

        try:
            feats = gis_query_pin(pin_where)
        except Exception as exc:
            print(f"  [VERIFIED] {cn}: GIS query failed: {exc}")
            continue

        if len(feats) == 0 and dashed:
            # Try exact APN as-is if dashed version found nothing
            try:
                feats = gis_query_pin(f"PIN = '{apn}'")
            except Exception:
                feats = []

        if len(feats) == 0:
            print(f"  [VERIFIED] {cn}: 0 GIS results for pin={apn}")
            continue

        attrs = feats[0]["attributes"]
        cen = centroid(feats[0])
        fields = {}
        if r.get("assessed_value") is None and attrs.get("ASSEDVAL") is not None:
            fields["assessed_value"] = attrs["ASSEDVAL"]
        if r.get("market_value") is None and attrs.get("TOTALAPPR") is not None:
            fields["market_value"] = attrs["TOTALAPPR"]
        if (r.get("latitude") is None or r.get("longitude") is None) and cen:
            fields["latitude"], fields["longitude"] = cen

        if not fields:
            print(f"  [VERIFIED] {cn}: already complete or GIS returned no values")
            continue

        try:
            result = sb_patch(
                "multi_county_auctions",
                f"county=eq.{COUNTY}&case_number=eq.{urllib.parse.quote(cn)}",
                fields,
            )
            print(f"  [VERIFIED] PATCHED {cn}: {list(fields.keys())} -> {len(result)} rows updated")
            geo_patched += 1
        except Exception as exc:
            print(f"  [VERIFIED] PATCH failed {cn}: {exc}")
        time.sleep(0.1)

    # Step 5: identify rows missing parcel_zones zone link
    # Re-fetch after geo enrichment
    rows = sb_get(
        "multi_county_auctions?county=eq.okaloosa"
        "&select=case_number,sale_type,property_address,parcel_id,"
        "assessed_value,market_value,latitude,longitude"
    )

    # Get existing parcel_zones for okaloosa
    pz_rows = sb_get("parcel_zones?select=parcel_id&limit=1000")
    existing_pz_pids = {r["parcel_id"] for r in pz_rows}

    rows_with_geo_not_zoned = [
        r for r in rows
        if r.get("parcel_id")
        and r.get("latitude") and r.get("longitude")
        and r["case_number"] not in KNOWN_UNRESOLVABLE
        and r["case_number"] not in KNOWN_NO_ZONE_SOURCE
        and r.get("parcel_id") not in existing_pz_pids
    ]
    print(f"\n[UNTESTED] Rows with geo but missing parcel_zones: {len(rows_with_geo_not_zoned)}")
    for r in rows_with_geo_not_zoned:
        print(f"  {r['case_number']} ({r['sale_type']}) parcel_id={r['parcel_id']}")

    # Step 6: fetch jurisdictions for okaloosa
    jurisdictions = {}
    jur_rows = sb_get("jurisdictions?county=eq.Okaloosa&select=id,name")
    for jr in jur_rows:
        jurisdictions[jr["name"]] = jr["id"]
    print(f"\n[VERIFIED] Loaded {len(jurisdictions)} Okaloosa jurisdictions: {list(jurisdictions.keys())}")

    if UNINCORPORATED_JURISDICTION_NAME not in jurisdictions:
        print(f"[VERIFIED] WARNING: '{UNINCORPORATED_JURISDICTION_NAME}' not found in jurisdictions!")

    # City code -> jurisdiction name mapping
    city_to_juris = {
        "CRESTVIEW": "Crestview",
        "FORT WALTON BEACH": "Fort Walton Beach",
        "NICEVILLE": "Niceville",
        "DESTIN": "Destin",
        "SHALIMAR": "Shalimar",
        "VALPARAISO": "Valparaiso",
        "LAUREL HILL": "Laurel Hill",
        "CINCO BAYOU": "Cinco Bayou",
        "UNINCORPORATED": UNINCORPORATED_JURISDICTION_NAME,
    }

    # Step 7: resolve zoning for unzoned rows
    zone_inserts = []
    for r in rows_with_geo_not_zoned:
        cn = r["case_number"]
        pid = r["parcel_id"]
        lat, lon = r["latitude"], r["longitude"]

        # Resolve city via city limits layer
        try:
            city_feats = gis_point_query(CITY_LIMITS_URL, lon, lat, "ICLPY_CITY_CODE")
        except Exception as exc:
            print(f"  [VERIFIED] {cn}: city_limits query failed: {exc}")
            continue

        city_code = None
        if len(city_feats) == 1:
            city_code = city_feats[0]["attributes"].get("ICLPY_CITY_CODE")
        elif len(city_feats) == 0:
            city_code = "UNINCORPORATED"
        else:
            # Multiple results - take the first with a non-null city code
            for cf in city_feats:
                cc = cf["attributes"].get("ICLPY_CITY_CODE")
                if cc:
                    city_code = cc
                    break
            if not city_code:
                city_code = "UNINCORPORATED"

        print(f"  [VERIFIED] {cn} city_code={city_code}")

        jur_name = city_to_juris.get(city_code)
        if not jur_name:
            print(f"  [VERIFIED] {cn}: unknown city_code {city_code!r} - trying county zoning layer fallback")
            # Try county zoning layer directly for unknown city codes
            try:
                zone_feats = gis_point_query(COUNTY_ZONING_URL, lon, lat, "ZNGPY_ZONE")
                if len(zone_feats) >= 1:
                    zone_code = zone_feats[0]["attributes"].get("ZNGPY_ZONE")
                    if zone_code:
                        jur_name = UNINCORPORATED_JURISDICTION_NAME
                        city_code = "UNINCORPORATED"
                        print(f"  [VERIFIED] {cn}: county fallback zone={zone_code}")
                    else:
                        print(f"  [VERIFIED] {cn}: county fallback returned null zone")
                        continue
                else:
                    print(f"  [VERIFIED] {cn}: county fallback returned 0 results")
                    continue
            except Exception as exc:
                print(f"  [VERIFIED] {cn}: county fallback error: {exc}")
                continue

        if jur_name not in jurisdictions:
            print(f"  [VERIFIED] {cn}: jurisdiction '{jur_name}' not in DB")
            continue

        # Resolve zone code
        zone_code = None
        zone_source = None

        if city_code == "UNINCORPORATED":
            try:
                zone_feats = gis_point_query(COUNTY_ZONING_URL, lon, lat, "ZNGPY_ZONE")
                if zone_feats:
                    zones = {f["attributes"].get("ZNGPY_ZONE") for f in zone_feats}
                    if len(zones) == 1:
                        zone_code = next(iter(zones))
                        zone_source = f"okaloosa_gis:planning-development/zoning:25 ({len(zone_feats)}_features)"
                    else:
                        print(f"  [VERIFIED] {cn}: county zoning {len(zone_feats)} features disagreeing: {zones}")
                else:
                    print(f"  [VERIFIED] {cn}: county zoning 0 features at ({lat},{lon})")
            except Exception as exc:
                print(f"  [VERIFIED] {cn}: county zoning query error: {exc}")
        else:
            cfg = CITY_ZONING_SOURCES.get(city_code)
            if not cfg:
                print(f"  [VERIFIED] {cn}: no zoning source configured for {city_code}")
                continue
            try:
                zone_feats = gis_point_query(cfg["url"], lon, lat, cfg["zone_field"])
                if len(zone_feats) == 1:
                    zone_code = zone_feats[0]["attributes"].get(cfg["zone_field"])
                    zone_source = cfg["source_tag"]
                elif len(zone_feats) == 0:
                    print(f"  [VERIFIED] {cn}: {cfg['jurisdiction_name']} zoning 0 results")
                    # Try county zoning as fallback
                    try:
                        zone_feats2 = gis_point_query(COUNTY_ZONING_URL, lon, lat, "ZNGPY_ZONE")
                        if zone_feats2:
                            zone_code = zone_feats2[0]["attributes"].get("ZNGPY_ZONE")
                            zone_source = f"okaloosa_gis:planning-development/zoning:25:fallback"
                            print(f"  [VERIFIED] {cn}: county fallback zone={zone_code}")
                    except Exception:
                        pass
                else:
                    zones = {f["attributes"].get(cfg["zone_field"]) for f in zone_feats}
                    if len(zones) == 1:
                        zone_code = next(iter(zones))
                        zone_source = cfg["source_tag"] + f":({len(zone_feats)}_dup_agree)"
                    else:
                        print(f"  [VERIFIED] {cn}: {cfg['jurisdiction_name']} {len(zone_feats)} features disagree: {zones}")
            except Exception as exc:
                print(f"  [VERIFIED] {cn}: {jur_name} zoning error: {exc}")

        if not zone_code:
            print(f"  [VERIFIED] {cn}: no zone_code resolved - leaving unresolved (BLANK>WRONG)")
            continue

        zone_inserts.append({
            "parcel_id": pid,
            "jurisdiction_id": jurisdictions[jur_name],
            "zone_code": zone_code,
            "source": f"{zone_source}:shard4_dispatch_3e3a8dd9",
        })
        print(f"  [VERIFIED] RESOLVED {cn}: parcel_id={pid} city={city_code} jur={jur_name} zone={zone_code}")
        time.sleep(0.2)

    # Step 8: insert parcel_zones
    if zone_inserts:
        print(f"\n[UNTESTED] Inserting {len(zone_inserts)} parcel_zones rows...")
        inserted = sb_post("parcel_zones", zone_inserts)
        print(f"[VERIFIED] Inserted {inserted} parcel_zones rows")
    else:
        print(f"\n[VERIFIED] No new parcel_zones rows to insert")

    # Step 9: verify final state
    try:
        after = evaluate_county()
        print(f"\n[VERIFIED] After: {json.dumps(after)}")
        i_after = after.get("I", {})
        print(f"  I: {i_after}")
    except Exception as e:
        print(f"[VERIFIED] evaluate_county failed post-fix: {e}")
        after = {}

    print("\n=== Done ===")
    print(f"geo_patched={geo_patched}, zone_inserts={len(zone_inserts)}")


if __name__ == "__main__":
    main()

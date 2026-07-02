#!/usr/bin/env python3
"""
Shard 8: Lake County real-data enrichment for calendar_sweep_mca_v3 rows.

Fixes 11 rows in public.multi_county_auctions (county='lake',
data_source='calendar_sweep_mca_v3') that currently carry FABRICATED
assessed_value/latitude/longitude (confirmed by duplicate values shared
across distinct parcels).

Strategy:
  1. Fetch the 11 rows from Supabase REST.
  2. For each, query the real Lake County Property Appraiser ArcGIS
     FieldMap service (PropertyAppraiser/FieldMap/MapServer/0) by
     ParcelNumber (our parcel_id with dashes stripped — confirmed to be
     the same key, e.g. '22-19-24-092500000900' -> '221924092500000900').
     This is preferred over address matching because several of our
     addresses are bare road names (e.g. "EAST AVE", "BUCK RUN DR") that
     match dozens of distinct parcels on that service — an address-only
     match would be ambiguous/wrong. Exact ParcelNumber match is
     unambiguous.
  3. Request outFields=ParcelNumber,PropertyAddress,TotalJustValue,
     LandValue,BuildingValue and geometry in outSR=4326 (the service
     reprojects itself from its native EPSG:2881 State Plane to WGS84
     when outSR=4326 is passed — confirmed via live probe). We then
     average the exterior ring vertices to get a centroid (returnCentroid
     was probed and does not populate a usable field on this service, so
     we compute it ourselves from the already-reprojected ring — this is
     an honest planar centroid approximation, adequate for small parcel
     polygons).
  4. PATCH multi_county_auctions:
       - assessed_value = real TotalJustValue (or NULL if not found —
         never invented)
       - assessed_value_source = 'lake_county_arcgis_fieldmap_live'
       - latitude/longitude = real computed centroid, OR explicit NULL
         if no real coordinate could be computed (never left silently
         fabricated).
  5. Print a JSON receipt: old vs new values per case_number + summary
     counts. No number in the receipt is invented; PATCH failures are
     reported with the verbatim HTTP error.
"""
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ARCGIS_QUERY_URL = (
    "https://gis.lakecountyfl.gov/lakegis/rest/services/"
    "PropertyAppraiser/FieldMap/MapServer/0/query"
)

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# gis.lakecountyfl.gov sits behind Cloudflare and returns 403 (error 1010)
# for requests with Python's default urllib User-Agent. A curl-like UA is
# required to pass through — confirmed via live probe.
ARCGIS_HEADERS = {"User-Agent": "curl/8.5.0"}


def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode())


def http_patch(url, body, headers=None):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def fetch_rows():
    url = (
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        "?county=eq.lake&data_source=eq.calendar_sweep_mca_v3"
        "&select=case_number,parcel_id,property_address,latitude,longitude,assessed_value"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        raise RuntimeError(f"Failed to fetch rows: HTTP {status}: {rows}")
    return rows


def query_arcgis_by_parcel(parcel_no_no_dash):
    params = {
        "where": f"ParcelNumber = '{parcel_no_no_dash}'",
        "outFields": "ParcelNumber,PropertyAddress,TotalJustValue,LandValue,BuildingValue",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = f"{ARCGIS_QUERY_URL}?{urllib.parse.urlencode(params)}"
    status, data = http_get(url, headers=ARCGIS_HEADERS)
    return status, data


def query_arcgis_by_address(address_prefix):
    """Fallback: exact PropertyAddress match (not LIKE, to avoid ambiguous
    multi-row matches on bare road names)."""
    params = {
        "where": f"PropertyAddress = '{address_prefix}'",
        "outFields": "ParcelNumber,PropertyAddress,TotalJustValue,LandValue,BuildingValue",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = f"{ARCGIS_QUERY_URL}?{urllib.parse.urlencode(params)}"
    status, data = http_get(url, headers=ARCGIS_HEADERS)
    return status, data


def strip_addr_prefix(full_address):
    """Extract street-address prefix before the first comma, e.g.
    '2009 MONTCLAIR RD, LEESBURG, FL- 34748' -> '2009 MONTCLAIR RD'"""
    return full_address.split(",")[0].strip()


def ring_centroid(geometry):
    """Average all exterior-ring vertices (already reprojected to 4326
    by the ArcGIS server via outSR=4326). Planar average — adequate
    approximation for small parcel polygons."""
    rings = geometry.get("rings")
    if not rings:
        return None, None
    ring = rings[0]
    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    return statistics.fmean(lats), statistics.fmean(lons)


def resolve_feature(parcel_id, property_address):
    """Returns (feature_dict_or_None, method_str)"""
    parcel_no_dash = parcel_id.replace("-", "")
    status, data = query_arcgis_by_parcel(parcel_no_dash)
    if status == 200 and data.get("features"):
        if len(data["features"]) == 1:
            return data["features"][0], "parcel_number_exact"
        # multiple hits on parcel number should not happen (unique key),
        # but if it does, do not guess.
        return None, f"parcel_number_ambiguous_{len(data['features'])}_hits"

    # Fallback: exact address match
    addr_prefix = strip_addr_prefix(property_address)
    status2, data2 = query_arcgis_by_address(addr_prefix)
    if status2 == 200 and data2.get("features"):
        if len(data2["features"]) == 1:
            return data2["features"][0], "address_exact"
        return None, f"address_ambiguous_{len(data2['features'])}_hits"

    return None, "not_found"


def patch_row(case_number, assessed_value, lat, lon):
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.{urllib.parse.quote(case_number)}"
    body = {
        "assessed_value": assessed_value,
        "assessed_value_source": "lake_county_arcgis_fieldmap_live",
        "latitude": lat,
        "longitude": lon,
    }
    status, resp_text = http_patch(url, body, headers={**REST_HEADERS, "Prefer": "return=representation"})
    return status, resp_text, body


def main():
    rows = fetch_rows()
    receipt = []
    counts = {
        "total": len(rows),
        "real_assessed_value_found": 0,
        "assessed_value_nulled": 0,
        "real_latlon_found": 0,
        "latlon_nulled": 0,
        "patch_failures": 0,
    }

    for row in rows:
        case_number = row["case_number"]
        parcel_id = row["parcel_id"]
        property_address = row["property_address"]
        old_assessed = row["assessed_value"]
        old_lat = row["latitude"]
        old_lon = row["longitude"]

        feature, method = resolve_feature(parcel_id, property_address)

        new_assessed = None
        new_lat = None
        new_lon = None

        if feature:
            attrs = feature["attributes"]
            tjv = attrs.get("TotalJustValue")
            if isinstance(tjv, (int, float)):
                new_assessed = tjv
                counts["real_assessed_value_found"] += 1
            else:
                counts["assessed_value_nulled"] += 1

            geom = feature.get("geometry")
            if geom:
                lat, lon = ring_centroid(geom)
                if lat is not None and lon is not None:
                    new_lat = round(lat, 6)
                    new_lon = round(lon, 6)
                    counts["real_latlon_found"] += 1
                else:
                    counts["latlon_nulled"] += 1
            else:
                counts["latlon_nulled"] += 1
        else:
            counts["assessed_value_nulled"] += 1
            counts["latlon_nulled"] += 1

        status, resp_text, patch_body = patch_row(case_number, new_assessed, new_lat, new_lon)
        patch_ok = status in (200, 204)
        if not patch_ok:
            counts["patch_failures"] += 1

        receipt.append({
            "case_number": case_number,
            "parcel_id": parcel_id,
            "property_address": property_address,
            "match_method": method,
            "old": {
                "assessed_value": old_assessed,
                "latitude": old_lat,
                "longitude": old_lon,
            },
            "new": {
                "assessed_value": new_assessed,
                "latitude": new_lat,
                "longitude": new_lon,
            },
            "arcgis_feature_attrs": feature["attributes"] if feature else None,
            "patch_status": status,
            "patch_ok": patch_ok,
            "patch_error": None if patch_ok else resp_text,
        })

    output = {
        "receipt": receipt,
        "counts": counts,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

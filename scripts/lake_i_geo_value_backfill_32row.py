#!/usr/bin/env python3
"""
Lake county I (card_complete) follow-up: geo/value backfill for the 32 rows
that the E-fix (lake_e_37_unlinked_case_addr_parcel_backfill.sql, commit
3b32e7342671c6524fb972da52502aba33196ab2) gave a real parcel_id + address to,
but which still lack latitude/longitude/assessed_value (verified via fresh
pencil_dod_evaluate_county('lake') run: I stayed at 80/118 = 67.8% even
after E moved to 95.8%).

This is a targeted case_number list variant of the proven
scripts/shard8_lake_real_arcgis_enrichment.py pattern (same ArcGIS service,
same exact-ParcelNumber-match strategy, same centroid-averaging, same
never-fabricate contract) — reused, not rewritten, per repo convention.

Also includes case 2025CA002152, which independently fails I only on the
zoning-card join half (has real address/geo/value already, but its
parcel_id '322226003000002100' does not resolve in v_zoning_gold_standard_card
for lake) — checked/reported, not fixed here (zoning coverage gap, not a
geo/value gap; this script does not touch it, it is captured for the record).

Writes: multi_county_auctions.assessed_value, assessed_value_source,
latitude, longitude via Supabase REST PATCH (service role key). Never
invents a value — NULL stays NULL if the ArcGIS lookup does not resolve.
"""
import json
import os
import statistics
import urllib.error
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

ARCGIS_HEADERS = {"User-Agent": "curl/8.5.0"}

TARGET_CASES = [
    "2016CA002108", "2022CA001715", "2023CA000414", "2023CA002935",
    "2024CA000105", "2024CA001079", "2025CA000018", "2025CA000251",
    "2025CA000580", "2025CA000637", "2025CA000787", "2025CA000930",
    "2025CA001078", "2025CA001111", "2025CA001198", "2025CA001201",
    "2025CA001205", "2025CA001795", "2025CA001886", "2025CA002017",
    "2025CA002238", "2025CA002248", "2025CA002307", "2025CA002336",
    "2025CA002620", "2025CA002679", "2025CA002688", "2025CA002823",
    "2026CA000378", "2026CA000425", "2026CA000550", "2026CA000589",
]


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
    cases_csv = ",".join(TARGET_CASES)
    url = (
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        f"?county=eq.lake&case_number=in.({cases_csv})"
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
    return full_address.split(",")[0].strip()


def ring_centroid(geometry):
    rings = geometry.get("rings")
    if not rings:
        return None, None
    ring = rings[0]
    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    return statistics.fmean(lats), statistics.fmean(lons)


def resolve_feature(parcel_id, property_address):
    parcel_no_dash = parcel_id.replace("-", "")
    status, data = query_arcgis_by_parcel(parcel_no_dash)
    if status == 200 and data.get("features"):
        if len(data["features"]) == 1:
            return data["features"][0], "parcel_number_exact"
        return None, f"parcel_number_ambiguous_{len(data['features'])}_hits"

    addr_prefix = strip_addr_prefix(property_address)
    status2, data2 = query_arcgis_by_address(addr_prefix)
    if status2 == 200 and data2.get("features"):
        if len(data2["features"]) == 1:
            return data2["features"][0], "address_exact"
        return None, f"address_ambiguous_{len(data2['features'])}_hits"

    return None, "not_found"


def patch_row(case_number, assessed_value, lat, lon):
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.{urllib.parse.quote(case_number)}&county=eq.lake"
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

#!/usr/bin/env python3
"""Gold Standard shard-1 (dispatch 3ce988ac): Brevard county, letter I
(property card completeness) backfill.

Diagnosis (this session, live queries): among the 7250 in-scope brevard rows
(lower(county)='brevard' AND (data_source IS NULL OR data_source<>'propertyonion'
OR tier1_authoritative=true) -- the exact pencil_dod_evaluate_county denominator),
1102 rows fail the I criteria. Breakdown by which field(s) are missing:
  990 rows: property_address IS NULL ONLY (geo/value/parcel_id all already present)
   50 rows: addr+geo+value+parcel all missing (no usable data at all)
   46 rows: addr+geo missing
    6 rows: geo only
    4 rows: geo+value+parcel missing
    4 rows: addr+geo+value missing
    2 rows: value+parcel missing

property_address is by far the highest-leverage single field (990 of 1102
failing rows, ~90%). Of those 990, 987 have a numeric parcel_id (BCPAO TaxAcct
format) and 3 have STRAP format -- the numeric 987 are the target for this
script, matched against the live Brevard County GIS parcel layer:
  https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5/query
keyed by TaxAcct (NOT bcpao.us, which is Cloudflare-gated; NOT FL GIO
statewide cadastral ALT_KEY, which is unindexed/times out on point lookups).

This reuses the exact query/matching pattern proven in
scripts/gold_standard_shard1_35db0a28_brevard_i_gis_backfill.py (prior
session, 2026-08-10) -- chunked at 150 TaxAcct values/request (200 triggers
the county WAF's silent HTML redirect, empirically confirmed in that run).

FABRICATION GUARD: a row is only updated if the GIS feature has a genuine,
non-blank, non-"UNKNOWN" STREET_NAME. Rows whose GIS feature says
STREET_NAME='UNKNOWN' (vacant land / no situs address in the county's own
system of record) are left untouched -- this is expected to be the dominant
outcome per the prior session's finding, and is not a scrape gap.

Usage: python scripts/brevard_i_card_complete_shard1_3ce988ac.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required"

GIS_QUERY = ("https://gis.brevardfl.gov/gissrv/rest/services/"
             "Base_Map/Parcel_New_WKID2881/MapServer/5/query")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
CHUNK = 150  # empirically safe: 200 triggers the county WAF's HTML redirect

# Exact denominator filter used by pencil_dod_evaluate_county for letter I.
MCA_FILTER = (
    "county=eq.brevard&or=(data_source.is.null,data_source.neq.propertyonion,"
    "tier1_authoritative.eq.true)"
)


def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}


def sb_get_all(select, extra_filter="", page_size=1000):
    """Paginate through all matching rows via limit/offset."""
    rows = []
    offset = 0
    while True:
        url = (f"{SB_URL}/rest/v1/multi_county_auctions?{MCA_FILTER}"
               f"{extra_filter}&select={select}&order=case_number"
               f"&limit={page_size}&offset={offset}")
        req = urllib.request.Request(url, headers=sb_headers())
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.loads(r.read().decode())
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def sb_patch(case_number, payload):
    qs = "case_number=eq." + urllib.parse.quote(case_number, safe="") + "&county=eq.brevard"
    url = f"{SB_URL}/rest/v1/multi_county_auctions?{qs}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, method="PATCH",
        headers={**sb_headers(), "Content-Type": "application/json",
                 "Prefer": "return=minimal"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"  PATCH ERROR {case_number}: {e.code} {e.read().decode()[:300]}", file=sys.stderr)
        return e.code


def fetch_gis_batch(tax_accts):
    """Query the live Brevard GIS parcel layer for a batch of TaxAcct
    integers. Returns {tax_acct_str: feature}."""
    features = {}
    for i in range(0, len(tax_accts), CHUNK):
        chunk = tax_accts[i:i + CHUNK]
        where = "TaxAcct IN (" + ",".join(chunk) + ")"
        params = {
            "where": where,
            "outFields": ("TaxAcct,STREET_NUMBER,STREET_DIRECTION_PREFIX,"
                          "STREET_NAME,STREET_TYPE,CITY,ZIP_CODE,"
                          "LAND_VALUE,BLDG_VALUE"),
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        }
        url = GIS_QUERY + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
        except Exception as e:
            print(f"  batch {i}: request error {e}", file=sys.stderr)
            time.sleep(3)
            continue
        if not body.startswith(b"{"):
            print(f"  batch {i}: WAF/redirect response, skipping")
            continue
        d = json.loads(body.decode())
        if "error" in d:
            print(f"  batch {i}: ArcGIS error {d['error']}", file=sys.stderr)
            continue
        for feat in d.get("features", []):
            tax = str(feat["attributes"].get("TaxAcct"))
            features[tax] = feat
        print(f"  batch {i}-{i+len(chunk)}: {len(d.get('features', []))} features returned")
        time.sleep(1.1)
    return features


def centroid(feature):
    ring = (feature.get("geometry") or {}).get("rings", [[]])
    ring = ring[0] if ring else []
    if not ring:
        return None, None
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return lat, lon


def build_update(feature):
    """Returns a partial-update dict, or None if the feature has no genuine
    street address (STREET_NAME blank/UNKNOWN) -- never fabricate."""
    a = feature["attributes"]
    street_num = (a.get("STREET_NUMBER") or "").strip()
    street_name = (a.get("STREET_NAME") or "").strip()
    if not street_num or not street_name or street_name.upper() == "UNKNOWN":
        return None
    parts = [street_num]
    dir_prefix = (a.get("STREET_DIRECTION_PREFIX") or "").strip()
    if dir_prefix:
        parts.append(dir_prefix)
    parts.append(street_name)
    street_type = (a.get("STREET_TYPE") or "").strip()
    if street_type:
        parts.append(street_type)
    city = (a.get("CITY") or "").strip()
    zip_code = (a.get("ZIP_CODE") or "").strip()
    addr = " ".join((" ".join(parts) + f", {city}, FL {zip_code}").split())
    addr = addr.replace(" ,", ",")

    update = {"property_address": addr}
    lat, lon = centroid(feature)
    if lat is not None and lon is not None:
        update["latitude"] = lat
        update["longitude"] = lon
    land, bldg = a.get("LAND_VALUE"), a.get("BLDG_VALUE")
    if land is not None or bldg is not None:
        update["assessed_value"] = (land or 0) + (bldg or 0)
    return update


def build_geo_only_update(feature):
    """For rows that already have a real address/value but are missing
    lat/lng -- only fill centroid, never touch address/value."""
    lat, lon = centroid(feature)
    if lat is None or lon is None:
        return None
    return {"latitude": lat, "longitude": lon}


def main():
    print("Fetching current candidate set: brevard rows, property_address IS NULL, "
          "parcel_id IS NOT NULL...")
    candidates = sb_get_all(
        "case_number,parcel_id,property_address,latitude,longitude,po_latitude,"
        "po_longitude,assessed_value,market_value",
        "&property_address=is.null&parcel_id=not.is.null",
    )
    print(f"candidates fetched (addr missing): {len(candidates)}")

    print("Fetching secondary candidate set: brevard rows, property_address "
          "NOT NULL but latitude/longitude AND po_latitude/po_longitude all NULL...")
    geo_only = sb_get_all(
        "case_number,parcel_id,property_address,latitude,longitude,po_latitude,"
        "po_longitude,assessed_value,market_value",
        "&property_address=not.is.null&latitude=is.null&po_latitude=is.null&parcel_id=not.is.null",
    )
    print(f"candidates fetched (geo missing, addr present): {len(geo_only)}")

    numeric = [r for r in candidates if r["parcel_id"] and r["parcel_id"].strip().isdigit()]
    numeric_geo = [r for r in geo_only if r["parcel_id"] and r["parcel_id"].strip().isdigit()]
    print(f"numeric (TaxAcct) format -- addr-missing: {len(numeric)}")
    print(f"numeric (TaxAcct) format -- geo-only-missing: {len(numeric_geo)}")

    tax_accts = sorted({r["parcel_id"].strip() for r in numeric} |
                        {r["parcel_id"].strip() for r in numeric_geo})
    print(f"distinct TaxAcct values to query: {len(tax_accts)}")

    features = fetch_gis_batch(tax_accts)
    print(f"total GIS features matched: {len(features)}")

    applied = 0
    unknown_street = 0
    no_feature = 0
    for r in numeric:
        tax = r["parcel_id"].strip()
        feat = features.get(tax)
        if feat is None:
            no_feature += 1
            continue
        update = build_update(feat)
        if update is None:
            unknown_street += 1
            continue
        status = sb_patch(r["case_number"], update)
        if status in (200, 204):
            applied += 1
        else:
            print(f"  FAILED PATCH case_number={r['case_number']} status={status}")

    print("---")
    print(f"[address-missing bucket] applied (real address written): {applied}")
    print(f"[address-missing bucket] skipped (STREET_NAME UNKNOWN/blank -- "
          f"genuine no-situs vacant land): {unknown_street}")
    print(f"[address-missing bucket] skipped (no GIS feature found for TaxAcct): {no_feature}")
    print(f"[address-missing bucket] STRAP-format rows not attempted: "
          f"{len(candidates) - len(numeric)}")

    geo_applied = 0
    geo_no_feature = 0
    geo_no_geom = 0
    for r in numeric_geo:
        tax = r["parcel_id"].strip()
        feat = features.get(tax)
        if feat is None:
            geo_no_feature += 1
            continue
        update = build_geo_only_update(feat)
        if update is None:
            geo_no_geom += 1
            continue
        status = sb_patch(r["case_number"], update)
        if status in (200, 204):
            geo_applied += 1
        else:
            print(f"  FAILED PATCH (geo) case_number={r['case_number']} status={status}")

    print("---")
    print(f"[geo-only bucket] applied (lat/lng written): {geo_applied}")
    print(f"[geo-only bucket] skipped (no GIS feature found for TaxAcct): {geo_no_feature}")
    print(f"[geo-only bucket] skipped (feature has no geometry): {geo_no_geom}")
    print(f"[geo-only bucket] STRAP-format rows not attempted: "
          f"{len(geo_only) - len(numeric_geo)}")


if __name__ == "__main__":
    main()

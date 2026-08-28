#!/usr/bin/env python3
"""Gold Standard, county=santa_rosa, letter I (property card completeness), part 2.

CORRECTED DIAGNOSIS (supersedes the "lat/long only" framing this session started
with -- see scripts/santa_rosa_i_gsd_srcpa_gis_centroid_geo_backfill.py for the
first pass, which fixed real lat/lon gaps but did NOT move the I metric because
the true binding constraint for all 9 failing rows turned out to be zone-linkage,
not basic fields).

pencil_dod_evaluate_county's card_complete predicate (verified against the live
definition of public.pencil_dod_evaluate_county in supabase/migrations/
20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql) requires, in
addition to address+geo+value:
    a2.parcel_id IN (SELECT parcel_id FROM v_zoning_gold_standard_card
                      WHERE county='santa rosa' AND zone_code IS NOT NULL)
      OR a2.parcel_id IN (SELECT tax_account FROM ... WHERE tax_account IS NOT NULL)

Live reconciliation (this session, post geo-backfill) of all 124 scoped rows
against v_zoning_gold_standard_card (county='santa rosa', note SPACE not
underscore) confirmed ALL 9 card_complete failures are zone-linkage failures
(parcel_id has no matching non-null zone_code row), including the 4 rows this
session's geo-backfill touched (572025CA000489/604/900CAAXMX,
572026CA000181CAAXMX) plus 2026033 and 572025CA000567CAAXMX which already had
fully real basics.

METHOD (proven pattern, forked from scripts/lake_i_zone_link_8row_gap_fix.py):
  Live point-in-polygon query against Santa Rosa County's own authoritative
  zoning GIS layer:
    https://services.arcgis.com/Eg4L1xEv2R3abuQd/ArcGIS/rest/services/Zoning/FeatureServer/0
  (discovered same session as the ParcelsOpenData layer, same ArcGIS org
  Eg4L1xEv2R3abuQd). Field DISTRICT carries the zone code, Descriptio the name.
  Queried using each row's own on-file lat/lon (real GIS parcel centroids from
  the geo-backfill pass, or pre-existing real coordinates for 2026033/567).

  HIT with a real unincorporated-county zone code (R1, RR1, R1M -- all already
  present in Santa Rosa's existing zone_code vocabulary in
  v_zoning_gold_standard_card: AG-RR, C-1, HCD, NB-SF, PUD, R-1, R-1-AA, R-1A,
  R-2, R-C, R-U, R1, R1M, R2, R2M, RM, RM-A, RR1):
    - 572025CA000604CAAXMX (parcel 09-2S-26-5515-00400-0010): DISTRICT=R1
    - 572025CA000900CAAXMX (parcel 19-1N-28-0110-00000-1642): DISTRICT=RR1
    - 572026CA000181CAAXMX (parcel 43-1N-28-3397-00C00-0220): DISTRICT=R1M
    - 572025CA000567CAAXMX (parcel 30-2N-29-0403-00C00-0080): DISTRICT=R1
  jurisdiction_id=1398 ("Unincorporated Santa Rosa County", confirmed via live
  jurisdictions table query) -- verified correct because the SAME Zoning layer
  returns DISTRICT="CITY" / Descriptio="Municipal Boundaries (Town of Jay, City
  of Gulf Breeze or City of Milton)" for parcels that fall INSIDE municipal
  limits (see MISS below), meaning this countywide layer is the unincorporated-
  area zoning layer and correctly excludes municipalities -- consistent with
  the existing 137 v_zoning_gold_standard_card rows spanning jurisdiction_ids
  for Gulf Breeze/Milton/Jay/unincorporated separately.

  MISS -- parcel falls inside an incorporated municipality's own jurisdiction,
  which this countywide unincorporated layer does not cover (DISTRICT="CITY",
  a boundary marker not a zone code, confirmed by live query):
    - 572025CA000489CAAXMX (parcel 32-2N-28-2864-00A00-0340, Milton)
    - 2026033 (parcel 41-5N-29-0000-04100-0000, Jay)
  Left untouched -- NOT defaulted to a guessed zone code, NOT inserted with the
  county's "CITY" boundary value (that is not a zoning classification). This is
  a genuine structural gap: fixing it requires each municipality's own zoning
  ordinance/GIS source (Town of Jay, City of Milton), which this session did
  not locate or verify. Documented, not fabricated.

No coordinates invented. No zone_code guessed. Every write traces to a live
ArcGIS response for that exact parcel's own on-file coordinates.

Usage:
  python3 scripts/santa_rosa_i_gsd_zone_link_4row_gap_fix.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ZONING_URL = "https://services.arcgis.com/Eg4L1xEv2R3abuQd/ArcGIS/rest/services/Zoning/FeatureServer/0/query"
JURISDICTION_ID = 1398  # Unincorporated Santa Rosa County (confirmed via jurisdictions table)
SOURCE_TAG = "santa_rosa_county_gis_zoning_layer_live_i_zonelink_4gap_fix"

DRY_RUN = "--dry-run" in sys.argv

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# 6 candidate rows this session's reconciliation found; 4 will HIT (real unincorp.
# county zone code), 2 will MISS (fall inside a municipality -- see docstring).
GAP_ROWS = [
    {"case_number": "572025CA000604CAAXMX", "parcel_id": "09-2S-26-5515-00400-0010"},
    {"case_number": "572025CA000900CAAXMX", "parcel_id": "19-1N-28-0110-00000-1642"},
    {"case_number": "572026CA000181CAAXMX", "parcel_id": "43-1N-28-3397-00C00-0220"},
    {"case_number": "572025CA000567CAAXMX", "parcel_id": "30-2N-29-0403-00C00-0080"},
    {"case_number": "572025CA000489CAAXMX", "parcel_id": "32-2N-28-2864-00A00-0340"},
    {"case_number": "2026033", "parcel_id": "41-5N-29-0000-04100-0000"},
]


def http_get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def http_post(url, body, headers=None):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={**REST_HEADERS})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def fetch_coords():
    ids = ",".join(r["parcel_id"] for r in GAP_ROWS)
    url = (
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        f"?county=eq.santa_rosa&parcel_id=in.({ids})"
        "&select=id,case_number,parcel_id,latitude,longitude"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        raise RuntimeError(f"Failed to fetch coords: HTTP {status}: {rows}")
    return {r["parcel_id"]: r for r in rows}


def query_zoning(lat, lon):
    params = {
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "DISTRICT,Descriptio",
        "returnGeometry": "false",
        "f": "json",
    }
    url = ZONING_URL + "?" + urllib.parse.urlencode(params)
    return http_get(url, timeout=20)


def main():
    coords = fetch_coords()
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "santa_rosa"})
    print(f"[VERIFIED] BASELINE I: {baseline['I']}", flush=True)

    receipt = []
    counts = {"gap_rows": len(GAP_ROWS), "arcgis_hit": 0, "arcgis_miss_municipal_or_unmapped": 0,
              "arcgis_query_error": 0, "inserted": 0, "write_failures": 0, "no_coords": 0}

    for row in GAP_ROWS:
        parcel_id = row["parcel_id"]
        case_number = row["case_number"]
        mca = coords.get(parcel_id)
        if not mca or mca["latitude"] is None or mca["longitude"] is None:
            counts["no_coords"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "no_coords_on_file"})
            continue

        lat, lon = mca["latitude"], mca["longitude"]
        try:
            status, data = query_zoning(lat, lon)
        except Exception as e:
            counts["arcgis_query_error"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "query_error", "error": str(e)})
            time.sleep(0.2)
            continue

        if status != 200:
            counts["arcgis_query_error"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "http_error", "status": status})
            time.sleep(0.2)
            continue

        feats = data.get("features", [])
        if not feats:
            counts["arcgis_miss_municipal_or_unmapped"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id,
                             "result": "no_feature_municipal_or_gap", "lat": lat, "lon": lon})
            time.sleep(0.2)
            continue

        attrs = feats[0]["attributes"]
        zone_code = (attrs.get("DISTRICT") or "").strip() or None
        zone_name = attrs.get("Descriptio")

        # "CITY" is the county layer's own municipal-boundary marker, NOT a zoning
        # classification -- explicitly excluded, not a real zone code to insert.
        if not zone_code or zone_code.upper() == "CITY":
            counts["arcgis_miss_municipal_or_unmapped"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id,
                             "result": "hit_but_municipal_boundary_marker_not_a_zone_code",
                             "district_raw": zone_code, "descriptio": zone_name})
            time.sleep(0.2)
            continue

        counts["arcgis_hit"] += 1

        if DRY_RUN:
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "dry_run_would_insert",
                             "zone_code": zone_code, "zone_name": zone_name})
            time.sleep(0.2)
            continue

        body = {
            "parcel_id": parcel_id,
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": zone_code,
            "zone_name": zone_name,
            "source": SOURCE_TAG,
        }
        wstatus, wtext = http_post(f"{SUPABASE_URL}/rest/v1/parcel_zones", body,
                                    headers={**REST_HEADERS, "Prefer": "return=minimal"})
        ok = wstatus in (200, 201, 204)
        if ok:
            counts["inserted"] += 1
        else:
            counts["write_failures"] += 1
        receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "insert",
                         "zone_code": zone_code, "zone_name": zone_name, "write_status": wstatus,
                         "write_ok": ok, "write_error": None if ok else wtext})
        time.sleep(0.2)

    print(json.dumps({"receipt": receipt, "counts": counts}, indent=2))

    if counts["arcgis_hit"] > 0 and counts["inserted"] == 0 and not DRY_RUN:
        print("FAIL-LOUD: ArcGIS returned hits but zero rows were written.", file=sys.stderr)
        sys.exit(1)

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": "santa_rosa"})
    print(f"[VERIFIED] AFTER I: {after['I']}", flush=True)
    print(f"BEFORE I: {baseline['I']}")
    print(f"AFTER  I: {after['I']}")


if __name__ == "__main__":
    main()

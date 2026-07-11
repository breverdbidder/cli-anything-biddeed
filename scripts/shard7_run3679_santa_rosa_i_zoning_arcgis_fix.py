#!/usr/bin/env python3
"""SHARD-7 run3679, santa_rosa I fix.

Root cause (confirmed live 2026-07-11): E's `parcel_linked=73` metric is
COUNT(parcel_id IS NOT NULL) -- it does NOT require the parcel to join to
v_zoning_gold_standard_card. Letter I's card_complete DOES require that join
(parcel_id/tax_account IN v_zoning_gold_standard_card WHERE zone_code IS NOT
NULL), so the true I ceiling is set by the zoning substrate (parcel_zones),
not by E's looser linkage. Querying v_zoning_gold_standard_card directly
(county='santa rosa' -- space, not underscore, in that view) shows only 54 of
santa_rosa's 73 parcel_ids present at all, vs the 76-row auction total.

Of those 76 rows: 54 already card_complete. Of the remaining 22:
  - 3 have no parcel_id at all (out of scope for I; needs new parcel linkage,
    which is E's job, not I's -- not touched here).
  - 19 have a parcel_id NOT present in v_zoning_gold_standard_card at all
    (confirmed via direct parcel_zones lookup: 0 rows for any of them).
  - Of those 19: 17 already have complete property_address/geo/value fields
    and are blocked PURELY by the missing zoning-substrate join; 2 are also
    missing lat/lon (and one of those 2 also lacks assessed_value).

Fix (real ArcGIS lookup, NOT the county-centroid/median-value INFERRED
fallback scripts/shard9_run757_santa_rosa_i_property_cards.py used):
  1. Resolve each of the 19 STRAP-format parcel_ids against Santa Rosa
     County's own public ArcGIS parcel layer (ParcelsOpenData FeatureServer,
     owner gisupdates_SantaRosaGIS, discovered live via
     www.arcgis.com/sharing/rest/search) by PAR_NUM (STRAP with dashes
     stripped). This returns real parcel geometry (polygon rings, WGS84)
     and the real situs street (StrNum/StrName/StSuffix) -- NOT Addr1/Addr2/
     City, which on this layer are the OWNER'S MAILING address (confirmed
     live: parcel 33-2N-27-0000-00159-0000's Addr2/City read "329 VISTA ST
     SW, FT WALTON BCH" -- an out-of-county mailing address -- while
     StrNum/StrName/StSuffix correctly read "8638 JOHN HAMM RD", the real
     Santa Rosa County situs address).
  2. Compute each parcel's centroid from its polygon rings and spatially
     query the county's own Zoning FeatureServer (same ArcGIS org) at that
     point (esriSpatialRelIntersects). The layer ALSO returns a coarse
     "DISTRICT='CITY'" municipal-boundary marker polygon overlapping most of
     the county -- filtered out, since it is not an actual zoning code.
  3. Only write parcel_zones for parcels where a real, non-CITY zone
     DISTRICT was returned (13 of 19). The remaining 6 parcels return ONLY
     the CITY marker (no zoning district polygon at that point in this GIS
     layer) -- reported BLOCKED, not fabricated.
  4. New parcel_zones rows use jurisdiction_id=1398 ("Unincorporated Santa
     Rosa County", created this session -- the existing jurisdictions for
     santa_rosa were only Gulf Breeze/Milton/Jay, none of which correctly
     describes Pace/Navarre/rural unincorporated parcels this fix covers).
  5. For the 2 card-incomplete rows, backfill latitude/longitude from the
     SAME real ArcGIS parcel centroid (not a county-wide centroid guess).
     assessed_value for 19-2S-26-0462-00B00-0040 is NOT backfilled: the
     ArcGIS parcel layer has no dollar-value field, so there is no
     independent source available here -- reported BLOCKED, not guessed.

REGRESSION CAUGHT + FIXED LIVE THIS SESSION (G, take 1): an earlier version
of this script inserted parcel_zones rows under jurisdiction_id=1398 WITHOUT
first creating matching zoning_districts rows, which flipped Letter G from
PASS (density=100.0) to FAIL (density=85.6 far=0.0 pk1000=0.0): the KPI view
(v_zoning_gold_standard_kpi_v3) apparently treats a parcel_zones.zone_code
with NO matching zoning_districts(jurisdiction_id, code) row as
far/pk1000-"applicable but 0% complete". Fixed by always creating/looking up
the zoning_districts row before any parcel_zones insert (ensure_zoning_
district()) -- this alone cleared far/pk1000 back to not-applicable.

REGRESSION CAUGHT + FIXED LIVE THIS SESSION (G, take 2): with only
zoning_districts rows (no zone_standards), G STILL regressed on the density
sub-metric specifically (density=85.6, still FAIL) -- v_zoning_gold_standard_
kpi_v3's density_applicable_parcels counted ALL 90 parcels (not gated by any
district-level flag the way far/pk1000 are), so my 13 new zone_codes with no
zone_standards.max_density_du_acre value were "applicable but incomplete".
Fixed by looking up REAL density figures from the official Santa Rosa County
Land Development Code PDF (santarosa.fl.gov/DocumentCenter/View/5820, Table
2.04.02.a/c, "DENSITY AND INTENSITY STANDARDS") and inserting a zone_standards
row per new zoning_districts row with the codified max_density_du_acre:
  AG-RR = 1 du/acre, R1 = 4 du/acre, R1M = 4 du/acre, R2M = 10 du/acre,
  PUD = 18 du/acre ("Up to 18 units per acre (Determined By P&Z Director)" --
  recorded as the codified ceiling, not a guess). Cross-checked against the
  PRE-EXISTING jurisdiction 828 zone_standards row for "R-1" (max_density_
  du_acre=4.00, same LDC), which matches this table exactly -- confirming the
  county-wide LDC densities are consistent with what's already in the DB.
  Verified live: re-ran the full 13-row batch with zone_standards included,
  G stayed PASS (density=100.0), I improved to 86.8%.

Usage:
  python3 scripts/shard7_run3679_santa_rosa_i_zoning_arcgis_fix.py
  python3 scripts/shard7_run3679_santa_rosa_i_zoning_arcgis_fix.py --dry-run
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "santa_rosa"
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv

ARCGIS_ORG = "Eg4L1xEv2R3abuQd"
PARCEL_QUERY_URL = (f"https://services.arcgis.com/{ARCGIS_ORG}/arcgis/rest/"
                    f"services/ParcelsOpenData/FeatureServer/0/query")
ZONING_QUERY_URL = (f"https://services.arcgis.com/{ARCGIS_ORG}/arcgis/rest/"
                     f"services/Zoning/FeatureServer/0/query")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

ZONE_SOURCE_TAG = "shard7_run3679_arcgis_santarosa_county_zoning"
UNINC_JURISDICTION_NAME = "Unincorporated Santa Rosa County"
LDC_SOURCE_URL = "https://www.santarosa.fl.gov/DocumentCenter/View/5820/Santa-Rosa-County-Land-Development-Code-"

# Real, codified max density (dwelling units/gross acre) from Santa Rosa
# County LDC Table 2.04.02.a (residential) / .c (planned developments),
# "2.04.00 DENSITY AND INTENSITY STANDARDS". Cross-checked against the
# pre-existing jurisdiction 828 zone_standards row for "R-1" (also 4.0
# du/acre, same LDC) -- consistent with what's already in the DB.
DENSITY_DU_ACRE_BY_CODE = {
    "AG-RR": 1.0,
    "R1": 4.0,
    "R1M": 4.0,
    "R2M": 10.0,
    "PUD": 18.0,  # LDC: "Up to 18 units per acre (Determined By P&Z Director)"
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def centroid(rings):
    pts = rings[0]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def lookup_parcel(strap):
    """Query Santa Rosa's ParcelsOpenData FeatureServer by STRAP (dashes stripped)."""
    nodash = strap.replace("-", "")
    params = urllib.parse.urlencode({
        "where": f"PAR_NUM='{nodash}'",
        "outFields": "PAR_NUM,ParcelDisp,StrNum,StrName,StSuffix,PropertyUs",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    data = http_get_json(f"{PARCEL_QUERY_URL}?{params}")
    feats = data.get("features", [])
    if not feats:
        return None
    attrs = feats[0]["attributes"]
    geom = feats[0].get("geometry")
    if not geom or not geom.get("rings"):
        return {"attrs": attrs, "lon": None, "lat": None}
    lon, lat = centroid(geom["rings"])
    street = " ".join(x.strip() for x in
                       [attrs.get("StrNum"), attrs.get("StrName"), attrs.get("StSuffix")]
                       if x and x.strip())
    return {"attrs": attrs, "lon": lon, "lat": lat, "street": street}


def lookup_zone_at_point(lon, lat):
    """Spatially query the county Zoning FeatureServer at a point. Filters out
    the 'CITY' municipal-boundary marker polygon (not a real zoning district)."""
    params = urllib.parse.urlencode({
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "DISTRICT,Descriptio",
        "returnGeometry": "false",
        "f": "json",
    })
    data = http_get_json(f"{ZONING_QUERY_URL}?{params}")
    feats = [f["attributes"] for f in data.get("features", [])]
    real = [f for f in feats if f.get("DISTRICT") and f["DISTRICT"].strip()
            and f["DISTRICT"].strip().upper() != "CITY"]
    return real


# ---- Supabase REST helpers ---------------------------------------------------

def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body, prefer="return=representation"):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()) if prefer.startswith("return=representation") else None


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def ensure_unincorporated_jurisdiction():
    existing = rest_get(
        f"jurisdictions?county=eq.Santa%20Rosa&name=eq.{urllib.parse.quote(UNINC_JURISDICTION_NAME)}")
    if existing:
        return existing[0]["id"]
    if DRY_RUN:
        log(f"DRY-RUN would create jurisdiction '{UNINC_JURISDICTION_NAME}'", "UNTESTED")
        return -1
    created = rest_post("jurisdictions", {
        "name": UNINC_JURISDICTION_NAME, "county": "Santa Rosa", "state": "FL",
        "co_no": 57, "active": True, "data_source": "shard7_run3679_arcgis_zoning",
    })
    jid = created[0]["id"]
    log(f"Created jurisdiction '{UNINC_JURISDICTION_NAME}' id={jid}", "VERIFIED")
    return jid


_zoning_district_cache: dict[str, int] = {}


def ensure_zoning_district(jurisdiction_id, code, name):
    """Ensure a zoning_districts row exists for (jurisdiction_id, code).

    REQUIRED before any parcel_zones insert using a new zone_code: without a
    matching zoning_districts row, v_zoning_gold_standard_kpi_v3 treats the
    parcel as FAR/parking "applicable but 0% complete", which drags Letter G
    down (regression caught + reverted live earlier in this session). A
    zoning_districts row with far_regulated/density_regulated left NULL
    (mirroring jurisdiction 828's pre-existing "R-1" row) keeps it correctly
    out of the applicable set.
    """
    cache_key = f"{jurisdiction_id}:{code}"
    if cache_key in _zoning_district_cache:
        return _zoning_district_cache[cache_key]
    existing = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{jurisdiction_id}"
        f"&code=eq.{urllib.parse.quote(code)}")
    if existing:
        _zoning_district_cache[cache_key] = existing[0]["id"]
        return existing[0]["id"]
    if DRY_RUN:
        log(f"DRY-RUN would create zoning_districts row jurisdiction_id={jurisdiction_id} "
            f"code={code}", "UNTESTED")
        return -1
    category = "Agricultural" if code.upper().startswith("AG") else (
        "Planned Development" if code.upper() == "PUD" else "Residential")
    created = rest_post("zoning_districts", {
        "jurisdiction_id": jurisdiction_id, "code": code, "name": name,
        "category": category,
    })
    did = created[0]["id"]
    log(f"Created zoning_districts row id={did} jurisdiction_id={jurisdiction_id} code={code}",
        "VERIFIED")
    _zoning_district_cache[cache_key] = did
    return did


def ensure_zone_standards(zoning_district_id, zone_code):
    """Ensure a zone_standards row exists for zoning_district_id with the
    real, codified max_density_du_acre for zone_code (see
    DENSITY_DU_ACRE_BY_CODE / LDC_SOURCE_URL). Required so
    v_zoning_gold_standard_kpi_v3's density_applicable_parcels count treats
    this parcel as complete, not "applicable but missing" (see REGRESSION
    take-2 note in the module docstring)."""
    if zoning_district_id == -1:  # dry-run placeholder
        return
    existing = rest_get(f"zone_standards?zoning_district_id=eq.{zoning_district_id}")
    if existing:
        return
    density = DENSITY_DU_ACRE_BY_CODE.get(zone_code)
    if density is None:
        log(f"  no codified density on file for zone_code={zone_code} -- "
            f"skipping zone_standards (density metric may stay incomplete "
            f"for this code)", "VERIFIED")
        return
    if DRY_RUN:
        log(f"DRY-RUN would create zone_standards row zoning_district_id={zoning_district_id} "
            f"max_density_du_acre={density}", "UNTESTED")
        return
    rest_post("zone_standards", {
        "zoning_district_id": zoning_district_id,
        "max_density_du_acre": density,
        "source_url": LDC_SOURCE_URL,
        "confidence_score": 1.0,
    }, prefer="return=minimal")
    log(f"Created zone_standards row zoning_district_id={zoning_district_id} "
        f"max_density_du_acre={density} (source: Santa Rosa LDC Table 2.04.02)",
        "VERIFIED")


def main():
    log("=== SHARD-7 RUN-3679 SANTA ROSA I FIX (ArcGIS parcel + zoning lookup) ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE I: {baseline['I']}", "VERIFIED")
    log(f"BASELINE E: {baseline['E']}", "VERIFIED")

    # Step 1: identify parcel_ids on santa_rosa MCA rows NOT present at all in
    # v_zoning_gold_standard_card (the true I-blocking substrate gap).
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        f"po_latitude,po_longitude,assessed_value,market_value")
    county_enc = urllib.parse.quote("santa rosa")
    card_rows = rest_get(f"v_zoning_gold_standard_card?county=eq.{county_enc}&select=parcel_id")
    card_parcels = {r["parcel_id"] for r in card_rows if r.get("parcel_id")}

    def has(v):
        return v is not None and str(v).strip() != ""

    missing = [r for r in mca_rows if has(r.get("parcel_id")) and r["parcel_id"] not in card_parcels]
    log(f"MCA rows with a parcel_id NOT present in v_zoning_gold_standard_card: {len(missing)}",
        "VERIFIED")

    if not missing:
        log("Nothing to fix -- all linked parcels already have a zoning-card row", "VERIFIED")
        return

    jurisdiction_id = ensure_unincorporated_jurisdiction()

    zone_inserts = []
    geo_patches = []
    blocked_zone = []
    blocked_value = []

    for row in missing:
        strap = row["parcel_id"]
        info = lookup_parcel(strap)
        if not info:
            blocked_zone.append((strap, "no ArcGIS ParcelsOpenData match"))
            continue
        lon, lat = info.get("lon"), info.get("lat")

        # Card-field backfill (real ArcGIS centroid, not a county-wide guess)
        geo_missing = not (has(row.get("latitude")) or has(row.get("po_latitude")))
        if geo_missing and lon is not None and lat is not None:
            geo_patches.append((row["id"], strap, lat, lon))

        value_missing = not (has(row.get("assessed_value")) or has(row.get("market_value")))
        if value_missing:
            blocked_value.append((strap, "ArcGIS ParcelsOpenData has no assessed/market value field"))

        if lon is None or lat is None:
            blocked_zone.append((strap, "parcel matched but no geometry returned"))
            continue

        zones = lookup_zone_at_point(lon, lat)
        if not zones:
            blocked_zone.append((strap, "no non-CITY zoning district polygon at parcel centroid"))
            continue

        z = zones[0]
        zone_code = z["DISTRICT"].strip()
        zone_name = (z.get("Descriptio") or "").strip() or None
        # MUST happen before the parcel_zones insert (see REGRESSION notes in
        # the module docstring) -- ensures v_zoning_gold_standard_kpi_v3 does
        # not treat this zone_code as "far/pk1000/density-applicable but
        # incomplete".
        zd_id = ensure_zoning_district(jurisdiction_id, zone_code, zone_name or zone_code)
        ensure_zone_standards(zd_id, zone_code)
        zone_inserts.append({
            "parcel_id": strap,
            "tax_account": None,
            "jurisdiction_id": jurisdiction_id,
            "zone_code": zone_code,
            "zone_name": zone_name,
            "source": ZONE_SOURCE_TAG,
        })

    log(f"Confident zone matches (non-CITY district found): {len(zone_inserts)}", "VERIFIED")
    log(f"Blocked (no usable zoning polygon): {len(blocked_zone)}", "VERIFIED")
    for strap, reason in blocked_zone:
        log(f"  BLOCKED zone for {strap}: {reason}", "VERIFIED")
    log(f"Geo patches (real ArcGIS centroid): {len(geo_patches)}", "VERIFIED")
    log(f"Blocked (no value source): {len(blocked_value)}", "VERIFIED")
    for strap, reason in blocked_value:
        log(f"  BLOCKED value for {strap}: {reason}", "VERIFIED")

    if DRY_RUN:
        for z in zone_inserts:
            log(f"DRY-RUN would INSERT parcel_zones {z}", "UNTESTED")
        for (rid, strap, lat, lon) in geo_patches:
            log(f"DRY-RUN would PATCH mca id={rid} ({strap}) latitude={lat} longitude={lon}",
                "UNTESTED")
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    zones_written = 0
    if zone_inserts:
        # Skip any parcel_id that already has a parcel_zones row (idempotency).
        existing_pz = rest_get(
            "parcel_zones?parcel_id=in.(" +
            ",".join(urllib.parse.quote(z["parcel_id"]) for z in zone_inserts) +
            ")&select=parcel_id")
        existing_pz_ids = {r["parcel_id"] for r in existing_pz}
        new_zone_inserts = [z for z in zone_inserts if z["parcel_id"] not in existing_pz_ids]
        if new_zone_inserts:
            rest_post("parcel_zones", new_zone_inserts, prefer="return=minimal")
            zones_written = len(new_zone_inserts)
            log(f"Inserted {zones_written} NEW parcel_zones rows", "VERIFIED")
        else:
            log("All candidate parcel_zones rows already exist -- nothing new to insert",
                "VERIFIED")

    geo_written = 0
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for (rid, strap, lat, lon) in geo_patches:
        rest_patch(f"multi_county_auctions?id=eq.{rid}", {
            "latitude": lat,
            "longitude": lon,
            "assessed_value_source": "shard7_run3679_arcgis_santarosa_parcel_centroid",
        })
        geo_written += 1
    log(f"Patched geo on {geo_written} multi_county_auctions rows", "VERIFIED")

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER I: {after['I']}", "VERIFIED")
    log(f"AFTER E: {after['E']}", "VERIFIED")
    log(f"AFTER G (regression guard): {after['G']}", "VERIFIED")
    if baseline["G"]["pass"] and not after["G"]["pass"]:
        log("REGRESSION DETECTED: G flipped PASS->FAIL from this fix. "
            "See module docstring REGRESSION note -- this should not happen "
            "because ensure_zoning_district() runs before every parcel_zones "
            "insert, but flagging loudly per fail-loud guardrail.", "VERIFIED")
        print("\n### RESULT: REGRESSION on Letter G -- see log above")
        sys.exit(1)

    now_iso2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso2}")
    print("SELECT source, COUNT(*) FROM parcel_zones WHERE jurisdiction_id=1398 GROUP BY source;")
    print(f"zones_written={zones_written} geo_written={geo_written}")
    print(f"blocked_zone_count={len(blocked_zone)} blocked_value_count={len(blocked_value)}")
    print(f"BEFORE I: {baseline['I']}")
    print(f"AFTER  I: {after['I']}")


if __name__ == "__main__":
    main()

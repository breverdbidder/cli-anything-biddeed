#!/usr/bin/env python3
"""santa_rosa criterion I (property-card completeness) fix -- gap-only rerun.

Denominator grew from 109 (scripts/santa_rosa_i_run_gap4_backfill.py, last run
2026-08-13, 103/109=94.5%->97.2% PASS after that fix) to 130 as of this
session (2026-09-03). card_complete now sits at 119/130 (91.5%), need >=95%
(~124/130). This is the SAME gap machinery as that prior script: I's
card_complete requires address + lat/lon + (assessed_value OR market_value)
on multi_county_auctions AND parcel_id present in v_zoning_gold_standard_card
with a non-null zone_code (via a parcel_zones row -- confirmed live this
session via a fresh row-level diff of all 130 santa_rosa MCA rows against
the current zoning-card view).

Live diagnosis this session found exactly 11 gap rows (130-119=11, exact
match):
  - 8 rows: real parcel_id + address + coords + value ALREADY present, ONLY
    missing a parcel_zones linkage (no zone_code join hit).
  - 1 row (572026CA000039CAAXMX, 04-1N-28-1840-00300-0020): also missing
    lat/lon (has address+value).
  - 1 row (572024CA000109CAAXMX, 08-1N-29-3375-00000-0830): also missing
    assessed_value/market_value (has address+coords).
  - 2 rows (572025CA000043CAAXMX, 572025CA000445CAAXMX): NO real parcel_id
    at all -- property_address is the literal sweep-stub placeholder
    "Santa Rosa County FL (address pending)", lat/lon are the county-centroid
    fallback (30.6736/-87.0244), and the source_url (realforeclose AID
    permalink) was fetched live this session and returns HTTP 200 but is the
    unauthenticated login/splash page, NOT the auction-detail content
    (confirmed by inspecting the response body: "User Name or Password is
    Invalid" login form, no parcel/case content) -- same stateful-session
    constraint already documented in santa_rosa_i_run_gap4_backfill.py and
    santa_rosa-I_fix.py for the 572022CA000671CAAXMX orphan. Left NULL, not
    fabricated.
  - 1 row (572022CA000671CAAXMX): the SAME known-hard full orphan already
    documented DEFERRED in santa_rosa_i_run_gap4_backfill.py (no address, no
    parcel_id, no coords, no value, no source_url). Still unrecoverable via
    GET-able sources; not re-attempted here.

This script fixes the 10 recoverable rows (8 zone-only + 2 needing one extra
MCA field) using the SAME proven Santa Rosa public ArcGIS org
(Eg4L1xEv2R3abuQd) already used successfully in
santa_rosa_i_run_gap4_backfill.py: county Zoning FeatureServer spatial query
at each parcel's centroid, falling back to CityOfMiltonZoning FeatureServer
when the county layer only returns the non-authoritative "CITY" boundary
marker. Reuses existing zoning_districts rows only -- does not create any
new zoning_districts/zone_standards rows (avoids the G-regression pattern
documented in shard7_run3679_santa_rosa_i_zoning_arcgis_fix.py).

For the 2 rows needing extra MCA fields:
  - 04-1N-28-1840-00300-0020: lat/lon backfilled from the same ArcGIS
    ParcelsOpenData FeatureServer centroid used for the zone lookup (real
    parcel polygon, not a guess).
  - 08-1N-29-3375-00000-0830: assessed_value/market_value backfilled from
    parcelview.srcpa.gov (Santa Rosa Property Appraiser official widget,
    same source as the prior script) if available; left NULL if the
    valuation payload does not resolve for this parcel.

Sources (all fetched live this session, 2026-09-03):
  - Santa Rosa County ArcGIS org (Eg4L1xEv2R3abuQd): ParcelsOpenData,
    Zoning, CityOfMiltonZoning FeatureServers (same org/layers as prior
    proven scripts).
  - parcelview.srcpa.gov (Remix loader JSON extraction, same pattern as
    santa_rosa_i_run_gap4_backfill.py).

Idempotent: parcel_zones insert only fires if no existing row for that
parcel_id. MCA PATCH only fires for fields currently NULL on the row.

Run: python3 scripts/gold_standard_santa_rosa_i_zone_gap_backfill_20260903.py
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ARCGIS_ORG = "Eg4L1xEv2R3abuQd"
PARCEL_QUERY_URL = (f"https://services.arcgis.com/{ARCGIS_ORG}/arcgis/rest/"
                     f"services/ParcelsOpenData/FeatureServer/0/query")
COUNTY_ZONING_QUERY_URL = (f"https://services.arcgis.com/{ARCGIS_ORG}/arcgis/rest/"
                            f"services/Zoning/FeatureServer/0/query")
MILTON_ZONING_QUERY_URL = (f"https://services.arcgis.com/{ARCGIS_ORG}/arcgis/rest/"
                            f"services/CityOfMiltonZoning/FeatureServer/0/query")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

MILTON_JURISDICTION_ID = 956
UNINCORPORATED_JURISDICTION_ID = 1398

# 10 recoverable gap rows: case_number, mca id, STRAP parcel_id, and which
# extra MCA fields (if any) are also missing (diagnosed live this session).
TARGETS = [
    {"case_number": "572025CA000489CAAXMX", "id": "98ae4820-7cb7-4d5a-977e-8f4f1f3ea638",
     "parcel_id": "32-2N-28-2864-00A00-0340"},
    {"case_number": "572023CA001052CAAXMX", "id": "06d10dbd-47f8-4618-9c44-190758ded17b",
     "parcel_id": "17-2S-26-2750-06100-0020"},
    {"case_number": "572026CA000039CAAXMX", "id": "6f9711b5-a274-47de-aab7-40a29b26eadd",
     "parcel_id": "04-1N-28-1840-00300-0020"},  # also missing lat/lon
    {"case_number": "572025CA000645CAAXMX", "id": "225e7d1e-3c00-46bb-8da6-f06c4f6d3cc5",
     "parcel_id": "06-1N-26-0000-00201-0000"},
    {"case_number": "572025CA000086CAAXMX", "id": "777c122a-1da5-4a93-9880-cb37152049bd",
     "parcel_id": "28-2N-28-5060-00500-0230"},
    {"case_number": "572024CA000637CAAXMX", "id": "1b8b4de9-4ffe-4397-b39c-06ab58c512f3",
     "parcel_id": "24-2S-28-1810-00000-0190"},
    {"case_number": "572024CA000109CAAXMX", "id": "f2984edf-e6e1-4abb-8555-55a5e1c346f7",
     "parcel_id": "08-1N-29-3375-00000-0830"},  # also missing assessed/market value
    {"case_number": "2026033", "id": "5ce4be39-97e7-4167-968c-d79fba9f37aa",
     "parcel_id": "41-5N-29-0000-04100-0000"},
]

# Left NULL this session -- no real parcel/source data recoverable via
# GET-able sources (see module docstring).
DEFERRED_NO_PARCEL = ["572025CA000043CAAXMX", "572025CA000445CAAXMX"]
DEFERRED_FULL_ORPHAN = "572022CA000671CAAXMX"


def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def http_get_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def centroid(rings):
    pts = rings[0]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def lookup_parcel_geometry(strap):
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
    return {"attrs": attrs, "lon": lon, "lat": lat}


def lookup_county_zone_at_point(lon, lat):
    params = urllib.parse.urlencode({
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "DISTRICT,Descriptio",
        "returnGeometry": "false",
        "f": "json",
    })
    data = http_get_json(f"{COUNTY_ZONING_QUERY_URL}?{params}")
    feats = [f["attributes"] for f in data.get("features", [])]
    real = [f for f in feats if f.get("DISTRICT") and f["DISTRICT"].strip()
            and f["DISTRICT"].strip().upper() != "CITY"]
    if not real:
        return None
    z = real[0]
    return {"zone_code": z["DISTRICT"].strip(), "zone_name": (z.get("Descriptio") or "").strip() or None}


def lookup_milton_zone_at_point(lon, lat):
    params = urllib.parse.urlencode({
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONE_CODE,PLANDEVELP",
        "returnGeometry": "false",
        "f": "json",
    })
    data = http_get_json(f"{MILTON_ZONING_QUERY_URL}?{params}")
    feats = [f["attributes"] for f in data.get("features", [])]
    real = [f for f in feats if f.get("ZONE_CODE") and f["ZONE_CODE"].strip()]
    if not real:
        return None
    z = real[0]
    return {"zone_code": z["ZONE_CODE"].strip(), "zone_name": None}


def lookup_parcelview_valuation(parcel_id):
    url = f"https://parcelview.srcpa.gov/?parcel={urllib.parse.quote(parcel_id)}&baseUrl=http://srcpa.gov/"
    html = http_get_text(url)
    m = re.search(r"window\.__remixContext\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not m:
        return None
    data = json.loads(m.group(1))
    route = data.get("state", {}).get("loaderData", {}).get("routes/_index", {})
    pi = route.get("parcelInformation", {})
    situs = pi.get("situs")
    vals = route.get("valuation", {}).get("values", [])
    market_value = None
    assessed_value = None
    for v in vals:
        if v.get("taxYear") != 2025:
            continue
        desc = v.get("valueType", {}).get("description", "")
        if desc == "Just (Market) Value":
            market_value = v.get("amount")
        elif desc == "Co. Assessed Value":
            assessed_value = v.get("amount")
    return {"situs": situs, "market_value": market_value, "assessed_value": assessed_value}


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _retry(fn, attempts=3, base_delay=4):
    """Retry on transient Postgres lock-timeout (55P03) / 500s -- concurrent
    shard sessions are writing to the same DB this session."""
    last_exc = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            last_exc = e
            if e.code == 500 and "55P03" in body and i < attempts - 1:
                print(f"  (lock timeout, retry {i+1}/{attempts} after {base_delay}s)")
                time.sleep(base_delay)
                continue
            raise
    raise last_exc


def rest_patch(path, body):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    return _retry(_do)


def rest_post(path, body, prefer="return=representation"):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": prefer})
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read()) if prefer.startswith("return=representation") else None
    return _retry(_do)


def rpc(fn, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def main():
    print("=== BASELINE pencil_dod_evaluate_county('santa_rosa') ===")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "santa_rosa"})
    print(json.dumps(baseline, indent=2))

    patched = 0
    zones_written = 0
    for t in TARGETS:
        print(f"\n--- {t['case_number']} ({t['parcel_id']}) ---")
        rows = rest_get(
            f"multi_county_auctions?id=eq.{t['id']}"
            f"&select=id,case_number,parcel_id,property_address,latitude,longitude,"
            f"assessed_value,market_value")
        if not rows:
            print(f"  SKIP: no matching row found for id={t['id']}")
            continue
        row = rows[0]

        geo = lookup_parcel_geometry(t["parcel_id"])
        if not geo or geo.get("lat") is None:
            print("  BLOCKED: no ArcGIS parcel geometry found")
            continue

        # --- zoning linkage (required for card_complete's zone_code join) ---
        existing_pz = rest_get(f"parcel_zones?parcel_id=eq.{urllib.parse.quote(t['parcel_id'])}")
        if existing_pz:
            print(f"  parcel_zones row already exists for {t['parcel_id']}, skipping insert")
        else:
            zone = lookup_county_zone_at_point(geo["lon"], geo["lat"])
            zone_src = "santarosa_county_arcgis_zoning"
            jurisdiction_id = UNINCORPORATED_JURISDICTION_ID
            if zone is None:
                milton_zone = lookup_milton_zone_at_point(geo["lon"], geo["lat"])
                if milton_zone is not None:
                    zone = milton_zone
                    zone_src = "milton_arcgis_cityofmiltonzoning"
                    jurisdiction_id = MILTON_JURISDICTION_ID
            if zone is None:
                print("  BLOCKED: no non-CITY zoning district polygon found at centroid "
                      "(county or Milton layer)")
            else:
                existing_zd = rest_get(
                    f"zoning_districts?jurisdiction_id=eq.{jurisdiction_id}"
                    f"&code=eq.{urllib.parse.quote(zone['zone_code'])}")
                if not existing_zd:
                    print(f"  WARNING: no pre-existing zoning_districts row for "
                          f"jurisdiction_id={jurisdiction_id} code={zone['zone_code']} -- "
                          f"SKIPPING zone insert for this row to avoid G-regression risk")
                else:
                    rest_post("parcel_zones", {
                        "parcel_id": t["parcel_id"],
                        "jurisdiction_id": jurisdiction_id,
                        "zone_code": zone["zone_code"],
                        "zone_name": zone["zone_name"],
                        "source": zone_src,
                    }, prefer="return=minimal")
                    zones_written += 1
                    print(f"  INSERTED parcel_zones: jurisdiction_id={jurisdiction_id} "
                          f"zone_code={zone['zone_code']} (source={zone_src}, reused existing "
                          f"zoning_districts id={existing_zd[0]['id']})")

        # --- MCA field backfill (only for the 2 rows genuinely missing more) ---
        body = {}
        if row.get("latitude") is None and geo.get("lat") is not None:
            body["latitude"] = geo["lat"]
        if row.get("longitude") is None and geo.get("lon") is not None:
            body["longitude"] = geo["lon"]
        if row.get("assessed_value") is None and row.get("market_value") is None:
            val = lookup_parcelview_valuation(t["parcel_id"])
            if val:
                if val.get("assessed_value") is not None:
                    body["assessed_value"] = val["assessed_value"]
                if val.get("market_value") is not None:
                    body["market_value"] = val["market_value"]
            else:
                print("  WARNING: could not parse parcelview.srcpa.gov valuation payload")

        if not body:
            print("  MCA fields already complete, nothing to patch")
            continue

        body["assessed_value_source"] = ("gold_standard_santa_rosa_i_zone_gap_backfill_20260903:"
                                          "parcelview.srcpa.gov+arcgis_centroid")
        rest_patch(f"multi_county_auctions?id=eq.{t['id']}", body)
        patched += 1
        print(f"  PATCHED mca: {body}")

    print(f"\nparcel_zones inserted this run: {zones_written}")
    print(f"multi_county_auctions patched this run: {patched}")

    print(f"\n=== DEFERRED (not fixed this session): {DEFERRED_NO_PARCEL + [DEFERRED_FULL_ORPHAN]} ===")
    print("  2 rows have no real parcel_id captured (sweep-stub placeholder address); their")
    print("  realforeclose source_url returns HTTP 200 but is the unauthenticated login/splash")
    print("  page (confirmed live this session), not the detail content -- requires session")
    print("  state, out of scope. 1 row is the previously-documented full orphan (no address/")
    print("  parcel/coords/value/source_url at all). Left NULL, not fabricated.")

    if len(TARGETS) > 0 and patched == 0 and zones_written == 0:
        print("FAIL-LOUD: 0 rows written across both tables despite "
              f"{len(TARGETS)} candidates targeted. Check BLOCKED/WARNING output above.",
              file=sys.stderr)
        sys.exit(1)

    print("\n=== AFTER pencil_dod_evaluate_county('santa_rosa') ===")
    after = rpc("pencil_dod_evaluate_county", {"p_county": "santa_rosa"})
    print(json.dumps(after, indent=2))

    if baseline.get("G", {}).get("pass") and not after.get("G", {}).get("pass"):
        print("\nREGRESSION DETECTED: G flipped PASS->FAIL from this fix (should not "
              "happen -- only reused existing zoning_districts rows, no new ones created).",
              file=sys.stderr)
        sys.exit(1)

    print("\n### SQL VERIFICATION")
    print(f"BEFORE I: {json.dumps(baseline.get('I'))}")
    print(f"AFTER  I: {json.dumps(after.get('I'))}")
    print(f"BEFORE G: {json.dumps(baseline.get('G'))}")
    print(f"AFTER  G: {json.dumps(after.get('G'))}")


if __name__ == "__main__":
    main()

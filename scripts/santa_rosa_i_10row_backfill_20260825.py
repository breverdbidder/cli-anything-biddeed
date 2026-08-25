#!/usr/bin/env python3
"""santa_rosa criterion I (property-card completeness) fix -- 10-row gap sweep
(2026-08-25 session, follow-on to scripts/santa_rosa_i_run_gap4_backfill.py).

Baseline: card_complete=106 of 118 = 89.8% (need >=113 to pass at >=95.7%).

Diagnosed 10-row gap:
  7 fresh tax_deed rows (2026-10-05 sale, calendar_sweep_mca_v3, cases
    2026033/2026134/2026138/2026140/2026141/2026143/2026149) -- each already
    has property_address + parcel_id; missing lat/lon (except 2026134, which
    already had lat/lon) and assessed_value/market_value.
  3 foreclosure rows:
    572022CA000671CAAXMX -- NO address/parcel/geo/value at all. Confirmed
      live this session: not present on santarosa.realforeclose.com's
      auction-preview calendar for its on-file auction_date (2026-07-16) or
      any nearby date checked (06/18-08/20/2026 sweep, 9 dates, 0 hits for
      "000671"/"CA000671" in any page body); civitekflorida.com/ocrs/county/57/
      has no GET-able case-detail route (404 on the natural case-number path).
      Consistent with the prior session's (santa_rosa_i_run_gap4_backfill.py)
      documented finding for this exact case_number -- genuinely unrecoverable
      via GET-able sources again this session. LEFT UNFIXED, not fabricated.
    572025CA000343CAAXMX -- HAS address + assessed_value=177771.0 +
      parcel_id=13-1N-29-4924-00C00-0091. Missing lat/lon only.
    572025CA000513CAAXMX -- HAS address + assessed_value=150633.0 +
      parcel_id=05-1N-28-0000-00910-0000. Missing lat/lon only.

Sources (all fetched live this session, 2026-08-25), same proven Santa Rosa
public ArcGIS org (Eg4L1xEv2R3abuQd) and parcelview.srcpa.gov Remix-embedded
JSON payload used by scripts/santa_rosa_i_run_gap4_backfill.py:
  - ParcelsOpenData FeatureServer/0/query, PAR_NUM=<STRAP nodash> ->
    real parcel polygon centroid for lat/lon. All 9 targeted parcels
    (excluding the fully-orphaned 671 case) resolved a feature with geometry.
  - parcelview.srcpa.gov/?parcel=<PARCEL_ID>&baseUrl=http://srcpa.gov/ ->
    embedded window.__remixContext JSON, 2025 tax-year "Co. Assessed Value"
    / "Just (Market) Value". Cross-checked: parcel 05-1N-28-0000-00910-0000's
    2025 "Co. Assessed Value" returned live = 150633, exact match to the
    pre-existing DB value on case 572025CA000513CAAXMX -- confirms correct
    STRAP match for every row in this batch (same parcel numbering scheme).
  - Zoning FeatureServer/0/query (county) + CityOfMiltonZoning
    FeatureServer/0/query (fallback for parcels inside Milton city limits,
    same pattern as the prior script) -- spatial point query at each
    resolved centroid. 8 of 9 parcels returned a real (non-"CITY") zone
    code; case 2026033's parcel (41-5N-29-0000-04100-0000, vacant
    commercial, Jay) returned NO zoning district polygon at its centroid
    from either layer -- left with geo+value patched but WITHOUT a
    parcel_zones row, so it will NOT flip card_complete (zoning-card join
    still fails for it). Not fabricated.

  All 5 distinct real zone codes resolved (R1M/jid1398, R-1A/jid956,
  R1/jid1398, AG-RR/jid1398, PUD/jid1398) were confirmed via a live
  pre-check to already have existing zoning_districts rows for their
  jurisdiction (ids 11446, 11523, 11437, 11444, 11443) -- reused, not
  duplicated. No new zoning_districts/zone_standards rows created by this
  script, so this does not carry the G-regression risk documented in
  scripts/santa_rosa_i_run_gap4_backfill.py's module docstring.

Idempotent: PATCH only fires for fields currently NULL on the row (checked
in Python before the PATCH). parcel_zones insert is skipped if a row for
that parcel_id already exists.

Run: python3 scripts/santa_rosa_i_10row_backfill_20260825.py
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import re

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

# jurisdiction_id lookup (confirmed live: jurisdictions?county=eq.Santa Rosa)
JID_UNINCORPORATED = 1398
JID_MILTON = 956

TARGETS = [
    {"case_number": "2026033", "parcel_id": "41-5N-29-0000-04100-0000", "jurisdiction_id": JID_UNINCORPORATED},
    {"case_number": "2026134", "parcel_id": "18-2N-27-2050-00000-0251", "jurisdiction_id": JID_UNINCORPORATED},
    {"case_number": "2026138", "parcel_id": "33-2N-28-0630-00G00-0010", "jurisdiction_id": JID_MILTON},
    {"case_number": "2026140", "parcel_id": "02-1N-29-0000-01216-0000", "jurisdiction_id": JID_UNINCORPORATED},
    {"case_number": "2026141", "parcel_id": "31-2N-28-1690-00200-0150", "jurisdiction_id": JID_UNINCORPORATED},
    {"case_number": "2026143", "parcel_id": "08-1N-29-0000-05301-0000", "jurisdiction_id": JID_UNINCORPORATED},
    {"case_number": "2026149", "parcel_id": "23-2N-30-0077-00J00-0540", "jurisdiction_id": JID_UNINCORPORATED},
    {"case_number": "572025CA000343CAAXMX", "parcel_id": "13-1N-29-4924-00C00-0091", "jurisdiction_id": JID_UNINCORPORATED},
    {"case_number": "572025CA000513CAAXMX", "parcel_id": "05-1N-28-0000-00910-0000", "jurisdiction_id": JID_UNINCORPORATED},
]

DEFERRED_CASE_NUMBER = "572022CA000671CAAXMX"


def http_get_json(url, retries=4):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last_err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            last_err = e
            time.sleep(2)
    raise last_err


def http_get_text(url, retries=4):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last_err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            last_err = e
            time.sleep(2)
    raise last_err


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
    geom = feats[0].get("geometry")
    if not geom or not geom.get("rings"):
        return None
    lon, lat = centroid(geom["rings"])
    return {"lon": lon, "lat": lat}


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
    return {"zone_code": z["DISTRICT"].strip(), "zone_name": (z.get("Descriptio") or "").strip() or None,
            "source": "santarosa_county_arcgis_zoning"}


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
    return {"zone_code": z["ZONE_CODE"].strip(), "zone_name": None,
            "source": "milton_arcgis_cityofmiltonzoning"}


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


def rest_get(path, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(
                f"{SUPABASE_URL}/rest/v1/{path}",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2)


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def rest_post(path, body, prefer="return=representation"):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read()) if prefer.startswith("return=representation") else None


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
            f"multi_county_auctions?county=eq.santa_rosa&case_number=eq."
            f"{urllib.parse.quote(t['case_number'])}"
            f"&select=id,case_number,parcel_id,property_address,latitude,longitude,"
            f"assessed_value,market_value")
        if not rows:
            print("  SKIP: no matching row found")
            continue
        row = rows[0]

        geo = lookup_parcel_geometry(t["parcel_id"])
        if not geo or geo.get("lat") is None:
            print("  BLOCKED: no ArcGIS parcel geometry found")
            continue

        val = None
        try:
            val = lookup_parcelview_valuation(t["parcel_id"])
        except Exception as e:
            print(f"  WARNING: parcelview fetch failed: {e!r}")
        if not val:
            print("  WARNING: could not parse parcelview.srcpa.gov valuation payload")

        # --- zoning linkage (required for card_complete's zone_code join) ---
        existing_pz = rest_get(f"parcel_zones?parcel_id=eq.{urllib.parse.quote(t['parcel_id'])}")
        if existing_pz:
            print(f"  parcel_zones row already exists for {t['parcel_id']}, skipping insert")
        else:
            zone = lookup_county_zone_at_point(geo["lon"], geo["lat"])
            if zone is None and t["jurisdiction_id"] == JID_MILTON:
                zone = lookup_milton_zone_at_point(geo["lon"], geo["lat"])
            if zone is None:
                print("  BLOCKED: no non-CITY zoning district polygon at centroid "
                      "(this row will NOT flip card_complete even after geo/value patch)")
            else:
                existing_zd = rest_get(
                    f"zoning_districts?jurisdiction_id=eq.{t['jurisdiction_id']}"
                    f"&code=eq.{urllib.parse.quote(zone['zone_code'])}")
                if not existing_zd:
                    print(f"  WARNING: no pre-existing zoning_districts row for "
                          f"jurisdiction_id={t['jurisdiction_id']} code={zone['zone_code']} -- "
                          f"SKIPPING zone insert to avoid G-regression risk")
                else:
                    rest_post("parcel_zones", {
                        "parcel_id": t["parcel_id"],
                        "jurisdiction_id": t["jurisdiction_id"],
                        "zone_code": zone["zone_code"],
                        "zone_name": zone["zone_name"],
                        "source": zone["source"],
                    }, prefer="return=minimal")
                    zones_written += 1
                    print(f"  INSERTED parcel_zones: jurisdiction_id={t['jurisdiction_id']} "
                          f"zone_code={zone['zone_code']} (source={zone['source']}, reused "
                          f"existing zoning_districts id={existing_zd[0]['id']})")

        body = {}
        if row.get("latitude") is None and geo.get("lat") is not None:
            body["latitude"] = geo["lat"]
        if row.get("longitude") is None and geo.get("lon") is not None:
            body["longitude"] = geo["lon"]
        if val:
            if row.get("assessed_value") is None and val.get("assessed_value") is not None:
                body["assessed_value"] = val["assessed_value"]
            if row.get("market_value") is None and val.get("market_value") is not None:
                body["market_value"] = val["market_value"]

        if not body:
            print("  MCA fields already complete, nothing to patch")
        else:
            body["assessed_value_source"] = "santa_rosa_i_10row_backfill_20260825:parcelview.srcpa.gov+arcgis_centroid"
            rest_patch(f"multi_county_auctions?county=eq.santa_rosa&case_number=eq."
                       f"{urllib.parse.quote(t['case_number'])}", body)
            patched += 1
            print(f"  PATCHED mca: {body}")
            print(f"  situs on file: parcelview={val.get('situs') if val else None} | "
                  f"mca={row.get('property_address')}")

    print(f"\nmulti_county_auctions patched={patched} of {len(TARGETS)} targeted, "
          f"parcel_zones inserted={zones_written} of {len(TARGETS)} targeted")

    print(f"\n=== DEFERRED (not fixed this session): {DEFERRED_CASE_NUMBER} ===")
    print("  No parcel_id/address/coords/value on file, no source_url captured by the")
    print("  tier1 sweep. Confirmed live: not present on santarosa.realforeclose.com's")
    print("  auction-preview calendar for its on-file auction_date (2026-07-16) or any")
    print("  of 9 nearby dates checked. civitekflorida.com/ocrs/county/57/ has no")
    print("  GET-able case-detail route. Genuinely unrecoverable this session, matches")
    print("  the prior session's documented finding for this same case_number.")

    if patched == 0 and zones_written == 0:
        print("FAIL-LOUD: 0 rows written across both tables despite "
              f"{len(TARGETS)} candidates fetched. Check BLOCKED/WARNING output above.",
              file=sys.stderr)
        sys.exit(1)

    print("\n=== AFTER pencil_dod_evaluate_county('santa_rosa') ===")
    after = rpc("pencil_dod_evaluate_county", {"p_county": "santa_rosa"})
    print(json.dumps(after, indent=2))

    if baseline.get("G", {}).get("pass") and not after.get("G", {}).get("pass"):
        print("\nREGRESSION DETECTED: G flipped PASS->FAIL from this fix (should not "
              "happen -- all zone codes used reused pre-existing zoning_districts rows).",
              file=sys.stderr)
        sys.exit(1)

    print("\n### SQL VERIFICATION")
    print(f"BEFORE I: {json.dumps(baseline.get('I'))}")
    print(f"AFTER  I: {json.dumps(after.get('I'))}")
    print(f"BEFORE G: {json.dumps(baseline.get('G'))}")
    print(f"AFTER  G: {json.dumps(after.get('G'))}")


if __name__ == "__main__":
    main()

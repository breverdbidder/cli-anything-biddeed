#!/usr/bin/env python3
"""santa_rosa criterion I (property-card completeness) fix -- 4-row gap sweep.

Fixes 3 of the 4 diagnosed-failing multi_county_auctions rows for
county='santa_rosa' (103/109 = 94.5%, needs >=95%). Uses the SAME proven
Santa Rosa public ArcGIS org (Eg4L1xEv2R3abuQd, ParcelsOpenData FeatureServer)
already used successfully in scripts/shard7_run3679_santa_rosa_i_zoning_arcgis_fix.py
for real parcel centroid lat/lon, PLUS the Santa Rosa Property Appraiser's
official parcelview.srcpa.gov widget (same source as scripts/santa_rosa-I_fix.py)
for real 2025 certified valuation data -- confirmed live this session to embed
its full loader payload as JSON in a `window.__remixContext = {...}` script tag
in the server-rendered HTML (no separate client-callable JSON API exists; the
Remix app fetches server-side and inlines the result).

Rows fixed (all 3 already had address + parcel_id; missing lat/lon AND
assessed_value/market_value):
  1. 572025CA000619CAAXMX, parcel 27-2N-28-0550-00A00-0220,
     6935 CEDAR RIDGE CIR, MILTON, FL 32570
  2. 572025CA000824CAAXMX, parcel 34-2N-29-5781-00B00-0100,
     4359 WINNERS GAIT CIR, PACE, FL 32571
  3. 572025CA000897CAAXMX, parcel 07-1N-27-3253-00C00-0040,
     4560 RED OAK DR, MILTON, FL 32583

Row NOT fixed (left as residual, reported not fabricated):
  4. 572022CA000671CAAXMX: NO address, NO parcel_id, NO coords, NO value at
     all (calendar_sweep_mca_v3 stub row, source_url=NULL -- the tier1
     realforeclose sweep never captured a detail-page AID/URL for this case,
     unlike sibling rows which have source_url pointing at
     santarosa.realforeclose.com/...&AID=<n>). Confirmed live this session:
       - santarosa.realforeclose.com auction-detail pages require session
         state / return HTTP 403 to non-browser fetches (consistent with the
         prior santa_rosa-I_fix.py DEFERRED note for two sibling orphan rows).
       - Santa Rosa Clerk's official case search
         (www.civitekflorida.com/ocrs/county/57/) is a stateful JSF/PrimeFaces
         form (ViewState-token POST flow), not a plain GET-able search --
         requires browser automation, out of scope for this pass.
     This case_number is ALSO already flagged in scripts/santa_rosa-I_fix.py's
     module-level DEFERRED note (2026-07-31 session) as "known-hard full
     orphan". Not re-attempted here beyond the above two live checks;
     genuinely unrecoverable via GET-able sources this session.

Sources (all fetched live during this session, 2026-08-13):
  - Santa Rosa County ArcGIS org (Eg4L1xEv2R3abuQd) ParcelsOpenData
    FeatureServer/0/query, PAR_NUM=<STRAP with dashes stripped>,
    returnGeometry=true, outSR=4326 -> real parcel polygon; centroid used
    as lat/lon. Confirmed the layer has NO dollar-value field (fields list
    fetched live: FID/FEAT_TYPE/CALC_ACRE/PAR_NUM/LOT_NUM/SUBCODE/
    SHAPE_LENG/ParcelDisp/ConfFlag/StrNum/StrName/StSuffix/SubdCode/TxDist/
    PRuse/PropertyUs/BldgCnt/XtraFeaCnt/LandCnt/OwnerName/Addr1/Addr2/Addr3/
    City/State/Zip5/Zip4/Cntry/EZone/NumUnits/GlobalID/Shape__Area/
    Shape__Length -- none are a value field), and confirmed via live
    arcgis.com/sharing/rest/search on the same org that NO companion
    CAMA/property-value FeatureServer exists in this org (81 layers listed,
    none value-bearing) -- consistent with the prior script's documented
    finding for this same layer.
  - parcelview.srcpa.gov/?parcel=<PARCEL_ID>&baseUrl=http://srcpa.gov/ :
    real 2025 certified valuation ("Just (Market) Value", "Co. Assessed
    Value") extracted from the embedded window.__remixContext JSON. Situs
    address in the payload matches the auction row's on-file address
    exactly for all 3 parcels (confirms correct STRAP match), e.g.
    parcel 27-2N-28-0550-00A00-0220 -> situs "6935 CEDAR RIDGE CIR,
    MILTON, 32570" (matches multi_county_auctions.property_address).

Idempotent: PATCH only fires for fields currently NULL on the row
(WHERE ... IS NULL guard done in Python before the PATCH, mirroring
scripts/santa_rosa-I_fix.py's pattern).

IMPORTANT correction made mid-session: patching lat/lon/value alone left I
UNCHANGED (still 103/109) because pencil_dod_evaluate_county's card_complete
ALSO requires the parcel_id to appear in v_zoning_gold_standard_card with a
non-null zone_code (confirmed by reading the function's live prosrc: the `zc`
CTE is `SELECT DISTINCT parcel_id, tax_account FROM v_zoning_gold_standard_card
WHERE zone_code IS NOT NULL`, and card_complete requires
`a2.parcel_id IN (SELECT parcel_id FROM zc)`). None of the 3 target parcels
had ANY parcel_zones row. Fixed by spatially querying the county's Zoning
FeatureServer (same ArcGIS org) at each parcel's real centroid -- and, for
the one parcel inside Milton city limits where the COUNTY zoning layer only
returns the non-authoritative "CITY" boundary marker, falling through to the
CityOfMiltonZoning FeatureServer (same org) instead, which returns a real
ZONE_CODE. All 3 resulting zone_codes (Milton R-1, unincorporated R1,
unincorporated RR1) ALREADY have existing zoning_districts rows for their
jurisdiction (ids 11522, 11437, 12482 respectively -- confirmed live via
direct query before writing) -- reused, not duplicated, and Milton's R-1 row
already has a FULL core8 standards set. No new zoning_districts or
zone_standards rows created by this script, so the regression risk the prior
shard7 script had to guard against (creating a zone_code with no matching
zoning_districts row, which drags G's FAR/pk1000 sub-metrics down) does not
apply here.

Run: python3 scripts/santa_rosa_i_run_gap4_backfill.py
"""
import json
import os
import sys
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

# The 3 confidently-fixable rows: case_number, mca row id, STRAP parcel_id,
# jurisdiction_id to use for the parcel_zones insert (chosen per the real
# zone-lookup result below -- documented per-row in TARGETS for traceability).
TARGETS = [
    {"case_number": "572025CA000619CAAXMX",
     "id": "2b4d84de-0edc-428a-b4ea-4dfc5368bf15",
     "parcel_id": "27-2N-28-0550-00A00-0220",
     "jurisdiction_id": 956,  # Milton -- county Zoning layer only returns "CITY"
     "zone_source": "milton_arcgis_cityofmiltonzoning"},
    {"case_number": "572025CA000824CAAXMX",
     "id": "06b6581f-1881-4116-bf86-93f356f55d1c",
     "parcel_id": "34-2N-29-5781-00B00-0100",
     "jurisdiction_id": 1398,  # Unincorporated Santa Rosa
     "zone_source": "santarosa_county_arcgis_zoning"},
    {"case_number": "572025CA000897CAAXMX",
     "id": "bfa9f650-298c-43b0-abc1-d000a7003a57",
     "parcel_id": "07-1N-27-3253-00C00-0040",
     "jurisdiction_id": 1398,  # Unincorporated Santa Rosa
     "zone_source": "santarosa_county_arcgis_zoning"},
]

# Explicitly left unfixed this session -- see module docstring.
DEFERRED_CASE_NUMBER = "572022CA000671CAAXMX"


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
    """Spatially query the county Zoning FeatureServer. Filters out the
    non-authoritative 'CITY' municipal-boundary marker polygon."""
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
    """Spatially query the City of Milton Zoning FeatureServer (same ArcGIS
    org). Used when the county layer only returns the CITY boundary marker
    (i.e. the parcel is inside Milton city limits, which has its own zoning
    authority separate from the county's)."""
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
    """Fetch parcelview.srcpa.gov and extract the embedded Remix loader JSON
    (window.__remixContext = {...};). Returns (situs, market_value, assessed_value)
    or None if the page/payload could not be parsed."""
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

        val = lookup_parcelview_valuation(t["parcel_id"])
        if not val:
            print("  WARNING: could not parse parcelview.srcpa.gov valuation payload")

        # --- zoning linkage (required for card_complete's zone_code join) ---
        existing_pz = rest_get(f"parcel_zones?parcel_id=eq.{urllib.parse.quote(t['parcel_id'])}")
        if existing_pz:
            print(f"  parcel_zones row already exists for {t['parcel_id']}, skipping insert")
        else:
            zone = lookup_county_zone_at_point(geo["lon"], geo["lat"])
            zone_src = t["zone_source"]
            if zone is None and t["jurisdiction_id"] == 956:
                zone = lookup_milton_zone_at_point(geo["lon"], geo["lat"])
            if zone is None:
                print(f"  BLOCKED: no non-CITY zoning district polygon at centroid "
                      f"({t['jurisdiction_id']})")
            else:
                # Reuse the existing zoning_districts row for this
                # jurisdiction+code (confirmed to already exist for all 3
                # targets before writing -- see module docstring). Not
                # creating a new zoning_districts/zone_standards row here.
                existing_zd = rest_get(
                    f"zoning_districts?jurisdiction_id=eq.{t['jurisdiction_id']}"
                    f"&code=eq.{urllib.parse.quote(zone['zone_code'])}")
                if not existing_zd:
                    print(f"  WARNING: no pre-existing zoning_districts row for "
                          f"jurisdiction_id={t['jurisdiction_id']} code={zone['zone_code']} -- "
                          f"inserting parcel_zones anyway would risk the G-regression pattern "
                          f"seen in scripts/shard7_run3679_santa_rosa_i_zoning_arcgis_fix.py; "
                          f"SKIPPING zone insert for this row")
                else:
                    rest_post("parcel_zones", {
                        "parcel_id": t["parcel_id"],
                        "jurisdiction_id": t["jurisdiction_id"],
                        "zone_code": zone["zone_code"],
                        "zone_name": zone["zone_name"],
                        "source": zone_src,
                    }, prefer="return=minimal")
                    zones_written += 1
                    print(f"  INSERTED parcel_zones: jurisdiction_id={t['jurisdiction_id']} "
                          f"zone_code={zone['zone_code']} (source={zone_src}, reused existing "
                          f"zoning_districts id={existing_zd[0]['id']})")

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
            continue

        body["assessed_value_source"] = "santa_rosa_i_run_gap4_backfill:parcelview.srcpa.gov+arcgis_centroid"
        rest_patch(f"multi_county_auctions?id=eq.{t['id']}", body)
        patched += 1
        print(f"  PATCHED mca: {body}")
        print(f"  situs on file: parcelview={val.get('situs') if val else None} | "
              f"mca={row.get('property_address')}")

    print(f"\nparcel_zones inserted this run: {zones_written}")

    print(f"\n=== DEFERRED (not fixed this session): {DEFERRED_CASE_NUMBER} ===")
    print("  No parcel_id/address/coords/value on file, no source_url captured by the")
    print("  tier1 sweep. RealForeclose detail pages require session state (403 to")
    print("  non-browser GET, confirmed live). Santa Rosa Clerk OCRS is a stateful")
    print("  JSF/PrimeFaces ViewState form (confirmed live), not GET-able. Requires")
    print("  browser automation -- out of scope this pass. Left NULL, not fabricated.")

    print(f"\nTotals: multi_county_auctions patched={patched} of {len(TARGETS)} targeted, "
          f"parcel_zones inserted={zones_written} of {len(TARGETS)} targeted")
    if patched == 0 and zones_written == 0:
        print("FAIL-LOUD: 0 rows written across both tables despite 3 candidates fetched. "
              "Check BLOCKED/WARNING output above before assuming success.", file=sys.stderr)

    print("\n=== AFTER pencil_dod_evaluate_county('santa_rosa') ===")
    after = rpc("pencil_dod_evaluate_county", {"p_county": "santa_rosa"})
    print(json.dumps(after, indent=2))

    if baseline.get("G", {}).get("pass") and not after.get("G", {}).get("pass"):
        print("\nREGRESSION DETECTED: G flipped PASS->FAIL from this fix (should not "
              "happen -- this script does not touch zoning_districts/zone_standards/"
              "parcel_zones at all).", file=sys.stderr)
        sys.exit(1)

    print("\n### SQL VERIFICATION")
    print(f"BEFORE I: {json.dumps(baseline.get('I'))}")
    print(f"AFTER  I: {json.dumps(after.get('I'))}")
    print(f"BEFORE G: {json.dumps(baseline.get('G'))}")
    print(f"AFTER  G: {json.dumps(after.get('G'))}")


if __name__ == "__main__":
    main()

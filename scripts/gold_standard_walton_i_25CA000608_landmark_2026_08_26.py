#!/usr/bin/env python3
"""Gold Standard walton letter I (property card completeness) — 2026-08-26,
2nd fix this session: case 25CA000608.

Context: this case_number was previously investigated and marked a genuine
data ceiling by scripts/gold_standard_shard3_walton_i_run9906_c5a8b2c7.py
(RealForeclose auction detail 403, civitek OCRS is a JSF postback form,
qpublic/waltonpa.com bot-blocked, realforeclose_aids has parcel_id=
'Property Appraiser' scrape-artifact placeholder). That investigation was
correct for the sources it tried. This session found a genuinely NEW,
previously-unexplored source for the same case: realforeclose_aids also
carries `case_clerk_url`, a direct link to a specific recorded book/page on
the Walton County Clerk's LandmarkWeb GetDocumentByBookPage endpoint (a
different system than the civitek OCRS search form). That endpoint is
directly GET-fetchable (no JS postback) and returned the actual recorded
Final Judgment of Foreclosure for this case as a scanned PDF.

============================================================================
SOURCE CHAIN (VERIFIED live this session)
============================================================================
1. realforeclose_aids.case_clerk_url for case_number=25CA000608:
   http://orsearch.clerkofcourts.co.walton.fl.us/LandmarkWeb/Document/
   GetDocumentByBookPage/?booktype=OR&booknumber=3403&pagenumber=21
   -> HTTP 200, returns a 5-page scanned PDF (Walton County Official
   Records Inst #20260025596, OR Bk 3403 Pg 21-25).

2. Read the PDF directly (rendered pages to images, read by inspection —
   no OCR tool available in this environment, but the document is a
   standard Florida "Final Judgment of Foreclosure" template, machine-typed,
   fully legible):
     Case No. 25000608CAAXMX (=25CA000608), MIDFIRST BANK v. MISTY FRANTZ.
     Legal description (metes-and-bounds), Walton County, FL:
       "COMMENCE AT THE SOUTHEAST CORNER OF THE NORTHEAST QUARTER OF THE
       NORTHWEST QUARTER OF SECTION 14, TOWNSHIP 3 NORTH, RANGE 19 WEST,
       WALTON COUNTY, FLORIDA; THENCE RUN SOUTH 88 DEGREES 52 MINUTES 44
       SECONDS WEST, A DISTANCE OF 1334.19 FEET TO THE POINT OF BEGINNING;
       THENCE CONTINUE SOUTH 88 DEGREES 14 MINUTES 52 SECONDS WEST, A
       DISTANCE OF 102.00 FEET; THENCE NORTH 01 DEGREES 06 MINUTES 59
       SECONDS WEST, A DISTANCE OF 179.43 FEET TO THE SOUTHERLY
       RIGHT-OF-WAY LINE OF JUNIPER LAKE ROAD..."
     Copies-furnished section gives the defendant's service address:
       "MISTY FRANTZ, 2008 JUNIPER LAKE RD, DEFUNIAK SPRINGS, FL 32433-8502"

3. Cross-checked BOTH the legal description AND the name+address against
   Walton EnerGov ArcGIS FeatureServer Layer 4 (Parcels), queried by
   OWNER_NAME LIKE '%FRANTZ%' (VERIFIED live):
     PARCELNO='14-3N-19-19010-003-0130'
     OWNER_NAME='FRANTZ MISTY'
     OWN_ADDRESS_1='2008 JUNIPER LAKE RD', OWN_CITY='DEFUNIAK SPRINGS'
     LEGAL_1/2/3='COM SE/C NE4 OF NW4 SEC 14-3N-19W, S 88 DEG 52'44"W
       1334.19FT TO POB; CONT S 88 DEG 14'52"W 102FT, N 01 DEG 06'59"W
       179.43FT TO S...' -- EXACT match to the judgment's legal description
       (section/township/range, bearings, and distances all identical).
     APPRAISED_VALUE=142556, JUST_VALUE=142556.
   This is a 3-way independent corroboration (case number in the recorded
   judgment -> legal description -> EnerGov parcel attribute match), not a
   guess. No fabrication: every written value traces to this chain.

4. Parcel centroid (EnerGov Layer 4 geometry, WGS84): lat=30.76105276103693,
   lon=-86.11824433950206.

5. EnerGov Layer 19 (Zoning) point-in-polygon at that centroid:
   ZONE_CLASS='Urban Residential', PLAN_AREA='North Central'. A
   zoning_districts row for code='Urban Residential' already exists live
   (id=11996, jurisdiction_id=1333 Unincorporated Walton County,
   category=residential) — reused as-is, no new district invented.

Fix: PATCH multi_county_auctions (property_address, latitude, longitude,
assessed_value, market_value, parcel_id) for id=1d2916fb-ef5d-45b8-bfc0-
a0d28e9e903f, then INSERT parcel_zones linking the parcel to the existing
Urban Residential district. This closes ALL FOUR missing card_complete
dimensions (address/geo/value/zoned_parcel) for this one row from a single
verified source chain.

FAIL-LOUD invariant: if the target row is parsed but zero DB writes occur,
raise.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

SB_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

DISPATCH_TAG = "gs_walton_i_25CA000608_landmark_20260826"
ENERG0V_BASE = "https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer"

ROW_ID = "1d2916fb-ef5d-45b8-bfc0-a0d28e9e903f"
CASE_NUMBER = "25CA000608"
PARCEL_ID = "14-3N-19-19010-003-0130"
PROPERTY_ADDRESS = "2008 JUNIPER LAKE RD, DEFUNIAK SPRINGS, FL 32433"


def _sb_headers(prefer: str = "") -> dict:
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    return h


def sb_get(table: str, params: dict) -> list:
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}?{qs}", headers=_sb_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(table: str, filter_qs: str, body: dict) -> bytes:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{filter_qs}",
        data=json.dumps(body).encode(),
        headers=_sb_headers("return=minimal"),
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sb_post(table: str, body, prefer: str = "return=minimal") -> bytes:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=json.dumps(body).encode(),
        headers=_sb_headers(prefer),
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sb_rpc(fn: str, payload: dict):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(payload).encode(),
        headers=_sb_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def arcgis_query(url: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{qs}",
        headers={"User-Agent": "BidDeed-GoldStandard-Walton-608/1.0; contact:ariel@everestcapitalusa.com"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main() -> int:
    if not SB_KEY or not SB_URL:
        print("ERROR: missing Supabase credentials/env", file=sys.stderr)
        return 1

    print("=== BEFORE (walton I) ===")
    before = sb_rpc("pencil_dod_evaluate_county", {"p_county": "walton"})
    print(json.dumps(before.get("I", {}), indent=2))

    row = sb_get(
        "multi_county_auctions",
        {"select": "id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value",
         "id": f"eq.{ROW_ID}"},
    )
    if not row:
        print(f"SKIP: row {ROW_ID} not found live")
        return 0
    row = row[0]
    print(f"Live row: {row}")
    assert row["case_number"] == CASE_NUMBER, f"case_number mismatch: {row['case_number']}"

    # Re-verify EnerGov parcel attributes live (not reused from memory)
    parcel_result = arcgis_query(f"{ENERG0V_BASE}/4/query", {
        "where": f"PARCELNO='{PARCEL_ID}'",
        "outFields": "PARCELNO,OWNER_NAME,APPRAISED_VALUE,JUST_VALUE",
        "returnGeometry": "true", "geometryType": "esriGeometryPolygon",
        "outSR": "4326", "f": "json",
    })
    feats = parcel_result.get("features", [])
    if not feats:
        raise RuntimeError(f"FAIL-LOUD: EnerGov no longer returns parcel {PARCEL_ID} — aborting, no write")
    attrs = feats[0]["attributes"]
    print(f"EnerGov Layer 4 VERIFIED: {attrs}")
    assert attrs["OWNER_NAME"] == "FRANTZ MISTY", f"owner mismatch: {attrs['OWNER_NAME']}"

    rings = feats[0]["geometry"]["rings"]
    flat = [pt for ring in rings for pt in ring]
    lon = sum(p[0] for p in flat) / len(flat)
    lat = sum(p[1] for p in flat) / len(flat)
    appraised = float(attrs["APPRAISED_VALUE"])
    just_value = float(attrs["JUST_VALUE"])
    print(f"centroid lat={lat} lon={lon} appraised={appraised} just_value={just_value}")

    # PATCH the mca row
    patch = {
        "parcel_id": PARCEL_ID,
        "property_address": PROPERTY_ADDRESS,
        "latitude": lat,
        "longitude": lon,
        "assessed_value": appraised,
        "market_value": just_value,
        "updated_at": "now()",
    }
    sb_patch("multi_county_auctions", f"id=eq.{ROW_ID}", patch)
    print(f"PATCHED multi_county_auctions id={ROW_ID}: {list(patch.keys())}")

    # zoning link
    zone_result = arcgis_query(f"{ENERG0V_BASE}/19/query", {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONE_CLASS,PLAN_AREA", "inSR": "4326", "f": "json",
    })
    zfeats = zone_result.get("features", [])
    if not zfeats or not zfeats[0]["attributes"].get("ZONE_CLASS"):
        print("WARNING: no ZONE_CLASS resolved — card_complete may still fail for this row")
    else:
        zone_class = zfeats[0]["attributes"]["ZONE_CLASS"].strip()
        print(f"EnerGov Layer 19 VERIFIED: ZONE_CLASS={zone_class!r} PLAN_AREA={zfeats[0]['attributes'].get('PLAN_AREA')!r}")

        existing_pz = sb_get("parcel_zones", {"select": "id", "parcel_id": f"eq.{PARCEL_ID}", "limit": "1"})
        if existing_pz:
            print("parcel_zones already present for this parcel (skip insert)")
        else:
            district = sb_get(
                "zoning_districts",
                {"select": "id,jurisdiction_id,code,category", "code": f"eq.{zone_class}", "limit": "1"},
            )
            if not district:
                print(f"SKIP zone link: no existing zoning_districts row for code={zone_class!r}")
            else:
                jur_id = district[0]["jurisdiction_id"]
                print(f"zoning_districts VERIFIED match: id={district[0]['id']} jurisdiction_id={jur_id}")
                sb_post(
                    "parcel_zones",
                    {
                        "parcel_id": PARCEL_ID,
                        "tax_account": PARCEL_ID,
                        "jurisdiction_id": jur_id,
                        "zone_code": zone_class,
                        "source": f"walton_enerGov_arcgis/{DISPATCH_TAG}_{date.today().isoformat()}",
                        "effective_date": "2018-12-11",
                    },
                    prefer="resolution=ignore-duplicates,return=minimal",
                )
                print(f"parcel_zones INSERTED: {PARCEL_ID} -> jur={jur_id} zone={zone_class}")

    print("\n=== AFTER (walton I) ===")
    after = sb_rpc("pencil_dod_evaluate_county", {"p_county": "walton"})
    print(json.dumps(after.get("I", {}), indent=2))

    print("\n=== SUMMARY ===")
    print(f"I before: {before.get('I')}")
    print(f"I after:  {after.get('I')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

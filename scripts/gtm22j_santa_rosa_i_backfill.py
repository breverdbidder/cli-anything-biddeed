#!/usr/bin/env python3
"""GTM-22J santa_rosa criterion I (property-card completeness) backfill.

Fixes 7 of the 10 diagnosed-failing multi_county_auctions rows for
county='santa_rosa' by filling the specific missing card_complete fields
(lat/long, assessed_value/market_value, parcel_zones.zone_code) with REAL,
sourced data. Row 1 (orphan case 572022CA000671CAAXMX, no parcel linkage at
all) is SKIPPED — RealForeclose blocks non-browser fetches (403) and no
Clerk case record was found in the time available; left for a future pass.

Sources (all fetched live during this session, 2026-07-19):
  - Santa Rosa County Property Appraiser parcel-detail widget:
    https://parcelview.srcpa.gov/?parcel=<PARCEL_ID>&baseUrl=http://srcpa.gov/
    -> real 2025 certified "Co. Assessed Value" (-> assessed_value) and
       "Just (Market) Value" (-> market_value), and real zoning records
       (code + jurisdiction source, e.g. "County" or "Town of Jay").
  - Santa Rosa County Property Appraiser open-data parcel polygons (ArcGIS
    Feature Service, official, updated 2025-03-20):
    https://services.arcgis.com/Eg4L1xEv2R3abuQd/arcgis/rest/services/ParcelsOpenData/FeatureServer/0
    -> used ONLY for the 2 parcels with no street address ("NO ADDRESS ON
       TAX ROLL"); real parcel centroid computed via shoelace formula from
       the official parcel boundary geometry (outSR=4326).
  - US Census Bureau geocoder (official, free, no key):
    https://geocoding.geo.census.gov/geocoder/locations/onelineaddress
    -> used for the 2 parcels that DO have a real street address on file.

Idempotent: every UPDATE/INSERT is a no-op re-run (WHERE ... IS NULL guards
on multi_county_auctions writes; parcel_zones INSERT uses a pre-check + is
safe to re-run since it only inserts when no row exists for that parcel_id).

Run: python3 scripts/gtm22j_santa_rosa_i_backfill.py
"""
import os
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


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


def rest_post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation,resolution=ignore-duplicates"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


# --- multi_county_auctions fixes -------------------------------------------------
# source for all assessed_value/market_value/lat/long below: see module docstring
MCA_FIXES = [
    {
        "case_number": "2026091",
        "fields": {"assessed_value": 72600, "market_value": 80000},
        "source": "parcelview.srcpa.gov parcel 19-2S-26-0462-00B00-0040: "
                   "2025 Co. Assessed Value $72,600 / 2025 Just (Market) Value $80,000",
    },
    {
        "case_number": "572025CA000652CAAXMX",
        "fields": {"latitude": 30.622948970398, "longitude": -87.150298067409,
                   "market_value": 122321},
        "source": "Census geocoder onelineaddress '4081 WINDSOR LN, PACE, FL 32571' "
                   "-> lat 30.622948970398 / lon -87.150298067409 (exact TIGER match); "
                   "parcelview.srcpa.gov parcel 04-1N-29-0754-00B00-0770: "
                   "2025 Just (Market) Value $122,321 (assessed_value already present: $60,401)",
    },
    {
        "case_number": "2026085",
        "fields": {"market_value": 69851},
        "source": "parcelview.srcpa.gov parcel 41-5N-29-2080-00A00-0090: "
                   "2025 Just (Market) Value $69,851 (assessed_value already present: $51,905)",
    },
    {
        "case_number": "2026077",
        "fields": {"market_value": 317408},
        "source": "parcelview.srcpa.gov parcel 05-3S-29-0215-00100-0010: "
                   "2025 Just (Market) Value $317,408 (assessed_value already present: $270,886)",
    },
    {
        "case_number": "2026110",
        "fields": {"latitude": 30.536238667077654, "longitude": -87.10475772992115,
                   "assessed_value": 44081, "market_value": 92160},
        "source": "no street address on tax roll -> centroid computed (shoelace) from real "
                   "parcel polygon, ArcGIS FeatureServer "
                   "services.arcgis.com/Eg4L1xEv2R3abuQd/.../ParcelsOpenData/FeatureServer/0, "
                   "PAR_NUM=401N280090379000010 (=40-1N-28-0090-37900-0010); "
                   "values from parcelview.srcpa.gov: 2025 Co. Assessed Value $44,081 / "
                   "Just (Market) Value $92,160",
    },
    {
        "case_number": "2026111",
        "fields": {"latitude": 30.9463331295764, "longitude": -87.1497682669472,
                   "assessed_value": 9884, "market_value": 29400},
        "source": "no street address on tax roll -> centroid computed (shoelace) from real "
                   "parcel polygon, ArcGIS FeatureServer "
                   "services.arcgis.com/Eg4L1xEv2R3abuQd/.../ParcelsOpenData/FeatureServer/0, "
                   "PAR_NUM=415N29197000A000320 (=41-5N-29-1970-00A00-0320); "
                   "values from parcelview.srcpa.gov: 2025 Co. Assessed Value $9,884 / "
                   "Just (Market) Value $29,400",
    },
    {
        "case_number": "2026117",
        "fields": {"latitude": 30.603079037813, "longitude": -87.09877087401,
                   "assessed_value": 197033, "market_value": 368160},
        "source": "Census geocoder onelineaddress '5392 HWY 90, PACE, FL 32571' "
                   "-> lat 30.603079037813 / lon -87.09877087401 (exact TIGER match); "
                   "parcelview.srcpa.gov parcel 12-1N-29-0000-01000-0000: "
                   "2025 Co. Assessed Value $197,033 / Just (Market) Value $368,160",
    },
]

# --- parcel_zones inserts ---------------------------------------------------------
# source for every zone_code: parcelview.srcpa.gov "zonings" block for that parcel,
# which cites its own upstream source (County zoning-classification page, or the
# Town of Jay zoning map PDF hosted by SRCPA).
PARCEL_ZONES = [
    {
        "parcel_id": "41-5N-29-2080-00A00-0090",
        "jurisdiction_id": 1124,  # Jay
        "zone_code": "RM-A",
        "zone_name": "Residential Medium - Activity Center",
        "source": "parcelview.srcpa.gov parcel 41-5N-29-2080-00A00-0090 zonings[]; "
                   "source=Town of Jay, https://srcpa.gov/resources/Zoning%20-%20Town%20of%20Jay.pdf",
    },
    {
        "parcel_id": "05-3S-29-0215-00100-0010",
        "jurisdiction_id": 828,  # Gulf Breeze
        "zone_code": "C-1",
        "zone_name": "Commercial",
        "source": "parcelview.srcpa.gov parcel 05-3S-29-0215-00100-0010 zonings[]; "
                   "source=City of Gulf Breeze, "
                   "https://library.municode.com/fl/gulf_breeze/codes/code_of_ordinances?nodeId=SPBLADECO_CH21LAUSZO_ARTIIDIRE_DIV1GE",
    },
    {
        "parcel_id": "04-1N-29-0754-00B00-0770",
        "jurisdiction_id": 1398,  # Unincorporated Santa Rosa (Pace)
        "zone_code": "R1M",
        "zone_name": "Mixed Residential Subdivision",
        "source": "parcelview.srcpa.gov parcel 04-1N-29-0754-00B00-0770 zonings[]; "
                   "source=County, https://www.santarosa.fl.gov/193/Zoning-Classifications "
                   "(parcel also carries overlay R1M-APZ1, Air Accident Potential Zone 1 -- "
                   "base district R1M used as primary zone_code)",
    },
    {
        "parcel_id": "40-1N-28-0090-37900-0010",
        "jurisdiction_id": 956,  # Milton
        "zone_code": "R1",
        "zone_name": "Single Family",
        "source": "parcelview.srcpa.gov parcel 40-1N-28-0090-37900-0010 zonings[]; "
                   "source=County, https://www.santarosa.fl.gov/193/Zoning-Classifications",
    },
    {
        "parcel_id": "41-5N-29-1970-00A00-0320",
        "jurisdiction_id": 1124,  # Jay
        "zone_code": "RM",
        "zone_name": "Residential Medium",
        "source": "parcelview.srcpa.gov parcel 41-5N-29-1970-00A00-0320 zonings[]; "
                   "source=Town of Jay, https://srcpa.gov/resources/Zoning%20-%20Town%20of%20Jay.pdf",
    },
    {
        "parcel_id": "12-1N-29-0000-01000-0000",
        "jurisdiction_id": 1398,  # Unincorporated Santa Rosa (Pace)
        "zone_code": "HCD",
        "zone_name": "Highway Commercial Development",
        "source": "parcelview.srcpa.gov parcel 12-1N-29-0000-01000-0000 zonings[]; "
                   "source=County, https://www.santarosa.fl.gov/193/Zoning-Classifications "
                   "(parcel also carries R2 Medium Density overlay -- HCD used as primary "
                   "zone_code, matches PropertyUsage 'VACANT - COMMERCIAL')",
    },
]

# NOTE: case_number=2026091 parcel_id 19-2S-26-0462-00B00-0040 already had a
# parcel_zones row (id=832208, zone_code='R1', jurisdiction_id=1398) before
# this session -- confirmed matching against parcelview.srcpa.gov zonings[]
# (code R1, source=County). No insert needed for this parcel.


def main():
    print("=== multi_county_auctions field backfill (county=santa_rosa) ===")
    for fix in MCA_FIXES:
        cn = fix["case_number"]
        rows = rest_get(
            f"multi_county_auctions?case_number=eq.{cn}&county=eq.santa_rosa"
            f"&select=case_number,latitude,longitude,assessed_value,market_value")
        if not rows:
            print(f"  SKIP {cn}: no matching row found")
            continue
        row = rows[0]
        # idempotent: only set fields that are currently NULL
        body = {k: v for k, v in fix["fields"].items() if row.get(k) is None}
        if not body:
            print(f"  {cn}: already complete, nothing to patch")
            continue
        result = rest_patch(
            f"multi_county_auctions?case_number=eq.{cn}&county=eq.santa_rosa", body)
        print(f"  PATCHED {cn}: {body}")
        print(f"    source: {fix['source']}")

    print("\n=== parcel_zones inserts ===")
    for pz in PARCEL_ZONES:
        existing = rest_get(f"parcel_zones?parcel_id=eq.{pz['parcel_id']}&select=id,zone_code")
        if existing:
            print(f"  SKIP {pz['parcel_id']}: parcel_zones row already exists ({existing})")
            continue
        body = {
            "parcel_id": pz["parcel_id"],
            "jurisdiction_id": pz["jurisdiction_id"],
            "zone_code": pz["zone_code"],
            "zone_name": pz["zone_name"],
        }
        result = rest_post("parcel_zones", body)
        print(f"  INSERTED {pz['parcel_id']} -> zone_code={pz['zone_code']}")
        print(f"    source: {pz['source']}")

    print("\nDone. case_number=572022CA000671CAAXMX (orphan, no parcel_id) "
          "intentionally SKIPPED -- see module docstring.")


if __name__ == "__main__":
    main()

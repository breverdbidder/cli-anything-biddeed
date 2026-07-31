#!/usr/bin/env python3
"""santa_rosa criterion I (property-card completeness) fix — dispatch 09f985fc follow-up.

Fixes 3 of the 6 diagnosed-failing multi_county_auctions rows for
county='santa_rosa' by (a) geocoding the 2 rows that have a real on-file
street address but no lat/lon, and (b) inserting a real parcel_zones row
(sourced from Santa Rosa County Property Appraiser) for all 3 rows that
already have a real parcel_id but no zoning link at all.

Fixing even ONE of these 6 rows flips card_complete from 97/103 (94.2%) to
98/103 (95.1%), which crosses the 95% PASS threshold. This script targets
the 3 rows with the highest-confidence, free, already-sourced data (no
paid API, no risky scraping) for margin/durability. The remaining 3 rows
(2 orphan cases behind RealForeclose's 403 anti-bot wall + AcclaimWeb
search API mismatch, 1 known-hard full orphan) are intentionally left for
a future pass — see module-level "DEFERRED" note at bottom.

Sources (all fetched live during this session, 2026-07-31):
  - Santa Rosa County Property Appraiser parcel-detail widget:
    https://parcelview.srcpa.gov/?parcel=<PARCEL_ID>&baseUrl=http://srcpa.gov/
    -> real "zonings[]" block (code + description + source citation) and
       real 2025 "Just (Market) Value" from the certified-values table.
  - US Census Bureau geocoder (official, free, no key):
    https://geocoding.geo.census.gov/geocoder/locations/onelineaddress
    -> exact TIGER-line address match for the 2 rows with a real street
       address on file (WOODVILLE RD Milton, OAKHILL RD Gulf Breeze).

Idempotent: every PATCH/INSERT is a no-op re-run (WHERE ... IS NULL guards
on multi_county_auctions writes; parcel_zones INSERT only fires when no
row already exists for that parcel_id).

Run: python3 scripts/santa_rosa-I_fix.py
"""
import os
import sys
import json
import urllib.request
import urllib.error

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
                 "Content-Type": "application/json",
                 "Prefer": "return=representation,resolution=ignore-duplicates"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def rpc(fn, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


# --- multi_county_auctions geocode fixes ------------------------------------------
# source for lat/lon: US Census geocoder onelineaddress, exact TIGER match
MCA_GEOCODE_FIXES = [
    {
        "id": "3fa9d2c7-83f8-493c-a907-3ce55de36545",
        "case_number": "572025CA000406CAAXMX",
        "fields": {"latitude": 30.588702343793, "longitude": -87.035293960886,
                    "market_value": 149971},
        "source": "Census geocoder onelineaddress '4268 WOODVILLE RD, MILTON, FL 32583' "
                   "-> lat 30.588702343793 / lon -87.035293960886 (exact TIGER match); "
                   "parcelview.srcpa.gov parcel 15-1N-28-5120-00200-0012: "
                   "2025 Just (Market) Value $149,971 (assessed_value already present: $83,616)",
    },
    {
        "id": "6edf871c-7029-4e60-bb81-d4efc5c6f78b",
        "case_number": "572025CA000551CAAXMX",
        "fields": {"latitude": 30.3906718451, "longitude": -87.069140923695,
                    "market_value": 271618},
        "source": "Census geocoder onelineaddress '1474 OAKHILL RD, GULF BREEZE, FL 32563' "
                   "-> lat 30.3906718451 / lon -87.069140923695 (exact TIGER match); "
                   "parcelview.srcpa.gov parcel 28-2S-28-0000-01001-0000: "
                   "2025 Just (Market) Value $271,618 (assessed_value already present: $262,033)",
    },
]

# --- parcel_zones inserts ---------------------------------------------------------
# source for every zone_code: parcelview.srcpa.gov "zonings[]" block for that parcel
PARCEL_ZONES = [
    {
        "parcel_id": "15-1N-28-5120-00200-0012",
        "jurisdiction_id": 1398,  # Unincorporated Santa Rosa (Milton)
        "zone_code": "R1",
        "zone_name": "Single Family",
        "source": "parcelview.srcpa.gov parcel 15-1N-28-5120-00200-0012 zonings[]; "
                   "source=County, https://www.santarosa.fl.gov/193/Zoning-Classifications",
    },
    {
        "parcel_id": "28-2S-28-0000-01001-0000",
        "jurisdiction_id": 1398,  # Unincorporated Santa Rosa (Gulf Breeze area, county zoning)
        "zone_code": "R1",
        "zone_name": "Single Family",
        "source": "parcelview.srcpa.gov parcel 28-2S-28-0000-01001-0000 zonings[]; "
                   "source=County, https://www.santarosa.fl.gov/193/Zoning-Classifications",
    },
    {
        "parcel_id": "05-3S-29-1570-00300-0170",
        "jurisdiction_id": 828,  # Gulf Breeze
        "zone_code": "R-1-AA",
        "zone_name": "Single-Family Residential",
        "source": "parcelview.srcpa.gov parcel 05-3S-29-1570-00300-0170 zonings[]; "
                   "source=City of Gulf Breeze, "
                   "https://library.municode.com/fl/gulf_breeze/codes/code_of_ordinances?nodeId=SPBLADECO_CH21LAUSZO_ARTIIDIRE_DIV1GE",
    },
]

# DEFERRED (not attempted or attempted-and-blocked this session):
#   - 300732f1-4d9a-4364-ad56-465db830ba37 (572025CA000043CAAXMX): no parcel_id.
#     RealForeclose source_url returns HTTP 403 to non-browser fetches (confirmed
#     this session). AcclaimWeb JSON search endpoint pattern from Brevard
#     (commit 276cb9fa) does not match Santa Rosa's AcclaimWeb instance (404 on
#     probed endpoints, confirmed this session) -- needs browser automation.
#   - c1c4bbf5-f601-49b7-82fc-38aa5101581f (572025CA000445CAAXMX): same blockers.
#   - 9cc6143d-f736-4230-8d38-cc486991ca8c (572022CA000671CAAXMX): known-hard full
#     orphan, already explicitly deferred in scripts/gtm22j_santa_rosa_i_backfill.py.
# Fixing the 3 rows below is mathematically sufficient to flip I to PASS
# (98/103 = 95.1% >= 95%), so these 3 are left for a future pass.


def main():
    mca_patched = 0
    pz_inserted = 0

    print("=== multi_county_auctions geocode/value backfill (county=santa_rosa) ===")
    for fix in MCA_GEOCODE_FIXES:
        rid = fix["id"]
        rows = rest_get(
            f"multi_county_auctions?id=eq.{rid}"
            f"&select=id,case_number,latitude,longitude,market_value")
        if not rows:
            print(f"  SKIP {fix['case_number']} ({rid}): no matching row found")
            continue
        row = rows[0]
        # idempotent: only set fields that are currently NULL
        body = {k: v for k, v in fix["fields"].items() if row.get(k) is None}
        if not body:
            print(f"  {fix['case_number']}: already complete, nothing to patch")
            continue
        rest_patch(f"multi_county_auctions?id=eq.{rid}", body)
        mca_patched += 1
        print(f"  PATCHED {fix['case_number']} ({rid}): {body}")
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
        rest_post("parcel_zones", body)
        pz_inserted += 1
        print(f"  INSERTED {pz['parcel_id']} -> zone_code={pz['zone_code']}")
        print(f"    source: {pz['source']}")

    print(f"\nTotals: multi_county_auctions patched={mca_patched}, "
          f"parcel_zones inserted={pz_inserted}")

    if mca_patched == 0 and pz_inserted == 0:
        print("FAIL-LOUD: 0 rows written across both tables despite candidates fetched. "
              "This is either a full re-run (all idempotent guards already satisfied) or "
              "a real failure -- check output above for SKIP reasons before assuming success.",
              file=sys.stderr)

    print("\n=== re-verify pencil_dod_evaluate_county('santa_rosa') ===")
    result = rpc("pencil_dod_evaluate_county", {"p_county": "santa_rosa"})
    print(json.dumps(result.get("I"), indent=2))


if __name__ == "__main__":
    main()

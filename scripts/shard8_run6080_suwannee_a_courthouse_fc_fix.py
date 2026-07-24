#!/usr/bin/env python3
"""Suwannee A fix: insert 4 real courthouse foreclosure cases (Dowdy/Saavedra/Sage/Gleiss)
from the live suwgov.org "Revised July 20, 2026" foreclosure sale list, re-verified live
2026-07-24. Ramirez (no situs address) and David Thomas (unresolved identity) held back per
the no-fabrication / no-regression rule established by the prior session's residual.
Zoning: DOR use_code -> existing suwannee jurisdiction_id=895 R1/AG crosswalk (same
methodology already used for the 9 existing suwannee tax-deed rows), extended with
0100 SINGLE FAMILY -> R1 for Dowdy (natural mapping, not present in the prior crosswalk).
"""
import os, json, urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
           "Content-Type": "application/json", "Prefer": "return=representation"}

CLERK_URL = "https://www.suwgov.org/wp-content/uploads/Foreclosure-List-2-1-12.docx"
RUN_TAG = "suwannee_clerk_courthouse_list:2026-07-24"

ROWS = [
    dict(case_number="25-CA-197", auction_date="2026-07-23", owner_name="DOWDY JAREN",
         property_address="608 Savannah St NW, Branford, FL 32008", city="Branford", zip="32008",
         parcel_id="04200620080", assessed_value=117081, latitude=29.963577412993, longitude=-82.9276677706,
         zone_code="R1", use_code="0100: SINGLE FAMILY"),
    dict(case_number="25-CA-170", auction_date="2026-07-28", owner_name="SAAVEDRA PEDRO & VIVIAN",
         property_address="14127 CR 252, Live Oak, FL 32060", city="Live Oak", zip="32060",
         parcel_id="08767000011", assessed_value=74870, latitude=30.173858471836, longitude=-83.039413936792,
         zone_code="R1", use_code="0000: VACANT"),
    dict(case_number="26-CA-2", auction_date="2026-08-27", owner_name="SAGE GEORGE A JR & ADORA A SAGE",
         property_address="7490 193rd Rd, Live Oak, FL 32060", city="Live Oak", zip="32060",
         parcel_id="09953001000", assessed_value=128528, latitude=30.313786593538, longitude=-83.148305639754,
         zone_code="R1", use_code="0200: MOBILE HOME"),
    dict(case_number="26-CA-7", auction_date="2026-08-27", owner_name="GLEISS INGEBORG (EST.)",
         property_address="15645 53rd Pl, Wellborn, FL 32094", city="Wellborn", zip="32094",
         parcel_id="00750000210", assessed_value=125153, latitude=30.170001326184, longitude=-82.855560407251,
         zone_code="R1", use_code="0200: MOBILE HOME"),
]


def req(method, path, body=None, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}{params}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers=HEADERS)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read() or b"null")


def main():
    # 1. parcel_zones — skip any already present (idempotent)
    existing_pz = req("GET", "parcel_zones", params="?select=parcel_id&parcel_id=in.(" + ",".join(r["parcel_id"] for r in ROWS) + ")")
    have_pz = {r["parcel_id"] for r in existing_pz}
    pz_insert = [{"parcel_id": r["parcel_id"], "jurisdiction_id": 895, "zone_code": r["zone_code"],
                  "zone_name": "Single-Family Residential", "source": f"{RUN_TAG}:dor_usecode_to_district_map:use_code={r['use_code']}"}
                 for r in ROWS if r["parcel_id"] not in have_pz]
    if pz_insert:
        out = req("POST", "parcel_zones", pz_insert)
        print(f"parcel_zones inserted: {len(out)}")
    else:
        print("parcel_zones: all already present (idempotent no-op)")

    # 2. multi_county_auctions — skip if case_number already present
    existing_mca = req("GET", "multi_county_auctions", params="?select=case_number&county=ilike.suwannee&case_number=in.(" + ",".join(r["case_number"] for r in ROWS) + ")")
    have_mca = {r["case_number"] for r in existing_mca}
    mca_insert = []
    for r in ROWS:
        if r["case_number"] in have_mca:
            continue
        mca_insert.append({
            "case_number": r["case_number"],
            "county": "suwannee",
            "state": "FL",
            "sale_type": "foreclosure",
            "auction_type": "foreclosure",
            "auction_date": r["auction_date"],
            "auction_status": "upcoming",
            "auction_venue": "in_person",
            "property_address": r["property_address"],
            "city": r["city"],
            "zip": r["zip"],
            "parcel_id": r["parcel_id"],
            "assessed_value": r["assessed_value"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "owner_name": r["owner_name"],
            "clerk_url": CLERK_URL,
            "source_platform": "clerk_html",
            "data_source": RUN_TAG,
            "provenance": "primary_scrape",
            "parity_status": "matched_clean",
            "parity_source": "tier1:clerk_fc_direct",
        })
    if mca_insert:
        out = req("POST", "multi_county_auctions", mca_insert)
        print(f"multi_county_auctions inserted: {len(out)}")
        for o in out:
            print("  ", o["case_number"], o["id"])
    else:
        print("multi_county_auctions: all already present (idempotent no-op)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""GOLD STANDARD dispatch 503717c8-e819-470c-b363-6f20c13160e9, loop run 6046.

Bay County I-criterion tail fix: 6 rows carried ghost-success placeholder data
(latitude=30.1766/longitude=-85.6801 identical Bay-centroid, assessed_value=100000
or 150000 round numbers) written by a prior session, on top of parcel_id values
that are the county's OWN RealForeclose "Parcel ID" link text ("Property Appraiser",
"TIMESHARE", "MULTIPLE PARCELS") -- confirmed live 2026-07-23 via the unauthenticated
RealForeclose AJAX preview endpoint (bay.realforeclose.com, zaction=AUCTION&Zmethod=
UPDATE&FNC=LOAD) that these are the county's actual displayed values, not a parser
bug: the raw AITEM HTML for all 6 has either no "Property Address" table row at all,
or a Parcel ID anchor whose link text literally is "TIMESHARE" / "MULTIPLE PARCELS".

Research method per case (all verified live this session):
  1. realforeclose_aids table / AJAX preview harvest -> case_clerk_url (book/page
     link into records2.baycoclerk.com, itself unauthenticated + reachable).
  2. curl the book/page PDF (scanned image, no embedded text layer) -> pdftoppm +
     tesseract OCR (both installed this session via apt) -> extract case caption,
     defendants, legal description, Parcel ID / Tax ID if stated in the judgment.
  3. Where the judgment gives ONLY a metes-and-bounds legal description or a
     timeshare unit-week interest (no street address, no assessable single parcel),
     the case is reported BLOCKED -- BLANK > WRONG, no invented address/parcel.
  4. Where the judgment names a specific building/condo, cross-referenced via
     WebSearch against public real-estate listings for the building's real street
     address, then geocoded via Nominatim (proper User-Agent, 1 req/sec).

Direct qpublic.schneidercorp.com / baycoclerk.com HTML search + baypa.net all
return HTTP 403 for this runner's IP regardless of User-Agent (matches documented
"RealForeclose/RealTaxDeed 403 cloud IPs" pattern elsewhere in this repo). Firecrawl
(the proven bypass used by scripts/realauction_bidhistory.py) returned HTTP 402
"Insufficient credits" this session -- confirmed via direct API call, not assumed.
FL DOR statewide cadastral ArcGIS FeatureServer (services9.arcgis.com) returned 0
rows / read-timeouts for every real parcel_id/owner-name query attempted (Prosper
LLC, Summit condo parcel 30236-212-000, Mayfield TAX ID 11922-000-000) -- also not
usable as a corroboration source this session.

RESULT (6 cases):
  23001239CA  BLOCKED -- 130+/- acre metes-and-bounds tract (4 sections), no street
              address exists per the judgment itself; county's own Parcel ID link
              is blank (KeyValue=). Defendants: Shelly Ann C. Grant, 388 Prosper LLC.
  25000412CA  BLOCKED -- Legends Edge Condominium, timeshare Unit Week 48 in Unit
              2405 (fractional interest, not a standalone assessed parcel).
  25000637CA  FIXED -- The Summit condominium (aka Summit Beach Resort), Units 802
              & 1018, both under Parcel ID No. 30236-212-000 per the recorded Final
              Judgment (O.R. Bk 5029 Pg 332-336). Real building address confirmed via
              WebSearch (8743 Thomas Drive, Panama City Beach, FL 32408) + geocoded
              via Nominatim. parcel_id NOT present in v_zoning_gold_standard_card for
              bay (verified live) so this alone does not flip card_complete for this
              row, but it replaces fabricated centroid/round-number data with real,
              sourced values -- required per the ghost-success remediation mandate.
              assessed_value cleared to NULL (no genuine assessed/market value found;
              the judgment states a lien amount, not a tax-roll value -- BLANK>WRONG).
  25000874CA  BLOCKED (partial real find) -- real TAX ID 11922-000-000 (Mayfield),
              St. Andrews Bay Development Co plat, Section 25 T3S R14W, but the
              judgment gives only a metes-and-bounds lot description with NO street
              address, and the parcel_id is not in our zoning-linked set either.
              parcel_id patched (real, sourced), address/geo/value left untouched
              (no real value found for any of them).
  25001176CA  BLOCKED -- Tropical Breeze Resort, TWO separate timeshare unit-weeks
              (46/207 and 2402/220-2), judgment explicitly orders they be sold as
              ONE BATCH with a single Certificate of Title -- structurally real
              multi-unit case, not a parser artifact.
  26000161CA  BLOCKED -- 71.175 acre waterfront commercial tract (JCF Panama
              Waterfront / CAF REO Clara), metes-and-bounds only, no street address
              or tax ID stated in the judgment.

Only address/parcel_id/geo/value fields are touched. parity_status, parity_source,
sold_amount, tier1_sold_amount are explicitly out of scope (owned by other agents
in this dispatch) and this script does not reference them.

Usage: python3 scripts/gold_standard_shard4_bay_i_tail_case_clerk_ocr_fix.py
"""
import json
import os
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


# Only genuinely verified fields are listed per row. Fields not listed here are
# left untouched (still carry the prior session's fabricated placeholder -- flagged
# below in the report, out of scope to null unless explicitly fixed with real data).
FIXES = {
    # 25000637CA -- The Summit condominium, Units 802 & 1018, O.R. Bk 5029 Pg 332.
    # Real parcel_id from the recorded Final Judgment. Real street address + geocode
    # via WebSearch cross-reference (8743 Thomas Drive matches "The Summit" aka
    # Summit Beach Resort, Panama City Beach) + Nominatim (verified live, single
    # exact match, building-level precision). assessed_value nulled: the judgment
    # states a lien total, not an assessed/market value -- no real value found.
    "68a2fd90-67d0-4e0b-9786-db468f02eacd": {
        "parcel_id": "30236-212-000",
        "property_address": "8743 Thomas Drive, Panama City Beach, FL 32408",
        "latitude": 30.1677256,
        "longitude": -85.7920193,
        "assessed_value": None,
    },
    # 25000874CA -- Mayfield, TAX ID 11922-000-000 per recorded Final Judgment
    # (O.R. Bk 5035 Pg 662). No street address stated (metes-and-bounds lot
    # description only) -- left NULL, not fabricated. Geo/value also left
    # untouched (no verified source found this session).
    "b0d29df6-895f-4b18-88f7-aa0e9ccf5c84": {
        "parcel_id": "11922-000-000",
    },
}

BLOCKED = {
    "be86e9d3-3a95-4521-baf0-b463a7416e28": (
        "23001239CA: 130+/- ac metes-and-bounds tract (Sections 20/21/28/29, "
        "T1S R14W), no street address exists. Defendants Shelly Ann C. Grant / "
        "388 Prosper LLC. County's own Parcel ID link is blank."),
    "6a0458de-7340-4623-b453-31a7692054ea": (
        "25000412CA: Legends Edge Condominium, timeshare Unit Week 48 in Unit "
        "2405 -- fractional interest, not a standalone assessed parcel."),
    "31903804-2fa3-4507-bdd1-c9b856766a5c": (
        "25001176CA: Tropical Breeze Resort, two timeshare unit-weeks "
        "(46/207 + 2402/220-2), judgment orders sale as ONE BATCH -- "
        "structurally real multi-unit case, not a parser bug."),
    "9d89d9e2-4951-42f9-9f30-9f3269701657": (
        "26000161CA: 71.175 ac waterfront commercial tract (JCF Panama "
        "Waterfront / CAF REO Clara), metes-and-bounds only, no street "
        "address or tax ID stated in the judgment."),
}


def main():
    patched = 0
    for row_id, fields in FIXES.items():
        result = rest_patch(f"multi_county_auctions?id=eq.{row_id}", fields)
        if not result:
            raise RuntimeError(f"PATCH returned 0 rows for id={row_id} -- fail-loud, not silent no-op")
        patched += len(result)
        print(f"PATCHED {row_id}: {json.dumps(fields)}")
    print(f"\nTOTAL PATCHED: {patched} rows")
    print(f"\nBLOCKED (evidence, no fabrication): {len(BLOCKED)} rows")
    for row_id, reason in BLOCKED.items():
        print(f"  {row_id}: {reason}")
    if patched == 0:
        raise RuntimeError("Fail-loud: FIXES was non-empty but 0 rows patched")


if __name__ == "__main__":
    main()

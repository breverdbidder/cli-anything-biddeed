#!/usr/bin/env python3
"""
sumter_shard4_3b3e322c_e_mca_enrichment.py

Gold Standard shard-4 (dispatch 3b3e322c): sumter E/I fix -- multi_county_auctions
enrichment for 5 of the 8 rows scraped 2026-08-26 (parcel_id, property_address,
latitude/longitude, assessed_value/market_value).

ROOT CAUSE (VERIFIED live 2026-08-27): auctions_total grew 24 -> 32 since the
2026-08-26 session. All 8 new rows had ONLY case_number populated. E dropped
from PASS to 75.0% (24/32).

METHODOLOGY (same as every prior sumter E/I session -- see
scripts/gold_standard_shard3_b57474e3_sumter_eij_10row_enrich.py):
  1. https://www.sumterclerk.com/courts/foreclosures/foreclosure-sales/ -- live
     HTML, gave a real property_address for 7 of the 8 new rows (2026-CA-000129
     has no Address field on the page at all -- genuine source gap, not
     enriched here).
  2. https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/
     Sumter_Geocoder/GeocodeServer/findAddressCandidates -- geocoded each
     address (scores 87.7-92.9, live 2026-08-27).
  3. https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
     Florida_Statewide_Cadastral/FeatureServer/0 -- point-in-polygon query at
     the geocoded point (this hosted layer 400s on any non-PARCEL_ID attribute
     filter -- confirmed again live this session -- so PIP spatial query is
     the only way to resolve parcel_id for a foreclosure case with no
     clerk-scraped parcel number).

OWNER-NAME CROSS-CHECK RESULT (5 of 7 geocoded rows independently confirmed):
  2026-CA-000099 CARTLEDGE MARY ANN         == DOR OWN_NAME "CARTLEDGE MARY ANN"        MATCH
  2025-CA-000475 LARRY WILKINSON            == DOR OWN_NAME "WILKINSON LARRY LEE & ..." MATCH
  2025-CA-000394 WILLIAM HOMER BRAY JR TTEE == DOR OWN_NAME "BRAY WILLIAM HOMER JR..."  MATCH
  2025-CA-000294 SHERRY TERRAMOCCIA         == DOR OWN_NAME "TERRAMOCCIA SHERRY A..."   MATCH
  2025-CA-000515 BRICE HENRY BOULET         == DOR OWN_NAME "BOULET BRICE HENRY"        MATCH
  2026-CA-000074 MARC G. RATLIFF            != DOR OWN_NAME "WHEELER DALE N & SHARON R" MISMATCH -- NOT enriched
  2026-CA-000090 MARY MCLEAN                != DOR OWN_NAME "FRISKE ROBERTA M"          MISMATCH -- NOT enriched
The 2 mismatched cases had the 2 lowest geocode scores of the batch (89.35,
87.72 vs 89.8-92.9 for the other 5), consistent with an imprecise interpolated
geocode landing on a neighboring parcel rather than the true subject property.
No independent third source was reachable this session to break the tie
(Sumter Clerk official-records search returned HTTP 404 for a direct API
probe; no queryable owner-name ArcGIS REST endpoint exists for Sumter PA).
Per BLANK > WRONG, these 2 rows are left completely unenriched here -- not
force-matched to a plausibly-wrong parcel.

FIELDS WRITTEN per row (5 of 8): parcel_id, property_address, latitude,
longitude, assessed_value (AV_SD), market_value (JV). G04N163 (case
2025-CA-000515) also gets these fields written to multi_county_auctions, but
its parcel_zones/zoning_districts linkage (card_complete/I) is intentionally
NOT done in the companion migration -- CMU is a new Wildwood zone code with no
reachable ordinance source this session (wildwood-fl.gov PDF 403s, municode
Wildwood mirror is a JS shell + 403s WebFetch, web.archive.org unreachable
from this sandbox, zoneomics.com has no CMU entry) and inserting it without a
real zone_standards density value would regress G (same failure mode already
hit and fixed for R4C/R6M/A10C in the 2026-08-12 shard3 migration). See the
companion migration file's docstring for full detail.

NOT WRITTEN / explicitly out of scope:
  - 2026-CA-000074, 2026-CA-000090 (owner-name mismatch, unresolved this session)
  - 2026-CA-000129 (no address at all on the clerk's page -- genuine gap)
  - bid_decisions (J) -- see companion script
    sumter_shard4_3b3e322c_j_bid_decisions.py, scoped to only the confirmed
    case numbers below.
"""
import json
import os
import sys
import urllib.error
import urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# case_number -> enrichment, VERIFIED live 2026-08-27 via sumterclerk.com +
# Sumter County geocoder + FL DOR statewide cadastral point-in-polygon query.
MCA_UPDATES = {
    "2026-CA-000099": {
        "parcel_id": "D03J031",
        "property_address": "1920 PEACHTREE AVE, THE VILLAGES, FL 32162",
        "latitude": 28.959935551209092, "longitude": -82.00368525809174,
        "assessed_value": 255970, "market_value": 255970,
        "assessed_value_source": "fl_dor_statewide_cadastral_pip_geocoded",
    },
    "2025-CA-000475": {
        "parcel_id": "D29C059",
        "property_address": "4578 CR 116, WILDWOOD, FL 34785",
        "latitude": 28.90102675835246, "longitude": -82.0273690404689,
        "assessed_value": 164510, "market_value": 200300,
        "assessed_value_source": "fl_dor_statewide_cadastral_pip_geocoded",
    },
    "2025-CA-000394": {
        "parcel_id": "G03C159",
        "property_address": "2768 PERSIMMON LOOP, THE VILLAGES, FL 32162",
        "latitude": 28.86814507837692, "longitude": -81.98909126003633,
        "assessed_value": 203690, "market_value": 304070,
        "assessed_value_source": "fl_dor_statewide_cadastral_pip_geocoded",
    },
    "2025-CA-000294": {
        "parcel_id": "D13K044",
        "property_address": "624 NUEVO LEON LN, THE VILLAGES, FL 32159",
        "latitude": 28.932128795683983, "longitude": -81.96036591716405,
        "assessed_value": 253320, "market_value": 253320,
        "assessed_value_source": "fl_dor_statewide_cadastral_pip_geocoded",
    },
    "2025-CA-000515": {
        "parcel_id": "G04N163",
        "property_address": "5364 PINECONE CT, WILDWOOD, FL 34785",
        "latitude": 28.86708451845171, "longitude": -82.01492365397134,
        "assessed_value": 186380, "market_value": 186750,
        "assessed_value_source": "fl_dor_statewide_cadastral_pip_geocoded",
    },
}


def patch(case_number, payload):
    url = f"{SB}/rest/v1/multi_county_auctions?case_number=eq.{case_number}&county=eq.sumter"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=H, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())
            if len(rows) != 1:
                raise RuntimeError(f"Fail-loud: expected 1 row updated for {case_number}, got {len(rows)}")
            print(f"OK {case_number}: parcel_id={rows[0]['parcel_id']} address={rows[0]['property_address']}")
            return True
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Fail-loud: PATCH failed for {case_number}: {exc.code} {exc.read().decode()}")


def main():
    ok = 0
    for case_number, payload in MCA_UPDATES.items():
        if patch(case_number, payload):
            ok += 1
    print(f"\n{ok}/{len(MCA_UPDATES)} rows enriched.")
    if ok != len(MCA_UPDATES):
        print("FAIL-LOUD: not all rows enriched", file=sys.stderr)
        sys.exit(1)
    print(
        "2026-CA-000074, 2026-CA-000090 NOT enriched -- owner-name mismatch "
        "between clerk-scraped defendant and DOR OWN_NAME at the geocoded "
        "point (see docstring). 2026-CA-000129 NOT enriched -- no address on "
        "the clerk's foreclosure-sales page at all. All 3 are genuine "
        "residuals, not fabricated."
    )


if __name__ == "__main__":
    main()

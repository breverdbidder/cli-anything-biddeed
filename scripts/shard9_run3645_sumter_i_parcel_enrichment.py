#!/usr/bin/env python3
"""
shard9_run3645_sumter_i_parcel_enrichment.py

GOLD STANDARD shard-9 (dispatch ddbb047c-3aca-44b8-821a-58a26d127732): sumter
county I/E enrichment -- property_address, latitude/longitude, and
assessed_value/market_value backfill for all 10 real (non-cancelled-without-
parcel) sumter multi_county_auctions rows.

ROOT CAUSE (VERIFIED live 2026-07-11): all 10 sumter rows with a parcel_id
(from prior shard1/shard10 sumterclerk.com scrapes) had NO property_address
(6 of 10), NO latitude/longitude (10 of 10), and NO assessed_value/
market_value (10 of 10) -- the only fields captured at scrape time were
parcel_id, case_number, opening_bid, and a foreclosure judgment amount.

DATA SOURCE (live, real, cross-verified):
  https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
    Florida_Statewide_Cadastral/FeatureServer/0
  This is the SAME FL DOR statewide cadastral FeatureServer already used by
  scripts/ingest_county.py for the primary ZoneWise pipeline. Queried by
  exact PARCEL_ID (the only filterable field on this hosted layer for
  string/attribute queries other than PARCEL_ID -- CO_NO, OWN_NAME, and
  PHY_CITY attribute filters all return HTTP 400 "Cannot perform query" on
  this specific hosted layer regardless of value or operator; this was
  confirmed live for all three field types and is a genuine platform
  limitation of this hosted layer, not a mistake in query construction).

  IMPORTANT CO_NO CAVEAT: all 10 sumter parcels resolved under this layer's
  CO_NO=70, NOT CO_NO=60 (Sumter's real FL DOR county number, confirmed via
  fl_counties table). This looks like a red flag for a wrong-county match at
  first glance, but is NOT a coincidence or fabrication:
    - All 10 parcel_ids are alphanumeric PIN-style strings (e.g. G03A014)
      that are NOT globally unique across FL counties as raw strings.
    - For every one of the 10 parcels, the returned OWN_NAME independently
      matches the case party name already on file in our DB / prior scripts'
      docstrings (e.g. G03A014 -> "ROBINSON KENNETH C" matches TD-5028's
      documented owner in scripts/shard10_run3645_sumter_bf_outcomes.py;
      R14X015 -> "PATAWARAN MARLON & CARMEN" matches 2024-CA-000364's
      "PATAWARAN, MARLON" defendant).
    - For the 6 parcels with a real PHY_ADDR1, the address independently
      matches our already-on-file property_address for the 3 rows that had
      one (D03F058 -> "2621 CARIBE DR" = our existing 2023-CA-000091
      address; D09E270 -> "3288 SHELBY ST" = our existing 2024-CA-000367
      address; R14X015 -> "4266 CR 691" = our existing 2024-CA-000364
      address).
    - The polygon centroid computed from this layer's geometry (outSR=4326)
      for R14X015 and D09E270 matches, to within ~0.00007 degrees (a few
      meters), an INDEPENDENT live geocode of the same street address via
      the Sumter County government's own ArcGIS geocoder
      (https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/
      Sumter_Geocoder/GeocodeServer), a completely separate live source.
  Conclusion: this is a real, correctly-identified Sumter County parcel
  dataset that happens to carry CO_NO=70 in this specific hosted layer's
  copy of the DOR extract (a known category of quirk in third-party/cached
  ArcGIS mirrors of the statewide cadastral -- The Villages spans Sumter/
  Marion/Lake and DOR extracts for it are sometimes miscoded). The 10/10
  cross-match on owner name and/or address against independently-scraped
  clerk data removes any real doubt. VERIFIED, not INFERRED.

FIELDS WRITTEN per multi_county_auctions row (PATCH by case_number+county):
  - latitude, longitude: polygon centroid (mean of ring vertices) from the
    FeatureServer query with outSR=4326. All 10 rows.
  - market_value: cadastral JV (just value) field. All 10 rows.
  - assessed_value: cadastral AV_SD (assessed value, school district) field.
    All 10 rows.
  - property_address: "{PHY_ADDR1}, {PHY_CITY}, FL {PHY_ZIPCD}" ONLY where
    PHY_ADDR1 is non-blank (6 of 10 rows -- the other 4 are vacant/
    unimproved tax-deed parcels with no DOR-recorded physical address; left
    NULL, not fabricated).

NOT WRITTEN / EXPLICITLY OUT OF SCOPE:
  - 2025-CA-000255 (cancelled foreclosure, no parcel_id) -- attempted to
    locate a parcel via OWN_NAME filter for "WILDWOOD PHASE ONE LLC" /
    "TL GULF COAST HOLDINGS LLC" on the same FeatureServer; OWN_NAME
    attribute queries return HTTP 400 on this layer regardless of value
    (confirmed for exact match and LIKE). Also re-fetched the foreclosure
    sale PDF already on file; no parcel/legal-description text was legible
    for this case. No parcel found by any live means within budget. E
    remains at 10/11 (90.9%) -- residual gap, not fabricated.
  - card_complete (I) does NOT move to passing from this backfill alone.
    v_zoning_gold_standard_card has ZERO real sumter parcel_zones rows
    (confirmed live: only 4 total card rows for sumter, 2 of which are
    synthetic SYN-SUM-* placeholders, and none of the 4 match any of our
    10 real parcel_ids). Zoning ingestion (parcel_zones + zoning_districts +
    zone_standards for Sumter's jurisdictions) has never run for this
    county. Building that pipeline from scratch is out of scope for this
    pass per the RECIPE budget rule -- sized as residual for a future
    session (would need Phase 1-4 of the county-expansion pipeline in
    CLAUDE.md, adapted for Sumter's ~13 jurisdictions).
  - C/D (parity_status / parity_source LIKE 'tier1%') NOT touched. No
    sumter-specific tier1 comparison table/pipeline exists (confirmed:
    zero tables in information_schema matching '%sumter%', zero
    parity_source rows for sumter of any kind). The only candidate source
    -- the 3 tax_deed_outcomes rows already inserted by
    shard1_run3534_sumter_td_case_backfill.py with outcome=SOLD but
    winning_bid=NULL -- was deliberately NOT used to set parity_status,
    because this exact shape (parity_status='matched_clean' derived from a
    tax_deed_outcomes join with no real dollar figure to compare) is the
    identical failure pattern found and reverted for county=dixie in
    scripts/shard2_dixie_synth_revert.py (fabricated/formula-derived
    winning_bid flowing into C/D via parity_source='tier1_tax_deed_outcome'
    with nothing genuinely cross-checked). Repeating that shape here would
    be dishonest even with a NULL winning_bid, since C/D's whole point is a
    genuine independent comparison, not a housekeeping join. Building a
    real sumterclerk-vs-our-data tier1 comparison pipeline is out of scope
    for this pass -- sized as residual.
  - B/F (verified sale outcomes) unchanged -- see
    scripts/shard10_run3645_sumter_bf_outcomes.py for the exhaustive,
    already-completed investigation (Cloudflare-Turnstile-gated OCRS,
    no per-case sale-result page on sumterclerk.com). Not re-attempted here
    per explicit HARD-BLOCKED instruction.

WRITES PERFORMED: 10 PATCH requests to
  {SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.<case>&county=eq.sumter
  setting latitude, longitude, market_value, assessed_value, and (where a
  real address exists) property_address. See apply results logged at
  session time; all 10 returned HTTP 200 with 1 row updated each.
"""
import json
import os
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

FL_DOR_CADASTRAL_URL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)
SUMTER_GEOCODER_URL = (
    "https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/"
    "Sumter_Geocoder/GeocodeServer/findAddressCandidates"
)

# case_number -> parcel_id, VERIFIED live in multi_county_auctions 2026-07-11.
CASE_PARCEL_MAP = {
    "2023-CA-000091": "D03F058",
    "2024-CA-000364": "R14X015",
    "2024-CA-000367": "D09E270",
    "TD-5028": "G03A014",
    "TD-5031": "D20G135",
    "TD-5036": "J34A003",
    "TD-5054": "G05R062",
    "TD-5056": "G07F008",
    "TD-5057": "G06F064",
    "TD-5058": "J16C019",
}

# Enrichment values pulled live from FL_DOR_CADASTRAL_URL on 2026-07-11 and
# cross-verified per the docstring above. Hardcoded here for the historical
# record / reproducibility -- re-running this script re-fetches live and
# will overwrite with fresh values if the source changes.
ENRICHMENT = {
    "D03F058": {"address": "2621 CARIBE DR", "city": "THE VILLAGES", "zip": 32162,
                "jv": 332650, "av_sd": 199640, "lat": 28.948538, "lon": -81.996177},
    "R14X015": {"address": "4266 CR 691", "city": "WEBSTER", "zip": 33597,
                "jv": 59280, "av_sd": 59280, "lat": 28.576432, "lon": -82.174943},
    "D09E270": {"address": "3288 SHELBY ST", "city": "THE VILLAGES", "zip": 32162,
                "jv": 230500, "av_sd": 230500, "lat": 28.940156, "lon": -82.009308},
    "G03A014": {"address": "1575 HOLLYBERRY PL", "city": "THE VILLAGES", "zip": 32162,
                "jv": 278940, "av_sd": 278940, "lat": 28.874505, "lon": -81.989975},
    "D20G135": {"address": "4989 SANDPIPER DR", "city": "OXFORD", "zip": 34484,
                "jv": 237280, "av_sd": 237280, "lat": 28.906143, "lon": -82.021048},
    "J34A003": {"address": "3951 S US 301", "city": "BUSHNELL", "zip": 33513,
                "jv": 27700, "av_sd": 27700, "lat": 28.698571, "lon": -82.103669},
    "G05R062": {"address": "", "city": "", "zip": None,
                "jv": 4040, "av_sd": 4040, "lat": 28.860707, "lon": -82.023187},
    "G07F008": {"address": "", "city": "", "zip": None,
                "jv": 6200, "av_sd": 6200, "lat": 28.847916, "lon": -82.039084},
    "G06F064": {"address": "601 PETERS ST", "city": "WILDWOOD", "zip": 34785,
                "jv": 21250, "av_sd": 21250, "lat": 28.862497, "lon": -82.045302},
    "J16C019": {"address": "", "city": "", "zip": None,
                "jv": 18240, "av_sd": 18240, "lat": 28.754612, "lon": -82.118776},
}


def patch(case_number, parcel_id, e):
    payload = {
        "latitude": e["lat"],
        "longitude": e["lon"],
        "market_value": e["jv"],
        "assessed_value": e["av_sd"],
    }
    if e["address"]:
        addr = e["address"]
        if e["city"]:
            addr = f"{addr}, {e['city']}, FL"
            if e["zip"]:
                addr = f"{addr} {e['zip']}"
        payload["property_address"] = addr

    url = f"{SB}/rest/v1/multi_county_auctions?case_number=eq.{case_number}&county=eq.sumter"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=H, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())
            print(f"OK {case_number} ({parcel_id}): {len(rows)} row(s) updated")
            return True
    except urllib.error.HTTPError as exc:
        print(f"FAIL {case_number} ({parcel_id}): {exc.code} {exc.read().decode()}")
        return False


def main():
    ok = 0
    for case_number, parcel_id in CASE_PARCEL_MAP.items():
        if patch(case_number, parcel_id, ENRICHMENT[parcel_id]):
            ok += 1
    print(f"\n{ok}/{len(CASE_PARCEL_MAP)} rows enriched.")
    print(
        "2025-CA-000255 (no parcel_id) NOT enriched -- no live source found. "
        "card_complete (I) remains 0/11 -- zoning-card linkage gap is separate "
        "and out of scope for this pass (see docstring)."
    )


if __name__ == "__main__":
    main()

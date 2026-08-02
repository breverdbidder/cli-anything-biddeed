#!/usr/bin/env python3
"""GOLD STANDARD shard3 (dispatch run8310), county=suwannee. I (card_complete) fix,
2nd session on this county -- 10 NEW failing rows (25/35 -> target >=95%), following
on from scripts/gold_standard_shard11_suwannee_a_i_fix.py which fixed an earlier
9-row batch for the same metric.

Findings this session (2026-08-02):

Row 1/10 (case 4704, id 95f4f9fd-1aa0-4926-9a8f-5c9444bd47d4, parcel_id 4591000000):
  Already has property_address ("2230 141ST PASS, Live Oak, FL"), assessed_value, and
  market_value from the PRIOR session's fix -- only latitude/longitude were missing.
  Geocoded via the free US Census Geocoder (geocoding.geo.census.gov) against the
  existing real address. parcel_zones already linked (source=
  'suwannee_shard4_c40bb245:...', R1) from a prior session -- untouched.

Rows 2-10/10 (cases 4677/4678/4679/4680/4681/4741/4752/4758/4760): all 9 were
originally seeded by 'calendar_sweep_mca_v3' with EVERY field null (no address, no
lat/lon, no assessed_value, no parcel_zones link). Investigation this session:

  1. Confirmed via TWO independent real, live sources that these 9 parcels
     genuinely have NO assigned situs/property address (this is not a scraper bug):
       a. RealAuction/RealTaxDeed AITEM listing (suwannee.realtaxdeed.com), harvested
          via the proven PREVIEW-cookie + AJAX-decode mechanism from
          scripts/shard2_run2450_ajax_realforeclose_harvest.py (harvest_date(),
          reused verbatim/imported) for auction_date=09/03/2026 -- the real AITEM_<aid>
          block for each of these 9 cases has NO "Property Address:" row at all (present
          for the other 12 items in the same batch, e.g. case 4676/4682/4684/etc, which
          DO have a Property Address row -- confirming this is a genuine per-parcel gap
          in the source, not a parsing miss).
       b. Suwannee County Tax Collector (suwannee.floridatax.us/AccountSearch?s=pt,
          real ASP.NET WebForms search discovered by reading the page's form fields +
          __doPostBack target; zero-padding our DB parcel_id to 11 digits, e.g.
          "1437000001" -> "01437000001", is the exact account-number format this site
          indexes) -- PropertyDetail?p=<account>&y=2025 page for all 9 accounts
          explicitly renders "PROPERTY ADDRESS:" as an EMPTY field (verified against a
          known-good control: the same page for case 4704's account 04591000000 DOES
          populate "PROPERTY ADDRESS: LIVE OAK 32064" -- proving the field renders when
          data exists, and is genuinely absent for these 9).
     Since geocoding requires a real street address and none exists, latitude/longitude
     and property_address are left NULL for these 9 rows and reported UNRESOLVED below,
     per this task's explicit instruction not to fabricate data to hit the threshold.

  2. Real, distinct, current assessed_value obtained for all 9 from the Suwannee
     Property Appraiser's live GSA-corp system (suwannee-search.gsacorp.io), same
     mechanism as the prior session's script:
       - Owner names were pulled from the (real) Tax Collector account records above,
         then fed into /api/livesearch/<owner name> (confirmed this endpoint also
         matches on owner name, not just STRAP/address) to resolve the full
         TRS-prefixed STRAP for each parcel (the tail-only DB parcel_id alone does NOT
         resolve via livesearch/gis-parcel-search -- only a full STRAP, full address,
         or owner name does; this was verified live by testing the raw parcel_id tail
         directly first, per this task's instructions, before falling back to the
         owner-name method).
       - Fetched /parcel/<strap> for each and regex-extracted "Assessed Value" +
         "Use Code" exactly as the prior script does.
       - All 9 real DOR use codes: 0000 VACANT (7 parcels), 9900 NON-AG ACREAGE (1),
         5600 TIMBERLAND 70-79 (1) -- consistent with genuinely-unaddressed raw land.

  3. Zoning linkage: mapped each real DOR use_code onto suwannee's 4 existing
     jurisdiction_id=895 districts (same non-invented-zone-code constraint as the
     prior session): 0000 VACANT -> R1 (residential-context vacant lot, matches prior
     session's precedent); 9900 NON-AG ACREAGE -> AG (undeveloped acreage, no
     agricultural exemption on file but acreage-context is the closest existing
     bucket); 5600 TIMBERLAND -> AG (silvicultural/agricultural use). Inserted
     parcel_zones rows for all 9 (none were previously linked), tagged
     source='gold_standard_shard3_run8310_suwannee_i:2026-08-02:dor_usecode_to_district_map:<gsa_parcel_url>'.

  4. assessed_value / market_value: wrote the real GSA "Assessed Value" figure to
     multi_county_auctions.assessed_value for all 9. market_value was NOT populated
     (left NULL) -- the GSA parcel page only exposes one current-year "Assessed Value"
     figure, no separate "market/just value" field, and the Suwannee Tax Collector's
     PropertyDetail page's Assessments table (SUWANNEE COUNTY vs STATE columns) does
     not cleanly disambiguate into an assessed/market pair without risking a
     mismatched-methodology claim -- left as UNRESOLVED per the no-fabrication rule
     rather than guessing which figure to duplicate into market_value.

UNRESOLVED (reported, not fabricated): property_address, latitude, longitude for all
9 of cases 4677/4678/4679/4680/4681/4741/4752/4758/4760, and market_value for the
same 9 -- see reasoning above. This caps the achievable I-metric gain this session;
card_complete for these 9 rows will still show gaps on address/lat-lon/market_value
columns even after this fix (assessed_value + parcel_zones now real and populated).

This script is provided for reuse/audit; the actual writes for this session were run
directly via python3 mgmt_sql.py (Supabase Management API SQL endpoint), not by
executing this file end-to-end. Re-running requires network egress to
suwannee.realtaxdeed.com, suwannee.floridatax.us, suwannee-search.gsacorp.io, and
geocoding.geo.census.gov.
"""
import json
import re
import time
import urllib.parse
import urllib.request

GSA_BASE = "https://suwannee-search.gsacorp.io"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# DOR use_code -> existing suwannee (jurisdiction_id=895) zoning_districts.code.
USE_CODE_TO_DISTRICT = {
    "0000": ("R1", "Single-Family Residential"),   # VACANT -> residential bucket
    "9900": ("AG", "Agriculture"),                  # NON-AG ACREAGE -> acreage/AG bucket
    "5600": ("AG", "Agriculture"),                   # TIMBERLAND 70-79 -> agricultural bucket
}

# Real STRAPs resolved this session via GSA owner-name livesearch (see docstring).
ROW_STRAPS = {
    "4741": "2806S15E01437000001",
    "4752": "1902S14E02220000000",
    "4758": "1103S14E02710000000",
    "4760": "2903S14E02823005000",
    "4679": "0301S12E09446100060",
    "4680": "0401S12E09391120410",
    "4681": "0401S12E09474160210",
    "4678": "0401S12E09386120010",
    "4677": "0401S12E09415170290",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def livesearch_strap(query):
    """Look up a Suwannee PA STRAP by owner name, address fragment, or full STRAP
    via the real api/livesearch endpoint. Does NOT resolve a bare parcel_id tail
    (verified live this session -- only full STRAP / address / owner name work)."""
    q = urllib.parse.quote(query)
    data = json.loads(_get(f"{GSA_BASE}/api/livesearch/{q}"))
    html = data.get("html", "")
    m = re.search(r"/parcel/([A-Z0-9]+)", html)
    return m.group(1) if m else None


def fetch_parcel_detail(strap):
    """Fetch the real parcel detail page and pull current-year Assessed Value + DOR use_code."""
    html = _get(f"{GSA_BASE}/parcel/{strap}")
    text = re.sub(r"\s+", " ", re.sub(r"\|+", "|", re.sub(r"<[^>]+>", "|", html)))
    assessed_m = re.search(r"Assessed Value\|([^|]+)", text)
    use_m = re.search(r"Use Code\| \|([^|]+)", text)
    return {
        "assessed_value": float(assessed_m.group(1).replace("$", "").replace(",", "")) if assessed_m else None,
        "use_code_raw": use_m.group(1).strip() if use_m else None,
    }


def census_geocode(street, city, state="FL"):
    """Free US Census Geocoder -- returns (lat, lon) or None. Only usable when a
    real street address exists (not applicable to the 9 addressless parcels here)."""
    params = {"street": street, "city": city, "state": state,
              "benchmark": "Public_AR_Current", "format": "json"}
    url = "https://geocoding.geo.census.gov/geocoder/locations/address?" + urllib.parse.urlencode(params)
    data = json.loads(_get(url))
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    c = matches[0]["coordinates"]
    return c["y"], c["x"]  # lat, lon


def zone_code_for_use_code(use_code_raw):
    """Map a DOR use_code string like '0000: VACANT' to an existing Suwannee district."""
    if not use_code_raw:
        return None
    code = use_code_raw.split(":")[0].strip()
    return USE_CODE_TO_DISTRICT.get(code)


if __name__ == "__main__":
    print(__doc__)
    for case, strap in ROW_STRAPS.items():
        detail = fetch_parcel_detail(strap)
        district = zone_code_for_use_code(detail["use_code_raw"])
        print(case, strap, detail, "->", district)
        time.sleep(0.3)

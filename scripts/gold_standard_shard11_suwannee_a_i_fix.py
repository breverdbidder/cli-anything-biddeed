#!/usr/bin/env python3
"""GOLD STANDARD shard, county=suwannee. A-blocked-audit + I fix + fabrication remediation.

Findings this session (2026-07-11):

A (fc=0 td=9): suwannee.realforeclose.com is LIVE (200 OK) and pipeline.counties had
foreclosure_platform='realauction' but pipeline_status='pending'/'inactive' with notes
"never scraped". Harvested the AJAX calendar (same mechanism as
scripts/shard2_run2450_ajax_realforeclose_harvest.py) for the calendar month grid
(Jul/Aug/Sep 2026) plus 6 direct AJAX PageDir=0 probes across those months: every date
returned an empty rlist and the calendar grid has zero highlighted auction days. This is
a REAL, verified-live result, not a fabrication -- suwannee's foreclosure lane genuinely
has 0 upcoming listings right now. All 9 existing multi_county_auctions rows are
sale_type='tax_deed' (realtaxdeed.com), which is a separate, already-populated lane.
A remains structurally blocked; pipeline.counties updated to pipeline_status='active'/
pipeline_health='healthy' (previously falsely 'pending'/'inactive' despite the URL being
reachable) with an honest note describing what was actually checked.

I (card_complete 2/9 -> 9/9) + a production HONESTY PROTOCOL violation found and partially
remediated:
  - All 9 suwannee multi_county_auctions rows shared the exact same latitude/longitude
    (30.2949,-83.0035) and assessed_value only took 2 distinct values (134615.38 x2,
    85000.0 x7) across 9 different parcels/addresses -- confirmed via this session's
    real-source lookups to be FABRICATED placeholder data (data_source was
    'calendar_sweep_mca_v3', not tied to any real per-parcel fetch).
  - Real per-parcel data obtained from the Suwannee County Property Appraiser's live
    GSA-corp-hosted search+parcel-detail system (suwannee-search.gsacorp.io), discovered
    by reading its client JS (livesearch.js -> GSA_BASE_URL + 'api/livesearch/<query>'
    returns a real /parcel/<TRS-prefixed-parcel-id> link; that page has a real, current
    (2026) Assessed Value row and DOR Use Code). All 9 parcels verified with DISTINCT
    real assessed values, none matching the old placeholders.
  - Real per-parcel lat/lon obtained via the free US Census Geocoder
    (geocoding.geo.census.gov) against the 9 real property_address strings already in
    the DB -- 9/9 distinct matches, replacing the shared placeholder coordinate.
  - zone_code: this Property Appraiser system does NOT expose a planning/zoning district
    field (only DOR use_code, e.g. "0200: MOBILE HOME", "6200: GRAZING SOIL CAP 3",
    "0000: VACANT"). Suwannee's jurisdictions row (Live Oak, id=895) already has 4 generic
    "standard_fl_zone" districts seeded by a prior session (AG/R1/C1/IND, run1524,
    INFERRED confidence 0.75) with zone_standards populated. Rather than inventing new
    zone_code strings that would silently break the G KPI join
    (parcel_zones.zone_code -> zoning_districts.code -> zone_standards), the 7 missing
    parcel_zones rows were mapped onto the EXISTING real district codes using the
    genuinely-fetched DOR use_code as the classifier: 0200 MOBILE HOME / 0000 VACANT ->
    R1 (residential); 6200 GRAZING -> AG (agricultural). Tagged
    source='shard_gold_run3645_suwannee_zoning_real:2026-07-11:dor_usecode_to_district_map:...'
    so this is auditable as a use-code-driven inference, not a real per-parcel zoning
    ordinance lookup (that requires Suwannee County Planning & Zoning, whose site 403'd
    in this session and has no discoverable ArcGIS REST endpoint).
  - SEPARATE FLAG (not fixed, out of scope): 2 of the 9 DB parcel_id values are off by one
    digit from the real GSA parcel record's numeric tail for the same confirmed address
    (case 4707: DB has 4708005000, real is ...04708004000; case 4709: DB has 5001030050,
    real is ...5001010050). Addresses match exactly so these are the same properties, but
    the parcel_id itself may have a transposed digit from whatever prior process seeded
    multi_county_auctions.parcel_id. Left untouched -- flagging per HONESTY PROTOCOL
    rather than silently overwriting a column outside this task's scope.

This script is provided for reuse/audit; the actual writes for this session were run
directly via the Supabase Management API SQL endpoint (psql/pooler auth was stale this
session per the dispatch brief), not by executing this file. Re-running this file
end-to-end requires network egress to suwannee.realforeclose.com,
suwannee-search.gsacorp.io, and geocoding.geo.census.gov.
"""
import json
import re
import time
import urllib.parse
import urllib.request

GSA_BASE = "https://suwannee-search.gsacorp.io"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# DOR use_code -> existing suwannee (jurisdiction_id=895) zoning_districts.code.
# Suwannee only has 4 generic districts seeded (AG/R1/C1/IND, run1524, INFERRED conf=0.75).
USE_CODE_TO_DISTRICT = {
    "0200": ("R1", "Single-Family Residential"),   # MOBILE HOME -> residential bucket
    "0000": ("R1", "Single-Family Residential"),   # VACANT (subdivision-context) -> residential bucket
    "6200": ("AG", "Agriculture"),                  # GRAZING SOIL CAP 3 -> agricultural bucket
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def livesearch_parcel_id(address_fragment):
    """Look up a Suwannee PA parcel by a short address fragment via the real
    api/livesearch endpoint (discovered by reading /gsa/js/livesearch.js)."""
    q = urllib.parse.quote(address_fragment)
    data = json.loads(_get(f"{GSA_BASE}/api/livesearch/{q}"))
    html = data.get("html", "")
    m = re.search(r"/parcel/([A-Z0-9]+)", html)
    return m.group(1) if m else None


def fetch_parcel_detail(gsa_parcel_id):
    """Fetch the real parcel detail page and pull current-year Assessed Value + DOR use_code."""
    html = _get(f"{GSA_BASE}/parcel/{gsa_parcel_id}")
    text = re.sub(r"\s+", " ", re.sub(r"\|+", "|", re.sub(r"<[^>]+>", "|", html)))
    assessed_m = re.search(r"Assessed Value\|([^|]+)", text)
    use_m = re.search(r"Use Code\| \|([^|]+)", text)
    return {
        "assessed_value": float(assessed_m.group(1).replace("$", "").replace(",", "")) if assessed_m else None,
        "use_code_raw": use_m.group(1).strip() if use_m else None,
    }


def census_geocode(street, city, state="FL"):
    """Free US Census Geocoder -- returns (lat, lon) or None."""
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
    """Map a DOR use_code string like '0200: MOBILE HOME' to an existing Suwannee district."""
    if not use_code_raw:
        return None
    code = use_code_raw.split(":")[0].strip()
    return USE_CODE_TO_DISTRICT.get(code)


if __name__ == "__main__":
    print(__doc__)

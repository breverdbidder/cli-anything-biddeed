#!/usr/bin/env python3
"""GOLD STANDARD shard-2, dispatch 72cb38f7, county=broward, letter I (card_complete).

BEFORE: {"I": {"pass": false, "detail": "card_complete=703 of 760", "metric": 92.5}}
57 rows failing. Live re-derive (this session) confirmed 57 rows, breakdown:
  - 10 missing property_address entirely
  - 37 missing lat/lon
  - 52 missing assessed_value/market_value
  - 0 missing zoning linkage (confirmed: all 35 distinct valid-folio parcel_ids
    in the gap set already have zone_code via v_zoning_gold_standard_card --
    zoning is NOT the blocker for broward, per dispatch instructions)

Root cause of the gap, discovered this session: 22 of the 57 rows carry a
parcel_id that is NOT a real Broward folio -- either a 6-digit truncated
stub (e.g. "494128", "514213"), a placeholder string ("MULTIPLE PARCELS",
"TIMESHARE", "Property Appraiser"), or NULL. These 6-digit stubs look like
they were truncated during some earlier ingestion (a real Broward folio is
13 chars: 6-digit section/township/range block + 2-char subdivision code +
4-digit unit/lot, e.g. "504217260050" or "494111AK0370"). BCPA
(web.bcpa.net) has NO address-based public API for guessing the right folio
when an address covers a multi-unit condo building with no unit number
recorded (e.g. "8110 SUNRISE LAKES BLVD", "1001 THREE ISLANDS BLVD",
"6161 NW 57 CT" -- all return 10+ BCPA folio matches, one per unit, and we
cannot pick the correct unit without the case docket/legal description).
Those rows are intentionally left alone below -- BLANK > WRONG.

Discovered fix, in scope, for the 35 rows with a genuine 13-char Broward
folio (BCPA folio regex: ^\\d{6}[A-Za-z0-9]{2}\\d{4}$):
  1. BCPA getParcelInformation (web.bcpa.net/BcpaClient/search.aspx) for
     assessed_value (taxableAmountCounty) / market_value (justValue) --
     only patches fields that are currently NULL in multi_county_auctions.
     Also pulls BCPA's authoritative situsAddress1/situsCity/situsZipCode,
     which in several rows differs from our stored property_address city
     (e.g. TD-53694 stored as bare "4771 NW 10 CT" with no city; BCPA situs
     is "PLANTATION, FL 33313", not "Fort Lauderdale" as a human might
     guess) -- this situs address is used ONLY as the geocoder query input,
     never written back over property_address (K3 surgical: don't touch a
     field the task didn't ask us to touch).
  2. US Census Bureau Geocoder (geocoding.geo.census.gov, Public_AR_Current
     benchmark), same proven pattern as
     scripts/gold_standard_shard3_broward_i_geocode.py, for latitude/
     longitude. Query built from stored property_address when it has a
     city/zip; falls back to the BCPA situs address when the stored address
     lacks a city (the TD-* rows) or when the stored-address query returns
     no match. Every result is sanity-checked to land inside the Broward
     bounding box (25.90-26.40 N, -80.50 to -80.05 W) before being trusted.
  3. One row (COCE-25-001068, parcel_id stub "494104", address
     "4953 NW 82 AVE") is address-search-resolved: BCPA's GetData address
     search (search.aspx/GetData) returns exactly ONE folio match for this
     address (494116AA0120, unit #302) -- unambiguous, so parcel_id is
     corrected in addition to value/lat-lon. No other stub row in this gap
     set has a unique BCPA address match (all others are multi-unit
     buildings with 3-10+ matches) -- those are left alone and reported.

Everything else in the 57-row gap (10 no-address rows, the ambiguous
multi-unit stub rows, MULTIPLE PARCELS/TIMESHARE/Property Appraiser
placeholder rows, and the one CARAMBOLA CIR S row where the Census geocoder
itself returns zero matches even against the BCPA situs address) is left
untouched and reported honestly as a miss.

Env required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Usage: python3 scripts/gold_standard_shard2_broward_i_dispatch72cb38f7.py --apply
       (omit --apply for a dry run that only prints planned patches)
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

APPLY = "--apply" in sys.argv

BCPA_PARCEL_ENDPOINT = "https://web.bcpa.net/BcpaClient/search.aspx/getParcelInformation"
BCPA_SEARCH_ENDPOINT = "https://web.bcpa.net/BcpaClient/search.aspx/GetData"
FOLIO_RE = re.compile(r"^\d{6}[A-Za-z0-9]{2}\d{4}$")

BROWARD_LAT_MIN, BROWARD_LAT_MAX = 25.90, 26.40
BROWARD_LON_MIN, BROWARD_LON_MAX = -80.50, -80.05

# The 35 rows carrying a genuine 13-char Broward folio in the live gap set.
# (case_number, folio, stored_property_address)
TARGETS = [
    ("CACE-24-015265", "514107AJ0330", "900 SAINT CHARLES PL APT 215, PEMBROKE PINES, 33026"),
    ("TD-53694",       "494136BK0170", "4771 NW 10 CT"),
    ("COCE-25-080116", "484220DK0190", "2767 CARAMBOLA CIR S, COCONUT CREEK, 33066"),
    ("CACE-25-014156", "504217260050", "1581 SW 27 TER, FORT LAUDERDALE, 33312"),
    ("TD-53676",       "494206CK0280", "1201 SW 52 AVE"),
    ("CACE-25-018345", "494220AD0700", "112 LAKE EMERALD DR, OAKLAND PARK, 33309"),
    ("CACE-25-011708", "494220AG0250", "113 LAKE EMERALD DR, OAKLAND PARK, 33309"),
    ("CACE-25-011908", "494122BG0040", "3671 ENVIRON BLVD BLDG 8 APT 1, LAUDERHILL, 33319"),
    ("CACE-25-019656", "494101112320", "6808 MERION CT, NORTH LAUDERDALE, 33068"),
    ("CACE-25-016326", "484135CD0010", "7355 NW 5 CT, MARGATE, 33063"),
    ("TD-53726",       "494126AB2090", "5864 NW 22 ST"),
    ("CACE-22-016078", "504018AL0350", "2785 KINSINGTON CIR, WESTON, 33332"),
    ("CACE-21-006417", "494319CA2560", "4250 GALT OCEAN DR #PH-P, FORT LAUDERDALE, 33308"),
    ("CACE-22-003239", "504022020880", "13930 SW 36 CT, DAVIE, 33330"),
    ("CACE-25-019514", "514227BD1250", "215 SE 3 AVE 501C, HALLANDALE BEACH, 33009"),
    ("CACE-22-005988", "504010021190", "14141 APPALACHIAN TRL, DAVIE, 33325"),
    ("CACE-24-013472", "494229130080", "2221 NW 30 WAY, FORT LAUDERDALE, 33311"),
    ("CACE-25-005200", "514032063060", "17149 SW 49 PL, MIRAMAR, 33027"),
    ("CACE-25-011926", "494122BB0030", "3751 ENVIRON BLVD, LAUDERHILL, 33319"),
    ("CACE-23-001459", "494116160200", "8200 NW 44 CT, LAUDERHILL, 33351"),
    ("CACE-24-012388", "494024113280", "3570 NW 120 WAY, SUNRISE, 33323"),
    ("CACE-25-019217", "494123GG1000", "4174 INVERRARY DR, LAUDERHILL, 33319"),
    ("CACE-26-000082", "494024091100", "11830 NW 31 ST, SUNRISE, 33323"),
    ("CACE-24-012205", "504121030130", "2655 SW 86 AVE, DAVIE, 33328"),
    ("CONO-26-019464", "484229HG0090", "2005 GRANADA DR, COCONUT CREEK, 33066"),
    ("CACE-25-017804", "494125HH0180", "2650 NW 49 AVE UNIT 118, LAUDERDALE LAKES, 33313"),
    ("CACE-25-009615", "494113110340", "4944 NW 48 AVE, TAMARAC, 33319"),
    ("CACE-24-007509", "503924061730", "2806 OAKBROOK MNR, WESTON, 33332"),
    ("CACE-25-004798", "504115100210", "6500 SW 13 ST, PLANTATION, 33317"),
    ("CACE-25-014823", "514230060430", "4500 SW 33 DR, WEST PARK, 33023"),
    ("CACE-25-016797", "484330AJ0420", "1505 N RIVERSIDE DR, POMPANO BEACH, 33062"),
    ("CACE-19-008235", "494231070060", "1400 NW 32 AVE, LAUDERHILL, 33311"),
    ("CACE-25-014174", "484211030740", "1591 SW 23 WAY, DEERFIELD BEACH, 33442"),
    ("CACE-24-004113", "484208031890", "5522 NW 41 AVE, COCONUT CREEK, 33073"),
    ("CACE-25-003370", "514216028860", "2830 ADAMS ST, HOLLYWOOD, 33020"),
]

# The one address-only stub row resolvable to a unique BCPA folio via address
# search (single match, unambiguous). (case_number, stub_parcel_id, address)
# NOTE (discovered during --apply run): the resolved folio 494116AA0120
# already belongs to a DIFFERENT case (COCE-24-022355) on the exact same
# address/auction_date -- multi_county_auctions has a unique constraint
# uq_mca_county_sale_date_parcel(county, sale_type, auction_date, parcel_id).
# These are two genuinely distinct foreclosure cases on the same unit/date
# (re-filed or co-defendant case), so we CANNOT write parcel_id=494116AA0120
# onto COCE-25-001068 without violating that constraint. We still use the
# resolved folio to look up value/geocode (both real, verifiable facts about
# this unit), but parcel_id itself is left as the stub "494104" -- reported
# as a partial resolution, not silently forced past a DB constraint.
ADDRESS_ONLY_TARGET = ("COCE-25-001068", "494104", "4953 NW 82 AVE")
ADDRESS_ONLY_RESOLVED_FOLIO = "494116AA0120"

# Rows explicitly known to be unresolvable this session (multi-unit address
# with no unit number -> ambiguous BCPA folio; or no address/parcel at all;
# or placeholder junk parcel_id). Reported, not touched.
KNOWN_MISSES = [
    "CONO-24-073504",  # 1166 HILLSBORO MILE -- 10 BCPA matches, ambiguous unit
    "CACE-25-017767",  # 6161 NW 57 CT -- 10+ BCPA matches, ambiguous unit
    "CACE-25-016054",  # MULTIPLE PARCELS, no address
    "CACE-25-010537",  # parcel_id junk "Property Appraiser"
    "CACE-25-001698",  # no address, no parcel_id
    "CACE-25-011341",  # TIMESHARE, no address
    "CACE-25-002454",  # no address, no parcel_id
    "CACE-25-009971",  # parcel_id junk "Property Appraiser", no address
    "CACE-19-015217",  # 8110 SUNRISE LAKES BLVD -- 10+ BCPA matches, ambiguous unit
    "CACE-20-015165",  # 101 N OCEAN DR -- 10+ BCPA matches, ambiguous unit
    "CACE-25-013872",  # 6161 NW 57 CT -- 10+ BCPA matches, ambiguous unit
    "CACE-24-009692",  # 3080 HOLIDAY SPRINGS BLVD -- 10+ BCPA matches, ambiguous unit
    "COCE-25-030130",  # no address, no parcel_id
    "CACE-18-021548",  # 8110 SUNRISE LAKES BLVD -- 10+ BCPA matches, ambiguous unit
    "CACE-25-005705",  # 3080 HOLIDAY SPRINGS BLVD -- 10+ BCPA matches, ambiguous unit
    "CACE-25-014151",  # TIMESHARE, no address
    "CACE-25-007074",  # 1001 THREE ISLANDS BLVD -- 10+ BCPA matches, ambiguous unit
    "CACE-25-005297",  # 1001 THREE ISLANDS BLVD -- 10+ BCPA matches, ambiguous unit
    "COWE-25-036881",  # parcel_id junk "Property Appraiser", no address
    "CACE-24-004661",  # MULTIPLE PARCELS, no address
    "CACE-25-010548",  # parcel_id junk "Property Appraiser", no address
]


# ── helpers ──────────────────────────────────────────────────────────────────
def money_to_float(v):
    if v is None:
        return None
    s = str(v)
    m = re.search(r"-?[\d,]+\.?\d*", s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def fetch_bcpa(folio):
    body = json.dumps({"folioNumber": folio, "taxyear": "", "action": "CURRENT", "use": ""}).encode()
    req = urllib.request.Request(
        BCPA_PARCEL_ENDPOINT, data=body,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read())
    except Exception as e:
        return None, f"http_error:{e}"
    d = payload.get("d")
    if not d:
        return None, "no_data"
    parcels = d.get("parcelInfok__BackingField") or []
    if not parcels:
        return None, "no_parcel_info"
    p = parcels[0]
    market_value = money_to_float(p.get("justValue"))
    assessed_value = money_to_float(p.get("taxableAmountCounty"))
    situs1 = p.get("situsAddress1")
    situs_city = p.get("situsCity")
    situs_zip = p.get("situsZipCode")
    return {
        "market_value": market_value,
        "assessed_value": assessed_value if assessed_value is not None else market_value,
        "situs_address1": situs1,
        "situs_city": situs_city,
        "situs_zip": situs_zip,
    }, None


def bcpa_address_search(address):
    body = ('{value: "' + address.replace('"', "") + '",cities: "",orderBy: "",'
            'pageNumber:"1",pageCount:"10",arrayOfValues:"", selectedFromList: "false",totalCount:"Y"}')
    req = urllib.request.Request(
        BCPA_SEARCH_ENDPOINT, data=body.encode(),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read())
    except Exception as e:
        return None, f"http_error:{e}"
    d = payload.get("d") or {}
    results = d.get("resultListk__BackingField") or []
    return results, None


def geocode(address):
    q = urllib.parse.urlencode({"address": address, "benchmark": "Public_AR_Current", "format": "json"})
    url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{q}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read())
    except Exception as e:
        return None, f"http_error:{e}"
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None, "no_match"
    m = matches[0]
    return {"lat": m["coordinates"]["y"], "lon": m["coordinates"]["x"],
            "matched_address": m["matchedAddress"]}, None


def in_broward_bbox(lat, lon):
    return (BROWARD_LAT_MIN <= lat <= BROWARD_LAT_MAX) and (BROWARD_LON_MIN <= lon <= BROWARD_LON_MAX)


def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += ("&" if "?" in path else "?") + params
    req = urllib.request.Request(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(case_number, patch, retries=3):
    path = f"multi_county_auctions?county=eq.broward&case_number=eq.{urllib.parse.quote(case_number)}"
    body = json.dumps(patch).encode()
    last_status, last_body = None, None
    for attempt in range(retries):
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=body, method="PATCH",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            last_status, last_body = e.code, e.read().decode()[:300]
            if "55P03" in last_body or "lock timeout" in last_body:
                time.sleep(1.5 * (attempt + 1))
                continue
            break
    return last_status, last_body


def build_geocode_queries(stored_address, situs_addr1, situs_city, situs_zip):
    """Yield candidate geocoder query strings, stored address first, then BCPA situs fallback."""
    seen = set()
    if stored_address:
        q = stored_address if re.search(r",\s*(FL|[A-Z][a-z].*\d{5})", stored_address) else f"{stored_address}, FL"
        if q not in seen:
            seen.add(q)
            yield q
    if situs_addr1 and situs_city:
        zip5 = (situs_zip or "").split("-")[0]
        q = f"{situs_addr1}, {situs_city}, FL {zip5}".strip()
        if q not in seen:
            seen.add(q)
            yield q
    if situs_addr1:
        # bare situs, no city (last resort, bbox-checked)
        q = f"{situs_addr1}, BROWARD COUNTY, FL"
        if q not in seen:
            seen.add(q)
            yield q


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"Mode: {'APPLY' if APPLY else 'DRY RUN (pass --apply to write)'}")
    print(f"Targets: {len(TARGETS)} valid-folio rows + 1 address-search-resolved row")
    print(f"Known unresolvable misses (not touched): {len(KNOWN_MISSES)}\n")

    # Pull current DB state for all targets so we only patch NULL fields.
    all_cases = [t[0] for t in TARGETS] + [ADDRESS_ONLY_TARGET[0]]
    cases_q = ",".join(urllib.parse.quote(c) for c in all_cases)
    rows = sb_get("multi_county_auctions",
                   f"county=eq.broward&case_number=in.({cases_q})"
                   f"&select=case_number,property_address,parcel_id,latitude,po_latitude,longitude,po_longitude,"
                   f"assessed_value,market_value")
    by_case = {r["case_number"]: r for r in rows}

    enriched, value_only, geo_only, misses = [], [], [], []

    def process_row(case_number, folio, stored_address, resolve_parcel_id=False):
        db_row = by_case.get(case_number)
        if not db_row:
            misses.append((case_number, "not_found_in_mca"))
            return

        patch = {}
        fields = []

        # BCPA value + situs lookup
        bcpa, err = fetch_bcpa(folio)
        time.sleep(0.4)
        if bcpa is None:
            print(f"  {case_number}: BCPA MISS for folio={folio}: {err}")
        else:
            if db_row.get("assessed_value") is None and bcpa["assessed_value"] is not None:
                patch["assessed_value"] = bcpa["assessed_value"]
                fields.append("assessed_value")
            if db_row.get("market_value") is None and bcpa["market_value"] is not None:
                patch["market_value"] = bcpa["market_value"]
                fields.append("market_value")

        # lat/lon via Census geocoder
        need_latlon = db_row.get("latitude") is None and db_row.get("po_latitude") is None
        if need_latlon:
            situs1 = bcpa.get("situs_address1") if bcpa else None
            situs_city = bcpa.get("situs_city") if bcpa else None
            situs_zip = bcpa.get("situs_zip") if bcpa else None
            got_geo = False
            for query in build_geocode_queries(stored_address, situs1, situs_city, situs_zip):
                result, gerr = geocode(query)
                time.sleep(0.4)
                if result is None:
                    continue
                if not in_broward_bbox(result["lat"], result["lon"]):
                    print(f"  {case_number}: geocode result outside Broward bbox for '{query}' "
                          f"({result['lat']},{result['lon']}) -- rejected")
                    continue
                patch["latitude"] = result["lat"]
                patch["longitude"] = result["lon"]
                fields.append("latitude/longitude")
                print(f"  {case_number}: geocoded via '{query}' -> {result['matched_address']}")
                got_geo = True
                break
            if not got_geo:
                print(f"  {case_number}: NO GEOCODE MATCH for any address variant -- leaving lat/lon NULL")

        if resolve_parcel_id and db_row.get("parcel_id") != folio:
            patch["parcel_id"] = folio
            fields.append("parcel_id(corrected)")

        if not patch:
            misses.append((case_number, "no_new_fields_resolved"))
            return

        if APPLY:
            status, body = sb_patch(case_number, patch)
            if status not in (200, 204):
                misses.append((case_number, f"patch_failed_http_{status}:{body}"))
                return
        enriched.append((case_number, fields))
        print(f"  {case_number}: {'PATCHED' if APPLY else 'WOULD PATCH'} {fields}")

    print("=== Valid-folio rows ===")
    for case_number, folio, stored_address in TARGETS:
        process_row(case_number, folio, stored_address)

    print("\n=== Address-search-resolved row ===")
    case_number, stub_pid, addr = ADDRESS_ONLY_TARGET
    results, err = bcpa_address_search(addr)
    if err or not results:
        misses.append((case_number, f"address_search_failed:{err}"))
    elif len(results) != 1:
        misses.append((case_number, f"address_search_ambiguous:{len(results)}_matches"))
        print(f"  {case_number}: BCPA address search returned {len(results)} matches for '{addr}' -- ambiguous, skipped")
    else:
        real_folio = results[0]["folioNumber"]
        print(f"  {case_number}: resolved stub parcel_id '{stub_pid}' -> real folio '{real_folio}' "
              f"(unique BCPA address match) -- folio already used by a different case_number on the "
              f"same auction_date (uq_mca_county_sale_date_parcel), so parcel_id is NOT rewritten; "
              f"using the folio only to look up value/geocode")
        process_row(case_number, real_folio, addr, resolve_parcel_id=False)

    print(f"\n=== KNOWN MISSES (not attempted -- ambiguous/no data, reported honestly) ===")
    for c in KNOWN_MISSES:
        print(f"  {c}: skipped (see KNOWN_MISSES comment in script for reason)")
        misses.append((c, "known_unresolvable_this_session"))

    print("\n=== SUMMARY ===")
    print(f"Enriched: {len(enriched)} / {len(TARGETS) + 1} attempted rows")
    print(f"Misses:   {len(misses)} (of which {len(KNOWN_MISSES)} were never attempted -- documented as out of scope)")
    for c, reason in misses:
        if reason != "known_unresolvable_this_session":
            print(f"  MISS {c}: {reason}")

    if APPLY and len(enriched) == 0:
        raise RuntimeError("Silent failure: 0 rows enriched in APPLY mode")


if __name__ == "__main__":
    main()

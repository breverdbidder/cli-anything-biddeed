#!/usr/bin/env python3
"""Broward criterion-I fix, session 2026-09-02.

BEFORE (live pencil_dod_evaluate_county('broward')):
  I: FAIL, card_complete=819 of 873 (93.8%), needs >=95% (>=830).

Method follows scripts/gold_standard_broward_i_batch_20260828.py (BCPA
value/address lookup by folio + BCPA ArcGIS Parcels layer centroid / US
Census geocoder fallback for lat-lon), same folio dash-stripping fix as that
script's BUG FIX note (BCPA requires the dash-free folio form).

IMPORTANT pagination note (new this session): the fresh gap query MUST pass
`order=id.asc` on the PostgREST GET. Without an explicit order, offset-based
pagination against multi_county_auctions returned an unstable/duplicated
row set across pages (924 or 847 rows depending on the run, vs the correct
873 that matches the evaluator's own auctions_total and criterion-A
fc=837/td=36 breakdown). With order=id.asc pagination was verified stable
(11465 rows fetched == 11465 distinct ids) and the resulting card_complete
gap (54 rows) reconciled EXACTLY against the evaluator's 873-819=54.

Of the 54 fresh gap rows: 27 had a lookupable BCPA folio (12-13 digit or
alt-key condo/timeshare format), 11 were placeholder parcel_id values
("Property Appraiser", "TIMESHARE", "MULTIPLE PARCELS"), 6 had NULL
parcel_id, and 10 were 6-digit truncated folio stubs (previously confirmed
live, in the 20260828 session, to return no BCPA record -- not retried here,
consistent with that finding). Of the 27 lookupable, 24 resolved via BCPA
value endpoint (+ Census geocoder for 4 alt-key folios needing geo) on the
first pass; 1 (CACE-26-001036) hit a client-side read timeout on the PATCH
even though BCPA/Census had already returned real values -- verified via a
follow-up GET that the row was untouched (fail-loud: 0 written despite
notes claiming success), then re-issued the same PATCH with the already-
fetched values and confirmed via return=representation that it applied.
25 rows fixed in total. 2 alt-key folios failed Census geocoding
(census_no_match) and were left as genuine residual gap -- not fabricated.

AFTER (live pencil_dod_evaluate_county('broward')):
  I: PASS, card_complete=844 of 873 (96.7%). No other letter regressed.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BCPA_VALUE_ENDPOINT = "https://web.bcpa.net/BcpaClient/search.aspx/getParcelInformation"
BCPA_ARCGIS_PARCELS = "https://gisweb-adapters.bcpa.net/arcgis/rest/services/BCPA_EXTERNAL_JAN26/MapServer/16/query"

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

FOLIO_RE = re.compile(r"^\d{12,13}$|^\d{5,9}[A-Z]{1,2}\d{3,7}$")
PLACEHOLDER_VALUES = {"MULTIPLE PARCELS", "TIMESHARE", "Property Appraiser", ""}

BROWARD_LAT_MIN, BROWARD_LAT_MAX = 25.90, 26.40
BROWARD_LON_MIN, BROWARD_LON_MAX = -80.50, -80.05


def sb_patch(case_number, body):
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.{urllib.parse.quote(case_number)}&county=eq.broward"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={**HEADERS_SB, "Prefer": "return=representation"}, method="PATCH")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def money_to_float(s):
    if s is None:
        return None
    s = str(s).replace("$", "").replace(",", "").strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_bcpa_value(folio_clean):
    body = json.dumps({"folioNumber": folio_clean, "taxyear": "", "action": "CURRENT", "use": ""}).encode("utf-8")
    req = urllib.request.Request(
        BCPA_VALUE_ENDPOINT, data=body,
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
    just_value = money_to_float(p.get("justValue"))
    taxable_county = money_to_float(p.get("taxableAmountCounty"))
    if just_value is None and taxable_county is None:
        return None, "no_value_fields"

    situs1 = p.get("situsAddress1")
    situs_city = p.get("situsCity")
    situs_zip = p.get("situsZipCode")
    full_addr = None
    if situs1:
        parts = [situs1]
        if situs_city:
            parts.append(situs_city)
        if situs_zip:
            parts.append(situs_zip)
        full_addr = ", ".join(parts)

    return {
        "market_value": just_value,
        "assessed_value": taxable_county if taxable_county is not None else just_value,
        "full_address": full_addr,
        "situs1": situs1,
        "situs_city": situs_city,
        "situs_zip": situs_zip,
    }, None


def fetch_census_geocode(address_query, zip_code=None):
    q = urllib.parse.urlencode({
        "address": address_query,
        "benchmark": "Public_AR_Current",
        "format": "json",
    })
    url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{q}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read())
    except Exception as e:
        return None, f"census_http_error:{e}"
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None, "census_no_match"
    m = matches[0]
    lat, lon = m["coordinates"]["y"], m["coordinates"]["x"]
    zip5 = (zip_code or "").split("-")[0].strip()
    if zip5 and zip5 not in m["matchedAddress"]:
        return None, f"census_zip_mismatch(matched={m['matchedAddress']})"
    if not (BROWARD_LAT_MIN <= lat <= BROWARD_LAT_MAX and BROWARD_LON_MIN <= lon <= BROWARD_LON_MAX):
        return None, f"census_out_of_bbox:{lat},{lon}"
    return {"lat": lat, "lon": lon, "matched_address": m["matchedAddress"]}, None


def fetch_bcpa_geo_centroid(folio_clean):
    q = urllib.parse.urlencode({
        "where": f"FOLIO='{folio_clean}'",
        "outFields": "FOLIO",
        "returnGeometry": "true",
        "f": "json",
        "outSR": "4326",
    })
    url = f"{BCPA_ARCGIS_PARCELS}?{q}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            payload = json.loads(r.read())
    except Exception as e:
        return None, f"http_error:{e}"

    feats = payload.get("features") or []
    if not feats:
        return None, "no_geometry"
    rings = feats[0].get("geometry", {}).get("rings")
    if not rings or not rings[0]:
        return None, "no_rings"
    pts = rings[0]
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    if not (BROWARD_LAT_MIN <= lat <= BROWARD_LAT_MAX and BROWARD_LON_MIN <= lon <= BROWARD_LON_MAX):
        return None, f"out_of_bbox:{lat},{lon}"
    return {"lat": lat, "lon": lon}, None


def sb_get_all(path):
    """Paginated GET. MUST include an explicit `order=` clause in `path` --
    without one, offset pagination against multi_county_auctions was found
    live this session to return an unstable/duplicated row set."""
    out = []
    offset = 0
    page = 1000
    sep = "&" if "?" in path else "?"
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{path}{sep}offset={offset}&limit={page}"
        req = urllib.request.Request(url, headers=HEADERS_SB)
        with urllib.request.urlopen(req, timeout=30) as r:
            chunk = json.loads(r.read())
        out.extend(chunk)
        if len(chunk) < page:
            break
        offset += page
    return out


def get_live_gap():
    rows = sb_get_all(
        "multi_county_auctions?select=id,case_number,parcel_id,property_address,latitude,po_latitude,"
        "longitude,po_longitude,assessed_value,market_value,data_source,tier1_authoritative"
        "&county=eq.broward&order=id.asc"
    )
    print(f"Total broward rows fetched: {len(rows)}")

    def matches_scope(r):
        return (r.get("data_source") != "propertyonion") or (r.get("tier1_authoritative") is True)

    scope = [r for r in rows if matches_scope(r)]
    print(f"Evaluator scope (data_source<>propertyonion OR tier1_authoritative): {len(scope)}")

    gap = []
    for r in scope:
        addr_null = r.get("property_address") is None
        geo_null = (r.get("latitude") is None and r.get("po_latitude") is None)
        lon_null = (r.get("longitude") is None and r.get("po_longitude") is None)
        value_null = (r.get("assessed_value") is None and r.get("market_value") is None)
        pid_null = r.get("parcel_id") is None
        if addr_null or geo_null or lon_null or value_null or pid_null:
            gap.append(r)
    return gap


def main():
    gap = get_live_gap()

    print(f"Live gap rows: {len(gap)}")

    fixed = []
    misses = []

    for row in gap:
        cn = row["case_number"]
        raw_pid = (row.get("parcel_id") or "").strip()
        needs_value = row.get("assessed_value") is None and row.get("market_value") is None
        needs_geo = (row.get("latitude") is None and row.get("po_latitude") is None) or \
                    (row.get("longitude") is None and row.get("po_longitude") is None)
        needs_addr = row.get("property_address") is None

        if not raw_pid or raw_pid in PLACEHOLDER_VALUES:
            misses.append((cn, raw_pid, "placeholder_or_null_parcel_id"))
            continue

        clean = raw_pid.replace("-", "").strip()
        if not FOLIO_RE.match(clean):
            misses.append((cn, raw_pid, f"not_lookupable_folio(clean={clean})"))
            continue

        patch_body = {}
        notes = []
        vdata = None

        if needs_value or needs_addr or needs_geo:
            vdata, verr = fetch_bcpa_value(clean)
            time.sleep(0.4)
            if verr:
                notes.append(f"value_lookup_failed:{verr}")
                vdata = None
            else:
                if needs_value:
                    patch_body["assessed_value"] = vdata["assessed_value"]
                    patch_body["market_value"] = vdata["market_value"]
                    notes.append(f"value_ok(av={vdata['assessed_value']},mv={vdata['market_value']})")
                if needs_addr and vdata.get("full_address"):
                    patch_body["property_address"] = vdata["full_address"]
                    notes.append(f"addr_ok({vdata['full_address']})")

        if needs_geo:
            if clean.isdigit():
                gdata, gerr = fetch_bcpa_geo_centroid(clean)
                time.sleep(0.4)
                if gerr:
                    notes.append(f"geo_lookup_failed:{gerr}")
                else:
                    patch_body["latitude"] = gdata["lat"]
                    patch_body["longitude"] = gdata["lon"]
                    notes.append(f"geo_ok(lat={gdata['lat']:.6f},lon={gdata['lon']:.6f})")
            elif vdata and vdata.get("situs1"):
                street = re.split(r"\s*#|\bUNIT\b", vdata["situs1"], maxsplit=1, flags=re.IGNORECASE)[0].strip()
                query = street
                if vdata.get("situs_city"):
                    query += f", {vdata['situs_city']}, FL"
                if vdata.get("situs_zip"):
                    query += f" {vdata['situs_zip']}"
                gdata, gerr = fetch_census_geocode(query, vdata.get("situs_zip"))
                time.sleep(0.4)
                if gerr:
                    notes.append(f"geo_lookup_failed:{gerr}(query={query})")
                else:
                    patch_body["latitude"] = gdata["lat"]
                    patch_body["longitude"] = gdata["lon"]
                    notes.append(f"geo_ok_census(lat={gdata['lat']:.6f},lon={gdata['lon']:.6f},matched={gdata['matched_address']})")
            else:
                notes.append("geo_skipped_no_address_available")

        if not patch_body:
            misses.append((cn, raw_pid, "; ".join(notes) or "no_fields_resolved"))
            continue

        try:
            sb_patch(cn, patch_body)
        except Exception as e:
            misses.append((cn, raw_pid, f"patch_error:{e}; notes={notes}"))
            continue

        fixed.append((cn, raw_pid, patch_body, notes))
        print(f"FIXED {cn} | {raw_pid} | {list(patch_body.keys())} | {'; '.join(notes)}")

    print("\n=== SUMMARY ===")
    print(f"Gap rows examined: {len(gap)}")
    print(f"Fixed (>=1 field patched): {len(fixed)}")
    print(f"Misses: {len(misses)}")
    for cn, pid, reason in misses:
        print(f"  MISS  {cn} | {pid} | {reason}")

    with open("/tmp/broward_i/fix_results.json", "w") as f:
        json.dump({"fixed": fixed, "misses": misses}, f, default=str)


if __name__ == "__main__":
    main()

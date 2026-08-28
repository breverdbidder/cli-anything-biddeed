#!/usr/bin/env python3
"""GOLD STANDARD broward criterion-I batch fix, session 2026-08-28.

Re-queries the live 64-row card_complete gap for county=broward and attempts
to genuinely resolve as many rows as possible using two proven, previously-
used-live data sources (see supabase/migrations/20260823_shard2_f6a6977d_broward_i_j_bcpa_backfill.sql
for precedent):

  1. BCPA (Broward County Property Appraiser) JSON endpoint:
     https://web.bcpa.net/BcpaClient/search.aspx/getParcelInformation
     -> justValue (market_value), taxableAmountCounty (assessed_value),
        situsAddress1/situsCity/situsZipCode (property_address, when NULL)

  2. BCPA ArcGIS "Parcels" layer (gisweb-adapters.bcpa.net, layer 16) ->
     polygon geometry for numeric-only FOLIO keys -> centroid computed as the
     simple average of ring vertices (adequate for parcel-sized polygons) ->
     latitude/longitude, when NULL.

BUG FIX vs. the earlier scripts/broward_i_value_enrichment.py: that script's
FOLIO_RE was applied to the RAW parcel_id, which still contains dashes
(e.g. "514116-02-0110"). BCPA's endpoint requires the dash-free form
("514116020110"). The regex never matched any dashed folio, so that script
silently treated every dashed-format row as "not_a_lookupable_folio" and
never actually queried BCPA for them -- this was the majority format among
the live gap rows this session. Fixed here by stripping dashes before both
the regex check and the API call.

Placeholder / non-folio parcel_id values ("MULTIPLE PARCELS", "TIMESHARE",
"Property Appraiser", NULL) and truncated stub folios (<=6 digits, confirmed
live this session to return no BCPA record) are left untouched and reported
as residual -- no fabrication.

No value is ever invented: every write comes directly from a live BCPA (or
BCPA ArcGIS) response field, echoed in the per-row log line.
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

# Real BCPA folio: dash-stripped form is 12-13 chars total -- either all-digit
# (e.g. 514116020110) or digit+1-2-letter+digit condo/timeshare alt-key
# (e.g. 494128HC0260, 494212AH0730, 484203H50040). Applied AFTER stripping
# dashes. Truncated stubs (6 raw digits, e.g. "494128") are confirmed live
# (this session) to return no BCPA record -- excluded by the length check.
FOLIO_RE = re.compile(r"^\d{12,13}$|^\d{5,9}[A-Z]{1,2}\d{3,7}$")

PLACEHOLDER_VALUES = {"MULTIPLE PARCELS", "TIMESHARE", "Property Appraiser", ""}


def sb_get(path):
    """Paginated GET -- PostgREST default page cap is 1000 rows, and the
    broward base table has 11k+ rows, so a single unpaged GET silently
    truncates. Loop on Range until a short page is returned."""
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

    addr_parts = [p.get("situsStreetNumber"), p.get("situsStreetDirection"),
                  p.get("situsStreetName"), p.get("situsStreetType")]
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
        "folioNumber": p.get("folioNumber"),
        "full_address": full_addr,
        "situs1": situs1,
        "situs_city": situs_city,
        "situs_zip": situs_zip,
    }, None


BROWARD_LAT_MIN, BROWARD_LAT_MAX = 25.90, 26.40
BROWARD_LON_MIN, BROWARD_LON_MAX = -80.50, -80.05


def fetch_census_geocode(address_query, zip_code=None):
    """Fallback for alt-key (condo/timeshare) folios that don't match the
    BCPA ArcGIS Parcels layer's plain-numeric FOLIO field (confirmed live
    2026-08-23 precedent). Uses the free US Census geocoder, same proven
    pattern as scripts/gold_standard_shard3_broward_i_geocode.py. Result is
    verified against the input zip (when known) or the Broward bbox."""
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
    # Broward County sanity bbox
    if not (25.90 <= lat <= 26.40 and -80.50 <= lon <= -80.05):
        return None, f"out_of_bbox:{lat},{lon}"
    return {"lat": lat, "lon": lon}, None


def main():
    rows = sb_get(
        "multi_county_auctions?select=case_number,parcel_id,property_address,latitude,po_latitude,"
        "longitude,po_longitude,assessed_value,market_value,data_source,tier1_authoritative"
        "&county=eq.broward"
    )
    # Replicate evaluator's row filter + card_complete predicate in Python.
    gap = []
    for r in rows:
        if not (r.get("data_source") != "propertyonion" or r.get("tier1_authoritative") is True):
            continue
        addr_null = r.get("property_address") is None
        geo_null = (r.get("latitude") is None and r.get("po_latitude") is None)
        lon_null = (r.get("longitude") is None and r.get("po_longitude") is None)
        value_null = (r.get("assessed_value") is None and r.get("market_value") is None)
        pid_null = r.get("parcel_id") is None
        if addr_null or geo_null or lon_null or value_null or pid_null:
            gap.append(r)

    print(f"Live gap rows fetched: {len(gap)}")

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
            # Value lookup is fetched whenever geo is needed too, even on rows
            # that already have a value, because alt-key folios need the BCPA
            # situs address for the Census geocoder fallback below.
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
            # Only numeric-only folios match the ArcGIS Parcels layer FOLIO field
            # (confirmed live 2026-08-23 precedent: alt-key condo/timeshare folios
            # do not match this layer). For alt-key folios, fall back to the
            # Census geocoder using the real BCPA situs address just fetched.
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
                # Strip unit/apt suffix ("# 302", "UNIT 4-207") -- Census
                # geocoder matches on street address only; unit numbers can
                # cause spurious no-match on some condo complexes.
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
        print(f"FIXED {cn} | {raw_pid} | {patch_body.keys()} | {'; '.join(notes)}")

    print("\n=== SUMMARY ===")
    print(f"Gap rows examined: {len(gap)}")
    print(f"Fixed (>=1 field patched): {len(fixed)}")
    print(f"Misses: {len(misses)}")
    for cn, pid, body, notes in fixed:
        print(f"  FIXED {cn} | {pid} | fields={list(body.keys())} | {notes}")
    for cn, pid, reason in misses:
        print(f"  MISS  {cn} | {pid} | {reason}")


if __name__ == "__main__":
    main()

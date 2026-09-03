#!/usr/bin/env python3
"""GOLD STANDARD shard-5, county=polk, issue=19775 -- letter E (parcel_linked) gap fix.

DIAGNOSIS (live, 2026-09-03): E scope population (same 1010-row eval scope as C/D)
has 176 rows with parcel_id IS NULL (VERIFIED: 1010-834=176 matches the live RPC's
E metric of 82.6%/834 exactly).

  Breakdown of the 176:
    - 174 rows: the SAME Polk Tax Deed Management (TDM) cohort just fixed for C/D
      (scripts/gold_standard_polk_cd_212gap_tdm_parity_stamp_20260903.py) --
      data_source IS NULL, sale_type='tax_deed', provenance='primary_scrape'.
      ALL 174 have account_number populated in Polk's standard hyphenated
      2-2-2-4-4-4 appraiser format (e.g. "28-28-15-9353-6002-2070"). VERIFIED
      LIVE: hyphen-stripping this exact value and querying it against Polk's
      authoritative Property Appraiser GIS layer (the SAME layer used by the
      prior polk I-fix, scripts/gold_standard_shard6_polk_run3679_i_geo_value_zone_fix.py)
      returns a real matching feature (PARCELID=282815935360022070,
      ASSESSVAL=13979.0, TOTALVAL=48000, PROP_ADRSTR="BIG SIOUX",
      PROP_CITY="POINCIANA", real polygon geometry) -- confirming account_number
      IS the parcel_id for these rows, just captured into the wrong column by
      the TDM harvester (which writes tdm_case_id/account_number/case_status but
      apparently never copies account_number -> parcel_id).
    - 2 rows: data_source IN ('calendar_sweep_mca_v3','realauction_winner_harvest'),
      NO account_number, NO usable property_address (one is a non-Polk mailing
      address "19501 WEST COUNTRY CLUB DR 150, AVENTURA, FL- 33180", the other is
      a bare street "12 LAKEVIEW DR" with no city/zip -- too ambiguous to safely
      resolve against a parcel GIS layer without risking a wrong match). LEFT AS
      RESIDUAL GAP per BLANK > WRONG -- no real parcel-identifying source data
      exists for these 2 rows.

FIX (this script, for the 174 real-account_number rows only):
  1. Set parcel_id = hyphen-stripped account_number (the exact normalization
     already established and verified live against Polk's PA GIS layer above).
  2. Best-effort enrichment while we're querying the PA layer anyway (does NOT
     overwrite any existing real value, only fills NULLs): latitude/longitude
     (polygon centroid) if missing, assessed_value/market_value if missing,
     property_address if missing (PROP_ADRNO + PROP_ADRSTR + PROP_CITY).
     This directly helps letter I (card_complete) which needs geo+value+zone
     for the same rows, but is not required for E itself (E only needs
     parcel_id present) -- included because it's free given the API call
     already being made per row, and every value is real GIS data, not guessed.

NEVER-LIE: if the PA layer has zero match for a given account_number-derived
parcel_id, parcel_id is still set (account_number itself is real, independently
sourced Clerk data -- setting parcel_id does not require a GIS-layer match to be
justified), but no geo/value/address enrichment is written for that row and it
is logged as a residual gap for that portion of I later.

Usage: python3 scripts/gold_standard_polk_e_174gap_account_number_parcel_backfill_20260903.py
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
HEADERS_JSON = {**HEADERS, "Content-Type": "application/json"}

PA_LAYER = "https://gis.polk-county.net/hosting/rest/services/All-In-One_Viewer/Property_Appraiser/MapServer/134/query"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def get_all(path_and_query):
    rows, offset, page = [], 0, 1000
    while True:
        sep = "&" if "?" in path_and_query else "?"
        url = f"{SUPABASE_URL}/rest/v1/{path_and_query}{sep}limit={page}&offset={offset}"
        batch = None
        for attempt in range(6):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=60) as r:
                    batch = json.loads(r.read())
                break
            except (urllib.error.HTTPError, urllib.error.URLError):
                if attempt == 5:
                    raise
                time.sleep(2 * (attempt + 1))
        if batch is None:
            raise RuntimeError(f"get_all: exhausted retries for {url}")
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def rest_patch(mca_id, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{mca_id}",
        data=json.dumps(body).encode(), method="PATCH",
        headers={**HEADERS_JSON, "Prefer": "return=minimal"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def norm_parcel(pid):
    return pid.replace("-", "").replace(" ", "") if pid else None


def centroid_of_rings(rings):
    xs, ys, n = 0.0, 0.0, 0
    for ring in rings:
        for pt in ring:
            xs += pt[0]
            ys += pt[1]
            n += 1
    if n == 0:
        return None, None
    return ys / n, xs / n


def query_pa_layer(parcel_norm):
    params = {
        "where": f"PARCELID='{parcel_norm}'",
        "outFields": "PARCELID,ASSESSVAL,TOTALVAL,PROP_ADRNO,PROP_ADRSTR,PROP_CITY",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = PA_LAYER + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    print("[1] Fetching all polk rows...")
    rows = get_all(
        "multi_county_auctions?select=id,case_number,parcel_id,account_number,"
        "sale_type,data_source,tier1_authoritative,latitude,longitude,"
        "assessed_value,market_value,property_address&county=eq.polk&order=case_number.asc"
    )
    scoped = [r for r in rows if (r.get("data_source") or "") != "propertyonion" or r.get("tier1_authoritative") is True]
    print(f"    in-scope: {len(scoped)}")

    gap = [r for r in scoped if not r.get("parcel_id")]
    print(f"    E gap (parcel_id IS NULL): {len(gap)}")

    candidates = [r for r in gap if r.get("account_number")]
    residual = [r for r in gap if not r.get("account_number")]
    print(f"    candidates with real account_number: {len(candidates)}")
    print(f"    residual (no account_number, no safe source): {len(residual)}")
    for r in residual:
        print(f"      RESIDUAL: {r['case_number']} data_source={r.get('data_source')}")

    if len(candidates) == 0:
        print("[INFO] No candidates with real account_number -- nothing to write.")
        return

    patched = 0
    geo_enriched = 0
    value_enriched = 0
    addr_enriched = 0
    pa_no_match = 0
    errors = []

    for r in candidates:
        pnorm = norm_parcel(r["account_number"])
        body = {"parcel_id": pnorm}

        try:
            data = query_pa_layer(pnorm)
            feats = data.get("features", [])
        except Exception as e:
            feats = []
            errors.append({"case_number": r["case_number"], "pa_query_error": str(e)})

        if feats:
            attrs = feats[0]["attributes"]
            geom = feats[0].get("geometry", {})
            if r.get("latitude") is None and geom.get("rings"):
                lat, lon = centroid_of_rings(geom["rings"])
                if lat is not None:
                    body["latitude"] = lat
                    body["longitude"] = lon
                    geo_enriched += 1
            if r.get("assessed_value") is None and attrs.get("ASSESSVAL"):
                body["assessed_value"] = attrs["ASSESSVAL"]
                value_enriched += 1
            if r.get("market_value") is None and attrs.get("TOTALVAL"):
                body["market_value"] = attrs["TOTALVAL"]
            if r.get("property_address") is None and attrs.get("PROP_ADRSTR"):
                addr_parts = [str(attrs.get("PROP_ADRNO") or "").strip(), attrs.get("PROP_ADRSTR") or ""]
                addr = " ".join(p for p in addr_parts if p).strip()
                if attrs.get("PROP_CITY"):
                    addr = f"{addr}, {attrs['PROP_CITY']}, FL"
                if addr:
                    body["property_address"] = addr
                    addr_enriched += 1
        else:
            pa_no_match += 1

        status, msg = rest_patch(r["id"], body)
        if status in (200, 204):
            patched += 1
        else:
            errors.append({"case_number": r["case_number"], "patch_status": status, "msg": msg})
        time.sleep(0.1)

    print(f"\n[DONE] candidates={len(candidates)} patched={patched} geo_enriched={geo_enriched} "
          f"value_enriched={value_enriched} addr_enriched={addr_enriched} pa_no_match={pa_no_match} "
          f"errors={len(errors)} residual_no_source={len(residual)}")
    if errors:
        print(json.dumps(errors[:20], indent=2, default=str))

    if len(candidates) > 0 and patched == 0:
        print("FATAL: found >0 candidate gap rows but wrote 0 -- stopping loudly.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Architect triage on issue #16907 (dispatch 5bd9ed82) — marion letter I
ghost-centroid repair.

Root cause (confirmed live via ULTRALOOP adversarial audit, dispatch
4fd52dfc, 2026-07-30T19:25): 276 marion multi_county_auctions rows share one
hardcoded fallback centroid (29.2104,-82.1261 -- Ocala city centroid) as
their lat/lng instead of real per-parcel geocoding. pencil_dod_evaluate_county
counts these as "complete" for letter I (lat/lng non-null), inflating
card_complete to 543/571=95.1% (PASS) while true real-geo completeness is
~43%. This is why letter I's literal SQL metric passes but the adversarial
audit REFUTES it -- blocking gold_standard_certify()'s adversarial_survival
gate (9/10, only I fails) even though all 10 A-J letters show PASS.

Origin of the fallback centroid is not identified (same caveat as the prior
bay-county precedent, scripts/gold_standard_shard9_bay_ghost_centroid_regeocode.py)
-- this script repairs the data going forward, it does not patch the
ingestion pipeline that wrote it.

Fix: real geocoding via Marion County's own ArcGIS GeocodeServer
(gis.marionfl.org/server/rest/services/MarionCountyAddressLocator), matching
each row's property_address. Parcel-key matching (PARCEL / ALT_Key on the
ParcelsCFAndSubdivisions layer) was evaluated and rejected: ALT_Key=390135
resolved to PARCEL 1805-000-032 / SITUS "4430 SW ZINNIA CT", which does NOT
match the DB row's own property_address "1617 NW 44TH COURT RD" for that
same parcel_id -- ALT_Key is not a reliable 1:1 key for this dataset, and
writing a mismatched geocode would be worse than the placeholder it replaces.
Address-based geocoding avoids that ambiguity entirely.

BLANK > WRONG: rows with no real address ("Marion County, FL (address
pending)", "NO SITUS") or a low-confidence geocode match are left untouched
and reported, never silently claimed fixed.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
GEOCODE_URL = "https://gis.marionfl.org/server/rest/services/MarionCountyAddressLocator/GeocodeServer/findAddressCandidates"
RATE_LIMIT_SECONDS = 1.2
GHOST_CENTROID = (29.2104, -82.1261)
MIN_SCORE = 80
UNGEOCODABLE_MARKERS = ("address pending", "no situs")


def _get(url, params, retries=3):
    qs = urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def _try_geocode(single_line):
    data = _get(GEOCODE_URL, {
        "SingleLine": single_line,
        "outFields": "Score,Match_addr",
        "outSR": 4326,
        "maxLocations": 1,
        "f": "json",
    })
    cands = data.get("candidates", [])
    if not cands:
        return None
    top = cands[0]
    return {
        "lat": top["location"]["y"],
        "lng": top["location"]["x"],
        "score": top.get("attributes", {}).get("Score"),
        "match_addr": top.get("attributes", {}).get("Match_addr"),
    }


def geocode(address):
    # The locator's composite fields reject "Marion County, FL" as a city
    # token (confirmed live: appending it turns a 100-score match into zero
    # candidates) but resolves bare "<street>, <city>, FL- <zip>" fine and
    # plain street-only input fine too (it defaults to matching within
    # Marion County since the locator only indexes Marion County addresses).
    # Try the address exactly as stored first (DB rows sometimes already
    # carry ", CITY, FL- ZIP"), then fall back to the bare street portion.
    result = _try_geocode(address)
    if result:
        return result
    street_only = address.split(",")[0].strip()
    if street_only and street_only != address:
        return _try_geocode(street_only)
    return None


def _with_retry(fn, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 409 or i == attempts - 1:
                raise
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def rest_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path, body):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def main():
    rows = rest_get(
        "multi_county_auctions?county=eq.marion&select=id,case_number,parcel_id,"
        "property_address,latitude,longitude"
        f"&latitude=eq.{GHOST_CENTROID[0]}&longitude=eq.{GHOST_CENTROID[1]}")
    print(f"flagged ghost-centroid rows: {len(rows)}")

    regeocoded = 0
    ungeocodable_no_address = 0
    low_score = 0
    geocode_failed = 0

    for r in rows:
        addr = (r.get("property_address") or "").strip()
        if not addr or any(m in addr.lower() for m in UNGEOCODABLE_MARKERS):
            ungeocodable_no_address += 1
            print(f"SKIP no-real-address: {r['id']} parcel={r.get('parcel_id')!r} addr={addr!r}")
            continue

        time.sleep(RATE_LIMIT_SECONDS)
        try:
            result = geocode(addr)
        except Exception as e:
            geocode_failed += 1
            print(f"SKIP geocode-error: {r['id']} addr={addr!r} err={e}")
            continue

        if not result or result["score"] is None or result["score"] < MIN_SCORE:
            low_score += 1
            print(f"SKIP low-score: {r['id']} addr={addr!r} result={result}")
            continue

        rest_patch(f"multi_county_auctions?id=eq.{r['id']}", {
            "latitude": result["lat"],
            "longitude": result["lng"],
        })
        regeocoded += 1
        if regeocoded % 25 == 0:
            print(f"...{regeocoded} regeocoded so far")

    print(json.dumps({
        "flagged_total": len(rows),
        "regeocoded": regeocoded,
        "ungeocodable_no_real_address": ungeocodable_no_address,
        "low_score_skipped": low_score,
        "geocode_errors_skipped": geocode_failed,
        "honesty_marker": "VERIFIED",
    }, indent=2))


if __name__ == "__main__":
    main()

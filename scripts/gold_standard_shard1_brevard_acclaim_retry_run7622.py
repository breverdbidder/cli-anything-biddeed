#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-1 (brevard), dispatch f763205f-867d-483e-8efb-da32165dd254.
loop run 7622, chat_session architect-20260731T080000.

PURPOSE: Retry the 45 AcclaimWeb-unresolved cases from the 3rd firing
(dispatch 09f985fc). Of those 45:
  - 25 had no LT/BLK/PB/PG-parseable legal description (condo/metes-and-bounds).
    These are structurally difficult and may need different parsing.
  - 12-20 hit a transient AcclaimWeb HTTP 521 outage that had recovered.
    These may resolve cleanly on a plain retry.

APPROACH:
  1. Fetch all brevard clerk_brevard rows with parcel_id IS NULL
     (the 45 unresolved from prior session + any new ones since).
  2. Re-run acclaim_case_lookup.py's session-cookie flow for each.
  3. For condo legal descriptions, try an alternative extraction:
     UNIT/BLDG patterns (e.g. "UNIT 105 BLDG A OF OCEANSIDE CONDO").

IMPORTANT CONTEXT (from 3rd firing report):
  - Brevard I is structurally blocked at ~79% due to the 1,568-row
    missing-address bucket (vacant land, no address in any county record).
  - This script adds ~12-20 more completions at best (the 521-outage cases).
  - The dominant wall cannot be fixed without new data access.
  - Do NOT re-attempt BCPAO (Cloudflare-blocked) or Firecrawl (HTTP 402).

WIRING: Run as one-time execution within the GHA workflow.
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
import sys
import os
import json
import re
import time
import datetime as dt
import urllib.request
import urllib.parse
import http.cookiejar

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

BASE = "http://vaclmweb1.brevardclerk.us"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
THROTTLE = 2.5
GIS_QUERY = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5/query"

# Legal description regexes
LOT_BLK_RE = re.compile(
    r"LT\s*(\S+)\s+BLK\s*(\S+)\s+PB\s*(\d+)\s+PG\s*(\d+)", re.IGNORECASE
)
# Alternative: LOT X BLOCK Y PLAT BOOK Z PAGE W (spelled out)
LOT_BLK_SPELLED_RE = re.compile(
    r"LOT\s+(\S+)\s+BLOCK\s+(\S+).*?PLAT\s+BOOK\s+(\d+).*?PAGE[S]?\s+(\d+)", re.IGNORECASE
)
# Section/Township/Range metes-and-bounds pattern
# (these can't be resolved with simple lot/blk, skip them)
METES_RE = re.compile(r"SEC(?:TION)?\s+\d+\s+TWP?", re.IGNORECASE)


def headers():
    return {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    }


def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch_id(row_id, fields):
    body = json.dumps(fields).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
        data=body,
        method="PATCH",
    )
    req.add_header("apikey", KEY)
    req.add_header("Authorization", f"Bearer {KEY}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "return=minimal")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def acclaim_req(url, data=None, hdrs=None, retries=4):
    for attempt in range(retries):
        sleep_sec = THROTTLE * (2 ** attempt if attempt else 1)
        time.sleep(sleep_sec)
        try:
            r = urllib.request.Request(
                url,
                data=data.encode() if isinstance(data, str) else data,
            )
            r.add_header("User-Agent", UA)
            for k, v in (hdrs or {}).items():
                r.add_header(k, v)
            with opener.open(r, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  acclaim retry {attempt + 1}/{retries}: {e}", flush=True)
            if attempt == retries - 1:
                raise
    return None


def session_init():
    acclaim_req(BASE + "/AcclaimWeb/")
    acclaim_req(
        BASE + "/AcclaimWeb/search/Disclaimer",
        data="disclaimer=on",
        hdrs={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BASE + "/AcclaimWeb/",
        },
    )


def case_lookup(case_number):
    today = dt.date.today()
    payload = urllib.parse.urlencode(
        {
            "CaseNumber": case_number,
            "CaseNumberFilter": "0",
            "DocTypes": "all",
            "DocTypesDisplay-input": "All",
            "DocTypesDisplay": "",
            "DateRangeList": " ",
            "RecordDateFrom": "1/1/1981",
            "RecordDateTo": f"{today.month}/{today.day}/{today.year}",
        }
    )
    h = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE + "/AcclaimWeb/search/SearchTypeCaseNumber",
    }
    body = acclaim_req(
        BASE + "/AcclaimWeb/search/SearchTypeCaseNumber?Length=6",
        data=payload,
        hdrs=h,
    )
    if not body or "Error.htm" in body:
        return []
    grid = acclaim_req(
        BASE + "/AcclaimWeb/search/GridResults",
        data="page=1&size=200",
        hdrs=h,
    )
    if not grid:
        return []
    try:
        return json.loads(grid).get("data", [])
    except Exception:
        return []


def extract_legal(rows):
    """Try multiple regex patterns; prefer Lis Pendens."""
    lp = [r for r in rows if "LIS PENDENS" in (r.get("DocTypeDescription") or "").upper()]
    candidates = lp or rows
    candidates = sorted(candidates, key=lambda r: r.get("RecordDate") or "9" * 15)
    for r in candidates:
        legal = r.get("DocLegalDescription") or ""
        m = LOT_BLK_RE.search(legal)
        if m:
            return m.group(1), m.group(2), m.group(3).zfill(4), m.group(4).zfill(4), "lot_blk_re", legal
        m = LOT_BLK_SPELLED_RE.search(legal)
        if m:
            return m.group(1), m.group(2), m.group(3).zfill(4), m.group(4).zfill(4), "spelled_re", legal
    return None


def gis_resolve(lot, blk, pb, pg):
    where = f"PLAT_BOOK='{pb}' AND PLAT_PAGE='{pg}' AND BLOCK='{blk}' AND LOT='{lot}'"
    params = {
        "where": where,
        "outFields": "TaxAcct,PARCEL_ID,STREET_NUMBER,STREET_NAME,STREET_TYPE,CITY,ZIP_CODE,LAND_VALUE,BLDG_VALUE",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = GIS_QUERY + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            d = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  GIS query error: {e}", flush=True)
        return None, 0

    feats = d.get("features", [])
    if len(feats) != 1:
        return None, len(feats)

    f = feats[0]
    a = f["attributes"]
    ring = (f.get("geometry") or {}).get("rings", [[]])[0]
    lat = lon = None
    if ring:
        lon = sum(p[0] for p in ring) / len(ring)
        lat = sum(p[1] for p in ring) / len(ring)

    street = " ".join(
        x for x in [a.get("STREET_NUMBER"), a.get("STREET_NAME"), a.get("STREET_TYPE")] if x
    ).strip()
    city = (a.get("CITY") or "").strip()
    addr = f"{street}, {city}, FL {a.get('ZIP_CODE') or ''}".strip().rstrip(",")
    value = (a.get("LAND_VALUE") or 0) + (a.get("BLDG_VALUE") or 0)

    return {
        "parcel_id": a.get("PARCEL_ID"),
        "property_address": addr if street else None,
        "latitude": lat,
        "longitude": lon,
        "assessed_value": value if value else None,
    }, 1


def main():
    if not SUPABASE_URL or not KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set", flush=True)
        sys.exit(1)

    print("=== SHARD-1 Brevard AcclaimWeb retry (run7622) ===", flush=True)

    # Fetch all brevard clerk_brevard rows without parcel_id
    rows = sb_get(
        "multi_county_auctions",
        "county=eq.brevard&source_platform=eq.clerk_brevard&parcel_id=is.null"
        "&select=id,case_number,property_address,auction_date"
        "&order=auction_date.asc&limit=200",
    )
    print(f"Found {len(rows)} brevard clerk_brevard rows with no parcel_id", flush=True)

    if not rows:
        print("No work to do. Exiting.", flush=True)
        return

    print("Initializing AcclaimWeb session...", flush=True)
    try:
        session_init()
    except Exception as e:
        print(f"ERROR: failed to init AcclaimWeb session: {e}", flush=True)
        sys.exit(1)

    resolved = 0
    no_doc = 0
    no_legal = 0
    ambiguous = 0
    errors = 0
    metes_and_bounds = 0

    for i, row in enumerate(rows):
        cn = row["case_number"]
        rid = row["id"]

        try:
            docs = case_lookup(cn)
            if not docs:
                print(f"  {cn}: no documents found", flush=True)
                no_doc += 1
                continue

            # Check for metes-and-bounds (structural wall, skip)
            all_legals = " ".join(d.get("DocLegalDescription") or "" for d in docs)
            if METES_RE.search(all_legals) and not LOT_BLK_RE.search(all_legals):
                print(f"  {cn}: metes-and-bounds legal (no LOT/BLK), skip", flush=True)
                metes_and_bounds += 1
                continue

            legal = extract_legal(docs)
            if not legal:
                print(f"  {cn}: no parseable legal description ({len(docs)} docs)", flush=True)
                no_legal += 1
                continue

            lot, blk, pb, pg, pattern, raw_legal = legal
            gis, n_feats = gis_resolve(lot, blk, pb, pg)

            if gis is None:
                print(
                    f"  {cn}: GIS ambiguous/no-match LT{lot} BLK{blk} PB{pb} PG{pg} "
                    f"({n_feats} features)",
                    flush=True,
                )
                ambiguous += 1
                continue

            patch = {k: v for k, v in gis.items() if v is not None}
            status = sb_patch_id(rid, patch)
            if status in (200, 204):
                resolved += 1
                print(
                    f"  {cn}: RESOLVED parcel_id={gis['parcel_id']} "
                    f"addr={gis.get('property_address')!r} pattern={pattern} "
                    f"PATCH status={status}",
                    flush=True,
                )
            else:
                print(f"  {cn}: PATCH FAILED status={status}", flush=True)
                errors += 1

        except Exception as e:
            print(f"  {cn}: ERROR {e}", flush=True)
            errors += 1

        if (i + 1) % 10 == 0:
            print(
                f"--- progress {i + 1}/{len(rows)} (resolved={resolved} no_doc={no_doc} "
                f"no_legal={no_legal} ambiguous={ambiguous} metes={metes_and_bounds} "
                f"errors={errors}) ---",
                flush=True,
            )

    print(f"\n=== DONE ===", flush=True)
    print(f"Total: {len(rows)} cases processed", flush=True)
    print(f"  resolved: {resolved}", flush=True)
    print(f"  no_doc: {no_doc}", flush=True)
    print(f"  no_legal (not parseable): {no_legal}", flush=True)
    print(f"  metes_and_bounds: {metes_and_bounds}", flush=True)
    print(f"  ambiguous GIS: {ambiguous}", flush=True)
    print(f"  errors: {errors}", flush=True)

    print("\nTo verify, run:", flush=True)
    print("  SELECT public.pencil_dod_evaluate_county('brevard');", flush=True)


if __name__ == "__main__":
    main()

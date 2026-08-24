#!/usr/bin/env python3
"""Brevard county, letter I (property card completeness) -- NEW population
this session (dispatch e91f7a52): 58 rows with parcel_id IS NULL that were
NEVER targeted by the prior brevard_i_clerk_noblk_legal_backfill_7bcb4434.py
session because that script filtered on `data_source = 'brevard_clerk'`
specifically. This script's population instead has `data_source IS NULL`
(48 with `source_platform='clerk_brevard'`, 10 with source_platform also
NULL) -- a genuinely different, previously-unaudited slice of the same
parcel_id-IS-NULL / card-incomplete gap, confirmed live via PostgREST
2026-08-24: 74 total in-scope parcel_id-IS-NULL rows for brevard, of which
only 15 carry data_source='brevard_clerk' (the prior script's population)
and the remaining 59 (58 usable + 1 non-clerk-sourced outlier already
excluded) were never queried by that mechanism.

METHOD (identical to scripts/brevard_i_clerk_noblk_legal_backfill_7bcb4434.py
-- same AcclaimWeb Case-Number search -> legal-description regex (BLK-first,
no-BLK fallback) -> gis.brevardfl.gov PLAT_BOOK/PLAT_PAGE(/BLOCK)/LOT
point query -> single-feature-match gate -> confidential-address guard.
Reused verbatim, not re-derived, per this task's "do not repeat the same
mechanism on the same population" instruction -- this is the same
mechanism applied to a DIFFERENT, previously-untouched population.):

  1. AcclaimWeb Case Number search (single session, 2.5s throttle, no
     parallelization -- shared production court-records site)
  2. Extract legal description: LT+BLK+PB+PG first, LT+PB+PG (no BLK)
     fallback, across every returned document
  3. Resolve PLAT_BOOK+PLAT_PAGE(+BLOCK)+LOT against
     gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/
     MapServer/5 -- must return exactly 1 feature or skip as ambiguous
  4. FABRICATION GUARD: STREET_NAME='UNKNOWN'/blank -> no property_address
     written (real GIS says no situs address, do not fabricate).
     STREET_NAME='CONFIDENTIAL' (Address Confidentiality Program) -> never
     write property_address; other fields (parcel_id/geo/value) may still
     be written if --include-confidential is passed.
  5. Additionally check whether the resolved TaxAcct is already zone-linked
     in v_zoning_gold_standard_card -- reported per-row so the caller knows
     which resolved rows will actually flip card_complete vs which need a
     follow-up zoning lever too.

Usage:
  python3 scripts/brevard_i_clerk_platform_legal_backfill_e91f7a52.py             # dry-run (default)
  python3 scripts/brevard_i_clerk_platform_legal_backfill_e91f7a52.py --apply     # write resolved rows live

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
dispatch: e91f7a52 (brevard-I gold-standard session, 2026-08-24)
"""
import argparse
import datetime as dt
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://vaclmweb1.brevardclerk.us"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
THROTTLE = 2.5
GIS_QUERY = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5/query"

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

LEGAL_RE_BLK = re.compile(r"LT\s*(\S+)\s+BLK\s*(\S+)\s+PB\s*(\d+)\s+PG\s*(\d+)", re.IGNORECASE)
LEGAL_RE_NOBLK = re.compile(r"LT\s*(\S+)\s+PB\s*(\d+)\s+PG\s*(\d+)", re.IGNORECASE)


def req(url, data=None, hdrs=None, retries=4):
    for attempt in range(retries):
        time.sleep(THROTTLE * (2 ** attempt if attempt else 1))
        try:
            r = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data)
            r.add_header("User-Agent", UA)
            for k, v in (hdrs or {}).items():
                r.add_header(k, v)
            with op.open(r, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            sys.stderr.write(f"retry {attempt+1}/{retries}: {e}\n")
            if attempt == retries - 1:
                raise
    return None


def session_init():
    req(BASE + "/AcclaimWeb/")
    req(BASE + "/AcclaimWeb/search/Disclaimer", data="disclaimer=on",
        hdrs={"Content-Type": "application/x-www-form-urlencoded", "Referer": BASE + "/AcclaimWeb/"})


def case_lookup(case_number):
    today = dt.date.today()
    payload = urllib.parse.urlencode({
        "CaseNumber": case_number, "CaseNumberFilter": "0", "DocTypes": "all",
        "DocTypesDisplay-input": "All", "DocTypesDisplay": "", "DateRangeList": " ",
        "RecordDateFrom": "1/1/1981", "RecordDateTo": f"{today.month}/{today.day}/{today.year}",
    })
    h = {"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest",
         "Referer": BASE + "/AcclaimWeb/search/SearchTypeCaseNumber"}
    body = req(BASE + "/AcclaimWeb/search/SearchTypeCaseNumber?Length=6", data=payload, hdrs=h)
    if not body or "Error.htm" in body:
        return []
    d = json.loads(req(BASE + "/AcclaimWeb/search/GridResults", data="page=1&size=200", hdrs=h))
    return d.get("data", [])


def extract_legal(rows):
    for r in rows:
        legal = r.get("DocLegalDescription") or ""
        m = LEGAL_RE_BLK.search(legal)
        if m:
            return "blk", m.group(1), m.group(2), m.group(3).zfill(4), m.group(4).zfill(4), legal
    for r in rows:
        legal = r.get("DocLegalDescription") or ""
        m = LEGAL_RE_NOBLK.search(legal)
        if m:
            return "noblk", m.group(1), None, m.group(2).zfill(4), m.group(3).zfill(4), legal
    return None


def gis_resolve(lot, blk, pb, pg):
    if blk:
        where = f"PLAT_BOOK='{pb}' AND PLAT_PAGE='{pg}' AND BLOCK='{blk}' AND LOT='{lot}'"
    else:
        where = f"PLAT_BOOK='{pb}' AND PLAT_PAGE='{pg}' AND LOT='{lot}'"
    params = {"where": where,
              "outFields": "TaxAcct,PARCEL_ID,STREET_NUMBER,STREET_NAME,STREET_TYPE,CITY,ZIP_CODE,LAND_VALUE,BLDG_VALUE",
              "returnGeometry": "true", "outSR": "4326", "f": "json"}
    url = GIS_QUERY + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        d = json.loads(resp.read().decode())
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
    street = " ".join(x for x in [a.get("STREET_NUMBER"), a.get("STREET_NAME"), a.get("STREET_TYPE")] if x).strip()
    city = (a.get("CITY") or "").strip()
    is_confidential = "CONFIDENTIAL" in (a.get("STREET_NAME") or "").upper()
    is_unknown = (a.get("STREET_NAME") or "").strip().upper() == "UNKNOWN" or not street
    addr = None
    if street and city and not is_confidential and not is_unknown:
        addr = f"{street}, {city}, FL {a.get('ZIP_CODE') or ''}".strip().rstrip(",")
    value = (a.get("LAND_VALUE") or 0) + (a.get("BLDG_VALUE") or 0)
    return {
        "parcel_id": a.get("PARCEL_ID"), "tax_account": str(a.get("TaxAcct")) if a.get("TaxAcct") is not None else None,
        "property_address": addr, "is_confidential": is_confidential, "is_unknown": is_unknown,
        "latitude": lat, "longitude": lon,
        "assessed_value": value if value else None,
    }, 1


def fetch_population(limit=None):
    url = (f"{SB_URL}/rest/v1/multi_county_auctions"
           "?select=id,case_number,parcel_id,property_address,data_source,source_platform"
           "&county=eq.brevard&parcel_id=is.null&data_source=is.null"
           "&or=(source_platform.eq.clerk_brevard,source_platform.is.null)"
           "&order=case_number")
    if limit:
        url += f"&limit={limit}"
    r = urllib.request.Request(url)
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())


def zone_linked(tax_account):
    if not tax_account:
        return False
    url = (f"{SB_URL}/rest/v1/v_zoning_gold_standard_card?select=tax_account"
           f"&county=eq.brevard&zone_code=not.is.null&tax_account=eq.{urllib.parse.quote(tax_account)}")
    r = urllib.request.Request(url)
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return len(json.loads(resp.read().decode())) > 0


def sb_patch(row_id, fields):
    body = json.dumps(fields).encode()
    r = urllib.request.Request(f"{SB_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}", data=body, method="PATCH")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    r.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.status


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write resolved rows live (default: dry-run, print only)")
    ap.add_argument("--include-confidential", action="store_true",
                     help="Also PATCH parcel_id/geo/value (never property_address) for address-confidentiality rows")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

    rows = fetch_population(args.limit)
    print(f"Population: {len(rows)} rows (county=brevard, parcel_id IS NULL, data_source IS NULL, "
          f"source_platform IN (clerk_brevard, NULL))")
    session_init()

    resolved, confidential_skipped, unknown_street, not_zone_linked, no_doc, no_legal, ambiguous, errors, applied = \
        0, 0, 0, 0, 0, 0, 0, 0, 0
    resolved_rows = []
    for i, row in enumerate(rows):
        cn = row["case_number"]
        try:
            docs = case_lookup(cn)
            if not docs:
                print(f"{cn}: no documents found")
                no_doc += 1
                continue
            legal = extract_legal(docs)
            if not legal:
                print(f"{cn}: no LOT/PB/PG parseable legal (condo/metes-and-bounds -- cannot verify)")
                no_legal += 1
                continue
            kind, lot, blk, pb, pg, raw_legal = legal
            gis, n = gis_resolve(lot, blk, pb, pg)
            if gis is None:
                print(f"{cn}: GIS ambiguous ({kind}) lot={lot} blk={blk} pb={pb} pg={pg} -> {n} features")
                ambiguous += 1
                continue
            if gis["is_unknown"]:
                print(f"{cn}: RESOLVED TaxAcct={gis['tax_account']} but STREET_NAME=UNKNOWN/blank "
                      f"(no situs address in county's own system of record) -- not fabricated, skipped")
                unknown_street += 1
                continue
            if gis["is_confidential"] and not args.include_confidential:
                print(f"{cn}: RESOLVED but address-confidentiality parcel (TaxAcct={gis['tax_account']}) "
                      f"-- skipped by default, rerun with --include-confidential to write parcel_id/geo/value only")
                confidential_skipped += 1
                continue
            zl = zone_linked(gis["tax_account"])
            resolved += 1
            print(f"{cn}: RESOLVED ({kind}) TaxAcct={gis['tax_account']} addr={gis['property_address']!r} "
                  f"zone_linked={zl} legal={raw_legal[:80]!r}")
            if not zl:
                not_zone_linked += 1
                print("   NOTE: will NOT flip card_complete alone (tax_account not in v_zoning_gold_standard_card)")
            patch = {"parcel_id": gis["tax_account"]}
            if gis["property_address"]:
                patch["property_address"] = gis["property_address"]
            if gis["latitude"] is not None:
                patch["latitude"] = gis["latitude"]
                patch["longitude"] = gis["longitude"]
            if gis["assessed_value"]:
                patch["assessed_value"] = gis["assessed_value"]
            resolved_rows.append({"case_number": cn, "id": row["id"], "patch": patch, "zone_linked": zl})
            if args.apply:
                status = sb_patch(row["id"], patch)
                print(f"   -> APPLIED PATCH status={status}")
                applied += 1
        except Exception as e:
            print(f"{cn}: ERROR {e}", file=sys.stderr)
            errors += 1
        if (i + 1) % 10 == 0:
            print(f"--- progress {i+1}/{len(rows)} resolved={resolved} unknown_street={unknown_street} "
                  f"confidential_skipped={confidential_skipped} no_legal={no_legal} ambiguous={ambiguous} "
                  f"errors={errors} applied={applied} ---")

    print(f"\nDONE: {len(rows)} rows -> resolved={resolved} (of which not_zone_linked={not_zone_linked}) "
          f"unknown_street={unknown_street} confidential_skipped={confidential_skipped} no_legal={no_legal} "
          f"ambiguous={ambiguous} no_doc={no_doc} errors={errors} applied={applied}")
    json.dump(resolved_rows, open("/tmp/brevard_clerk_platform_resolved.json", "w"), indent=2, default=str)
    if not args.apply and resolved:
        print(f"\nDRY-RUN: re-run with --apply to write the {resolved} resolved rows "
              f"({resolved - not_zone_linked} expected to flip card_complete fail->pass).")

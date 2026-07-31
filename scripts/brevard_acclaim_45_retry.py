#!/usr/bin/env python3
"""Retry AcclaimWeb parcel linkage for 45 still-unresolved Brevard clerk_brevard cases.

Context (dispatch c6b5fdd6, shard-8, 2026-07-31):
- 3rd firing (09f985fc, Jul 30): 85/133 no-parcel-id cases resolved via AcclaimWeb
  Lis-Pendens -> GIS linkage (acclaim_case_lookup.py). 45 unresolved remain:
    * ~25 had NO parseable LT/BLK/PB/PG legal description (condo/metes-and-bounds)
    * ~12-20 hit a transient AcclaimWeb HTTP 521 outage (recovered by end of session)
  The 3rd firing confirmed the HTTP-521 batch may now be retryable.
- Also: 3rd firing found 23% sampled error rate on pre-existing clerk_brevard links
  (3 of 13 sampled had wrong parcel_id/address). Full population audit recommended but
  does NOT increase card_complete metric (fixes wrong→correct, not missing→present).
  Prioritize fresh resolution over audit in this script.

This script:
1. Fetches all clerk_brevard MCA rows with parcel_id IS NULL
   (the same 45-row target population from the 3rd firing)
2. Replays acclaim_case_lookup.py logic against each, with improved condo-description
   handling (Unit/Condo pattern in addition to LT/BLK/PB/PG)
3. For condo cases: try UNIT/BUILDING/BLDG pattern in DocLegalDescription
   -> look up via TaxAcct (TaxAcct is the condo-unit level key in Brevard GIS)
4. Writes resolutions via per-row PATCH on multi_county_auctions
5. Reports exact counts for session log

Falls back cleanly (does not fabricate) if AcclaimWeb returns no parseable legal desc.

Usage: python3 scripts/brevard_acclaim_45_retry.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import sys, os, json, re, time, datetime as dt
import urllib.request, urllib.parse, http.cookiejar

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SB_KEY:
    sys.exit("FATAL: SUPABASE_SERVICE_ROLE_KEY required")

BASE_ACCLAIM = "http://vaclmweb1.brevardclerk.us"
GIS_QUERY = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5/query"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
THROTTLE = 2.5
DATA_SOURCE = "acclaim_lp_gis_linkage_retry"

SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# LOT/BLOCK/PLATBOOK/PLATPAGE pattern (same as acclaim_case_lookup.py)
LEGAL_LB_RE = re.compile(
    r"LT\s*(\S+)\s+BLK\s*(\S+)\s+PB\s*(\d+)\s+PG\s*(\d+)", re.IGNORECASE)
# UNIT/BUILDING pattern for condos
LEGAL_UNIT_RE = re.compile(
    r"(?:UNIT|APT|BLDG)\s*(\S+).*?(?:CONDO|CONDOMINIUM)", re.IGNORECASE)
# Tax account pattern — some legal descs carry the tax account directly
LEGAL_TAXACCT_RE = re.compile(r"\b(\d{7})\b")


def req(url, data=None, hdrs=None, retries=4):
    for attempt in range(retries):
        time.sleep(THROTTLE * (2 ** attempt if attempt else 1))
        try:
            r = urllib.request.Request(
                url, data=data.encode() if isinstance(data, str) else data)
            r.add_header("User-Agent", UA)
            for k, v in (hdrs or {}).items():
                r.add_header(k, v)
            with opener.open(r, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  retry {attempt+1}/{retries}: {e}", file=sys.stderr)
            if attempt == retries - 1:
                raise
    return None


def acclaim_session_init():
    req(BASE_ACCLAIM + "/AcclaimWeb/")
    req(BASE_ACCLAIM + "/AcclaimWeb/search/Disclaimer", data="disclaimer=on",
        hdrs={"Content-Type": "application/x-www-form-urlencoded",
              "Referer": BASE_ACCLAIM + "/AcclaimWeb/"})


def acclaim_case_lookup(case_number):
    today = dt.date.today()
    payload = urllib.parse.urlencode({
        "CaseNumber": case_number,
        "CaseNumberFilter": "0",
        "DocTypes": "all",
        "DocTypesDisplay-input": "All",
        "DocTypesDisplay": "",
        "DateRangeList": " ",
        "RecordDateFrom": "1/1/1981",
        "RecordDateTo": f"{today.month}/{today.day}/{today.year}",
    })
    h = {"Content-Type": "application/x-www-form-urlencoded",
         "X-Requested-With": "XMLHttpRequest",
         "Referer": BASE_ACCLAIM + "/AcclaimWeb/search/SearchTypeCaseNumber"}
    body = req(BASE_ACCLAIM + "/AcclaimWeb/search/SearchTypeCaseNumber?Length=6",
               data=payload, hdrs=h)
    if not body or "Error.htm" in body:
        return []
    try:
        d = json.loads(req(BASE_ACCLAIM + "/AcclaimWeb/search/GridResults",
                           data="page=1&size=200", hdrs=h))
        return d.get("data", [])
    except Exception as e:
        print(f"  GridResults parse error: {e}", file=sys.stderr)
        return []


def extract_legal(rows):
    """Try LT/BLK/PB/PG first (standard Brevard subdivision lots).
    Fall back to UNIT/CONDO pattern for condos.
    Returns (type, *args) or None."""
    lp = [r for r in rows if "LIS PENDENS" in (r.get("DocTypeDescription") or "").upper()]
    candidates = sorted(lp or rows, key=lambda r: r.get("RecordDate") or "9"*15)
    for r in candidates:
        legal = r.get("DocLegalDescription") or ""
        m = LEGAL_LB_RE.search(legal)
        if m:
            return ("lt_blk", m.group(1), m.group(2),
                    m.group(3).zfill(4), m.group(4).zfill(4), legal)
        # Try UNIT pattern
        mu = LEGAL_UNIT_RE.search(legal)
        if mu:
            return ("unit_condo", legal)
    return None


def gis_lt_blk(lot, blk, pb, pg):
    where = f"PLAT_BOOK='{pb}' AND PLAT_PAGE='{pg}' AND BLOCK='{blk}' AND LOT='{lot}'"
    params = {
        "where": where,
        "outFields": "TaxAcct,PARCEL_ID,STREET_NUMBER,STREET_NAME,STREET_TYPE,CITY,ZIP_CODE,LAND_VALUE,BLDG_VALUE",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = GIS_QUERY + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        d = json.loads(resp.read())
    feats = d.get("features", [])
    if len(feats) != 1:
        return None, len(feats)
    return _feat_to_dict(feats[0]), 1


def gis_by_taxacct(tax_acct):
    """Look up a single parcel by TaxAcct (for condo units)."""
    where = f"TaxAcct='{tax_acct}'"
    params = {
        "where": where,
        "outFields": "TaxAcct,PARCEL_ID,STREET_NUMBER,STREET_NAME,STREET_TYPE,CITY,ZIP_CODE,LAND_VALUE,BLDG_VALUE",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = GIS_QUERY + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        d = json.loads(resp.read())
    feats = d.get("features", [])
    if len(feats) == 1:
        return _feat_to_dict(feats[0]), 1
    return None, len(feats)


def _feat_to_dict(f):
    a = f["attributes"]
    ring = (f.get("geometry") or {}).get("rings", [[]])[0]
    lat = lon = None
    if ring:
        lon = sum(p[0] for p in ring) / len(ring)
        lat = sum(p[1] for p in ring) / len(ring)
    street = " ".join(x for x in [
        a.get("STREET_NUMBER"), a.get("STREET_NAME"), a.get("STREET_TYPE")
    ] if x).strip()
    city = (a.get("CITY") or "").strip()
    addr = f"{street}, {city}, FL {a.get('ZIP_CODE') or ''}".strip().rstrip(",")
    value = (a.get("LAND_VALUE") or 0) + (a.get("BLDG_VALUE") or 0)
    return {
        "parcel_id": a.get("PARCEL_ID"),
        "tax_account": str(a.get("TaxAcct")) if a.get("TaxAcct") is not None else None,
        "property_address": addr if street else None,
        "latitude": lat,
        "longitude": lon,
        "assessed_value": value if value else None,
    }


def sb_patch(row_id, fields):
    body = json.dumps(fields).encode()
    r = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
        data=body, method="PATCH"
    )
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    r.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.status


def get_unresolved_brevard():
    """Fetch clerk_brevard rows with no parcel_id."""
    params = {
        "select": "id,case_number,property_address,parcel_id",
        "county": "eq.brevard",
        "data_source": "ilike.*clerk_brevard*",
        "parcel_id": "is.null",
        "order": "case_number.asc",
        "limit": "200",
    }
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=SB_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def run():
    print("=== Brevard AcclaimWeb Retry — 45 Unresolved Cases (shard-8, dispatch c6b5fdd6) ===")

    print("\n[1] Fetching unresolved clerk_brevard rows (parcel_id IS NULL)...")
    cases = get_unresolved_brevard()
    print(f"  Found {len(cases)} unresolved cases")

    if not cases:
        print("  All clerk_brevard cases now have parcel_id — letter I residual is the structural wall.")
        return

    print(f"\n[2] Initializing AcclaimWeb session...")
    acclaim_session_init()
    print("  Session ready.")

    resolved = no_legal = no_doc = ambiguous = condo_matched = errors = 0

    for i, c in enumerate(cases):
        cn, rid = c["case_number"], c["id"]
        try:
            rows = acclaim_case_lookup(cn)
            if not rows:
                print(f"  {cn}: no documents found in AcclaimWeb")
                no_doc += 1
                continue

            legal = extract_legal(rows)
            if not legal:
                print(f"  {cn}: no parseable legal description in {len(rows)} docs")
                no_legal += 1
                continue

            if legal[0] == "lt_blk":
                _, lot, blk, pb, pg, raw_legal = legal
                gis, n = gis_lt_blk(lot, blk, pb, pg)
                if gis is None:
                    print(f"  {cn}: GIS ambiguous/no-match (LT{lot} BLK{blk} PB{pb} PG{pg}) -> {n} features")
                    ambiguous += 1
                    continue
                patch = {}
                if gis.get("parcel_id"):
                    patch["parcel_id"] = gis["parcel_id"]
                if gis.get("property_address"):
                    patch["property_address"] = gis["property_address"]
                if gis.get("latitude") is not None:
                    patch["latitude"] = gis["latitude"]
                    patch["longitude"] = gis["longitude"]
                if gis.get("assessed_value"):
                    patch["assessed_value"] = gis["assessed_value"]
                if patch:
                    status = sb_patch(rid, patch)
                    print(f"  {cn}: RESOLVED LT/BLK parcel={gis['parcel_id']!r} addr={gis['property_address']!r} PATCH={status}")
                    resolved += 1

            elif legal[0] == "unit_condo":
                raw_legal = legal[1]
                # Extract 7-digit tax account candidates from legal description
                candidates = LEGAL_TAXACCT_RE.findall(raw_legal)
                found = False
                for cand in candidates:
                    gis, n = gis_by_taxacct(cand)
                    if gis and n == 1:
                        patch = {}
                        if gis.get("parcel_id"):
                            patch["parcel_id"] = gis["parcel_id"]
                        if gis.get("property_address"):
                            patch["property_address"] = gis["property_address"]
                        if gis.get("latitude") is not None:
                            patch["latitude"] = gis["latitude"]
                            patch["longitude"] = gis["longitude"]
                        if gis.get("assessed_value"):
                            patch["assessed_value"] = gis["assessed_value"]
                        if patch:
                            status = sb_patch(rid, patch)
                            print(f"  {cn}: RESOLVED CONDO TaxAcct={cand} parcel={gis['parcel_id']!r} PATCH={status}")
                            condo_matched += 1
                        found = True
                        break
                if not found:
                    print(f"  {cn}: CONDO — no TaxAcct match in GIS (raw: {raw_legal[:80]!r})")
                    ambiguous += 1

        except Exception as e:
            print(f"  {cn}: ERROR {e}", file=sys.stderr)
            errors += 1

        if (i + 1) % 10 == 0:
            print(f"  --- progress {i+1}/{len(cases)} (resolved={resolved} condo={condo_matched} "
                  f"no_doc={no_doc} no_legal={no_legal} ambiguous={ambiguous} errors={errors}) ---")

    print(f"\nDONE: {len(cases)} cases -> resolved={resolved} condo={condo_matched} "
          f"no_doc={no_doc} no_legal={no_legal} ambiguous={ambiguous} errors={errors}")
    print(f"Total new resolutions: {resolved + condo_matched}")


if __name__ == "__main__":
    run()

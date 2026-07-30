#!/usr/bin/env python3
"""Brevard AcclaimWeb case-number -> parcel linkage for PRE-SALE (scheduled)
foreclosures that have no parcel_id at all (source_platform=clerk_brevard,
courthouse-calendar-only rows: case_number + auction_date, nothing else).

Diagnosed 2026-07-30 (dispatch 09f985fc, 3rd firing) via a live ULTRALOOP
research pass: AcclaimWeb's "Case Number" search returns the case's Lis
Pendens (filed at case START, well before any sale/CT), whose
DocLegalDescription carries a Lot/Block/Plat-Book/Plat-Page legal description.
That legal description resolves uniquely against Brevard's own public GIS
parcel layer (gis.brevardfl.gov -- NOT bcpao.us, which is Cloudflare-gated
and independently reconfirmed dead this session) via
PLAT_BOOK+PLAT_PAGE+BLOCK+LOT, which also yields the real site address,
land+building value, and parcel polygon (we derive centroid lat/lon from the
ring vertices ourselves -- this is the resolved parcel's OWN geometry, not a
reverse-geocode of an arbitrary point, so it does not repeat the
nearest-neighbor mistake flagged in the prior session's report).

Session-cookie flow (same scaffolding as scripts/acclaim_ct_sweep.py):
  GET  /AcclaimWeb/                                    -> session cookie
  POST /AcclaimWeb/search/Disclaimer  disclaimer=on    -> accept
  POST /AcclaimWeb/search/SearchTypeCaseNumber?Length=6 -> criteria in session
       CaseNumber=<case>, DocTypes=all (literal lowercase -- required, see
       report), DateRangeList=" ", RecordDateFrom=1/1/1981, RecordDateTo=today
  POST /AcclaimWeb/search/GridResults page=1&size=200  -> {"data":[...],"total":N}

Hard rules (same as acclaim_ct_sweep.py): single session, ~2.5s throttle,
exponential backoff, never rotate IPs, never parallelize -- this is a shared
production court records site.

Writes multi_county_auctions per-row via scoped PATCH (?id=eq.<uuid>), never
bulk upsert-by-id -- PostgREST's ON CONFLICT validates the full INSERT
payload against NOT NULL columns even on the UPDATE branch, which broke bulk
upsert against this table in the prior session.

Usage: acclaim_case_lookup.py cases.json   (cases.json = [{"id":..,"case_number":..}, ...])
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
import sys, os, json, re, time, datetime as dt
import urllib.request, urllib.parse, http.cookiejar

BASE = "http://vaclmweb1.brevardclerk.us"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
THROTTLE = 2.5
GIS_QUERY = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5/query"
DATA_SOURCE = "acclaim_lp_gis_linkage"

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

LEGAL_RE = re.compile(
    r"LT\s*(\S+)\s+BLK\s*(\S+)\s+PB\s*(\d+)\s+PG\s*(\d+)", re.IGNORECASE)

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
        hdrs={"Content-Type": "application/x-www-form-urlencoded",
              "Referer": BASE + "/AcclaimWeb/"})

def case_lookup(case_number):
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
         "Referer": BASE + "/AcclaimWeb/search/SearchTypeCaseNumber"}
    body = req(BASE + "/AcclaimWeb/search/SearchTypeCaseNumber?Length=6", data=payload, hdrs=h)
    if not body or "Error.htm" in body:
        return []
    d = json.loads(req(BASE + "/AcclaimWeb/search/GridResults", data="page=1&size=200", hdrs=h))
    return d.get("data", [])

def extract_legal(rows):
    """Prefer the LIS PENDENS row (earliest doc, pre-sale); fall back to any row with a legal desc."""
    lp = [r for r in rows if "LIS PENDENS" in (r.get("DocTypeDescription") or "").upper()]
    candidates = lp or rows
    candidates = sorted(candidates, key=lambda r: r.get("RecordDate") or "9" * 15)
    for r in candidates:
        legal = r.get("DocLegalDescription") or ""
        m = LEGAL_RE.search(legal)
        if m:
            return m.group(1), m.group(2), m.group(3).zfill(4), m.group(4).zfill(4), legal
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
    addr = f"{street}, {city}, FL {a.get('ZIP_CODE') or ''}".strip().rstrip(",")
    value = (a.get("LAND_VALUE") or 0) + (a.get("BLDG_VALUE") or 0)
    return {
        "parcel_id": a.get("PARCEL_ID"),
        "tax_account": str(a.get("TaxAcct")) if a.get("TaxAcct") is not None else None,
        "property_address": addr if street else None,
        "latitude": lat, "longitude": lon,
        "assessed_value": value if value else None,
    }, 1

def sb_patch(row_id, fields):
    body = json.dumps(fields).encode()
    r = urllib.request.Request(
        f"{SB_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
        data=body, method="PATCH")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    r.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.status

if __name__ == "__main__":
    cases = json.load(open(sys.argv[1]))
    session_init()
    resolved, no_legal, ambiguous, no_doc, errors = 0, 0, 0, 0, 0
    for i, c in enumerate(cases):
        cn, rid = c["case_number"], c["id"]
        try:
            rows = case_lookup(cn)
            if not rows:
                print(f"{cn}: no documents found")
                no_doc += 1
                continue
            legal = extract_legal(rows)
            if not legal:
                print(f"{cn}: no LOT/BLK/PB/PG in any legal description ({len(rows)} docs)")
                no_legal += 1
                continue
            lot, blk, pb, pg, raw_legal = legal
            gis, n = gis_resolve(lot, blk, pb, pg)
            if gis is None:
                print(f"{cn}: GIS lookup ambiguous/no-match (LT{lot} BLK{blk} PB{pb} PG{pg}) -> {n} features")
                ambiguous += 1
                continue
            patch = {
                "parcel_id": gis["parcel_id"],
                "data_source_i_backfill": DATA_SOURCE,
            }
            if gis["property_address"]:
                patch["property_address"] = gis["property_address"]
            if gis["latitude"] is not None:
                patch["latitude"] = gis["latitude"]
                patch["longitude"] = gis["longitude"]
            if gis["assessed_value"]:
                patch["assessed_value"] = gis["assessed_value"]
            status = sb_patch(rid, {k: v for k, v in patch.items() if k != "data_source_i_backfill"})
            print(f"{cn}: RESOLVED parcel_id={gis['parcel_id']} addr={gis['property_address']!r} "
                  f"(legal={raw_legal[:60]!r}) PATCH status={status}")
            resolved += 1
        except Exception as e:
            print(f"{cn}: ERROR {e}", file=sys.stderr)
            errors += 1
        if (i + 1) % 10 == 0:
            print(f"--- progress {i+1}/{len(cases)} (resolved={resolved} no_doc={no_doc} "
                  f"no_legal={no_legal} ambiguous={ambiguous} errors={errors}) ---")

    print(f"\nDONE: {len(cases)} cases -> resolved={resolved} no_doc={no_doc} "
          f"no_legal={no_legal} ambiguous={ambiguous} errors={errors}")

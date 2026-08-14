#!/usr/bin/env python3
"""Brevard I: backfill the 38-row brevard_clerk / parcel_id IS NULL population
via a regex fix to the existing AcclaimWeb legal-description extractor.

ORIGIN (dispatch 7bcb4434, this session): the sibling script
scripts/brevard_clerk_link_integrity_audit_7bcb4434.py audits a DIFFERENT,
already-parcel_id-linked 124-row population (data_source IN brevard_clerk/
brevard_clerk_scraper AND parcel_id IS NOT NULL) for wrong-property links --
that lever does NOT move card_complete (a wrong-but-complete card is replaced
with a correct-but-still-complete card).

THIS script targets a genuinely different, previously-unaudited population:
  data_source = 'brevard_clerk' AND parcel_id IS NULL   (38 rows live,
  confirmed via PostgREST 2026-08-14)
These rows are missing property_address/parcel_id/geo/value entirely and are
counted in the I-gate failure bucket. All 38 fail today's I-gate.

ROOT CAUSE FOUND (live, this session): the sibling script's LEGAL_RE regex
`LT\\s*(\\S+)\\s+BLK\\s*(\\S+)\\s+PB\\s*(\\d+)\\s+PG\\s*(\\d+)` hard-requires a
"BLK <n>" token. Many Brevard subdivisions plat lots directly under a unit
with NO block segment at all, e.g. case 05-2025-CA-032554-XXCA-BC's LIS
PENDENS legal is literally `LT 5 PB 27 PG 35 U E  MEADOWS SEC 1, THE ...`
-- no BLK token anywhere in ANY doc type for that case, so the sibling
script's extractor returns None and the row is permanently skipped as
"no_legal", even though the county's own GIS layer resolves this exact
LOT+PLAT_BOOK+PLAT_PAGE (no BLOCK filter) to exactly ONE feature:
TaxAcct=2211596, "1110 CHENEY HWY, TITUSVILLE, FL 32780" (BLOCK='*' in the
live layer -- i.e. the county's own data literally has no block for this
parcel, confirming the legal description is not malformed, the regex is).

LIVE RESULT this session (dry-run diagnosis only, method identical to
sibling script Sections 1-4, extended with a no-BLK fallback pattern -- see
FIX below): ran against all 38 rows.
  blk_match_resolved   = 0
  noblk_match_resolved = 24   (24/38 = 63%)
  no_legal              = 12  (metes-and-bounds or condo/timeshare unit
                                descriptions -- genuinely unparseable by this
                                method, correctly excluded, NOT fabricated)
  ambiguous              = 2  (0 or >1 GIS features -- correctly skipped)
  no_doc                 = 0
Of the 24 noblk-resolved:
  - 1 (case 05-2025-CC-051498-XXCC-BC, TaxAcct=2460880) is an ADDRESS
    CONFIDENTIALITY PROGRAM parcel -- GIS STREET_NAME literally returns the
    string "CONFIDENTIAL" with blank STREET_NUMBER/CITY. Do NOT write this
    as property_address (not a real usable address -- would be a Honesty
    Protocol violation to present "CONFIDENTIAL, FL" as a card-complete
    address). Excluded from APPLY. parcel_id/assessed_value/geo MAY still be
    written for this row if desired -- left OUT of this script's default
    scope to keep the fix mechanically simple (address-confidentiality rows
    need a human policy call, not a script default).
  - 1 (case 05-2025-CA-063757-XXCA-BC, TaxAcct=2423749) resolves a valid
    address/geo/value but its TaxAcct is NOT present in
    v_zoning_gold_standard_card with zone_code IS NOT NULL (confirmed live
    via tax_account=in.() lookup) -- writing this row alone would NOT flip
    it to card_complete (zone-link gate still fails). Still safe/correct to
    write (real, GIS-verified, non-fabricated data) but will not move the I
    metric on its own.
  - 22 remaining rows: real address + real geo + real value (LAND_VALUE+
    BLDG_VALUE) + CONFIRMED already zone-linked (tax_account IN
    v_zoning_gold_standard_card WHERE county=brevard AND zone_code IS NOT
    NULL). These 22 will flip fail->pass on the I gate when written.

EXPECTED I-METRIC IMPACT (computed, not yet applied): card_complete
6121 -> 6143 of 7250 = 84.43% -> 84.73% (+0.30pp). Does NOT reach the 95%
pass threshold alone -- this is one incremental, honest lever among several
needed, not a full fix. The remaining ~990 zero-address rows (BCPAO 403 /
Firecrawl exhausted, reconfirmed live this session) and the 6
retired/unresolvable numeric-case TaxAcct rows are OUT OF SCOPE here (see
this session's report for detail).

FIX (vs sibling script): extend_legal() below tries the original
LT+BLK+PB+PG pattern FIRST (higher precision, matches sibling script
exactly), then falls back to LT+PB+PG (no BLK) ONLY if the first fails on
every doc for that case. GIS query correspondingly omits the BLOCK clause
when blk is None. Everything else (single-feature-match gate, confidential-
address guard, PATCH scoping) is new to this script -- the sibling script's
population (parcel_id NOT NULL) never needs these because it always has an
existing address to compare against.

Usage:
  python3 scripts/brevard_i_clerk_noblk_legal_backfill_7bcb4434.py             # dry-run (default)
  python3 scripts/brevard_i_clerk_noblk_legal_backfill_7bcb4434.py --apply     # write resolved rows live
  python3 scripts/brevard_i_clerk_noblk_legal_backfill_7bcb4434.py --apply --include-confidential
                                                                                # also PATCH parcel_id/geo/value
                                                                                # (never property_address) for the
                                                                                # 1 confidential-address row

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
dispatch_id: 7bcb4434-c068-4a5d-b140-0dcf65c8c87f (brevard-I gold-standard session)
"""
import sys, os, json, re, time, datetime as dt, argparse
import urllib.request, urllib.parse, http.cookiejar

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
    """BLK pattern first (precise), then no-BLK fallback across ALL doc types."""
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
    addr = None
    if street and city and not is_confidential:
        addr = f"{street}, {city}, FL {a.get('ZIP_CODE') or ''}".strip().rstrip(",")
    value = (a.get("LAND_VALUE") or 0) + (a.get("BLDG_VALUE") or 0)
    return {
        "parcel_id": a.get("PARCEL_ID"), "tax_account": str(a.get("TaxAcct")) if a.get("TaxAcct") is not None else None,
        "property_address": addr, "is_confidential": is_confidential,
        "latitude": lat, "longitude": lon,
        "assessed_value": value if value else None,
    }, 1


def fetch_population(limit=None):
    url = (f"{SB_URL}/rest/v1/multi_county_auctions"
           "?select=id,case_number,parcel_id,property_address,data_source"
           "&county=eq.brevard&data_source=eq.brevard_clerk&parcel_id=is.null"
           "&order=case_number")
    if limit:
        url += f"&limit={limit}"
    r = urllib.request.Request(url)
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())


def zone_linked(tax_account):
    """Confirm tax_account resolves in v_zoning_gold_standard_card (zone_code NOT NULL) for brevard."""
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
                     help="Also PATCH parcel_id/geo/value (never property_address) for the address-confidentiality row")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

    rows = fetch_population(args.limit)
    print(f"Population: {len(rows)} rows (county=brevard, data_source=brevard_clerk, parcel_id IS NULL)")
    session_init()

    resolved, confidential_skipped, not_zone_linked, no_legal, ambiguous, errors, applied = 0, 0, 0, 0, 0, 0, 0
    for i, row in enumerate(rows):
        cn = row["case_number"]
        try:
            docs = case_lookup(cn)
            if not docs:
                print(f"{cn}: no documents found")
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
            if args.apply:
                patch = {"parcel_id": gis["tax_account"]}
                if gis["property_address"]:
                    patch["property_address"] = gis["property_address"]
                if gis["latitude"] is not None:
                    patch["latitude"] = gis["latitude"]
                    patch["longitude"] = gis["longitude"]
                if gis["assessed_value"]:
                    patch["assessed_value"] = gis["assessed_value"]
                status = sb_patch(row["id"], patch)
                print(f"   -> APPLIED PATCH status={status}")
                applied += 1
        except Exception as e:
            print(f"{cn}: ERROR {e}", file=sys.stderr)
            errors += 1
        if (i + 1) % 10 == 0:
            print(f"--- progress {i+1}/{len(rows)} resolved={resolved} confidential_skipped={confidential_skipped} "
                  f"no_legal={no_legal} ambiguous={ambiguous} errors={errors} applied={applied} ---")

    print(f"\nDONE: {len(rows)} rows -> resolved={resolved} (of which not_zone_linked={not_zone_linked}) "
          f"confidential_skipped={confidential_skipped} no_legal={no_legal} ambiguous={ambiguous} "
          f"errors={errors} applied={applied}")
    if not args.apply and resolved:
        print(f"\nDRY-RUN: re-run with --apply to write the {resolved} resolved rows "
              f"({resolved - not_zone_linked} expected to flip card_complete fail->pass).")

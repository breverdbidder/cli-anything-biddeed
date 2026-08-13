#!/usr/bin/env python3
"""Brevard clerk_brevard-sourced parcel_id link integrity audit + fix.

Origin: 3rd-firing session on dispatch 09f985fc (2026-07-30) flagged this as
the top residual: a routine adversarial spot-check found 3 of 13 sampled
PRE-EXISTING (not that session's own writes) clerk_brevard/brevard_clerk_scraper
parcel_id links pointed at the WRONG property for a live, currently-scheduled
foreclosure case (real risk of a bidder relying on the wrong address). This
session (dispatch 7bcb4434) re-verified the lever live on a fresh 20-row
random sample (seed=42) and CONFIRMED it is real and current: 15/20 confirmed
correct, 2/20 REFUTED (both independently double-checked against the case's
own Lis Pendens/Judgment/Certificate-of-Title legal description via a second,
manual AcclaimWeb query -- not a script artifact), 3/20 had no LOT/BLK/PB/PG-
parseable legal description (can't verify with this method, excluded from the
error-rate denominator). Verifiable error rate this session: 2/17 = 11.8%.
Both confirmed-wrong rows were fixed live this session:
  - case 05-2023-CA-058831-XXXX-XX (id=70060b0b-5e1b-4e1e-81a0-8f7ce997ff4e):
    was "5510 PACE'S LANDING RD, MIMS" -> corrected to
    "1490 SHEAFE AVE, PALM BAY, FL 32905" (parcel_id 28 3720-75-92-19,
    TaxAcct 2829582), matching the case's own Lis Pendens/Judgment/CT legal
    "LT 19 BLK 92 PB 28 PG 23 PORT MALABAR COUNTRY CLUB UNIT 7".
  - case 05-2025-CA-064556-XXCA-BC (id=25ecc8d2-a32d-4e7f-9c16-79b018369e4e):
    was "147 OXFORD CT, INDIALANTIC" -> corrected to
    "204 CHERRY DR, MELBOURNE BEACH, FL 32951" (parcel_id 28 3808-51-F-11,
    TaxAcct 2848418), matching the case's own Lis Pendens/Judgment legal
    "LT 11 BLK F PB 19 PG 53 MELBOURNE BEACH SOUTH".

NOTE ON METRIC IMPACT: this lever does NOT move the I card-completeness
percentage -- every row in this population already has a complete card (one
wrong-but-complete card is replaced with one correct-and-complete card), same
as the 3rd firing's finding. Value is data-integrity / bidder-safety on live
auctions, not I-metric coverage. Do not expect card_complete to change after
running the full sweep; a stable card_complete count post-sweep is the
correct, expected outcome, not a sign the script did nothing.

RESIDUAL FOR NEXT SESSION: full population is 124 rows (data_source IN
('brevard_clerk','brevard_clerk_scraper') AND parcel_id IS NOT NULL). Only
20 have been sampled across the two sessions combined (13 in the 3rd firing +
20 here, likely some overlap since both were random draws from the same
124-row population without exclusion tracking -- dedupe by case_number before
resuming). At an ~11-23% error rate, extrapolated ~14-28 further wrong rows
plausibly remain in the ~104 unaudited rows. Recommended: run this script in
--dry-run (verify-only, default) first across the FULL 124-row population to
get an exact count, THEN re-run with --apply to fix only the confirmed-wrong
ones. Budget: ~2.5s x 2 requests/case x 124 cases ~= 10-11 minutes single-
threaded (AcclaimWeb hard rule: single session, no parallelization, no IP
rotation -- shared production court-records site).

Method (identical to scripts/acclaim_case_lookup.py, read-only until --apply):
  1. AcclaimWeb Case Number search -> Lis Pendens (fallback: any doc with a
     legal description) -> DocLegalDescription
  2. Parse LT <lot> BLK <blk> PB <pb> PG <pg> (only pattern supported; condo/
     metes-and-bounds legal descriptions are skipped as no_legal, NOT treated
     as confirmed -- do not assume no_legal rows are correct)
  3. Resolve PLAT_BOOK+PLAT_PAGE+BLOCK+LOT against gis.brevardfl.gov
     (Base_Map/Parcel_New_WKID2881/MapServer/5) -- must return exactly 1
     feature or the row is "ambiguous" (skip, do not write)
  4. Compare stored parcel_id/tax_account and stored city against the GIS
     resolution's parcel_id/tax_account/city. CONFIRMED if either the
     parcel_id (or tax_account) matches OR the city matches (case-insensitive,
     to tolerate address-format differences that aren't a wrong-property
     bug); otherwise REFUTED.
  5. --apply mode only: PATCH the REFUTED row's parcel_id, property_address,
     latitude/longitude (ring centroid of GIS geometry), assessed_value
     (LAND_VALUE+BLDG_VALUE) via scoped id=eq.<uuid> PATCH. Never bulk-upsert
     (breaks NOT NULL validation on this table per prior sessions' notes).
  6. Log every REFUTED finding (before/after) to stdout for the session
     report's SQL VERIFICATION section -- these are Honesty-Protocol-grade
     data corrections and must be individually auditable.

Usage:
  python3 scripts/brevard_clerk_link_integrity_audit_7bcb4434.py            # dry-run, full 124-row population
  python3 scripts/brevard_clerk_link_integrity_audit_7bcb4434.py --apply    # fix confirmed-wrong rows live
  python3 scripts/brevard_clerk_link_integrity_audit_7bcb4434.py --limit 30 # smaller batch (rate-limit budget)

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

LEGAL_RE = re.compile(r"LT\s*(\S+)\s+BLK\s*(\S+)\s+PB\s*(\d+)\s+PG\s*(\d+)", re.IGNORECASE)


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
    addr = f"{street}, {city}, FL {a.get('ZIP_CODE') or ''}".strip().rstrip(",")
    value = (a.get("LAND_VALUE") or 0) + (a.get("BLDG_VALUE") or 0)
    return {
        "parcel_id": a.get("PARCEL_ID"), "tax_account": str(a.get("TaxAcct")) if a.get("TaxAcct") is not None else None,
        "property_address": addr if street else None, "latitude": lat, "longitude": lon,
        "assessed_value": value if value else None,
    }, 1


def norm_city(addr):
    m = re.search(r",\s*([A-Za-z .]+),\s*FL", addr or "")
    return (m.group(1).strip().upper() if m else "")


def fetch_population(limit=None):
    url = (f"{SB_URL}/rest/v1/multi_county_auctions"
           "?select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,data_source"
           "&county=eq.brevard&data_source=in.(brevard_clerk,brevard_clerk_scraper)&parcel_id=not.is.null"
           "&order=case_number")
    if limit:
        url += f"&limit={limit}"
    r = urllib.request.Request(url)
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())


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
    ap.add_argument("--apply", action="store_true", help="Write fixes for REFUTED rows (default: dry-run, print only)")
    ap.add_argument("--limit", type=int, default=None, help="Cap population size (rate-limit budget)")
    args = ap.parse_args()

    assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

    rows = fetch_population(args.limit)
    print(f"Population: {len(rows)} rows (data_source IN brevard_clerk/brevard_clerk_scraper, parcel_id IS NOT NULL)")
    session_init()

    confirmed, refuted, fixed, no_doc, no_legal, ambiguous, errors = 0, 0, 0, 0, 0, 0, 0
    refuted_rows = []
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
                print(f"{cn}: no LOT/BLK/PB/PG parseable legal (cannot verify with this method)")
                no_legal += 1
                continue
            lot, blk, pb, pg, raw_legal = legal
            gis, n = gis_resolve(lot, blk, pb, pg)
            if gis is None:
                print(f"{cn}: GIS ambiguous/no-match -> {n} features")
                ambiguous += 1
                continue
            stored_city = norm_city(row.get("property_address"))
            gis_city = norm_city(gis.get("property_address"))
            match_pid = (row.get("parcel_id") == gis.get("parcel_id")) or (row.get("parcel_id") == gis.get("tax_account"))
            match_city = bool(stored_city) and bool(gis_city) and stored_city == gis_city
            ok = match_pid or match_city
            if ok:
                confirmed += 1
                print(f"{cn}: CONFIRMED")
                continue
            refuted += 1
            print(f"{cn}: REFUTED id={row['id']} stored_pid={row.get('parcel_id')!r} stored_addr={row.get('property_address')!r} "
                  f"| gis_pid={gis.get('parcel_id')!r} gis_tax={gis.get('tax_account')!r} gis_addr={gis.get('property_address')!r} "
                  f"legal={raw_legal[:80]!r}")
            refuted_rows.append({"case_number": cn, "id": row["id"], "before": row, "after_gis": gis})
            if args.apply:
                patch = {"parcel_id": gis["parcel_id"]}
                if gis["property_address"]:
                    patch["property_address"] = gis["property_address"]
                if gis["latitude"] is not None:
                    patch["latitude"] = gis["latitude"]
                    patch["longitude"] = gis["longitude"]
                if gis["assessed_value"]:
                    patch["assessed_value"] = gis["assessed_value"]
                status = sb_patch(row["id"], patch)
                print(f"  -> APPLIED PATCH status={status}")
                fixed += 1
        except Exception as e:
            print(f"{cn}: ERROR {e}", file=sys.stderr)
            errors += 1
        if (i + 1) % 10 == 0:
            print(f"--- progress {i+1}/{len(rows)} confirmed={confirmed} refuted={refuted} fixed={fixed} "
                  f"no_doc={no_doc} no_legal={no_legal} ambiguous={ambiguous} errors={errors} ---")

    verifiable = confirmed + refuted
    err_rate = (100.0 * refuted / verifiable) if verifiable else 0.0
    print(f"\nDONE: {len(rows)} rows -> confirmed={confirmed} refuted={refuted} fixed={fixed} "
          f"no_doc={no_doc} no_legal={no_legal} ambiguous={ambiguous} errors={errors}")
    print(f"Verifiable error rate: {refuted}/{verifiable} = {err_rate:.1f}%")
    json.dump(refuted_rows, open("/tmp/brevard_link_audit_refuted.json", "w"), indent=2, default=str)
    if not args.apply and refuted_rows:
        print(f"\nDRY-RUN: {len(refuted_rows)} REFUTED rows written to /tmp/brevard_link_audit_refuted.json. "
              f"Re-run with --apply to fix.")

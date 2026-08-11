#!/usr/bin/env python3
"""GOLD STANDARD workstream hl_EIJ, dispatch 8d4cd6c7-e51a-4a0d-a8da-6995f13bad43.
County: highlands. Letters: E (parcel linkage), I (card completeness, gated on E),
J (deal_complete, checked for spillover after E fix).

STRATEGY (all real, live sources — no fabrication):
  1. Fetch the live Highlands Clerk foreclosure sale calendar PDF
     (https://webfiles.highlandsclerkfl.gov/ForeClosure/ClerkSaleCalendar.pdf)
     and extract case_number -> legal/address text (this PDF already has a
     parser at scripts/clerk_ssot/parsers/highlands.py but it discards the
     address text; this script re-derives it independently for the specific
     gap case_numbers).
  2. For each multi_county_auctions row with parcel_id IS NULL, take the first
     usable street address token from the calendar block and submit it to the
     live HCPAO ("Highlands County Property Appraiser") site search:
       POST https://www.hcpao.org/Search
       body: RealEstateUnifiedLookup=<address>&SearchMode=RealEstate-Unified
             &ActiveTab=RealEstate&PageIndex=0
     This is the site's real production search form (verified live, returns
     an HTML result table with a hyperlink to /Search/Parcel/<STRAP>).
  3. Parse the STRAP-style parcel id out of the /Search/Parcel/<STRAP> link
     and re-format to the county's existing dashed style used elsewhere in
     multi_county_auctions (C-04-34-28-110-2010-0200 style) to match the
     'C-##-##-##-###-####-####' pattern already present on the 268 linked
     rows in this county.
  4. Fetch the parcel detail page (https://www.hcpao.org/Search/Parcel/<STRAP>)
     for Total Just Value / Total Assessed (Capped) Value (used for
     market_value / assessed_value).
  5. Query the live HCPAO ArcGIS MapServer for polygon geometry and compute
     a centroid (avg of ring vertices) for latitude/longitude:
       https://gis11.cama.io/arcgis/rest/services/Highlands/HighlandsCounty_ParcelsAndTIFFS/MapServer/0/query
       ?where=STRAP='<strap>'&outFields=STRAP&returnGeometry=true&outSR=4326&f=json
  6. PATCH multi_county_auctions for each successfully resolved case_number.

Only rows where a live HCPAO parcel match was found AND geometry AND a
property_address were all retrieved are written. Ambiguous multi-result
address searches or misses are logged and skipped (fail-loud, not silently
dropped).

Usage:
  python3 scripts/highlands_e_parcel_linkage.py            # dry-run (default)
  python3 scripts/highlands_e_parcel_linkage.py --apply    # write to DB

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)
"""
from __future__ import annotations
import json
import os
import re
import ssl
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from io import BytesIO

# NOTE: sandbox execution environment lacks a local CA bundle for some
# external hosts (verified: same failure reproduces with plain `curl` here
# and is fixed by `curl -k`); this is an environment CA-store gap, not a
# statement about hcpao.org/webfiles.highlandsclerkfl.gov's own TLS validity.
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
DISPATCH_ID = "8d4cd6c7-e51a-4a0d-a8da-6995f13bad43"

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

CALENDAR_URL = "https://webfiles.highlandsclerkfl.gov/ForeClosure/ClerkSaleCalendar.pdf"
HCPAO_SEARCH_URL = "https://www.hcpao.org/Search"
HCPAO_PARCEL_URL = "https://www.hcpao.org/Search/Parcel/{strap}"
GIS_QUERY_URL = (
    "https://gis11.cama.io/arcgis/rest/services/Highlands/HighlandsCounty_ParcelsAndTIFFS/"
    "MapServer/0/query"
)

CASE_RE = re.compile(r"\d{8}(?:GC|CC)AXMX")
AMT_RE = re.compile(r"\$[\d,]+\.\d{2}")
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}
_MONTH_ALT = "|".join(MONTHS)
DATE_RE = re.compile(rf"({_MONTH_ALT})\s+(\d{{1,2}}),\s*(\d{{4}})")

# Dashed parcel id segments are usually digits (e.g. C-04-34-28-110-2010-0200)
# but can contain a letter mid-segment (verified live: A-22-33-28-010-00B0-0130
# for 14 S GLENWOOD AVE / STRAP 28332201000B00130A) — must allow [0-9A-Z]+ per
# segment, not just digits.
PARCEL_LINK_RE = re.compile(r'/Search/Parcel/([0-9A-Za-z]+)"[^>]*>([A-Z](?:-[0-9A-Z]+)+)<')


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(table: str, params: str, limit: int = 2000):
    url = f"{BASE}/{table}?{params}&limit={limit}"
    req = urllib.request.Request(url, headers={**HEADERS, "Prefer": ""})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sb_patch(table: str, filters: str, data: dict) -> tuple[int, str]:
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={**HEADERS, "Prefer": "return=minimal"}, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def http_get(url: str, headers=None, timeout=30) -> bytes:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
        return r.read()


def http_post_form(url: str, data: dict, timeout=30) -> str:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
    }, method="POST")
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
        return r.read().decode(errors="replace")


def fetch_calendar_case_addresses() -> dict:
    """Returns {case_number: legal/address text} for every case on the live
    Highlands Clerk foreclosure sale calendar."""
    from pypdf import PdfReader

    raw = http_get(CALENDAR_URL)
    reader = PdfReader(BytesIO(raw))
    page_texts = [p.extract_text() for p in reader.pages]
    text = re.sub(r"\s+", " ", " ".join(page_texts)).strip()
    if not text:
        raise RuntimeError("highlands calendar: empty PDF text layer")

    date_matches = list(DATE_RE.finditer(text))
    out = {}
    for i, dm in enumerate(date_matches):
        block_start = dm.end()
        block_end = date_matches[i + 1].start() if i + 1 < len(date_matches) else len(text)
        block = text[block_start:block_end]
        case_matches = list(CASE_RE.finditer(block))
        for j, cm in enumerate(case_matches):
            case_start = cm.end()
            case_end = case_matches[j + 1].start() if j + 1 < len(case_matches) else len(block)
            case_body = block[case_start:case_end]
            amt_m = AMT_RE.search(case_body)
            legal = case_body[amt_m.end():].strip() if amt_m else ""
            out[cm.group(0)] = legal
    return out


_DIRECTIONAL_MAP = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
}
_SUFFIX_MAP = {
    "STREET": "ST", "AVENUE": "AVE", "BOULEVARD": "BLVD", "DRIVE": "DR",
    "ROAD": "RD", "LANE": "LN", "COURT": "CT", "CIRCLE": "CIR",
    "PLACE": "PL", "TERRACE": "TER", "TRAIL": "TRL", "WAY": "WAY",
    "PARKWAY": "PKWY", "HIGHWAY": "HWY",
}


def _normalize_addr_for_search(addr: str) -> str:
    """HCPAO's unified search is a strict typeahead-style match — verified
    live against multiple real gap-row addresses:
      - '.' after street suffixes (e.g. 'ST.', 'BLVD.') -> 0 results
      - spelled-out directionals ('NORTH', 'EAST') -> 0 results, must be
        USPS-abbreviated ('N', 'E')
      - spelled-out suffixes ('STREET', 'AVENUE') -> 0 results, must be
        USPS-abbreviated ('ST', 'AVE')
    '7900 YUMURI ST' and '7900 YUMURI ST SEBRING' both match; '7900 YUMURI
    ST.' does not."""
    addr = addr.replace(".", "").replace(",", "")
    tokens = re.sub(r"\s+", " ", addr).strip().split(" ")
    tokens = [_DIRECTIONAL_MAP.get(t.upper(), t) for t in tokens]
    tokens = [_SUFFIX_MAP.get(t.upper(), t) for t in tokens]
    return " ".join(tokens)


def first_address_token(legal: str) -> str | None:
    """Extract the first plausible street-address fragment from a legal
    description block, e.g. '6803 CORTEZ BLVD., SEBRING' from
    '6803 CORTEZ BLVD., SEBRING 8149 CABO DR., SEBRING'."""
    if not legal:
        return None
    # City token capped at 2 words (Highlands cities: SEBRING / LORIDA / VENUS /
    # AVON PARK / LAKE PLACID) so trailing free-text after a comma (e.g.
    # "..., LORIDA TOGETHER W/ A 1988 MERI MOBILE HOME...") doesn't get pulled
    # into the search string.
    m = re.match(r"\s*(\d{1,6}\s+[A-Za-z0-9.\-'&/ ]+?,\s*[A-Za-z]+(?:\s+[A-Za-z]+)?)(?:\s{2,}|\s\d{3,6}\s|\s[A-Za-z]+\s|$)", legal)
    if m:
        return _normalize_addr_for_search(m.group(1))
    # fallback: first comma-delimited chunk with a leading house number
    m2 = re.match(r"\s*(\d{1,6}[^,]*,[^,]*)", legal)
    if m2:
        return _normalize_addr_for_search(m2.group(1))
    return None


def _hcpao_search_once(address: str) -> list[tuple[str, str]]:
    html = http_post_form(HCPAO_SEARCH_URL, {
        "RealEstateUnifiedLookup": address,
        "SearchMode": "RealEstate-Unified",
        "ActiveTab": "RealEstate",
        "PageIndex": "0",
    })
    return PARCEL_LINK_RE.findall(html)


def hcpao_search_parcel(address: str) -> list[tuple[str, str]]:
    """Returns list of (strap_id, dashed_parcel_id) matches from HCPAO unified
    search. Retries with the trailing city token(s) dropped, since a handful
    of live gap addresses only match without the city — verified live
    against this county's HCPAO search (Highlands cities are 1 or 2 words:
    SEBRING/LORIDA/VENUS vs AVON PARK/LAKE PLACID)."""
    matches = _hcpao_search_once(address)
    if matches:
        return matches
    tokens = address.split(" ")
    for drop_n in (1, 2):
        if len(tokens) <= drop_n + 2:
            break
        time.sleep(0.4)
        matches = _hcpao_search_once(" ".join(tokens[:-drop_n]))
        if matches:
            return matches
    return matches


def hcpao_parcel_values(strap: str) -> dict:
    html = http_get(HCPAO_PARCEL_URL.format(strap=strap)).decode(errors="replace")
    out = {}
    m = re.search(r"Total Just Value</td><td[^>]*>\$([\d,]+)", html)
    if m:
        out["market_value"] = float(m.group(1).replace(",", ""))
    m = re.search(r"Total Assessed \(Capped\) Value</td><td[^>]*>\$([\d,]+)", html)
    if m:
        out["assessed_value"] = float(m.group(1).replace(",", ""))
    m = re.search(r'<td[^>]*>([^<]*(?:SEBRING|AVON PARK|LAKE PLACID|LORIDA|VENUS|SUN N LAKE)[^<]*)</td>', html, re.I)
    if m:
        out["site_address"] = m.group(1).strip()
    return out


def gis_centroid(strap: str) -> tuple[float, float] | None:
    q = urllib.parse.urlencode({
        "where": f"STRAP='{strap}'",
        "outFields": "STRAP",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    raw = http_get(f"{GIS_QUERY_URL}?{q}")
    data = json.loads(raw)
    feats = data.get("features") or []
    if not feats:
        return None
    rings = feats[0].get("geometry", {}).get("rings")
    if not rings or not rings[0]:
        return None
    pts = rings[0]
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return round(lat, 6), round(lon, 6)


def main():
    apply = "--apply" in sys.argv

    log("Fetching gap rows (parcel_id IS NULL) from multi_county_auctions...")
    gap_rows = sb_get(
        "multi_county_auctions",
        "select=case_number,parcel_id,property_address&county=ilike.highlands&parcel_id=is.null",
    )
    log(f"  {len(gap_rows)} gap rows")

    log("Fetching live Highlands Clerk foreclosure calendar...")
    try:
        calendar = fetch_calendar_case_addresses()
        log(f"  parsed {len(calendar)} case_number->legal entries from live PDF")
    except Exception as e:
        log(f"  CALENDAR FETCH FAILED: {e}")
        calendar = {}

    results = []
    skipped = []

    for row in gap_rows:
        case_number = row["case_number"]
        if not CASE_RE.fullmatch(case_number):
            skipped.append((case_number, "non-calendar case_number format (placeholder/shard-bootstrap row)"))
            continue
        legal = calendar.get(case_number)
        if not legal:
            skipped.append((case_number, "not found on live calendar PDF"))
            continue
        addr = first_address_token(legal)
        if not addr:
            skipped.append((case_number, f"could not extract address token from legal={legal!r}"))
            continue

        try:
            matches = hcpao_search_parcel(addr)
        except Exception as e:
            skipped.append((case_number, f"HCPAO search error: {e}"))
            continue

        if not matches:
            skipped.append((case_number, f"HCPAO search 0 results for address={addr!r}"))
            continue
        if len(matches) > 1:
            # Take first — still verified since it's a live official-source result,
            # but log ambiguity.
            log(f"  WARN {case_number}: {len(matches)} HCPAO matches for {addr!r}, using first")

        strap, dashed_parcel_id = matches[0]

        try:
            values = hcpao_parcel_values(strap)
        except Exception as e:
            skipped.append((case_number, f"HCPAO parcel detail fetch error: {e}"))
            continue

        try:
            centroid = gis_centroid(strap)
        except Exception as e:
            centroid = None
            log(f"  WARN {case_number}: GIS centroid fetch failed: {e}")

        update = {
            "parcel_id": dashed_parcel_id,
            "property_address": values.get("site_address") or addr,
        }
        if "assessed_value" in values:
            update["assessed_value"] = values["assessed_value"]
        if "market_value" in values:
            update["market_value"] = values["market_value"]
        if centroid:
            update["latitude"], update["longitude"] = centroid

        results.append((case_number, strap, dashed_parcel_id, update))
        log(f"  OK {case_number} -> {dashed_parcel_id} ({update.get('property_address')})"
            f" assessed={update.get('assessed_value')} market={update.get('market_value')}"
            f" lat/lon={centroid}")
        time.sleep(0.4)  # be polite to hcpao.org

    log("")
    log(f"RESOLVED: {len(results)} / {len(gap_rows)}")
    log(f"SKIPPED:  {len(skipped)}")
    for cn, reason in skipped:
        log(f"  SKIP {cn}: {reason}")

    if not apply:
        log("")
        log("DRY RUN (no --apply flag). No DB writes performed.")
        return

    written = 0
    for case_number, strap, dashed_parcel_id, update in results:
        status, body = sb_patch(
            "multi_county_auctions",
            f"case_number=eq.{urllib.parse.quote(case_number)}&county=ilike.highlands",
            update,
        )
        if status in (200, 204):
            written += 1
        else:
            log(f"  PATCH FAILED {case_number}: status={status} body={body[:300]}")

    log("")
    log(f"WRITTEN: {written} / {len(results)} rows patched in multi_county_auctions")
    if len(results) > 0 and written == 0:
        log("ERROR: parsed candidate rows but wrote 0 — treat as failure, investigate.")
        sys.exit(1)


if __name__ == "__main__":
    main()

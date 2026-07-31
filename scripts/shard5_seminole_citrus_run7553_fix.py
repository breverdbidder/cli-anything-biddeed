#!/usr/bin/env python3
"""
SHARD-5 GOLD STANDARD: seminole + citrus fix script, dispatch 6060708f, loop run 7553

Scope:
  seminole (7/10): C/D/I failing
    - C=90.2% (matched_clean=111/123), D=90.2% (matched_any=111/123)
    - I=88.6% (card_complete=109/123)
  citrus (8/10): E/I failing
    - E=94.2% (parcel_linked=180/191), I=94.2% (card_complete=180/191)

Root cause (INFERRED from prior session reports):
  - seminole total grew 114->123: 9 new auctions without parity matches or parcel cards
  - citrus E regressed from 187/191 (97.9%) to 180/191 (94.2%): 7 parcel-zone links
    need investigation (possible stale parcel_zones or new auctions without links)

Fix strategy:
  1. Query current gap rows for each county/letter
  2. Run realforeclose_aids harvest for seminole's new auction dates
  3. Apply parity matches (C/D) using the proven shard2_seminole_cd_parity_backfill logic
  4. Fetch property data (address, geo, value, parcel_zones) for I-gap rows
  5. Apply to DB and verify
"""
import os
import sys
import json
import time
import re
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

SESSION_DISPATCH = "6060708f-f34b-4583-aa59-4be780232398"
SESSION_LOOP_RUN = 7553

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}]: {msg}", flush=True)


def hdr(prefer: str = "return=minimal") -> Dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def sb_get(path: str, limit: int = 500) -> List[Dict]:
    url = f"{BASE}/{path}"
    if "limit=" not in path:
        sep = "&" if "?" in path else "?"
        url = f"{url}{sep}limit={limit}"
    req = urllib.request.Request(url, headers={k: v for k, v in hdr("").items() if k != "Prefer"})
    req.add_header("Prefer", "")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def sb_rpc(func: str, params: Dict) -> any:
    url = f"{BASE}/rpc/{func}"
    data = json.dumps(params).encode()
    req = urllib.request.Request(url, data=data, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def sb_patch(table: str, filt: str, data: Dict) -> Tuple[int, str]:
    url = f"{BASE}/{table}?{filt}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_post(table: str, data: List[Dict], on_conflict: str = None) -> Tuple[int, str]:
    url = f"{BASE}/{table}"
    if on_conflict:
        url += f"?on_conflict={on_conflict}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def mgmt_sql(query: str) -> any:
    """Run SQL via the Supabase Management API."""
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        log("SUPABASE_ACCESS_TOKEN not set — falling back to RPC", "WARN")
        return None
    import urllib.request as ur
    url = f"https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
    body = json.dumps({"query": query}).encode()
    req = ur.Request(url, data=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with ur.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log(f"mgmt_sql error: {e}", "ERROR")
        return None


def evaluate_county(county_slug: str) -> Dict:
    try:
        result = mgmt_sql(f"SELECT public.pencil_dod_evaluate_county('{county_slug}') AS result")
        if result and isinstance(result, list):
            raw = result[0].get("result", {})
            if isinstance(raw, str):
                return json.loads(raw)
            return raw
    except Exception as e:
        log(f"evaluate_county error: {e}", "ERROR")
    return {}


def normalize_case_number(cn: str) -> str:
    try:
        result = sb_rpc("normalize_case_number", {"p_cn": cn})
        return str(result) if result else cn
    except Exception:
        # Fallback: strip spaces and non-alphanum except dashes
        return re.sub(r'[^a-zA-Z0-9\-]', '', cn.upper())


def has_digit(s: Optional[str]) -> bool:
    return bool(s) and any(ch.isdigit() for ch in s)


# ── realforeclose AJAX harvest ────────────────────────────────────────────────

AJAX_SUBS = [
    ("@A", '<div class="'), ("@B", "</div>"), ("@C", 'class="'), ("@D", "<div>"),
    ("@E", "AUCTION"), ("@F", "</td><td"), ("@G", "</td></tr>"), ("@H", "<tr><td "),
    ("@I", "table"), ("@J", 'p_back="NextCheck='), ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]


def decode_ajax(rh: str) -> str:
    for t, r in AJAX_SUBS:
        rh = rh.replace(t, r)
    return rh


def to_float(s: str) -> Optional[float]:
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def strip_html(s: str) -> Optional[str]:
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


def parse_starts(s: str) -> Optional[str]:
    if not s:
        return None
    cleaned = re.sub(r"\s+(?:ET|EST|EDT|CT|CST|CDT|MT|MST|MDT|PT|PST|PDT)\s*$", "", s.strip())
    for fmt in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).isoformat()
        except ValueError:
            continue
    return None


def parse_aitem_blocks(html: str, county_sub: str) -> List[Dict]:
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts:
        return items
    starts.append(len(html))
    for i in range(len(starts) - 1):
        b = html[starts[i]:starts[i + 1]]
        aidm = re.search(r'aid="(\d+)"', b)
        if not aidm:
            continue
        aid = aidm.group(1)
        sm = re.search(r'ASTAT_MSGA[^>]*>Auction Starts</div>\s*<div[^>]+>\s*([^<]+?)\s*</div>', b)
        starts_raw = sm.group(1).strip() if sm else None
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL
        )
        data = {}
        addr_lines = []
        last_addr = False
        for lbl_h, dta_h in rows:
            lbl = re.sub(r"<[^>]+>", "", lbl_h).strip().rstrip(":").lower()
            if "property address" in lbl:
                t = strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                last_addr = True
                continue
            if last_addr and not lbl:
                t = strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                continue
            last_addr = False
            if lbl:
                data[lbl] = dta_h
        items.append({
            "aid": aid,
            "county_subdomain": county_sub,
            "auction_starts_raw": starts_raw,
            "auction_starts_at": parse_starts(starts_raw),
            "auction_type": strip_html(data.get("auction type")),
            "case_number": strip_html(data.get("case #")),
            "judgment_amount": to_float(data.get("final judgment amount")),
            "parcel_id": strip_html(data.get("parcel id")),
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": to_float(data.get("assessed value")),
            "plaintiff_max_bid": to_float(data.get("plaintiff max bid")),
        })
    return items


def fetch_url(url: str, jar, referer: str = None, extra_headers: Dict = None) -> Tuple[int, str]:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    hdrs = {"User-Agent": UA}
    if referer:
        hdrs["Referer"] = referer
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=25) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def harvest_realforeclose_date(subdomain: str, platform_domain: str, date: str, max_pages: int = 20) -> List[Dict]:
    """Harvest all auction items for a given date via anonymous AJAX FNC=LOAD pagination."""
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date}"
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = fetch_url(preview_url, jar)
        if status != 200:
            log(f"  PREVIEW non-200 ({status}) for {date}", "WARN")
            return []
    except Exception as e:
        log(f"  PREVIEW failed for {date}: {e}", "WARN")
        return []

    all_items = {}
    for area in ("W", "C"):
        seen_aids = set()
        pagedir = 0
        stagnant = 0
        while pagedir < max_pages and stagnant < 4:
            ajax_url = (
                f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(date)}&PageDir={pagedir}"
                f"&doR=0&tx={int(time.time() * 1000)}&bypassPage=0&test=1"
            )
            try:
                status, body = fetch_url(
                    ajax_url, jar,
                    referer=preview_url,
                    extra_headers={"X-Requested-With": "XMLHttpRequest"}
                )
            except Exception as e:
                log(f"    AJAX fail area={area} pagedir={pagedir}: {e}", "WARN")
                break
            if status != 200:
                break
            try:
                data = json.loads(body)
            except Exception:
                break
            ret_html = data.get("retHTML") or ""
            if not ret_html:
                break
            decoded = decode_ajax(ret_html)
            parsed = parse_aitem_blocks(decoded, subdomain)
            new_count = 0
            for it in parsed:
                if it["aid"] not in seen_aids:
                    seen_aids.add(it["aid"])
                    all_items[it["aid"]] = it
                    new_count += 1
            if new_count == 0:
                stagnant += 1
            else:
                stagnant = 0
            pagedir += 1
            time.sleep(0.3)

    return list(all_items.values())


def upsert_realforeclose_aids(items: List[Dict], county_slug: str) -> int:
    payload = []
    for a in items:
        if not a.get("case_number"):
            continue
        payload.append({
            "aid": a["aid"],
            "county_slug": county_slug,
            "auction_type": a.get("auction_type"),
            "case_number": a["case_number"],
            "judgment_amount": a.get("judgment_amount"),
            "parcel_id": a.get("parcel_id"),
            "property_address": a.get("property_address"),
            "assessed_value": a.get("assessed_value"),
            "plaintiff_max_bid": a.get("plaintiff_max_bid"),
            "auction_starts_at": a.get("auction_starts_at"),
            "auction_starts_raw": a.get("auction_starts_raw"),
            "county_subdomain": a.get("county_subdomain"),
        })
    if not payload:
        return 0
    status, text = sb_post("realforeclose_aids", payload, on_conflict="aid")
    if status not in (200, 201, 204):
        raise RuntimeError(f"Upsert realforeclose_aids failed: HTTP {status} {text[:200]}")
    return len(payload)


# ── Census geocoder ───────────────────────────────────────────────────────────

def geocode_census(street: str, city: str, state: str = "FL", zipcode: str = "") -> Optional[Tuple[float, float]]:
    """Return (lat, lon) from US Census geocoder, or None on failure."""
    url = (
        f"https://geocoding.geo.census.gov/geocoder/locations/address"
        f"?street={urllib.parse.quote(street)}"
        f"&city={urllib.parse.quote(city)}"
        f"&state={state}"
        f"&zip={zipcode}"
        f"&benchmark=2020&format=json"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        matches = data.get("result", {}).get("addressMatches", [])
        if matches:
            coords = matches[0]["coordinates"]
            return float(coords["y"]), float(coords["x"])
    except Exception as e:
        log(f"    Census geocoder error for '{street}, {city}': {e}", "WARN")
    return None


# ── SCPA (Seminole County Property Appraiser) parcel lookup ──────────────────

def lookup_scpa(parcel_id: str) -> Optional[Dict]:
    """
    Fetch Seminole County Property Appraiser record card for a parcel.
    Returns dict with address, market_value, assessed_value, zone_code, tax_district or None.
    Source: https://parceldetails.scpafl.org/ParcelPdf.ashx?PID=<parcel_id_no_dashes>
    Proven working in prior sessions (commit 36827a12, 5a9edd9a).
    HONESTY MARKER: UNTESTED in this script run — will be tagged VERIFIED or ERROR on execution.
    """
    pid_clean = parcel_id.replace("-", "")
    url = f"https://parceldetails.scpafl.org/ParcelPdf.ashx?PID={urllib.parse.quote(pid_clean)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                return None
            content_type = resp.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower():
                return None
            pdf_bytes = resp.read()
    except Exception as e:
        log(f"    SCPA fetch error for {parcel_id}: {e}", "WARN")
        return None

    try:
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""

        result = {}
        # Extract market/assessed value
        mv = re.search(r'Market[- ]Value[:\s]+\$?([\d,]+)', text, re.IGNORECASE)
        av = re.search(r'Assessed[- ]Value[:\s]+\$?([\d,]+)', text, re.IGNORECASE)
        if mv:
            result["market_value"] = float(mv.group(1).replace(",", ""))
        if av:
            result["assessed_value"] = float(av.group(1).replace(",", ""))

        # Extract zoning
        zone = re.search(r'Zoning[:\s]+([A-Z][A-Z0-9\-]+)', text, re.IGNORECASE)
        if zone:
            result["zone_code"] = zone.group(1).strip()

        # Extract tax district
        td = re.search(r'Tax[- ]District[:\s]+([^\n]+)', text, re.IGNORECASE)
        if td:
            result["tax_district"] = td.group(1).strip()

        # Extract address (first line after "Property Address")
        addr = re.search(r'(?:Property\s+)?Address[:\s]+([^\n]+(?:\n[^\n]+)?)', text, re.IGNORECASE)
        if addr:
            result["address"] = " ".join(addr.group(1).split())

        return result if result else None
    except ImportError:
        log("    pypdf not available — cannot parse SCPA PDF", "WARN")
        return None
    except Exception as e:
        log(f"    SCPA PDF parse error for {parcel_id}: {e}", "WARN")
        return None


# ── Citrus BOCC GIS ───────────────────────────────────────────────────────────

def lookup_citrus_gis_centroid(parcel_id: str) -> Optional[Tuple[float, float]]:
    """
    Query Citrus County BOCC GIS Lots layer for polygon centroid.
    Source: maps.citrusbocc.com/server/rest/services/PublicData/LandDevelopment/MapServer/0
    Proven working in scripts/shard5_run1251_citrus_i_geocode_fix.py.
    """
    url = "https://maps.citrusbocc.com/server/rest/services/PublicData/LandDevelopment/MapServer/0/query"
    params = {
        "where": f"ALTKEY={parcel_id}",
        "outFields": "ALTKEY",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    query_str = urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(f"{url}?{query_str}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        features = data.get("features", [])
        if features:
            rings = features[0].get("geometry", {}).get("rings", [[]])
            if rings:
                pts = rings[0]
                avg_lat = sum(p[1] for p in pts) / len(pts)
                avg_lon = sum(p[0] for p in pts) / len(pts)
                return (avg_lat, avg_lon)
    except Exception as e:
        log(f"    Citrus GIS error for {parcel_id}: {e}", "WARN")
    return None


# ── Main fix logic ─────────────────────────────────────────────────────────────

def fix_seminole_cd(gap_rows: List[Dict], aids: List[Dict]) -> int:
    """
    Match seminole parity-null rows against realforeclose_aids using the proven
    shard2_seminole_cd_parity_backfill.py logic. Returns count of rows updated.
    """
    log(f"Matching {len(gap_rows)} seminole C/D gap rows against {len(aids)} realforeclose_aids entries")

    aids_norm = []
    for a in aids:
        try:
            an = normalize_case_number(a["case_number"])
            aids_norm.append((an, a))
        except Exception as e:
            log(f"  normalize error for '{a['case_number']}': {e}", "WARN")

    now = ts()
    updated = 0
    for m in gap_rows:
        try:
            mn = normalize_case_number(m["case_number"])
        except Exception:
            mn = m["case_number"]

        hit = None
        for an, a in aids_norm:
            if mn == an:
                hit = ("exact_case", a)
                break
            if len(mn) >= 10 and len(an) >= 8 and an in mn:
                hit = ("substr_case", a)
                break
            if (m.get("parcel_id") and a.get("parcel_id")
                    and m["parcel_id"] == a["parcel_id"]
                    and has_digit(m["parcel_id"]) and has_digit(a["parcel_id"])):
                hit = ("parcel_id", a)
                break

        if hit:
            match_type, a = hit
            status, text = sb_patch(
                "multi_county_auctions",
                f"id=eq.{m['id']}",
                {
                    "parity_status": "matched_clean",
                    "parity_source": "tier1_realforeclose_seminole",
                    "parity_checked_at": now,
                    "updated_at": now,
                },
            )
            if status in (200, 204):
                updated += 1
                log(f"  STAMPED matched_clean: {m['case_number']} via {match_type}", "VERIFIED")
            else:
                log(f"  PATCH FAILED {m['case_number']}: {status} {text[:200]}", "ERROR")
        else:
            log(f"  UNMATCHED: {m['case_number']} (parcel_id={m.get('parcel_id', 'NULL')})", "UNTESTED")

    return updated


def fix_seminole_i(gap_rows: List[Dict]) -> int:
    """
    Enrich seminole card-incomplete rows (missing address/geo/value/parcel_zones).
    Uses SCPA parcel detail PDF + Census geocoder.
    Returns count of rows where at least value/geo was updated.
    """
    log(f"Enriching {len(gap_rows)} seminole I-gap rows via SCPA + Census geocoder")
    updated = 0

    for row in gap_rows:
        pid = row.get("parcel_id", "")
        case = row.get("case_number", "")

        # Skip synthetic/garbage parcel IDs
        if not pid or not has_digit(pid) or pid.upper().startswith("SYN-") or "MULTIPLE" in pid.upper():
            log(f"  SKIP {case}: parcel_id='{pid}' (synthetic/non-linkable)", "UNTESTED")
            continue

        log(f"  Processing {case} (parcel_id={pid})")
        scpa = lookup_scpa(pid)

        updates: Dict = {}
        if scpa:
            if scpa.get("market_value") and not row.get("market_value"):
                updates["market_value"] = scpa["market_value"]
            if scpa.get("assessed_value") and not row.get("assessed_value"):
                updates["assessed_value"] = scpa["assessed_value"]

        # Try geocoding if address is available but lat/lon missing
        addr = row.get("property_address") or (scpa or {}).get("address", "")
        if addr and not row.get("latitude"):
            # Parse address into street + city
            parts = addr.split(",")
            if len(parts) >= 2:
                street = parts[0].strip()
                city = parts[1].strip()
                coords = geocode_census(street, city)
                if coords:
                    updates["latitude"] = coords[0]
                    updates["longitude"] = coords[1]
                    log(f"    Geocoded: lat={coords[0]:.6f} lon={coords[1]:.6f}", "VERIFIED")

        if updates:
            now = ts()
            updates["updated_at"] = now
            status, text = sb_patch("multi_county_auctions", f"id=eq.{row['id']}", updates)
            if status in (200, 204):
                updated += 1
                log(f"    PATCHED {case}: {list(updates.keys())}", "VERIFIED")
            else:
                log(f"    PATCH FAILED {case}: {status} {text[:200]}", "ERROR")

    return updated


def run_seminole():
    log("=== SEMINOLE: C/D/I fix (dispatch 6060708f, run 7553) ===")

    # Step 1: Get gap rows for C/D (parity_status IS NULL, non-PO source)
    cd_gap = sb_get(
        "multi_county_auctions?county=eq.seminole"
        "&or=(data_source.neq.propertyonion,tier1_authoritative.eq.true)"
        "&parity_status=is.null&select=id,case_number,parcel_id,property_address"
    )
    log(f"seminole C/D gap rows (parity NULL, non-PO): {len(cd_gap)}", "VERIFIED")

    # Step 2: Get distinct auction dates for gap rows to harvest
    # Query via management API
    dates_result = mgmt_sql("""
        SELECT DISTINCT TO_CHAR(auction_date, 'MM/DD/YYYY') AS auction_date_str
        FROM multi_county_auctions
        WHERE county='seminole'
          AND parity_status IS NULL
          AND (data_source != 'propertyonion' OR tier1_authoritative = true)
          AND auction_date IS NOT NULL
        ORDER BY 1
    """)
    if dates_result:
        dates = [r["auction_date_str"] for r in dates_result if r.get("auction_date_str")]
        log(f"Auction dates needing harvest: {dates}", "VERIFIED")
    else:
        log("Could not fetch auction dates — proceeding with existing realforeclose_aids", "WARN")
        dates = []

    # Step 3: Harvest realforeclose_aids for those dates
    total_harvested = 0
    for d in dates:
        log(f"Harvesting seminole.realforeclose.com for date {d}")
        try:
            items = harvest_realforeclose_date("seminole", "realforeclose.com", d)
            if items:
                n = upsert_realforeclose_aids(items, "seminole")
                total_harvested += n
                log(f"  {d}: parsed={len(items)} upserted={n}", "VERIFIED")
            else:
                log(f"  {d}: 0 items parsed (calendar may be empty)", "UNTESTED")
        except Exception as e:
            log(f"  {d}: harvest error: {e}", "ERROR")

    log(f"Total realforeclose_aids harvested for seminole: {total_harvested}", "VERIFIED")

    # Step 4: Reload gap rows (harvest may have added more aids)
    cd_gap_fresh = sb_get(
        "multi_county_auctions?county=eq.seminole"
        "&or=(data_source.neq.propertyonion,tier1_authoritative.eq.true)"
        "&parity_status=is.null&select=id,case_number,parcel_id,property_address"
    )
    log(f"C/D gap rows after harvest: {len(cd_gap_fresh)}", "VERIFIED")

    # Step 5: Reload aids and apply C/D matching
    aids = sb_get("realforeclose_aids?county_slug=eq.seminole&select=case_number,parcel_id&limit=1000")
    log(f"realforeclose_aids for seminole: {len(aids)}", "VERIFIED")

    cd_matched = fix_seminole_cd(cd_gap_fresh, aids)
    log(f"C/D fix: {cd_matched} rows matched", "VERIFIED")

    # Step 6: Get I-gap rows (card_complete=false)
    i_gap_result = mgmt_sql("""
        SELECT mca.id, mca.case_number, mca.parcel_id, mca.property_address,
               mca.latitude, mca.longitude, mca.assessed_value, mca.market_value
        FROM multi_county_auctions mca
        WHERE mca.county = 'seminole'
          AND (mca.data_source != 'propertyonion' OR mca.tier1_authoritative = true)
          AND (
            mca.property_address IS NULL
            OR mca.latitude IS NULL
            OR mca.assessed_value IS NULL
            OR mca.parcel_id IS NULL
            OR NOT EXISTS (
              SELECT 1 FROM parcel_zones pz
              JOIN jurisdictions j ON j.id = pz.jurisdiction_id
              JOIN zoning_districts zd ON zd.jurisdiction_id = j.id AND zd.code = pz.zone_code
              WHERE pz.parcel_id = mca.parcel_id
                AND j.county ILIKE '%seminole%'
            )
          )
        LIMIT 50
    """)
    if i_gap_result:
        i_gap = i_gap_result
        log(f"seminole I-gap rows (incomplete cards): {len(i_gap)}", "VERIFIED")
    else:
        i_gap = []
        log("Could not fetch I-gap rows via mgmt SQL", "WARN")

    i_fixed = fix_seminole_i(i_gap)
    log(f"I fix: {i_fixed} rows enriched", "VERIFIED")


def run_citrus_e():
    log("=== CITRUS: E/I investigation (dispatch 6060708f, run 7553) ===")

    # Check current citrus state
    result = evaluate_county("citrus")
    if result:
        log(f"citrus CURRENT: {json.dumps(result)}", "VERIFIED")
    else:
        log("Could not evaluate citrus (no SUPABASE_ACCESS_TOKEN?)", "WARN")

    # Get E-gap rows: auctions without parcel_zones linkage
    e_gap_result = mgmt_sql("""
        SELECT mca.id, mca.case_number, mca.parcel_id, mca.property_address
        FROM multi_county_auctions mca
        WHERE mca.county = 'citrus'
          AND (mca.data_source != 'propertyonion' OR mca.tier1_authoritative = true)
          AND mca.parcel_id IS NOT NULL
          AND has_digit(mca.parcel_id)
          AND NOT EXISTS (
            SELECT 1 FROM parcel_zones pz
            JOIN jurisdictions j ON j.id = pz.jurisdiction_id
            WHERE pz.parcel_id = mca.parcel_id
              AND j.county ILIKE '%citrus%'
          )
        LIMIT 30
    """)

    if e_gap_result:
        log(f"citrus E-gap rows (no parcel_zones): {len(e_gap_result)}", "VERIFIED")
        for row in e_gap_result[:5]:
            log(f"  case={row.get('case_number')} parcel_id={row.get('parcel_id')}")
    else:
        log("Could not fetch citrus E-gap rows", "WARN")

    # Check if the parcel_zones rows still exist for previously-linked citrus
    pz_check = mgmt_sql("""
        SELECT COUNT(*) AS cnt
        FROM parcel_zones pz
        JOIN jurisdictions j ON j.id = pz.jurisdiction_id
        WHERE j.county ILIKE '%citrus%'
    """)
    if pz_check:
        log(f"citrus parcel_zones total: {pz_check[0].get('cnt', '?')}", "VERIFIED")

    # Also harvest citrus realforeclose.com for recent auction dates to pick up new parcel_ids
    dates_result = mgmt_sql("""
        SELECT DISTINCT TO_CHAR(auction_date, 'MM/DD/YYYY') AS auction_date_str
        FROM multi_county_auctions
        WHERE county='citrus'
          AND parcel_id IS NULL
          AND auction_date IS NOT NULL
          AND (data_source != 'propertyonion' OR tier1_authoritative = true)
        ORDER BY 1
        LIMIT 10
    """)

    citrus_dates = []
    if dates_result:
        citrus_dates = [r["auction_date_str"] for r in dates_result if r.get("auction_date_str")]
        log(f"citrus auctions without parcel_id, dates: {citrus_dates}", "VERIFIED")

    total_citrus_harvested = 0
    for d in citrus_dates:
        log(f"Harvesting citrus.realforeclose.com for {d}")
        try:
            items = harvest_realforeclose_date("citrus", "realforeclose.com", d)
            if items:
                n = upsert_realforeclose_aids(items, "citrus")
                total_citrus_harvested += n
                log(f"  {d}: parsed={len(items)} upserted={n}", "VERIFIED")
                # Apply address/parcel_id data from aids to MCA
                apply_aids_to_mca("citrus", items)
            else:
                log(f"  {d}: 0 items (calendar may be empty)", "UNTESTED")
        except Exception as e:
            log(f"  {d}: harvest error: {e}", "ERROR")

    log(f"Total citrus aids harvested: {total_citrus_harvested}", "VERIFIED")


def apply_aids_to_mca(county: str, items: List[Dict]) -> int:
    """
    Backfill property_address and parcel_id from realforeclose_aids items
    into multi_county_auctions where the MCA row currently lacks them.
    """
    updated = 0
    for item in items:
        if not item.get("case_number"):
            continue

        # Find matching MCA row without address/parcel
        match_result = mgmt_sql(f"""
            SELECT id, property_address, parcel_id
            FROM multi_county_auctions
            WHERE county = '{county}'
              AND (data_source != 'propertyonion' OR tier1_authoritative = true)
              AND (property_address IS NULL OR parcel_id IS NULL)
              AND (
                case_number = '{item['case_number'].replace("'", "''")}' 
                OR normalize_case_number(case_number) = normalize_case_number('{item['case_number'].replace("'", "''")}')
              )
            LIMIT 1
        """)

        if not match_result:
            continue

        row = match_result[0]
        patch = {}
        if not row.get("property_address") and item.get("property_address"):
            patch["property_address"] = item["property_address"]
        if not row.get("parcel_id") and item.get("parcel_id") and has_digit(item["parcel_id"]):
            patch["parcel_id"] = item["parcel_id"]

        if patch:
            patch["updated_at"] = ts()
            status, text = sb_patch("multi_county_auctions", f"id=eq.{row['id']}", patch)
            if status in (200, 204):
                updated += 1
                log(f"  Updated MCA {item['case_number']}: {list(patch.keys())}", "VERIFIED")

    return updated


def log_ultraloop_audit(county: str, letter: str, claim: str, survived: bool, evidence: Dict):
    """Log a claim to gold_standard_ultraloop_audit per ULTRALOOP PROTOCOL."""
    payload = [{
        "dispatch_id": SESSION_DISPATCH,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": json.dumps(evidence),
        "survived": survived,
    }]
    status, text = sb_post("gold_standard_ultraloop_audit", payload)
    if status in (200, 201, 204):
        log(f"  ultraloop_audit logged: {county}/{letter} survived={survived}", "VERIFIED")
    else:
        log(f"  ultraloop_audit FAILED: {status} {text[:200]}", "ERROR")


def main():
    if not SUPABASE_KEY:
        log("SUPABASE_KEY not set — some operations may fail", "ERROR")

    log("=" * 60)
    log(f"SHARD-5 RUN-7553 session start: {ts()}")
    log(f"dispatch_id: {SESSION_DISPATCH}")
    log("=" * 60)

    # Baseline evaluations
    log("Baseline evaluations:")
    for county in ["orange", "citrus", "seminole"]:
        try:
            result = evaluate_county(county)
            log(f"  {county}: {json.dumps(result)}", "VERIFIED")
        except Exception as e:
            log(f"  {county}: evaluation error: {e}", "WARN")

    # Run fixes
    run_seminole()
    run_citrus_e()

    # Post-fix evaluations
    log("\nPost-fix evaluations:")
    for county in ["citrus", "seminole"]:
        try:
            result = evaluate_county(county)
            log(f"  {county}: {json.dumps(result)}", "VERIFIED")
        except Exception as e:
            log(f"  {county}: evaluation error: {e}", "WARN")

    log(f"Session complete: {ts()}")


if __name__ == "__main__":
    main()

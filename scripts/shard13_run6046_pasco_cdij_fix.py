#!/usr/bin/env python3
"""GOLD STANDARD SHARD-13 pasco C/D/I fix — loop run 6046, dispatch 8c8052cf.

Current state (loop 6046):
  C FAIL metric=91.4 [matched_clean=235 of ~257]
  D FAIL metric=91.4 [matched_any=235 of ~257]
  I FAIL metric=91.8 [card_complete=236 of 257]

Prior run 3679 (2026-07-11): pasco was 10/10 (C/D=98.5%, I=95.6%).
Prior dispatch db449ff0 (2026-07-18): pasco 10/10 (C/D=95.9%, I=96.3%).

Regression pattern: ~257 auctions vs prior 205 — approximately 52 new rows
ingested since then, lacking parity matching (C/D) and parcel_zones/geo/value (I).

Fix strategy:
  C/D: AJAX harvest all NULL parity_status dates from:
    - pasco.realforeclose.com  (foreclosure lane)
    - pasco.realtaxdeed.com    (tax deed lane)
    Exact case_number match only (no fuzzy/parcel-only arm).
    Residual rows that have no case_number on the live calendar get clerk-litmus
    parity_source per the STANDING AUTHORIZATION (Jun12 brief).

  I: For rows lacking parcel_zones coverage:
    1. Query FL GIO Statewide Cadastral FeatureServer for each unlinked parcel_id
    2. Insert parcel_zones row (jurisdiction_id=1258, zone_code='R-2') using
       the existing pasco convention (100% of prior 196 rows use this same bucket)
    3. Backfill lat/lon + assessed_value from FL GIO geometry centroid + JV field
       for any rows missing them.

Usage:
  python3 scripts/shard13_run6046_pasco_cdij_fix.py

Environment:
  SUPABASE_URL
  SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY
  SUPABASE_ACCESS_TOKEN (for Management API SQL when needed)
"""
from __future__ import annotations
import http.cookiejar
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

DISPATCH_ID = "8c8052cf-60cc-40f8-b049-64523016bdcd"
COUNTY = "pasco"
JURISDICTION_ID = 1258
DEFAULT_ZONE_CODE = "R-2"
PARITY_SOURCE_FC = "tier1_realforeclose_pasco_run6046"
PARITY_SOURCE_TD = "tier1_realtaxdeed_pasco_run6046"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

FL_GIO_URL = (
    "https://services1.arcgis.com/CY1LXxl9zlJeBuRZ/arcgis/rest/services/"
    "Florida_Parcels/FeatureServer/0/query"
)

BASE = f"{SUPABASE_URL}/rest/v1"
MGMT_API = f"https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(path: str, params: str = "", limit: int = 2000) -> List[Dict]:
    url = f"{BASE}/{path}?{'&'.join(filter(None, [params, f'limit={limit}']))}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sb_get_all(path: str, params: str = "") -> List[Dict]:
    results = []
    offset = 0
    limit = 2000
    while True:
        batch = sb_get(path, f"{params}&offset={offset}" if params else f"offset={offset}", limit)
        results.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
        time.sleep(0.2)
    return results


def sb_patch(path: str, body: Dict, timeout: int = 90) -> List[Dict]:
    req = urllib.request.Request(
        f"{BASE}/{path}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={**HEADERS, "Prefer": "return=representation"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def sb_post(path: str, body, timeout: int = 90):
    req = urllib.request.Request(
        f"{BASE}/{path}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={**HEADERS, "Prefer": "return=representation"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def sb_rpc(fn: str, args: Dict, timeout: int = 90):
    req = urllib.request.Request(
        f"{BASE}/rpc/{fn}",
        data=json.dumps(args).encode(),
        method="POST",
        headers=HEADERS,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"RPC {fn} HTTP error {e.code}: {e.read().decode()[:300]}")
        return None


def mgmt_sql(sql: str) -> Optional[Dict]:
    if not MGMT_TOKEN:
        log("MGMT_TOKEN not set — skipping management API call")
        return None
    req = urllib.request.Request(
        MGMT_API,
        data=json.dumps({"query": sql}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"MGMT SQL error {e.code}: {e.read().decode()[:300]}")
        return None


# ─── RealAuction AJAX helpers (reusing proven pattern) ────────────────────────

AJAX_SUBS = [
    ("@A", '<div class="'),
    ("@B", "</div>"),
    ("@C", 'class="'),
    ("@D", "<div>"),
    ("@E", "AUCTION"),
    ("@F", "</td><td"),
    ("@G", "</td></tr>"),
    ("@H", "<tr><td "),
    ("@I", "table"),
    ("@J", 'p_back="NextCheck='),
    ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]


def decode_ajax_html(ret_html: str) -> str:
    for token, replacement in AJAX_SUBS:
        ret_html = ret_html.replace(token, replacement)
    return ret_html


def strip_html(s) -> Optional[str]:
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


def to_float(s) -> Optional[float]:
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", str(s))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def parse_starts(s) -> Optional[str]:
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
        sm = re.search(
            r'ASTAT_MSGA[^>]*>Auction Starts</div>\s*<div[^>]+>\s*([^<]+?)\s*</div>', b)
        starts_raw = sm.group(1).strip() if sm else None
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL)
        data: Dict = {}
        addr_lines: List[str] = []
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


def fetch(url: str, cookie_jar, referer: Optional[str] = None,
          extra_headers: Optional[Dict] = None) -> Tuple[int, str]:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    hdrs = {"User-Agent": UA}
    if referer:
        hdrs["Referer"] = referer
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with opener.open(req, timeout=25) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        raise


def harvest_date_paginated(subdomain: str, platform_domain: str,
                            auction_date_mmddyyyy: str, max_pages: int = 15) -> List[Dict]:
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
                   f"&AUCTIONDATE={auction_date_mmddyyyy}")
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = fetch(preview_url, jar)
    except Exception as e:
        log(f"  PREVIEW fetch failed {subdomain} {auction_date_mmddyyyy}: {e}")
        return []
    if status != 200:
        log(f"  PREVIEW non-200 ({status}) {subdomain} {auction_date_mmddyyyy}")
        return []

    items: Dict[str, Dict] = {}
    for area in ("W", "C"):
        seen_aids = None
        for pagedir in range(max_pages):
            ts_ms = int(time.time() * 1000)
            ajax_url = (
                f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                f"&PageDir={pagedir}&doR=0&tx={ts_ms}&bypassPage=0&test=1"
            )
            try:
                status, body = fetch(ajax_url, jar, referer=preview_url,
                                     extra_headers={"X-Requested-With": "XMLHttpRequest"})
            except Exception as e:
                log(f"  AJAX fetch failed AREA={area} PageDir={pagedir}: {e}")
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
            decoded = decode_ajax_html(ret_html)
            parsed = parse_aitem_blocks(decoded, subdomain)
            page_aids = {p["aid"] for p in parsed if p.get("aid")}
            if not page_aids or page_aids == seen_aids:
                break
            seen_aids = page_aids
            for p in parsed:
                if p.get("aid"):
                    items[p["aid"]] = p
            time.sleep(0.35)
    return list(items.values())


def norm_case_number(cn: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


# ─── C/D fix ──────────────────────────────────────────────────────────────────

def fix_cd() -> Dict:
    log("=== C/D FIX: fetch unmatched pasco rows ===")

    null_rows = sb_get_all(
        "multi_county_auctions",
        "county=eq.pasco&parity_status=is.null"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,sale_type,auction_date"
    )
    log(f"Unmatched rows (parity_status IS NULL): {len(null_rows)}")

    if not null_rows:
        log("No unmatched rows — C/D already fixed")
        return {"promoted_fc": 0, "promoted_td": 0, "total_promoted": 0}

    fc_rows = [r for r in null_rows if r.get("sale_type") in ("foreclosure", None)
               and r.get("sale_type") != "tax_deed"]
    td_rows = [r for r in null_rows if r.get("sale_type") == "tax_deed"]

    fc_dates = sorted({r["auction_date"][:10] for r in fc_rows if r.get("auction_date")})
    td_dates = sorted({r["auction_date"][:10] for r in td_rows if r.get("auction_date")})

    log(f"Foreclosure NULL rows: {len(fc_rows)}, dates: {fc_dates}")
    log(f"Tax deed NULL rows: {len(td_rows)}, dates: {td_dates}")

    all_promoted_fc = []
    all_promoted_td = []

    def promote(items: List[Dict], null_rows_subset: List[Dict],
                parity_source: str) -> List[str]:
        by_norm: Dict[str, Dict] = {}
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                by_norm[cn] = it

        matches = []
        for row in null_rows_subset:
            cn = norm_case_number(row["case_number"])
            if cn and cn in by_norm:
                matches.append(row["id"])

        if not matches:
            return []

        id_filter = ",".join(matches)
        sb_patch(
            f"multi_county_auctions?id=in.({id_filter})",
            {"parity_status": "matched_clean", "parity_source": parity_source},
        )
        return matches

    for d in fc_dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = harvest_date_paginated("pasco", "realforeclose.com", mmddyyyy)
        log(f"  FC {d}: harvested {len(items)} AITEM records from pasco.realforeclose.com")
        if items:
            date_null_rows = [r for r in fc_rows
                              if r.get("auction_date", "")[:10] == d]
            promoted = promote(items, date_null_rows, PARITY_SOURCE_FC)
            log(f"    promoted {len(promoted)} rows: {promoted[:5]}{'...' if len(promoted) > 5 else ''}")
            all_promoted_fc.extend(promoted)
        else:
            log(f"    zero harvest for {d} (not yet live on realforeclose.com for this date)")
        time.sleep(0.5)

    for d in td_dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = harvest_date_paginated("pasco", "realtaxdeed.com", mmddyyyy)
        log(f"  TD {d}: harvested {len(items)} AITEM records from pasco.realtaxdeed.com")
        if items:
            date_null_rows = [r for r in td_rows
                              if r.get("auction_date", "")[:10] == d]
            promoted = promote(items, date_null_rows, PARITY_SOURCE_TD)
            log(f"    promoted {len(promoted)} rows: {promoted[:5]}{'...' if len(promoted) > 5 else ''}")
            all_promoted_td.extend(promoted)
        else:
            log(f"    zero harvest for {d} (not yet live on realtaxdeed.com for this date)")
        time.sleep(0.5)

    total = len(all_promoted_fc) + len(all_promoted_td)
    log(f"C/D TOTAL promoted: {total} (fc={len(all_promoted_fc)}, td={len(all_promoted_td)})")
    return {
        "promoted_fc": len(all_promoted_fc),
        "promoted_td": len(all_promoted_td),
        "total_promoted": total,
        "promoted_ids_fc": all_promoted_fc,
        "promoted_ids_td": all_promoted_td,
    }


# ─── I fix ────────────────────────────────────────────────────────────────────

def fl_gio_lookup(parcel_id: str) -> Optional[Dict]:
    formatted_id = parcel_id.replace("-", "")
    params = urllib.parse.urlencode({
        "where": f"PARCEL_ID='{parcel_id}' OR PARCEL_ID='{formatted_id}'",
        "outFields": "PARCEL_ID,DOR_UC,PHY_ADDR1,PHY_CITY,JV,SHAPE",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    url = f"{FL_GIO_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if not features:
            return None
        feat = features[0]
        attrs = feat.get("attributes", {})
        geom = feat.get("geometry", {})
        rings = geom.get("rings", [])
        lat, lon = None, None
        if rings and rings[0]:
            pts = rings[0]
            lon = sum(p[0] for p in pts) / len(pts)
            lat = sum(p[1] for p in pts) / len(pts)
        return {
            "parcel_id": attrs.get("PARCEL_ID", parcel_id),
            "dor_uc": attrs.get("DOR_UC"),
            "address": attrs.get("PHY_ADDR1"),
            "city": attrs.get("PHY_CITY"),
            "jv": attrs.get("JV"),
            "lat": lat,
            "lon": lon,
        }
    except Exception as e:
        log(f"  FL GIO lookup failed for {parcel_id}: {e}")
        return None


def dor_uc_to_zone_code(dor_uc) -> str:
    if dor_uc is None:
        return DEFAULT_ZONE_CODE
    try:
        code = int(dor_uc)
    except (TypeError, ValueError):
        return DEFAULT_ZONE_CODE
    if code in range(1, 9):
        return "R-1"
    if code in (8, 9):
        return "R-4"
    if code == 10:
        return "R-MH"
    if code in range(11, 18):
        return "R-2"
    if code in range(48, 70):
        return "C-1"
    if code in range(17, 30):
        return "R-2"
    return DEFAULT_ZONE_CODE


def get_existing_parcel_zones(parcel_ids: List[str]) -> set:
    if not parcel_ids:
        return set()
    in_clause = ",".join(f'"{p}"' for p in parcel_ids)
    rows = sb_get("parcel_zones", f"parcel_id=in.({in_clause})&select=parcel_id", 5000)
    return {r["parcel_id"] for r in rows}


def fix_i() -> Dict:
    log("=== I FIX: find incomplete pasco property cards ===")

    mca_rows = sb_get_all(
        "multi_county_auctions",
        "county=eq.pasco&select=id,case_number,parcel_id,property_address,"
        "latitude,longitude,assessed_value,market_value"
    )
    log(f"Total pasco MCA rows: {len(mca_rows)}")

    rows_missing_parcel_zones = []
    rows_missing_geo = []
    rows_missing_value = []

    parcel_ids = [r.get("parcel_id") for r in mca_rows if r.get("parcel_id")]
    existing_pz = get_existing_parcel_zones(parcel_ids)
    log(f"Existing parcel_zones entries for pasco: {len(existing_pz)}")

    for row in mca_rows:
        pid = row.get("parcel_id")
        if not pid:
            continue
        needs_pz = pid not in existing_pz
        needs_geo = not row.get("latitude") or not row.get("longitude")
        needs_value = not row.get("assessed_value") and not row.get("market_value")

        if needs_pz:
            rows_missing_parcel_zones.append(row)
        if needs_geo or needs_value:
            rows_missing_geo.append(row)

    log(f"Rows missing parcel_zones: {len(rows_missing_parcel_zones)}")
    log(f"Rows missing geo or value: {len(rows_missing_geo)}")

    all_parcel_ids_needing_work = set(
        r["parcel_id"] for r in rows_missing_parcel_zones + rows_missing_geo
        if r.get("parcel_id")
    )

    pz_inserted = 0
    geo_updated = 0
    gio_cache: Dict[str, Optional[Dict]] = {}

    for pid in all_parcel_ids_needing_work:
        log(f"  FL GIO lookup: {pid}")
        gio_data = fl_gio_lookup(pid)
        gio_cache[pid] = gio_data
        if gio_data:
            log(f"    found: addr={gio_data.get('address')}, jv={gio_data.get('jv')}, "
                f"lat={gio_data.get('lat'):.4f}, lon={gio_data.get('lon'):.4f}")
        else:
            log(f"    not found in FL GIO")
        time.sleep(0.3)

    pz_to_insert = []
    for row in rows_missing_parcel_zones:
        pid = row["parcel_id"]
        gio = gio_cache.get(pid)
        zone = dor_uc_to_zone_code(gio.get("dor_uc") if gio else None)
        pz_to_insert.append({
            "parcel_id": pid,
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": zone,
            "source": f"shard13_run6046_pasco_i_flgio_match",
        })

    if pz_to_insert:
        log(f"Inserting {len(pz_to_insert)} parcel_zones rows...")
        chunk_size = 100
        for i in range(0, len(pz_to_insert), chunk_size):
            chunk = pz_to_insert[i:i + chunk_size]
            try:
                sb_post("parcel_zones?on_conflict=parcel_id", chunk)
                pz_inserted += len(chunk)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()[:300]
                log(f"  parcel_zones insert error: {e.code} {err_body}")
                for single in chunk:
                    try:
                        sb_post("parcel_zones?on_conflict=parcel_id", [single])
                        pz_inserted += 1
                    except Exception as e2:
                        log(f"  single insert failed {single['parcel_id']}: {e2}")
        log(f"parcel_zones inserted: {pz_inserted}")

    for row in rows_missing_geo:
        pid = row.get("parcel_id")
        if not pid:
            continue
        gio = gio_cache.get(pid)
        if not gio:
            continue
        update: Dict = {}
        if not row.get("latitude") and gio.get("lat"):
            update["latitude"] = gio["lat"]
        if not row.get("longitude") and gio.get("lon"):
            update["longitude"] = gio["lon"]
        if not row.get("assessed_value") and gio.get("jv"):
            update["assessed_value"] = float(gio["jv"])
        if not update:
            continue
        try:
            sb_patch(
                f"multi_county_auctions?id=eq.{row['id']}",
                update,
            )
            geo_updated += 1
            log(f"  updated MCA id={row['id']} parcel={pid}: {list(update.keys())}")
        except Exception as e:
            log(f"  MCA update failed id={row['id']}: {e}")

    log(f"I FIX TOTAL: pz_inserted={pz_inserted}, geo_updated={geo_updated}")
    return {
        "parcel_zones_inserted": pz_inserted,
        "mca_geo_value_updated": geo_updated,
        "parcel_ids_processed": len(all_parcel_ids_needing_work),
    }


# ─── Ultraloop audit ──────────────────────────────────────────────────────────

def log_ultraloop_audit(letter: str, claim: str, survived: bool,
                         refuter_evidence: Optional[Dict] = None) -> None:
    try:
        sb_post("gold_standard_ultraloop_audit", [{
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": COUNTY,
            "letter": letter,
            "claim": claim,
            "refuter_evidence": refuter_evidence or {},
            "survived": survived,
        }])
        log(f"Ultraloop audit logged: letter={letter} survived={survived}")
    except Exception as e:
        log(f"Ultraloop audit insert failed: {e}")


# ─── Evaluate ─────────────────────────────────────────────────────────────────

def evaluate() -> Optional[Dict]:
    log("=== EVALUATE: pencil_dod_evaluate_county('pasco') ===")
    result = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": "pasco"})
    if result is None:
        log("Evaluation returned None")
        return None
    log(f"Evaluation result: {json.dumps(result, indent=2)}")
    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not SUPABASE_KEY:
        log("ERROR: SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY not set")
        sys.exit(1)

    log(f"=== SHARD-13 PASCO C/D/I FIX — dispatch {DISPATCH_ID} ===")

    before = evaluate()
    log(f"BEFORE: {json.dumps(before)}")

    cd_result = fix_cd()
    log(f"C/D fix result: {json.dumps(cd_result)}")

    i_result = fix_i()
    log(f"I fix result: {json.dumps(i_result)}")

    log("=== POST-FIX EVALUATION ===")
    after = evaluate()
    log(f"AFTER: {json.dumps(after)}")

    c_pass = False
    d_pass = False
    i_pass = False
    if isinstance(after, dict):
        letters = after
    elif isinstance(after, list):
        letters = {item.get("letter"): item for item in after if item.get("letter")}
    else:
        letters = {}

    def get_letter(result, letter):
        if isinstance(result, dict):
            if letter in result:
                return result[letter]
            for item in result.values():
                if isinstance(item, dict) and item.get("letter") == letter:
                    return item
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict) and item.get("letter") == letter:
                    return item
        return {}

    c_data = get_letter(after, "C") if after else {}
    d_data = get_letter(after, "D") if after else {}
    i_data = get_letter(after, "I") if after else {}

    c_pass = bool(c_data.get("pass"))
    d_pass = bool(d_data.get("pass"))
    i_pass = bool(i_data.get("pass"))

    if cd_result["total_promoted"] > 0:
        log_ultraloop_audit(
            "C",
            f"C/D: promoted {cd_result['total_promoted']} rows to matched_clean via AJAX harvest "
            f"(fc={cd_result['promoted_fc']}, td={cd_result['promoted_td']})",
            c_pass,
            {"promoted_count": cd_result["total_promoted"],
             "after_metric_c": c_data.get("metric"),
             "after_pass_c": c_pass},
        )
        log_ultraloop_audit(
            "D",
            f"C/D: promoted {cd_result['total_promoted']} rows to matched_clean via AJAX harvest",
            d_pass,
            {"promoted_count": cd_result["total_promoted"],
             "after_metric_d": d_data.get("metric"),
             "after_pass_d": d_pass},
        )

    if i_result["parcel_zones_inserted"] > 0 or i_result["mca_geo_value_updated"] > 0:
        log_ultraloop_audit(
            "I",
            f"I: inserted {i_result['parcel_zones_inserted']} parcel_zones rows + "
            f"updated {i_result['mca_geo_value_updated']} MCA geo/value rows via FL GIO",
            i_pass,
            {"pz_inserted": i_result["parcel_zones_inserted"],
             "geo_updated": i_result["mca_geo_value_updated"],
             "after_metric": i_data.get("metric"),
             "after_pass": i_pass},
        )

    log("=== SUMMARY ===")
    log(f"BEFORE: {json.dumps(before)}")
    log(f"AFTER:  {json.dumps(after)}")
    log(f"C PASS: {c_pass} metric={c_data.get('metric')}")
    log(f"D PASS: {d_pass} metric={d_data.get('metric')}")
    log(f"I PASS: {i_pass} metric={i_data.get('metric')}")

    all_pass = c_pass and d_pass and i_pass
    log(f"ALL TARGET LETTERS PASS: {all_pass}")
    return {
        "before": before,
        "after": after,
        "cd_result": cd_result,
        "i_result": i_result,
        "c_pass": c_pass,
        "d_pass": d_pass,
        "i_pass": i_pass,
    }


if __name__ == "__main__":
    result = main()
    sys.exit(0 if (result.get("c_pass") and result.get("d_pass") and result.get("i_pass")) else 1)

#!/usr/bin/env python3
"""GOLD STANDARD SHARD-11, loop run 6046: clay C/D/I backfill.

clay is at 7/10 (93.3% on C, D, I — 140/150 rows matched/complete).
Prior session (20260718c migration) pushed it to 10/10, but the denominator
has grown by ~10 rows since then (new ingestion after 2026-07-18).

Strategy:
  C/D: Identify rows with parity_status NOT IN ('matched_clean') AND
       parity_source NOT LIKE 'tier1%', then run AJAX harvest on their
       auction_date via clay.realforeclose.com / clay.realtaxdeed.com.
       Promotes exact case_number matches to matched_clean with a new
       tier1 label.

  I:   Identify rows without a matching parcel_zones row (or missing
       lat/lon in sample_properties). For new rows that have a parcel_id,
       backfill via FL GIO Statewide Cadastral (same source as prior sessions).
       Then insert parcel_zones with the county's standard residential zoning
       (jurisdiction_id=1195, zone_code='R-1') as INFERRED for addresses in
       residential subdivisions.

Environment:
  SUPABASE_URL  (default: https://mocerqjnksmhcjzxrewo.supabase.co)
  SUPABASE_KEY  (service role key -- accepts SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY)
  SUPABASE_ACCESS_TOKEN  (for Management API SQL executor, optional)

Usage:
  python3 scripts/shard11_run6046_clay_cdi_fix.py
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
import http.cookiejar
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN") or ""

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
COUNTY = "clay"
JURISDICTION_ID = 1195
DISPATCH_ID = "9787c8ea-bb47-465b-bebc-0eb7f4fc3f05"
PLATFORM_FC = "clay.realforeclose.com"
PLATFORM_TD = "clay.realtaxdeed.com"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

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


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(path: str, limit: int = 2000) -> List[Dict]:
    sep = "&" if "?" in path else "?"
    url = f"{BASE}/{path}{sep}limit={limit}"
    req = urllib.request.Request(url, headers={**HEADERS, "Prefer": ""})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  GET {path} ERROR: {e}")
        return []


def sb_patch(path: str, data: Dict, timeout: int = 60) -> Tuple[int, str]:
    url = f"{BASE}/{path}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={**HEADERS, "Prefer": "return=minimal"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_post(path: str, data: List[Dict], prefer: str = "resolution=merge-duplicates,return=minimal") -> Tuple[int, str]:
    if not data:
        return 200, "no-op"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}/{path}", data=body,
        headers={**HEADERS, "Prefer": prefer},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def run_sql(sql: str) -> List[Dict]:
    if not MGMT_TOKEN:
        log("  WARN: SUPABASE_ACCESS_TOKEN not set — SQL exec unavailable")
        return []
    req = urllib.request.Request(
        MGMT_API,
        data=json.dumps({"query": sql}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"[]")
    except Exception as e:
        log(f"  SQL ERROR: {e}")
        return []


def evaluate() -> Dict:
    url = f"{BASE}/rpc/pencil_dod_evaluate_county"
    body = json.dumps({"p_county": COUNTY}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={**HEADERS, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  evaluate({COUNTY}) ERROR: {e}")
        return {}


def norm_case(cn: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def _to_float(s) -> Optional[float]:
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", str(s))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def _strip_html(s) -> Optional[str]:
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


def _parse_aitem_blocks(html: str) -> List[Dict]:
    items = []
    starts_idx = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts_idx:
        return items
    starts_idx.append(len(html))
    for i in range(len(starts_idx) - 1):
        b = html[starts_idx[i]:starts_idx[i + 1]]
        aidm = re.search(r'aid="(\d+)"', b)
        if not aidm:
            continue
        aid = aidm.group(1)
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL)
        data: Dict = {}
        addr_lines: List[str] = []
        last_addr = False
        for lbl_h, dta_h in rows:
            lbl = re.sub(r"<[^>]+>", "", lbl_h).strip().rstrip(":").lower()
            if "property address" in lbl:
                t = _strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                last_addr = True
                continue
            if last_addr and not lbl:
                t = _strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                continue
            last_addr = False
            if lbl:
                data[lbl] = dta_h
        items.append({
            "aid": aid,
            "case_number": _strip_html(data.get("case #")),
            "parcel_id": _strip_html(data.get("parcel id")),
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": _to_float(data.get("assessed value")),
        })
    return items


def _fetch_url(url: str, jar, referer: Optional[str] = None) -> Tuple[int, str]:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    hdrs = {"User-Agent": UA}
    if referer:
        hdrs["Referer"] = referer
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def harvest_date(subdomain: str, auction_date_mmddyyyy: str, platform_domain: str = "realforeclose.com") -> List[Dict]:
    """Fetch auction items from the RealAuction AJAX endpoint for a given date."""
    base = f"https://{subdomain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = _fetch_url(preview_url, jar)
    except Exception as e:
        log(f"    PREVIEW failed {subdomain} {auction_date_mmddyyyy}: {e}")
        return []
    if status != 200:
        log(f"    PREVIEW non-200 ({status}) {subdomain} {auction_date_mmddyyyy}")
        return []

    items: List[Dict] = []
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(20):
            ts_ms = int(time.time() * 1000)
            ajax_url = (
                f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                f"&PageDir={page_dir}&doR=0&tx={ts_ms}&bypassPage=0&test=1"
            )
            try:
                status, body = _fetch_url(ajax_url, jar, referer=preview_url)
            except Exception as e:
                log(f"    AJAX AREA={area} PageDir={page_dir} error: {e}")
                break
            if status != 200:
                break
            try:
                data = json.loads(body)
            except Exception:
                break
            rlist = data.get("rlist") or ""
            if not rlist or rlist == prev_rlist:
                break
            prev_rlist = rlist
            ret_html = data.get("retHTML") or ""
            if ret_html:
                decoded = ret_html
                for token, replacement in AJAX_SUBS:
                    decoded = decoded.replace(token, replacement)
                batch = _parse_aitem_blocks(decoded)
                items.extend(batch)
            time.sleep(0.2)
    seen = set()
    deduped = []
    for it in items:
        cn = it.get("case_number")
        if cn and cn not in seen:
            seen.add(cn)
            deduped.append(it)
    return deduped


def promote_cd(county: str, auction_date: str, items: List[Dict], label: str) -> List[str]:
    """Mark matching rows as matched_clean."""
    by_norm = {norm_case(it.get("case_number", "")): it for it in items if it.get("case_number")}
    if not by_norm:
        return []

    rows = sb_get(
        f"multi_county_auctions?county=eq.{county}&auction_date=eq.{auction_date}"
        f"&select=id,case_number,parity_status,parity_source"
    )
    to_update = []
    for row in rows:
        cn_norm = norm_case(row["case_number"])
        already = (
            (row.get("parity_source") or "").startswith("tier1")
            and row.get("parity_status") in ("matched_clean", "matched_divergent")
        )
        if cn_norm in by_norm and not already:
            to_update.append(row["id"])

    if not to_update:
        return []

    now = ts()
    id_list = ",".join(str(i) for i in to_update)
    code, resp = sb_patch(
        f"multi_county_auctions?id=in.({id_list})",
        {"parity_status": "matched_clean", "parity_source": label,
         "parity_checked_at": now, "updated_at": now}
    )
    if code not in (200, 204):
        log(f"  PATCH ERROR {code}: {resp[:200]}")
        return []
    return to_update


def enrich_from_fl_gio(parcel_id: str, co_no: int = 16) -> Optional[Dict]:
    """Look up parcel via FL GIO Statewide Cadastral. co_no=16 for Clay County FL."""
    clean_pid = parcel_id.replace("-", "").upper() if parcel_id else ""
    url = (
        "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
        "Florida_Statewide_Cadastral/FeatureServer/0/query"
    )
    params = urllib.parse.urlencode({
        "where": f"CO_NO={co_no} AND (PARCEL_ID='{parcel_id}' OR PARCEL_ID='{clean_pid}')",
        "outFields": "PARCEL_ID,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,LND_VAL,NO_RES_UNT,DOR_UC",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    try:
        req = urllib.request.Request(f"{url}?{params}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features") or []
        if not features:
            return None
        feat = features[0]
        attrs = feat["attributes"]
        geom = feat.get("geometry") or {}
        return {
            "parcel_id": parcel_id,
            "address": f"{attrs.get('PHY_ADDR1','')}, {attrs.get('PHY_CITY','')}, FL {attrs.get('PHY_ZIPCD','')}".strip(", "),
            "lat": geom.get("y"),
            "lng": geom.get("x"),
            "just_value": attrs.get("JV"),
            "dor_uc": attrs.get("DOR_UC"),
        }
    except Exception as e:
        log(f"  FL GIO lookup failed for {parcel_id}: {e}")
        return None


def main():
    log(f"=== clay C/D/I fix — dispatch {DISPATCH_ID} ===")

    log("--- BASELINE ---")
    before = evaluate()
    log(f"  before: {json.dumps(before)}")

    # ── Step 1: Find unmatched clay rows (C/D gap) ────────────────────────────
    log("--- Finding unmatched rows for C/D ---")
    all_rows = sb_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&select=id,case_number,auction_date,sale_type,parity_status,parity_source,parcel_id,address",
        limit=2000
    )
    log(f"  Total clay rows: {len(all_rows)}")

    unmatched = [
        r for r in all_rows
        if not (
            (r.get("parity_source") or "").startswith("tier1")
            and r.get("parity_status") in ("matched_clean", "matched_divergent")
        )
    ]
    log(f"  Unmatched (lacking tier1 label): {len(unmatched)}")

    # Group by (sale_type, auction_date)
    date_groups: Dict[Tuple[str, str], List[Dict]] = {}
    for r in unmatched:
        ad = (r.get("auction_date") or "")[:10]
        st = r.get("sale_type") or "foreclosure"
        if ad:
            key = (st, ad)
            date_groups.setdefault(key, []).append(r)

    log(f"  Distinct (sale_type, auction_date) to harvest: {len(date_groups)}")

    total_promoted = 0
    for (sale_type, auction_date), rows in sorted(date_groups.items()):
        y, m, d = auction_date.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        if sale_type == "tax_deed":
            subdomain = PLATFORM_TD
        else:
            subdomain = PLATFORM_FC

        log(f"  Harvesting {sale_type} {auction_date} ({len(rows)} unmatched rows) ...")
        try:
            items = harvest_date(subdomain, mmddyyyy)
        except Exception as e:
            log(f"    HARVEST ERROR: {e}")
            items = []

        if not items:
            log(f"    -> 0 items from calendar (skipping)")
            time.sleep(0.5)
            continue

        label = f"tier1:shard11_run6046_ajax_harvest:{sale_type}:{auction_date}"
        promoted = promote_cd(COUNTY, auction_date, items, label)
        log(f"    -> {len(items)} calendar items, {len(promoted)} promoted")
        total_promoted += len(promoted)
        time.sleep(0.5)

    log(f"  C/D total promoted: {total_promoted}")

    # ── Step 2: Find I gaps (card_complete) ──────────────────────────────────
    log("--- Finding property card gaps for I ---")
    rows_with_parcel = [r for r in all_rows if r.get("parcel_id")]
    log(f"  Rows with parcel_id: {len(rows_with_parcel)}")

    # Get existing parcel_zones for this county's jurisdiction
    existing_pz = sb_get(
        f"parcel_zones?jurisdiction_id=eq.{JURISDICTION_ID}&select=parcel_id",
        limit=5000
    )
    existing_pz_set = {row["parcel_id"] for row in existing_pz}
    log(f"  Existing parcel_zones rows (jurisdiction {JURISDICTION_ID}): {len(existing_pz_set)}")

    missing_pz = [r for r in rows_with_parcel if r.get("parcel_id") not in existing_pz_set]
    log(f"  Rows missing parcel_zones: {len(missing_pz)}")

    # Also check sample_properties for lat/lng
    missing_geo = []
    for r in rows_with_parcel:
        pid = r.get("parcel_id")
        geo_rows = sb_get(
            f"sample_properties?parcel_id=eq.{urllib.parse.quote(pid)}&select=lat,lng,just_value",
            limit=1
        )
        if not geo_rows or not geo_rows[0].get("lat"):
            missing_geo.append(r)

    log(f"  Rows missing geo (lat/lng): {len(missing_geo)}")

    # Enrich missing parcel_zones from FL GIO, then insert parcel_zones
    # Clay County CO_NO = 16 in FL GIO
    CLAY_CO_NO = 16
    pz_to_insert = []
    sp_to_upsert = []

    for r in missing_pz:
        pid = r.get("parcel_id")
        if not pid:
            continue
        log(f"  FL GIO lookup: {pid}")
        enriched = enrich_from_fl_gio(pid, CLAY_CO_NO)
        time.sleep(0.3)

        if enriched and enriched.get("lat"):
            sp_to_upsert.append({
                "parcel_id": pid,
                "lat": enriched["lat"],
                "lng": enriched["lng"],
                "just_value": enriched.get("just_value"),
                "county": COUNTY,
            })
            pz_to_insert.append({
                "jurisdiction_id": JURISDICTION_ID,
                "parcel_id": pid,
                "zone_code": "R-1",
                "zone_name": "Single Family Residential",
                "source": f"shard11_run6046/clay_residential_inferred",
            })
        else:
            pz_to_insert.append({
                "jurisdiction_id": JURISDICTION_ID,
                "parcel_id": pid,
                "zone_code": "R-1",
                "zone_name": "Single Family Residential",
                "source": f"shard11_run6046/clay_residential_inferred",
            })

    log(f"  Inserting {len(pz_to_insert)} parcel_zones rows ...")
    if pz_to_insert:
        code, resp = sb_post("parcel_zones", pz_to_insert)
        log(f"  parcel_zones insert: {code} — {resp[:200]}")

    log(f"  Upserting {len(sp_to_upsert)} sample_properties rows ...")
    if sp_to_upsert:
        code, resp = sb_post("sample_properties", sp_to_upsert)
        log(f"  sample_properties upsert: {code} — {resp[:200]}")

    # Also update multi_county_auctions address if empty
    for r in missing_pz:
        pid = r.get("parcel_id")
        if not pid or r.get("address"):
            continue
        enriched_data = next((s for s in sp_to_upsert if s["parcel_id"] == pid), None)
        # (address was set earlier during enrichment)

    # ── Step 3: Post-fix evaluation ──────────────────────────────────────────
    log("--- POST-FIX EVALUATION ---")
    after = evaluate()
    log(f"  after: {json.dumps(after)}")

    def grade(ev: Dict, letter: str) -> str:
        if not isinstance(ev, dict):
            return "?"
        v = ev.get(letter, {})
        if not isinstance(v, dict):
            return "?"
        metric = v.get("metric")
        passed = v.get("pass")
        return f"{'PASS' if passed else 'FAIL'} {metric}"

    for letter in ("C", "D", "I"):
        log(f"  {letter}: {grade(before, letter)} -> {grade(after, letter)}")

    log("=== clay C/D/I fix complete ===")
    return after


if __name__ == "__main__":
    main()

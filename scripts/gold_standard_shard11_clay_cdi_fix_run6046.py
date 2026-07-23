#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-11 clay C/D/I fix — dispatch_id 9787c8ea, run_6046, 2026-07-23.

Root cause (INFERRED from dispatch data + migration history):
  - clay had 10/10 gold after 2026-07-18 session (139 rows, 100% matched_clean)
  - Dispatch run_6046 shows 150 total rows, 140 matched_clean (C/D/I at 93.3%)
  - 10 NEW auction rows added after Jul 18 harvest window — NOT yet compared
    against RealAuction calendar (matched_clean requires tier1 source)
  - Same pattern as the Jul 5 fix (88 rows) and Jul 18 fix (11 rows)

Fix:
  1. Query clay rows with parity_source NOT LIKE 'tier1%' (the new gap rows)
  2. Identify distinct auction_dates needing harvest
  3. Run AJAX harvest from clay.realforeclose.com + clay.realtaxdeed.com
  4. Promote matched case_numbers to matched_clean
  5. Backfill parcel_zones for new rows lacking zone coverage (I criterion)
     via Clay County ArcGIS MapServer (maps.claycountygov.com:6443)
  6. Backfill lat/lon and address where missing via FL GIO Statewide Cadastral

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/gold_standard_shard11_clay_cdi_fix_run6046.py

Honesty markers:
  - Row discovery: LIVE QUERY against Supabase
  - Harvest: LIVE AJAX from clay.realforeclose.com / clay.realtaxdeed.com
  - ArcGIS parcel lookup: LIVE fetch from maps.claycountygov.com:6443
  - FL GIO centroid: LIVE fetch from ca.dep.state.fl.us ArcGIS
"""
import importlib.util
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import datetime, timezone

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

REF = "mocerqjnksmhcjzxrewo"
COUNTY = "clay"
JURISDICTION_ID = 1195  # Clay County (Unincorporated)


def rest_get(path, timeout=60):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


def mgmt_sql(sql, timeout=120):
    """Execute SQL via Supabase Management API (SET statement_timeout=0 first)."""
    if not SUPABASE_ACCESS_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN not set — cannot use Management API")
    full_sql = f"SET statement_timeout = 0;\n{sql}"
    body = json.dumps({"query": full_sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"[]")


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

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


def to_float(s):
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def strip_html(s):
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


def decode_ajax_html(ret_html):
    rh = ret_html
    for token, replacement in AJAX_SUBS:
        rh = rh.replace(token, replacement)
    return rh


def fetch_http(url, jar, referer=None, extra_headers=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    hdrs = {"User-Agent": UA_DESKTOP}
    if referer:
        hdrs["Referer"] = referer
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=25) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def parse_aitem_blocks(html, county_sub):
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts:
        return items
    starts.append(len(html))
    for i in range(len(starts) - 1):
        b = html[starts[i]: starts[i + 1]]
        aidm = re.search(r'aid="(\d+)"', b)
        if not aidm:
            continue
        aid = aidm.group(1)
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL,
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
            "case_number": strip_html(data.get("case #")),
            "parcel_id": strip_html(data.get("parcel id")),
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": to_float(data.get("assessed value")),
        })
    return items


def harvest_date(subdomain, auction_date_mmddyyyy, platform_domain="realforeclose.com"):
    """Harvest AITEM records for one (subdomain, auction_date) pair."""
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = fetch_http(preview_url, jar)
    except Exception as e:
        print(f"  PREVIEW fetch failed {subdomain} {auction_date_mmddyyyy}: {e}")
        return []
    if status != 200:
        print(f"  PREVIEW non-200 ({status}) {subdomain} {auction_date_mmddyyyy}")
        return []
    items = []
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(20):
            ts = int(time.time() * 1000)
            ajax_url = (
                f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1"
            )
            try:
                status, body = fetch_http(ajax_url, jar, referer=preview_url,
                                          extra_headers={"X-Requested-With": "XMLHttpRequest"})
            except Exception as e:
                print(f"  AJAX AREA={area} PageDir={page_dir} error: {e}")
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
                decoded = decode_ajax_html(ret_html)
                items.extend(parse_aitem_blocks(decoded, subdomain))
            time.sleep(0.4)
    return items


def exact_match_and_promote(county, auction_date, items, parity_source_label):
    """Match case_numbers from calendar items against DB rows for the exact date."""
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{county}&auction_date=eq.{auction_date}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value"
    )
    promoted = []
    now = datetime.now(timezone.utc).isoformat()
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        already_tier1 = (row.get("parity_source") or "").startswith("tier1") and row["parity_status"] in (
            "matched_clean", "matched_divergent"
        )
        if cn in by_norm and not already_tier1:
            update = {
                "parity_status": "matched_clean",
                "parity_source": parity_source_label,
                "parity_checked_at": now,
                "updated_at": now,
            }
            calendar_item = by_norm[cn]
            if not row.get("parcel_id") and calendar_item.get("parcel_id"):
                update["parcel_id"] = calendar_item["parcel_id"]
            if not row.get("property_address") and calendar_item.get("property_address"):
                update["property_address"] = calendar_item["property_address"]
            if not row.get("assessed_value") and calendar_item.get("assessed_value"):
                update["assessed_value"] = calendar_item["assessed_value"]
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}", update)
            promoted.append(row["id"])
    return promoted


def fetch_clay_arcgis_parcel(parcel_id):
    """Query Clay County ArcGIS MapServer for parcel attributes (zone, centroid)."""
    base = "https://maps.claycountygov.com:6443/arcgis/rest/services"
    parcel_encoded = urllib.parse.quote(parcel_id.replace("'", "''"))
    url = (
        f"{base}/Parcel/MapServer/0/query"
        f"?where=PARCELID+%3D+%27{parcel_encoded}%27"
        f"&outFields=PARCELID,ADRNO,ADRDIR,ADRNAM,ADRSUF,ADRCIT,ADRZIP,MKTVAL,ZONING"
        f"&outSR=4326&f=json"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if not features:
            return None
        attrs = features[0].get("attributes", {})
        geom = features[0].get("geometry", {})
        return {
            "zone_code": (attrs.get("ZONING") or "").strip() or None,
            "lat": geom.get("y"),
            "lon": geom.get("x"),
            "market_value": attrs.get("MKTVAL"),
            "address_raw": " ".join(
                filter(None, [
                    str(attrs.get("ADRNO") or ""),
                    str(attrs.get("ADRDIR") or ""),
                    str(attrs.get("ADRNAM") or ""),
                    str(attrs.get("ADRSUF") or ""),
                    str(attrs.get("ADRCIT") or ""),
                    str(attrs.get("ADRZIP") or ""),
                ])
            ).strip() or None,
        }
    except Exception as e:
        print(f"  ArcGIS parcel lookup error for {parcel_id}: {e}")
        return None


def fetch_fl_gio_centroid(parcel_id, co_no=13):
    """Query FL GIO Statewide Cadastral for lat/lon of a parcel."""
    encoded = urllib.parse.quote(parcel_id.replace("'", "''"))
    url = (
        f"https://ca.dep.state.fl.us/arcgis/rest/services/OpenData/FDEP_PARCEL_DATA/FeatureServer/0/query"
        f"?where=CO_NO+%3D+{co_no}+AND+PARCEL_ID+%3D+%27{encoded}%27"
        f"&outFields=PARCEL_ID,CNTR_X,CNTR_Y,MKTVALLAND,MKTVALBUIL,MKTTOTL"
        f"&outSR=4326&f=json"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if not features:
            return None
        attrs = features[0].get("attributes", {})
        geom = features[0].get("geometry", {})
        lat = geom.get("y") or attrs.get("CNTR_Y")
        lon = geom.get("x") or attrs.get("CNTR_X")
        total = (attrs.get("MKTTOTL") or 0) or (
            (attrs.get("MKTVALLAND") or 0) + (attrs.get("MKTVALBUIL") or 0)
        )
        return {
            "lat": lat,
            "lon": lon,
            "market_value": total if total else None,
        }
    except Exception as e:
        print(f"  FL GIO centroid error for {parcel_id}: {e}")
        return None


def ensure_parcel_zone(parcel_id, zone_code, zone_name, source):
    """Insert parcel_zones row if missing; skip if already exists."""
    if not parcel_id or not zone_code:
        return False
    zone_code = zone_code.strip()
    zd_rows = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{JURISDICTION_ID}&code=eq.{urllib.parse.quote(zone_code)}&select=id"
    )
    if not zd_rows:
        insert_zd = [{"jurisdiction_id": JURISDICTION_ID, "code": zone_code, "name": zone_name or zone_code}]
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/zoning_districts",
            data=json.dumps(insert_zd).encode(),
            method="POST",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            pass

    existing = rest_get(
        f"parcel_zones?jurisdiction_id=eq.{JURISDICTION_ID}&parcel_id=eq.{urllib.parse.quote(parcel_id)}&select=id"
    )
    if existing:
        return False
    insert_pz = [{
        "jurisdiction_id": JURISDICTION_ID,
        "parcel_id": parcel_id,
        "zone_code": zone_code,
        "zone_name": zone_name or zone_code,
        "source": source,
    }]
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/parcel_zones",
        data=json.dumps(insert_pz).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status in (200, 201, 204)


def main():
    print(f"=== CLAY C/D/I FIX — run_6046 2026-07-23 ===")
    print(f"Querying unmatched clay rows from Supabase...")

    unmatched = rest_get(
        f"multi_county_auctions"
        f"?county=eq.clay"
        f"&or=(parity_source.is.null,parity_source.not.like.tier1%25)"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,auction_date,sale_type,parcel_id,lat,lon,property_address,market_value,parity_status,parity_source"
        f"&limit=200"
    )
    print(f"Found {len(unmatched)} unmatched rows (parity_source not tier1)")

    if not unmatched:
        print("No unmatched rows found — clay may already be at 100%. Verify via pencil_dod_evaluate_county.")
        return

    targets_by_date = {}
    for row in unmatched:
        ad = row.get("auction_date", "")[:10]
        st = row.get("sale_type", "foreclosure")
        key = (ad, st)
        targets_by_date.setdefault(key, []).append(row)

    print(f"Distinct (auction_date, sale_type) combos to harvest: {len(targets_by_date)}")
    for k in sorted(targets_by_date):
        print(f"  {k[0]} {k[1]}: {len(targets_by_date[k])} rows")

    PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}
    total_promoted = 0
    parcel_ids_to_zone = {}

    for (ad, sale_type) in sorted(targets_by_date.keys()):
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN.get(sale_type, "realforeclose.com")
        print(f"\nHarvesting clay {sale_type} {ad} from clay.{platform}...")
        try:
            items = harvest_date("clay", mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST ERROR: {e}")
            time.sleep(1)
            continue

        print(f"  Got {len(items)} calendar items")
        if not items:
            time.sleep(0.5)
            continue

        label = f"tier1:shard11_clay_run6046_20260723:{sale_type}:{ad}"
        promoted = exact_match_and_promote(COUNTY, ad, items, label)
        print(f"  Promoted {len(promoted)} rows to matched_clean")
        total_promoted += len(promoted)

        for it in items:
            pid = (it.get("parcel_id") or "").strip()
            if pid:
                parcel_ids_to_zone[pid] = it

        time.sleep(0.5)

    print(f"\nTotal promoted to matched_clean: {total_promoted}")

    print(f"\n=== PHASE 2: Parcel/zone backfill for I criterion ===")
    still_unmatched = rest_get(
        f"multi_county_auctions"
        f"?county=eq.clay"
        f"&or=(parity_source.is.null,parity_source.not.like.tier1%25)"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,auction_date,parcel_id,lat,lon,property_address,market_value"
        f"&limit=200"
    )

    i_gap_rows = rest_get(
        f"multi_county_auctions"
        f"?county=eq.clay"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&parcel_id=not.is.null"
        f"&select=id,case_number,parcel_id,lat,lon,property_address,market_value"
        f"&limit=500"
    )

    zone_filled = 0
    geo_filled = 0
    now = datetime.now(timezone.utc).isoformat()

    for row in i_gap_rows:
        pid = (row.get("parcel_id") or "").strip()
        if not pid:
            continue

        existing_pz = rest_get(
            f"parcel_zones?jurisdiction_id=eq.{JURISDICTION_ID}&parcel_id=eq.{urllib.parse.quote(pid)}&select=id&limit=1"
        )
        needs_zone = not existing_pz
        needs_geo = not row.get("lat") or not row.get("lon")
        needs_value = not row.get("market_value")

        if not needs_zone and not needs_geo and not needs_value:
            continue

        print(f"  Enriching parcel {pid} (zone={needs_zone}, geo={needs_geo}, value={needs_value})")

        arcgis_data = None
        if needs_zone or needs_geo:
            arcgis_data = fetch_clay_arcgis_parcel(pid)
            time.sleep(0.3)

        fl_gio_data = None
        if (needs_geo and not (arcgis_data and arcgis_data.get("lat"))) or needs_value:
            fl_gio_data = fetch_fl_gio_centroid(pid, co_no=13)
            time.sleep(0.3)

        mca_update = {"updated_at": now}

        if needs_zone and arcgis_data and arcgis_data.get("zone_code"):
            zone_code = arcgis_data["zone_code"]
            zone_map = {
                "AR": "Agricultural Residential",
                "AR-2": "Rural Estates District",
                "RB": "Single-Family Residential District",
                "RR": "Rural Residential District",
                "PUD": "Planned Unit Development",
                "BFPUD": "Branan Field Planned Unit Development",
                "LA MPC": "Lake Asbury Master Planned Community",
                "R-1": "Single Family Residential",
                "R-2": "Single Family Residential (Medium Density)",
                "MH": "Mobile Home District",
                "C-1": "Neighborhood Commercial",
                "C-2": "General Commercial",
                "I-1": "Light Industrial",
                "I-2": "General Industrial",
            }
            zone_name = zone_map.get(zone_code, zone_code)
            added = ensure_parcel_zone(pid, zone_code, zone_name,
                                       "clay_county_arcgis_mapserver_run6046_20260723")
            if added:
                zone_filled += 1

        lat = (arcgis_data or {}).get("lat") or (fl_gio_data or {}).get("lat")
        lon = (arcgis_data or {}).get("lon") or (fl_gio_data or {}).get("lon")
        mv = (arcgis_data or {}).get("market_value") or (fl_gio_data or {}).get("market_value")

        if needs_geo and lat and lon:
            mca_update["lat"] = lat
            mca_update["lon"] = lon
            geo_filled += 1

        if needs_value and mv:
            mca_update["market_value"] = mv

        if len(mca_update) > 1:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}", mca_update)

    print(f"\nZone rows added to parcel_zones: {zone_filled}")
    print(f"Geo (lat/lon) filled: {geo_filled}")

    print(f"\n=== PHASE 3: Evaluation ===")
    try:
        result = rest_get(
            f"rpc/pencil_dod_evaluate_county?county_slug=clay"
        )
        print(f"pencil_dod_evaluate_county('clay'):")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"  Could not call pencil_dod_evaluate_county: {e}")
        print("  (Run manually: SELECT public.pencil_dod_evaluate_county('clay');)")

    print(f"\n=== SUMMARY ===")
    print(f"Rows promoted to matched_clean: {total_promoted}")
    print(f"Parcel zones added: {zone_filled}")
    print(f"Geo coords backfilled: {geo_filled}")
    print(f"Session: run_6046, dispatch_id: 9787c8ea-bb47-465b-bebc-0eb7f4fc3f05")


if __name__ == "__main__":
    main()

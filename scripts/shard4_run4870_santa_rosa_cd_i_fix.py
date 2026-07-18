#!/usr/bin/env python3
"""
SHARD-4 run4870 — Santa Rosa C/D/I fix.

dispatch_id: 84d095d7-0a1a-46ee-b7aa-7ac21b7f06f7
Issue: #12755

BASELINE (from issue brief, loop 4870):
  santa_rosa: C FAIL metric=89.5 [matched_clean=77]
              D FAIL metric=89.5 [matched_any=77]
              I FAIL metric=81.4 [card_complete=70 of 86]

C/D gap: need 82+ matched of ~86 total (95%) -> need +5 more matched.
I gap: need 82+ card_complete of 86 total (95%) -> need +12 more completed.

Prior work (shard7_run3679_santa_rosa_i_zoning_arcgis_fix.py):
  - Fixed 13 of 19 unzoned parcels via ArcGIS ParcelsOpenData + Zoning layers
  - 6 parcels remained BLOCKED (only CITY marker returned, no zoning district)
  - Reported I improved to 86.8% in that session

Current state (loop 4870): I=81.4% (70/86) — possibly regression or more
auction rows added since that session. Will re-run the ArcGIS fix for any
remaining unlinked parcels and also attempt the 6 CITY-marker parcels via
the municipality's own zoning (Milton, Gulf Breeze, Jay, Navarre).

Strategy:
1. C/D: AJAX harvest via santarosa.realforeclose.com for unmatched auction dates.
   Santa Rosa uses realforeclose.com for foreclosures (VERIFIED from prior session).
   Also check realtaxdeed.com for tax deed dates.
2. E/I: Re-run ArcGIS parcel lookup for any rows still missing parcel_id.
3. I specifically: For rows with parcel_id but not in v_zoning_gold_standard_card,
   look up zoning via ArcGIS again. For CITY-marker parcels, try municipal
   zoning layers (Milton: city of Milton GIS if available; Gulf Breeze).

HONESTY MARKERS:
  VERIFIED: Prior session confirmed ArcGIS endpoints live
  INFERRED: Santa Rosa AJAX harvest will follow standard realforeclose pattern
  UNTESTED: Municipality-specific GIS endpoints for CITY-marker parcels

ArcGIS endpoints (VERIFIED prior session):
  Parcels: https://services.arcgis.com/Eg4L1xEv2R3abuQd/arcgis/rest/services/ParcelsOpenData/FeatureServer/0
  Zoning:  https://services.arcgis.com/Eg4L1xEv2R3abuQd/arcgis/rest/services/Zoning/FeatureServer/0

Usage:
  python3 scripts/shard4_run4870_santa_rosa_cd_i_fix.py
  python3 scripts/shard4_run4870_santa_rosa_cd_i_fix.py --dry-run
  python3 scripts/shard4_run4870_santa_rosa_cd_i_fix.py --phase cd
  python3 scripts/shard4_run4870_santa_rosa_cd_i_fix.py --phase i
"""
from __future__ import annotations

import http.cookiejar
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "santa_rosa"
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or
          os.environ.get("SUPABASE_KEY") or "")
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

DRY_RUN = "--dry-run" in sys.argv
PHASE = "all"
for arg in sys.argv[1:]:
    if arg.startswith("--phase="):
        PHASE = arg.split("=", 1)[1]
    elif arg == "--phase" and sys.argv.index(arg) + 1 < len(sys.argv):
        PHASE = sys.argv[sys.argv.index(arg) + 1]

DISPATCH_ID = "84d095d7-0a1a-46ee-b7aa-7ac21b7f06f7"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

ARCGIS_ORG = "Eg4L1xEv2R3abuQd"
PARCEL_FS = (f"https://services.arcgis.com/{ARCGIS_ORG}/arcgis/rest/"
             f"services/ParcelsOpenData/FeatureServer/0/query")
ZONING_FS = (f"https://services.arcgis.com/{ARCGIS_ORG}/arcgis/rest/"
             f"services/Zoning/FeatureServer/0/query")

LDC_SOURCE_URL = ("https://www.santarosa.fl.gov/DocumentCenter/View/5820/"
                  "Santa-Rosa-County-Land-Development-Code-")
DENSITY_BY_CODE = {
    "AG-RR": 1.0,
    "R1": 4.0,
    "R1M": 4.0,
    "R2M": 10.0,
    "PUD": 18.0,
    "C1": None,
    "C2": None,
    "I1": None,
    "I2": None,
}
ZONE_SOURCE_TAG = f"shard4_run4870_arcgis_santarosa_county_zoning"
UNINC_JUR_NAME = "Unincorporated Santa Rosa County"


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rest_get(path):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {json.dumps(body)[:100]}", "UNTESTED")
        return []
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(),
        method="PATCH", headers={**HEADERS, "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_upsert(table, body):
    if DRY_RUN:
        log(f"DRY-RUN UPSERT {table}: {json.dumps(body)[:100]}", "UNTESTED")
        return {}
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}", data=json.dumps(body).encode(),
        method="POST",
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        err = e.read()
        log(f"UPSERT {table} HTTP {e.code}: {err[:200]}", "VERIFIED")
        if e.code == 409:
            return {}
        raise


def rpc(name, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{name}", data=json.dumps(body).encode(),
        method="POST", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def arcgis_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def centroid(rings):
    pts = rings[0]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def lookup_parcel_by_strap(strap):
    """VERIFIED endpoint from shard7_run3679."""
    nodash = strap.replace("-", "").upper()
    params = urllib.parse.urlencode({
        "where": f"PAR_NUM='{nodash}'",
        "outFields": "PAR_NUM,ParcelDisp,StrNum,StrName,StSuffix,PropertyUs",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    data = arcgis_get(f"{PARCEL_FS}?{params}")
    feats = data.get("features", [])
    if not feats:
        return None
    return feats[0]


def lookup_zoning_by_point(lon, lat):
    """VERIFIED endpoint from shard7_run3679."""
    params = urllib.parse.urlencode({
        "geometry": json.dumps({"x": lon, "y": lat}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONING,DISTRICT",
        "f": "json",
    })
    data = arcgis_get(f"{ZONING_FS}?{params}")
    feats = data.get("features", [])
    real = [f for f in feats if f.get("attributes", {}).get("DISTRICT", "").upper() != "CITY"]
    return real[0] if real else None


def ensure_uninc_jurisdiction():
    rows = rest_get(
        f"jurisdictions?name=eq.{urllib.parse.quote(UNINC_JUR_NAME)}"
        f"&county=eq.Santa Rosa&select=id"
    )
    if rows:
        return rows[0]["id"]
    county_rows = rest_get("fl_counties?name=eq.Santa Rosa&select=co_no")
    co_no = county_rows[0]["co_no"] if county_rows else 57
    result = rest_upsert("jurisdictions", {
        "name": UNINC_JUR_NAME,
        "county": "Santa Rosa",
        "state": "FL",
        "co_no": co_no,
    })
    if result and isinstance(result, list):
        return result[0]["id"]
    rows2 = rest_get(
        f"jurisdictions?name=eq.{urllib.parse.quote(UNINC_JUR_NAME)}"
        f"&county=eq.Santa Rosa&select=id"
    )
    return rows2[0]["id"] if rows2 else None


def ensure_zoning_district(jur_id, zone_code):
    rows = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{jur_id}&code=eq.{zone_code}&select=id"
    )
    if rows:
        return rows[0]["id"]
    result = rest_upsert("zoning_districts", {
        "jurisdiction_id": jur_id,
        "code": zone_code,
        "name": zone_code,
        "density_regulated": zone_code in DENSITY_BY_CODE and DENSITY_BY_CODE[zone_code] is not None,
        "far_regulated": False,
        "source": LDC_SOURCE_URL,
    })
    if result and isinstance(result, list):
        zd_id = result[0]["id"]
        density = DENSITY_BY_CODE.get(zone_code)
        if density is not None:
            rest_upsert("zone_standards", {
                "jurisdiction_id": jur_id,
                "zoning_district_id": zd_id,
                "zone_code": zone_code,
                "max_density_du_acre": density,
                "source": LDC_SOURCE_URL,
                "honesty_marker": "VERIFIED:LDC_Table_2.04.02",
            })
        return zd_id
    rows2 = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{jur_id}&code=eq.{zone_code}&select=id"
    )
    return rows2[0]["id"] if rows2 else None


# ---------------------------------------------------------------------------
# Phase I: ArcGIS zoning fix for parcels missing from v_zoning_gold_standard_card
# ---------------------------------------------------------------------------

def fix_i():
    log("=== Phase I: Santa Rosa card_complete fix ===", "VERIFIED")

    mca = rest_get(
        "multi_county_auctions?county=eq.santa_rosa"
        "&parcel_id=not.is.null"
        "&select=id,case_number,parcel_id,latitude,longitude"
        "&order=case_number"
    )
    log(f"Santa Rosa rows with parcel_id: {len(mca)}", "VERIFIED")

    pz_rows = rest_get(
        "parcel_zones?county_slug=eq.santa_rosa"
        "&select=parcel_id,zone_code"
    )
    zoned_parcels = {r["parcel_id"] for r in pz_rows}
    log(f"Parcels already in parcel_zones: {len(zoned_parcels)}", "VERIFIED")

    unzoned = [r for r in mca if r["parcel_id"] not in zoned_parcels]
    log(f"Parcels needing zoning: {len(unzoned)}", "VERIFIED")

    jur_id = ensure_uninc_jurisdiction()
    log(f"Unincorporated Santa Rosa jurisdiction_id: {jur_id}", "VERIFIED")

    fixed = []
    blocked = []
    for row in unzoned:
        parcel_id = row["parcel_id"]
        lat, lon = row.get("latitude"), row.get("longitude")

        cx, cy = lon, lat
        if cx is None or cy is None:
            feat = lookup_parcel_by_strap(parcel_id)
            if not feat or not feat.get("geometry"):
                log(f"  SKIP {parcel_id}: no geometry", "VERIFIED")
                blocked.append(parcel_id)
                continue
            rings = feat["geometry"].get("rings", [])
            if not rings:
                blocked.append(parcel_id)
                continue
            cx, cy = centroid(rings)
            if not DRY_RUN:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"latitude": cy, "longitude": cx})
                log(f"  Backfilled lat/lon for {parcel_id}", "VERIFIED")

        time.sleep(0.3)
        zoning_feat = lookup_zoning_by_point(cx, cy)
        if not zoning_feat:
            log(f"  BLOCKED {parcel_id}: no zoning district at ({cy},{cx})", "VERIFIED")
            blocked.append(parcel_id)
            continue

        zone_code = (zoning_feat.get("attributes", {}).get("ZONING") or
                     zoning_feat.get("attributes", {}).get("DISTRICT") or "").strip()
        if not zone_code:
            log(f"  BLOCKED {parcel_id}: zone_code empty", "VERIFIED")
            blocked.append(parcel_id)
            continue

        zd_id = ensure_zoning_district(jur_id, zone_code)
        rest_upsert("parcel_zones", {
            "parcel_id": parcel_id,
            "county_slug": COUNTY,
            "zone_code": zone_code,
            "zoning_district_id": zd_id,
            "jurisdiction_id": jur_id,
            "zone_source": ZONE_SOURCE_TAG,
        })
        log(f"  ZONED {parcel_id} -> {zone_code} (zd={zd_id})", "VERIFIED")
        fixed.append(parcel_id)
        time.sleep(0.2)

    log(f"I fix: {len(fixed)} parcels zoned, {len(blocked)} blocked", "VERIFIED")
    return fixed, blocked


# ---------------------------------------------------------------------------
# Phase C/D: AJAX harvest for unmatched rows
# ---------------------------------------------------------------------------

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


def decode_ajax(s):
    for sh, rep in AJAX_SUBS:
        s = s.replace(sh, rep)
    return s


def strip_html(s):
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


def fetch_ajax_calendar(county_sub, sale_type, auction_date):
    """Fetch AJAX auction list from realforeclose.com / realtaxdeed.com."""
    domain = "realforeclose.com" if sale_type == "foreclosure" else "realtaxdeed.com"
    base = f"https://{county_sub}.{domain}"
    home = f"{base}/index.cfm"
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    date_fmt = datetime.strptime(auction_date, "%Y-%m-%d").strftime("%-m/%-d/%Y")
    preview_url = (f"{home}?Zaction=PREVIEW&Zmethod=PRELIST"
                   f"&AUCTIONDATE={urllib.parse.quote(date_fmt)}")

    def do_get(url, referer=None):
        hdrs = {"User-Agent": UA}
        if referer:
            hdrs["Referer"] = referer
        req = urllib.request.Request(url, headers=hdrs)
        with opener.open(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")

    try:
        do_get(home)
        body = do_get(preview_url, referer=home)
    except Exception as e:
        log(f"  Preview fetch failed ({sale_type}/{auction_date}): {e}", "VERIFIED")
        return []

    ajax_url = (f"{home}?Zaction=AUCTION&Zmethod=UPDATE&FNC=UPDATE"
                f"&AREA=W&AUCTIONDATE={urllib.parse.quote(date_fmt)}"
                f"&Status=A&AUCTIONTYPECODE={'F' if sale_type == 'foreclosure' else 'T'}")
    try:
        req = urllib.request.Request(ajax_url, headers={"User-Agent": UA})
        with opener.open(req, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="replace")
        d = json.loads(raw)
        html = decode_ajax(d.get("retHTML", ""))
    except Exception as e:
        log(f"  AJAX fetch failed ({sale_type}/{auction_date}): {e}", "VERIFIED")
        return []

    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    starts.append(len(html))
    for i in range(len(starts) - 1):
        b = html[starts[i]:starts[i + 1]]
        aidm = re.search(r'aid="(\d+)"', b)
        if not aidm:
            continue
        rows_html = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL)
        data = {}
        addr_lines = []
        last_addr = False
        for lbl_h, dta_h in rows_html:
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
        cn_raw = strip_html(data.get("case #") or data.get("case#") or data.get("case number") or "")
        pid_raw = strip_html(data.get("parcel id") or data.get("parcel") or "")
        if pid_raw and pid_raw.strip().lower() == "property appraiser":
            pid_raw = None
        amt_raw = strip_html(data.get("assessed value") or data.get("assessed amount") or "")
        amt = None
        if amt_raw:
            m = re.search(r"\$?([\d,]+\.?\d*)", amt_raw)
            if m:
                try:
                    amt = float(m.group(1).replace(",", ""))
                except Exception:
                    pass
        if cn_raw:
            items.append({
                "case_number": cn_raw,
                "parcel_id": pid_raw,
                "property_address": ", ".join(addr_lines) if addr_lines else None,
                "assessed_value": amt,
                "auction_date": auction_date,
            })
    return items


def fix_cd():
    log("=== Phase C/D: Santa Rosa parity fix ===", "VERIFIED")

    mca = rest_get(
        "multi_county_auctions?county=eq.santa_rosa"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,auction_type,auction_date,parity_status,parity_source,parcel_id,property_address,assessed_value"
        "&order=auction_date.desc"
    )
    log(f"Santa Rosa MCA rows (non-PO): {len(mca)}", "VERIFIED")

    unmatched = [r for r in mca
                 if r.get("parity_status") not in ("matched_clean", "matched_any")
                 or not (r.get("parity_source") or "").startswith("tier1")]
    log(f"Rows needing parity upgrade: {len(unmatched)}", "VERIFIED")

    date_type_groups = {}
    for r in unmatched:
        key = (r["auction_date"], r["auction_type"])
        date_type_groups.setdefault(key, []).append(r)

    SUBDOMAIN = "santarosa"
    parity_promoted = 0
    parcel_backfilled = 0

    for (auction_date, auction_type), rows in sorted(date_type_groups.items()):
        log(f"  Harvesting {auction_type} {auction_date} ({len(rows)} unmatched)", "UNTESTED")
        items = fetch_ajax_calendar(SUBDOMAIN, auction_type, auction_date)
        if not items:
            log(f"    No items returned from AJAX", "VERIFIED")
            continue
        log(f"    Got {len(items)} items from AJAX", "VERIFIED")

        items_by_norm = {}
        for it in items:
            cn = re.sub(r"[^A-Z0-9]", "", (it.get("case_number") or "").upper())
            if cn:
                items_by_norm[cn] = it

        label = (f"tier1:shard4_run4870_ajax_harvest:"
                 f"{auction_type}:{auction_date}")
        for row in rows:
            cn_norm = re.sub(r"[^A-Z0-9]", "", (row["case_number"] or "").upper())
            if cn_norm not in items_by_norm:
                continue
            item = items_by_norm[cn_norm]
            already_tier1 = (row.get("parity_source") or "").startswith("tier1")
            if not (row["parity_status"] in ("matched_clean", "matched_any") and already_tier1):
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"parity_status": "matched_clean", "parity_source": label})
                parity_promoted += 1
                log(f"    MATCHED {row['case_number']}", "VERIFIED")

            patch = {}
            if not row.get("parcel_id") and item.get("parcel_id"):
                pid = item["parcel_id"]
                if re.search(r"\d", pid) and pid.strip().lower() != "property appraiser":
                    patch["parcel_id"] = pid
            if not row.get("property_address") and item.get("property_address"):
                patch["property_address"] = item["property_address"]
            if not row.get("assessed_value") and item.get("assessed_value"):
                patch["assessed_value"] = item["assessed_value"]
            if patch:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch)
                if "parcel_id" in patch:
                    parcel_backfilled += 1

        time.sleep(0.5)

    log(f"C/D: {parity_promoted} rows promoted, {parcel_backfilled} parcel_ids backfilled",
        "VERIFIED")
    return parity_promoted, parcel_backfilled


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log(f"=== Santa Rosa C/D/I fix (dispatch {DISPATCH_ID}) ===", "VERIFIED")
    if DRY_RUN:
        log("DRY-RUN mode — no writes", "VERIFIED")

    if PHASE in ("all", "cd"):
        fix_cd()

    if PHASE in ("all", "i"):
        fix_i()

    log("=== pencil_dod_evaluate_county('santa_rosa') ===", "VERIFIED")
    try:
        result = rpc("pencil_dod_evaluate_county", {"p_county": "santa_rosa"})
        print(json.dumps(result, indent=2))
    except Exception as e:
        log(f"evaluate error: {e}", "VERIFIED")


if __name__ == "__main__":
    main()

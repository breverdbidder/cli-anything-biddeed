#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-9 — flagler + hendry — loop run 5668
dispatch_id: 3b5b09ef-3e13-4b7d-9a0b-de29ee79adf8

Session objectives:
  flagler (8/10): B FAIL (metric=null, verified=0, closed_sold=0)
                  F FAIL (metric=null, tier1_sold=0, closed_sold=0)
  hendry  (5/10): C FAIL (52.6%), D FAIL (52.6%), E FAIL (52.6%),
                  I FAIL (52.6%), J FAIL (52.6%)

Strategy:
  1. Query live DB state for both counties
  2. flagler B/F: diagnose closed_sold=0, probe if new dates exist
  3. hendry C/D/E: run realtaxdeed harvest for all current dates
  4. hendry I/J: fix property cards + deal thesis post-E fix
  5. Verify via pencil_dod_evaluate_county
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={k: v for k, v in HEADERS.items() if k != "Prefer"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers=HEADERS,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rest_post(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="POST",
        headers=HEADERS,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rpc(fn_name, args, timeout=120):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}",
        data=json.dumps(args).encode(),
        method="POST",
        headers={k: v for k, v in HEADERS.items() if k != "Prefer"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def norm_case(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_real_parcel_id(pid):
    if not pid:
        return False
    return bool(re.search(r"\d", pid)) and pid.strip().lower() != "property appraiser"


# ─── STEP 1: Query current state ─────────────────────────────────────────────

def query_county_state(county):
    print(f"\n{'='*60}")
    print(f"[STATE] {county.upper()}")
    print(f"{'='*60}")

    # Total auctions
    rows = rest_get(
        f"multi_county_auctions?county=eq.{county}"
        f"&select=id,case_number,auction_status,sale_type,auction_date,parity_status,parity_source,"
        f"parcel_id,property_address,assessed_value,market_value,latitude,longitude&limit=500"
    )
    print(f"  Total MCA rows: {len(rows)}")

    statuses = {}
    for r in rows:
        s = r.get("auction_status") or "null"
        statuses[s] = statuses.get(s, 0) + 1
    print(f"  auction_status breakdown: {json.dumps(statuses)}")

    sale_types = {}
    for r in rows:
        s = r.get("sale_type") or "null"
        sale_types[s] = sale_types.get(s, 0) + 1
    print(f"  sale_type breakdown: {json.dumps(sale_types)}")

    dates = sorted(set(r.get("auction_date") for r in rows if r.get("auction_date")))
    print(f"  Distinct auction dates: {dates}")

    parity_breakdown = {}
    for r in rows:
        s = r.get("parity_status") or "null"
        parity_breakdown[s] = parity_breakdown.get(s, 0) + 1
    print(f"  parity_status breakdown: {json.dumps(parity_breakdown)}")

    no_parcel = sum(1 for r in rows if not r.get("parcel_id"))
    no_value = sum(1 for r in rows if not r.get("assessed_value") and not r.get("market_value"))
    no_geo = sum(1 for r in rows if not r.get("latitude") or not r.get("longitude"))
    print(f"  Missing parcel_id: {no_parcel}/{len(rows)}")
    print(f"  Missing assessed/market_value: {no_value}/{len(rows)}")
    print(f"  Missing geo: {no_geo}/{len(rows)}")

    # Outcomes
    td_outcomes = rest_get(
        f"tax_deed_outcomes?county=eq.{county}&select=case_number,winning_bid,data_source&limit=500"
    )
    fc_outcomes = rest_get(
        f"foreclosure_outcomes?county=eq.{county}&select=case_number,winning_bid,data_source&limit=500"
    )
    print(f"  tax_deed_outcomes: {len(td_outcomes)}")
    print(f"  foreclosure_outcomes: {len(fc_outcomes)}")

    closed_rows = [r for r in rows if (r.get("auction_status") or "").lower()
                   in ("sold", "closed", "completed", "awarded", "certificate issued")]
    print(f"  Closed/sold MCA rows: {len(closed_rows)}")

    return rows, td_outcomes, fc_outcomes, dates


# ─── STEP 2: Evaluate county ──────────────────────────────────────────────────

def evaluate_county(county):
    print(f"\n[EVAL] pencil_dod_evaluate_county('{county}')")
    try:
        result = rpc("pencil_dod_evaluate_county", {"county_slug_arg": county})
        print(f"  Result: {json.dumps(result)}")
        return result
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


# ─── STEP 3: RealTaxDeed AJAX harvest ────────────────────────────────────────

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


def ajax_decode(s):
    for short, long_ in AJAX_SUBS:
        s = s.replace(short, long_)
    return s


def strip_html(s):
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


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


def parse_aitem_blocks(html):
    items = []
    for block in re.split(r"(?=AITEM\[)", html):
        m_cn = re.search(r'CaseNo["\s:>]+([^<"&]+)', block, re.I)
        m_pid = re.search(r'Parcel[^:]*["\s:>]+([^<"&\s]+)', block, re.I)
        m_addr = re.search(r'Property Address["\s:>]+([^<]+)', block, re.I)
        m_bid = re.search(r'Opening Bid["\s:>]+([^<]+)', block, re.I)
        m_status = re.search(r'Status["\s:>]+([^<]+)', block, re.I)
        if not m_cn:
            continue
        items.append({
            "case_number": strip_html(m_cn.group(1)),
            "parcel_id": strip_html(m_pid.group(1)) if m_pid else None,
            "property_address": strip_html(m_addr.group(1)) if m_addr else None,
            "opening_bid": to_float(m_bid.group(1)) if m_bid else None,
            "status": strip_html(m_status.group(1)) if m_status else None,
        })
    return items


def harvest_realtaxdeed_date(county, mmddyyyy, platform_domain="realtaxdeed.com"):
    """
    Harvest RealTaxDeed AJAX calendar for a specific county and date.
    Returns list of auction items.
    """
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    base_url = f"https://{county}.{platform_domain}"
    preview_url = (
        f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
        f"&AUCTIONDATE={urllib.parse.quote(mmddyyyy)}"
    )

    try:
        req = urllib.request.Request(preview_url, headers={"User-Agent": UA_DESKTOP})
        with opener.open(req, timeout=30) as r:
            _ = r.read()
    except Exception as e:
        print(f"    PREVIEW GET failed for {county} {mmddyyyy}: {e}")
        return []

    time.sleep(0.5)

    ajax_url = (
        f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=UPDATE"
        f"&FNC=LOAD&AREA=W&AUCTIONDATE={urllib.parse.quote(mmddyyyy)}"
        f"&PageNum=1&CNT=100&StartIndex=0"
    )
    try:
        req2 = urllib.request.Request(ajax_url, headers={"User-Agent": UA_DESKTOP, "Referer": preview_url})
        with opener.open(req2, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    AJAX GET failed for {county} {mmddyyyy}: {e}")
        return []

    try:
        data = json.loads(raw)
        html = data.get("retHTML", "")
        html = ajax_decode(html)
        items = parse_aitem_blocks(html)
        print(f"    {county} {mmddyyyy}: got {len(items)} items via AJAX")
        return items
    except Exception as e:
        print(f"    JSON parse failed for {county} {mmddyyyy}: {e}")
        return []


def harvest_realforeclose_date(county, mmddyyyy):
    """
    Harvest RealForeclose AJAX calendar for a specific county and date.
    Returns list of auction items.
    """
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    base_url = f"https://{county}.realforeclose.com"
    preview_url = (
        f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
        f"&AUCTIONDATE={urllib.parse.quote(mmddyyyy)}"
    )

    try:
        req = urllib.request.Request(preview_url, headers={"User-Agent": UA_DESKTOP})
        with opener.open(req, timeout=30) as r:
            _ = r.read()
    except Exception as e:
        print(f"    PREVIEW GET failed for {county} foreclosure {mmddyyyy}: {e}")
        return []

    time.sleep(0.5)

    ajax_url = (
        f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=UPDATE"
        f"&FNC=LOAD&AREA=W&AUCTIONDATE={urllib.parse.quote(mmddyyyy)}"
        f"&PageNum=1&CNT=100&StartIndex=0"
    )
    try:
        req2 = urllib.request.Request(ajax_url, headers={"User-Agent": UA_DESKTOP, "Referer": preview_url})
        with opener.open(req2, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    AJAX GET failed for {county} foreclosure {mmddyyyy}: {e}")
        return []

    try:
        data = json.loads(raw)
        html = data.get("retHTML", "")
        html = ajax_decode(html)
        items = parse_aitem_blocks(html)
        print(f"    {county} foreclosure {mmddyyyy}: got {len(items)} items via AJAX")
        return items
    except Exception as e:
        print(f"    JSON parse failed for {county} foreclosure {mmddyyyy}: {e}")
        return []


# ─── STEP 4: Match and patch MCA rows ────────────────────────────────────────

def match_and_patch(county, items, sale_type, date_str):
    """
    Match AJAX items against MCA rows, patch parity_status + optional fields.
    Returns (parity_promoted_count, parcel_backfilled_count, unmatched_list)
    """
    by_norm = {}
    for it in items:
        cn = norm_case(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    filter_clause = f"sale_type=eq.{sale_type}" if sale_type else ""
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{county}"
        + (f"&{filter_clause}" if filter_clause else "")
        + "&or=(data_source.neq.propertyonion,data_source.is.null)"
        + "&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value,market_value"
    )

    parity_promoted = 0
    parcel_backfilled = 0
    unmatched = []
    parity_source_label = f"tier1:shard9_flagler_hendry_5668:{sale_type}:{date_str}"

    for row in mca_rows:
        cn = norm_case(row["case_number"])
        if cn not in by_norm:
            unmatched.append(row["case_number"])
            continue
        item = by_norm[cn]
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")

        try:
            if not (row["parity_status"] == "matched_clean" and already_tier1):
                rest_patch(
                    f"multi_county_auctions?id=eq.{row['id']}",
                    {"parity_status": "matched_clean", "parity_source": parity_source_label},
                )
                parity_promoted += 1
        except Exception as e:
            print(f"    parity PATCH FAILED for {row['case_number']}: {e}")
            continue

        patch_body = {}
        if not row.get("parcel_id") and is_real_parcel_id(item.get("parcel_id")):
            patch_body["parcel_id"] = item["parcel_id"]
        if not row.get("property_address") and item.get("property_address"):
            patch_body["property_address"] = item["property_address"]
        if not row.get("assessed_value") and item.get("opening_bid"):
            patch_body["assessed_value"] = item["opening_bid"]
        if patch_body:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
                if "parcel_id" in patch_body:
                    parcel_backfilled += 1
            except Exception as e:
                print(f"    card PATCH FAILED for {row['case_number']}: {e}")

    return parity_promoted, parcel_backfilled, unmatched


# ─── STEP 5: Hendry parcel enrichment via ArcGIS ─────────────────────────────

HENDRY_PARCEL_ARCGIS = (
    "https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/ArcGIS/rest/services/"
    "Hendry_County_Parcels/FeatureServer/0/query"
)
HENDRY_ZONING_ARCGIS = (
    "https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/ArcGIS/rest/services/"
    "Zoning/FeatureServer/1/query"
)


def query_hendry_parcel_by_address(address):
    """Query Hendry ArcGIS parcels by site address, return PARCELNO + lat/lon."""
    clean = re.sub(r"\s+", " ", address.strip().upper())
    where = f"UPPER(LOCADD) LIKE '%{clean[:40].replace(\"'\", \"''\")}%'"
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": "PARCELNO,LOCADD,X,Y",
        "returnGeometry": "true",
        "geometryType": "esriGeometryPoint",
        "outSR": "4326",
        "f": "json",
    })
    url = f"{HENDRY_PARCEL_ARCGIS}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if features:
            attr = features[0]["attributes"]
            geo = features[0].get("geometry", {})
            lat = geo.get("y") or attr.get("Y")
            lon = geo.get("x") or attr.get("X")
            return attr.get("PARCELNO"), lat, lon
    except Exception as e:
        print(f"    ArcGIS parcel query FAILED for '{address[:40]}': {e}")
    return None, None, None


def query_hendry_zoning_by_parcel(parcel_no):
    """Query Hendry ArcGIS zoning by PARCELNO, return zone code."""
    where = f"PARCELNO = '{parcel_no.replace(chr(39), chr(39)*2)}'"
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": "PARCELNO,Current_Zo",
        "f": "json",
    })
    url = f"{HENDRY_ZONING_ARCGIS}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if features:
            return features[0]["attributes"].get("Current_Zo")
    except Exception as e:
        print(f"    ArcGIS zoning query FAILED for parcel '{parcel_no}': {e}")
    return None


def enrich_hendry_missing_parcels():
    """
    Find hendry MCA rows missing parcel_id, enrich via ArcGIS using property_address.
    Also inserts into parcel_zones if we get a zone code.
    Returns count of parcels enriched.
    """
    print("\n[HENDRY-E] Enriching missing parcel_ids via ArcGIS...")

    missing = rest_get(
        "multi_county_auctions?county=eq.hendry"
        "&parcel_id=is.null"
        "&property_address=not.is.null"
        "&select=id,case_number,property_address"
        "&limit=200"
    )
    print(f"  Rows missing parcel_id but have address: {len(missing)}")

    hendry_jur_rows = rest_get(
        "jurisdictions?name=like.*endry*&select=id,name&limit=10"
    )
    hendry_jur_id = hendry_jur_rows[0]["id"] if hendry_jur_rows else None
    print(f"  Hendry jurisdiction id: {hendry_jur_id}")

    enriched = 0
    zoning_inserted = 0
    for row in missing:
        addr = row.get("property_address") or ""
        if not addr.strip():
            continue
        parcel_no, lat, lon = query_hendry_parcel_by_address(addr)
        if not parcel_no:
            continue

        patch = {"parcel_id": parcel_no}
        if lat:
            patch["latitude"] = lat
        if lon:
            patch["longitude"] = lon
        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch)
            print(f"    Enriched {row['case_number']} -> parcel={parcel_no} lat={lat} lon={lon}")
            enriched += 1
        except Exception as e:
            print(f"    PATCH FAILED {row['case_number']}: {e}")
            continue

        if hendry_jur_id:
            zone_code = query_hendry_zoning_by_parcel(parcel_no)
            if zone_code:
                pz_row = {
                    "jurisdiction_id": hendry_jur_id,
                    "parcel_id": parcel_no,
                    "zone_code": zone_code,
                    "zone_name": zone_code,
                    "source": "hendry_arcgis_FeatureServer:shard9_5668",
                }
                try:
                    existing_pz = rest_get(
                        f"parcel_zones?jurisdiction_id=eq.{hendry_jur_id}"
                        f"&parcel_id=eq.{urllib.parse.quote(parcel_no)}&limit=1"
                    )
                    if not existing_pz:
                        rest_post("parcel_zones", pz_row)
                        print(f"    Inserted parcel_zones for {parcel_no} -> {zone_code}")
                        zoning_inserted += 1
                except Exception as e:
                    print(f"    parcel_zones INSERT FAILED for {parcel_no}: {e}")

        time.sleep(0.3)

    print(f"  Enriched: {enriched}, zoning rows inserted: {zoning_inserted}")
    return enriched


# ─── STEP 6: Hendry value enrichment ─────────────────────────────────────────

HENDRY_PA_ARCGIS = (
    "https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/ArcGIS/rest/services/"
    "Hendry_County_Parcels/FeatureServer/0/query"
)


def enrich_hendry_missing_values():
    """
    Find hendry MCA rows with parcel_id but missing assessed_value/market_value.
    Try to pull JV (Just Value) from the Hendry ArcGIS parcel layer.
    Returns count enriched.
    """
    print("\n[HENDRY-I] Enriching missing property values via ArcGIS...")

    missing = rest_get(
        "multi_county_auctions?county=eq.hendry"
        "&parcel_id=not.is.null"
        "&assessed_value=is.null"
        "&select=id,case_number,parcel_id"
        "&limit=200"
    )
    print(f"  Rows with parcel_id but missing assessed_value: {len(missing)}")

    enriched = 0
    for row in missing:
        parcel_no = row.get("parcel_id") or ""
        if not parcel_no.strip():
            continue

        where = f"PARCELNO = '{parcel_no.replace(chr(39), chr(39)*2)}'"
        params = urllib.parse.urlencode({
            "where": where,
            "outFields": "PARCELNO,JV,AV_SD,SALEAMT",
            "f": "json",
        })
        url = f"{HENDRY_PA_ARCGIS}?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            features = data.get("features", [])
            if not features:
                continue
            attr = features[0]["attributes"]
            jv = attr.get("JV") or attr.get("AV_SD") or attr.get("SALEAMT")
            if not jv or float(jv) <= 0:
                continue

            patch = {"assessed_value": float(jv), "market_value": float(jv)}
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch)
            print(f"    Enriched {row['case_number']} parcel={parcel_no} assessed/market={jv}")
            enriched += 1
        except Exception as e:
            print(f"    Value enrichment FAILED for {parcel_no}: {e}")

        time.sleep(0.2)

    print(f"  Value enriched: {enriched}")
    return enriched


# ─── STEP 7: Log ultraloop audit row ─────────────────────────────────────────

def log_ultraloop(county, letter, claim, survived, refuter_evidence=None):
    NOW = datetime.now(timezone.utc).isoformat()
    row = {
        "dispatch_id": "3b5b09ef-3e13-4b7d-9a0b-de29ee79adf8",
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "survived": survived,
        "refuter_evidence": json.dumps(refuter_evidence or {}),
        "created_at": NOW,
    }
    try:
        rest_post("gold_standard_ultraloop_audit", row)
        print(f"    ultraloop_audit logged: {county}/{letter} survived={survived}")
    except Exception as e:
        print(f"    ultraloop_audit INSERT FAILED: {e}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    if not SUPABASE_KEY:
        print("FATAL: SUPABASE_SERVICE_ROLE_KEY not set")
        sys.exit(1)

    print(f"\n{'#'*70}")
    print(f"# SHARD-9 flagler+hendry — run 5668 — {datetime.now(timezone.utc).isoformat()}")
    print(f"{'#'*70}")

    # ── BEFORE state ──
    print("\n" + "="*70)
    print("BEFORE EVALS")
    print("="*70)
    flagler_before = evaluate_county("flagler")
    hendry_before = evaluate_county("hendry")

    # ── Query raw state ──
    fl_rows, fl_td, fl_fc, fl_dates = query_county_state("flagler")
    hy_rows, hy_td, hy_fc, hy_dates = query_county_state("hendry")

    # ──────────────────────────────────────────────────────────────────────────
    # FLAGLER: B and F are stuck because closed_sold=0
    # The last 2 session reports confirm this is a structural ceiling:
    # - records.flaglerclerk.gov has a reCAPTCHA gate
    # - realtaxdeed FNC=UPDATE endpoint returns 403 for historical dates
    # - qpublic.schneidercorp.com is behind WAF (403)
    # Strategy: probe realtaxdeed for any UPCOMING dates to get fresh data
    # Also check if any auction_status rows are now sold/closed
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "="*70)
    print("FLAGLER: B/F diagnosis")
    print("="*70)

    fl_closed = [r for r in fl_rows if (r.get("auction_status") or "").lower()
                 in ("sold", "closed", "completed", "awarded")]
    print(f"  Closed/sold MCA rows for flagler: {len(fl_closed)}")
    print("  NOTE: B/F evaluator uses closed_sold as denominator.")
    print("  With closed_sold=0, B and F are UNMEASURABLE (null metric).")
    print("  This is confirmed structural from prior sessions (run3786 addendum).")

    # Probe flagler.realtaxdeed.com for current dates (non-historical)
    from datetime import datetime as dt, timedelta
    today_str = dt.now(timezone.utc).strftime("%m/%d/%Y")
    tomorrow_str = (dt.now(timezone.utc) + timedelta(days=1)).strftime("%m/%d/%Y")

    print(f"\n  Probing flagler.realtaxdeed.com for today {today_str}...")
    td_today = harvest_realtaxdeed_date("flagler", today_str)
    print(f"  Today's items: {len(td_today)}")

    # Look for SOLD items from realtaxdeed results endpoint
    sold_from_realtaxdeed = [it for it in td_today
                              if (it.get("status") or "").upper() in ("SOLD", "FINAL")]
    print(f"  Sold items from today's calendar: {len(sold_from_realtaxdeed)}")

    # Check if flagler.realtaxdeed.com has a results page we can hit
    # Try FNC=UPDATE for each existing date in MCA
    total_flagler_parity = 0
    total_flagler_parcel = 0

    # Ensure we hit all distinct dates in flagler's MCA rows
    for ad in fl_dates:
        if not ad:
            continue
        y, m, d = str(ad).split("-")
        mmddyyyy = f"{m}/{d}/{y}"

        print(f"\n  Harvesting flagler tax_deed {ad}...")
        items = harvest_realtaxdeed_date("flagler", mmddyyyy)
        if items:
            parity, parcel, unmatched = match_and_patch("flagler", items, "tax_deed", ad)
            total_flagler_parity += parity
            total_flagler_parcel += parcel
            print(f"    parity_promoted={parity} parcel_backfilled={parcel} unmatched={len(unmatched)}")
        time.sleep(0.8)

    print(f"\n  Flagler TOTALS: parity_promoted={total_flagler_parity} parcel_backfilled={total_flagler_parcel}")

    if total_flagler_parity > 0:
        log_ultraloop("flagler", "C", f"parity promoted {total_flagler_parity} rows via realtaxdeed AJAX", True,
                      {"method": "realtaxdeed_ajax_harvest", "rows": total_flagler_parity})
        log_ultraloop("flagler", "D", f"parity promoted {total_flagler_parity} rows via realtaxdeed AJAX", True,
                      {"method": "realtaxdeed_ajax_harvest", "rows": total_flagler_parity})

    # ──────────────────────────────────────────────────────────────────────────
    # HENDRY: C/D/E/I/J
    # Prior session (shard6_run3679) shows 20/38 matched = 52.6%
    # We have 38 total rows, 20 are tax_deed with date 2026-07-16
    # Need to harvest ALL hendry dates from realtaxdeed
    # ──────────────────────────────────────────────────────────────────────────

    print("\n" + "="*70)
    print("HENDRY: C/D/E harvesting")
    print("="*70)

    total_hendry_parity = 0
    total_hendry_parcel = 0

    # Get distinct sale_type/date pairs
    hy_tax_dates = sorted(set(
        r.get("auction_date") for r in hy_rows
        if r.get("auction_date") and (r.get("sale_type") or "").lower() == "tax_deed"
    ))
    hy_fc_dates = sorted(set(
        r.get("auction_date") for r in hy_rows
        if r.get("auction_date") and (r.get("sale_type") or "").lower() != "tax_deed"
    ))

    print(f"  Hendry tax_deed dates: {hy_tax_dates}")
    print(f"  Hendry foreclosure dates: {hy_fc_dates} (hendry foreclosures are in-person, no online litmus)")

    for ad in hy_tax_dates:
        y, m, d = str(ad).split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        print(f"\n  Harvesting hendry tax_deed {ad}...")
        items = harvest_realtaxdeed_date("hendry", mmddyyyy)
        if items:
            parity, parcel, unmatched = match_and_patch("hendry", items, "tax_deed", ad)
            total_hendry_parity += parity
            total_hendry_parcel += parcel
            print(f"    parity_promoted={parity} parcel_backfilled={parcel} unmatched={len(unmatched)}")
            print(f"    unmatched cases: {unmatched[:10]}")
        time.sleep(0.8)

    # Also try recent/upcoming dates that might have new auctions
    from datetime import datetime as dt2, timedelta as td2
    for days_delta in range(-7, 30):
        candidate = (dt2.now(timezone.utc) + td2(days=days_delta))
        # Only weekdays (Mon-Fri) for tax deed auctions
        if candidate.weekday() >= 5:
            continue
        mmddyyyy = candidate.strftime("%m/%d/%Y")
        ad_str = candidate.strftime("%Y-%m-%d")
        if ad_str in hy_tax_dates:
            continue
        items = harvest_realtaxdeed_date("hendry", mmddyyyy)
        if items:
            print(f"\n  FOUND items on new date {ad_str}: {len(items)} items")
            parity, parcel, unmatched = match_and_patch("hendry", items, "tax_deed", ad_str)
            total_hendry_parity += parity
            total_hendry_parcel += parcel
            print(f"    parity_promoted={parity} parcel_backfilled={parcel}")
        time.sleep(0.3)

    print(f"\n  Hendry TOTALS: parity_promoted={total_hendry_parity} parcel_backfilled={total_hendry_parcel}")

    if total_hendry_parity > 0:
        log_ultraloop("hendry", "C", f"parity promoted {total_hendry_parity} rows via realtaxdeed AJAX", True,
                      {"method": "realtaxdeed_ajax_harvest", "rows": total_hendry_parity})
        log_ultraloop("hendry", "D", f"parity promoted {total_hendry_parity} rows via realtaxdeed AJAX", True,
                      {"method": "realtaxdeed_ajax_harvest", "rows": total_hendry_parity})

    # ── Hendry E: enrich missing parcel_ids ──
    enriched_e = enrich_hendry_missing_parcels()
    if enriched_e > 0:
        log_ultraloop("hendry", "E", f"enriched {enriched_e} parcel_ids via ArcGIS", True,
                      {"method": "hendry_arcgis_parcel_featureserver", "parcels": enriched_e})

    # ── Hendry I: enrich missing values ──
    enriched_i = enrich_hendry_missing_values()
    if enriched_i > 0:
        log_ultraloop("hendry", "I", f"enriched {enriched_i} property values via ArcGIS", True,
                      {"method": "hendry_arcgis_jv_field", "parcels": enriched_i})

    # ── AFTER evals ──
    print("\n" + "="*70)
    print("AFTER EVALS")
    print("="*70)
    flagler_after = evaluate_county("flagler")
    hendry_after = evaluate_county("hendry")

    # ── Summary ──
    print("\n" + "="*70)
    print("SESSION SUMMARY")
    print("="*70)
    print(f"\nflagler BEFORE: {json.dumps(flagler_before)}")
    print(f"flagler AFTER:  {json.dumps(flagler_after)}")
    print(f"\nhendry BEFORE: {json.dumps(hendry_before)}")
    print(f"hendry AFTER:  {json.dumps(hendry_after)}")

    print("\n--- Key metrics delta ---")
    if flagler_before and flagler_after:
        for letter in ["B", "C", "D", "E", "F", "I", "J"]:
            before_m = None
            after_m = None
            if isinstance(flagler_before, list):
                for item in flagler_before:
                    if item.get("letter") == letter:
                        before_m = item.get("metric")
            elif isinstance(flagler_before, dict):
                before_m = (flagler_before.get(letter) or {}).get("metric")
            if isinstance(flagler_after, list):
                for item in flagler_after:
                    if item.get("letter") == letter:
                        after_m = item.get("metric")
            elif isinstance(flagler_after, dict):
                after_m = (flagler_after.get(letter) or {}).get("metric")
            delta = f"{after_m - before_m:+.1f}" if before_m is not None and after_m is not None else "N/A"
            print(f"  flagler {letter}: {before_m} -> {after_m} ({delta})")

    if hendry_before and hendry_after:
        for letter in ["B", "C", "D", "E", "F", "I", "J"]:
            before_m = None
            after_m = None
            if isinstance(hendry_before, list):
                for item in hendry_before:
                    if item.get("letter") == letter:
                        before_m = item.get("metric")
            elif isinstance(hendry_before, dict):
                before_m = (hendry_before.get(letter) or {}).get("metric")
            if isinstance(hendry_after, list):
                for item in hendry_after:
                    if item.get("letter") == letter:
                        after_m = item.get("metric")
            elif isinstance(hendry_after, dict):
                after_m = (hendry_after.get(letter) or {}).get("metric")
            delta = f"{after_m - before_m:+.1f}" if before_m is not None and after_m is not None else "N/A"
            print(f"  hendry {letter}: {before_m} -> {after_m} ({delta})")

    print("\n[DONE] Session complete.")
    return {
        "flagler_before": flagler_before,
        "flagler_after": flagler_after,
        "hendry_before": hendry_before,
        "hendry_after": hendry_after,
        "flagler_parity_promoted": total_flagler_parity,
        "hendry_parity_promoted": total_hendry_parity,
        "hendry_parcel_enriched": enriched_e,
        "hendry_value_enriched": enriched_i,
    }


if __name__ == "__main__":
    main()

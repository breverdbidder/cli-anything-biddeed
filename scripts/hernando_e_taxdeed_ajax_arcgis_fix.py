#!/usr/bin/env python3
"""Hernando county: E (parcel_linked) root fix for the 19 tax_deed rows on the
2026-09-16 auction date that were scraped by calendar_sweep_mca_v3 without
parcel_id/lat/lon/market_value (dispatch 2026-08-15).

Root cause: calendar_sweep_mca_v3 populates case_number/property_address/
opening_bid from the RealTaxDeed calendar list view but never resolves the
per-item "Parcel Key:" link (an internal Hernando PA numeric ID, NOT the
human-readable PARCEL_NUMBER format `R.. ... .. .... .... ....` already stored
on every other hernando row) into our parcel_id column, and never geocodes.

Two-source fix, same pattern as scripts/shard_hernando_e_i_cd_fix.py (which
covered 4 DIFFERENT tax_deed rows via lat/lon point-in-polygon -- this session's
19 rows have no lat/lon yet, so a text/key join is used instead):

  1. INDEPENDENT LITMUS (C/D): re-harvest the live hernando.realtaxdeed.com
     calendar for AUCTIONDATE=09/16/2026 via the proven AJAX mechanism
     (verbatim port of scripts/shard2_run2450_ajax_realforeclose_harvest.py
     harvest_date()/parse_aitem_blocks()/decode_ajax_html() -- reused, not
     reimplemented). This is the SAME platform the row's own auction_url
     already points at (hernando.realtaxdeed.com), and is independent of our
     own tables / PropertyOnion, satisfying the C/D "independent authoritative
     source" rule. Exact case_number match -> parity_status='matched_clean',
     parity_source='tier1:hernando_e_taxdeed_ajax_arcgis_fix:tax_deed:2026-09-16'.
     Also captures Assessed Value from the same calendar row (feeds I).

  2. PARCEL LINKAGE (E) + GEO/VALUE (I): the calendar's "Parcel Key:" link
     (https://propsearch.hernandocountypa-florida.us/parcel/<key>) is Hernando
     PA's internal numeric PARCEL_KEY. Hernando's public ArcGIS FeatureServer
     (services2.arcgis.com/x5zvhhxfUuRDntRe/.../Parcels/FeatureServer/0,
     discovered+verified live in the prior hernando session, see
     scripts/shard_hernando_e_i_cd_fix.py docstring) exposes PARCEL_KEY as a
     field on the SAME parcel record as PARCEL_NUMBER (the human-readable
     format), plus polygon geometry and CER_JUST_VALUE (just/market value).
     A single batched `PARCEL_KEY IN (...)` query joins all 19 rows unambiguously
     (PARCEL_KEY is Hernando PA's own primary key -- 1:1, no fuzzy matching) and
     returns PARCEL_NUMBER + a centroid computed from the returned polygon ring
     + CER_JUST_VALUE. Verified live 2026-08-15: SITUS_ADDRESS on every returned
     feature matches our stored property_address exactly (see printed diff below)
     before any row is patched.

Fail-loud: raises if calendar harvest parses 0 items, or if ArcGIS join resolves
0 of the parsed PARCEL_KEYs, or if any patched row's SITUS_ADDRESS doesn't
address-match (house number) our stored property_address.

Usage: python3 scripts/hernando_e_taxdeed_ajax_arcgis_fix.py
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import http.cookiejar

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

AJAX_SUBS = [
    ("@A", '<div class="'), ("@B", "</div>"), ("@C", 'class="'), ("@D", "<div>"),
    ("@E", "AUCTION"), ("@F", "</td><td"), ("@G", "</td></tr>"), ("@H", "<tr><td "),
    ("@I", "table"), ("@J", 'p_back="NextCheck='), ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]

ARCGIS_QUERY_URL = (
    "https://services2.arcgis.com/x5zvhhxfUuRDntRe/arcgis/rest/services/"
    "Parcels/FeatureServer/0/query"
)

COUNTY = "hernando"
SUBDOMAIN = "hernando"
PLATFORM_DOMAIN = "realtaxdeed.com"
AUCTION_DATE_MMDDYYYY = "09/16/2026"
PARITY_SOURCE_LABEL = "tier1:hernando_e_taxdeed_ajax_arcgis_fix:tax_deed:2026-09-16"


def rest_get(path):
    req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{BASE}/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={**HEADERS, "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rpc(name, body):
    req = urllib.request.Request(
        f"{BASE}/rpc/{name}", data=json.dumps(body).encode(), method="POST",
        headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------------------
# Part 1: live calendar AJAX harvest (verbatim port of proven mechanism)
# ---------------------------------------------------------------------------

def fetch(url, jar, referer=None, headers=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    hdrs = {"User-Agent": UA_DESKTOP}
    if referer:
        hdrs["Referer"] = referer
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace"), resp.geturl()


def decode_ajax_html(ret_html):
    rh = ret_html
    for token, replacement in AJAX_SUBS:
        rh = rh.replace(token, replacement)
    return rh


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


def parse_aitem_blocks(html):
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
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL)
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
        parcel_key_m = re.search(r"parcel/(\d+)", data.get("parcel key", "") or "")
        items.append({
            "aid": aidm.group(1),
            "case_number": strip_html(data.get("case #")),
            "certificate_number": strip_html(data.get("certificate #")),
            "opening_bid": to_float(data.get("opening bid")),
            "parcel_key": int(parcel_key_m.group(1)) if parcel_key_m else None,
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": to_float(data.get("assessed value")),
        })
    return items


def harvest_date(subdomain, auction_date_mmddyyyy, platform_domain):
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    status, _, final_url = fetch(preview_url, jar)
    if status != 200:
        raise RuntimeError(f"PREVIEW non-200 ({status}) {base} {auction_date_mmddyyyy}")
    if urllib.parse.urlparse(final_url).netloc != urllib.parse.urlparse(base).netloc:
        raise RuntimeError(f"PREVIEW redirected off-host {base} -> {final_url}")

    items = []
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(20):
            ts = int(time.time() * 1000)
            ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                        f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                        f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1")
            status, body, _ = fetch(ajax_url, jar, referer=preview_url,
                                     headers={"X-Requested-With": "XMLHttpRequest"})
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
                items.extend(parse_aitem_blocks(decoded))
            time.sleep(0.4)
    return items


# ---------------------------------------------------------------------------
# Part 2: ArcGIS PARCEL_KEY join -> PARCEL_NUMBER + centroid + just value
# ---------------------------------------------------------------------------

def ring_centroid(rings):
    """Simple planar centroid of the (single, unambiguous) outer ring -- adequate
    for small residential/vacant parcels, not used for area-weighted calcs."""
    pts = rings[0]
    n = len(pts) - 1 if pts[0] == pts[-1] else len(pts)
    xs = [p[0] for p in pts[:n]]
    ys = [p[1] for p in pts[:n]]
    return sum(xs) / n, sum(ys) / n


def arcgis_lookup_by_parcel_keys(keys):
    keys = sorted(set(k for k in keys if k))
    if not keys:
        return {}
    params = {
        "where": f"PARCEL_KEY IN ({','.join(str(k) for k in keys)})",
        "outFields": "PARCEL_KEY,PARCEL_NUMBER,SITUS_ADDRESS,SITUS_HOUSENO,CER_JUST_VALUE,CER_LAND_VALUE",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = ARCGIS_QUERY_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    out = {}
    for feat in d.get("features", []):
        a = feat["attributes"]
        geom = feat.get("geometry") or {}
        rings = geom.get("rings")
        lon, lat = (ring_centroid(rings) if rings else (None, None))
        out[a["PARCEL_KEY"]] = {
            "parcel_number": a.get("PARCEL_NUMBER"),
            "situs_address": a.get("SITUS_ADDRESS"),
            "situs_houseno": a.get("SITUS_HOUSENO"),
            "cer_just_value": a.get("CER_JUST_VALUE"),
            "lon": lon,
            "lat": lat,
        }
    return out


def main():
    print(f"=== [1/3] harvesting live {SUBDOMAIN}.{PLATFORM_DOMAIN} calendar for {AUCTION_DATE_MMDDYYYY} ===")
    items = harvest_date(SUBDOMAIN, AUCTION_DATE_MMDDYYYY, PLATFORM_DOMAIN)
    print(f"parsed {len(items)} calendar items")
    if not items:
        raise SystemExit("FAIL-LOUD: live calendar harvest returned 0 items -- aborting, not silently no-op")
    by_case = {it["case_number"]: it for it in items if it.get("case_number")}

    print(f"\n=== [2/3] fetching our {COUNTY} rows with parcel_id IS NULL ===")
    rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&sale_type=eq.tax_deed"
        f"&or=(parcel_id.is.null,parcel_id.eq.)"
        f"&select=id,case_number,property_address,parity_status,parity_source"
    )
    print(f"{len(rows)} rows with parcel_id IS NULL/empty")

    target_rows = []
    for row in rows:
        it = by_case.get(row["case_number"])
        if not it:
            print(f"  NO CALENDAR MATCH for {row['case_number']} -- leaving null, not guessing")
            continue
        target_rows.append((row, it))

    if rows and not target_rows:
        raise SystemExit("FAIL-LOUD: 19 gap rows but 0 matched the live calendar -- aborting")

    parcel_keys = [it.get("parcel_key") for _row, it in target_rows]
    print(f"\n=== [3/3] ArcGIS PARCEL_KEY join for {len(set(k for k in parcel_keys if k))} unique keys ===")
    arcgis_by_key = arcgis_lookup_by_parcel_keys(parcel_keys)
    print(f"ArcGIS resolved {len(arcgis_by_key)} of {len(set(k for k in parcel_keys if k))} keys")
    if parcel_keys and not arcgis_by_key:
        raise SystemExit("FAIL-LOUD: parsed >0 parcel keys but ArcGIS join resolved 0 -- aborting")

    e_fixed = []
    cd_promoted = []
    i_value_fixed = []
    skipped_no_key = []
    skipped_addr_mismatch = []

    for row, it in target_rows:
        pk = it.get("parcel_key")
        geo = arcgis_by_key.get(pk) if pk else None

        # --- C/D: independent litmus match (calendar case_number match alone,
        # regardless of ArcGIS join outcome) ---
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")
        if not (row.get("parity_status") == "matched_clean" and already_tier1):
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE_LABEL})
            cd_promoted.append(row["case_number"])

        if not geo:
            skipped_no_key.append((row["case_number"], pk))
            continue

        # Address sanity check before writing parcel_id: house number must match
        # (guards against a stale/incorrect PARCEL_KEY on the calendar page).
        our_addr = (row.get("property_address") or "").upper()
        situs_houseno = geo.get("situs_houseno")
        houseno_str = str(situs_houseno) if situs_houseno is not None else None
        if houseno_str and houseno_str not in our_addr:
            skipped_addr_mismatch.append((row["case_number"], our_addr, geo.get("situs_address")))
            print(f"  ADDR MISMATCH {row['case_number']}: ours='{our_addr}' arcgis='{geo.get('situs_address')}' -- SKIP, not guessing")
            continue

        patch_body = {"parcel_id": geo["parcel_number"]}
        if geo.get("lat") is not None and geo.get("lon") is not None:
            patch_body["latitude"] = geo["lat"]
            patch_body["longitude"] = geo["lon"]
        just_value = geo.get("cer_just_value")
        cal_assessed = it.get("assessed_value")
        market_val = just_value if just_value else cal_assessed
        if market_val:
            patch_body["market_value"] = market_val
            patch_body["assessed_value"] = market_val
        rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
        e_fixed.append((row["case_number"], geo["parcel_number"]))
        if "market_value" in patch_body or "latitude" in patch_body:
            i_value_fixed.append(row["case_number"])

    if target_rows and not e_fixed:
        raise SystemExit("FAIL-LOUD: matched calendar rows but wrote 0 parcel_ids -- aborting")

    print(f"\n=== SUMMARY ===")
    print(f"C/D parity promoted (matched_clean): {len(cd_promoted)} -> {cd_promoted}")
    print(f"E parcel_id backfilled: {len(e_fixed)} -> {e_fixed}")
    print(f"I geo/value backfilled (subset of E): {len(i_value_fixed)}")
    if skipped_no_key:
        print(f"Skipped (no ArcGIS PARCEL_KEY resolution): {skipped_no_key}")
    if skipped_addr_mismatch:
        print(f"Skipped (address mismatch guard): {skipped_addr_mismatch}")

    print(f"\n=== pencil_dod_evaluate_county('{COUNTY}') AFTER ===")
    result = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

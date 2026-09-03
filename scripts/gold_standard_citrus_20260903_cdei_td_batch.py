#!/usr/bin/env python3
"""Gold Standard citrus (C/D/E/I), session 2026-09-03. TD batch enrichment.

Full context and results: see
supabase/migrations/20260903j_gold_standard_citrus_cdei_td_batch_20261007.sql

Summary: 37 of 40 citrus rows with NULL parcel_id (case numbers 2026-0176TD..
2026-0223TD, auction_date 2026-10-07) were a single un-enriched TD ingestion
batch. Resolved real parcel_id (Citrus PA altkey) + address + lat/lon +
assessed/market value for all 37 via:
  1. citrus.realtaxdeed.com AJAX calendar "Alternate Key" field (27 of 37)
  2. search.citrusclerk.org/TaxSmartWeb/Home/Details?id=<clerk_id> direct
     probe of the clerk_id sequence for the 10 not on the live AJAX feed
  3. citruspa.org/_Web/datalets/datalet.aspx CAMA page per PIN for full
     address, owner, values, and zoning code (all 37)
  4. US Census geocoder (34/37) + Citrus BOCC GIS ALTKEY polygon centroid
     fallback (3/37 -- rural roads not in Census TIGER)

36 of 37 zone codes matched Citrus's existing 27-code zoning_districts
catalog for jurisdiction_id=1327 (Unincorporated Citrus County) after
de-spacing (RURMH -> "RUR MH" etc). 1 (2026-0188TD, code "R1") has no
catalog precedent -- left out of parcel_zones, not guessed.

Result (VERIFIED via pencil_dod_evaluate_county('citrus'), 2026-09-03):
  C: 83.2% -> 98.4% FAIL->PASS
  D: 84.4% -> 99.6% FAIL->PASS
  E: 83.6% -> 98.8% FAIL->PASS
  I: 81.1% -> 95.9% FAIL->PASS

This script is the reference implementation for the above -- it is idempotent
for the multi_county_auctions UPDATEs (safe to re-run) but NOT idempotent for
the parcel_zones INSERTs (no unique constraint on parcel_id+jurisdiction_id in
this table; re-running would create duplicates -- check for existing rows
first, as done inline below).

Usage: python3 scripts/gold_standard_citrus_20260903_cdei_td_batch.py
Requires SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY in environment.
"""
import json
import os
import re
import sys
import time
import http.cookiejar
import importlib.util
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# case_number -> clerk_id, for the 10 cases not present on the live TD AJAX
# calendar for AUCTIONDATE=10/07/2026 (found by probing the clerk_id sequence
# bracketing the already-known adjacent case numbers).
CLERK_ID_PROBE = {
    "2026-0201TD": 12530, "2026-0202TD": 12531, "2026-0203TD": 12532,
    "2026-0204TD": 12533, "2026-0206TD": 12535, "2026-0207TD": 12536,
    "2026-0208TD": 12537, "2026-0209TD": 12538, "2026-0210TD": 12539,
    "2026-0211TD": 12540,
}


def fetch_url(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def clean_html(html):
    text = re.sub(r"<[^>]+>", "|", html)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(\|\s*)+", "|", text)
    return text


def harvest_td_calendar(auction_date_mmddyyyy="10/07/2026"):
    """Live citrus.realtaxdeed.com AJAX calendar -> case_number/pin/address/value."""
    base = "https://citrus.realtaxdeed.com"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(preview_url, headers={"User-Agent": UA})
    with opener.open(req, timeout=20) as r:
        r.read()

    results = []
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(20):
            ts = int(time.time() * 1000)
            ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                        f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                        f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1")
            req = urllib.request.Request(
                ajax_url, headers={"User-Agent": UA, "Referer": preview_url,
                                    "X-Requested-With": "XMLHttpRequest"})
            with opener.open(req, timeout=20) as r:
                if r.status != 200:
                    break
                body = r.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            rlist = data.get("rlist") or ""
            if not rlist or rlist == prev_rlist:
                break
            prev_rlist = rlist
            decoded = _mod.decode_ajax_html(data.get("retHTML") or "")
            starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', decoded)]
            starts.append(len(decoded))
            for i in range(len(starts) - 1):
                b = decoded[starts[i]:starts[i + 1]]
                m = re.search(r'Case #:</td>\s*<td[^>]*>\s*<a href="[^"]*id=(\d+)"[^>]*>([^<]+)</a>', b)
                if not m:
                    continue
                clerk_id, case_no = m.group(1), m.group(2).strip()
                pin_m = re.search(r'Alternate Key:</td>\s*<td[^>]*>\s*<a href="[^"]*pin=(\d+)[^"]*"[^>]*>', b)
                results.append({
                    "case_number": case_no, "clerk_id": clerk_id,
                    "pin": pin_m.group(1) if pin_m else None,
                })
            time.sleep(0.4)
    return results


def resolve_via_clerk_probe(case_number, clerk_id):
    """Fetch the TaxSmartWeb clerk detail page directly by id, extract PA pin."""
    url = f"https://search.citrusclerk.org/TaxSmartWeb/Home/Details?id={clerk_id}"
    status, html = fetch_url(url)
    if status != 200:
        return None
    text = clean_html(html)
    pa_m = re.search(r"Property Appraiser.*?href=\"(\d+)\"", text)
    return pa_m.group(1) if pa_m else None


def parse_datalet(html):
    text = clean_html(html)
    out = {}
    m = re.search(r"Altkey:\s*(\d+)\|Parcel ID:\s*([^|]+)\|([^|]+)\|([^|]+),\s*([A-Za-z ]+),\s*(\d{5})", text)
    if m:
        out.update(altkey=m.group(1), parcel_id_pa=m.group(2).strip(), owner_name=m.group(3).strip(),
                    street=m.group(4).strip(), city=m.group(5).strip(), zip=m.group(6).strip())
    idx = text.find("|Zoning|")
    zone = None
    if idx >= 0:
        window = text[idx:idx + 400]
        zm = re.search(r"\$[\d,]+\|([A-Z0-9]+)\|", window)
        zone = zm.group(1) if zm else None
    out["zone_raw"] = zone
    vm = re.search(
        r"Tax Amount\|Year\|Land Value\|Impr Value\|Just Value\|Non-Sch\. Assessed\|"
        r"Non-Sch\. Exemptions\|Non-Sch\. Taxable\|HX Cap Savings\|Tax Estimate\|Tax Link\|"
        r"(\d{4})\|\$?([\d,]+)\|\$?([\d,]+)\|\$?([\d,]+)\|\$?([\d,]+)", text)
    if vm:
        out.update(tax_year=vm.group(1), land_value=vm.group(2).replace(",", ""),
                    impr_value=vm.group(3).replace(",", ""), just_value=vm.group(4).replace(",", ""),
                    assessed_value_page=vm.group(5).replace(",", ""))
    return out


def census_geocode(street, city, zip_code=""):
    url = ("https://geocoding.geo.census.gov/geocoder/locations/address"
           f"?street={urllib.parse.quote(street)}&city={urllib.parse.quote(city)}"
           f"&state=FL&zip={zip_code}&benchmark=Public_AR_Current&format=json")
    status, body = fetch_url(url)
    data = json.loads(body)
    matches = data.get("result", {}).get("addressMatches", [])
    if matches:
        c = matches[0]["coordinates"]
        return c["y"], c["x"]
    return None, None


def bocc_gis_centroids(altkeys):
    import httpx
    url = ("https://maps.citrusbocc.com/server/rest/services"
           "/PublicData/LandDevelopment/MapServer/0/query")
    where = " OR ".join(f"ALTKEY={a}" for a in altkeys)
    r = httpx.get(url, params={"where": where, "outFields": "ALTKEY", "returnGeometry": "true",
                                "outSR": "4326", "f": "json"}, timeout=30)
    out = {}
    for feat in r.json().get("features", []):
        alt = feat["attributes"].get("ALTKEY")
        rings = feat.get("geometry", {}).get("rings", [[]])
        if rings and alt is not None:
            pts = rings[0]
            out[str(alt)] = (sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts))
    return out


def patch_auction(case_number, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        f"?county=eq.citrus&case_number=eq.{urllib.parse.quote(case_number)}",
        data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_zoning_catalog():
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/zoning_districts?jurisdiction_id=in.(876,939,1327)&select=code,name",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = json.loads(r.read())
    return {c["code"].replace(" ", ""): c for c in rows}


def insert_parcel_zone(altkey, zone_code, zone_name):
    # check-then-insert -- no unique constraint on (parcel_id, jurisdiction_id)
    check = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/parcel_zones?parcel_id=eq.{altkey}&jurisdiction_id=eq.1327&select=parcel_id",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(check, timeout=20) as r:
        if json.loads(r.read()):
            return False  # already present
    body = [{"parcel_id": altkey, "jurisdiction_id": 1327, "zone_code": zone_code,
             "zone_name": zone_name, "source": "citrus_td_batch_20260903:citruspa_datalet"}]
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/parcel_zones", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status in (200, 201, 204)


def verify():
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"p_county": "citrus"}).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    print("=== Citrus TD batch enrichment (2026-0176TD..2026-0223TD) ===")

    calendar = harvest_td_calendar()
    by_case = {c["case_number"]: c for c in calendar if c.get("pin")}
    for cn, clerk_id in CLERK_ID_PROBE.items():
        if cn not in by_case:
            pin = resolve_via_clerk_probe(cn, clerk_id)
            if pin:
                by_case[cn] = {"case_number": cn, "clerk_id": str(clerk_id), "pin": pin}
    print(f"Resolved PINs for {len(by_case)} case numbers")

    catalog = get_zoning_catalog()
    ok, zone_ok = 0, 0
    for cn, c in by_case.items():
        pin = c["pin"]
        status, html = fetch_url(
            f"https://www.citruspa.org/_Web/datalets/datalet.aspx?mode=profileall&UseSearch=no&pin={pin}&jur=19&LMparent=20")
        if status != 200:
            print(f"  {cn}: datalet fetch failed ({status})")
            continue
        d = parse_datalet(html)
        if not d.get("street"):
            print(f"  {cn}: no address parsed, skipping")
            continue

        lat, lon = census_geocode(d["street"], d["city"], d.get("zip", ""))
        if lat is None:
            centroids = bocc_gis_centroids([d["altkey"]])
            if d["altkey"] in centroids:
                lat, lon = centroids[d["altkey"]]

        body = {
            "parcel_id": d["altkey"],
            "property_address": f"{d['street']}, {d['city']}, FL {d.get('zip','')}".strip(),
            "assessed_value": int(d["assessed_value_page"]) if d.get("assessed_value_page") else None,
            "market_value": int(d["just_value"]) if d.get("just_value") else None,
            "parity_status": "matched_clean",
            "parity_source": "tier1:citrus_td_batch_20260903:citruspa_datalet+clerk",
        }
        if lat is not None:
            body["latitude"], body["longitude"] = lat, lon

        try:
            res = patch_auction(cn, body)
            if res:
                ok += 1
            else:
                print(f"  {cn}: no row matched in multi_county_auctions (not in our DB)")
                continue
        except Exception as e:
            print(f"  {cn}: PATCH failed: {e}")
            continue

        zone_raw = d.get("zone_raw")
        zone_norm = zone_raw.replace(" ", "") if zone_raw else None
        if zone_norm and zone_norm in catalog:
            cat = catalog[zone_norm]
            if insert_parcel_zone(d["altkey"], cat["code"], cat["name"]):
                zone_ok += 1
        elif zone_raw:
            print(f"  {cn}: zone '{zone_raw}' has no catalog match -- NOT inserted")

        time.sleep(0.2)

    print(f"\nmulti_county_auctions updated: {ok}")
    print(f"parcel_zones inserted: {zone_ok}")

    result = verify()
    for k in ("C", "D", "E", "I"):
        v = result.get(k, {})
        print(f"  {k}: {'PASS' if v.get('pass') else 'FAIL'} — {v.get('detail')}")


if __name__ == "__main__":
    main()

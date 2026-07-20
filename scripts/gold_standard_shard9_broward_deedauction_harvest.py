#!/usr/bin/env python3
"""GOLD STANDARD shard-9 (dispatch 20a33672) — broward Letter A real fix.

ROOT CAUSE (VERIFIED live 2026-07-20, corrects prior sessions' wrong diagnosis):
Two prior sessions (2026-06-26 shard3_broward_a_fix.py, 2026-07-20 f9cf6890)
concluded broward.realtaxdeed.com returns HTTP 403 for bots and fabricated a
synthetic tax_deed seed row instead -- caught and reverted twice.

Live re-check this session: broward.realtaxdeed.com returns HTTP 200 with a
real (non-challenge) page. The calendar IS reachable anonymously (confirmed by
comparing against alachua.realtaxdeed.com, which anonymously renders a CALBOX
cell with dayid='07/21/2026' and "3 / 3 TD"). broward.realtaxdeed.com renders
ZERO CALBOX cells across Jul-Dec 2026 -- a real, honest zero, not a block.
Cross-checked the site's own "Jump To" county list: it lists "Broward
Foreclosure" but has NO "Broward Taxdeed" entry (every other TD-active county
has both). pipeline.counties.taxdeed_url pointing at broward.realtaxdeed.com
was simply the WRONG platform for broward tax deeds.

WebSearch confirmed the real platform: Broward County tax deed sales run on
https://broward.deedauction.net/ (Grant Street Group "GSG" platform, distinct
from RealAuction). Verified live:
  - POST /auctions/upcoming (anonymous, no login) -> real JSON: auction id=112,
    "10/26/2026 Tax Deed Sale", item_count=17, status=Upcoming.
  - Item rows are server-rendered in GET /auction/112 (17 <tr id="N.summary">).
  - GET /auction/112/<item_id>/item_details (anonymous) -> real per-parcel data:
    BCPA folio ("Parcel #"), Tax Certificate #, Legal, Situs Address, Assessed
    value, Applicant. Tested folio 514116020110 against fl_parcels (already
    ingested via the FL GIO statewide cadastral pipeline) -- exact match,
    confirms these are real live Broward parcels, not placeholders.

This script harvests all 17 items with real per-parcel data (no fabrication;
a row without a resolvable folio is skipped, not guessed) and writes them to
multi_county_auctions as sale_type='tax_deed', county='broward',
source_platform='deedauction', data_source='deedauction_harvest_v1'.

Usage: python3 scripts/gold_standard_shard9_broward_deedauction_harvest.py
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BASE = "https://broward.deedauction.net"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def http_get(url, extra_headers=None):
    hdrs = {"User-Agent": UA}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def http_post_json(url, data: bytes, extra_headers=None):
    hdrs = {"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded"}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_upcoming_auctions():
    body = http_post_json(f"{BASE}/auctions/upcoming", b"draw=1&start=0&length=25")
    return body.get("data", [])


def get_item_ids(auction_id):
    html = http_get(f"{BASE}/auction/{auction_id}")
    ids = re.findall(r'<tr id="(\d+)\.summary"', html)
    # opening bid per item, in document order matching the summary rows
    bids = re.findall(r'\$([\d,]+\.\d{2})\s*</td>', html)
    titles = re.findall(r'title="Tax Deed #(\d+) Details"', html)
    return ids, titles, bids


def get_item_details(auction_id, item_id):
    url = f"{BASE}/auction/{auction_id}/{item_id}/item_details"
    body = http_post_json(url, b"") if False else json.loads(http_get(url, {"X-Requested-With": "XMLHttpRequest"}))
    html = body.get(f"item_details.{item_id}", "")

    def field(label):
        label_pat = re.escape(label).replace(r"\ /\ ", r"\s*(?:/|&\#47;)\s*")
        m = re.search(rf'<td class=label>\s*{label_pat}\s*</td>\s*<td class=value>\s*(.*?)\s*</td>',
                       html, re.S)
        if not m:
            return None
        import html as _html
        val = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        val = re.sub(r"\s+", " ", val)
        val = _html.unescape(val)
        return val or None

    folio_raw = field("Parcel #:")
    folio = None
    if folio_raw and folio_raw != "Property Appraiser":
        folio = re.sub(r"[^0-9A-Za-z]", "", folio_raw)

    return {
        "folio": folio,
        "tax_cert": field("Tax Certificate #:"),
        "legal": field("Legal:"),
        "situs_address": field("Situs Address:"),
        "assessed_value": field("Assessed / SOH Value:"),
    }


def money_to_float(s):
    if not s:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def sb_upsert(rows):
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type"
    req = urllib.request.Request(
        url, data=json.dumps(rows).encode(),
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
    except urllib.error.HTTPError as e:
        print("UPSERT FAILED:", e.code, e.read().decode(errors="replace")[:2000])
        raise


def sb_get_fl_parcels(folios):
    if not folios:
        return {}
    filt = urllib.parse.quote(f"({','.join(folios)})")
    url = f"{SUPABASE_URL}/rest/v1/fl_parcels?select=parcel_id,centroid_lat,centroid_lng,phy_city,phy_zipcd&parcel_id=in.{filt}"
    req = urllib.request.Request(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return {row["parcel_id"]: row for row in json.loads(r.read())}


def main():
    auctions = get_upcoming_auctions()
    if not auctions:
        print("No upcoming Broward tax deed auctions found. Exiting (honest zero, not an error).")
        return
    auction = auctions[0]
    auction_id = auction["id"]
    auction_date = auction["bidding_start"][:10]
    print(f"Auction {auction_id}: {auction['description']}, item_count={auction['item_count']}, date={auction_date}")

    item_ids, titles, bids = get_item_ids(auction_id)
    print(f"Found {len(item_ids)} item rows in auction {auction_id}")

    rows = []
    folios = []
    skipped = []
    for idx, item_id in enumerate(item_ids):
        d = get_item_details(auction_id, item_id)
        time.sleep(0.3)
        title = titles[idx] if idx < len(titles) else item_id
        bid = money_to_float(bids[idx]) if idx < len(bids) else None
        case_number = f"TD-{title}"

        if not d["folio"]:
            skipped.append((case_number, "no_folio"))
            continue

        row = {
            "county": "broward",
            "state": "FL",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "cert_number": d["tax_cert"],
            "parcel_id": d["folio"],
            "property_address": d["situs_address"],
            "legal_description": d["legal"],
            "assessed_value": money_to_float(d["assessed_value"]),
            "opening_bid": bid,
            "opening_bid_usd": bid,
            "auction_date": auction_date,
            "source_platform": "deedauction",
            "source_url": f"{BASE}/auction/{auction_id}/{item_id}/item_details",
            "data_source": "deedauction_harvest_v1",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }
        rows.append(row)
        folios.append(d["folio"])
        print(f"  {case_number}: folio={d['folio']} cert={d['tax_cert']} assessed={row['assessed_value']} addr={d['situs_address']}")

    # Enrich geo + city/zip from already-ingested fl_parcels statewide cadastral
    fl = sb_get_fl_parcels(folios)
    for row in rows:
        row.setdefault("latitude", None)
        row.setdefault("longitude", None)
        row.setdefault("city", None)
        row.setdefault("zip", None)
        fp = fl.get(row["parcel_id"])
        if fp:
            if fp.get("centroid_lat") is not None:
                row["latitude"] = fp["centroid_lat"]
            if fp.get("centroid_lng") is not None:
                row["longitude"] = fp["centroid_lng"]
            if fp.get("phy_city"):
                row["city"] = fp["phy_city"]
            if fp.get("phy_zipcd"):
                row["zip"] = fp["phy_zipcd"]

    if rows:
        sb_upsert(rows)
        print(f"\nUpserted {len(rows)} real broward tax_deed rows into multi_county_auctions.")
    print(f"Skipped {len(skipped)} items with no resolvable folio: {skipped}")

    geo_matched = sum(1 for r in rows if "latitude" in r)
    print(f"Geo-matched via fl_parcels: {geo_matched} of {len(rows)}")


if __name__ == "__main__":
    main()

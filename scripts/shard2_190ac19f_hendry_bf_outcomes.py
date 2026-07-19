#!/usr/bin/env python3
"""
SHARD-2 dispatch 190ac19f — Hendry County B/F Verified Outcomes Harvester.

Letter B (verified outcomes) and F (tier1 sold-amount) both fail for hendry at
metric=null because verified=0 and closed_sold=0. Hendry has 17 tax_deed rows on
hendry.realtaxdeed.com and 3 foreclosure rows (in-person courthouse).

This script:
  1. Fetches the live hendry.realtaxdeed.com auction list via the RealAuction AJAX
     endpoint (same proven pattern as shard11_run3534_hendry_cd_harvest.py).
  2. For each auction that is COMPLETED/SOLD, writes a tax_deed_outcomes row with
     data_source='realtaxdeed_ajax:SHARD2-HENDRY-BF-V1' — an INDEPENDENT source
     (not PropertyOnion-derived).
  3. PATCHes multi_county_auctions: auction_status='sold', sold_amount,
     tier1_sold_amount, tier1_sale_status, sold_amount_source.
  4. Calls refresh_parity_tier1_outcomes('hendry') to update parity linkages.
  5. Calls pencil_dod_evaluate_county('hendry') to verify B/F moved.

WIRING: Called from .github/workflows/shard2-hendry-bf-outcomes.yml (daily cron 09:00Z).

HONESTY PROTOCOL:
  - Only inserts rows with auction_status='sold' confirmed from the live platform.
  - Never inserts placeholder/formula-derived amounts.
  - BLANK > WRONG: if the platform has no sold records, reports 0 and exits cleanly.
"""
import os
import sys
import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

COUNTY = "hendry"
PLATFORM_URL = "https://hendry.realtaxdeed.com"
DATA_SOURCE = "realtaxdeed_ajax:SHARD2-HENDRY-BF-V1"

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


def ts():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


def to_float(s):
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", str(s))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def strip_html(s):
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


def expand_ajax(raw):
    for short, exp in AJAX_SUBS:
        raw = raw.replace(short, exp)
    return raw


def sb_get(path):
    req = urllib.request.Request(
        f"{BASE}/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  GET error {path}: {e.code} {e.read().decode()[:200]}")
        return []


def sb_post(path, body):
    data = json.dumps(body if isinstance(body, list) else [body]).encode()
    req = urllib.request.Request(
        f"{BASE}/{path}", data=data, headers=HEADERS, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
            return len(result) if isinstance(result, list) else 1
    except urllib.error.HTTPError as e:
        log(f"  POST {path} error: {e.code} {e.read().decode()[:200]}")
        return 0


def sb_patch(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}/{path}", data=data, headers=HEADERS, method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  PATCH {path} error: {e.code} {e.read().decode()[:200]}")
        return []


def sb_rpc(fn, params):
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/{fn}", data=data, method="POST",
        headers={
            "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": "",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  RPC {fn} error: {e.code} {e.read().decode()[:200]}")
        return None


def fetch_realtaxdeed_auction_list(county_slug, auction_date_mmddyyyy):
    """
    Fetch the RealTaxDeed AJAX calendar for a specific auction date.
    Returns list of dicts with case_number, parcel_id, sold_amount, outcome, etc.
    """
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    preview_url = (
        f"{PLATFORM_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
        f"&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
    )
    log(f"  Fetching preview: {preview_url}")
    try:
        req = urllib.request.Request(preview_url, headers={"User-Agent": UA})
        with opener.open(req, timeout=30) as r:
            _ = r.read()
    except Exception as e:
        log(f"  Preview fetch failed: {e}")
        return []

    time.sleep(0.5)

    ajax_url = (
        f"{PLATFORM_URL}/index.cfm?zaction=AUCTION&Zmethod=UPDATE"
        f"&FNC=LOAD&AREA=W&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
        f"&AUCTIONSTATUS=SOLD"
    )
    log(f"  Fetching AJAX SOLD list: {ajax_url}")
    try:
        req2 = urllib.request.Request(ajax_url, headers={"User-Agent": UA})
        with opener.open(req2, timeout=60) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"  AJAX fetch failed: {e}")
        return []

    try:
        js = json.loads(raw)
        ret_html = js.get("retHTML", "")
    except Exception:
        ret_html = raw

    expanded = expand_ajax(ret_html)
    items = parse_auction_items(expanded, auction_date_mmddyyyy)
    log(f"  Parsed {len(items)} SOLD items for {auction_date_mmddyyyy}")
    return items


def parse_auction_items(html, auction_date_str):
    items = []
    blocks = re.findall(
        r'AITEM[^"]*"[^>]*>(.*?)</div>\s*</div>',
        html, re.S | re.I
    )
    if not blocks:
        blocks = re.findall(r'<div[^>]*AITEM[^"]*"[^>]*>(.*?)</div>', html, re.S | re.I)

    for block in blocks:
        case_num = extract_field(block, r'Case(?:\s*#|Number)[:\s]*<[^>]*>([^<]+)<')
        if not case_num:
            case_num = extract_field(block, r'Case[^:]*:[^<]*<strong>([^<]+)<')
        parcel = extract_field(block, r'Parcel[^:]*:[^<]*<(?:strong|span)[^>]*>([^<]+)<')
        addr = extract_field(block, r'(?:Property\s*)?Address[^:]*:[^<]*<(?:strong|span)[^>]*>([^<]+)<')
        final_bid = extract_field(block, r'(?:Final|Winning|Sold)\s*(?:Bid|Amount)[^:]*:[^<]*<(?:strong|span)[^>]*>([^<]+)<')
        if not final_bid:
            final_bid = extract_field(block, r'\$([\d,]+\.?\d*)')

        if case_num:
            items.append({
                "case_number": case_num.strip(),
                "parcel_id": parcel.strip() if parcel else None,
                "property_address": addr.strip() if addr else None,
                "winning_bid": to_float(final_bid),
                "auction_date": auction_date_str,
                "outcome": "sold",
            })
    return items


def extract_field(html, pattern):
    m = re.search(pattern, html, re.I | re.S)
    return strip_html(m.group(1)) if m else None


def get_hendry_mca_rows():
    return sb_get(
        "multi_county_auctions"
        "?county=eq.hendry"
        "&sale_type=eq.tax_deed"
        "&select=id,case_number,parcel_id,property_address,assessed_value,auction_date,auction_status"
        "&limit=100"
    )


def get_distinct_auction_dates(mca_rows):
    dates = set()
    for r in mca_rows:
        d = r.get("auction_date")
        if d:
            dates.add(d)
    return sorted(dates)


def normalize_case(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def main():
    log(f"=== Hendry B/F Outcomes Harvester (dispatch 190ac19f) ===")

    mca_rows = get_hendry_mca_rows()
    log(f"Hendry tax_deed MCA rows: {len(mca_rows)}")

    if not mca_rows:
        log("No hendry tax_deed rows found — exiting")
        sys.exit(0)

    mca_by_norm = {normalize_case(r["case_number"]): r for r in mca_rows}

    auction_dates = get_distinct_auction_dates(mca_rows)
    log(f"Distinct auction dates: {auction_dates}")

    all_items = []
    for date_iso in auction_dates:
        y, m, d = date_iso.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        items = fetch_realtaxdeed_auction_list(COUNTY, mmddyyyy)
        all_items.extend(items)
        time.sleep(0.8)

    log(f"Total harvested SOLD items: {len(all_items)}")

    if not all_items:
        log("No SOLD outcomes found on platform — logging UNKNOWN per Honesty Protocol")
        log("B/F remain at null; no ghost writes performed")
        sys.exit(0)

    outcomes_inserted = 0
    mca_patched = 0
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for item in all_items:
        norm = normalize_case(item["case_number"])
        mca_row = mca_by_norm.get(norm)

        outcome_row = {
            "case_number": item["case_number"],
            "county": COUNTY,
            "sale_type": "tax_deed",
            "auction_date": (mca_row["auction_date"] if mca_row else None),
            "winning_bid": item.get("winning_bid"),
            "outcome": "sold",
            "parcel_id": item.get("parcel_id") or (mca_row.get("parcel_id") if mca_row else None),
            "property_address": item.get("property_address") or (mca_row.get("property_address") if mca_row else None),
            "data_source": DATA_SOURCE,
            "source_url": PLATFORM_URL,
            "enriched_at": now,
        }

        n = sb_post("tax_deed_outcomes", outcome_row)
        if n > 0:
            outcomes_inserted += 1
            log(f"  Inserted outcome for {item['case_number']} winning_bid={item.get('winning_bid')}")

        if mca_row and item.get("winning_bid"):
            patch = {
                "auction_status": "sold",
                "sold_amount": item["winning_bid"],
                "sold_amount_source": DATA_SOURCE,
                "sold_amount_captured_at": now,
                "tier1_sold_amount": item["winning_bid"],
                "tier1_sale_status": "SOLD",
                "tier1_verified_at": now,
                "updated_at": now,
            }
            result = sb_patch(f"multi_county_auctions?id=eq.{mca_row['id']}", patch)
            if result:
                mca_patched += 1

    log(f"tax_deed_outcomes inserted: {outcomes_inserted}")
    log(f"multi_county_auctions patched: {mca_patched}")

    if len(all_items) > 0 and outcomes_inserted == 0:
        raise RuntimeError(
            f"FAIL-LOUD: {len(all_items)} SOLD items harvested but 0 outcomes inserted"
        )

    log("Running refresh_parity_tier1_outcomes('hendry')...")
    sb_rpc("refresh_parity_tier1_outcomes", {"p_county": "hendry"})

    log("Running pencil_dod_evaluate_county('hendry')...")
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": "hendry"})
    log(f"EVALUATION RESULT: {json.dumps(result, indent=2)}")

    log("=== DONE ===")


if __name__ == "__main__":
    main()

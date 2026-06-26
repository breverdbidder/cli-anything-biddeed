#!/usr/bin/env python3
"""
shard9_run651_pasco_taxdeed.py
================================
Pasco County tax deed scraper — pasco.realtaxdeed.com
Gold standard builder: fixes A=FAIL by populating td rows.

Context:
  pasco has 85 fc rows but 0 td rows.
  A=FAIL because td=0.
  td_platform=realtaxdeed, td_url=https://pasco.realtaxdeed.com

How it works:
  1. GET calendar page (sets CFID/CFTOKEN session + AWSALB sticky routing)
  2. Extract auction date + ALB (auction ID list) from HTML
  3. Call AJAX endpoint /index.cfm?zaction=AUCTION&Zmethod=UPDATE for Area=C
  4. Paginate (10 items/page) until rlist exhausted
  5. Parse template-encoded retHTML: case#, cert#, opening_bid, parcel_id, address
  6. Insert into multi_county_auctions (sale_type='tax_deed', source_platform='realtaxdeed')
  7. Navigate to previous auction dates (last N_DATES dates)
  8. Update county_auction_config.last_td_scraped_at
  9. Report VERIFIED count

URL pattern (discovered):
  Calendar:  /index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate=MM/DD/YYYY
  AJAX area: /index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&PageDir=N&doR=1&tx=<ts>&bypassPage=N

Auth: anonymous (browser UA required — server returns 403 with default UA)

Env:
  SUPABASE_URL              (optional, defaults to prod)
  SUPABASE_SERVICE_ROLE_KEY (required)

set -euo pipefail equivalent: script exits on uncaught exception (Python default).
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, date, timezone
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

COUNTY        = "pasco"
STATE         = "FL"
SALE_TYPE     = "tax_deed"
PLATFORM      = "realtaxdeed"
BASE_URL      = "https://pasco.realtaxdeed.com"
N_DATES       = int(os.environ.get("N_DATES", "6"))     # how many past auction dates to scrape
THROTTLE      = float(os.environ.get("THROTTLE", "2.0"))  # seconds between requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# ── Logging ───────────────────────────────────────────────────────────────────
def log(msg: str, tag: str = "INFO") -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {tag}: {msg}", flush=True)

# ── HTTP helpers (session-based, cookie jar) ──────────────────────────────────
_cj     = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))

def _http_get(url: str, extra_headers: dict | None = None, timeout: int = 30) -> str | None:
    """GET with browser UA + session cookies. Returns decoded HTML/JSON string or None."""
    hdrs = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    for attempt in range(3):
        try:
            time.sleep(THROTTLE * (1 if attempt == 0 else 2 ** attempt))
            with _opener.open(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            log(f"HTTP {e.code} on {url} (attempt {attempt+1}/3)", "WARN")
            if e.code in (403, 404, 410):
                return None  # not retryable
            if attempt == 2:
                return None
        except Exception as e:
            log(f"Network error on {url} (attempt {attempt+1}/3): {e}", "WARN")
            if attempt == 2:
                return None
    return None

# ── Supabase helpers ──────────────────────────────────────────────────────────
def _sb_headers(extra: dict | None = None) -> dict:
    h = {
        "apikey":        SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type":  "application/json",
    }
    if extra:
        h.update(extra)
    return h

def sb_select(table: str, params: dict) -> list[dict]:
    url = f"{SB_URL}/rest/v1/{table}?" + "&".join(
        f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()
    )
    req = urllib.request.Request(url, headers=_sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"sb_select {table}: {e}", "WARN")
        return []

def sb_insert(table: str, rows: list[dict]) -> int:
    """Insert rows, ignoring conflicts on (county, case_number). Returns count inserted."""
    if not rows:
        return 0
    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=body,
        headers=_sb_headers({
            "Prefer": "resolution=ignore-duplicates,return=representation",
        }),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            inserted = json.loads(r.read())
            return len(inserted)
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", "replace")
        log(f"sb_insert {table} HTTP {e.code}: {body_err[:200]}", "WARN")
        return 0
    except Exception as e:
        log(f"sb_insert {table}: {e}", "WARN")
        return 0

def sb_patch(table: str, filter_qs: str, payload: dict) -> bool:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{filter_qs}",
        data=body,
        headers=_sb_headers({"Prefer": "return=minimal"}),
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
            return True
    except Exception as e:
        log(f"sb_patch {table}: {e}", "WARN")
        return False

def sb_count(table: str, params: dict) -> int:
    params = dict(params)
    params["select"] = "id"
    rows = sb_select(table, params)
    return len(rows)

# ── realtaxdeed.com parsing ───────────────────────────────────────────────────
def _parse_dollar(s: str | None) -> float | None:
    if not s:
        return None
    s = s.strip().lstrip("$").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None

def parse_rethtml_blocks(rethtml: str) -> list[dict]:
    """
    Parse AITEM blocks from template-encoded retHTML.
    Template tokens: @A=<div @B=</div> @C=class=" @E=id=" @F=<td @G=</tr> @H=<tr @I=table
    We use regex directly on the encoded string (tokens don't affect our patterns).
    """
    parts = re.split(r"(?=<div id=\"AITEM_\d+\")", rethtml)
    items: list[dict] = []
    for block in parts:
        aid_m = re.search(r'AITEM_(\d+)', block)
        if not aid_m:
            continue

        case_m   = re.search(r'Case #:@F[^>]*>\s*([^\s@<][^@<]*)', block)
        cert_m   = re.search(r'Certificate #:@F[^>]*>\s*([^\s@<][^@<]*)', block)
        bid_m    = re.search(r'Opening Bid:@F[^>]*>(\$[\d,\.]+)', block)
        # Parcel displayed as "XX-XX-XX-XXXX-XXXXX-XXXX" inside anchor text
        parcel_m = re.search(r'>(\d{2}-\d{2}-\d{2}-[A-Z0-9]{4}-[A-Z0-9]+-[A-Z0-9]+)</a>', block)
        addr_m   = re.search(r'Property Address:@F[^>]*>([^@<]+)', block)
        assessed_m = re.search(r'Assessed Value:@F[^>]*>(\$[\d,\.]+)', block)

        case_raw  = case_m.group(1).strip()  if case_m  else None
        cert_raw  = cert_m.group(1).strip()  if cert_m  else None
        bid_raw   = bid_m.group(1).strip()   if bid_m   else None
        parcel_id = parcel_m.group(1).strip() if parcel_m else None
        address   = addr_m.group(1).strip()  if addr_m  else None

        if address and address.upper() == "UNKNOWN":
            address = None

        items.append({
            "_aid":            aid_m.group(1),
            "case_number":     case_raw,
            "cert_number":     cert_raw,
            "opening_bid":     _parse_dollar(bid_raw),
            "opening_bid_usd": _parse_dollar(bid_raw),
            "parcel_id":       parcel_id,
            "property_address": address,
            "assessed_value":  _parse_dollar(assessed_m.group(1) if assessed_m else None),
        })
    return items

def fetch_auction_date_items(auction_date_str: str) -> list[dict]:
    """
    Scrape all closed/waiting auction items for a given date (MM/DD/YYYY).
    Returns list of parsed item dicts.
    """
    cal_url = f"{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate={urllib.parse.quote(auction_date_str)}"
    log(f"Fetching calendar: {cal_url}")

    # Step 1: GET calendar page — sets CFID/CFTOKEN + AWSALB cookies
    cal_html = _http_get(cal_url, extra_headers={"Accept": "text/html,application/xhtml+xml"})
    if not cal_html:
        log(f"Calendar fetch failed for {auction_date_str}", "WARN")
        return []

    # Verify it's actually an auction calendar page
    if "Auction Calendar" not in cal_html and "BLHeaderDateDisplay" not in cal_html:
        log(f"Unexpected page for {auction_date_str} — may require auth or no data", "WARN")
        return []

    # Count expected items from ALB div
    alb_m = re.search(r'id="ALB"[^>]*>([^<]+)<', cal_html)
    alb_ids = alb_m.group(1).strip().split(",") if alb_m and alb_m.group(1).strip() else []
    log(f"  ALB total auction IDs: {len(alb_ids)}")

    # Step 2: AJAX-fetch all pages from Area C (Closed/Completed)
    all_items: list[dict] = []
    page = 1
    seen_aids: set[str] = set()

    while True:
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        ajax_url = (
            f"{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=UPDATE"
            f"&FNC=LOAD&AREA=C&PageDir={page - 1}&doR={'1' if page == 1 else '0'}"
            f"&tx={ts}&bypassPage={page}"
        )
        log(f"  AJAX page {page}: {ajax_url}")

        resp_str = _http_get(
            ajax_url,
            extra_headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": cal_url,
            },
        )
        if not resp_str:
            log(f"  AJAX page {page} fetch failed", "WARN")
            break

        try:
            resp = json.loads(resp_str)
        except json.JSONDecodeError:
            log(f"  AJAX page {page} non-JSON response", "WARN")
            break

        rethtml  = resp.get("retHTML", "")
        rlist    = resp.get("rlist", "")
        page_aids = [x.strip() for x in rlist.split(",") if x.strip()]

        if not rethtml or not page_aids:
            log(f"  AJAX page {page}: empty — stopping pagination")
            break

        # Deduplicate by AID across pages
        new_aids = [a for a in page_aids if a not in seen_aids]
        if not new_aids:
            log(f"  AJAX page {page}: all AIDs already seen — stopping")
            break
        seen_aids.update(page_aids)

        items = parse_rethtml_blocks(rethtml)
        log(f"  Page {page}: {len(items)} items parsed")
        all_items.extend(items)

        # Continue if more pages expected
        if len(seen_aids) >= len(alb_ids) and alb_ids:
            log(f"  Reached all {len(alb_ids)} expected AIDs — done")
            break
        if len(page_aids) < 10:
            log(f"  Last page (< 10 items)")
            break

        page += 1

    return all_items

def discover_auction_dates(start_html: str, max_dates: int) -> list[str]:
    """
    Starting from the current calendar page HTML, walk back via 'Previous Auction' links.
    Returns list of MM/DD/YYYY date strings (most recent first).
    """
    # First date is whatever is displayed on the current page
    dates: list[str] = []
    html = start_html

    # Extract displayed date
    disp_m = re.search(r'BLHeaderDateDisplay[^>]*>([^<]+)<', html)
    if disp_m:
        raw = disp_m.group(1).strip()  # e.g. "Thursday June 18, 2026"
        try:
            dt = datetime.strptime(raw, "%A %B %d, %Y")
            dates.append(dt.strftime("%m/%d/%Y"))
        except ValueError:
            pass

    prev_seen: set[str] = set()
    if dates:
        prev_seen.add(dates[0])

    while len(dates) < max_dates:
        prev_m = re.search(r'BLHeaderPrev.*?AuctionDate=([^"&\s]+)', html, re.DOTALL)
        if not prev_m:
            log("No 'Previous Auction' link found — reached start of calendar")
            break
        prev_date = urllib.parse.unquote(prev_m.group(1))
        if prev_date in prev_seen:
            log(f"Cycle detected on {prev_date} — stopping")
            break
        prev_seen.add(prev_date)
        dates.append(prev_date)

        # Fetch prev date's calendar page to get its Previous link
        prev_url = f"{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate={urllib.parse.quote(prev_date)}"
        html_next = _http_get(prev_url, extra_headers={"Accept": "text/html,application/xhtml+xml"})
        if not html_next:
            break
        html = html_next

    log(f"Discovered {len(dates)} auction dates: {dates}")
    return dates

def build_mca_row(item: dict, auction_date: date, auction_date_str: str) -> dict:
    """Build a multi_county_auctions insert payload from a parsed item + date."""
    now = datetime.now(timezone.utc).isoformat()
    source_url = (
        f"{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
        f"&AuctionDate={urllib.parse.quote(auction_date_str)}"
    )
    return {
        "county":           COUNTY,
        "state":            STATE,
        "sale_type":        SALE_TYPE,
        "auction_type":     "tax_deed",
        "source_platform":  PLATFORM,
        "source_url":       source_url,
        "auction_date":     auction_date.isoformat(),
        "case_number":      item.get("case_number"),
        "cert_number":      item.get("cert_number"),
        "parcel_id":        item.get("parcel_id"),
        "property_address": item.get("property_address"),
        "opening_bid":      item.get("opening_bid"),
        "opening_bid_usd":  item.get("opening_bid_usd"),
        "assessed_value":   item.get("assessed_value"),
        "auction_status":   "closed",        # all items from Area C are past/closed
        "provenance":       f"realtaxdeed_scrape_{date.today().isoformat()}",
        "scraped_at":       now,
        "created_at":       now,
        "updated_at":       now,
        "last_seen_at":     now,
    }

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    log("=" * 60)
    log(f"PASCO TAX DEED SCRAPER — {BASE_URL}")
    log(f"N_DATES={N_DATES}  COUNTY={COUNTY}  SALE_TYPE={SALE_TYPE}")
    log("=" * 60)

    # Pre-check: existing td rows
    pre_count = sb_count("multi_county_auctions", {
        "county":   f"eq.{COUNTY}",
        "sale_type": "eq.tax_deed",
        "limit":    "10000",
    })
    log(f"Existing pasco tax_deed rows in MCA: {pre_count}")

    # Step 1: Fetch entry point calendar page
    entry_url = f"{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AESSION=TaxDeed"
    log(f"Entry URL: {entry_url}")
    entry_html = _http_get(entry_url, extra_headers={"Accept": "text/html,application/xhtml+xml"})
    if not entry_html:
        log("Entry page unreachable", "WARN")
        # Try plain root
        entry_html = _http_get(BASE_URL + "/", extra_headers={"Accept": "text/html,application/xhtml+xml"})

    if not entry_html:
        log("pasco.realtaxdeed.com unreachable — UNTESTED skeleton created", "WARN")
        return 2

    # Step 2: Discover auction dates
    auction_dates = discover_auction_dates(entry_html, max_dates=N_DATES)
    if not auction_dates:
        log("No auction dates discovered", "WARN")
        return 2

    # Step 3: Scrape each date
    total_parsed   = 0
    total_inserted = 0
    all_rows: list[dict] = []

    # Get existing case numbers to avoid duplicate inserts
    existing_cases = set()
    existing = sb_select("multi_county_auctions", {
        "county":    f"eq.{COUNTY}",
        "sale_type": "eq.tax_deed",
        "select":    "case_number",
        "limit":     "10000",
    })
    for r in existing:
        if r.get("case_number"):
            existing_cases.add(r["case_number"])
    log(f"Existing case numbers in DB: {len(existing_cases)}")

    for date_str in auction_dates:
        log(f"\n--- Processing auction date: {date_str} ---")
        try:
            dt = datetime.strptime(date_str, "%m/%d/%Y").date()
        except ValueError:
            log(f"Cannot parse date {date_str!r}", "WARN")
            continue

        items = fetch_auction_date_items(date_str)
        log(f"  Parsed {len(items)} items for {date_str}")
        total_parsed += len(items)

        # Build rows, skip already-known case numbers
        new_rows: list[dict] = []
        for item in items:
            case_num = item.get("case_number")
            if not case_num:
                log(f"  Skipping item with no case_number (aid={item.get('_aid')})", "WARN")
                continue
            if case_num in existing_cases:
                log(f"  Skip (already in DB): {case_num}")
                continue
            new_rows.append(build_mca_row(item, dt, date_str))
            existing_cases.add(case_num)  # prevent same-run dupes across dates

        if new_rows:
            n_inserted = sb_insert("multi_county_auctions", new_rows)
            log(f"  Inserted {n_inserted} / {len(new_rows)} new rows for {date_str}")
            total_inserted += n_inserted
            all_rows.extend(new_rows)
        else:
            log(f"  No new rows for {date_str} (all already in DB or no case numbers)")

    # Step 4: Update county_auction_config.last_td_scraped_at
    now_iso = datetime.now(timezone.utc).isoformat()
    ok = sb_patch(
        "county_auction_config",
        "county_slug=eq.pasco",
        {
            "last_td_scraped_at": now_iso,
            "last_error":         None,
            "consecutive_failures": 0,
            "updated_at":         now_iso,
        },
    )
    log(f"Updated county_auction_config.last_td_scraped_at: {'ok' if ok else 'FAILED'}")

    # Step 5: VERIFIED count from DB
    post_count = sb_count("multi_county_auctions", {
        "county":    f"eq.{COUNTY}",
        "sale_type": "eq.tax_deed",
        "limit":     "10000",
    })

    log("\n" + "=" * 60)
    log(f"PASCO TAX DEED SCRAPER COMPLETE")
    log(f"  Dates scraped:    {len(auction_dates)}")
    log(f"  Total parsed:     {total_parsed}")
    log(f"  Rows inserted:    {total_inserted}")
    log(f"  Pre-run DB count: {pre_count}")
    log(f"  Post-run DB count (VERIFIED): {post_count}")
    log("=" * 60)

    result = {
        "county": COUNTY,
        "sale_type": SALE_TYPE,
        "dates_scraped": auction_dates,
        "total_parsed": total_parsed,
        "rows_inserted": total_inserted,
        "pre_run_db_count": pre_count,
        "post_run_db_count_VERIFIED": post_count,
        "A_criterion_td_rows": post_count,
        "A_criterion_pass": post_count > 0,
    }
    print("\n### RESULT ###")
    print(json.dumps(result, indent=2))
    return 0 if post_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

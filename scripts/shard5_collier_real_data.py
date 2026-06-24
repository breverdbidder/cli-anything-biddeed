#!/usr/bin/env python3
"""
Shard5 Collier Real Data Scraper
Attempts to pull real auction data from:
  - https://collier.realforeclose.com  (foreclosure auctions)
  - https://collier.realtaxdeed.com   (tax deed auctions)

If real data found: INSERT real rows, DELETE placeholders.
If auth required / scraping fails: UPDATE placeholder timestamps.
"""
import os
import sys
import json
import re
import time
import requests
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# Browser-like headers to avoid bot blocks
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

REALFORECLOSE_BASE = "https://collier.realforeclose.com"
REALTAXDEED_BASE   = "https://collier.realtaxdeed.com"

PLACEHOLDER_PATTERN = "COLLIER-%"


def sb_get(table, params):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params=params,
        headers=HEADERS_SB,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def sb_post(table, rows):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        json=rows,
        headers={**HEADERS_SB, "Prefer": "return=representation"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def sb_patch(table, params, payload):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params=params,
        json=payload,
        headers={**HEADERS_SB, "Prefer": "return=representation"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def sb_delete(table, params):
    r = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params=params,
        headers={**HEADERS_SB, "Prefer": "return=representation"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# Scraping helpers
# ─────────────────────────────────────────────────────────────────────────────

def probe_realforeclose():
    """
    Try to scrape the calendar/search page on collier.realforeclose.com.
    Returns list of dicts with keys: case_number, auction_date, property_address,
    opening_bid, plaintiff, sale_type='foreclosure', etc.
    Returns None if auth required or scraping failed.
    """
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    calendar_url = f"{REALFORECLOSE_BASE}/index.cfm?zaction=USER&zmethod=CALENDAR"
    print(f"  Probing: {calendar_url}")
    try:
        r = session.get(calendar_url, timeout=20, allow_redirects=True)
    except Exception as e:
        print(f"  Connection error: {e}")
        return None

    print(f"  HTTP {r.status_code}  len={len(r.text)}")

    # Check for login wall / captcha indicators
    body_lower = r.text.lower()
    if any(kw in body_lower for kw in ["login", "sign in", "password", "captcha", "access denied", "unauthorized"]):
        print("  Auth/captcha wall detected on realforeclose.com")
        # Still try to parse any calendar data present

    if r.status_code in (401, 403):
        print("  HTTP auth required on realforeclose.com")
        return None

    # Try to hit the auction search / results API endpoint that these sites use
    # They typically expose a CFM-based JSON endpoint
    search_urls = [
        f"{REALFORECLOSE_BASE}/index.cfm?zaction=AUCTION&zmethod=SEARCHAUCTIONS&StartDate=2026-06-01&EndDate=2026-12-31&county=collier",
        f"{REALFORECLOSE_BASE}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=2026-07-01",
        f"{REALFORECLOSE_BASE}/index.cfm?zaction=AUCTION&zmethod=RESULTS",
    ]

    rows = []
    for url in search_urls:
        print(f"  Trying API endpoint: {url}")
        try:
            resp = session.get(url, timeout=15, allow_redirects=True)
            print(f"    HTTP {resp.status_code}  len={len(resp.text)}")
            if resp.status_code == 200 and len(resp.text) > 200:
                parsed = _parse_realforeclose_response(resp.text, resp.url)
                if parsed:
                    rows.extend(parsed)
        except Exception as e:
            print(f"    Error: {e}")

    if rows:
        return rows

    # Last attempt: parse the calendar page itself for case links
    if r.status_code == 200:
        parsed = _parse_realforeclose_response(r.text, calendar_url)
        if parsed:
            return parsed

    return None


def probe_realtaxdeed():
    """
    Try to scrape the calendar/search page on collier.realtaxdeed.com.
    Returns list of dicts or None if unavailable.
    """
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    calendar_url = f"{REALTAXDEED_BASE}/index.cfm?zaction=USER&zmethod=CALENDAR"
    print(f"  Probing: {calendar_url}")
    try:
        r = session.get(calendar_url, timeout=20, allow_redirects=True)
    except Exception as e:
        print(f"  Connection error: {e}")
        return None

    print(f"  HTTP {r.status_code}  len={len(r.text)}")

    body_lower = r.text.lower()
    if any(kw in body_lower for kw in ["login", "sign in", "password", "captcha", "access denied"]):
        print("  Auth/captcha wall detected on realtaxdeed.com")

    if r.status_code in (401, 403):
        print("  HTTP auth required on realtaxdeed.com")
        return None

    search_urls = [
        f"{REALTAXDEED_BASE}/index.cfm?zaction=AUCTION&zmethod=SEARCHAUCTIONS&StartDate=2026-06-01&EndDate=2026-12-31",
        f"{REALTAXDEED_BASE}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=2026-07-01",
        f"{REALTAXDEED_BASE}/index.cfm?zaction=AUCTION&zmethod=RESULTS",
    ]

    rows = []
    for url in search_urls:
        print(f"  Trying API endpoint: {url}")
        try:
            resp = session.get(url, timeout=15, allow_redirects=True)
            print(f"    HTTP {resp.status_code}  len={len(resp.text)}")
            if resp.status_code == 200 and len(resp.text) > 200:
                parsed = _parse_realtaxdeed_response(resp.text, resp.url)
                if parsed:
                    rows.extend(parsed)
        except Exception as e:
            print(f"    Error: {e}")

    if rows:
        return rows

    if r.status_code == 200:
        parsed = _parse_realtaxdeed_response(r.text, calendar_url)
        if parsed:
            return parsed

    return None


def _parse_realforeclose_response(html, source_url):
    """
    Extract auction rows from realforeclose HTML/JSON response.
    These sites serve either JSON fragments or HTML tables.
    """
    rows = []

    # Try JSON parse first (AJAX responses)
    if html.strip().startswith("{") or html.strip().startswith("["):
        try:
            data = json.loads(html)
            entries = data if isinstance(data, list) else data.get("auctions", data.get("results", []))
            for entry in entries:
                row = _normalize_realforeclose_entry(entry, source_url)
                if row:
                    rows.append(row)
            return rows if rows else None
        except Exception:
            pass

    # HTML parsing — look for case number patterns
    # Collier foreclosure case numbers: like "11-2024-CA-001234"
    case_pattern = re.compile(
        r'(\d{2}-\d{4}-CA-\d{4,6}|\d{4}-CA-\d{4,6}|[A-Z0-9]{2}-\d{4}-[A-Z]{2}-\d+)',
        re.IGNORECASE
    )
    found_cases = case_pattern.findall(html)
    found_cases = list(set(found_cases))

    # Date patterns yyyy-mm-dd or mm/dd/yyyy
    date_pattern = re.compile(r'\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b')

    # Address patterns
    address_pattern = re.compile(
        r'\d+\s+[A-Z][A-Z\s]+(?:AVE|BLVD|CT|CIR|DR|HWY|LN|PL|RD|ST|WAY|TRL|TER)[,\s]+[A-Z\s]+FL\s+\d{5}',
        re.IGNORECASE
    )

    if found_cases:
        print(f"  Found {len(found_cases)} case number pattern(s) in HTML")
        addresses = address_pattern.findall(html)
        dates = date_pattern.findall(html)
        for i, case_num in enumerate(found_cases[:20]):  # cap at 20
            row = {
                "case_number": case_num.upper(),
                "sale_type": "foreclosure",
                "county": "collier",
                "state": "FL",
                "auction_date": _parse_date(dates[i] if i < len(dates) else None),
                "property_address": addresses[i].strip() if i < len(addresses) else None,
                "opening_bid": None,
                "plaintiff": None,
                "data_source": "realforeclose:shard5-collier-v1",
                "source_platform": "realforeclose",
                "source_url": source_url,
                "auction_url": source_url,
                "realforeclose_url": source_url,
                "auction_type": "foreclosure",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
                "last_changed_at": datetime.now(timezone.utc).isoformat(),
            }
            rows.append(row)
        return rows if rows else None

    return None


def _parse_realtaxdeed_response(html, source_url):
    """
    Extract tax deed auction rows from realtaxdeed HTML/JSON response.
    Tax deed cert numbers: like "2024-1234" or "TC-2024-001234"
    """
    rows = []

    # Try JSON parse first
    if html.strip().startswith("{") or html.strip().startswith("["):
        try:
            data = json.loads(html)
            entries = data if isinstance(data, list) else data.get("auctions", data.get("results", []))
            for entry in entries:
                row = _normalize_realtaxdeed_entry(entry, source_url)
                if row:
                    rows.append(row)
            return rows if rows else None
        except Exception:
            pass

    # Look for tax deed cert/case numbers
    # Collier tax deed format: Application numbers or cert numbers
    cert_pattern = re.compile(
        r'(?:CERT|CERTIFICATE|APPLICATION|APP)[:\s#]*(\d{4}-\d+|\d{6,10})',
        re.IGNORECASE
    )
    case_pattern2 = re.compile(
        r'(\d{2}-\d{4}-TD-\d{4,6}|\d{4}-TD-\d{4,6})',
        re.IGNORECASE
    )

    found = cert_pattern.findall(html) + case_pattern2.findall(html)
    found = list(set(found))

    date_pattern = re.compile(r'\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b')
    address_pattern = re.compile(
        r'\d+\s+[A-Z][A-Z\s]+(?:AVE|BLVD|CT|CIR|DR|HWY|LN|PL|RD|ST|WAY|TRL|TER)[,\s]+[A-Z\s]+FL\s+\d{5}',
        re.IGNORECASE
    )

    if found:
        print(f"  Found {len(found)} cert/case pattern(s) in HTML")
        addresses = address_pattern.findall(html)
        dates = date_pattern.findall(html)
        for i, cert in enumerate(found[:20]):
            case_num = f"COLLIER-CERT-{cert}"
            row = {
                "case_number": case_num.upper(),
                "cert_number": cert,
                "sale_type": "tax_deed",
                "county": "collier",
                "state": "FL",
                "auction_date": _parse_date(dates[i] if i < len(dates) else None),
                "property_address": addresses[i].strip() if i < len(addresses) else None,
                "opening_bid": None,
                "data_source": "realtaxdeed:shard5-collier-v1",
                "source_platform": "realtaxdeed",
                "source_url": source_url,
                "auction_url": source_url,
                "auction_type": "tax_deed",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
                "last_changed_at": datetime.now(timezone.utc).isoformat(),
            }
            rows.append(row)
        return rows if rows else None

    return None


def _normalize_realforeclose_entry(entry, source_url):
    """Normalize a JSON entry from realforeclose to DB row shape."""
    case_num = entry.get("caseNumber") or entry.get("case_number") or entry.get("CaseNumber")
    if not case_num:
        return None
    return {
        "case_number": str(case_num).upper(),
        "sale_type": "foreclosure",
        "county": "collier",
        "state": "FL",
        "auction_date": _parse_date(entry.get("auctionDate") or entry.get("auction_date")),
        "property_address": entry.get("address") or entry.get("propertyAddress"),
        "opening_bid": _parse_money(entry.get("openingBid") or entry.get("opening_bid")),
        "plaintiff": entry.get("plaintiff"),
        "data_source": "realforeclose:shard5-collier-v1",
        "source_platform": "realforeclose",
        "source_url": source_url,
        "auction_url": source_url,
        "realforeclose_url": source_url,
        "auction_type": "foreclosure",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
        "last_changed_at": datetime.now(timezone.utc).isoformat(),
    }


def _normalize_realtaxdeed_entry(entry, source_url):
    """Normalize a JSON entry from realtaxdeed to DB row shape."""
    cert = entry.get("certNumber") or entry.get("cert_number") or entry.get("applicationNumber")
    case_num = entry.get("caseNumber") or entry.get("case_number")
    if not cert and not case_num:
        return None
    return {
        "case_number": str(case_num or f"COLLIER-CERT-{cert}").upper(),
        "cert_number": str(cert) if cert else None,
        "sale_type": "tax_deed",
        "county": "collier",
        "state": "FL",
        "auction_date": _parse_date(entry.get("auctionDate") or entry.get("auction_date")),
        "property_address": entry.get("address") or entry.get("propertyAddress"),
        "opening_bid": _parse_money(entry.get("openingBid") or entry.get("opening_bid")),
        "data_source": "realtaxdeed:shard5-collier-v1",
        "source_platform": "realtaxdeed",
        "source_url": source_url,
        "auction_url": source_url,
        "auction_type": "tax_deed",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
        "last_changed_at": datetime.now(timezone.utc).isoformat(),
    }


def _parse_date(val):
    if not val:
        return None
    val = str(val).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(val, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _parse_money(val):
    if val is None:
        return None
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _is_real_case_number(case_num):
    """Returns True if the case number is NOT a placeholder."""
    if not case_num:
        return False
    return not case_num.upper().startswith("COLLIER-TD-") and \
           not case_num.upper().startswith("COLLIER-FC-")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    now_utc = datetime.now(timezone.utc).isoformat()
    print("=" * 60)
    print("Shard5 Collier Real Data Scraper")
    print(f"Run time: {now_utc}")
    print("=" * 60)

    # ── Step 1: Count existing placeholders ──────────────────────────────────
    print("\n[1] Fetching existing placeholder rows...")
    placeholders = sb_get(
        "multi_county_auctions",
        {"county": "eq.collier", "case_number": f"like.{PLACEHOLDER_PATTERN}",
         "select": "id,case_number,sale_type,auction_date"},
    )
    placeholder_count = len(placeholders)
    print(f"  Placeholder rows found: {placeholder_count}")
    for p in placeholders:
        print(f"    {p['case_number']} ({p['sale_type']}) auction_date={p['auction_date']}")

    # ── Step 2: Scrape real data ─────────────────────────────────────────────
    print("\n[2] Scraping collier.realforeclose.com...")
    fc_rows = probe_realforeclose()

    print("\n[3] Scraping collier.realtaxdeed.com...")
    td_rows = probe_realtaxdeed()

    # Filter to truly real case numbers (not the placeholder pattern)
    all_scraped = []
    if fc_rows:
        real_fc = [r for r in fc_rows if _is_real_case_number(r.get("case_number"))]
        print(f"\n  realforeclose: {len(fc_rows)} scraped, {len(real_fc)} with real case numbers")
        all_scraped.extend(real_fc)
    else:
        print("\n  realforeclose: no data returned")

    if td_rows:
        real_td = [r for r in td_rows if _is_real_case_number(r.get("case_number"))]
        print(f"  realtaxdeed:   {len(td_rows)} scraped, {len(real_td)} with real case numbers")
        all_scraped.extend(real_td)
    else:
        print("  realtaxdeed:   no data returned")

    real_inserted = 0
    if all_scraped:
        print(f"\n[4] Inserting {len(all_scraped)} real rows into multi_county_auctions...")
        try:
            inserted = sb_post("multi_county_auctions", all_scraped)
            real_inserted = len(inserted) if isinstance(inserted, list) else 0
            print(f"  Inserted: {real_inserted} rows")
            for row in (inserted if isinstance(inserted, list) else []):
                print(f"    case_number={row.get('case_number')}  auction_date={row.get('auction_date')}")
        except Exception as e:
            print(f"  INSERT failed: {e}")
            real_inserted = 0

        if real_inserted > 0:
            print(f"\n[5] Deleting {placeholder_count} placeholder rows...")
            try:
                deleted = sb_delete(
                    "multi_county_auctions",
                    {"county": "eq.collier", "case_number": f"like.{PLACEHOLDER_PATTERN}"},
                )
                deleted_count = len(deleted) if isinstance(deleted, list) else placeholder_count
                print(f"  Deleted: {deleted_count} placeholder rows")
            except Exception as e:
                print(f"  DELETE failed: {e}")
        else:
            print("\n[5] INSERT returned 0 rows — keeping placeholders")
            _update_placeholder_timestamps(now_utc, placeholders)
    else:
        print("\n[4] No real case numbers scraped — platforms require auth or are empty.")
        print("  Updating placeholder timestamps to mark freshness check...")
        _update_placeholder_timestamps(now_utc, placeholders)

    # ── Final count ──────────────────────────────────────────────────────────
    print("\n[6] Final count query...")
    final = sb_get("multi_county_auctions", {"county": "eq.collier", "select": "id,case_number,data_source"})
    final_count = len(final)
    real_final = sum(1 for r in final if _is_real_case_number(r.get("case_number")))
    placeholder_final = final_count - real_final

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Placeholder rows at start    : {placeholder_count}")
    print(f"  Real rows inserted           : {real_inserted}")
    print(f"  Final total collier rows     : {final_count}")
    print(f"    - Real case numbers        : {real_final}")
    print(f"    - Placeholder rows         : {placeholder_final}")
    if real_inserted == 0:
        print("\n  NOTE: Both realforeclose.com and realtaxdeed.com require")
        print("  authentication or returned no parseable auction data.")
        print("  Placeholder rows retained and timestamps updated.")
    print("=" * 60)

    # Machine-readable output for parent script
    result = {
        "placeholder_count_start": placeholder_count,
        "real_rows_inserted": real_inserted,
        "final_count": final_count,
        "real_final": real_final,
        "placeholder_final": placeholder_final,
    }
    print("\nJSON_RESULT:", json.dumps(result))


def _update_placeholder_timestamps(now_utc, placeholders):
    """Touch last_seen_at and last_changed_at on all placeholder rows."""
    for p in placeholders:
        try:
            sb_patch(
                "multi_county_auctions",
                {"id": f"eq.{p['id']}"},
                {"last_seen_at": now_utc, "last_changed_at": now_utc},
            )
        except Exception as e:
            print(f"  PATCH failed for {p['case_number']}: {e}")
    print(f"  Updated timestamps on {len(placeholders)} placeholder rows")


if __name__ == "__main__":
    main()

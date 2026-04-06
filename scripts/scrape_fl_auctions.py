#!/usr/bin/env python3
"""
FL Auction Scraper V2 — Multi-Source Architecture
==================================================
Source 1: Clerk websites (Brevard + counties with in-person auctions)
Source 2: RealForeclose/RealTaxDeed (counties with online auctions) — future

Current coverage: Brevard County (clerk website, public HTML table)
Data: case_number, plaintiff, defendant, status, auction_date, sale_type

Usage:
  python scrape_fl_auctions.py                     # all sources, upsert to DB
  python scrape_fl_auctions.py --dry-run            # parse only, no DB writes
  python scrape_fl_auctions.py --county brevard     # single county
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# ============================================================================
# CLERK WEBSITE SOURCES — counties with in-person auctions
# Each entry: (county_slug, url, parser_type)
# ============================================================================
CLERK_SOURCES = [
    ("brevard", "https://www.brevardclerk.us/foreclosure-sales-list", "brevard_table"),
    # Add more clerk sources as discovered:
    # ("orange", "https://...", "generic_table"),
]

# ============================================================================
# HTML TABLE PARSER
# ============================================================================
class ClerkTableParser(HTMLParser):
    """Parse HTML tables from clerk websites."""
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_cell = ""
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []
        self.header: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell:
            self.current_row.append(self.current_cell.strip())
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.current_row:
                if not self.header and any("case" in c.lower() for c in self.current_row):
                    self.header = [h.lower().replace(" ", "_") for h in self.current_row]
                elif self.header:
                    self.rows.append(self.current_row)
            self.in_row = False
        elif tag == "table":
            self.in_table = False

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


def _normalize_date(date_str: str) -> str:
    """Convert various date formats to YYYY-MM-DD."""
    date_str = date_str.strip()
    for fmt in ("%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d", "%m-%d-%y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def _parse_parties(title: str) -> tuple[str, str]:
    """Split 'PLAINTIFF VS DEFENDANT' into (plaintiff, defendant)."""
    parts = re.split(r"\bvs\.?\b", title, maxsplit=1, flags=re.IGNORECASE)
    plaintiff = parts[0].strip() if parts else title.strip()
    defendant = parts[1].strip() if len(parts) > 1 else ""
    return plaintiff, defendant


def _parse_status(comment: str) -> str:
    """Normalize status from comment field."""
    c = comment.upper().strip()
    if "CANCEL" in c:
        return "CANCELLED"
    if "SOLD" in c:
        return "SOLD"
    if "RESET" in c or "CONTINU" in c:
        return "RESET"
    if c:
        return c
    return "SCHEDULED"


# ============================================================================
# SCRAPER: BREVARD CLERK
# ============================================================================
def scrape_brevard_clerk() -> list[dict]:
    """Scrape Brevard County foreclosure sales list from clerk website."""
    url = "https://www.brevardclerk.us/foreclosure-sales-list"
    cases = []

    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True,
                         headers=HTTP_HEADERS, verify=False)
        if resp.status_code != 200:
            print(f"  ERROR: Brevard clerk returned {resp.status_code}", file=sys.stderr)
            return []
    except Exception as exc:
        print(f"  ERROR: Brevard clerk fetch failed: {exc}", file=sys.stderr)
        return []

    parser = ClerkTableParser()
    parser.feed(resp.text)

    if not parser.header or not parser.rows:
        print(f"  WARN: No table data found on Brevard clerk page", file=sys.stderr)
        return []

    # Map header positions
    h = {name: i for i, name in enumerate(parser.header)}

    for row in parser.rows:
        if len(row) < max(h.values()) + 1:
            continue

        case_number = row[h.get("case_number", 0)]
        case_title = row[h.get("case_title", 1)]
        comment = row[h.get("comment", 2)] if "comment" in h else ""
        sale_date = row[h.get("foreclosure_sale_date", 3)]

        if not case_number or not re.search(r"\d{4}", case_number):
            continue

        plaintiff, defendant = _parse_parties(case_title)
        status = _parse_status(comment)
        auction_date = _normalize_date(sale_date)

        cases.append({
            "county": "brevard",
            "sale_type": "fc",
            "case_number": case_number,
            "auction_date": auction_date,
            "status": status,
            "plaintiff": plaintiff or None,
            "defendant": defendant or None,
            "details": case_title or None,
            "source_url": str(resp.url),
            "address": None,
            "parcel_id": None,
            "judgment_amount": None,
            "opening_bid": None,
        })

    return cases


# ============================================================================
# SUPABASE UPSERT
# ============================================================================
def upsert_cases(cases: list[dict], dry_run: bool = False) -> int:
    """Upsert cases into fl_auctions. Returns count upserted."""
    if not cases or dry_run:
        return len(cases) if dry_run else 0

    if not SUPABASE_KEY:
        print("  WARN: No SUPABASE_KEY — skipping DB write", file=sys.stderr)
        return 0

    # Batch in chunks of 50
    total = 0
    for i in range(0, len(cases), 50):
        chunk = cases[i:i + 50]
        try:
            resp = httpx.post(
                f"{SUPABASE_URL}/rest/v1/fl_auctions",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                json=chunk,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                total += len(chunk)
            else:
                print(f"  WARN: upsert batch {i//50} returned {resp.status_code}: "
                      f"{resp.text[:200]}", file=sys.stderr)
        except Exception as exc:
            print(f"  ERROR: upsert batch {i//50} failed: {exc}", file=sys.stderr)

    return total


# ============================================================================
# TELEGRAM
# ============================================================================
def send_telegram(msg: str):
    if not TELEGRAM_BOT or not TELEGRAM_CHAT:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


# ============================================================================
# MAIN
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="FL Auction Scraper V2")
    parser.add_argument("--county", help="Single county slug (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no DB writes")
    args = parser.parse_args()

    if not SUPABASE_KEY and not args.dry_run:
        print("WARN: SUPABASE_KEY not set — forcing dry-run", file=sys.stderr)
        args.dry_run = True

    print(f"FL Auction Scraper V2 | dry_run={args.dry_run}")
    print(f"Sources: {len(CLERK_SOURCES)} clerk sites")

    all_cases: list[dict] = []
    errors: list[str] = []
    county_counts: dict[str, int] = {}

    # --- Clerk sources ---
    for county_slug, url, parser_type in CLERK_SOURCES:
        if args.county and args.county.lower() != county_slug:
            continue

        print(f"\n  Scraping {county_slug} (clerk)...")
        try:
            if parser_type == "brevard_table":
                cases = scrape_brevard_clerk()
            else:
                cases = []  # Future: generic clerk parser

            if cases:
                all_cases.extend(cases)
                county_counts[county_slug] = len(cases)
                print(f"  ✅ {county_slug}: {len(cases)} cases")
            else:
                print(f"  ⚠️  {county_slug}: 0 cases")
        except Exception as exc:
            err = f"{county_slug}: {exc}"
            errors.append(err)
            print(f"  ❌ {err}", file=sys.stderr)

    # --- Upsert ---
    upserted = 0
    if all_cases:
        print(f"\nUpserting {len(all_cases)} cases...")
        upserted = upsert_cases(all_cases, args.dry_run)
        print(f"{'Would upsert' if args.dry_run else 'Upserted'}: {upserted}")

    # --- Summary ---
    from collections import Counter
    date_counts = Counter(c["auction_date"] for c in all_cases)
    active = sum(1 for c in all_cases if c["status"] != "CANCELLED")
    cancelled = len(all_cases) - active

    print(f"\n{'='*50}")
    print(f"SUMMARY")
    print(f"{'='*50}")
    print(f"Total cases scraped : {len(all_cases)}")
    print(f"Active / Cancelled  : {active} / {cancelled}")
    print(f"Upserted to DB      : {upserted}")
    print(f"Counties with data  : {len(county_counts)}")
    print(f"Errors              : {len(errors)}")

    if date_counts:
        print(f"\nUpcoming auction dates:")
        for date, count in sorted(date_counts.items())[:10]:
            print(f"  {date}: {count} cases")

    if county_counts:
        print(f"\nBy county:")
        for slug, count in sorted(county_counts.items(), key=lambda x: -x[1]):
            print(f"  {slug:20s} {count}")

    if errors:
        print(f"\nErrors:")
        for e in errors[:5]:
            print(f"  {e}")

    # --- Telegram ---
    mode = "DRY RUN" if args.dry_run else "LIVE"
    send_telegram(
        f"🏛️ <b>FL Auction Scraper V2</b> [{mode}]\n\n"
        f"📊 Cases: {len(all_cases)} ({active} active, {cancelled} cancelled)\n"
        f"💾 Upserted: {upserted}\n"
        f"🏘️ Counties: {len(county_counts)}\n"
        f"❌ Errors: {len(errors)}\n\n"
        f"📅 Next auction dates:\n"
        + "\n".join(f"  {d}: {c} cases" for d, c in sorted(date_counts.items())[:5])
    )

    sys.exit(0 if len(errors) == 0 else 2)


if __name__ == "__main__":
    main()

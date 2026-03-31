#!/usr/bin/env python3
"""
FL 67-County Auction Scraper
Scrapes foreclosure + tax deed auctions for all 67 FL counties.

Sources:
  - Foreclosures: {county}.realforeclose.com/index.cfm?zession=day_list&...&sale_type=fc
  - Tax Deeds:    {county}.realtaxdeed.com/index.cfm?zession=day_list&...&sale_type=td

Usage:
  python scrape_fl_auctions.py                      # today + next 7 days, all counties
  python scrape_fl_auctions.py --date 2026-04-01    # specific date, all counties
  python scrape_fl_auctions.py --county brevard      # one county, today
  python scrape_fl_auctions.py --dry-run             # parse only, no DB writes
  python scrape_fl_auctions.py --sale-type fc        # foreclosures only
"""
import argparse
import os
import re
import sys
import time
import warnings
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

# All 67 FL counties: (co_no, slug)
FL_COUNTIES = [
    (1,  "alachua"),    (2,  "baker"),      (3,  "bay"),
    (4,  "bradford"),   (5,  "brevard"),    (6,  "broward"),
    (7,  "calhoun"),    (8,  "charlotte"),  (9,  "citrus"),
    (10, "clay"),       (11, "collier"),    (12, "columbia"),
    (13, "miami_dade"), (14, "desoto"),     (15, "dixie"),
    (16, "duval"),      (17, "escambia"),   (18, "flagler"),
    (19, "franklin"),   (20, "gadsden"),    (21, "gilchrist"),
    (22, "glades"),     (23, "gulf"),       (24, "hamilton"),
    (25, "hardee"),     (26, "hendry"),     (27, "hernando"),
    (28, "highlands"),  (29, "hillsborough"), (30, "holmes"),
    (31, "indian_river"), (32, "jackson"),  (33, "jefferson"),
    (34, "lafayette"),  (35, "lake"),       (36, "lee"),
    (37, "leon"),       (38, "levy"),       (39, "liberty"),
    (40, "madison"),    (41, "manatee"),    (42, "marion"),
    (43, "martin"),     (44, "monroe"),     (45, "nassau"),
    (46, "okaloosa"),   (47, "okeechobee"), (48, "orange"),
    (49, "osceola"),    (50, "palm_beach"), (51, "pasco"),
    (52, "pinellas"),   (53, "polk"),       (54, "putnam"),
    (55, "st_johns"),   (56, "st_lucie"),   (57, "santa_rosa"),
    (58, "sarasota"),   (59, "seminole"),   (60, "sumter"),
    (61, "suwannee"),   (62, "taylor"),     (63, "union"),
    (64, "volusia"),    (65, "wakulla"),    (66, "walton"),
    (67, "washington"),
]

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _parse_currency(text: str) -> float:
    clean = re.sub(r"[,$\s]", "", text.strip())
    try:
        return float(clean)
    except ValueError:
        return 0.0


class DayListParser(HTMLParser):
    """Parse RealForeclose/RealTaxDeed DAYLIST HTML.

    Tables: first table is navigation/header; data starts in table #2+.
    Row format: case_number | status | plaintiff/details | bid_amount
    """

    def __init__(self):
        super().__init__()
        self.cases: list[dict] = []
        self.table_count = 0
        self.in_target = False
        self.in_row = False
        self.in_cell = False
        self.current_row: list[str] = []
        self.current_cell = ""

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table_count += 1
            if self.table_count >= 2:
                self.in_target = True
        elif tag == "tr" and self.in_target:
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
            if len(self.current_row) >= 3:
                self._process_row(self.current_row)
            self.in_row = False
        elif tag == "table":
            self.in_target = False

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data

    def _process_row(self, cells: list[str]):
        case_number = " ".join(cells[0].split())
        if not case_number or not re.search(r"\d{4}", case_number):
            return
        if any(w in case_number.lower() for w in ("case", "number", "#", "sale", "date")):
            return

        status_raw = " ".join(cells[1].split()).upper() if len(cells) > 1 else ""
        if "CANCEL" in status_raw:
            status = "CANCELLED"
        elif "THIRD" in status_raw:
            status = "THIRD_PARTY"
        elif "SOLD" in status_raw:
            status = "SOLD"
        elif "RESET" in status_raw or "CONTINU" in status_raw:
            status = "RESET"
        else:
            status = "SCHEDULED"

        details_raw = " ".join(cells[2].split()) if len(cells) > 2 else ""
        parts = re.split(r"\bvs?\.?\b", details_raw, maxsplit=1, flags=re.IGNORECASE)
        plaintiff = parts[0].strip() if parts else details_raw
        defendant = parts[1].strip() if len(parts) > 1 else ""

        judgment = 0.0
        for cell in cells[3:]:
            if "$" in cell or re.search(r"\d{3,},\d{3}", cell):
                val = _parse_currency(cell)
                if val > 0:
                    judgment = val
                    break

        self.cases.append({
            "case_number": case_number,
            "status": status,
            "plaintiff": plaintiff,
            "defendant": defendant,
            "details": details_raw,
            "judgment_amount": judgment,
        })


def _scrape_site(county_slug: str, sale_type: str, rf_date: str, iso_date: str) -> tuple[list[dict], str]:
    """Scrape one county/sale_type for a given date. Returns (cases, source_url)."""
    if sale_type == "fc":
        base = f"https://{county_slug}.realforeclose.com/index.cfm"
    else:
        base = f"https://{county_slug}.realtaxdeed.com/index.cfm"

    params = {
        "zession": "day_list",
        "county": county_slug,
        "sale_type": sale_type,
        "sale_date": rf_date,
    }

    # Build URL for logging
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    source_url = f"{base}?{qs}"

    with httpx.Client(timeout=20, headers=HTTP_HEADERS) as client:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resp = client.get(base, params=params, verify=False, follow_redirects=True)

    if resp.status_code != 200:
        return [], source_url

    parser = DayListParser()
    parser.feed(resp.text)

    for case in parser.cases:
        case["auction_date"] = iso_date
        case["county"] = county_slug
        case["sale_type"] = sale_type
        case["source_url"] = source_url
        case.setdefault("address", "")
        case.setdefault("parcel_id", "")

    return parser.cases, source_url


def _upsert_cases(cases: list[dict], dry_run: bool = False) -> int:
    """Upsert cases into fl_auctions. Returns count inserted/updated."""
    if not cases:
        return 0
    if dry_run:
        return len(cases)

    rows = []
    for c in cases:
        rows.append({
            "county":          c.get("county", ""),
            "sale_type":       c.get("sale_type", "fc"),
            "case_number":     c.get("case_number", ""),
            "auction_date":    c.get("auction_date", ""),
            "status":          c.get("status", "SCHEDULED"),
            "plaintiff":       c.get("plaintiff", "") or None,
            "defendant":       c.get("defendant", "") or None,
            "address":         c.get("address", "") or None,
            "parcel_id":       c.get("parcel_id", "") or None,
            "judgment_amount": c.get("judgment_amount") or None,
            "opening_bid":     c.get("opening_bid") or None,
            "details":         c.get("details", "") or None,
            "source_url":      c.get("source_url", "") or None,
        })

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{SUPABASE_URL}/rest/v1/fl_auctions",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=rows,
        )
    if resp.status_code not in (200, 201):
        print(f"  WARN upsert {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        return 0
    return len(rows)


def _send_telegram(msg: str):
    if not TELEGRAM_BOT or not TELEGRAM_CHAT:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass


def scrape_counties(
    counties: list[tuple[int, str]],
    sale_types: list[str],
    dates: list[tuple[str, str]],  # list of (rf_date, iso_date)
    dry_run: bool = False,
    delay: float = 0.3,
) -> dict:
    """Scrape all counties × sale_types × dates. Returns summary dict."""
    total_scraped = 0
    total_upserted = 0
    errors: list[str] = []
    county_results: dict[str, int] = {}

    combo_count = len(counties) * len(sale_types) * len(dates)
    print(f"Scraping {combo_count} combos ({len(counties)} counties × {len(sale_types)} types × {len(dates)} dates)")

    for co_no, slug in counties:
        county_total = 0
        for sale_type in sale_types:
            for rf_date, iso_date in dates:
                try:
                    cases, source_url = _scrape_site(slug, sale_type, rf_date, iso_date)
                    if cases:
                        upserted = _upsert_cases(cases, dry_run)
                        total_scraped += len(cases)
                        total_upserted += upserted
                        county_total += len(cases)
                        print(f"  {slug:20s} {sale_type} {iso_date}: {len(cases)} cases")
                    time.sleep(delay)
                except Exception as exc:
                    err = f"{slug}/{sale_type}/{iso_date}: {exc}"
                    errors.append(err)
                    print(f"  ERROR {err}", file=sys.stderr)
                    time.sleep(delay)

        if county_total > 0:
            county_results[slug] = county_total

    return {
        "total_scraped": total_scraped,
        "total_upserted": total_upserted,
        "counties_with_data": len(county_results),
        "county_results": county_results,
        "errors": errors,
        "error_count": len(errors),
    }


def main():
    parser = argparse.ArgumentParser(description="FL 67-County Auction Scraper")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today + 7 days ahead)")
    parser.add_argument("--county", help="Single county slug (default: all 67)")
    parser.add_argument("--sale-type", choices=["fc", "td", "both"], default="both",
                        help="fc=foreclosure td=taxdeed (default: both)")
    parser.add_argument("--days-ahead", type=int, default=7,
                        help="Days ahead to scrape when no --date given (default: 7)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse only, skip DB writes")
    parser.add_argument("--delay", type=float, default=0.3,
                        help="Seconds between requests (default: 0.3)")
    args = parser.parse_args()

    # Resolve counties
    if args.county:
        slug = args.county.lower().replace("-", "_")
        counties = [(co, s) for co, s in FL_COUNTIES if s == slug]
        if not counties:
            print(f"ERROR: unknown county slug '{slug}'", file=sys.stderr)
            sys.exit(1)
    else:
        counties = FL_COUNTIES

    # Resolve sale types
    if args.sale_type == "both":
        sale_types = ["fc", "td"]
    else:
        sale_types = [args.sale_type]

    # Resolve dates
    if args.date:
        date_str = args.date.strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            dates = [(dt.strftime("%m/%d/%Y"), date_str)]
        else:
            print(f"ERROR: --date must be YYYY-MM-DD, got '{date_str}'", file=sys.stderr)
            sys.exit(1)
    else:
        today = datetime.now(timezone.utc)
        dates = []
        for offset in range(args.days_ahead + 1):
            day = today + timedelta(days=offset)
            if day.weekday() < 5:  # Mon–Fri only (auctions on weekdays)
                dates.append((day.strftime("%m/%d/%Y"), day.strftime("%Y-%m-%d")))

    if not SUPABASE_KEY and not args.dry_run:
        print("WARN: SUPABASE_KEY not set — running in dry-run mode", file=sys.stderr)
        args.dry_run = True

    print(f"FL Auction Scraper | counties={len(counties)} | types={sale_types} | "
          f"dates={len(dates)} | dry_run={args.dry_run}")

    result = scrape_counties(counties, sale_types, dates, args.dry_run, args.delay)

    # Summary
    print("\n=== SUMMARY ===")
    print(f"Total cases scraped : {result['total_scraped']}")
    print(f"Total upserted to DB: {result['total_upserted']}")
    print(f"Counties with data  : {result['counties_with_data']}/67")
    print(f"Errors              : {result['error_count']}")
    if result["county_results"]:
        print("\nTop counties by case count:")
        for slug, count in sorted(result["county_results"].items(), key=lambda x: -x[1])[:10]:
            print(f"  {slug:20s} {count}")

    if result["errors"]:
        print(f"\nFirst 5 errors:")
        for e in result["errors"][:5]:
            print(f"  {e}")

    # Telegram report
    msg = (
        f"*FL Auction Scraper* ✅\n"
        f"Cases: {result['total_scraped']} | DB: {result['total_upserted']}\n"
        f"Counties with data: {result['counties_with_data']}/67\n"
        f"Errors: {result['error_count']}"
    )
    _send_telegram(msg)

    sys.exit(0 if result["error_count"] == 0 else 2)


if __name__ == "__main__":
    main()

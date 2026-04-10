"""Auction discovery — find upcoming foreclosure auctions.

Data source: RealForeclose.com public DAYLIST (no auth required)
Fallback:    Supabase multi_county_auctions table
"""

import re
import warnings
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from typing import Optional

import httpx


# Sample data kept as --date sample escape hatch for testing only
SAMPLE_CASES = [
    {"case_number": "2024-CA-001234", "address": "123 Ocean Ave, Satellite Beach, FL 32937",
     "judgment": 223000, "plaintiff": "Bank of America", "auction_date": "2026-03-15"},
    {"case_number": "2024-CA-002345", "address": "456 Banana River Dr, Merritt Island, FL 32953",
     "judgment": 185000, "plaintiff": "Wells Fargo", "auction_date": "2026-03-15"},
    {"case_number": "2024-CA-003456", "address": "789 A1A, Indialantic, FL 32903",
     "judgment": 342000, "plaintiff": "US Bank", "auction_date": "2026-03-15"},
    {"case_number": "2024-CA-004567", "address": "321 Elm St, Melbourne, FL 32940",
     "judgment": 156000, "plaintiff": "Nationstar", "auction_date": "2026-03-15"},
    {"case_number": "2024-CA-005678", "address": "555 Palm Bay Rd, Palm Bay, FL 32905",
     "judgment": 98000, "plaintiff": "HOA Sunset Palms", "auction_date": "2026-03-15"},
]

REALFORECLOSE_URL = "https://brevard.realforeclose.com/index.cfm"
RF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _normalize_date(date: str) -> tuple[str, str]:
    """Return (rf_format MM/DD/YYYY, iso_format YYYY-MM-DD)."""
    date = date.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        dt = datetime.strptime(date, "%Y-%m-%d")
        return dt.strftime("%m/%d/%Y"), date
    if re.match(r"^\d{2}/\d{2}/\d{4}$", date):
        dt = datetime.strptime(date, "%m/%d/%Y")
        return date, dt.strftime("%Y-%m-%d")
    raise ValueError(f"Unrecognized date format: {date!r}. Use YYYY-MM-DD or MM/DD/YYYY")


def _parse_currency(text: str) -> float:
    """Parse '$123,456.78' → 123456.78"""
    clean = re.sub(r"[,$\s]", "", text.strip())
    try:
        return float(clean)
    except ValueError:
        return 0.0


class DayListParser(HTMLParser):
    """Parse RealForeclose DAYLIST HTML.

    The page has multiple tables; the auction data starts in table #2+.
    Each data row has 4+ cells: case_number | status | plaintiff/details | bid_amount
    """

    def __init__(self):
        super().__init__()
        self.cases: list[dict] = []
        self.table_count = 0
        self.in_target_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row: list[str] = []
        self.current_cell = ""

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table_count += 1
            if self.table_count >= 2:
                self.in_target_table = True
        elif tag == "tr" and self.in_target_table:
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
            if len(self.current_row) >= 4:
                self._process_row(self.current_row)
            self.in_row = False
            self.current_row = []
        elif tag == "table":
            self.in_target_table = False

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data

    def _process_row(self, cells: list[str]):
        """Extract case fields from a data row."""
        case_number = " ".join(cells[0].split())

        # Skip header/blank rows
        if not case_number or not re.search(r"\d{4}", case_number):
            return
        header_words = ("case", "number", "#", "sale", "date")
        if any(w in case_number.lower() for w in header_words):
            return

        status_raw = " ".join(cells[1].split()).upper() if len(cells) > 1 else ""
        if "CANCEL" in status_raw:
            status = "CANCELLED"
        elif "THIRD" in status_raw:
            status = "THIRD_PARTY"
        elif "SOLD" in status_raw:
            status = "SOLD"
        elif "SCHEDULE" in status_raw or not status_raw:
            status = "SCHEDULED"
        else:
            status = status_raw

        # Column 3: plaintiff / case details (may contain defendant/address info)
        details_raw = " ".join(cells[2].split()) if len(cells) > 2 else ""
        # Plaintiff is typically the first name before "VS" or "vs."
        parts = re.split(r"\bvs?\b\.?", details_raw, maxsplit=1, flags=re.IGNORECASE)
        plaintiff = parts[0].strip() if parts else details_raw

        # Bid/judgment amount — scan remaining columns for currency
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
            "details": details_raw,
            "judgment": judgment,
        })


def _scrape_realforeclose_live(rf_date: str, iso_date: str, county: str = "brevard") -> list[dict]:
    """HTTP fetch + HTML parse RealForeclose DAYLIST. Returns raw case stubs."""
    params = {
        "zession": "day_list",
        "county": county,
        "sale_type": "fc",
        "sale_date": rf_date,
    }

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resp = httpx.get(
            REALFORECLOSE_URL,
            params=params,
            headers=RF_HEADERS,
            verify=False,
            timeout=30,
            follow_redirects=True,
        )

    resp.raise_for_status()

    parser = DayListParser()
    parser.feed(resp.text)

    for case in parser.cases:
        case["auction_date"] = iso_date
        case["county"] = county
        case.setdefault("address", "")

    return parser.cases


def _fallback_supabase(iso_date: str, county: str = "brevard") -> list[dict]:
    """Query Supabase multi_county_auctions if RealForeclose is unavailable."""
    import os
    try:
        from supabase import create_client
    except ImportError:
        return []
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return []
        client = create_client(url, key)
        result = (
            client.table("multi_county_auctions")
            .select("case_number,address,judgment,plaintiff,auction_date,county,status")
            .eq("auction_date", iso_date)
            .eq("county", county)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def scrape_auction_list(date: str, county: str = "brevard") -> list[dict]:
    """Get all cases for a specific auction date.

    Args:
        date: 'sample', YYYY-MM-DD, or MM/DD/YYYY
        county: RealForeclose county slug (default: brevard)

    Returns:
        List of case dicts with: case_number, status, plaintiff, judgment, auction_date
    """
    if date == "sample":
        return list(SAMPLE_CASES)

    rf_date, iso_date = _normalize_date(date)

    rf_error = None
    try:
        cases = _scrape_realforeclose_live(rf_date, iso_date, county)
        if cases:
            return cases
        # Empty parse — likely no auctions scheduled that day
    except Exception as exc:
        rf_error = str(exc)

    # Fallback: Supabase historical data
    cases = _fallback_supabase(iso_date, county)
    if cases:
        return cases

    # Surface the root cause
    if rf_error:
        raise RuntimeError(
            f"RealForeclose returned no data for {rf_date} ({rf_error}). "
            f"Supabase fallback also returned 0 results. "
            f"Check date has auctions or set SUPABASE_KEY for historical lookup."
        )
    return []


def get_upcoming_auctions(date: Optional[str] = None, county: str = "brevard") -> dict:
    """Get upcoming auction date and case count."""
    if date == "sample":
        return {
            "county": county,
            "date": "sample",
            "venue": "Sample Data",
            "type": "sample",
            "count": len(SAMPLE_CASES),
            "status": "sample_data",
            "next_date": "sample",
        }

    if date:
        rf_date, iso_date = _normalize_date(date)
    else:
        now = datetime.now(timezone.utc)
        # Find next weekday (Mon–Fri)
        for days_ahead in range(7):
            candidate = now + timedelta(days=days_ahead)
            if candidate.weekday() < 5:
                break
        iso_date = candidate.strftime("%Y-%m-%d")
        rf_date = candidate.strftime("%m/%d/%Y")

    cases = scrape_auction_list(rf_date, county)
    venue_map = {"brevard": "Titusville Courthouse"}

    return {
        "county": county,
        "date": iso_date,
        "rf_date": rf_date,
        "venue": venue_map.get(county, f"{county.title()} Courthouse"),
        "type": "in-person",
        "count": len(cases),
        "status": "live" if cases else "no_results",
        "next_date": iso_date,
    }


def get_case_details(case_number: str) -> Optional[dict]:
    """Look up a case by number from SAMPLE_CASES (testing) or return None."""
    case_number = case_number.upper()
    for case in SAMPLE_CASES:
        if case["case_number"] == case_number:
            return case
    return None

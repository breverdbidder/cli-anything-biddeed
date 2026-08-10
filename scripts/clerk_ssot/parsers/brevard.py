"""Brevard clerk foreclosure sales parser. Family A (plain html_table).

Reference/canary parser for the CLERK-SSOT project — proven 104/104 against
multi_county_auctions on 2026-08-10. Any regression here is the parity canary.
"""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html"
CASE_RE = re.compile(r"^\d{2}-\d{4}-C[AC]-")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def _normalize_date(raw: str) -> str | None:
    m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"


def parse_foreclosure() -> list[dict]:
    """Brevard publishes a real HTML <table> (not raw TSV, despite the docs).
    Columns: case_number | case_title | comment | foreclosure_sale_date.
    'comment' carries CANCELLED / RESCHEDULED markers — the signal RealAuction
    does not expose. Never drop it."""
    resp = httpx.get(FC_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table")
    if table is None:
        raise RuntimeError("brevard foreclosure: no <table> found — page structure changed")

    rows = []
    trs = table.find_all("tr")
    for tr in trs[1:]:  # skip header row
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 4:
            continue
        case_number, case_title, comment, sale_date_raw = cells[0], cells[1], cells[2], cells[3]
        if not CASE_RE.match(case_number):
            continue
        rows.append({
            "county_slug": "brevard",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_date(sale_date_raw),
            "cancelled": "CANCEL" in comment.upper(),
            "raw_comment": comment,
            "case_title": case_title,
            "source_url": FC_URL,
        })

    if not rows:
        raise RuntimeError("brevard foreclosure: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")

    return rows


if __name__ == "__main__":
    import json
    data = parse_foreclosure()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"parsed {len(data)} rows, {cancelled} cancelled")
    print(json.dumps(data[:2], indent=2))

"""Wakulla clerk foreclosure + tax deed parser. Family B (html_table).

Foreclosure: each row carries its own Case #/Sale Date. Tax deed: sale date
lives on a separator row ("August 19, 2026") and must be carried forward to
the tax-deed-# rows beneath it — those rows have no date of their own.
"""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://wakullaclerk.org/courts/foreclosures.php"
TD_URL = "https://wakullaclerk.org/official_records/tax_deed_sales.php"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

FC_CASE_RE = re.compile(r"^\d{2}-[A-Z]{2}-\d+$")
TD_CASE_RE = re.compile(r"^\d{4}-TXD-\d+$")
TD_DATE_RE = re.compile(r"^[A-Z][a-z]+ \d{1,2},\s*\d{4}$")

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


def _normalize_slash_date(raw: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _normalize_long_date(raw: str) -> str | None:
    m = re.match(r"^([A-Z][a-z]+) (\d{1,2}),\s*(\d{4})$", raw.strip())
    if not m:
        return None
    month_name, dd, yyyy = m.groups()
    mm = MONTHS.get(month_name)
    if not mm:
        return None
    return f"{yyyy}-{mm:02d}-{int(dd):02d}"


def _fetch_rows(url: str) -> list[list[str]]:
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table")
    if table is None:
        raise RuntimeError(f"wakulla: no <table> found at {url} — page structure changed")
    return [[td.get_text(strip=True) for td in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]


def parse_foreclosure() -> list[dict]:
    rows_out = []
    for cells in _fetch_rows(FC_URL):
        if len(cells) < 6 or not FC_CASE_RE.match(cells[2]):
            continue
        plaintiff, defendant, case_number, sale_date_raw, status, amount = cells[0], cells[1], cells[2], cells[3], cells[4], cells[5]
        notes = cells[6] if len(cells) > 6 else ""
        rows_out.append({
            "county_slug": "wakulla",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_slash_date(sale_date_raw),
            "cancelled": status.upper() in ("CANCELLED", "CANCELED") or "CANCEL" in notes.upper(),
            "raw_comment": f"{status} | {notes}".strip(" |"),
            "case_title": f"{plaintiff} VS {defendant}",
            "source_url": FC_URL,
        })
    if not rows_out:
        raise RuntimeError("wakulla foreclosure: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


def parse_tax_deed() -> list[dict]:
    rows_out = []
    current_date = None
    for cells in _fetch_rows(TD_URL):
        if len(cells) >= 1 and TD_DATE_RE.match(cells[0].strip()):
            current_date = _normalize_long_date(cells[0].strip())
            continue
        if len(cells) < 3 or not TD_CASE_RE.match(cells[1]):
            continue
        deed_no, status = cells[1], cells[2]
        notes = cells[4] if len(cells) > 4 else ""
        rows_out.append({
            "county_slug": "wakulla",
            "sale_type": "tax_deed",
            "case_number": deed_no,
            "sale_date": current_date,
            "cancelled": status.upper() == "REDEEMED",
            "raw_comment": f"{status} | {notes}".strip(" |"),
            "case_title": deed_no,
            "source_url": TD_URL,
        })
    if not rows_out:
        raise RuntimeError("wakulla tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    fc = parse_foreclosure()
    td = parse_tax_deed()
    print(f"foreclosure: {len(fc)} rows")
    print(f"tax_deed: {len(td)} rows, {sum(1 for r in td if r['cancelled'])} redeemed")

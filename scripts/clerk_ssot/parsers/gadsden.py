"""Gadsden clerk foreclosure + tax deed parser. Family B (legacy Excel-export
html_table, frameset site — requires a browser User-Agent, 403s otherwise)."""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "http://www.gadsdenclerk.com/Foreclosures/Foreclosures_files/sheet001.htm"
TD_URL = "http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds_files/sheet001.htm"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

FC_CASE_RE = re.compile(r"^\d{5,8}(CA|CC)[A-Z]{0,3}$")
TD_CASE_RE = re.compile(r"^\d{6,10}TDC$")


def _normalize_date(raw: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _fetch_table(url: str) -> list[list[str]]:
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")  # bytes in: let bs4/lxml sniff encoding, avoids UnicodeDecodeError
    table = soup.find("table")
    if table is None:
        raise RuntimeError(f"gadsden: no <table> found at {url} — page structure changed")
    return [[td.get_text(strip=True) for td in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]


def parse_foreclosure() -> list[dict]:
    rows_out = []
    for cells in _fetch_table(FC_URL):
        if len(cells) < 4 or not FC_CASE_RE.match(cells[1]):
            continue
        sale_date, case_number, plaintiff, defendant = cells[0], cells[1], cells[2], cells[3]
        rows_out.append({
            "county_slug": "gadsden",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_date(sale_date),
            "cancelled": False,
            "raw_comment": "",
            "case_title": f"{plaintiff} VS {defendant}",
            "source_url": FC_URL,
        })
    if not rows_out:
        raise RuntimeError("gadsden foreclosure: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


def parse_tax_deed() -> list[dict]:
    rows_out = []
    for cells in _fetch_table(TD_URL):
        if len(cells) < 6 or not TD_CASE_RE.match(cells[1]):
            continue
        sale_date, case_number, cert_no, holder, owner = cells[0], cells[1], cells[2], cells[3], cells[4]
        sale_price = cells[9] if len(cells) > 9 else ""
        rows_out.append({
            "county_slug": "gadsden",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": _normalize_date(sale_date),
            "cancelled": "REDEEM" in sale_price.upper(),
            "raw_comment": sale_price,
            "case_title": f"cert {cert_no} / {holder} vs {owner}",
            "source_url": TD_URL,
        })
    if not rows_out:
        raise RuntimeError("gadsden tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    fc = parse_foreclosure()
    td = parse_tax_deed()
    print(f"foreclosure: {len(fc)} rows")
    print(f"tax_deed: {len(td)} rows, {sum(1 for r in td if r['cancelled'])} redeemed")

"""Franklin clerk foreclosure + tax deed parser. Family E (WordPress card
grid -- same theme/markup as dixie.py: each sale is a div.grid.md:grid-cols-3
with label/value child divs). Case number format differs from dixie
(YYYY-CA-NN, no leading circuit prefix) and Sale Date carries a trailing
time ("08/26/2026 11:00 am") that dixie's dates don't have.

tax_deed: as of 2026-08-10 the live page has ZERO sale-card markup -- Franklin
genuinely has no tax deed sales currently scheduled, not a parser break.
parse_tax_deed is implemented for when sales appear.
"""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://www.franklinclerk.com/courts/foreclosures/"
TD_URL = "https://www.franklinclerk.com/courts/tax-deeds/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"^\d{4}-(CA|TD)-\d+$")


def _normalize_date(raw: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _fetch_cards(url: str) -> list[dict[str, str]]:
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    cards = []
    for lbl_text in soup.find_all(string=lambda s: s and s.strip() == "Case Number"):
        node = lbl_text.find_parent()
        grid = None
        for _ in range(8):
            if node is None:
                break
            node = node.parent
            cls = node.get("class") or []
            if "grid" in cls:
                grid = node
                break
        if grid is None:
            continue
        fields = {}
        for child in grid.find_all("div", recursive=False):
            label_tag = child.find("label")
            if not label_tag:
                continue
            key = label_tag.get_text(strip=True)
            label_tag.extract()
            fields[key] = child.get_text(strip=True)
        if fields:
            cards.append(fields)
    return cards


def parse_foreclosure() -> list[dict]:
    rows_out = []
    for f in _fetch_cards(FC_URL):
        case_number = f.get("Case Number", "")
        if not CASE_RE.match(case_number):
            continue
        status = f.get("Status", "")
        rows_out.append({
            "county_slug": "franklin",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_date(f.get("Sale Date", "")),
            "cancelled": status.upper() in ("CANCELLED", "CANCELED"),
            "raw_comment": status,
            "case_title": f.get("Parties", ""),
            "source_url": FC_URL,
        })
    if not rows_out:
        raise RuntimeError("franklin foreclosure: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


def parse_tax_deed() -> list[dict]:
    rows_out = []
    for f in _fetch_cards(TD_URL):
        case_number = f.get("Case Number", "")
        if not CASE_RE.match(case_number):
            continue
        status = f.get("Status", "")
        rows_out.append({
            "county_slug": "franklin",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": _normalize_date(f.get("Sale Date", "")),
            "cancelled": status.upper() in ("CANCELLED", "CANCELED", "REDEEMED"),
            "raw_comment": status,
            "case_title": f.get("Parties", case_number),
            "source_url": TD_URL,
        })
    if not rows_out:
        raise RuntimeError("franklin tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    fc = parse_foreclosure()
    print(f"foreclosure: {len(fc)} rows")
    try:
        td = parse_tax_deed()
        print(f"tax_deed: {len(td)} rows")
    except RuntimeError as e:
        print(f"tax_deed: {e}")

"""DeSoto clerk foreclosure + tax deed parser. Family D (single PDF calendar,
date-carry-forward -- same convention as wakulla tax_deed / highlands).

Both PDFs are re-uploaded to a dated wp-content/uploads/ path each time the
clerk refreshes the calendar (filename embeds the last-updated date, e.g.
8.5Foreclosure.pdf), so FC_URL/TD_URL below are point-in-time snapshots of
the *current* file discovered from the live desotoclerk.com landing pages
on 2026-08-10, not permanent URLs. If this parser starts 404ing, re-scrape
https://www.desotoclerk.com/public-sales/foreclosures/ (resp.
"UPCOMING FORECLOSURE SALES" link) / .../tax-deeds/ ("UPCOMING TAX DEED
SALES" link) for the new filename.
"""
import re

import httpx
from pypdf import PdfReader
from io import BytesIO

FC_LANDING_URL = "https://www.desotoclerk.com/public-sales/foreclosures/"
TD_LANDING_URL = "https://www.desotoclerk.com/public-sales/tax-deeds/"
FC_URL = "https://www.desotoclerk.com/wp-content/uploads/2026/08/8.5Foreclosure.pdf"
TD_URL = "https://www.desotoclerk.com/wp-content/uploads/2026/08/8.3_TAX-DEED-WEBSITE.pdf"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}
_MONTH_ALT = "|".join(MONTHS)
DATE_HEADER_RE = re.compile(rf"^({_MONTH_ALT}) (\d{{1,2}}), (\d{{4}})$", re.I)

FC_ROW_RE = re.compile(r"^(\S+)\s+(.+?)\s+([\d,]+\.\d{2})\s+(.+)$")
TD_ROW_RE = re.compile(r"^(\S+-TD)\s+(\S+)\s+(.+?)\s+\$([\d,]+\.\d{2})$")


def _normalize_date(month_name: str, dd: str, yyyy: str) -> str | None:
    mm = MONTHS.get(month_name.title())
    if not mm:
        return None
    return f"{yyyy}-{mm:02d}-{int(dd):02d}"


def _fetch_pdf_lines(url: str, label: str) -> list[str]:
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    reader = PdfReader(BytesIO(resp.content))
    text = "\n".join(page.extract_text() for page in reader.pages)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        raise RuntimeError(f"desoto {label}: PDF has no extractable text — likely a scanned image")
    return lines


def parse_foreclosure() -> list[dict]:
    """Layout: 'CASE NO. PLAINTIFF DEFENDANT F/J AMOUNT LEGAL DESCRIPTION/STREET
    ADDRESS' header, then a 'Month D, YYYY' date line, then one line per case:
    'CASENO PLAINTIFF DEFENDANT AMOUNT ADDRESS' -- carry the date forward to
    every case line beneath it until the next date line."""
    lines = _fetch_pdf_lines(FC_URL, "foreclosure")
    rows = []
    current_date = None
    for line in lines:
        dm = DATE_HEADER_RE.match(line)
        if dm:
            current_date = _normalize_date(*dm.groups())
            continue
        m = FC_ROW_RE.match(line)
        if not m:
            continue
        case_number, middle, amount, address = m.groups()
        if not re.match(r"^\d{2,4}CA\d+$", case_number):
            continue
        rows.append({
            "county_slug": "desoto",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": current_date,
            "cancelled": False,
            "raw_comment": "",
            "case_title": f"{middle.strip()} | {address.strip()}",
            "source_url": FC_URL,
        })

    if not rows:
        raise RuntimeError("desoto foreclosure: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows


def parse_tax_deed() -> list[dict]:
    """Layout: 'SALE DATE / TAX DEED # PARCEL ID # PROPERTY ADDRESS STARTING
    BID' header, then a 'MONTH D, YYYY' (all-caps) date line, then one line
    per deed: 'NN-NN-TD PARCELID ADDRESS $AMOUNT' -- same carry-forward."""
    lines = _fetch_pdf_lines(TD_URL, "tax_deed")
    rows = []
    current_date = None
    for line in lines:
        dm = DATE_HEADER_RE.match(line)
        if dm:
            current_date = _normalize_date(*dm.groups())
            continue
        m = TD_ROW_RE.match(line)
        if not m:
            continue
        deed_no, parcel_id, address, amount = m.groups()
        rows.append({
            "county_slug": "desoto",
            "sale_type": "tax_deed",
            "case_number": deed_no,
            "sale_date": current_date,
            "cancelled": False,
            "raw_comment": f"starting bid ${amount}",
            "case_title": f"{address.strip()} | parcel {parcel_id}",
            "source_url": TD_URL,
        })

    if not rows:
        raise RuntimeError("desoto tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows


if __name__ == "__main__":
    fc = parse_foreclosure()
    td = parse_tax_deed()
    print(f"foreclosure: {len(fc)} rows")
    print(f"tax_deed: {len(td)} rows")

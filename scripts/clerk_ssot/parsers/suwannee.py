"""Suwannee clerk tax deed parser. Family C (PDF-per-date, parser_hint='pdf_per_date').

Foreclosure is OUT OF SCOPE — clerk_sale_calendar_sources has
foreclosure_verified=false and the foreclosure_url is a stale .docx link.

Suwannee publishes ONE PDF per upcoming sale event (not a rolling calendar
table). The whole schedule is for a single sale date printed once near the
top of page 1 ("Thursday, September 3, 2026, at 11:00 a.m.") — every case
row beneath it shares that date, so (unlike wakulla) there's no per-row date
and no repeated date-header/rows-below pattern; it's one date for the whole
document. Case rows look like:

    Case No. TD  Base Opening Bid Assessed Party
    4672/2024-1229 11,832.84 Luis Ramirez & Alberto Ramirez & Nidia Malena Ramirez
    Legal Description:  05293010100  22-02S-13E  LEG 7.64 ACRES ...

The PDF has no per-row REDEEMED/CANCELLED marker — it only lists active
upcoming sales (the only "redeemed" text in the doc is boilerplate in the
bidder-notice section, not attached to any case). cancelled is therefore
always False here, same posture as gadsden foreclosure when no signal exists.

The published URL embeds the sale date in its filename
(Schedule-08.05.2026.pdf) and gets replaced whenever the clerk posts the next
sale — TD_URL below is discovered live from the tax-deed-sales landing page
rather than hardcoded, so this parser survives that churn.
"""
import re

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
import io

LANDING_URL = "https://www.suwgov.org/tax-deed-sales/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"^(\d{3,5}/\d{4}-\d{1,4})\s+([\d,]+\.\d{2})\s+(.+)$")
SALE_DATE_RE = re.compile(
    r"^[A-Z][a-z]+,\s*([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4}),\s*at\s+\d"
)

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


def _normalize_date(raw: str) -> str | None:
    """Converts 'September 3, 2026' style month names to 'YYYY-MM-DD'."""
    m = re.match(r"^([A-Z][a-z]+)\s+(\d{1,2}),?\s*(\d{4})$", raw.strip())
    if not m:
        return None
    month_name, dd, yyyy = m.groups()
    mm = MONTHS.get(month_name)
    if not mm:
        return None
    return f"{yyyy}-{mm:02d}-{int(dd):02d}"


def _discover_td_url() -> str:
    """The schedule PDF filename embeds the sale date and is replaced each
    sale cycle — scrape the landing page for the current 'Next Tax Deed Sale'
    link instead of hardcoding a dated filename."""
    resp = httpx.get(LANDING_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    pdf_links = soup.find_all("a", href=re.compile(r"\.pdf$", re.I))
    for a in pdf_links:
        if "schedule" in a["href"].lower() or "tax deed sale" in a.get_text(strip=True).lower():
            return a["href"]
    if pdf_links:
        return pdf_links[0]["href"]
    raise RuntimeError(f"suwannee: no tax deed schedule PDF link found on {LANDING_URL} — page structure changed")


def parse_tax_deed() -> list[dict]:
    td_url = _discover_td_url()
    resp = httpx.get(td_url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    reader = PdfReader(io.BytesIO(resp.content))

    full_text = ""
    for page in reader.pages:
        full_text += (page.extract_text() or "") + "\n"
    lines = full_text.split("\n")

    sale_date = None
    for line in lines:
        m = SALE_DATE_RE.match(line.strip())
        if m:
            month_name, dd, yyyy = m.groups()
            mm = MONTHS.get(month_name)
            if mm:
                sale_date = f"{yyyy}-{mm:02d}-{int(dd):02d}"
            break

    if sale_date is None:
        raise RuntimeError(f"suwannee tax_deed: no sale date header found in PDF at {td_url} — PDF structure changed")

    rows_out = []
    for line in lines:
        m = CASE_RE.match(line.strip())
        if not m:
            continue
        case_number, amount, party = m.groups()
        party = party.strip()
        rows_out.append({
            "county_slug": "suwannee",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": sale_date,
            "cancelled": False,  # no per-row REDEEMED/CANCELLED marker in this schedule format
            "raw_comment": f"opening bid {amount}",
            "case_title": party,
            "source_url": td_url,
        })

    if not rows_out:
        raise RuntimeError(f"suwannee tax_deed: parsed 0 rows from a 200 response at {td_url} — treat as FAILURE, not an empty calendar")

    return rows_out


if __name__ == "__main__":
    import json
    data = parse_tax_deed()
    print(f"tax_deed: {len(data)} rows")
    print(json.dumps(data[:2], indent=2))

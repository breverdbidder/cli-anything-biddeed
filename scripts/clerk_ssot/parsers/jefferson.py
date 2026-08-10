"""Jefferson clerk foreclosure + tax deed parser. Family D (single PDF
calendar per sale type, same shape as highlands.py).

jeffersonclerk.com links out to two S3-hosted PDFs (URL path changes per
upload, e.g. .../uploads/2026/08/03075239/FORECLOSURE-SALES.pdf — the
numeric path segment is a per-upload id, not stable, so it must be
discovered fresh from the listing page on every run rather than hardcoded).

FORECLOSURE-SALES.pdf is a flat label:value dump, one record per sale,
delimited by a repeating "Date of Sale:" header:
  Date of Sale: 08/27/2026
  Case #: 25-CA-145
  Plaintiff: U.S. Bank National Association
  Defendant: Kathleen Johnson et al.
  Final Judgement amount: $183,049.87
  Property Address: 595 Virginia St. Monticello, FL. 32344

Pending-Tax-Deed-Sales.pdf is likewise delimited by a repeating
"DATE OF SALE/FILE#" header that carries both the date AND the case number
on one line:
  DATE OF SALE/FILE# 8/19/2026            26-TD-05
  PROPERTY OWNER/S: Willie & Frances Story
  PROPERTY Parcel #: 01-1S-3E-0000-0021-0000
  DESCRIPTION OF PROPERTY: 7.63 Acres N1/2 of NE1/4 ...
  SITE ADDRESS: 300 Cherry Tree. Rd. Monticello, FL. 32344
  OPENING BID: $8,399.79

As of 2026-08-10 each PDF holds exactly one live record (Jefferson is a
small/rural calendar) — the record-splitting regex below is written to
also handle multiple repeats correctly, since a single-record snapshot
proves nothing about future volume. No CANCEL/RESCHEDULE/POSTPONE token
appears in either document; cancellation is inferred the same defensive
way as highlands.py, by scanning each record's text for those markers in
case the clerk ever adds one inline.
"""
import re

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from io import BytesIO

FC_PAGE_URL = "https://jeffersonclerk.com/clerk-services/property-sales/foreclosures/"
TD_PAGE_URL = "https://jeffersonclerk.com/clerk-services/property-sales/tax-deed-sales/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

FC_CASE_RE = re.compile(r"^\d{2}-C[AC]-\d+$")
TD_CASE_RE = re.compile(r"^\d{2}-TD-\d+$")

FC_DATE_HEADER_RE = re.compile(r"Date of Sale:\s*(\d{1,2}/\d{1,2}/\d{4})")
TD_RECORD_RE = re.compile(
    r"DATE OF SALE/FILE#\s*(\d{1,2}/\d{1,2}/\d{4})\s+(\d{2}-TD-\d+)"
)


def _normalize_date(raw: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _find_pdf_url(page_url: str, filename_hint: str) -> str:
    resp = httpx.get(page_url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf") and filename_hint.lower() in href.lower():
            return href
    # fallback: any pdf link at all, in case the clerk renames the file
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            return href
    raise RuntimeError(f"jefferson: no PDF link found on {page_url} — page structure changed")


def _fetch_pdf_text(pdf_url: str) -> str:
    resp = httpx.get(pdf_url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    reader = PdfReader(BytesIO(resp.content))
    page_texts = [page.extract_text() for page in reader.pages]
    text = re.sub(r"[ \t]+", " ", " ".join(page_texts)).strip()
    if not text:
        raise RuntimeError(f"jefferson: PDF at {pdf_url} has no extractable text layer — likely a scanned image")
    return text


def parse_foreclosure() -> list[dict]:
    pdf_url = _find_pdf_url(FC_PAGE_URL, "FORECLOSURE")
    text = _fetch_pdf_text(pdf_url)

    date_matches = list(FC_DATE_HEADER_RE.finditer(text))
    if not date_matches:
        raise RuntimeError("jefferson foreclosure: no 'Date of Sale:' headers found in PDF text — layout changed")

    rows = []
    for i, dm in enumerate(date_matches):
        block_start = dm.end()
        block_end = date_matches[i + 1].start() if i + 1 < len(date_matches) else len(text)
        block = text[block_start:block_end]
        sale_date = _normalize_date(dm.group(1))

        case_m = re.search(r"Case #:\s*([\d\-A-Za-z]+)", block)
        if not case_m:
            continue
        case_number = case_m.group(1).strip()
        if not FC_CASE_RE.match(case_number):
            continue

        plaintiff_m = re.search(r"Plaintiff:\s*(.+?)\s*Defendant:", block, re.DOTALL)
        defendant_m = re.search(r"Defendant:\s*(.+?)\s*Final Judge?ment amount:", block, re.DOTALL)
        plaintiff = re.sub(r"\s+", " ", plaintiff_m.group(1)).strip() if plaintiff_m else ""
        defendant = re.sub(r"\s+", " ", defendant_m.group(1)).strip() if defendant_m else ""
        case_title = f"{plaintiff} VS {defendant}".strip(" VS")

        block_upper = block.upper()
        rows.append({
            "county_slug": "jefferson",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": sale_date,
            "cancelled": "CANCEL" in block_upper or "RESCHEDULE" in block_upper or "POSTPONE" in block_upper,
            "raw_comment": "",
            "case_title": case_title,
            "source_url": pdf_url,
        })

    if not rows:
        raise RuntimeError("jefferson foreclosure: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")

    return rows


def parse_tax_deed() -> list[dict]:
    pdf_url = _find_pdf_url(TD_PAGE_URL, "Tax-Deed")
    text = _fetch_pdf_text(pdf_url)

    record_matches = list(TD_RECORD_RE.finditer(text))
    if not record_matches:
        raise RuntimeError("jefferson tax_deed: no 'DATE OF SALE/FILE#' headers found in PDF text — layout changed")

    rows = []
    for i, rm in enumerate(record_matches):
        block_start = rm.end()
        block_end = record_matches[i + 1].start() if i + 1 < len(record_matches) else len(text)
        block = text[block_start:block_end]
        sale_date = _normalize_date(rm.group(1))
        case_number = rm.group(2).strip()
        if not TD_CASE_RE.match(case_number):
            continue

        owner_m = re.search(r"PROPERTY OWNER/S:\s*(.+?)\s*PROPERTY Parcel #:", block, re.DOTALL)
        owner = re.sub(r"\s+", " ", owner_m.group(1)).strip() if owner_m else ""

        block_upper = block.upper()
        rows.append({
            "county_slug": "jefferson",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": sale_date,
            "cancelled": "CANCEL" in block_upper or "RESCHEDULE" in block_upper or "REDEEM" in block_upper,
            "raw_comment": "",
            "case_title": owner,
            "source_url": pdf_url,
        })

    if not rows:
        raise RuntimeError("jefferson tax_deed: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")

    return rows


if __name__ == "__main__":
    fc = parse_foreclosure()
    td = parse_tax_deed()
    print(f"foreclosure: {len(fc)} rows, {sum(1 for r in fc if r['cancelled'])} cancelled")
    print(f"tax_deed: {len(td)} rows, {sum(1 for r in td if r['cancelled'])} cancelled")

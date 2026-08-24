"""Highlands clerk foreclosure + tax deed sales parser.

FORECLOSURE: Family D (single PDF calendar, not HTML — despite
parser_hint='pdf_per_date' in clerk_sale_calendar_sources, the live document
is one PDF covering the whole calendar, not one PDF per sale date).

webfiles.highlandsclerkfl.gov publishes a 2-page PDF table: Date | Case
Number | Plaintiff | Defendant | Judgment Amount | Legal Description. Date
is a section header ("August 18, 2026") that applies to every case row
beneath it until the next date header — carry-forward, same convention as
wakulla's tax_deed date. pypdf's plain text extraction interleaves cells
onto separate lines with unpredictable wrapping (a name can split mid-word
across lines), so this parser does NOT do line-by-line parsing. Instead it
collapses the whole document to one whitespace-normalized string and walks
it with three nested regex passes: date headers -> case numbers -> dollar
amount as the boundary between the plaintiff+defendant span and the legal
description span. This is robust to the wrapping noise because the case
number / $amount tokens themselves never wrap.

No status/comment column is exposed on this calendar (verified against a
live fetch — no CANCEL/RESCHEDULE/POSTPONE token appears anywhere in the
document as of 2026-08-10). Cancellation is inferred the same way as
okeechobee: scan the combined plaintiff+defendant+legal text per row for
CANCEL/RESCHEDULE markers, in case the clerk ever adds one inline.

TAX_DEED: highlands.realtdm.com (public.cases.list) is the clerk's own
RealTDM-hosted case list (linked from
highlandsclerkfl.gov/clerk_to_the_board/tax_deeds/tax_deed_search.php as
"online tax deed sales from January 2026 to current"). Distinct from the
gated auction-bidding platforms (RealForeclose/RealAuction/RealTaxDeed) that
this pipeline is barred from driving: this is a plain, unauthenticated
public case-search form (`isPublic` hidden field = 1, no login), confirmed
live 2026-08-24 — POSTing filterCaseStatus=1827 (clerk's own "Active" status
id, discovered by reading the status-dropdown's data-status-id attributes on
the unfiltered list page) plus pagination returns a static server-rendered
`<table class="table public">` of ACTIVE cases, one row per case: Status |
Case Number | Date Created | App Number | Parcel Number | Sale Date |
Surplus Balance. No independent "cancelled" signal is exposed by the ACTIVE
filter (cancelled cases carry other status ids entirely -- see STATUS_IDS),
so cancelled is always False for rows returned by this filter; a case that
drops out of the ACTIVE list on a later run has changed status, which
run_parity's phantom-detection already handles at the orchestration layer.
"""
import re

import httpx
from pypdf import PdfReader
from io import BytesIO

FC_URL = "https://webfiles.highlandsclerkfl.gov/ForeClosure/ClerkSaleCalendar.pdf"
TD_URL = "https://highlands.realtdm.com/public/cases/list"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# realtdm.com's own "Active" case-status id, read off the live status filter
# dropdown (data-status-id attribute) 2026-08-24. Not derivable from the
# case list itself -- realtdm assigns numeric ids server-side.
TD_STATUS_ACTIVE = "1827"
TD_CASE_RE = re.compile(r"^\d{6,10}$")
TD_MAX_PAGES = 20  # 100/page; hard cap to avoid runaway pagination

# Highlands circuit court case numbers observed on the live calendar:
# YYYY NNNNNN (GC|CC) AXMX  e.g. 25000138GCAXMX, 26000086CCAXMX
CASE_RE = re.compile(r"\d{8}(?:GC|CC)AXMX")
AMT_RE = re.compile(r"\$[\d,]+\.\d{2}")

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}
_MONTH_ALT = "|".join(MONTHS)
DATE_RE = re.compile(rf"({_MONTH_ALT})\s+(\d{{1,2}}),\s*(\d{{4}})")


def _normalize_date(raw: str) -> str | None:
    m = DATE_RE.match(raw.strip())
    if not m:
        return None
    month_name, dd, yyyy = m.groups()
    mm = MONTHS.get(month_name)
    if not mm:
        return None
    return f"{yyyy}-{mm:02d}-{int(dd):02d}"


def parse_foreclosure() -> list[dict]:
    resp = httpx.get(FC_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    reader = PdfReader(BytesIO(resp.content))
    page_texts = [page.extract_text() for page in reader.pages]
    text = re.sub(r"\s+", " ", " ".join(page_texts)).strip()
    if not text:
        raise RuntimeError("highlands foreclosure: PDF has no extractable text layer — likely a scanned image")

    date_matches = list(DATE_RE.finditer(text))
    if not date_matches:
        raise RuntimeError("highlands foreclosure: no date headers found in PDF text — layout changed")

    rows = []
    for i, dm in enumerate(date_matches):
        block_start = dm.end()
        block_end = date_matches[i + 1].start() if i + 1 < len(date_matches) else len(text)
        block = text[block_start:block_end]
        sale_date = _normalize_date(dm.group(0))

        case_matches = list(CASE_RE.finditer(block))
        for j, cm in enumerate(case_matches):
            case_start = cm.end()
            case_end = case_matches[j + 1].start() if j + 1 < len(case_matches) else len(block)
            case_body = block[case_start:case_end]

            amt_m = AMT_RE.search(case_body)
            case_title = case_body[:amt_m.start()].strip() if amt_m else case_body.strip()
            legal = case_body[amt_m.end():].strip() if amt_m else ""
            raw_comment_text = f"{case_title} {legal}".upper()

            rows.append({
                "county_slug": "highlands",
                "sale_type": "foreclosure",
                "case_number": cm.group(0),
                "sale_date": sale_date,
                "cancelled": "CANCEL" in raw_comment_text or "RESCHEDULE" in raw_comment_text,
                "raw_comment": "",
                "case_title": case_title,
                "source_url": FC_URL,
            })

    if not rows:
        raise RuntimeError("highlands foreclosure: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")

    return rows


# Wide-view table rows: <tr class="link load-case" ...> ... </tr>, columns
# Status | Case Number | Date Created | App Number | Parcel Number | Sale
# Date | Surplus Balance. Split on the row boundary first, then pull cells
# by position with a tag-stripping per-cell regex -- some rows carry nested
# markup inside a cell (e.g. App Number = "<span..><em>N/A</em></span>" for
# cases realtdm hasn't assigned an application number to yet, confirmed live
# 2026-08-24 on case 24000612), which breaks a naive "[^<]+" capture and
# silently drops the whole row.
_TD_TR_RE = re.compile(r'<tr class="link load-case"[^>]*>(.*?)</tr>', re.DOTALL)
_TD_CELL_RE = re.compile(r'<td class="text-end">(.*?)</td>', re.DOTALL)
_TD_STATUS_RE = re.compile(r'<div>([^<]+)</div>')
_TAG_RE = re.compile(r"<[^>]+>")


def _td_cell_text(html: str) -> str:
    return _TAG_RE.sub("", html).strip()
_TD_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
_TD_DATE_RE = re.compile(r"^([A-Za-z]{3})[a-z]*\s+(\d{1,2}),\s*(\d{4})$")


def _normalize_td_date(raw: str) -> str | None:
    m = _TD_DATE_RE.match(raw.strip())
    if not m:
        return None
    mon, dd, yyyy = m.groups()
    mm = _TD_MONTHS.get(mon[:3].title())
    if not mm:
        return None
    return f"{yyyy}-{mm:02d}-{int(dd):02d}"


def _fetch_td_page(page: int) -> str:
    resp = httpx.post(
        TD_URL,
        headers={"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"filterFiltered": "1", "filterCaseStatus": TD_STATUS_ACTIVE,
              "filterCasesPerPage": "100", "filterPageNumber": str(page)},
        timeout=30, follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.text


_TD_FOUND_RE = re.compile(r"Found</span>\s*<strong>(\d+)</strong>")


def parse_tax_deed() -> list[dict]:
    rows_out = []
    total_found = None
    rows_seen = 0
    for page in range(1, TD_MAX_PAGES + 1):
        html = _fetch_td_page(page)
        if total_found is None:
            m = _TD_FOUND_RE.search(html)
            total_found = int(m.group(1)) if m else None
        page_rows = _TD_TR_RE.findall(html)
        if not page_rows:
            break
        rows_seen += len(page_rows)
        for row_html in page_rows:
            status_m = _TD_STATUS_RE.search(row_html)
            status = status_m.group(1).strip() if status_m else ""
            cells = [_td_cell_text(c) for c in _TD_CELL_RE.findall(row_html)]
            if len(cells) < 5:
                continue
            case_number, _created, _app_num, parcel, sale_date = cells[:5]
            case_number = case_number.strip()
            if not TD_CASE_RE.match(case_number):
                continue
            rows_out.append({
                "county_slug": "highlands",
                "sale_type": "tax_deed",
                "case_number": case_number,
                "sale_date": _normalize_td_date(sale_date),
                "cancelled": False,  # ACTIVE-status filter only; see module docstring
                "raw_comment": f"{status} | parcel {parcel}",
                "case_title": case_number,
                "source_url": TD_URL,
            })
        if total_found is not None and rows_seen >= total_found:
            break

    if not rows_out:
        raise RuntimeError("highlands tax_deed: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")

    return rows_out


if __name__ == "__main__":
    import json
    data = parse_foreclosure()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"foreclosure: parsed {len(data)} rows, {cancelled} cancelled")
    print(json.dumps(data[:2], indent=2))

    td = parse_tax_deed()
    print(f"tax_deed: parsed {len(td)} rows")
    print(json.dumps(td[:2], indent=2))

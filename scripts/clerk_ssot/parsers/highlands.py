"""Highlands clerk foreclosure sales parser. Family D (single PDF calendar,
not HTML — despite parser_hint='pdf_per_date' in clerk_sale_calendar_sources,
the live document is one PDF covering the whole calendar, not one PDF per
sale date).

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
CANCEL/RESCHEDULE markers, in case the clerk ever adds one inline. tax_deed
is NOT implemented here: unverified in clerk_sale_calendar_sources, out of
scope.
"""
import re

import httpx
from pypdf import PdfReader
from io import BytesIO

FC_URL = "https://webfiles.highlandsclerkfl.gov/ForeClosure/ClerkSaleCalendar.pdf"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

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


if __name__ == "__main__":
    import json
    data = parse_foreclosure()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"parsed {len(data)} rows, {cancelled} cancelled")
    print(json.dumps(data[:2], indent=2))

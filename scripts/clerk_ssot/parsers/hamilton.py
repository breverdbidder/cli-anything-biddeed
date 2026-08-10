"""Hamilton clerk foreclosure + tax deed parser. Family F (plain prose page,
not a table/grid -- closest existing convention is wakulla's tax_deed
date-carry-forward, but the "rows" here are <li>/<p> prose, not table cells).
NOTE: clerk_sale_calendar_sources lists parser_hint='plain_tsv_text' for
hamilton, but the live page is NOT a TSV/pre block -- it's normal WordPress
prose (h2 date headers + ul/li for foreclosure, h2 date header + p blocks
for tax deed). The hint is stale; this parser follows the actual live markup.

foreclosure: each `<h2>DATE OF SALE – MONTH DD, YYYY</h2>` is followed by a
sibling `<ul>` whose <li> holds "Case No. YYYY-CA-NN; Plaintiff vs.
Defendant." -- one case per date header (verified: 3/3 live headers each had
exactly one Case No. in their <ul>).

tax_deed: a single `<h2>TAX DEED SALE – WEEKDAY, MONTH DD, YYYY @ ...</h2>`
date header applies to every `<p>PARCEL NO. ... Cert. No. ...</p>` sibling
beneath it until a non-"PARCEL"-prefixed <p> breaks the run (the standard
disclaimer paragraphs). Same date-carry-forward convention as wakulla's
tax_deed. Case number = certificate number (no separate court case number is
published on the tax deed calendar).
"""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://hamiltonclerk.com/list-of-upcoming-foreclosure-sales/"
TD_URL = "https://hamiltonclerk.com/tax-deeds/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

FC_DATE_HDR_RE = re.compile(r"DATE OF SALE\s*[–—-]\s*([A-Z]+)\s+(\d{1,2}),\s*(\d{4})")
FC_CASE_RE = re.compile(r"Case No\.?\s*(\d{4}-CA-\d+)")

TD_DATE_HDR_RE = re.compile(r"TAX DEED SALE\s*[–—-].*?([A-Z]+)\s+(\d{1,2}),\s*(\d{4})")
TD_PARCEL_RE = re.compile(r"PARCEL NO\.\s*([\d-]+)\s*Cert\.?\s*No\.?\s*(\d+)")
TD_APPLICANT_RE = re.compile(r"Tax Deed Applicant:\s*([^:]+?)\s*(?:Name\(s\) in which assessed:|Opening Bid|$)")
TD_ASSESSED_RE = re.compile(r"Name\(s\) in which assessed:\s*([^:]+?)\s*(?:Opening Bid|$)")

MONTHS = {m: i for i, m in enumerate(
    ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY",
     "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], start=1)}


def _month_date(month_name: str, dd: str, yyyy: str) -> str | None:
    mm = MONTHS.get(month_name.upper())
    if not mm:
        return None
    return f"{yyyy}-{mm:02d}-{int(dd):02d}"


def parse_foreclosure() -> list[dict]:
    resp = httpx.get(FC_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    rows_out = []
    for h in soup.find_all("h2"):
        txt = h.get_text(" ", strip=True)
        m = FC_DATE_HDR_RE.search(txt)
        if not m:
            continue
        sale_date = _month_date(*m.groups())
        sib = h.find_next_sibling()
        if not sib or sib.name != "ul":
            continue
        block_text = " ".join(li.get_text(" ", strip=True) for li in sib.find_all("li"))
        cm = FC_CASE_RE.search(block_text)
        if not cm:
            continue
        case_number = cm.group(1)
        title = block_text[cm.end():].lstrip("; ").split(". Judgment")[0].strip().rstrip(".")
        rows_out.append({
            "county_slug": "hamilton",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": sale_date,
            "cancelled": "CANCEL" in block_text.upper() or "RESCHEDUL" in block_text.upper(),
            "raw_comment": "",
            "case_title": title,
            "source_url": FC_URL,
        })

    if not rows_out:
        raise RuntimeError("hamilton foreclosure: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


def parse_tax_deed() -> list[dict]:
    resp = httpx.get(TD_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    rows_out = []
    for h in soup.find_all("h2"):
        txt = h.get_text(" ", strip=True)
        m = TD_DATE_HDR_RE.search(txt)
        if not m:
            continue
        sale_date = _month_date(*m.groups())
        sib = h.find_next_sibling()
        while sib is not None and sib.name == "p":
            block_text = sib.get_text(" ", strip=True)
            pm = TD_PARCEL_RE.match(block_text)
            if not pm:
                break  # ran into the disclaimer paragraphs after the parcel list
            parcel_no, cert_no = pm.groups()
            applicant_m = TD_APPLICANT_RE.search(block_text)
            assessed_m = TD_ASSESSED_RE.search(block_text)
            applicant = applicant_m.group(1).strip() if applicant_m else ""
            assessed = assessed_m.group(1).strip() if assessed_m else ""
            rows_out.append({
                "county_slug": "hamilton",
                "sale_type": "tax_deed",
                "case_number": cert_no,
                "sale_date": sale_date,
                "cancelled": "REDEEM" in block_text.upper(),
                "raw_comment": f"parcel {parcel_no}",
                "case_title": f"{applicant} VS {assessed}" if applicant or assessed else f"parcel {parcel_no}",
                "source_url": TD_URL,
            })
            sib = sib.find_next_sibling()

    if not rows_out:
        raise RuntimeError("hamilton tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    fc = parse_foreclosure()
    td = parse_tax_deed()
    print(f"foreclosure: {len(fc)} rows")
    print(f"tax_deed: {len(td)} rows, {sum(1 for r in td if r['cancelled'])} redeemed")

"""Volusia clerk foreclosure sales parser. Format Family: disclaimer-gated
ASP.NET WebForms repeater, grouped by date-header sections (new family).

app02.clerk.org/cm_sales/ is a clerk-hosted (Laura E. Roth, Clerk of Circuit
Court) "Clerk Sale Information" list. The initial GET renders only a
click-through disclaimer; the real case data lives behind an ASP.NET
UpdatePanel postback triggered by clicking the #ctl00_Content1_button_accept
link (javascript:__doPostBack(...) — a plain requests/BeautifulSoup GET
never sees it, a real browser is required). Once accepted, the page renders
a flat sequence of "MM/DD/YYYY - h:mm a.m./p.m." date headers, each followed
by a <table> of case rows:
  <a id="...link1">2025 10945 CIDL</a> | <span id="...label1">[Cancelled: ]PLAINTIFF v. DEFENDANT</span>
Case numbers use Volusia's native "YYYY NNNNN DIV" format WITH spaces
(e.g. "2025 12769 CIDL") — this already matches multi_county_auctions'
stored case_number for volusia verbatim, confirmed live 2026-08-13, so no
case-number normalization fallback is needed here (unlike lake/suwannee).

Tax deed (app02.clerk.org/or_td/) uses the same disclaimer gate but requires
selecting one of ~20 future sale dates one at a time from a dropdown with no
"view all" — out of scope for this parser, left unparsed pending a future
per-date iteration pass.
"""
import re
from datetime import date

from playwright.sync_api import sync_playwright

FC_URL = "https://app02.clerk.org/cm_sales/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

DATE_HEADER_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})\s*-\s*\d")
CASE_RE = re.compile(r"^\d{4}\s+\d+\s+[A-Z]{2,6}$")


def _fetch_rendered_text() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent=UA)
            page = ctx.new_page()
            page.goto(FC_URL, wait_until="networkidle", timeout=30000)
            page.click("#ctl00_Content1_button_accept", timeout=10000)
            page.wait_for_selector("a[id*='link1']", timeout=20000)
            page.wait_for_timeout(1500)
            return page.inner_text("body")
        finally:
            browser.close()


def parse_foreclosure() -> list[dict]:
    body_text = _fetch_rendered_text()
    lines = [ln.strip() for ln in body_text.split("\n") if ln.strip()]

    rows = []
    current_date = None
    for line in lines:
        m = DATE_HEADER_RE.match(line)
        if m:
            mm, dd, yyyy = m.groups()
            current_date = f"{yyyy}-{mm}-{dd}"
            continue
        if "\t" not in line:
            continue
        case_number, case_title = line.split("\t", 1)
        case_number = case_number.strip()
        case_title = case_title.strip()
        if not current_date or not CASE_RE.match(case_number):
            continue
        cancelled = case_title.startswith("Cancelled:")
        raw_comment = "Cancelled" if cancelled else ""
        if cancelled:
            case_title = case_title[len("Cancelled:"):].strip()
        rows.append({
            "county_slug": "volusia",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": current_date,
            "cancelled": cancelled,
            "raw_comment": raw_comment,
            "case_title": case_title,
            "source_url": FC_URL,
        })

    if not rows:
        raise RuntimeError("volusia foreclosure: parsed 0 rows from a rendered page — treat as FAILURE, not an empty calendar")

    return rows


if __name__ == "__main__":
    import json
    data = parse_foreclosure()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"parsed {len(data)} rows, {cancelled} cancelled")
    print(json.dumps(data[:3], indent=2))

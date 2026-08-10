"""Okeechobee clerk foreclosure parser. Family A (html_table, non-<table> variant).

Okeechobee does not publish a real HTML <table> — each sale is an
<article class="summaryDisplay"> with the case number in an <h2><a> and
Date/Plaintiff/Defendant packed into a single <p> separated by <br>. Parsed
via get_text(), not cell-by-cell. tax_deed intentionally NOT implemented here:
tax_deed_verified=false in clerk_sale_calendar_sources for this county even
though a tax_deed_url exists — out of scope until verified.
"""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://myokeeclerk.com/foreclosures"
CASE_RE = re.compile(r"^\d{4}-CA-\d+$")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


def _normalize_date(raw: str) -> str | None:
    m = re.match(r"^([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})$", raw.strip())
    if not m:
        return None
    month_name, dd, yyyy = m.groups()
    mm = MONTHS.get(month_name)
    if not mm:
        return None
    return f"{yyyy}-{mm:02d}-{int(dd):02d}"


def parse_foreclosure() -> list[dict]:
    """Okeechobee publishes each sale as an <article class="summaryDisplay">:
    case number in <h2><a>, and Date/Plaintiff/Defendant packed into a single
    <p> (line breaks via <br>, not separate cells). No dedicated status/comment
    field is exposed — cancellation is inferred from CANCEL/RESCHEDULE markers
    anywhere in the article text, same convention as brevard's comment scan."""
    resp = httpx.get(FC_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    articles = soup.find_all("article", class_="summaryDisplay")
    if not articles:
        raise RuntimeError("okeechobee foreclosure: no <article class='summaryDisplay'> found — page structure changed")

    rows = []
    for article in articles:
        header = article.find("h2")
        link = header.find("a") if header else None
        if link is None:
            continue
        case_number = link.get_text(strip=True)
        if not CASE_RE.match(case_number):
            continue

        body = article.find("div", class_="body")
        body_text = body.get_text(" ", strip=True) if body else ""

        date_m = re.search(r"Date:\s*([A-Z][a-z]+ \d{1,2},\s*\d{4})", body_text)
        sale_date_raw = date_m.group(1) if date_m else ""

        plaintiff_m = re.search(r"Plaintiff:\s*(.*?)\s*Defendant:", body_text)
        plaintiff = plaintiff_m.group(1).strip() if plaintiff_m else ""

        defendant_m = re.search(r"Defendant:\s*(.*)$", body_text)
        defendant = defendant_m.group(1).strip() if defendant_m else ""

        rows.append({
            "county_slug": "okeechobee",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_date(sale_date_raw),
            "cancelled": "CANCEL" in body_text.upper() or "RESCHEDULE" in body_text.upper(),
            "raw_comment": body_text,
            "case_title": f"{plaintiff} VS {defendant}".strip(" VS"),
            "source_url": FC_URL,
        })

    if not rows:
        raise RuntimeError("okeechobee foreclosure: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")

    return rows


if __name__ == "__main__":
    import json
    data = parse_foreclosure()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"parsed {len(data)} rows, {cancelled} cancelled")
    print(json.dumps(data[:2], indent=2))

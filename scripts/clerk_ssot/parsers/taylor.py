"""Taylor clerk foreclosure + tax deed parser. Family C (same WordPress theme
family as sumter.py — "table-label"-style div grid for foreclosure; embedded
Vue-component JSON attribute for tax deed).

Foreclosure sales render directly on /departments/foreclosure-sales/ as
`div.grid.md:grid-cols-3` blocks with label/strong pairs for Status, Sale
Date, Case Number, Judgement Amount, Parties, Address. Case numbers are
2-digit-year dash 3-digit-sequence space "CA" (e.g. "25-014 CA") — no zero
padding, no leading century digits, unlike sumter's "YYYY-CA-NNNNNN" form.
Status values observed live: "scheduled" and "cancelled".

Tax deed sales render via the same `<tax-deed-sales :taxdeeds="[...]">`
Vue widget as sumter.py, HTML-entity-encoded JSON baked into the page
source at /departments/tax-deeds/. Taylor's `file` field (e.g.
"TDA 26-031") is the clerk's own case-style identifier and is used as
case_number instead of `cert` (a certificate-of-sale number, not a case
number). `iso_sale_date` here includes a time component
("2026-08-17 11:00:00") — only the date portion is kept. Status values
observed live: "redeemed" (both rows on the 2026-08-10 pull). No
"scheduled" example was observed in this pull, but the field is scraped
directly so any future value is honored via the same cancelled-status set
used across the sumter.py counterpart.
"""
import html
import json
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://taylorclerk.com/departments/foreclosure-sales/"
TD_URL = "https://taylorclerk.com/departments/tax-deeds/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

FC_CASE_RE = re.compile(r"^\d{2}-\d{3} CA$")
TD_WIDGET_RE = re.compile(r'taxdeeds="(\[.*?\])"', re.S)

CANCELLED_STATUSES = {"cancelled", "canceled", "redeemed"}


def _normalize_slash_date(raw: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def parse_foreclosure() -> list[dict]:
    resp = httpx.get(FC_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    rows_out = []
    for block in soup.find_all("div", class_=lambda c: c and "grid" in c.split() and "md:grid-cols-3" in c.split()):
        labels = [lbl.get_text(strip=True) for lbl in block.find_all("label")]
        values = [s.get_text(strip=True) for s in block.find_all("strong")]
        d = dict(zip(labels, values))
        case_number = d.get("Case Number", "")
        if not FC_CASE_RE.match(case_number):
            continue
        status = d.get("Status", "")
        rows_out.append({
            "county_slug": "taylor",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_slash_date(d.get("Sale Date", "")),
            "cancelled": status.strip().lower() in CANCELLED_STATUSES,
            "raw_comment": status,
            "case_title": d.get("Parties", ""),
            "source_url": FC_URL,
        })

    if not rows_out:
        raise RuntimeError("taylor foreclosure: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


def parse_tax_deed() -> list[dict]:
    resp = httpx.get(TD_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    m = TD_WIDGET_RE.search(resp.text)
    if m is None:
        raise RuntimeError("taylor tax_deed: no <tax-deed-sales :taxdeeds=...> widget found — page structure changed")

    raw = html.unescape(m.group(1))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"taylor tax_deed: taxdeeds JSON failed to parse — {e}") from e

    rows_out = []
    for d in data:
        case_number = str(d.get("file", "")).strip()
        if not case_number:
            continue
        status = str(d.get("status", "")).strip()
        owner = html.unescape(str(d.get("owner") or ""))
        cert_holder = html.unescape(str(d.get("cert_holder", "")))
        sale_date = d.get("iso_sale_date")
        sale_date = sale_date[:10] if sale_date else None
        case_title = f"{cert_holder} vs {owner}" if owner else cert_holder
        rows_out.append({
            "county_slug": "taylor",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": sale_date,
            "cancelled": status.lower() in CANCELLED_STATUSES,
            "raw_comment": status,
            "case_title": case_title,
            "source_url": TD_URL,
        })

    if not rows_out:
        raise RuntimeError("taylor tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    fc = parse_foreclosure()
    td = parse_tax_deed()
    print(f"foreclosure: {len(fc)} rows, {sum(1 for r in fc if r['cancelled'])} cancelled")
    print(f"tax_deed: {len(td)} rows, {sum(1 for r in td if r['cancelled'])} cancelled/redeemed")

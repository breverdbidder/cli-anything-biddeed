"""Sumter clerk foreclosure + tax deed parser. Family C (WordPress "table-label"
div grid for foreclosure; embedded Vue-component JSON attribute for tax deed).

Foreclosure sales live at a nested sub-page (not the /courts/foreclosures/
landing page, which is just marketing copy) — each sale renders as a
`div.grid.md:grid-cols-3` block with `label.table-label` / `strong` pairs for
Status, Sale Date, Case Number, Judgement Amount, Parties, Address. Status
values observed live: "scheduled" and "cancelled".

Tax deed sales live at a further-nested sub-page and are NOT rendered as the
same div grid — they're passed to a `<tax-deed-sales :taxdeeds="[...]">` Vue
component as an HTML-entity-encoded JSON array baked directly into the page
source. This is more reliable than scraping rendered text: every field
(cert number, parcel, sale date in ISO form, status, cert holder/owner) is
already structured. `cert` (a certificate number, not a case number in the
foreclosure sense) is the closest stable per-row identifier the tax deed
side exposes, so it is used as case_number. `status` observed live:
"scheduled" (no redeemed/cancelled example seen in the live pull on
2026-08-10, but the field is scraped directly so any future value —
"redeemed", "cancelled", "canceled" — is honored via a superset check).
"""
import html
import json
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://www.sumterclerk.com/courts/foreclosures/foreclosure-sales/"
TD_URL = "https://www.sumterclerk.com/public-records/tax-deeds/tax-deed-sales/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

FC_CASE_RE = re.compile(r"^\d{4}-C[AC]-\d+$")
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
            "county_slug": "sumter",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_slash_date(d.get("Sale Date", "")),
            "cancelled": status.strip().lower() in CANCELLED_STATUSES,
            "raw_comment": status,
            "case_title": d.get("Parties", ""),
            "source_url": FC_URL,
        })

    if not rows_out:
        raise RuntimeError("sumter foreclosure: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


def parse_tax_deed() -> list[dict]:
    resp = httpx.get(TD_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    m = TD_WIDGET_RE.search(resp.text)
    if m is None:
        raise RuntimeError("sumter tax_deed: no <tax-deed-sales :taxdeeds=...> widget found — page structure changed")

    raw = html.unescape(m.group(1))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"sumter tax_deed: taxdeeds JSON failed to parse — {e}") from e

    rows_out = []
    for d in data:
        cert = str(d.get("cert", "")).strip()
        if not cert:
            continue
        status = str(d.get("status", "")).strip()
        owner = html.unescape(str(d.get("owner", "")))
        cert_holder = html.unescape(str(d.get("cert_holder", "")))
        sale_date = d.get("iso_sale_date")
        sale_date = sale_date[:10] if sale_date else None
        rows_out.append({
            "county_slug": "sumter",
            "sale_type": "tax_deed",
            "case_number": cert,
            "sale_date": sale_date,
            "cancelled": status.lower() in CANCELLED_STATUSES,
            "raw_comment": status,
            "case_title": f"{cert_holder} vs {owner}".strip(),
            "source_url": TD_URL,
        })

    if not rows_out:
        raise RuntimeError("sumter tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    fc = parse_foreclosure()
    td = parse_tax_deed()
    print(f"foreclosure: {len(fc)} rows, {sum(1 for r in fc if r['cancelled'])} cancelled")
    print(f"tax_deed: {len(td)} rows, {sum(1 for r in td if r['cancelled'])} cancelled/redeemed")

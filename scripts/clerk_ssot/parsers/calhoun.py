"""Calhoun clerk foreclosure + tax deed parser. Family C (foreclosure: WordPress
Tailwind label/value div-grid, one block per sale) + Family C-json (tax deed:
Vue component with the full dataset embedded as an HTML-escaped JSON attribute
-- no AJAX call needed, the data ships with the initial page load).
"""
import html as html_lib
import json
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://calhounclerk.com/court-services/property-sales/foreclosure-sales/"
TD_URL = "https://calhounclerk.com/court-services/property-sales/tax-deed-sales/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def _normalize_slash_date(raw: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def parse_foreclosure() -> list[dict]:
    """Each sale is a '<div class="... border-primary/20 ...">' block containing
    a 3-column label/<strong> (or label/<a> for the Address field, which links
    out to a Google search) grid: Status, Sale Date, Case Number, Judgement
    Amount, Address, Parcel ID."""
    resp = httpx.get(FC_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    blocks = soup.find_all("div", class_=lambda c: c and "border-primary/20" in c)
    rows = []
    for b in blocks:
        grid = b.find("div", class_=lambda c: c and "grid" in c)
        if grid is None:
            continue
        fields = {}
        for wrapper in grid.find_all("div", recursive=False):
            label = wrapper.find("label")
            if not label:
                continue
            val_tag = label.find_next_sibling(["strong", "a"])
            fields[label.get_text(strip=True)] = val_tag.get_text(strip=True) if val_tag else ""

        case_number = fields.get("Case Number", "").strip()
        if not case_number:
            continue
        status = fields.get("Status", "")
        rows.append({
            "county_slug": "calhoun",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_slash_date(fields.get("Sale Date", "")),
            "cancelled": status.upper() in ("CANCELLED", "CANCELED"),
            "raw_comment": status,
            "case_title": f"{fields.get('Address', '')} | parcel {fields.get('Parcel ID', '')}".strip(" |"),
            "source_url": FC_URL,
        })

    if not rows:
        raise RuntimeError("calhoun foreclosure: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows


def parse_tax_deed() -> list[dict]:
    """A Vue <tax-deed-sales> component ships the entire dataset as an
    HTML-entity-escaped JSON array in its `:taxdeeds` attribute -- no separate
    API call needed. cert == our case_number equivalent."""
    resp = httpx.get(TD_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    m = re.search(r':taxdeeds="(\[.*?\])"', resp.text, re.S)
    if not m:
        raise RuntimeError("calhoun tax_deed: no :taxdeeds=\"[...]\" attribute found — page structure changed")
    data = json.loads(html_lib.unescape(m.group(1)))

    rows = []
    for item in data:
        cert = (item.get("cert") or "").strip()
        if not cert:
            continue
        iso_date = item.get("iso_sale_date", "")
        sale_date = iso_date.split(" ")[0] if iso_date else None
        status = (item.get("status") or "").strip()
        notes = (item.get("notes") or "").strip()
        rows.append({
            "county_slug": "calhoun",
            "sale_type": "tax_deed",
            "case_number": cert,
            "sale_date": sale_date,
            "cancelled": status.upper() in ("CANCELLED", "CANCELED", "REDEEMED"),
            "raw_comment": f"{status} | {notes}".strip(" |"),
            "case_title": f"cert {cert} / {item.get('cert_holder', '').strip()} / parcel {item.get('parcel', '')}",
            "source_url": TD_URL,
        })

    if not rows:
        raise RuntimeError("calhoun tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows


if __name__ == "__main__":
    fc = parse_foreclosure()
    td = parse_tax_deed()
    print(f"foreclosure: {len(fc)} rows")
    print(f"tax_deed: {len(td)} rows, {sum(1 for r in td if r['cancelled'])} cancelled/redeemed")

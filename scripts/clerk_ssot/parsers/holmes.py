"""Holmes clerk foreclosure + tax deed parser. Family E (WP block heading/list —
no genuine case number published; case_title carries the full plaintiff/
defendant caption instead).

Foreclosures live at .../foreclosures-tax-deeds/foreclosures/ as a repeating
WordPress pattern: an <h2> holds the full case caption (plaintiff VS defendant,
no docket number anywhere on the page — verified against raw HTML, not just
rendered text), followed by a <ul class="wp-block-list"> of <li><strong>LABEL:
</strong>value</li> pairs (SALE DATE / FINAL JUDGMENT AMOUNT / PARCEL ID /
PROPERTY ADDRESS). Since Holmes never exposes a case number here, PARCEL ID
(unique, stable, always present) is used as the case_number surrogate,
prefixed "PARCEL-" so downstream consumers can tell it's derived, not a
genuine docket number.

Tax deeds live at .../foreclosures-tax-deeds/tax-deeds/ — this sub-page uses a
different (newer) site template than /foreclosures/ (near-zero wp-block
markup) and its boilerplate copy is templated from Liberty County ("Liberty
County Courthouse"), not Holmes-specific. As of this scrape it reads "There
are no properties on the list of tax deeds at this time." — a genuine empty
calendar, not a parse failure, so parse_tax_deed() is NOT implemented: there
is currently no row structure to verify against live data (Family unknown).
"""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

DATE_RE = re.compile(r"^([A-Z]+) (\d{1,2}),\s*(\d{4})$")
PARCEL_RE = re.compile(r"^[\d.\-A-Z]{5,}$")

MONTHS = {m: i for i, m in enumerate(
    ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY",
     "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], start=1)}


def _normalize_date(raw: str) -> str | None:
    m = DATE_RE.match(raw.strip().upper())
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
    soup = BeautifulSoup(resp.text, "lxml")
    main = soup.find(id="content")
    if main is None:
        raise RuntimeError(f"holmes foreclosure: no #content found at {FC_URL} — page structure changed")

    h2s = main.find_all("h2")
    if len(h2s) < 2:
        raise RuntimeError("holmes foreclosure: no case-caption <h2> blocks found — page structure changed")

    rows = []
    for h2 in h2s[1:]:  # skip the "Upcoming Foreclosure Sales" section header
        case_title = h2.get_text(" ", strip=True)
        if not case_title:
            continue

        fields = {}
        sib = h2.find_next_sibling()
        while sib and sib.name != "h2":
            if sib.name == "ul":
                for li in sib.find_all("li"):
                    label_tag = li.find("strong")
                    if label_tag is None:
                        continue
                    label = label_tag.get_text(strip=True).rstrip(":").upper()
                    value = li.get_text(" ", strip=True)
                    value = value[len(label_tag.get_text(strip=True)):].strip()
                    fields[label] = value
            sib = sib.find_next_sibling()

        parcel_id = fields.get("PARCEL ID", "")
        if not PARCEL_RE.match(parcel_id):
            continue  # no stable identifier to key this row on — skip rather than fabricate

        sale_date_raw = fields.get("SALE DATE", "")
        amount = fields.get("FINAL JUDGMENT AMOUNT", "")
        address = fields.get("PROPERTY ADDRESS", "")
        raw_comment = " | ".join(p for p in (f"judgment {amount}" if amount else "", address) if p)

        rows.append({
            "county_slug": "holmes",
            "sale_type": "foreclosure",
            "case_number": f"PARCEL-{parcel_id}",
            "sale_date": _normalize_date(sale_date_raw),
            "cancelled": False,
            "raw_comment": raw_comment,
            "case_title": case_title,
            "source_url": FC_URL,
        })

    if not rows:
        raise RuntimeError("holmes foreclosure: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")

    return rows


if __name__ == "__main__":
    import json
    data = parse_foreclosure()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"foreclosure: {len(data)} rows, {cancelled} cancelled")
    print(json.dumps(data, indent=2))
    print(
        "tax_deed: SKIPPED — live page (courts/foreclosures-tax-deeds/tax-deeds/) "
        "reads 'There are no properties on the list of tax deeds at this time.' "
        "Genuine empty calendar; no row structure exists yet to verify a parser against."
    )

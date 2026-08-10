"""Lafayette clerk foreclosure + tax deed parser. Family C (WordPress
div/label/strong card grid, not a <table>). Same theme family as Madison:
each sale is one `div.even:bg-gray-100` card containing repeated
`div.w-full > label (field name) + strong` (or `a` for Address) pairs:
Status, Sale Date, Case Number, Judgement Amount, Parties, Address,
Parcel ID.

Both foreclosure and tax deed pages share the identical card markup, so one
`_parse_cards()` helper drives both parse functions. Cancellation is
signalled by the Status field (observed value: "scheduled" only -- no
CANCELLED/RESCHEDULED value seen live as of 2026-08-10, matched
case-insensitively for "cancel" if the clerk ever posts one).

NOTE: as of 2026-08-10 the live Tax Deed Sales page has zero card rows --
the WordPress template prints the literal sentence "There are no properties
on the list of tax deeds at this time." in place of the card grid (page
loads fine, statute boilerplate / Important Information section intact).
That is a genuinely empty calendar (Lafayette is FL's least populous
county), not a parse failure -- but per house rule parse_tax_deed() still
can't distinguish "genuinely empty" from "format changed" on 0 rows, so it
raises like every other parser here. If this starts failing once a real
tax deed sale is scheduled, that's the signal the card selector needs
adjusting.
"""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://www.lafayetteclerk.com/departments-services/court-services/foreclosure-sales/"
TD_URL = "https://www.lafayetteclerk.com/departments-services/clerk-services/tax-deeds/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"^\d{8,}[A-Z]{2,}[A-Z0-9]*$")


def _normalize_date(raw: str) -> str | None:
    """'08/13/2026 11:00 am' -> '2026-08-13'. Drop the time-of-day suffix."""
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _parse_cards(url: str) -> list[dict]:
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select("div.even\\:bg-gray-100")

    out = []
    for card in cards:
        fields = {}
        for label in card.find_all("label"):
            key = label.get_text(strip=True)
            value_el = label.find_parent("div").find(["strong", "a"])
            fields[key] = value_el.get_text(strip=True) if value_el else ""
        if "Case Number" not in fields:
            continue
        out.append(fields)
    return out


def parse_foreclosure() -> list[dict]:
    rows_out = []
    for c in _parse_cards(FC_URL):
        case_number = c.get("Case Number", "")
        if not case_number or not CASE_RE.match(case_number):
            continue
        status = c.get("Status", "")
        rows_out.append({
            "county_slug": "lafayette",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_date(c.get("Sale Date", "")),
            "cancelled": "cancel" in status.lower(),
            "raw_comment": status,
            "case_title": c.get("Parties", ""),
            "source_url": FC_URL,
        })
    if not rows_out:
        raise RuntimeError("lafayette foreclosure: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")
    return rows_out


def parse_tax_deed() -> list[dict]:
    rows_out = []
    for c in _parse_cards(TD_URL):
        case_number = c.get("Case Number", "")
        if not case_number:
            continue
        status = c.get("Status", "")
        rows_out.append({
            "county_slug": "lafayette",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": _normalize_date(c.get("Sale Date", "")),
            "cancelled": "cancel" in status.lower(),
            "raw_comment": status,
            "case_title": c.get("Parties", ""),
            "source_url": TD_URL,
        })
    if not rows_out:
        raise RuntimeError("lafayette tax_deed: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")
    return rows_out


if __name__ == "__main__":
    import json
    fc = parse_foreclosure()
    print(f"foreclosure: {len(fc)} rows, {sum(1 for r in fc if r['cancelled'])} cancelled")
    print(json.dumps(fc, indent=2))
    try:
        td = parse_tax_deed()
        print(f"tax_deed: {len(td)} rows, {sum(1 for r in td if r['cancelled'])} cancelled")
    except RuntimeError as e:
        print(f"tax_deed: {e}")

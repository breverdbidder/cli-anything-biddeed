"""Madison clerk foreclosure + tax deed parser. Family C (WordPress
div/label/strong card grid, not a <table> -- each sale is one
`div.bg-white.shadow-xl` containing `label` (field name) / `strong` (or
`a` for the Address field) pairs: Status, Sale Date, Case Number, Judgment
Amount, Parties, Address, Parcel ID.

Both foreclosure and tax deed pages share the identical card markup, so one
`_parse_cards()` helper drives both parse functions. Cancellation is
signalled by the Status field (observed values: "scheduled" -- no
CANCELLED/RESCHEDULED value seen live as of 2026-08-10, but the field is
still the correct signal to check per-row if the clerk ever posts one).

NOTE: as of 2026-08-10 the live Tax Deed Sales page has zero card rows
(the "Upcoming Tax Deed Sales" section is present but empty -- confirmed by
grep, no "Case Number" label appears anywhere in the tax-deed HTML). That is
a genuinely empty calendar, not a parse failure, but per house rule
parse_tax_deed() still can't distinguish "genuinely empty" from "format
changed" on 0 rows, so it will raise like every other parser here. If this
starts failing consistently once a real tax deed sale is scheduled, that's
the signal the card selector needs adjusting.
"""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://www.madisonclerk.com/departments-services/property-sales/foreclosure-sales/"
TD_URL = "https://www.madisonclerk.com/departments-services/property-sales/tax-deed-sales/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

FC_CASE_RE = re.compile(r"^\d{2}-\d+-CA$")
TD_CASE_RE = re.compile(r"^\d{2,4}-?\d*-?TD$", re.I)


def _normalize_date(raw: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _parse_cards(url: str) -> list[dict]:
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select("div.bg-white.shadow-xl")

    out = []
    for card in cards:
        fields = {}
        for label in card.find_all("label"):
            key = label.get_text(strip=True)
            value_el = label.find_next_sibling(["strong", "a"])
            fields[key] = value_el.get_text(strip=True) if value_el else ""
        if "Case Number" not in fields:
            continue
        out.append({
            "status": fields.get("Status", ""),
            "sale_date": fields.get("Sale Date", ""),
            "case_number": fields.get("Case Number", ""),
            "parties": fields.get("Parties", ""),
            "judgment": fields.get("Judgment Amount", ""),
        })
    return out


def parse_foreclosure() -> list[dict]:
    rows_out = []
    for c in _parse_cards(FC_URL):
        if not FC_CASE_RE.match(c["case_number"]):
            continue
        status = c["status"]
        rows_out.append({
            "county_slug": "madison",
            "sale_type": "foreclosure",
            "case_number": c["case_number"],
            "sale_date": _normalize_date(c["sale_date"]),
            "cancelled": status.upper() not in ("", "SCHEDULED"),
            "raw_comment": status,
            "case_title": c["parties"],
            "source_url": FC_URL,
        })
    if not rows_out:
        raise RuntimeError("madison foreclosure: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


def parse_tax_deed() -> list[dict]:
    rows_out = []
    for c in _parse_cards(TD_URL):
        if not c["case_number"]:
            continue
        status = c["status"]
        rows_out.append({
            "county_slug": "madison",
            "sale_type": "tax_deed",
            "case_number": c["case_number"],
            "sale_date": _normalize_date(c["sale_date"]),
            "cancelled": status.upper() not in ("", "SCHEDULED"),
            "raw_comment": status,
            "case_title": c["parties"],
            "source_url": TD_URL,
        })
    if not rows_out:
        raise RuntimeError("madison tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    fc = parse_foreclosure()
    print(f"foreclosure: {len(fc)} rows")
    try:
        td = parse_tax_deed()
        print(f"tax_deed: {len(td)} rows")
    except RuntimeError as e:
        print(f"tax_deed: {e}")

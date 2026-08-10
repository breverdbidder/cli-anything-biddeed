"""Liberty clerk foreclosure + tax deed parser. Family C (WordPress
label/strong card grid, same KMA-built theme family as lafayette.py /
madison.py -- not a <table>).

As of 2026-08-10 BOTH live pages render zero sale cards. Each page's
"Upcoming ... Sales" <h2> is followed directly by a
`<div class="prose md:prose-lg ...">` containing only a literal empty-state
sentence, no `label`/`Case Number` markup anywhere in the document:
  Foreclosure: "There are no foreclosure sales available at this time."
  Tax Deed:    "There are no properties on the list of tax deeds at this time."
Both pages are otherwise fully intact (nav, statute boilerplate, footer,
contact info all present) -- a 200 response with genuinely empty content,
not a broken/gated scrape. Liberty is one of FL's least populous counties,
so zero scheduled sales on a given day is plausible.

The card selector below is written from the sibling lafayette/madison
theme (label "Case Number" -> find_next_sibling "strong"/"a" for the
value, fields: Status / Sale Date / Case Number / Judgment(Judgement)
Amount / Parties / Address / Parcel ID) since Liberty ships the same
KMA WordPress theme family and would be expected to render sale rows the
same way once populated. This has NOT been verified against a live
populated card (none exist right now) -- if it starts failing once Liberty
posts a real sale, the label text / block wrapper class is the first thing
to re-check against the live HTML.

Per house rule, parse_foreclosure()/parse_tax_deed() cannot distinguish
"genuinely empty calendar" from "format changed" on 0 rows, so both still
raise RuntimeError on zero parsed rows rather than silently returning [].
"""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://libertyclerk.com/courts/foreclosure-sales/"
TD_URL = "https://libertyclerk.com/courts/tax-deeds/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"^\d{2,4}-?\d*-?(CA|CC|TD)[A-Z0-9-]*$", re.I)


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

    case_labels = soup.find_all("label", string=re.compile(r"Case Number"))

    out = []
    for case_label in case_labels:
        block = case_label.find_parent("div", class_=re.compile(r"\bgrid\b"))
        if block is None:
            block = case_label.parent

        def _field(name: str) -> str:
            lbl = block.find("label", string=re.compile(name))
            if lbl is None:
                return ""
            value_el = lbl.find_next_sibling(["strong", "a"])
            return value_el.get_text(strip=True) if value_el else ""

        case_number = _field("Case Number")
        if not case_number:
            continue

        out.append({
            "status": _field("Status"),
            "sale_date": _field("Sale Date"),
            "case_number": case_number,
            "parties": _field("Parties"),
        })
    return out


def parse_foreclosure() -> list[dict]:
    rows_out = []
    for c in _parse_cards(FC_URL):
        if not CASE_RE.match(c["case_number"]):
            continue
        status = c["status"]
        rows_out.append({
            "county_slug": "liberty",
            "sale_type": "foreclosure",
            "case_number": c["case_number"],
            "sale_date": _normalize_date(c["sale_date"]),
            "cancelled": "cancel" in status.lower(),
            "raw_comment": status,
            "case_title": c["parties"],
            "source_url": FC_URL,
        })
    if not rows_out:
        raise RuntimeError("liberty foreclosure: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")
    return rows_out


def parse_tax_deed() -> list[dict]:
    rows_out = []
    for c in _parse_cards(TD_URL):
        if not c["case_number"]:
            continue
        status = c["status"]
        rows_out.append({
            "county_slug": "liberty",
            "sale_type": "tax_deed",
            "case_number": c["case_number"],
            "sale_date": _normalize_date(c["sale_date"]),
            "cancelled": "cancel" in status.lower(),
            "raw_comment": status,
            "case_title": c["parties"],
            "source_url": TD_URL,
        })
    if not rows_out:
        raise RuntimeError("liberty tax_deed: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")
    return rows_out


if __name__ == "__main__":
    for name, fn in (("foreclosure", parse_foreclosure), ("tax_deed", parse_tax_deed)):
        try:
            rows = fn()
            print(f"{name}: {len(rows)} rows, {sum(1 for r in rows if r['cancelled'])} cancelled")
        except RuntimeError as e:
            print(f"{name}: {e}")

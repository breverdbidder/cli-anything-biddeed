"""Levy clerk foreclosure + tax deed parser.

Foreclosure: Family C (WordPress div/label/strong card grid, same KMA-built
theme family as liberty.py/lafayette.py/madison.py -- keriganmarketing.com
credited in the footer, identical FAQ-accordion + prose markup). As of
2026-08-10 the live page renders zero sale cards: the "Upcoming Foreclosure
Sales" <h2> is followed directly by a `<div class="prose md:prose-lg ...">`
containing only the literal empty-state sentence "There are no foreclosure
sales available at this time." -- no `label`/"Case Number" markup anywhere
in the document (grep-verified, 0 <label> elements total). The page is
otherwise fully intact (nav, statute boilerplate, footer, contact info all
present) -- a 200 response with genuinely empty content, not a broken/gated
scrape. No populated card exists right now to confirm the exact wrapper
class Levy's instance uses (liberty uses `div[class*=grid]`, lafayette uses
`div.even:bg-gray-100`, madison uses `div.bg-white.shadow-xl` -- all three
differ), so `_parse_cards()` here walks up from each "Case Number" label to
the nearest ancestor holding multiple `label` children instead of guessing
a class name, which should be robust to whichever variant Levy ships once a
sale is posted.

Tax deed: NOT the WordPress page (levyclerk.com/.../tax-deed-sales/ is a
disclaimer wall with no listing of its own) -- the real sale data lives on
Levy's independently hosted TaxSmartWeb search portal
(online.levyclerk.com/TaxSmartWeb), a plain ASP.NET/jQuery site with NO
login/paywall (confirmed: fresh unauthenticated GET/POST returns real JSON).
This is Levy's own in-house system, not RealAuction/RealTaxDeed/bid4assets.
Its "Sale Date" search tab posts `SearchSaleDateFrom`/`SearchSaleDateTo`
(exact strings copied from the <SELECT> dropdown, which lists real scheduled
auction dates going back to 2008 and forward through the last-posted future
date) to `/TaxSmartWeb/` to set server-side session/search state, then a
separate `/TaxSmartWeb/Home/GridSearchData?SearchType=Sale%20Date` endpoint
returns the matching rows as JSON (jqGrid backend). The grid endpoint has no
independent date filter of its own -- whatever range was last POSTed is what
it returns, capped at 1000 rows -- so scoping the query to "upcoming sales
only" (this parser's job) means the POST must only span today's dropdown
date through the furthest future dropdown date, NOT the full 2008-> archive
(verified live: a full-archive POST returns exactly 1000 historical rows,
all dated 2008-2014, none of them upcoming -- that is the grid's row cap
kicking in on old data, not real signal).

Verified live 2026-08-10: POSTing today's dropdown date through the
furthest-future one returns exactly 1 row -- Aug-10-2026 case 2026-4162TD,
status SOLD (today's sale, already run). Querying every other future-dated
dropdown option (Sep/Oct/Nov/Dec 2026) individually returns 0 rows each, and
a full Status=SALE ("scheduled, not yet sold") sweep across the entire
2008-2026 range returns only one stale 2021 placeholder row. That means
Levy genuinely has zero tax deed sales scheduled beyond today as of
2026-08-10 -- a real empty calendar on a live, working, non-fabricated data
source, not a scrape failure.

Per house rule, neither parse function can distinguish "genuinely empty
calendar" from "format changed" on 0 rows, so both still raise RuntimeError
rather than silently returning [].
"""
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://levyclerk.com/departments-services/court-services/foreclosure-sales/"
TD_PORTAL_URL = "https://online.levyclerk.com/TaxSmartWeb/"
TD_GRID_URL = "https://online.levyclerk.com/TaxSmartWeb/Home/GridSearchData"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"^\d{2,4}-?\d*-?(CA|CC|TD)[A-Z0-9-]*$", re.I)

# TaxSmartWeb's "Sale Date" search requires the exact <OPTION value=...>
# string from the dropdown, e.g. "Monday, December 14, 2026 10:00 AM" -- not
# an arbitrary date string. The dropdown mixes past AND future scheduled
# auction dates (newest first); we parse the leading "Month D, YYYY" out of
# each option to find which ones are >= today.
TD_OPTION_DATE_RE = re.compile(r"^[A-Za-z]+, ([A-Za-z]+ \d{1,2}, \d{4})")


def _normalize_date_slash(raw: str) -> str | None:
    """'8/10/2026' -> '2026-08-10'."""
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw.strip())
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
        # Walk up to the nearest ancestor that holds more than one <label>
        # (i.e. the whole card, not just this field's wrapper div) -- the
        # exact wrapper class varies per Levy's KMA theme instance and can't
        # be confirmed while the live page has zero populated cards.
        block = case_label.parent
        while block is not None and len(block.find_all("label")) < 2:
            block = block.parent
        if block is None:
            block = case_label.find_parent("div") or case_label.parent

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
            "county_slug": "levy",
            "sale_type": "foreclosure",
            "case_number": c["case_number"],
            "sale_date": _normalize_date_slash(c["sale_date"]) or c["sale_date"] or None,
            "cancelled": "cancel" in status.lower(),
            "raw_comment": status,
            "case_title": c["parties"],
            "source_url": FC_URL,
        })
    if not rows_out:
        raise RuntimeError("levy foreclosure: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")
    return rows_out


def _future_dropdown_bounds(client: httpx.Client) -> tuple[str, str]:
    """Fetch the live SearchSaleDateFrom <SELECT> and return the (earliest
    upcoming, latest upcoming) option strings, i.e. today's scheduled sale
    date (if any) through the furthest future one. The dropdown mixes past
    and future dates newest-first, so this filters by parsing each option's
    embedded date rather than assuming position."""
    resp = client.get(TD_PORTAL_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    select = soup.find("select", id="SearchSaleDateFrom")
    if select is None:
        raise RuntimeError("levy tax_deed: SearchSaleDateFrom <select> not found — page structure changed")

    today = datetime.now().date()
    future_options = []
    for opt in select.find_all("option"):
        value = opt.get("value", "").strip()
        m = TD_OPTION_DATE_RE.match(value)
        if not m:
            continue
        try:
            opt_date = datetime.strptime(m.group(1), "%B %d, %Y").date()
        except ValueError:
            continue
        if opt_date >= today:
            future_options.append((opt_date, value))

    if not future_options:
        raise RuntimeError("levy tax_deed: no upcoming dates found in SearchSaleDateFrom dropdown — treat as FAILURE, not an empty calendar")

    future_options.sort(key=lambda t: t[0])
    return future_options[0][1], future_options[-1][1]


def parse_tax_deed() -> list[dict]:
    """TaxSmartWeb requires a stateful POST (sets the search filter in the
    server session) before the JSON grid endpoint reflects it — a fresh GET
    to the grid with no prior POST returns 0 rows regardless of real data
    (verified live). The POST range is scoped to today->furthest-future
    dropdown date so this returns upcoming sales only, not the full
    2008-> historical archive (which hits the grid's 1000-row cap)."""
    with httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as client:
        date_from, date_to = _future_dropdown_bounds(client)

        post_resp = client.post(TD_PORTAL_URL, data={
            "SearchSaleDateFrom": date_from,
            "SearchSaleDateTo": date_to,
            "buttonSubmitSaleDate": "Search",
        })
        post_resp.raise_for_status()

        grid_resp = client.get(TD_GRID_URL, params={
            "SearchType": "Sale Date",
            "page": 1,
            "rows": 1000,
            "sidx": "SaleDate",
            "sord": "asc",
        })
        grid_resp.raise_for_status()
        data = grid_resp.json()

    rows_out = []
    for row in data.get("rows", []):
        cell = row.get("cell", [])
        if len(cell) < 6:
            continue
        applicant, case_number, cert_no, parcel_id, sale_date_raw, status = cell[0], cell[1], cell[2], cell[3], cell[4], cell[5]
        owners = cell[9] if len(cell) > 9 else ""
        if not case_number:
            continue
        rows_out.append({
            "county_slug": "levy",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": _normalize_date_slash(sale_date_raw),
            "cancelled": status.upper() in ("REDEEMED", "PULLED", "CANCELLED", "NO BID"),
            "raw_comment": f"{status} | cert {cert_no} | parcel {parcel_id}".strip(" |"),
            "case_title": f"{applicant} vs {owners}".strip(" vs"),
            "source_url": TD_PORTAL_URL,
        })
    if not rows_out:
        raise RuntimeError("levy tax_deed: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")
    return rows_out


if __name__ == "__main__":
    for name, fn in (("foreclosure", parse_foreclosure), ("tax_deed", parse_tax_deed)):
        try:
            rows = fn()
            print(f"{name}: {len(rows)} rows, {sum(1 for r in rows if r['cancelled'])} cancelled")
        except RuntimeError as e:
            print(f"{name}: {e}")

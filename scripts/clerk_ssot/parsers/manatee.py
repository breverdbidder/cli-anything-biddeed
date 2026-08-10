"""Manatee clerk foreclosure sales parser. Family B (html_table-adjacent --
Bootstrap panel/list-group, not a <table>, but same date-carry-forward shape
as wakulla: `div.panel.panel-info` is one sale-date group, `div.panel-heading
> strong` holds the date ("Tuesday, August 4, 2026"), and each
`li.list-group-item` beneath it is one case: bold case number span (e.g.
"2025CA002931AX"), judgment $ amount, "Judgement made: <date>", then a
trailing status token (SOLD ONLINE | CANCELLED ONLINE | PENDING ONLINE).

records.manateeclerk.com is the clerk's own Public Records Hub -- a genuine
static/server-rendered listing, NOT the RealForeclose auction platform
itself (that lives at manatee.realforeclose.com and is linked from this page
but never fetched here, per the RealAuction-family guardrail).

tax_deed is NOT implemented: Manatee's tax deed page
(manateeclerk.com/departments/tax-deeds/) states plainly that "A calendar of
upcoming tax deed sales is available at www.manatee.realforeclose.com" --
there is no independent clerk-hosted tax deed list, only a pointer to
RealForeclose. Out of scope per guardrail.
"""
import re

import httpx
from bs4 import BeautifulSoup

FC_URL = "http://records.manateeclerk.com/CourtRecords/Search/ForeclosureSales"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"^\d{4}[A-Z]{2}\d{6}[A-Z]{2}$")

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}
_MONTH_ALT = "|".join(MONTHS)
DATE_RE = re.compile(rf"({_MONTH_ALT})\s+(\d{{1,2}}),\s*(\d{{4}})")
JUDGMENT_RE = re.compile(r"made:\s*(\d{1,2})/(\d{1,2})/(\d{4})")


def _normalize_long_date(raw: str) -> str | None:
    m = DATE_RE.search(raw)
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

    panels = soup.select("div.panel.panel-info")
    if not panels:
        raise RuntimeError("manatee foreclosure: no panel.panel-info date groups found — page structure changed")

    rows_out = []
    for panel in panels:
        heading = panel.select_one("div.panel-heading strong")
        sale_date = _normalize_long_date(heading.get_text(strip=True)) if heading else None

        for li in panel.select("ul.list-group li.list-group-item"):
            spans = li.find_all("span")
            case_span = next((s for s in spans if CASE_RE.match(s.get_text(strip=True))), None)
            if case_span is None:
                continue
            case_number = case_span.get_text(strip=True)
            text = li.get_text(" ", strip=True)
            words = text.split()
            status = " ".join(words[-2:]) if len(words) >= 2 else ""
            rows_out.append({
                "county_slug": "manatee",
                "sale_type": "foreclosure",
                "case_number": case_number,
                "sale_date": sale_date,
                "cancelled": status.upper().startswith("CANCELLED"),
                "raw_comment": status,
                "case_title": case_number,
                "source_url": FC_URL,
            })

    if not rows_out:
        raise RuntimeError("manatee foreclosure: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    fc = parse_foreclosure()
    cancelled = sum(1 for r in fc if r["cancelled"])
    print(f"foreclosure: {len(fc)} rows, {cancelled} cancelled")

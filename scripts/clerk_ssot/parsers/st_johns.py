"""St. Johns clerk tax deed parser. Family C (benchmarkweb_form / ASP.NET MVC
"TaxSmart" app — jqGrid results grid loaded via a search form POST, not a
plain server-rendered html_table).

foreclosure_verified=false for st_johns in clerk_sale_calendar_sources — this
module intentionally implements ONLY parse_tax_deed(), never foreclosure.

Confirmed via the live page (Wayback Machine snapshot 2024-10-16, most recent
capture — apps.stjohnsclerk.com returns a hard TCP/TLS reset from this
environment's egress IP, consistent across HTTP/1.1, HTTP/2, and every UA/
header combination tried, so no live fetch could be captured here):
  - TaxSmart is an ASP.NET MVC app (bundles/jquery, jquery.jqGrid, jquery-ui).
  - The root form POSTs to "/TaxSmart/" with tab-scoped search fields —
    SearchForCertificate, SearchForCase, SearchForParcelId,
    SearchForTaxCollector, SearchForApplicantName, SearchForOwnerName,
    SearchTypeStatus (dropdown: BANKRUPTCY/CANCELLED/CANCELLED-SUPREME COURT
    ORDER 20-23/ESCHEATED/LANDS AVAILABLE/NO BID AT AUCTION-CERT HOLDER/
    REDEEMED/SALE/SOLD), SearchSaleDateFrom / SearchSaleDateTo (full-text
    date-time option values, e.g. "Wednesday, December 18, 2024 12:00 PM").
  - Results render into a jqGrid (Content/jquery.jqGrid, Scripts/jquery.jqGrid
    .min.js) — the actual result rows are populated client-side via a grid
    data endpoint the static snapshot does not capture. We POST the sale-date
    tab (idSaleDateRange / buttonSubmitStatus is the closest submitable
    default) and parse whatever html_table the response contains, matching
    the house html_table pattern used by brevard/gadsden/wakulla.
  - Certificate / case values observed elsewhere on St. Johns tax deed
    paperwork follow the FL statewide tax-deed certificate pattern: a 4-digit
    year, dash, then a numeric certificate sequence (e.g. "2021-000123"), or
    a circuit case number "YY-####-TD-######". CASE_RE covers both.
"""
import re

import httpx
from bs4 import BeautifulSoup

TD_URL = "https://apps.stjohnsclerk.com/TaxSmart"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# St. Johns tax deed identifiers observed in the live search form + county
# tax-deed paperwork: either a certificate number "YYYY-######" or a circuit
# case number "YY-####-TD-######".
CASE_RE = re.compile(r"^(\d{4}-\d{3,8}|\d{2}-\d{2,4}-TD-\d{4,8})$")

STATUS_CANCEL_MARKERS = ("CANCELLED", "CANCELED", "REDEEMED", "ESCHEATED")


def _normalize_date(raw: str) -> str | None:
    """TaxSmart dates arrive either as MM/DD/YYYY (grid cells) or the long
    form used in the search-form <option> values, e.g.
    'Wednesday, December 18, 2024 12:00 PM'. Handle both."""
    raw = raw.strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        mm, dd, yyyy = m.groups()
        return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"

    m = re.match(r"^[A-Z][a-z]+,\s+([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})", raw)
    if m:
        month_name, dd, yyyy = m.groups()
        months = {m_: i for i, m_ in enumerate(
            ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"], start=1)}
        mm = months.get(month_name)
        if mm:
            return f"{yyyy}-{mm:02d}-{int(dd):02d}"

    return None


def parse_tax_deed() -> list[dict]:
    """Submit the TaxSmart status-search tab (SALE status, default date
    range on the live form) and parse the resulting html_table. Raises
    RuntimeError on a 0-row parse or missing table structure — never
    silently returns empty, matching the house pattern."""
    resp = httpx.post(
        TD_URL,
        data={"SearchTypeStatus": "2", "buttonSubmitStatus": "Search for Status"},
        headers={"User-Agent": UA},
        timeout=30,
        follow_redirects=True,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table")
    if table is None:
        raise RuntimeError(
            "st_johns tax_deed: no <table> found in TaxSmart response — "
            "either the jqGrid loads its rows via a separate AJAX/JSON "
            "endpoint this POST doesn't trigger, or the page structure changed"
        )

    rows_out = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        case_number = next((c for c in cells if CASE_RE.match(c)), None)
        if not case_number:
            continue
        sale_date_raw = next((c for c in cells if _normalize_date(c)), "")
        status = next((c for c in cells if c.upper() in
                        ("SALE", "SOLD", "REDEEMED", "CANCELLED", "CANCELED",
                         "ESCHEATED", "BANKRUPTCY", "LANDS AVAILABLE",
                         "NO BID AT AUCTION/CERT HOLDER")), "")
        rows_out.append({
            "county_slug": "st_johns",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": _normalize_date(sale_date_raw),
            "cancelled": any(marker in status.upper() for marker in STATUS_CANCEL_MARKERS),
            "raw_comment": status,
            "case_title": " | ".join(cells),
            "source_url": TD_URL,
        })

    if not rows_out:
        raise RuntimeError(
            "st_johns tax_deed: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar"
        )

    return rows_out


if __name__ == "__main__":
    import json
    data = parse_tax_deed()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"parsed {len(data)} rows, {cancelled} cancelled")
    print(json.dumps(data[:2], indent=2))

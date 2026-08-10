"""St. Johns clerk tax deed parser. Family C (TaxSmart — ASP.NET MVC app,
session-scoped search form + jqGrid JSON data endpoint).

foreclosure_verified=false for st_johns in clerk_sale_calendar_sources — this
module intentionally implements ONLY parse_tax_deed(), never foreclosure.

Confirmed live 2026-08-10 (this environment's egress reaches
apps.stjohnsclerk.com fine over plain HTTPS — a prior session recorded a hard
TCP/TLS reset from a different sandbox's egress IP; that no longer applies).

Real flow (verified against live responses, not guessed from a static
snapshot):
  1. GET /TaxSmart/ to establish a session cookie.
  2. The "Status" tab search form POSTs to /TaxSmart/ with
     SearchTypeStatus=2 (the <option value='2' selected>SALE</option> —
     "SALE" is the only status meaning "scheduled, not yet occurred"; the
     other status values -- REDEEMED/SOLD/ESCHEATED/BANKRUPTCY/CANCELLED/
     NO BID AT AUCTION/CERT HOLDER -- are all historical outcomes and were
     the reason the previous "Sale Date" tab approach returned only rows
     dated up to 2018: it silently ignores upcoming SALE-status rows and is
     capped at 1000 historical results.
  3. The search POST just sets the session's saved criteria; the actual
     results come from a separate JSON endpoint the page's jqGrid config
     points at: GET /TaxSmart/Home/GridSearchData?SearchType=Status
     (same session/cookie). Response shape: {"total","page","records",
     "rows":[{"id":..,"cell":[Applicant, CaseNumber, CertificateNumber,
     ParcelID, SaleDate, Status, ...amounts, OwnerName]}]}.
  4. CaseNumber (cell[1]) is the real case identifier, format "TD26-0024"
     (literal "TD" + 2-digit year + dash + sequence) -- this is what we use
     as case_number, not the bare CertificateNumber.
"""
from datetime import date, timedelta

import httpx

BASE_URL = "https://apps.stjohnsclerk.com/TaxSmart"
GRID_URL = "https://apps.stjohnsclerk.com/TaxSmart/Home/GridSearchData"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

SALE_STATUS_VALUE = "2"  # <option value='2' selected>SALE</option>
SEARCH_WINDOW_DAYS = 180  # generous; run_parity.py's own 90-day window does the real filtering


def _mmddyyyy(d: date) -> str:
    return f"{d.month}/{d.day}/{d.year}"


def parse_tax_deed() -> list[dict]:
    today = date.today()
    with httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as client:
        client.get(BASE_URL)
        client.post(BASE_URL, data={
            "SearchTypeStatus": SALE_STATUS_VALUE,
            "dateFromStatus": _mmddyyyy(today),
            "dateToStatus": _mmddyyyy(today + timedelta(days=SEARCH_WINDOW_DAYS)),
            "buttonSubmitStatus": "Search for Status",
        })
        resp = client.get(GRID_URL, params={
            "SearchType": "Status", "rows": 500, "page": 1,
            "sidx": "SaleDate", "sord": "asc", "_search": "false", "nd": 1,
        })
    resp.raise_for_status()
    payload = resp.json()

    rows_out = []
    for row in payload.get("rows", []):
        cell = row.get("cell") or []
        if len(cell) < 6:
            continue
        applicant, case_number, cert_number, parcel_id, sale_date_raw, status = cell[0], cell[1], cell[2], cell[3], cell[4], cell[5]
        owner = cell[9] if len(cell) > 9 else ""
        sale_date = None
        try:
            mm, dd, yyyy = sale_date_raw.split("/")
            sale_date = f"{int(yyyy):04d}-{int(mm):02d}-{int(dd):02d}"
        except (ValueError, AttributeError):
            pass
        rows_out.append({
            "county_slug": "st_johns",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": sale_date,
            "cancelled": status.strip().upper() not in ("SALE",),
            "raw_comment": f"{status} | cert {cert_number} | parcel {parcel_id}",
            "case_title": f"{applicant.strip()} VS {owner.strip()}".strip(" VS"),
            "source_url": BASE_URL,
        })

    if not rows_out:
        raise RuntimeError(
            "st_johns tax_deed: parsed 0 rows from the GridSearchData response — treat as FAILURE, not an empty calendar"
        )

    return rows_out


if __name__ == "__main__":
    import json
    data = parse_tax_deed()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"parsed {len(data)} rows, {cancelled} non-SALE-status (shouldn't happen given the search filter)")
    print(json.dumps(data[:2], indent=2))

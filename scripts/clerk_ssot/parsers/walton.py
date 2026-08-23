"""Walton clerk tax deed parser. Family C (jqGrid JSON API, session-cookie
gated — two-step POST-then-GET dance, not a static <table>).

Mortgage foreclosure sales (waltonclerkfl.gov/foreclosures) are held
exclusively at walton.realforeclose.com (RealForeclose/RealAuction) with NO
independent public calendar on the clerk's own site — confirmed live
2026-08-10: both /foreclosures and the "Mortgage Foreclosure Sales" sub-page
(index.asp?SEC=...&DE=369527A5-...) only link out to RealForeclose, no
<table>, no PDF, no clerk-hosted list. parse_foreclosure() intentionally NOT
implemented here — off-limits per pipeline guardrails.

Tax deed sales DO have a genuine clerk-hosted source:
taxsmart.clerkofcourts.co.walton.fl.us — a Pioneer Technology Group "ATS"
jqGrid app (co.walton.fl.us subdomain, not RealForeclose/a third-party
auction platform). The public "Status" search tab defaults to status=2
(SALE) and is the closest analog to an "upcoming tax deed sales" calendar:
scoping to that status excludes REDEEMED/CANCELLED/SOLD/etc. history.

Flow (session-cookie dependent — plain GET to the JSON endpoint 500s):
  1. GET  /                                    (seed session cookie)
  2. POST / with SearchTypeStatus=2 (SALE) + a wide date range
     (this stashes the search criteria server-side against the cookie)
  3. GET  /Home/GridSearchData?SearchType=Status  (returns the JSON grid)

JSON row shape: {"cell": [Applicant, CaseNumber, CertificateNumber,
ParcelID, SaleDate, Status, BaseBid, HighBid, Surplus, PropertyOwners]}
(colModel index order, confirmed against the live jqGrid init script).
CaseNumber format: "2026-0026TD". SaleDate format: "M/D/YYYY".
"""
import re

import httpx

BASE_URL = "http://taxsmart.clerkofcourts.co.walton.fl.us/"
GRID_URL = BASE_URL + "Home/GridSearchData"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

TD_CASE_RE = re.compile(r"^\d{4}-\d{4}TD$")

# colModel order from the live jqGrid init script
CELL_FIELDS = ["applicant", "case_number", "certificate_number", "parcel_id",
               "sale_date", "status", "base_bid", "high_bid", "surplus", "owners"]


def _normalize_date(raw: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _fetch_sale_status_rows() -> list[dict]:
    session = httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    seed = session.get(BASE_URL)
    seed.raise_for_status()

    search = session.post(BASE_URL, data={
        "SearchTypeStatus": "2",  # 2 = SALE (per live <SELECT id='idSearchTypeStatus'> options)
        "dateFromStatus": "1/1/2020",
        "dateToStatus": "12/31/2030",
        "buttonSubmitStatus": "Search for Status",
    })
    search.raise_for_status()

    grid = session.get(GRID_URL, params={
        "page": 1, "rows": 500, "sidx": "SaleDate", "sord": "asc", "SearchType": "Status",
    })
    grid.raise_for_status()
    try:
        payload = grid.json()
    except ValueError as e:
        raise RuntimeError(f"walton tax_deed: GridSearchData did not return JSON — page structure changed ({e})")

    rows = payload.get("rows")
    if rows is None:
        raise RuntimeError("walton tax_deed: JSON payload missing 'rows' key — page structure changed")
    return [dict(zip(CELL_FIELDS, r.get("cell", []))) for r in rows]


def parse_tax_deed() -> list[dict]:
    rows_out = []
    for f in _fetch_sale_status_rows():
        case_number = f.get("case_number", "").strip()
        if not TD_CASE_RE.match(case_number):
            continue
        status = f.get("status", "").strip()
        owners = f.get("owners", "").strip()
        applicant = f.get("applicant", "").strip()
        rows_out.append({
            "county_slug": "walton",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": _normalize_date(f.get("sale_date", "")),
            "cancelled": status.upper() not in ("SALE", "SOLD"),
            "raw_comment": f"status={status} | cert={f.get('certificate_number', '').strip()} | base_bid={f.get('base_bid', '').strip()}",
            "case_title": f"{applicant} VS {owners}".strip(" VS"),
            "source_url": BASE_URL,
            "parcel_id": f.get("parcel_id", "").strip() or None,
        })
    if not rows_out:
        raise RuntimeError("walton tax_deed: parsed 0 rows from a successful fetch — treat as FAILURE, not an empty calendar")
    return rows_out


if __name__ == "__main__":
    import json
    data = parse_tax_deed()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"tax_deed: {len(data)} rows, {cancelled} non-SALE status")
    print(json.dumps(data[:2], indent=2))

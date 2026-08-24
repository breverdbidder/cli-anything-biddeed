"""St. Lucie clerk tax deed parser. Family C (acclaimweb "TributeWeb" — ASP.NET
WebForms search-form POST + server-rendered results table, Akamai-fronted).

foreclosure: NO parser here, by design. The clerk's own foreclosure page
(https://www.stlucieclerk.gov/services/auctions/foreclosure) states verbatim:
"Foreclosure sales are held online at RealAuction and administered by Real
Foreclose" and links directly to https://stlucie.realforeclose.com/ — a
gated third-party RealAuction-family platform this pipeline is not allowed
to touch. The only other candidate, courtcasesearch.stlucieclerk.gov
("BenchmarkWebExternal"), is a *generic* county case-search portal (any
case type/party/statute), not a foreclosure-sale calendar — and its search
form is gated behind a Google reCAPTCHA (confirmed via
Scripts/home/search.js: submits to CourtCase.aspx/CaseSearch, plus a
CourtCase.aspx/CaptchaQuestion audio-captcha fallback). No independent,
public, non-captcha foreclosure sale list exists on St. Lucie's own
infrastructure. Blocker, not an oversight.

tax_deed: real, working, live-verified 2026-08-10 against
acclaimweb.stlucieclerk.gov/TributeWeb/ (also known as "AcclaimWeb"/
"Tribute" in Acclaim/BenchmarkWeb's own product family).

Access quirk: Akamai in front of *.stlucieclerk.gov 403s a bare
User-Agent-only request ("Access Denied ... errors.edgesuite.net") on
EVERY path, including static .js assets. A full browser-shaped header set
(sec-ch-ua*, Sec-Fetch-*, Accept, Referer, Upgrade-Insecure-Requests) is
required on every request, not just the first — this is the load-bearing
fix, not cookies/session.

Form flow (classic ASP.NET WebForms postback, verified against the live
GET+POST round trip):
  1. GET https://acclaimweb.stlucieclerk.gov/TributeWeb/ to obtain
     __VIEWSTATE / __VIEWSTATEGENERATOR / __EVENTVALIDATION plus every
     other form field's default value (there are ~10 hidden fields beyond
     the 3 usual ASP.NET ones; omitting any of them makes the server 500
     with "System.FormatException: Input string was not in a correct
     format" while parsing an implicit numeric field — so the safe
     approach is to POST back literally every <input>/<select> the page
     shipped, only overriding the search-relevant ones).
  2. POST the same URL with GrpSaleDate=radDateRange (the "Date Range"
     radio, not the single-sale-date "By Sale Date" radio) + txtFrom/txtTo
     (MM/DD/YYYY) + ddStatus=0 (<Select All> status) + txtPageSize=500.
     Date-range mode returns every sale across the window in one page,
     which is far more useful for parity than the single-date dropdown
     (ddSaleDates) that only has ~200 discrete historical option values.
     Window is today-120d..today+180d — the full multi-decade archive
     (back to 1994, 2500+ rows) read-timeouts server-side; run_parity.py's
     own 90-day window does the real filtering on top of this anyway.
  3. Real results land in <table id="dgResults">: columns Applicant |
     Case Number | Certificate Number | Issue Year | Parcel ID |
     Sale Date | Current Status | Opening Bid | Property Owners.
     "Case Number" (e.g. "26-145") is the sale/case identifier — distinct
     from "Certificate Number" (e.g. "2024/3900"), which is the underlying
     tax certificate, not what run_parity.py should match against.
  Statuses observed live across a full-2026 date-range pull (174 real
  rows): SALE (scheduled/upcoming — NOT cancelled), SOLD (occurred),
  REDM (redeemed before sale — cancelled), BANKRUPTCY (cancelled), PULL
  (pulled from sale — cancelled). "SALE" is the only status meaning
  "still going to happen."
"""
import re
from datetime import date, timedelta

import httpx
from bs4 import BeautifulSoup

TD_URL = "https://acclaimweb.stlucieclerk.gov/TributeWeb/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# Full browser-shaped header set — Akamai 403s anything less on every path.
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Referer": TD_URL,
}

CASE_RE = re.compile(r"^\d{2}-\d{3,5}$")
CANCEL_STATUSES = {"REDM", "BANKRUPTCY", "PULL", "REDEEMED"}

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
     "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def _normalize_date(raw: str) -> str | None:
    """'Nov 09, 2026' -> '2026-11-09'."""
    m = re.match(r"^([A-Z][a-z]{2})\s+(\d{1,2}),\s*(\d{4})$", raw.strip())
    if not m:
        return None
    mon, dd, yyyy = m.groups()
    mm = MONTHS.get(mon)
    if not mm:
        return None
    return f"{yyyy}-{mm:02d}-{int(dd):02d}"


def _collect_form_fields(soup: BeautifulSoup) -> dict:
    """Grab every input/select's current value so the POST round-trips
    fields we don't care about (avoids the server-side FormatException
    seen when only the 'obviously relevant' fields are sent)."""
    data = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        if inp.get("type") == "checkbox" and not inp.get("checked"):
            continue
        data[name] = inp.get("value", "")
    for sel in soup.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        selected = sel.find("option", selected=True)
        chosen = selected or sel.find("option")
        data[name] = chosen.get("value", "") if chosen else ""
    return data


def parse_tax_deed() -> list[dict]:
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = client.get(TD_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        data = _collect_form_fields(soup)
        if "__VIEWSTATE" not in data:
            raise RuntimeError("st_lucie tax_deed: no __VIEWSTATE on GET — page structure changed")

        # A narrow-ish forward/backward window, not the full multi-decade
        # archive (~2500+ rows back to 1994) — the full archive is slow
        # enough server-side to read-timeout. run_parity.py applies its own
        # 90-day window on top of whatever we return, so err generous but
        # bounded, matching the house convention (see st_johns.py).
        today = date.today()
        data["GrpSaleDate"] = "radDateRange"
        data["txtFrom"] = (today - timedelta(days=120)).strftime("%m/%d/%Y")
        data["txtTo"] = (today + timedelta(days=180)).strftime("%m/%d/%Y")
        data["ddStatus"] = "0"  # <Select All>
        data["txtPageSize"] = "500"

        resp2 = client.post(TD_URL, data=data, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"})
        resp2.raise_for_status()

    soup2 = BeautifulSoup(resp2.text, "lxml")
    table = soup2.find("table", id="dgResults")
    if table is None:
        raise RuntimeError("st_lucie tax_deed: no #dgResults table in search response — page structure changed")

    rows_out = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 9 or not CASE_RE.match(cells[1]):
            continue
        applicant, case_number, cert_number, parcel_id, sale_date_raw, status, owners = (
            cells[0], cells[1], cells[2], cells[4], cells[5], cells[6], cells[8]
        )
        rows_out.append({
            "county_slug": "st_lucie",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "parcel_id": parcel_id or None,
            "sale_date": _normalize_date(sale_date_raw),
            "cancelled": status.strip().upper() in CANCEL_STATUSES,
            "raw_comment": f"{status} | cert {cert_number}",
            "case_title": f"{applicant} VS {owners}".strip(" VS"),
            "source_url": TD_URL,
        })

    if not rows_out:
        raise RuntimeError("st_lucie tax_deed: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")

    return rows_out


if __name__ == "__main__":
    import json
    data = parse_tax_deed()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"tax_deed: parsed {len(data)} rows, {cancelled} cancelled/redeemed/pulled")
    print(json.dumps(data[:2], indent=2))

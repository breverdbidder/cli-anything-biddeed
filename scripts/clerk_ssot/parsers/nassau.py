"""Nassau clerk tax deed sales parser. Family B (paginated key-value table
grid). taxdeeds.nassauclerk.com is the clerk's own tax-deed case list (NOT
RealTaxDeed -- that's nassau.realtaxdeed.com, linked but never fetched here).
Each case is its own small `<table>` of CASE NUMBER / SALE STATUS /
CERTIFICATE NUMBER / PARCEL NUMBER / SALE DATE / OPENING BID rows (5 case
tables per page + 1 trailing pagination table), paginated via
`?PageNum_summarycaselist=N` query param -- 51 pages observed live
(2026-08-10, 255 total records @ 5/page).

The main-site landing page linked in the task (nassauclerk.com/190/...)
is a static info page that only points OUT to two hosted platforms:
`taxdeeds.nassauclerk.com` (real, static, walkable -- used here) for tax
deeds, and `nassauclerk.realforeclose.com` for foreclosures. There is no
independent clerk-hosted foreclosure calendar, so parse_foreclosure() is
NOT implemented -- foreclosure sales here are RealAuction-only, out of
scope per guardrail.

SALE STATUS observed values: PENDING, SOLD, REDEEMED. REDEEMED is treated
as cancelled (the property was redeemed before sale, same convention as
gadsden/wakulla tax_deed).
"""
import re

import httpx
from bs4 import BeautifulSoup

TD_URL = "https://taxdeeds.nassauclerk.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"^\d{2}TD\d{6}[A-Z]{4}$")
MAX_PAGES = 60  # live site had 51 pages @ 2026-08-10; hard cap to avoid runaway pagination


def _normalize_date(raw: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _fetch_page(page: int) -> str:
    url = TD_URL if page == 1 else f"{TD_URL}/?PageNum_summarycaselist={page}"
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _total_pages(html: str) -> int:
    nums = [int(m) for m in re.findall(r"PageNum_summarycaselist=(\d+)", html)]
    return max(nums) if nums else 1


def parse_tax_deed() -> list[dict]:
    first_html = _fetch_page(1)
    total_pages = min(_total_pages(first_html), MAX_PAGES)

    rows_out = []
    for page in range(1, total_pages + 1):
        html = first_html if page == 1 else _fetch_page(page)
        soup = BeautifulSoup(html, "lxml")
        for table in soup.find_all("table"):
            fields = {}
            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) != 2:
                    continue
                key = tds[0].get_text(strip=True)
                val = tds[1].get_text(strip=True)
                if key:
                    fields[key] = val
            case_number = fields.get("CASE NUMBER", "")
            if not CASE_RE.match(case_number):
                continue
            status = fields.get("SALE STATUS", "")
            rows_out.append({
                "county_slug": "nassau",
                "sale_type": "tax_deed",
                "case_number": case_number,
                "sale_date": _normalize_date(fields.get("SALE DATE", "")),
                "cancelled": status.upper() == "REDEEMED",
                "raw_comment": f"{status} | cert {fields.get('CERTIFICATE NUMBER', '')} | bid {fields.get('OPENING BID', '')}",
                "case_title": case_number,
                "source_url": TD_URL,
            })

    if not rows_out:
        raise RuntimeError("nassau tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    td = parse_tax_deed()
    print(f"tax_deed: {len(td)} rows, {sum(1 for r in td if r['cancelled'])} redeemed")

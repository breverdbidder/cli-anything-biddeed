"""Hardee clerk tax deed parser. Family G (Vue component with the full sale
list embedded as static server-rendered JSON in a `:taxdeeds="[...]"`
attribute on a `<tax-deed-sales>` custom element -- no JS execution needed,
httpx + a JSON parse on the attribute value is sufficient).

foreclosure: NOT implemented. As of 2026-08-10 the live foreclosure-sales
page (https://www.hardeeclerk.com/departments/circuit-civil/foreclosure-sales/)
renders a plain static "There are no foreclosure sales available at this
time." paragraph with ZERO embedded Vue component/JSON anywhere in the raw
HTML (verified: 0 occurrences of any `<*-sales` custom element or `:sales`
attribute) -- unlike tax-deeds, there is no evidence of what a populated
foreclosure listing would look like on this site, so the format cannot be
inferred from a live fetch. Writing a parser against a guessed structure
would violate the "infer from actual live HTML" rule. Revisit when the
county has an active foreclosure sale to observe the real markup.

case_number = the `file` field (Florida court-style case number, e.g.
"252024TD055AXMX" = circuit "25", county "2024", "TD", sequence "055",
"AXMX" suffix). status field free-texts as "Sold for $X", "Redeemed on
MM/DD/YYYY", "Cancelled MM/DD/YYYY", etc. -- cancellation matched on any
CANCEL token; REDEEMED is also treated as cancelled (property no longer
available, same convention as gadsden/wakulla tax_deed parsers).
"""
import json
import re

import httpx
from bs4 import BeautifulSoup

TD_URL = "https://www.hardeeclerk.com/departments/tax-deeds/tax-deed-sales/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"^\d+TD\d+AXMX$")


def parse_tax_deed() -> list[dict]:
    resp = httpx.get(TD_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    el = soup.find("tax-deed-sales")
    if el is None or not el.has_attr(":taxdeeds"):
        raise RuntimeError("hardee tax_deed: no <tax-deed-sales :taxdeeds=...> component found — page structure changed")

    try:
        data = json.loads(el[":taxdeeds"])
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"hardee tax_deed: :taxdeeds attribute is not valid JSON — {e}")

    rows_out = []
    for d in data:
        case_number = d.get("file", "")
        if not CASE_RE.match(case_number):
            continue
        status = d.get("status", "")
        rows_out.append({
            "county_slug": "hardee",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": (d.get("iso_sale_date") or "")[:10] or None,
            "cancelled": "CANCEL" in status.upper() or "REDEEM" in status.upper(),
            "raw_comment": f"cert {d.get('cert', '')} | {status}".strip(" |"),
            "case_title": f"{d.get('cert_holder', '')} VS parcel {d.get('parcel', '')}",
            "source_url": TD_URL,
        })

    if not rows_out:
        raise RuntimeError("hardee tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    td = parse_tax_deed()
    print(f"tax_deed: {len(td)} rows, {sum(1 for r in td if r['cancelled'])} cancelled/redeemed")
    import json as _json
    print(_json.dumps(td[:2], indent=2))

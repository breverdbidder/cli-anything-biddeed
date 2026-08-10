"""Gulf clerk tax deed parser. Family E-variant (Bootstrap card grid, not
WordPress theme grid): each sale is a `div.shadow.mb-2` with a dark header
row (`div.bg-dark` containing `div.col-md-auto` cells, each holding a
`<span>` label + value text, plus a trailing status-only cell with no span)
and a body row with Applicant/Owner/Location/Amount.

foreclosure: NOT implemented. Gulf's foreclosures page ("Visit the
RealAuction Portal") only points to https://gulf.realforeclose.com/ -- no
independent public list on the clerk's own site. Per guardrails, RealAuction/
RealForeclose is off-limits, so parse_foreclosure is intentionally omitted.

Status values observed live: "active", "surplus" (no CANCELLED/REDEEMED seen
in the 10 live rows) -- cancellation is inferred defensively from any
CANCEL/REDEEM token in the status field in case the clerk ever adds one.
"""
import re

import httpx
from bs4 import BeautifulSoup

TD_URL = "https://www.gulfclerk.com/courts/tax-deeds/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"^(?:TD#)?\d{4}-\d+$")
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2})\s+at")


def _normalize_date(raw: str) -> str | None:
    m = DATE_RE.match(raw.strip())
    if not m:
        return None
    mm, dd, yy = m.groups()
    yyyy = 2000 + int(yy)
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def parse_tax_deed() -> list[dict]:
    resp = httpx.get(TD_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    cards = soup.find_all("div", class_=lambda c: c and "shadow" in c.split() and "mb-2" in c.split())
    if not cards:
        raise RuntimeError("gulf tax_deed: no sale cards (div.shadow.mb-2) found — page structure changed")

    rows_out = []
    for card in cards:
        header = card.find("div", class_=lambda cl: cl and "bg-dark" in cl.split())
        if header is None:
            continue
        fields = {}
        status = ""
        for col in header.find_all("div", class_="col-md-auto"):
            span = col.find("span")
            if span:
                key = span.get_text(strip=True)
                span.extract()
                fields[key] = col.get_text(strip=True)
            else:
                status = col.get_text(strip=True)

        case_number = fields.get("Case No.", "")
        if not CASE_RE.match(case_number):
            continue

        body = card.find_all("div", class_=lambda cl: cl and "d-flex" in cl.split())
        applicant = owner = ""
        if len(body) > 1:
            body_cols = body[1].find_all("div", recursive=False)
            for col in body_cols:
                text = col.get_text(" ", strip=True)
                if text.startswith("Applicant"):
                    applicant = text.replace("Applicant", "", 1).strip()
                elif text.startswith("Owner"):
                    owner = text.replace("Owner", "", 1).strip()

        rows_out.append({
            "county_slug": "gulf",
            "sale_type": "tax_deed",
            "case_number": case_number,
            "sale_date": _normalize_date(fields.get("Sale Date", "")),
            "cancelled": "CANCEL" in status.upper() or "REDEEM" in status.upper(),
            "raw_comment": f"cert {fields.get('Certificate No.', '')} | {status}".strip(" |"),
            "case_title": f"{applicant} VS {owner}" if applicant or owner else case_number,
            "source_url": TD_URL,
        })

    if not rows_out:
        raise RuntimeError("gulf tax_deed: parsed 0 rows from a 200 response — treat as FAILURE")
    return rows_out


if __name__ == "__main__":
    td = parse_tax_deed()
    print(f"tax_deed: {len(td)} rows")
    import json
    print(json.dumps(td[:2], indent=2))

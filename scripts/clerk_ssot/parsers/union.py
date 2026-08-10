"""Union clerk foreclosure sales parser. Family D (Cloudflare-gated card layout,
not a <table>, requires JS rendering).

unionclerk.com is a WordPress/headless-CMS site sitting behind Cloudflare's
"managed challenge" (JS + browser fingerprint check) — plain httpx.get() 403s
even on the homepage, confirmed live 2026-08-10. A headless-browser fetch
(Playwright/Chromium) is required to pass the challenge and get real HTML.

Once rendered, the page has NO literal <table> — each sale is a card:
  <div class="even:bg-gray-100">
    <div class="w-full grid ..."><div class="w-full">
      <label>Status</label><strong>scheduled</strong>
    </div> ... (Sale Date, Case Number, Judgment Amount, Parties,
                 Address, Parcel ID) ... </div>
  </div>
under the "Upcoming Foreclosure Sales" <h2>. tax_deed intentionally NOT
implemented here: tax_deed_verified=false in clerk_sale_calendar_sources
for this county even though a tax_deed_url exists — out of scope until
verified.
"""
import re

from bs4 import BeautifulSoup

FC_URL = "https://unionclerk.com/departments-services/court-services/foreclosure-sales/"
CASE_RE = re.compile(r"^\d{2}-\d{4}-CA-\d+$")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def _normalize_date(raw: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _fetch_rendered_html(url: str) -> str:
    """unionclerk.com sits behind a Cloudflare managed challenge that returns
    403 to plain httpx (even on '/') — a real browser must execute the
    challenge JS. Playwright + Chromium is the only reliable way through."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=UA)
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_selector("h2", timeout=15000)
            page.wait_for_timeout(5000)  # let the Cloudflare challenge + card list settle
            return page.content()
        finally:
            browser.close()


def parse_foreclosure() -> list[dict]:
    html = _fetch_rendered_html(FC_URL)
    soup = BeautifulSoup(html, "lxml")

    heading = soup.find("h2", string=lambda s: s and "Upcoming Foreclosure Sales" in s)
    if heading is None:
        raise RuntimeError("union foreclosure: 'Upcoming Foreclosure Sales' heading not found — page structure changed")

    container = heading.find_next("div", class_="divide-y")
    if container is None:
        raise RuntimeError("union foreclosure: no card container found after heading — page structure changed")

    cards = container.find_all("div", recursive=False)
    if not cards:
        raise RuntimeError("union foreclosure: no sale cards found in container — page structure changed")

    rows = []
    for card in cards:
        fields = {}
        for label_tag in card.select("div.w-full > label"):
            label = label_tag.get_text(strip=True)
            strong = label_tag.find_next_sibling("strong")
            fields[label] = strong.get_text(strip=True) if strong else ""

        case_number = fields.get("Case Number", "")
        if not CASE_RE.match(case_number):
            continue

        status = fields.get("Status", "")
        sale_date_raw = fields.get("Sale Date", "")
        parties = fields.get("Parties", "")

        rows.append({
            "county_slug": "union",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_date(sale_date_raw),
            "cancelled": status.upper() in ("CANCELLED", "CANCELED") or "CANCEL" in status.upper(),
            "raw_comment": status,
            "case_title": parties,
            "source_url": FC_URL,
        })

    if not rows:
        raise RuntimeError("union foreclosure: parsed 0 rows from a successful fetch — treat as FAILURE, not an empty calendar")

    return rows


if __name__ == "__main__":
    import json
    data = parse_foreclosure()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"parsed {len(data)} rows, {cancelled} cancelled")
    print(json.dumps(data[:2], indent=2))

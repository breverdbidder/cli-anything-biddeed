"""Lake clerk foreclosure sales parser. Family C (event-item html_table hybrid).

Lake's foreclosurecalendar.lakecountyclerkfl.gov is an ASP.NET WebForms
calendar app. The default view renders a nav table only (no data) — sale
rows live under ?view=list as a flat sequence of <div class="event_item">
blocks, NOT a <table>. Each block carries date/time, an event_type label
("Foreclosure" vs "Tax Deed" — we only take Foreclosure here; tax_deed is
out of scope / unverified), and a case link:
  <a href="/sale_details.aspx?id=NNNNN">
    <span class='pscalendar-foreclosure'>CASE#: PLAINTIFF vs DEFENDANT</span>
  </a>
Cancelled sales swap the span class to 'pscalendar-cancelled' and add a
sibling <span class='pscalendar-red'>reason</span> — that reason is the
cancellation signal and must be preserved in raw_comment.
"""
import re
from datetime import date, timedelta

import httpx
from bs4 import BeautifulSoup

FC_URL = "https://foreclosurecalendar.lakecountyclerkfl.gov/?view=list"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"^\d{4}(?:CA|CC)\d+$")
DATE_RE = re.compile(r"^[A-Za-z]{3}, (\d{1,2})/(\d{1,2})$")


def _normalize_date(raw: str) -> str | None:
    """Lake's list view prints 'Tue, 8/11' — no year — for sales more than a
    day out, but swaps in the bare word 'Today' (and, per the same relative-
    date convention, presumably 'Tomorrow') for the current/next day instead
    of the weekday-and-date form. Unhandled, that word never matches DATE_RE,
    sale_date comes back None, and diff_and_reconcile's window filter drops
    the row from ssot_by_case entirely — six genuinely-live 2026-08-18 sales
    were flagged PHANTOM_NOT_ON_CLERK by every run this way even though they
    were live on the clerk site the whole time (confirmed 2026-08-18)."""
    raw = raw.strip()
    today = date.today()
    if raw == "Today":
        return today.isoformat()
    if raw == "Tomorrow":
        return (today + timedelta(days=1)).isoformat()
    m = DATE_RE.match(raw)
    if not m:
        return None
    mm, dd = int(m.group(1)), int(m.group(2))
    yyyy = today.year
    if mm < today.month or (mm == today.month and dd < today.day - 3):
        yyyy += 1
    return f"{yyyy}-{mm:02d}-{dd:02d}"


def parse_foreclosure() -> list[dict]:
    resp = httpx.get(FC_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    items = soup.find_all("div", class_="event_item")
    if not items:
        raise RuntimeError("lake foreclosure: no <div class='event_item'> blocks found — page structure changed")

    rows = []
    for item in items:
        type_div = item.find("div", class_="event_type")
        if type_div is None or "foreclosure" not in type_div.get_text(strip=True).lower():
            continue  # skip Tax Deed events — out of scope

        time_div = item.find("div", class_="event_time")
        # event_time text is "Tue, 8/11<time range>" run together after strip()
        # for sales more than a day out, or "Today<time range>" / "Tomorrow
        # <time range>" for the next two days — extract via regex, relative
        # form first since it has no comma/slash for the dated regex to match.
        time_text = time_div.get_text(" ", strip=True) if time_div else ""
        date_match = re.search(r"^(Today|Tomorrow)\b", time_text) or re.search(r"[A-Za-z]{3},\s*\d{1,2}/\d{1,2}", time_text)
        sale_date_raw = date_match.group(0) if date_match else ""

        case_span = item.find("span", class_="pscalendar-foreclosure") or item.find("span", class_="pscalendar-cancelled")
        if case_span is None:
            continue
        case_text = case_span.get_text(strip=True)
        if ":" not in case_text:
            continue
        case_number, case_title = case_text.split(":", 1)
        case_number = case_number.strip()
        case_title = case_title.strip()
        if not CASE_RE.match(case_number):
            continue

        reason_span = item.find("span", class_="pscalendar-red")
        raw_comment = reason_span.get_text(strip=True) if reason_span else ""
        cancelled = case_span.get("class") and "pscalendar-cancelled" in case_span.get("class")

        rows.append({
            "county_slug": "lake",
            "sale_type": "foreclosure",
            "case_number": case_number,
            "sale_date": _normalize_date(sale_date_raw),
            "cancelled": bool(cancelled),
            "raw_comment": raw_comment,
            "case_title": case_title,
            "source_url": FC_URL,
        })

    if not rows:
        raise RuntimeError("lake foreclosure: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")

    return rows


if __name__ == "__main__":
    import json
    data = parse_foreclosure()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"parsed {len(data)} rows, {cancelled} cancelled")
    print(json.dumps(data[:2], indent=2))

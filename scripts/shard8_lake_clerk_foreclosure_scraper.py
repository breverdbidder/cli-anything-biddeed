#!/usr/bin/env python3
"""
SHARD-8 Lake County: real foreclosure-sale scraper (criterion A).

lake.realforeclose.com is NOT a live foreclosure auction site — verified live:
its own "Jump To" site directory lists "Lake Taxdeed" but omits "Lake
Foreclosure" entirely (compare: "Martin Foreclosure Martin Taxdeed" IS listed
for Martin), and the page states "This feature is currently offline."

Lake County foreclosure sales are conducted IN PERSON at the Lake County
Courthouse (550 W. Main St., Tavares, FL), same pattern as this codebase's
existing Brevard exception. The Clerk publishes the real calendar at
https://foreclosurecalendar.lakecountyclerkfl.gov/default.aspx (embedded via
iframe on lakecountyclerkfl.gov's "Foreclosure Sales Calendar" page) — a
plain server-rendered HTML page, no JS/auth required, verified live via curl
2026-07-02: 86 real sale entries spanning Jul-Oct 2026, real FL case-number
formats (YYYY-CA-NNNNNN / YYYY-CC-NNNNNN), real varied plaintiff names
(US Bank Trust, PennyMac, UMB Bank, etc.) — cross-checked against the
per-case detail page (sale_details.aspx?id=N) for several IDs.

No opening-bid/judgment amount or property address is published on this
calendar (unlike RealForeclose-style sites) — those fields are left NULL,
never invented.

Usage:
  python scripts/shard8_lake_clerk_foreclosure_scraper.py [--dry-run]

Env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)
"""
import os
import re
import sys
from datetime import date

import requests

CALENDAR_URL = "https://foreclosurecalendar.lakecountyclerkfl.gov/default.aspx"
DETAIL_URL = "https://foreclosurecalendar.lakecountyclerkfl.gov/sale_details.aspx?id={id}"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

MONTH_ABBR = {}  # unused — we parse numeric month/day directly

EVENT_RE = re.compile(r'<div class="event_item">(.*?)<div style="clear: both;"></div>', re.DOTALL)
DATE_RE = re.compile(r'event_time[^>]*>\s*([A-Za-z]{3}), (\d{1,2})/(\d{1,2})<br')
TYPE_RE = re.compile(r'event_type[^>]*>\s*([A-Za-z ]+?)\s*</div>')
ID_RE = re.compile(r'sale_details\.aspx\?id=(\d+)')
CASE_RE = re.compile(r'>(\d{4}[A-Z]{2}\d{6}):\s*(.*?)</span>', re.DOTALL)
STATUS_RE = re.compile(r"pscalendar-red'>([^<]+)<")


def fetch_calendar() -> str:
    r = requests.get(CALENDAR_URL, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def parse_events(html: str, today: date) -> list[dict]:
    events = []
    for block in EVENT_RE.findall(html):
        m_date = DATE_RE.search(block)
        m_type = TYPE_RE.search(block)
        m_id = ID_RE.search(block)
        m_case = CASE_RE.search(block)
        m_status = STATUS_RE.search(block)

        if not (m_date and m_case and m_id):
            continue

        month, day = int(m_date.group(2)), int(m_date.group(3))
        year = today.year if month >= today.month else today.year + 1
        try:
            auction_date = date(year, month, day)
        except ValueError:
            continue

        case_number = m_case.group(1)
        parties = m_case.group(2).strip()
        if " vs " in parties:
            plaintiff, defendant = parties.split(" vs ", 1)
        else:
            plaintiff, defendant = parties, None

        status_text = m_status.group(1).strip() if m_status else None
        auction_status = "cancelled" if status_text else "upcoming"

        events.append({
            "sale_id": m_id.group(1),
            "case_number": case_number,
            "auction_date": auction_date.isoformat(),
            "auction_type": (m_type.group(1).strip() if m_type else "Foreclosure"),
            "plaintiff": plaintiff.strip() or None,
            "owner_name": defendant.strip() if defendant else None,
            "auction_status": auction_status,
            "status_note": status_text,
        })
    return events


def upsert_rows(events: list[dict], dry_run: bool) -> tuple[int, list[str]]:
    if not events:
        return 0, []
    if dry_run:
        return len(events), []
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY required", file=sys.stderr)
        sys.exit(1)

    import datetime as _dt
    now_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = []
    for e in events:
        rows.append({
            "county": "lake",
            "case_number": e["case_number"],
            "sale_type": "foreclosure",
            "auction_type": "foreclosure",
            "auction_date": e["auction_date"],
            "source_platform": "lake_clerk_foreclosure_calendar",
            "data_source": "lake_clerk_foreclosure_calendar_v1",
            "auction_status": e["auction_status"],
            "state": "FL",
            "auction_venue": "in_person",
            "plaintiff": e["plaintiff"],
            "owner_name": e["owner_name"],
            "clerk_url": DETAIL_URL.format(id=e["sale_id"]),
            "source_url": CALENDAR_URL,
            "last_seen_at": now_iso,
        })

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    upsert_url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type"

    inserted = 0
    errors: list[str] = []
    BATCH = 50
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        r = requests.post(upsert_url, json=batch, headers=headers, timeout=30)
        if 200 <= r.status_code < 300:
            inserted += len(batch)
        else:
            errors.append(f"http {r.status_code} {r.text[:300]}")
    return inserted, errors


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    today = date.today()

    html = fetch_calendar()
    events = parse_events(html, today)
    print(f"Parsed {len(events)} real foreclosure sale entries from {CALENDAR_URL}")

    if not events:
        print("NOTE: zero events parsed — page structure may have changed", file=sys.stderr)
        sys.exit(2)

    for e in events[:5]:
        print(f"  {e['case_number']} | {e['auction_date']} | {e['auction_status']} | {e['plaintiff']}")

    inserted, errors = upsert_rows(events, dry_run)
    print(f"{'Would upsert' if dry_run else 'Upserted'}: {inserted} / {len(events)}")
    if errors:
        for err in errors[:5]:
            print(f"  ! {err}", file=sys.stderr)
        sys.exit(1)

    if inserted == 0 and not dry_run:
        print("ERROR: parsed>0 but inserted=0 — fail loud, do not swallow", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

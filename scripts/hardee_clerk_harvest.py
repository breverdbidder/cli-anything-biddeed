#!/usr/bin/env python3
"""
Hardee Clerk Foreclosure/Tax-Deed Harvest (2026-07-19, GOLD STANDARD shard-9
dispatch 30b3a3ea-d603-4f0f-b1a4-c9f25f233bef)
=========================================================
Forked from scripts/lafayette_clerk_harvest.py. Hardee's foreclosure_platform
and taxdeed_platform in pipeline.counties are both 'clerk_inperson' -- both
hardee.realforeclose.com and hardee.realtaxdeed.com are unprovisioned RealAuction
tenants (302 to the generic splash page). Sales are held in person (Wed 11am,
417 W Main St, Wauchula, 2nd floor outside Rm 202), but the Clerk's own
WordPress/Tailwind site publishes structured upcoming-sale cards for
foreclosures online (confirmed live 2026-07-19, plain curl, no Cloudflare
challenge):
  https://www.hardeeclerk.com/departments/circuit-civil/foreclosure-sales/
  https://www.hardeeclerk.com/departments/tax-deeds/tax-deed-sales/

Card markup differs from lafayette's (different theme): each field is a
`<label class="block uppercase tracking-wide text-primary text-xs">NAME</label>`
followed by either a `<strong>VALUE</strong>` (Case Number/Sale Date/Judgement
Amount/Parties) or an `<a ...>VALUE</a>` (Address, which links out to a Google
search). No Status or Parcel ID fields are present on this site's cards.
PAIR_RE below matches label/value pairs directly against the raw HTML; a new
card starts at each "Case Number" label so this is resilient to field-order
changes and to fields being added/removed.

Tax-deed page (verified 2026-07-19): zero `label class="block uppercase..."`
occurrences anywhere in the page -- i.e. the card component that renders real
listings is structurally absent, not merely empty text. Treated as a genuine
zero, not a scrape failure -- asserted explicitly (0 pairs matched) so a
future format change is detected instead of silently continuing to report 0.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row upserted), 1 = fatal error, 2 = no new rows found
"""
import os
import re
import sys
from datetime import datetime, timezone

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

PAGES = {
    "foreclosure": "https://www.hardeeclerk.com/departments/circuit-civil/foreclosure-sales/",
    "tax_deed": "https://www.hardeeclerk.com/departments/tax-deeds/tax-deed-sales/",
}

PAIR_RE = re.compile(
    r'<label class="block uppercase tracking-wide text-primary text-xs">([^<]+)</label>\s*'
    r'(?:<strong>([^<]*)</strong>|<a[^>]*>([^<]*)</a>)',
    re.S,
)


def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def fetch_html(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def parse_cards(html: str) -> list[dict]:
    pairs = [(label.strip(), (strong or a or "").strip()) for label, strong, a in PAIR_RE.findall(html)]
    cards = []
    cur = None
    for label, value in pairs:
        if label == "Case Number":
            cur = {}
            cards.append(cur)
        if cur is not None:
            cur[label] = value
    return [c for c in cards if "Case Number" in c]


def touch_existing_last_seen(supa_url: str, headers: dict, now_iso: str) -> int:
    """Update last_seen_at for all existing hardee rows (H-freshness keepalive).
    Called every run regardless of whether new cards were found, so the H metric
    (SLA <=48h) never drifts when the Clerk site temporarily shows 0 listings.
    Returns number of rows updated (0 is acceptable — county may have no rows yet)."""
    touch_headers = {**headers, "Prefer": "return=minimal"}
    resp = requests.patch(
        f"{supa_url}/rest/v1/multi_county_auctions?county=eq.hardee",
        headers=touch_headers,
        json={"last_seen_at": now_iso, "updated_at": now_iso},
        timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        print(f"WARNING: last_seen_at touch failed {resp.status_code} {resp.text[:200]}")
        return 0
    content_range = resp.headers.get("Content-Range", "")
    count = 0
    if content_range:
        try:
            count = int(content_range.split("/")[-1])
        except ValueError:
            pass
    print(f">>> last_seen_at touch: {count} hardee row(s) updated to {now_iso}")
    return count


def main() -> int:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }

    rows = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for sale_type, url in PAGES.items():
        html = fetch_html(url)
        cards = parse_cards(html)
        print(f">>> {sale_type}: {len(cards)} card(s) found on {url}")
        for c in cards:
            sale_date = c.get("Sale Date", "")
            if not re.match(r"^\d{2}/\d{2}/\d{4}$", sale_date):
                print(f"WARNING: skipping card with unparseable Sale Date {sale_date!r}: {c}")
                continue
            mm, dd, yyyy = sale_date.split("/")
            judgment_raw = c.get("Judgement Amount", "").replace("$", "").replace(",", "")
            rows.append({
                "county": "hardee",
                "case_number": c["Case Number"],
                "sale_type": sale_type,
                "auction_type": sale_type,
                "auction_date": f"{yyyy}-{mm}-{dd}",
                "property_address": c.get("Address", "").strip() or None,
                "judgment_amount": float(judgment_raw) if judgment_raw else None,
                "plaintiff": c.get("Parties", "").strip() or None,
                "auction_status": "upcoming",
                "state": "FL",
                "source_platform": "hardee_clerk_scrape",
                "data_source": "hardee_clerk_scrape",
                "source_url": url,
                "last_seen_at": now_iso,
                "scraped_at": now_iso,
                "scrape_timestamp": now_iso,
            })

    if not rows:
        print("NOTE: zero cards parsed from either page -- hardee genuinely has no listed inventory right now")
        touch_existing_last_seen(supa_url, headers, now_iso)
        return 2

    all_keys = set().union(*(r.keys() for r in rows))
    for r in rows:
        for k in all_keys:
            r.setdefault(k, None)

    resp = requests.post(
        f"{supa_url}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type",
        headers=headers, json=rows, timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        print(f"ERROR: upsert failed {resp.status_code} {resp.text[:300]}", file=sys.stderr)
        return 1

    print(f"\nSUCCESS: upserted {len(rows)} hardee row(s): {[r['case_number'] for r in rows]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

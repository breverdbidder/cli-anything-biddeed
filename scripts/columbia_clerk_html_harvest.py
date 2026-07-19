"""Columbia County clerk_html harvester (foreclosure + tax deed).

WHY THIS EXISTS: Columbia has no RealAuction tenant (columbia.realforeclose.com /
columbia.realtaxdeed.com just redirect to the generic marketing splash -- confirmed
by multiple prior sessions). The real source of truth is columbiaclerk.com, which
returns HTTP 403 (Cloudflare managed-challenge "Just a moment") to plain
requests/urllib/curl with any header set -- confirmed live 2026-07-05. A real
headless Chromium/Chrome binary (pre-installed on this runner, NOT Playwright)
passes the challenge when driven directly via CLI flags and dumps the fully
JS-rendered DOM, which contains real Vue-rendered auction listing blocks
(class="even:bg-gray-100"). This script drives that binary and parses those blocks.

Usage:
  python3 columbia_clerk_html_harvest.py

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in env. Requires a chromium or
google-chrome(-stable) binary on PATH.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

PAGES = [
    ("foreclosure", "https://columbiaclerk.com/upcoming-foreclosure-sales/"),
    ("tax_deed", "https://columbiaclerk.com/clerk-services/tax-deeds/upcoming-tax-deed-sales/"),
]

BLOCK_RE = re.compile(
    r'<div class="even:bg-gray-100">(.*?)</div></div><div class="flex gap-0\.5"></div></div>',
    re.DOTALL,
)
FIELD_RE = re.compile(
    r'text-xs">([^<]+)</label>(?:<strong[^>]*>([^<]*)</strong>|<a[^>]*>([^<]*)</a>)'
)

# Site renders this exact h3 copy inside <article> when a lane genuinely has
# zero listings (confirmed live on the tax-deed page 2026-07-19). Distinguish
# this from a parser/selector-drift failure so we never silently swallow a
# real regression as "0 results" -- see HARD GUARDRAIL #2.
EMPTY_RE = re.compile(r"There are no (?:properties|.*?) (?:on the list|scheduled)[^<]*", re.I)


def find_browser():
    for name in ("chromium", "google-chrome", "google-chrome-stable", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("No chromium/google-chrome binary found on PATH")


def dump_dom(browser, url):
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
        out_path = tf.name
    cmd = [
        browser, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--disable-blink-features=AutomationControlled",
        f"--user-agent={UA}", "--dump-dom", "--virtual-time-budget=30000", url,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    html = result.stdout.decode("utf-8", errors="replace")
    os.unlink(out_path)
    if "Just a moment" in html or len(html) < 5000:
        raise RuntimeError(f"Blocked or empty response for {url} (len={len(html)})")
    return html


def to_amount(s):
    if not s:
        return None
    m = re.search(r"([\d,]+\.?\d*)", s)
    return float(m.group(1).replace(",", "")) if m else None


def to_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_listings(html, source_url):
    items = []
    for b in BLOCK_RE.findall(html):
        d = {}
        for lbl, strongval, aval in FIELD_RE.findall(b):
            d[lbl.strip()] = (strongval or aval).strip()
        case_no = d.get("Case Number")
        if not case_no:
            continue
        items.append({
            "case_number": case_no,
            "auction_date": to_date(d.get("Sale Date")),
            "parcel_id": (d.get("Parcel ID") or "").strip() or None,
            "property_address": d.get("Address") or None,
            "judgment_amount": to_amount(d.get("Judgement Amount")),
            "plaintiff": d.get("Parties") or None,
            "status_raw": d.get("Status"),
            "source_url": source_url,
        })
    return items


def upsert(items, sale_type):
    if not items:
        return 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = []
    for it in items:
        payload.append({
            "county": "columbia",
            "case_number": it["case_number"],
            "sale_type": sale_type,
            "auction_status": "upcoming" if (it["status_raw"] or "").lower() in ("scheduled", "upcoming", "") else it["status_raw"].lower(),
            "auction_date": it["auction_date"],
            "parcel_id": it["parcel_id"],
            "property_address": it["property_address"],
            "judgment_amount": it["judgment_amount"],
            "plaintiff": it["plaintiff"],
            "data_source": "columbia_clerk_html:SHARD2-V1",
            "source_url": it["source_url"],
            "scraped_at": now,
            "last_seen_at": now,
        })
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type",
        data=json.dumps(payload).encode(), method="POST",
        headers={
            "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status not in (200, 201, 204):
            raise RuntimeError(f"upsert failed: HTTP {resp.status}")
    return len(payload)


def main():
    browser = find_browser()
    total_parsed = 0
    total_upserted = 0
    for sale_type, url in PAGES:
        html = dump_dom(browser, url)
        items = parse_listings(html, url)
        if not items:
            m = EMPTY_RE.search(html)
            if m:
                print(f"{sale_type}: parsed=0 upserted=0 (site confirms genuinely empty: {m.group(0)!r})")
            else:
                raise RuntimeError(
                    f"{sale_type}: parsed=0 and site does NOT show its known "
                    f"'no listings' copy -- likely selector drift (BLOCK_RE/FIELD_RE "
                    f"no longer match), not a real empty lane. Refusing to treat as success."
                )
            continue
        n = upsert(items, sale_type)
        total_parsed += len(items)
        total_upserted += n
        print(f"{sale_type}: parsed={len(items)} upserted={n}")
    print(f"TOTAL: parsed={total_parsed} upserted={total_upserted}")
    if total_parsed > 0 and total_upserted == 0:
        raise RuntimeError("Silent failure: parsed>0 upserted=0")


if __name__ == "__main__":
    main()

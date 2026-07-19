#!/usr/bin/env python3
"""
SHARD-2 dispatch 190ac19f — Columbia County B/F Verified Outcomes Harvester.

Letters B (verified=0 closed_sold=0) and F (tier1_sold=0) both fail because
the clerk scraper only writes upcoming rows; no past-sale outcomes exist.

Columbia has no RealAuction tenant. The clerk_html source (columbiaclerk.com)
shows both upcoming and past sales including "SOLD" status rows. This script:
  1. Fetches the Columbia clerk foreclosure + tax deed pages via headless chrome.
  2. Parses ALL rows including sold/closed ones (not just "upcoming").
  3. For rows with status=SOLD or similar, inserts foreclosure_outcomes /
     tax_deed_outcomes with data_source='columbia_clerk_html:SHARD2-BF-V1'.
  4. PATCHes multi_county_auctions with tier1_sold_amount.
  5. Calls pencil_dod_evaluate_county('columbia') to verify improvement.

WIRING: Called from .github/workflows/shard2-columbia-bf-outcomes.yml (daily 08:30Z).

HONESTY PROTOCOL:
  - Only writes outcomes for rows the clerk explicitly marks as sold/completed.
  - Winning_bid from clerk data directly — no formula derivation.
  - BLANK > WRONG: if page is blocked or 0 outcomes found, reports honestly.
"""
import os
import sys
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation",
}

COUNTY = "columbia"
DATA_SOURCE_FC = "columbia_clerk_html:SHARD2-BF-V1-FC"
DATA_SOURCE_TD = "columbia_clerk_html:SHARD2-BF-V1-TD"

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

SOLD_STATUSES = {"sold", "completed", "closed", "final", "certificate issued", "cert issued"}


def ts():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


def find_browser():
    for name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("No chromium/google-chrome binary found on PATH")


def dump_dom(browser, url):
    cmd = [
        browser, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--disable-blink-features=AutomationControlled",
        f"--user-agent={UA}", "--dump-dom", "--virtual-time-budget=30000", url,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=90)
    html = result.stdout.decode("utf-8", errors="replace")
    if "Just a moment" in html or len(html) < 1000:
        log(f"  Page blocked or empty for {url} (len={len(html)})")
        return None
    return html


def to_amount(s):
    if not s:
        return None
    m = re.search(r"([\d,]+\.?\d*)", str(s))
    return float(m.group(1).replace(",", "")) if m else None


def to_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_all_listings(html, source_url):
    """Parse ALL listings including sold/completed ones."""
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
            "winning_bid": to_amount(d.get("Final Bid") or d.get("Sale Amount") or d.get("Winning Bid")),
            "plaintiff": d.get("Parties") or None,
            "status_raw": (d.get("Status") or "").lower().strip(),
            "source_url": source_url,
        })
    return items


def sb_post(table, body):
    if isinstance(body, dict):
        body = [body]
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}/{table}", data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = r.read()
            return json.loads(result) if result else []
    except urllib.error.HTTPError as e:
        log(f"  POST {table}: {e.code} {e.read().decode()[:200]}")
        return []


def sb_patch(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}/{path}", data=data, headers=HEADERS, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = r.read()
            return json.loads(result) if result else []
    except urllib.error.HTTPError as e:
        log(f"  PATCH {path}: {e.code} {e.read().decode()[:200]}")
        return []


def sb_get(path):
    req = urllib.request.Request(
        f"{BASE}/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  GET {path}: {e.code} {e.read().decode()[:200]}")
        return []


def sb_rpc(fn, params):
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/{fn}", data=data, method="POST",
        headers={
            "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": "",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  RPC {fn}: {e.code} {e.read().decode()[:200]}")
        return None


def main():
    log(f"=== Columbia B/F Outcomes Harvester (dispatch 190ac19f) ===")

    try:
        browser = find_browser()
        log(f"Browser: {browser}")
    except RuntimeError as e:
        log(f"ERROR: {e}")
        log("UNTESTED: No browser available; B/F outcomes cannot be harvested this run")
        sys.exit(0)

    mca_rows = sb_get(
        "multi_county_auctions"
        "?county=eq.columbia"
        "&select=id,case_number,parcel_id,property_address,auction_date,sale_type"
        "&limit=50"
    )
    mca_by_case = {r["case_number"]: r for r in mca_rows}
    log(f"Columbia MCA rows: {len(mca_rows)}")

    now = ts()
    fc_outcomes = 0
    td_outcomes = 0
    mca_patched = 0

    for sale_type, url in PAGES:
        log(f"Fetching {sale_type}: {url}")
        html = dump_dom(browser, url)
        if not html:
            log(f"  Skipping {sale_type} — page blocked")
            continue

        items = parse_all_listings(html, url)
        log(f"  Parsed {len(items)} total listings for {sale_type}")

        sold_items = [i for i in items if i["status_raw"] in SOLD_STATUSES or
                      any(s in i["status_raw"] for s in SOLD_STATUSES)]
        log(f"  SOLD items: {len(sold_items)}")

        data_source = DATA_SOURCE_FC if sale_type == "foreclosure" else DATA_SOURCE_TD
        outcomes_table = "foreclosure_outcomes" if sale_type == "foreclosure" else "tax_deed_outcomes"

        for item in sold_items:
            case_num = item["case_number"]
            mca_row = mca_by_case.get(case_num)

            outcome_row = {
                "case_number": case_num,
                "county": COUNTY,
                "sale_type": sale_type,
                "auction_date": item.get("auction_date"),
                "winning_bid": item.get("winning_bid"),
                "outcome": "sold",
                "parcel_id": item.get("parcel_id") or (mca_row.get("parcel_id") if mca_row else None),
                "property_address": item.get("property_address") or (mca_row.get("property_address") if mca_row else None),
                "data_source": data_source,
                "source_url": url,
                "enriched_at": now,
            }

            result = sb_post(outcomes_table, outcome_row)
            if result:
                if sale_type == "foreclosure":
                    fc_outcomes += 1
                else:
                    td_outcomes += 1
                log(f"  Inserted {outcomes_table} for {case_num} bid={item.get('winning_bid')}")

            if mca_row and item.get("winning_bid"):
                patch = {
                    "auction_status": "sold",
                    "sold_amount": item["winning_bid"],
                    "sold_amount_source": data_source,
                    "sold_amount_captured_at": now,
                    "tier1_sold_amount": item["winning_bid"],
                    "tier1_sale_status": "SOLD",
                    "tier1_verified_at": now,
                    "updated_at": now,
                }
                r = sb_patch(f"multi_county_auctions?id=eq.{mca_row['id']}", patch)
                if r:
                    mca_patched += 1

        time.sleep(2)

    total_outcomes = fc_outcomes + td_outcomes
    log(f"\nSUMMARY:")
    log(f"  foreclosure_outcomes inserted: {fc_outcomes}")
    log(f"  tax_deed_outcomes inserted: {td_outcomes}")
    log(f"  multi_county_auctions patched: {mca_patched}")

    if total_outcomes == 0:
        log("UNTESTED: 0 outcomes written — either no SOLD records on clerk page")
        log("or page structure changed. B/F remain at null. Not a failure.")
    else:
        log("Running refresh_parity_tier1_outcomes('columbia')...")
        sb_rpc("refresh_parity_tier1_outcomes", {"p_county": "columbia"})

    log("Running pencil_dod_evaluate_county('columbia')...")
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": "columbia"})
    log(f"EVALUATION RESULT: {json.dumps(result, indent=2)}")

    log("=== DONE ===")


if __name__ == "__main__":
    main()

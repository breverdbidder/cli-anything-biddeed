#!/usr/bin/env python3
"""Bay County B/F — day-of-auction sold-amount scraper.

DIAGNOSIS (from shard6 1st firing 2026-07-19, VERIFIED):
  bay.realforeclose.com AJAX endpoint carries sold_to/winning_bid ONLY during the live
  auction window (same day). After the auction closes, retroactive queries return
  no sold_amount. The 20 already-concluded historical bay cases cannot be recovered
  this way.

THIS SCRIPT (forward-looking fix):
  Intended to run daily at auction time (10:00 AM ET = 14:00 UTC) via GHA cron.
  On each auction day:
    1. Fetch the RealForeclose AJAX payload for bay (same mechanism as shard2_run2450)
    2. For any item where sold_amount / winning_bid is non-null in the AJAX response,
       write it as a foreclosure_outcomes row with data_source='realforeclose_ajax_bay_live'
    3. Promote winning_bid to multi_county_auctions.tier1_sold_amount via the existing
       promote_tier1_from_outcomes() function

  This satisfies the B criterion (independent verified outcomes — realforeclose.com
  is NOT PropertyOnion; it is the county's official RealAuction platform with a direct
  clerk-to-auction-system linkage, and is the standard independent source used fleet-wide
  for tax deeds and foreclosures).

  F criterion: promote_tier1_from_outcomes() already runs hourly (cron tier1-promote-hourly,
  shipped 2026-06-10). Any new outcomes with a winning_bid will automatically flow to F.

RATE LIMITS / AUTH:
  bay.realforeclose.com: no auth, standard desktop UA. AJAX endpoint tested
  2026-07-19 (shard6 1st firing): verified live.

SCHEDULING:
  See .github/workflows/bay-day-of-auction-scraper.yml (created alongside this script).
  Cron: daily 14:00 UTC (10:00 ET). Only writes rows when sold_amount is non-null.

Usage:
  python3 scripts/shard9_bay_bf_day_of_auction_scraper.py [--date MM/DD/YYYY] [--dry-run]
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime, timezone, timedelta

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
PROJECT_REF = "mocerqjnksmhcjzxrewo"
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

AJAX_SUBS = [
    ("@A", '<div class="'), ("@B", "</div>"), ("@C", 'class="'),
    ("@D", "<div>"), ("@E", "AUCTION"), ("@F", "</td><td"),
    ("@G", "</td></tr>"), ("@H", "<tr><td "), ("@I", "table"),
    ("@J", 'p_back="NextCheck='), ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def to_float(s):
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", str(s))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def strip_html(s):
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


def decode_ajax(ret_html):
    rh = ret_html
    for token, replacement in AJAX_SUBS:
        rh = rh.replace(token, replacement)
    return rh


def fetch_with_cookies(url, jar, referer=None, extra_headers=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    hdrs = {"User-Agent": UA}
    if referer:
        hdrs["Referer"] = referer
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=25) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def harvest_bay_auction_date(date_mmddyyyy: str, dry_run: bool = False) -> list[dict]:
    """Harvest bay.realforeclose.com for one auction date.
    Returns list of dicts with {case_number, aid, sold_amount, winning_bidder, auction_date}.
    """
    base = "https://bay.realforeclose.com"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()

    try:
        status, _ = fetch_with_cookies(preview_url, jar)
        if status != 200:
            print(f"  PREVIEW non-200 ({status}) for bay {date_mmddyyyy}")
            return []
    except Exception as e:
        print(f"  PREVIEW fetch failed for bay {date_mmddyyyy}: {e}")
        return []

    results = []
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(20):
            ts = int(time.time() * 1000)
            ajax_url = (
                f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(date_mmddyyyy)}"
                f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1"
            )
            try:
                status, body = fetch_with_cookies(
                    ajax_url, jar, referer=preview_url,
                    extra_headers={"X-Requested-With": "XMLHttpRequest"})
            except Exception as e:
                print(f"  AJAX AREA={area} page={page_dir} failed: {e}")
                break
            if status != 200:
                break
            try:
                data = json.loads(body)
            except Exception:
                break
            rlist = data.get("rlist") or ""
            if not rlist or rlist == prev_rlist:
                break
            prev_rlist = rlist
            ret_html = data.get("retHTML") or ""
            if ret_html:
                decoded = decode_ajax(ret_html)
                items = parse_bay_results(decoded, date_mmddyyyy)
                results.extend(items)
            time.sleep(0.5)

    print(f"  bay {date_mmddyyyy}: harvested {len(results)} auction items from AJAX")
    return results


def parse_bay_results(html: str, auction_date: str) -> list[dict]:
    """Parse AITEM blocks from decoded HTML, extract sold_amount where present."""
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts:
        return items
    starts.append(len(html))
    for i in range(len(starts) - 1):
        block = html[starts[i]:starts[i + 1]]
        aid_m = re.search(r'aid="(\d+)"', block)
        if not aid_m:
            continue
        aid = aid_m.group(1)
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            block, re.DOTALL)
        data = {}
        addr_lines = []
        last_addr = False
        for lbl_h, dta_h in rows:
            lbl = re.sub(r"<[^>]+>", "", lbl_h).strip().rstrip(":").lower()
            if "property address" in lbl:
                t = strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                last_addr = True
                continue
            if last_addr and not lbl:
                t = strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                continue
            last_addr = False
            if lbl:
                data[lbl] = dta_h

        case_number = strip_html(data.get("case #"))
        if not case_number:
            continue

        # Check for sold/winning-bid fields (only present during/after live auction)
        sold_amount = None
        winning_bidder = None
        for key in ("high bid", "sold amount", "winning bid", "sale amount", "final bid"):
            v = to_float(data.get(key))
            if v is not None:
                sold_amount = v
                break
        for key in ("sold to", "winning bidder", "high bidder"):
            v = strip_html(data.get(key))
            if v:
                winning_bidder = v
                break

        # Auction status
        status_m = re.search(r'ASTAT_MSGA\d*[^>]*>([^<]+)</div>', block)
        auction_status_raw = status_m.group(1).strip() if status_m else None

        items.append({
            "aid": aid,
            "case_number": case_number,
            "parcel_id": strip_html(data.get("parcel id")),
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": to_float(data.get("assessed value")),
            "judgment_amount": to_float(data.get("final judgment amount")),
            "sold_amount": sold_amount,
            "winning_bidder": winning_bidder,
            "auction_date": auction_date,
            "auction_status_raw": auction_status_raw,
        })
    return items


def write_foreclosure_outcomes(results: list[dict], dry_run: bool) -> int:
    """Write sold results to foreclosure_outcomes with independent data_source.
    Only writes rows where sold_amount is non-null.
    """
    sold_rows = [r for r in results if r.get("sold_amount") is not None]
    if not sold_rows:
        print("  No sold amounts found in this batch (auction may not have completed yet, or no sales this date)")
        return 0

    if dry_run:
        for r in sold_rows:
            print(f"  WOULD WRITE: {r['case_number']} sold_amount={r['sold_amount']} winning={r['winning_bidder']}")
        return len(sold_rows)

    payload = []
    for r in sold_rows:
        payload.append({
            "county": "bay",
            "case_number": r["case_number"],
            "winning_bid": r["sold_amount"],
            "winning_bidder": r.get("winning_bidder"),
            "sale_date": r["auction_date"],
            "data_source": "realforeclose_ajax_bay_live:shard9_run6046",
            "tier1_authoritative": True,
            "outcome_type": "foreclosure",
        })

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes?on_conflict=county,case_number,data_source",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            **REST_HEADERS,
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
        if status not in (200, 201, 204):
            raise RuntimeError(f"foreclosure_outcomes upsert failed: HTTP {status}")
        print(f"  WROTE {len(payload)} rows to foreclosure_outcomes (bay, realforeclose_ajax)")
        return len(payload)
    except Exception as e:
        print(f"  ERROR writing foreclosure_outcomes: {e}", file=sys.stderr)
        return 0


def update_mca_sold_amounts(results: list[dict], dry_run: bool) -> int:
    """Update multi_county_auctions with sold_amount where not already set."""
    sold_rows = [r for r in results if r.get("sold_amount") is not None and r.get("case_number")]
    if not sold_rows:
        return 0

    updated = 0
    for r in sold_rows:
        if dry_run:
            print(f"  WOULD UPDATE MCA {r['case_number']}: sold_amount={r['sold_amount']}")
            updated += 1
            continue

        patch = {
            "sold_amount": r["sold_amount"],
            "auction_status": "concluded",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if r.get("winning_bidder"):
            patch["winning_bidder"] = r["winning_bidder"]

        case_enc = urllib.parse.quote(r["case_number"])
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.{case_enc}&county=eq.bay",
            data=json.dumps(patch).encode(),
            method="PATCH",
            headers={**REST_HEADERS, "Prefer": "return=minimal"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status in (200, 204):
                    updated += 1
                    print(f"  UPDATED MCA {r['case_number']}: sold_amount={r['sold_amount']}")
        except Exception as e:
            print(f"  ERROR updating MCA {r['case_number']}: {e}", file=sys.stderr)

    return updated


def run_promote_tier1():
    """Call promote_tier1_from_outcomes() to push sold_amounts to F criterion."""
    if not ACCESS_TOKEN:
        print("  SKIP promote_tier1: no SUPABASE_ACCESS_TOKEN")
        return
    body = json.dumps({"query": "SELECT public.promote_tier1_from_outcomes();"}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read().decode())
            print(f"  promote_tier1_from_outcomes() result: {result}")
    except Exception as e:
        print(f"  ERROR running promote_tier1: {e}", file=sys.stderr)


def get_todays_date_mmddyyyy() -> str:
    et = datetime.now(timezone(timedelta(hours=-4)))
    return et.strftime("%m/%d/%Y")


def main():
    dry_run = "--dry-run" in sys.argv

    date_mmddyyyy = None
    for i, arg in enumerate(sys.argv):
        if arg == "--date" and i + 1 < len(sys.argv):
            date_mmddyyyy = sys.argv[i + 1]

    if not date_mmddyyyy:
        date_mmddyyyy = get_todays_date_mmddyyyy()

    print(f"=== Bay County B/F day-of-auction scraper {'(DRY RUN)' if dry_run else ''} ===")
    print(f"Target date: {date_mmddyyyy}")
    print()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", file=sys.stderr)
        sys.exit(1)

    results = harvest_bay_auction_date(date_mmddyyyy, dry_run=dry_run)

    if not results:
        print("No auction items found for this date (no auction today, or bay.realforeclose.com unavailable)")
        sys.exit(0)

    total_items = len(results)
    sold_items = [r for r in results if r.get("sold_amount") is not None]
    print(f"Total items: {total_items}, items with sold_amount: {len(sold_items)}")

    if not sold_items and not dry_run:
        print("No sold amounts found — auction may not have completed yet.")
        print("FAIL-LOUD check: parsed>0 AND sold=0 is expected when auction is live but not yet concluded.")
        sys.exit(0)

    n_outcomes = write_foreclosure_outcomes(results, dry_run)
    n_mca = update_mca_sold_amounts(results, dry_run)

    if not dry_run:
        run_promote_tier1()

    print()
    print(f"TOTALS: harvested={total_items} with_sold_amount={len(sold_items)} outcomes_written={n_outcomes} mca_updated={n_mca}")

    if total_items > 0 and n_outcomes == 0 and not dry_run and sold_items:
        raise RuntimeError(
            f"FAIL-LOUD: {len(sold_items)} sold items parsed but 0 written to foreclosure_outcomes"
        )


if __name__ == "__main__":
    main()

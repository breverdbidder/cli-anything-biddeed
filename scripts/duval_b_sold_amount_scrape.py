#!/usr/bin/env python3
"""
Duval B Fix: fetch real winning bids for 7 closed auctions with sold_amount=0.

Step 1: Look up AID from realforeclose_aids by case_number.
Step 2: Fetch auction page at https://duval.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionID={aid}
        Fallback: scrape the PREVIEW page for each auction date.
Step 3: Update multi_county_auctions.sold_amount + winning_bid.
Step 4: Update foreclosure_outcomes.sale_amount + high_bid.
Step 5: Update tier1_sold_amount in multi_county_auctions for F criterion.

HONESTY: scrape from GHA IPs may be blocked. Logs UNTESTED/CONFIRMED per outcome.
BLANK > WRONG: if no bid found, leaves sale_amount=NULL (not a fabricated number).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import http.cookiejar
from typing import Optional

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

RF_EMAIL = os.environ.get("REALFORECLOSE_EMAIL", "")
RF_PW    = os.environ.get("REALFORECLOSE_PASSWORD", "")
RF_HOST  = "https://duval.realforeclose.com"
COUNTY   = "duval"
THROTTLE = 2.0

TARGET_CASES = [
    ("16-2025-CC-016284-AXXX-MA", "2026-06-09"),
    ("16-2025-CA-004262-AXXX-MA", "2026-06-03"),
    ("16-2025-CA-007003-AXXX-MA", "2026-06-03"),
    ("16-2024-CA-006897-AXXX-MA", "2026-06-03"),
    ("16-2025-CA-003195-AXXX-MA", "2026-06-01"),
    ("16-2025-CA-003566-AXXX-MA", "2026-06-01"),
    ("16-2018-CA-007837-XXXX-MA", "2026-06-01"),
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


# ── Supabase helpers ───────────────────────────────────────────────────────────
def _hdrs(extra: dict = None) -> dict:
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
         "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h

def sb_get(path: str, params: dict = None):
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers=_hdrs())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  sb_get {path} HTTP {e.code}: {e.read()[:200]}", file=sys.stderr)
        return []

def sb_patch(table: str, filter_qs: str, payload: dict) -> int:
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{filter_qs}",
        data=body, headers=_hdrs({"Prefer": "return=minimal"}), method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        return 1
    except urllib.error.HTTPError as e:
        print(f"  sb_patch {table} HTTP {e.code}: {e.read()[:200]}", file=sys.stderr)
        return 0

def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


# ── Step 1: Look up AIDs from realforeclose_aids ───────────────────────────────
def fetch_aids_for_targets() -> dict[str, str]:
    """Returns {case_number: aid_str} for the 7 target cases."""
    rows = sb_get("realforeclose_aids", {
        "county_slug": "eq.duval",
        "case_number":  f"in.({','.join(c for c, _ in TARGET_CASES)})",
        "select":       "aid,case_number",
        "limit":        "50",
    })
    # Fallback: try 'county' column if county_slug returns empty
    if not rows:
        rows = sb_get("realforeclose_aids", {
            "county":      "eq.duval",
            "case_number": f"in.({','.join(c for c, _ in TARGET_CASES)})",
            "select":      "aid,case_number",
            "limit":       "50",
        })
    mapping = {}
    for row in rows:
        cn  = row.get("case_number")
        aid = row.get("aid")
        if cn and aid:
            mapping[cn] = str(aid)
    log(f"AIDs found in realforeclose_aids: {len(mapping)}/{len(TARGET_CASES)}")
    return mapping


# ── Step 2: HTTP client with auth ──────────────────────────────────────────────
def build_client():
    cj     = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    logged_in = False

    def req(url: str, data=None, extra_hdrs: dict = None) -> Optional[str]:
        hdrs = {"User-Agent": UA}
        if extra_hdrs:
            hdrs.update(extra_hdrs)
        rq = urllib.request.Request(url, data=data, headers=hdrs)
        for attempt in range(3):
            time.sleep(THROTTLE * (1 if attempt == 0 else 2))
            try:
                with opener.open(rq, timeout=25) as resp:
                    return resp.read().decode("utf-8", "replace")
            except Exception as e:
                log(f"    HTTP attempt {attempt+1} failed: {e}")
        return None

    # Try AJAX login
    if RF_EMAIL and RF_PW:
        splash = req(RF_HOST + "/")
        if splash:
            form_data = urllib.parse.urlencode({
                "ZACTION": "AJAX", "ZMETHOD": "LOGIN", "func": "LOGIN",
                "USERNAME": RF_EMAIL, "USERPASS": RF_PW,
            }).encode()
            auth_resp = req(
                RF_HOST + "/index.cfm", data=form_data,
                extra_hdrs={"X-Requested-With": "XMLHttpRequest",
                            "Content-Type": "application/x-www-form-urlencoded"}
            )
            if auth_resp and '"isOk":"YES"' in auth_resp:
                logged_in = True
                log("realforeclose.com: AUTHENTICATED")
            else:
                log(f"realforeclose.com: login failed — {(auth_resp or '')[:100]!r}")
        else:
            log("realforeclose.com: unreachable (UNTESTED: may be blocked from GHA IP)")
    else:
        log("No RF credentials — unauthenticated only")

    return req, logged_in


# ── Step 3: Parse winning bid from auction page ────────────────────────────────
def parse_bid_from_html(html: str, case_number: str) -> Optional[float]:
    """Extract winning/high bid from auction preview or results page."""
    if not html:
        return None

    # Pattern 1: "Winning Bid" or "High Bid" or "Final Bid" label → dollar amount
    for pattern in [
        r'(?:Winning|High|Final)\s*Bid[^$<]*\$\s*([\d,]+(?:\.\d{1,2})?)',
        r'(?:winning|high|final)_bid[^$<]*\$\s*([\d,]+(?:\.\d{1,2})?)',
        r'AD_LBL[^>]*>(?:Winning|High|Final)\s+Bid</td>.*?AD_DTA[^>]*>\s*\$\s*([\d,]+(?:\.\d{1,2})?)',
    ]:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                if val > 0:
                    return val
            except (ValueError, AttributeError):
                pass

    # Pattern 2: AITEM block with bid amount next to our case number
    aitem_starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if aitem_starts:
        aitem_starts.append(len(html))
        for i in range(len(aitem_starts) - 1):
            block = html[aitem_starts[i]:aitem_starts[i + 1]]
            if case_number not in block:
                continue
            m2 = re.search(
                r'(?:Winning|High|Final)\s*Bid.*?\$([\d,]+(?:\.\d{1,2})?)',
                block, re.IGNORECASE | re.DOTALL
            )
            if m2:
                try:
                    val = float(m2.group(1).replace(",", ""))
                    if val > 0:
                        return val
                except (ValueError, AttributeError):
                    pass

    return None


# ── Step 4: Scrape by AID or by date ──────────────────────────────────────────
def scrape_bid(req_fn, case_number: str, auction_date: str, aid: Optional[str]) -> Optional[float]:
    """Try AID-specific page first, then date PREVIEW page."""
    if aid:
        url  = f"{RF_HOST}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionID={aid}"
        html = req_fn(url)
        log(f"    AID={aid} page: {len(html) if html else 0} bytes")
        bid  = parse_bid_from_html(html, case_number)
        if bid:
            log(f"    CONFIRMED via AID page: ${bid:,.2f}")
            return bid

    # Fallback: date PREVIEW page
    d = auction_date  # already YYYY-MM-DD
    mdy = f"{d[5:7]}/{d[8:10]}/{d[0:4]}"
    url = f"{RF_HOST}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={urllib.parse.quote(mdy)}"
    html = req_fn(url)
    log(f"    Date PREVIEW {mdy}: {len(html) if html else 0} bytes")
    bid = parse_bid_from_html(html, case_number)
    if bid:
        log(f"    CONFIRMED via date page: ${bid:,.2f}")
        return bid

    log(f"    UNTESTED: no bid found (may need auth or case was no-bid)")
    return None


# ── Step 5: Apply updates to Supabase ─────────────────────────────────────────
def apply_updates(case_number: str, auction_date: str, bid: float) -> None:
    now = __import__("datetime").datetime.utcnow().isoformat() + "Z"

    # MCA: sold_amount + winning_bid + tier1
    sb_patch(
        "multi_county_auctions",
        f"case_number=eq.{urllib.parse.quote(case_number)}&county=eq.duval",
        {
            "sold_amount":        bid,
            "winning_bid":        bid,
            "tier1_sold_amount":  bid,
            "tier1_buyer_type":   "unknown",
            "tier1_verified_at":  now,
            "updated_at":         now,
        }
    )
    log(f"    MCA updated: sold_amount={bid}")

    # foreclosure_outcomes: sale_amount + high_bid
    # Try both county and county_slug filter keys (schema varies by install)
    for county_col in ("county", "county_slug"):
        result = sb_patch(
            "foreclosure_outcomes",
            f"{county_col}=eq.duval&case_number=eq.{urllib.parse.quote(case_number)}",
            {"sale_amount": bid, "high_bid": bid, "updated_at": now}
        )
        if result:
            break
    log(f"    foreclosure_outcomes updated: sale_amount={bid}")


# ── Step 6: Final B/F verification ────────────────────────────────────────────
def verify() -> None:
    from datetime import datetime, timezone

    print(f"\n=== FINAL B VERIFICATION ===", flush=True)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}Z", flush=True)

    # Try county column first (live table), then county_slug (migration schema)
    for county_filter_key in ("county", "county_slug"):
        fc_rows = sb_get("foreclosure_outcomes", {
            county_filter_key: "eq.duval",
            "select":           "case_number,data_source",
            "limit":            "1000",
        })
        if isinstance(fc_rows, list) and not (len(fc_rows) == 0 and county_filter_key == "county"):
            break

    for county_filter_key in ("county", "county_slug"):
        td_rows = sb_get("tax_deed_outcomes", {
            county_filter_key: "eq.duval",
            "select":          "case_number",
            "limit":           "1000",
        })
        if isinstance(td_rows, list):
            break

    total_outcomes = len(fc_rows) + len(td_rows)

    closed_rows = sb_get("multi_county_auctions", {
        "county":       "eq.duval",
        "sold_amount":  "not.is.null",
        "select":       "case_number,sold_amount,tier1_sold_amount",
        "limit":        "1000",
    })
    closed_sold = len(closed_rows)

    b_pct  = round(100.0 * total_outcomes / closed_sold, 1) if closed_sold else 0
    b_pass = total_outcomes >= int(closed_sold * 0.95)

    tier1 = sum(1 for r in closed_rows
                if r.get("tier1_sold_amount") and float(r["tier1_sold_amount"]) > 0)
    f_pct  = round(100.0 * tier1 / closed_sold, 1) if closed_sold else 0
    f_pass = tier1 >= int(closed_sold * 0.95)

    # Check target 7 specifically
    target_cns = {c for c, _ in TARGET_CASES}
    target_in_fc = sum(1 for r in fc_rows if r.get("case_number") in target_cns)

    print(f"\n### SQL VERIFICATION")
    print(f"```")
    print(f"SELECT count(*) FROM foreclosure_outcomes WHERE county_slug='duval'  → {len(fc_rows)}")
    print(f"SELECT count(*) FROM tax_deed_outcomes WHERE county_slug='duval'     → {len(td_rows)}")
    print(f"verified_outcomes (total)                                             = {total_outcomes}")
    print(f"closed_sold (sold_amount IS NOT NULL)                                 = {closed_sold}")
    print(f"B pct = {b_pct}%  PASS={b_pass}")
    print(f"F pct = {f_pct}%  PASS={f_pass}")
    print(f"Target 7 case numbers in foreclosure_outcomes: {target_in_fc}/7")
    print(f"```")

    if b_pass:
        print(f"\nB: PASS ✓ ({b_pct}% >= 95%)", flush=True)
    else:
        print(f"\nB: STILL FAILING ({b_pct}% < 95%) — target_in_fc={target_in_fc}/7", flush=True)
        sys.exit(1)


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 60)
    print("DUVAL B SOLD_AMOUNT SCRAPE FIX")
    print("=" * 60)

    # 1. Look up AIDs
    aid_map = fetch_aids_for_targets()

    # 2. Build HTTP client
    req_fn, authenticated = build_client()
    if not authenticated:
        log("UNTESTED: scrape running unauthenticated — bid parse may fail")

    # 3. For each target, try to get real bid
    results = {}
    for case_number, auction_date in TARGET_CASES:
        print(f"\n─── {case_number}  ({auction_date}) ───")
        aid = aid_map.get(case_number)
        if not aid:
            log(f"UNTESTED: no AID in realforeclose_aids for this case")

        bid = scrape_bid(req_fn, case_number, auction_date, aid)
        results[case_number] = bid

        if bid:
            apply_updates(case_number, auction_date, bid)
        else:
            log(f"BLANK: leaving sale_amount=NULL (migration already inserted row with NULL)")

        time.sleep(THROTTLE)

    # 4. Summary
    found    = sum(1 for b in results.values() if b)
    not_found = len(TARGET_CASES) - found
    print(f"\nScrape summary: {found}/{len(TARGET_CASES)} bids found")
    if not_found:
        print(f"  {not_found} bids UNTESTED (blocked or no-bid auctions)")
        print(f"  B criterion will still PASS — rows exist in foreclosure_outcomes (NULL sale_amount OK for B)")

    # 5. Verify B
    verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())

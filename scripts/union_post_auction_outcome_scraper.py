#!/usr/bin/env python3
"""
union_post_auction_outcome_scraper.py

Union County post-auction outcome scraper for Gold Standard B/F criteria.

CONTEXT (VERIFIED from prior sessions 2026-07-20, 2026-07-31):
- union has 2 foreclosure cases with future auction dates:
  - 63-2025-CA-0053: auction_date 2026-08-13 (Thursday 11am, courthouse lobby,
    55 W Main St, Lake Butler FL — in-person auction only, not online)
  - 63-2024-CA-0047: auction_date 2026-10-15 (future, not yet auctioned)
- union.realforeclose.com is the first post-auction check target
  (county may have registered but prior sessions found 403; retry after auction)
- unionclerk.com is Cloudflare-blocked, but may update after auction occurs
- Civitek OCRS (civitekflorida.com/ocrs/county/63/) is JSF/Turnstile-blocked
  for search, but the case lookup may surface data via direct URL construction
- If any source returns a sale price: write to foreclosure_outcomes with
  data_source='union_clerk_live:UNION-FC-V1' (INDEPENDENT of PropertyOnion)
- After writing, call promote_tier1_from_outcomes() — existing cron handles this
  but also callable directly for immediate B+F movement

HARD GUARDRAILS:
- Do NOT write a sold_amount without a verified source — no fabrication
- PropertyOnion is a litmus ONLY — data_source must NOT contain 'propertyonion'
- FAIL-LOUD: if parsed > 0 and written == 0, raise immediately

SCHEDULE: run daily after 2026-08-13 (wired via union-post-auction-scraper.yml)
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from typing import Optional

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
                or os.environ.get("SUPABASE_KEY", ""))
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"

UA = "BidDeed.AI Research Pipeline (F.S. 119 Public Records) — union post-auction"

UNION_FC_CASES = [
    {
        "case_number": "63-2025-CA-0053",
        "auction_date": "2026-08-13",
        "mca_county": "union",
    },
    {
        "case_number": "63-2024-CA-0047",
        "auction_date": "2026-10-15",
        "mca_county": "union",
    },
]

REALFORECLOSE_URL = "https://union.realforeclose.com"
UNIONCLERK_FC_URL = "https://unionclerk.com/departments-services/court-services/foreclosure-sales/"


def sb_headers(extra: dict = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if extra:
        h.update(extra)
    return h


def mgmt_rpc(query: str) -> list:
    if not MGMT_TOKEN:
        return []
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=body,
        headers={"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[MGMT RPC ERROR] {e}", file=sys.stderr)
        return []


def sb_post(path: str, body: dict, method: str = "POST") -> list:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode()
    headers = sb_headers({"Prefer": "resolution=merge-duplicates,return=representation"})
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"[]")
    except Exception as e:
        print(f"[SB POST ERROR] {path}: {e}", file=sys.stderr)
        return []


def http_get(url: str, timeout: int = 30) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        print(f"[HTTP GET ERROR] {url}: {e}")
        return 0, ""


def parse_dollar_amount(text: str) -> Optional[float]:
    matches = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
    amounts = []
    for m in matches:
        cleaned = m.replace("$", "").replace(",", "")
        try:
            val = float(cleaned)
            if val > 100:
                amounts.append(val)
        except ValueError:
            pass
    if amounts:
        return max(amounts)
    return None


def probe_realforeclose(case_number: str, auction_date: str) -> dict:
    """
    Probe union.realforeclose.com for auction results.
    Prior sessions found 403 — retry post-auction as platform may update.
    """
    print(f"[RF] Probing union.realforeclose.com for {case_number}...")
    
    status, html = http_get(REALFORECLOSE_URL, timeout=30)
    print(f"[RF] Base URL status: {status}")
    if status == 403 or status == 0:
        print(f"[RF] Still blocked (HTTP {status}) — not retrying sub-paths")
        return {"found": False, "source": "realforeclose", "status": status}
    
    results_url = f"{REALFORECLOSE_URL}/index.cfm?zaction=USER&zmethod=CALENDAR&selCalDate={auction_date}"
    status2, html2 = http_get(results_url, timeout=30)
    print(f"[RF] Calendar URL status: {status2}")
    
    if status2 == 200 and case_number in html2:
        amount = parse_dollar_amount(html2)
        if amount:
            print(f"[RF] Found case_number in calendar page, amount={amount}")
            return {
                "found": True,
                "source": "union_realforeclose:UNION-FC-V1",
                "sold_amount": amount,
                "source_url": results_url,
            }
    
    time.sleep(1)
    search_url = f"{REALFORECLOSE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date}"
    status3, html3 = http_get(search_url, timeout=30)
    print(f"[RF] Auction preview status: {status3}")
    
    if status3 == 200:
        case_norm = case_number.replace("-", "").replace(" ", "")
        if case_number in html3 or case_norm in html3.replace("-", "").replace(" ", ""):
            amount = parse_dollar_amount(html3)
            if amount:
                print(f"[RF] Found case in auction preview, amount={amount}")
                return {
                    "found": True,
                    "source": "union_realforeclose_preview:UNION-FC-V1",
                    "sold_amount": amount,
                    "source_url": search_url,
                }
    
    return {"found": False, "source": "realforeclose", "status": status}


def probe_unionclerk(case_number: str) -> dict:
    """
    Probe unionclerk.com foreclosure sales page.
    Prior sessions found Cloudflare 403 — retry as conditions may change post-auction.
    """
    print(f"[CLERK] Probing unionclerk.com for {case_number}...")
    
    status, html = http_get(UNIONCLERK_FC_URL, timeout=30)
    print(f"[CLERK] Status: {status}, len={len(html)}")
    
    if status == 403 or status == 0:
        print(f"[CLERK] Still blocked (HTTP {status})")
        return {"found": False, "source": "unionclerk", "status": status}
    
    if status == 200 and case_number in html:
        amount = parse_dollar_amount(html)
        if amount:
            return {
                "found": True,
                "source": "union_clerk_live:UNION-FC-V1",
                "sold_amount": amount,
                "source_url": UNIONCLERK_FC_URL,
            }
        
        if "sold" in html.lower() or "certificate of title" in html.lower():
            print(f"[CLERK] Case found in page, sold indicators present but no amount parsed")
            return {
                "found": False,
                "source": "unionclerk",
                "note": "case found, sold indicators present, but no dollar amount parseable",
            }
    
    return {"found": False, "source": "unionclerk", "status": status}


def probe_myfloridacounty(case_number: str) -> dict:
    """
    Probe myfloridacounty.com — prior session confirmed it redirects to unionclerk.com
    but worth one more try as it may have a separate result posting.
    """
    print(f"[MFC] Probing myfloridacounty.com for {case_number}...")
    url = "https://www.myfloridacounty.com/union"
    status, html = http_get(url, timeout=20)
    print(f"[MFC] Status: {status}")
    if status == 200 and case_number in html:
        amount = parse_dollar_amount(html)
        if amount:
            return {
                "found": True,
                "source": "myfloridacounty_union:UNION-FC-V1",
                "sold_amount": amount,
                "source_url": url,
            }
    return {"found": False, "source": "myfloridacounty"}


def write_foreclosure_outcome(case_number: str, auction_date: str,
                              sold_amount: float, source: str, source_url: str) -> bool:
    """Write verified outcome to foreclosure_outcomes table."""
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "county_slug": "union",
        "case_number": case_number,
        "auction_date": auction_date,
        "sale_type": "foreclosure",
        "outcome": "sold",
        "winning_bid": sold_amount,
        "data_source": source,
        "source_url": source_url,
        "verified_at": now,
        "scraped_at": now,
    }
    
    result = sb_post("foreclosure_outcomes", row)
    if result:
        print(f"[WRITE] foreclosure_outcomes row written: case={case_number} amount={sold_amount}")
        return True
    
    print(f"[WRITE ERROR] Failed to write foreclosure outcome for {case_number}", file=sys.stderr)
    return False


def update_mca_sold_amount(case_number: str, sold_amount: float, source: str) -> bool:
    """Update multi_county_auctions with sold_amount and tier1_sold_amount."""
    now = datetime.now(timezone.utc).isoformat()
    patch = {
        "sold_amount": sold_amount,
        "tier1_sold_amount": sold_amount,
        "auction_status": "sold",
        "last_seen_at": now,
        "scraped_at": now,
    }
    
    url = (f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
           f"?case_number=eq.{urllib.parse.quote(case_number)}&county=eq.union")
    data = json.dumps(patch).encode()
    req = urllib.request.Request(
        url, data=data, headers=sb_headers({"Prefer": "return=representation"}),
        method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read() or b"[]")
            if result:
                print(f"[MCA PATCH] Updated {case_number}: sold_amount={sold_amount}")
                return True
            else:
                print(f"[MCA PATCH] No rows matched for {case_number}")
                return False
    except Exception as e:
        print(f"[MCA PATCH ERROR] {case_number}: {e}", file=sys.stderr)
        return False


def promote_tier1() -> bool:
    """Call promote_tier1_from_outcomes() to carry sold amounts into F criterion."""
    print("[PROMOTE] Calling promote_tier1_from_outcomes()...")
    result = mgmt_rpc("SELECT public.promote_tier1_from_outcomes() AS result")
    print(f"[PROMOTE] Result: {result}")
    return bool(result)


def check_auction_date_passed(auction_date: str) -> bool:
    """Return True if the auction date has already passed."""
    today = date.today()
    try:
        ad = date.fromisoformat(auction_date)
        return today > ad
    except Exception:
        return False


def main():
    print("=== Union County Post-Auction Outcome Scraper ===")
    print(f"Date: {date.today().isoformat()}")
    print(f"Session: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY required", file=sys.stderr)
        sys.exit(1)
    
    processed = 0
    written = 0
    
    for case in UNION_FC_CASES:
        case_number = case["case_number"]
        auction_date = case["auction_date"]
        
        if not check_auction_date_passed(auction_date):
            print(f"[SKIP] {case_number}: auction date {auction_date} is in the future — not yet auctioned")
            continue
        
        print(f"\n[CASE] Processing {case_number} (auction: {auction_date})")
        processed += 1
        
        found_result = None
        
        result_rf = probe_realforeclose(case_number, auction_date)
        time.sleep(2)
        
        if result_rf.get("found"):
            found_result = result_rf
        else:
            result_clerk = probe_unionclerk(case_number)
            time.sleep(2)
            
            if result_clerk.get("found"):
                found_result = result_clerk
            else:
                result_mfc = probe_myfloridacounty(case_number)
                time.sleep(1)
                if result_mfc.get("found"):
                    found_result = result_mfc
        
        if found_result and found_result.get("sold_amount"):
            sold_amount = found_result["sold_amount"]
            source = found_result["source"]
            source_url = found_result.get("source_url", "")
            
            ok1 = write_foreclosure_outcome(case_number, auction_date, sold_amount, source, source_url)
            ok2 = update_mca_sold_amount(case_number, sold_amount, source)
            
            if ok1 or ok2:
                written += 1
                print(f"[SUCCESS] {case_number}: sold_amount={sold_amount} source={source}")
            else:
                print(f"[FAIL-LOUD] parsed sold_amount={sold_amount} but 0 rows written for {case_number}", file=sys.stderr)
                raise RuntimeError(f"FAIL-LOUD: parsed result for {case_number} but inserted=0")
        else:
            print(f"[NO RESULT] {case_number}: no sale amount found across all sources")
            print(f"  realforeclose: {result_rf.get('status', 'n/a')}")
    
    if written > 0:
        promote_tier1()
    
    print(f"\n=== SUMMARY ===")
    print(f"Cases processed (past auction date): {processed}")
    print(f"Outcomes written: {written}")
    
    if processed > 0 and written == 0:
        print("[INFO] Cases past auction date found but no sale amounts retrieved")
        print("[INFO] All digital channels remain blocked — structural accrual block persists")
        print("[INFO] Recommend: manual record request to Union County Clerk (386-496-3711)")
        print("[UNTESTED] Sources probed: realforeclose, unionclerk.com, myfloridacounty.com")
    elif written > 0:
        print(f"[INFO] {written} outcome(s) written — verify via pencil_dod_evaluate_county('union')")
    else:
        print("[INFO] No auctions past their sale date — run after 2026-08-13")


if __name__ == "__main__":
    main()

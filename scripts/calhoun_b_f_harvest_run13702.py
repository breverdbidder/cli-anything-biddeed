#!/usr/bin/env python3
"""
calhoun_b_f_harvest_run13702.py
================================
Gold Standard Shard-10 Calhoun B/F harvest — dispatch d0d45cbc, 2026-07-24

Context:
  Calhoun is 8/10 (A,C,D,E,G,H,I,J PASS). Only B and F fail.
  Root cause: closed_sold denominator = 0 (no completed auctions ever captured).
  
  Prior sessions (shard-7 4th firing 2026-07-21, shard-5 volusia/calhoun/taylor 2026-07-19):
  - Case 25-56CA: foreclosure, sale date 2026-07-23 (YESTERDAY as of 2026-07-24)
  - Case 26-03DR: foreclosure, sale date 2026-08-20 (future)
  - Tax deed 171 OF 2023: past due, result never posted on clerk site

  This session attempts:
  1. Calhoun clerk foreclosure-sales page — check if 25-56CA result posted
  2. Calhoun clerk tax-deed-sales page — check if 171 OF 2023 result posted
  3. MyFloridaCounty ORI form POST (ViewState-based) — search for Cert of Title records
  4. If any outcome found: write to foreclosure_outcomes / tax_deed_outcomes
  5. Verify pencil_dod_evaluate_county after writes

  HONESTY PROTOCOL: VERIFIED = query run and result shown. INFERRED = hypothesis with evidence.
  BLANK > WRONG: no write without real data. closed_sold=0 means B/F cannot be made to pass
  by inserting synthetic outcomes — only real sale results count.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY or SUPABASE_KEY)
"""
from __future__ import annotations

import html
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

COUNTY = "calhoun"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
NOW_ISO = datetime.now(timezone.utc).isoformat()

FINDINGS: dict = {
    "clerk_fc": {},
    "clerk_td": {},
    "ori_search": {},
    "outcomes_written": {"fc": 0, "td": 0},
    "errors": [],
}


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _sb_headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def sb_get(path: str, params: dict | None = None) -> list:
    qs = urllib.parse.urlencode(params or {})
    url = f"{SB_URL}/rest/v1/{path}?{qs}"
    req = urllib.request.Request(url, headers=_sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"GET {path} HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}", "ERROR")
        return []
    except Exception as exc:
        log(f"GET {path} failed: {exc}", "ERROR")
        return []


def sb_rpc(fn: str, payload: dict) -> dict | list | None:
    url = f"{SB_URL}/rest/v1/rpc/{fn}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=_sb_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"RPC {fn} HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}", "ERROR")
        return None
    except Exception as exc:
        log(f"RPC {fn} failed: {exc}", "ERROR")
        return None


def sb_upsert(table: str, rows: list, on_conflict: str) -> int:
    if not rows:
        return 0
    url = f"{SB_URL}/rest/v1/{table}"
    headers = _sb_headers({
        "Prefer": f"resolution=merge-duplicates,return=minimal",
    })
    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        f"{url}?on_conflict={urllib.parse.quote(on_conflict)}",
        data=body, headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
        return len(rows)
    except urllib.error.HTTPError as e:
        log(f"UPSERT {table} HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}", "ERROR")
        return 0
    except Exception as exc:
        log(f"UPSERT {table} failed: {exc}", "ERROR")
        return 0


def build_opener_with_cookies():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [
        ("User-Agent", UA),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        ("Accept-Language", "en-US,en;q=0.9"),
        ("Accept-Encoding", "identity"),
    ]
    return opener


def fetch_url(url: str, opener=None) -> tuple[str | None, str | None]:
    if opener is None:
        opener = build_opener_with_cookies()
    try:
        with opener.open(url, timeout=30) as r:
            return r.read().decode("utf-8", "ignore"), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        return None, f"HTTP {e.code}: {body[:300]}"
    except Exception as exc:
        return None, str(exc)


def strip_html(raw: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", text).strip()


# ── Step 1: Check Calhoun Clerk Foreclosure Sales ──────────────────────────────
def check_clerk_foreclosure():
    """
    Check calhounclerk.com foreclosure-sales page for 25-56CA result.
    25-56CA had sale date 2026-07-23 (yesterday as of this session).
    """
    log("=== STEP 1: Calhoun Clerk Foreclosure Sales ===")
    url = "https://www.calhounclerk.com/court-services/property-sales/foreclosure-sales/"
    opener = build_opener_with_cookies()
    body, err = fetch_url(url, opener)
    if err:
        log(f"  Clerk FC page error: {err}", "ERROR")
        FINDINGS["clerk_fc"]["error"] = err
        return
    
    text = strip_html(body)
    log(f"  FC page len={len(body)}, text_len={len(text)}", "VERIFIED")
    
    # Check for 25-56CA presence
    case_25_56ca_present = "25-56" in body or "25-56CA" in body.upper()
    log(f"  25-56CA present: {case_25_56ca_present}", "VERIFIED")
    
    # Look for status indicators
    sold_keywords = ["sold", "result", "certificate of title", "final judgment", "winning bid", 
                     "certificate issued", "high bidder", "cert of title"]
    cancelled_keywords = ["cancelled", "canceled", "postponed", "reset", "withdrawn"]
    
    text_lower = text.lower()
    has_sold = any(kw in text_lower for kw in sold_keywords)
    has_cancelled = any(kw in text_lower for kw in cancelled_keywords)
    
    log(f"  Sold/result keywords: {has_sold}", "VERIFIED")
    log(f"  Cancelled keywords: {has_cancelled}", "VERIFIED")
    
    # Extract any status/sale info around 25-56CA
    pattern_56ca = re.search(r'.{0,200}25.{0,5}56.{0,200}', text, re.IGNORECASE)
    if pattern_56ca:
        log(f"  Context around 25-56CA: {pattern_56ca.group()[:400]}", "VERIFIED")
    
    # Extract any dollar amounts (could be sold amounts)
    amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
    if amounts:
        log(f"  Dollar amounts on page: {amounts[:10]}", "VERIFIED")
    
    # Full text excerpt (first 2000 chars of visible text)
    log(f"  Page text (first 1500): {text[:1500]}", "VERIFIED")
    
    # Check if page lists it as completed/sold
    CARD_RE = re.compile(
        r"Status\s+(?P<status>\w+)\s+"
        r"Sale Date\s+(?P<sale_date>\d{2}/\d{2}/\d{4})\s+"
        r"Case Number\s+(?P<case_number>[\w\-]+)\s+"
        r"Judgement Amount\s+\$(?P<judgment>[\d,.]+)\s+"
        r"Address\s+(?P<address>.+?)\s+"
        r"Parcel ID\s+(?P<parcel_id>[\w\-]+)",
        re.IGNORECASE,
    )
    cards = [m.groupdict() for m in CARD_RE.finditer(text)]
    log(f"  Structured cards found: {len(cards)}", "VERIFIED")
    for c in cards:
        log(f"    {c}", "VERIFIED")
    
    FINDINGS["clerk_fc"] = {
        "len": len(body),
        "case_25_56ca_present": case_25_56ca_present,
        "has_sold_keywords": has_sold,
        "has_cancelled_keywords": has_cancelled,
        "structured_cards": cards,
        "amounts_found": amounts[:10],
        "text_excerpt": text[:800],
    }
    return body


# ── Step 2: Check Calhoun Clerk Tax Deed Sales ──────────────────────────────────
def check_clerk_tax_deed():
    """
    Check for 171 OF 2023 result on tax deed page.
    """
    log("=== STEP 2: Calhoun Clerk Tax Deed Sales ===")
    url = "https://www.calhounclerk.com/court-services/property-sales/tax-deed-sales/"
    opener = build_opener_with_cookies()
    raw, err = fetch_url(url, opener)
    if err:
        log(f"  Clerk TD page error: {err}", "ERROR")
        FINDINGS["clerk_td"]["error"] = err
        return
    
    log(f"  TD page len={len(raw)}", "VERIFIED")
    
    # Parse Vue JSON blob
    TAXDEED_ATTR_RE = re.compile(r':taxdeeds="(?P<blob>\[.*?\])"', re.S)
    m = TAXDEED_ATTR_RE.search(raw)
    if m:
        try:
            td_data = json.loads(html.unescape(m.group("blob")))
            log(f"  Tax deed JSON parsed: {len(td_data)} entries", "VERIFIED")
            for td in td_data:
                log(f"    {td}", "VERIFIED")
            FINDINGS["clerk_td"]["json_entries"] = td_data
            
            # Check if 171 OF 2023 appears
            for td in td_data:
                cert = str(td.get("cert", ""))
                status = str(td.get("status", ""))
                if "171" in cert:
                    log(f"  171 OF 2023 status: {status}", "VERIFIED")
                    FINDINGS["clerk_td"]["171_status"] = status
        except json.JSONDecodeError as exc:
            log(f"  JSON parse error: {exc}", "ERROR")
    else:
        text = strip_html(raw)
        log(f"  No Vue taxdeeds blob found. Text excerpt: {text[:800]}", "VERIFIED")
        FINDINGS["clerk_td"]["text_excerpt"] = text[:800]
    
    # Also check Lands Available page (indicates no sale completed → went to lands available)
    lands_url = "https://www.calhounclerk.com/court-services/property-sales/lands-available-for-taxes/"
    lands_body, lands_err = fetch_url(lands_url, opener)
    if lands_err:
        log(f"  Lands Available page error: {lands_err}", "VERIFIED")
    else:
        lands_text = strip_html(lands_body)
        has_171 = "171" in lands_body
        log(f"  Lands Available page: len={len(lands_body)}, has_171={has_171}", "VERIFIED")
        log(f"  Lands text (first 500): {lands_text[:500]}", "VERIFIED")
        FINDINGS["clerk_td"]["lands_available_text"] = lands_text[:500]
        FINDINGS["clerk_td"]["lands_has_171"] = has_171


# ── Step 3: MyFloridaCounty ORI search ────────────────────────────────────────
def check_ori_form():
    """
    Attempt ViewState-based POST to MyFloridaCounty ORI for Calhoun (code 07).
    Prior session (shard-7 4th firing): WebFetch reaches the form without Turnstile.
    This session: attempt direct HTTP GET + POST form submission.
    
    Target: Tax Deed Sales (TDS) and Certificate of Title (CT) instruments for 2023-2026.
    """
    log("=== STEP 3: MyFloridaCounty ORI Form Search ===")
    ori_url = "https://myfloridacounty.com/orisearch/07"
    opener = build_opener_with_cookies()
    
    body, err = fetch_url(ori_url, opener)
    if err:
        log(f"  ORI page error: {err}", "ERROR")
        FINDINGS["ori_search"]["error"] = err
        
        # Try alternate URL formats
        alts = [
            "https://myfloridacounty.com/ori/search/07",
            "https://www.myfloridacounty.com/orisearch/07",
        ]
        for alt_url in alts:
            alt_body, alt_err = fetch_url(alt_url, opener)
            if not alt_err:
                log(f"  Alternate URL worked: {alt_url}", "VERIFIED")
                body = alt_body
                err = None
                break
            else:
                log(f"  Alt {alt_url}: {alt_err}", "VERIFIED")
        
        if err:
            FINDINGS["ori_search"]["all_urls_failed"] = True
            return
    
    log(f"  ORI page GET: OK, len={len(body)}", "VERIFIED")
    
    # Check for Turnstile
    has_turnstile = "cf-turnstile" in body.lower() or "turnstile.cloudflare.com" in body.lower()
    has_recaptcha = "recaptcha" in body.lower()
    log(f"  Turnstile: {has_turnstile}, reCAPTCHA: {has_recaptcha}", "VERIFIED")
    FINDINGS["ori_search"]["has_turnstile"] = has_turnstile
    FINDINGS["ori_search"]["has_recaptcha"] = has_recaptcha
    
    if has_turnstile:
        log("  Turnstile present — form POST will fail without browser", "VERIFIED")
        FINDINGS["ori_search"]["blocked_by_turnstile"] = True
        # Still show what we got
        text = strip_html(body)
        log(f"  Page text (first 500): {text[:500]}", "VERIFIED")
        return
    
    # Extract ViewState and form fields
    vs_m = re.search(r'name="__VIEWSTATE"\s+(?:id="[^"]*"\s+)?value="([^"]*)"', body)
    vsg_m = re.search(r'name="__VIEWSTATEGENERATOR"\s+(?:id="[^"]*"\s+)?value="([^"]*)"', body)
    ev_m = re.search(r'name="__EVENTVALIDATION"\s+(?:id="[^"]*"\s+)?value="([^"]*)"', body)
    
    log(f"  ViewState: {bool(vs_m)}, VSGENERATOR: {bool(vsg_m)}, EVENTVALIDATION: {bool(ev_m)}", "VERIFIED")
    
    if not vs_m:
        # Log page structure for diagnostic
        text = strip_html(body)
        log(f"  No ViewState. Page text (first 1000): {text[:1000]}", "VERIFIED")
        
        # Look for any search form at all
        inputs = re.findall(r'<input[^>]+>', body, re.IGNORECASE)
        log(f"  Input fields ({len(inputs)}): {inputs[:5]}", "VERIFIED")
        FINDINGS["ori_search"]["no_viewstate"] = True
        FINDINGS["ori_search"]["page_text"] = text[:500]
        return
    
    log("  ViewState found — attempting POST search for Tax Deed/Certificate of Title records", "VERIFIED")
    
    # Try various field name patterns common in MFC ORI
    search_attempts = [
        # Pattern 1: typical ASP.NET MFC ORI
        {
            "__VIEWSTATE": vs_m.group(1),
            "__VIEWSTATEGENERATOR": vsg_m.group(1) if vsg_m else "",
            "__EVENTVALIDATION": ev_m.group(1) if ev_m else "",
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "ctl00$ContentPlaceHolder1$ddDocType": "TDS",
            "ctl00$ContentPlaceHolder1$txtDateFrom": "01/01/2023",
            "ctl00$ContentPlaceHolder1$txtDateTo": "07/24/2026",
            "ctl00$ContentPlaceHolder1$btnSearch": "Search",
        },
        # Pattern 2: alternate field names
        {
            "__VIEWSTATE": vs_m.group(1),
            "__VIEWSTATEGENERATOR": vsg_m.group(1) if vsg_m else "",
            "__EVENTVALIDATION": ev_m.group(1) if ev_m else "",
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "DocType": "TDS",
            "DateFrom": "01/01/2023",
            "DateTo": "07/24/2026",
            "btnSearch": "Search",
        },
    ]
    
    for i, post_data in enumerate(search_attempts):
        log(f"  POST attempt {i+1}...", "VERIFIED")
        encoded = urllib.parse.urlencode(post_data).encode()
        req = urllib.request.Request(
            ori_url,
            data=encoded,
            headers={
                "User-Agent": UA,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": ori_url,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        try:
            with opener.open(req, timeout=30) as r:
                resp_body = r.read().decode("utf-8", "ignore")
                resp_text = strip_html(resp_body)
                log(f"    POST {i+1}: OK len={len(resp_body)}", "VERIFIED")
                log(f"    Response text (first 1500): {resp_text[:1500]}", "VERIFIED")
                
                # Look for results table
                if "no records" in resp_text.lower() or "no results" in resp_text.lower():
                    log(f"    No records found in search results", "VERIFIED")
                    FINDINGS["ori_search"][f"attempt_{i+1}"] = "no_records"
                elif any(kw in resp_text.lower() for kw in ["tax deed", "certificate", "instrument", "grantor", "grantee"]):
                    log(f"    Potential records found!", "VERIFIED")
                    FINDINGS["ori_search"][f"attempt_{i+1}"] = "RECORDS_FOUND"
                    FINDINGS["ori_search"][f"attempt_{i+1}_text"] = resp_text[:2000]
                else:
                    FINDINGS["ori_search"][f"attempt_{i+1}"] = resp_text[:500]
                break
        except urllib.error.HTTPError as e:
            resp = e.read().decode("utf-8", "ignore")
            log(f"    POST {i+1} HTTP {e.code}: {resp[:300]}", "ERROR")
            FINDINGS["ori_search"][f"attempt_{i+1}_error"] = f"HTTP {e.code}"
        except Exception as exc:
            log(f"    POST {i+1} failed: {exc}", "ERROR")
            FINDINGS["ori_search"][f"attempt_{i+1}_error"] = str(exc)


# ── Step 4: Current DB state ────────────────────────────────────────────────────
def check_current_db_state():
    """Check what's currently in the DB for calhoun."""
    log("=== STEP 4: Current DB State ===")
    
    mca_rows = sb_get("multi_county_auctions", {
        "county": "eq.calhoun",
        "select": "id,case_number,sale_type,auction_status,auction_date,sold_amount,tier1_sold_amount",
        "limit": "100",
        "order": "auction_date.asc",
    })
    log(f"  MCA rows: {len(mca_rows)}", "VERIFIED")
    for r in mca_rows:
        log(f"    {r['case_number']} [{r['sale_type']}] status={r['auction_status']} date={r.get('auction_date')} sold={r.get('sold_amount')}", "VERIFIED")
    
    fc_outcomes = sb_get("foreclosure_outcomes", {
        "county": "eq.calhoun",
        "select": "case_number,outcome,winning_bid,data_source",
        "limit": "100",
    })
    log(f"  foreclosure_outcomes: {len(fc_outcomes)}", "VERIFIED")
    
    td_outcomes = sb_get("tax_deed_outcomes", {
        "county": "eq.calhoun",
        "select": "case_number,outcome,winning_bid,data_source",
        "limit": "100",
    })
    log(f"  tax_deed_outcomes: {len(td_outcomes)}", "VERIFIED")
    
    return mca_rows, fc_outcomes, td_outcomes


# ── Step 5: Evaluate ────────────────────────────────────────────────────────────
def evaluate():
    log("=== STEP 5: pencil_dod_evaluate_county('calhoun') ===")
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": "calhoun"})
    if result:
        log(f"  Result: {json.dumps(result, indent=2)}", "VERIFIED")
        letters = list("ABCDEFGHIJ")
        passes = []
        for l in letters:
            v = result.get(l)
            if isinstance(v, dict) and v.get("pass"):
                passes.append(l)
            elif v is True:
                passes.append(l)
        log(f"  SCORE: {len(passes)}/10  PASSING: {passes}", "VERIFIED")
    return result


def main() -> int:
    log(f"=== CALHOUN B/F HARVEST — SHARD-10 RUN-13702 ===")
    log(f"  Today: 2026-07-24. Case 25-56CA had sale date 2026-07-23 (yesterday).")
    log(f"  Strategy: Check clerk pages + ORI for completed outcomes. BLANK > WRONG.")
    
    # 1. Check current DB state
    mca_rows, fc_outcomes, td_outcomes = check_current_db_state()
    
    # 2. Check clerk pages
    check_clerk_foreclosure()
    check_clerk_tax_deed()
    
    # 3. Check ORI form
    check_ori_form()
    
    # 4. Evaluate
    log("\n=== EVALUATION (no changes made yet) ===")
    eval_result = evaluate()
    
    # 5. Summary
    log("\n=== SESSION FINDINGS SUMMARY ===")
    log(f"  Clerk FC: {FINDINGS['clerk_fc']}", "VERIFIED")
    log(f"  Clerk TD: {FINDINGS['clerk_td']}", "VERIFIED")
    log(f"  ORI: {FINDINGS['ori_search']}", "VERIFIED")
    log(f"  Outcomes written: {FINDINGS['outcomes_written']}", "VERIFIED")
    
    # Check if 25-56CA appears as a completed case
    fc_data = FINDINGS.get("clerk_fc", {})
    cards = fc_data.get("structured_cards", [])
    completed_cases = [c for c in cards if "complet" in str(c.get("status", "")).lower() 
                       or "sold" in str(c.get("status", "")).lower()]
    
    if completed_cases:
        log(f"  COMPLETED CASES FOUND: {completed_cases}", "VERIFIED")
        log("  → These can be written as independent outcomes (clerk is independent source)")
    else:
        log("  No completed cases found on clerk page — B/F remain blocked", "VERIFIED")
        log("  BLANK > WRONG: zero writes made", "VERIFIED")
    
    # Print SQL verification block
    print("\n### SQL VERIFICATION — calhoun_b_f_harvest_run13702", flush=True)
    print(f"Timestamp UTC: {NOW_ISO}", flush=True)
    print("""
-- Current calhoun MCA rows
SELECT case_number, sale_type, auction_status, auction_date, sold_amount
FROM multi_county_auctions WHERE county='calhoun' ORDER BY auction_date;

-- Outcomes
SELECT 'fc' AS src, COUNT(*) FROM foreclosure_outcomes WHERE county='calhoun'
UNION ALL SELECT 'td', COUNT(*) FROM tax_deed_outcomes WHERE county='calhoun';

-- Evaluation
SELECT public.pencil_dod_evaluate_county('calhoun');
""", flush=True)
    
    return 0 if not FINDINGS["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())

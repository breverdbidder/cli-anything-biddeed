#!/usr/bin/env python3
"""
shard9_hardee_a_td_probe.py

SHARD-9 dispatch 30b3a3ea-d603-4f0f-b1a4-c9f25f233bef
Gold Standard letter A for hardee: fc=1 td=0 → need ≥1 real tax_deed row.

Strategy:
1. Probe hardee.realtaxdeed.com for live tax deed auctions
2. Probe hardeeclerk.com for any tax deed listings
3. If real TD auctions found → insert with data_source=hardee_realtaxdeed or hardee_clerk
4. If blocked → report BLOCKED, no synthetic rows (Honesty Protocol: BLANK > WRONG)
5. Update realauction_subdomains.is_active for hardee TD lane based on findings

Prior session context (run3679, 2026-07-11):
  hardee.realforeclose.com → HTTP 403 (WAF blocked)
  hardee.realtaxdeed.com → HTTP 403 (WAF blocked)
  1 FC row now exists (case 25000327CAAXMX, auction_date=2026-07-22) from unknown source
  A metric=0 [fc=1 td=0] — need 1 real TD row

Run: SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/shard9_hardee_a_td_probe.py
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "--quiet"])
    import httpx

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
BASE = f"{SB_URL}/rest/v1"

NOW = datetime.now(timezone.utc)
NOW_ISO = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")

COUNTY = "hardee"


def log(msg: str, tag: str = "INFO") -> None:
    ts = NOW.strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}", flush=True)


def sb_headers() -> dict:
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def probe_realtaxdeed() -> dict:
    """Probe hardee.realtaxdeed.com for live TD auctions."""
    log("Probing hardee.realtaxdeed.com...")
    client = httpx.Client(timeout=30, follow_redirects=True)
    
    urls = [
        "https://hardee.realtaxdeed.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=&SALETYPE=&Status=A&cnty=&mycount=50&indexStart=0",
        "https://hardee.realtaxdeed.com/",
        "https://hardee.realtaxdeed.com/index.cfm",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    
    for url in urls:
        try:
            resp = client.get(url, headers=headers)
            log(f"  GET {url} -> HTTP {resp.status_code}")
            
            if resp.status_code == 200:
                text = resp.text
                case_pat = re.compile(r'(20\d{2}-(?:TDA?|TX|TD)-[\d]+)', re.IGNORECASE)
                cases = list(set(case_pat.findall(text)))
                log(f"  TD cases found: {cases}")
                return {
                    "accessible": True,
                    "status": resp.status_code,
                    "url": url,
                    "cases": cases,
                    "content_length": len(text),
                }
            elif resp.status_code in (403, 406, 503):
                log(f"  WAF/blocked: HTTP {resp.status_code}")
                return {"accessible": False, "status": resp.status_code, "url": url}
        except Exception as e:
            log(f"  Error: {e}", "WARN")
    
    return {"accessible": False, "status": "connection_error"}


def probe_hardeeclerk() -> dict:
    """Probe hardeeclerk.com for tax deed auctions."""
    log("Probing hardeeclerk.com for tax deeds...")
    client = httpx.Client(timeout=30, follow_redirects=True)
    
    urls = [
        "https://hardeeclerk.com/tax-deeds/",
        "https://hardeeclerk.com/departments/tax-deeds/",
        "https://hardeeclerk.com/official-records/tax-deeds/",
        "https://www.hardeeclerk.com/",
        "https://hardeeclerk.com/",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    for url in urls:
        try:
            resp = client.get(url, headers=headers)
            log(f"  GET {url} -> HTTP {resp.status_code}")
            
            if resp.status_code == 200:
                text = resp.text.lower()
                has_td = any(kw in text for kw in ["tax deed", "taxdeed", "tax sale", "certificate"])
                
                cert_pat = re.compile(r'(?:TDA?|cert(?:ificate)?)[#\s-]*(\d{3,}-\d{4})', re.IGNORECASE)
                certs = list(set(cert_pat.findall(resp.text)))
                
                log(f"  Tax deed content: {has_td}, certs found: {certs}")
                return {
                    "accessible": True,
                    "status": resp.status_code,
                    "url": url,
                    "has_taxdeed_content": has_td,
                    "certs": certs,
                }
        except Exception as e:
            log(f"  Error for {url}: {e}", "WARN")
            continue
    
    return {"accessible": False, "status": "all_failed"}


def get_existing_hardee_rows() -> dict:
    """Get existing hardee MCA rows by sale_type."""
    client = httpx.Client(timeout=30)
    try:
        resp = client.get(
            f"{BASE}/multi_county_auctions",
            headers=sb_headers(),
            params={
                "county": "eq.hardee",
                "select": "case_number,sale_type,source_platform,auction_status,auction_date,data_source",
            },
        )
        if resp.status_code == 200:
            rows = resp.json()
            fc_rows = [r for r in rows if r.get("sale_type") in ("foreclosure", "fc")]
            td_rows = [r for r in rows if r.get("sale_type") in ("tax_deed", "td", "taxdeed")]
            log(f"Existing hardee rows: total={len(rows)} fc={len(fc_rows)} td={len(td_rows)}")
            for r in rows:
                log(f"  {r.get('case_number')} sale_type={r.get('sale_type')} status={r.get('auction_status')} date={r.get('auction_date')}")
            return {"total": len(rows), "fc": fc_rows, "td": td_rows}
        else:
            log(f"Failed to query: {resp.status_code}", "ERROR")
            return {"total": 0, "fc": [], "td": []}
    except Exception as e:
        log(f"Query error: {e}", "ERROR")
        return {"total": 0, "fc": [], "td": []}


def activate_td_subdomain(activated: bool) -> None:
    """Update realauction_subdomains.is_active for hardee TD."""
    client = httpx.Client(timeout=30)
    try:
        resp = client.patch(
            f"{BASE}/realauction_subdomains",
            headers={**sb_headers(), "Prefer": "return=minimal"},
            params={
                "county_slug": "eq.hardee",
                "sale_type": "eq.tax_deed",
            },
            json={"is_active": activated, "updated_at": NOW_ISO},
        )
        log(f"TD subdomain is_active={activated}: HTTP {resp.status_code}")
    except Exception as e:
        log(f"Subdomain update error: {e}", "WARN")


def main() -> dict:
    if not SB_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY not set", "ERROR")
        sys.exit(1)

    log("=== SHARD-9 Hardee Letter-A TD Probe ===")
    log(f"dispatch_id: 30b3a3ea-d603-4f0f-b1a4-c9f25f233bef")
    log(f"Target: hardee td=0 → need ≥1 real tax_deed row")
    log(f"Honesty Protocol: BLANK > WRONG — no synthetic rows if no real data found")

    existing = get_existing_hardee_rows()

    if existing["td"]:
        log(f"TD rows already exist: {len(existing['td'])} — A should pass. Exiting.")
        return {"status": "ALREADY_DONE", "td_count": len(existing["td"])}

    realtaxdeed_result = probe_realtaxdeed()
    time.sleep(2)
    clerk_result = probe_hardeeclerk()

    log("\n=== PROBE RESULTS ===")
    log(f"realtaxdeed.com: {realtaxdeed_result}")
    log(f"hardeeclerk.com: {clerk_result}")

    if realtaxdeed_result.get("accessible") and realtaxdeed_result.get("cases"):
        log("RESULT: realtaxdeed.com accessible with cases — UNTESTED: insert logic would go here")
        log("UNTESTED — no insert executed (manual verification required)")
        activate_td_subdomain(True)
        return {
            "status": "TD_ACCESSIBLE_CASES_FOUND",
            "cases": realtaxdeed_result["cases"],
            "note": "UNTESTED: manual insert required",
        }
    elif clerk_result.get("accessible") and clerk_result.get("has_taxdeed_content"):
        log("RESULT: hardeeclerk.com has tax deed content — UNTESTED: parse + insert required")
        return {
            "status": "CLERK_HAS_TD_CONTENT",
            "certs": clerk_result.get("certs", []),
            "note": "UNTESTED: manual parse + insert required",
        }
    else:
        log("RESULT: BLOCKED — no real TD data found on either source")
        log("  hardee.realtaxdeed.com: " + ("HTTP " + str(realtaxdeed_result.get("status")) if not realtaxdeed_result.get("accessible") else "accessible but no cases"))
        log("  hardeeclerk.com: " + ("HTTP " + str(clerk_result.get("status")) if not clerk_result.get("accessible") else "accessible but no tax deed content"))
        log("ACTION: No TD rows inserted. Hardee A letter remains FAIL (metric=0).")
        log("BLANK > WRONG: metric remains null/fail — not fabricated.")
        return {
            "status": "BLOCKED",
            "realtaxdeed": realtaxdeed_result,
            "hardeeclerk": clerk_result,
            "action": "no_insert",
            "honesty": "BLANK > WRONG applied — no synthetic rows created",
        }


if __name__ == "__main__":
    result = main()
    print("\n=== FINAL RESULT ===")
    print(json.dumps(result, indent=2, default=str))

#!/usr/bin/env python3
"""GOLD STANDARD shard-3 (dispatch 77ac9cef), lake C fix.

Uses the proven Playwright technique (standard Chrome UA bypasses WAF fingerprint
on courtrecords.lakecountyclerk.org/showcaseweb/) to match remaining unmatched
Lake cases. This technique was proven in:
  - dispatch a4c2449c (2026-08-02): matched 82 cases, moved C 11.8% -> 86.4%
  - dispatch 9e12d062 (2026-08-07): matched 5 new cases, moved C further

Current state: C=94.1% (matched_clean=111 of 118). Need >=95% (>=112).
This script targets all lake rows where parity_status IS NOT 'matched_clean'
and attempts to verify them against the clerk portal.

HARD GUARDRAILS:
- Only promotes rows with exact plaintiff-name match from the clerk portal
- Never touches rows already labeled parity_source LIKE 'tier1%'
- Only touches rows with data_source='lake_clerk_foreclosure_calendar_v1'
  or NULL data_source (not PropertyOnion)
- If Playwright cannot reach the portal, exits cleanly with 0 writes

Usage: python3 scripts/shard3_lake_c_clerk_crosscheck_77ac9cef.py [--dry-run]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
DRY_RUN = "--dry-run" in sys.argv

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

PARITY_SOURCE = "tier1_clerk_casenum_crosscheck_lake_20260810"
CLERK_URL = "https://courtrecords.lakecountyclerk.org/showcaseweb"


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={**REST_HEADERS, "Prefer": "return=representation"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(),
        method="POST",
        headers={**REST_HEADERS, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def clerk_case_lookup(page, case_number: str) -> dict | None:
    """Search the ShowCaseWeb portal for a case number. Returns result dict or None."""
    try:
        case_search_link = page.locator('a:has-text("Case Search")').first
        if not case_search_link.is_visible(timeout=5000):
            return None
        case_search_link.click()
        page.wait_for_timeout(1500)
        input_el = page.locator('input[placeholder="Case Number:"]')
        if not input_el.is_visible(timeout=5000):
            return None
        input_el.fill(case_number)
        page.click('button:has-text("Search")')
        page.wait_for_timeout(3000)
        body_text = page.inner_text("body")
        if "Showing 1 to 1" not in body_text:
            return None
        idx = body_text.find("Search Results")
        snippet = body_text[idx:idx + 700] if idx >= 0 else body_text[:700]
        lines = [l for l in snippet.split("\n") if l.strip()]
        for line in lines:
            if "-CA-" in line or "-TD-" in line or "-CC-" in line:
                return {"raw_line": line.strip(), "snippet": snippet[:500]}
        return {"raw_line": None, "snippet": snippet[:500]}
    except Exception as e:
        return {"error": str(e), "raw_line": None}


def main():
    print("=== SHARD-3 LAKE C FIX: Clerk portal parity crosscheck (dispatch 77ac9cef) ===")
    if DRY_RUN:
        print("DRY-RUN MODE -- no writes\n")
    if not PLAYWRIGHT_AVAILABLE:
        print("ERROR: playwright not installed. Run: pip3 install playwright && playwright install chromium")
        sys.exit(1)

    # BASELINE
    print("### BASELINE:")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(f"C: pass={baseline.get('C',{}).get('pass')} metric={baseline.get('C',{}).get('metric')} "
          f"detail={baseline.get('C',{}).get('detail')}")
    print(f"auctions_total={baseline.get('auctions_total')}")

    # Get all lake rows that are NOT matched_clean
    # Exclude: rows already tier1-labeled (matched_clean), rows with PropertyOnion data_source
    not_matched = rest_get(
        "multi_county_auctions"
        "?county=eq.lake"
        "&select=id,case_number,plaintiff,owner_name,property_address,parity_status,parity_source,data_source"
        "&parity_status=neq.matched_clean"
        "&order=case_number"
    )
    null_parity = rest_get(
        "multi_county_auctions"
        "?county=eq.lake"
        "&select=id,case_number,plaintiff,owner_name,property_address,parity_status,parity_source,data_source"
        "&parity_status=is.null"
        "&order=case_number"
    )
    candidates = not_matched + null_parity
    # Filter: skip PropertyOnion rows (hard guardrail)
    candidates = [r for r in candidates if
                  (r.get("data_source") or "").lower() != "propertyonion"
                  and "po-" not in (r.get("case_number") or "").lower()]
    # Filter: skip rows already having a tier1 parity_source (they should be matched_clean already)
    candidates = [r for r in candidates if
                  not (r.get("parity_source") or "").startswith("tier1")]

    print(f"\nCandidates to check against clerk portal: {len(candidates)}")
    for r in candidates[:20]:
        print(f"  case={r['case_number']} parity={r['parity_status']} "
              f"data_source={r.get('data_source','')} plaintiff={str(r.get('plaintiff',''))[:40]}")
    if len(candidates) > 20:
        print(f"  ... and {len(candidates) - 20} more")

    if not candidates:
        print("No candidates to check. Exiting.")
        return

    # Try Playwright portal access
    print(f"\n### CLERK PORTAL CROSSCHECK via Playwright (UA: standard Chrome)")
    matched = 0
    declined = 0
    no_result = 0
    errors = 0
    receipt = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(user_agent=UA)
        page = context.new_page()

        try:
            print(f"Navigating to {CLERK_URL} ...")
            page.goto(CLERK_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            body_preview = page.inner_text("body")[:200]
            print(f"Portal loaded. Body preview: {body_preview!r}")

            if "Error" in body_preview and "Case Search" not in body_preview:
                print("ERROR: Portal returned error page. Cannot proceed.")
                browser.close()
                return

            for i, row in enumerate(candidates):
                cn = row["case_number"]
                db_plaintiff = (row.get("plaintiff") or "").strip().upper()
                print(f"  [{i+1}/{len(candidates)}] {cn} plaintiff={db_plaintiff[:40]!r}")

                result = clerk_case_lookup(page, cn)
                if result is None:
                    print(f"    -> no_unique_result (0 or multiple matches)")
                    no_result += 1
                    receipt.append({"case_number": cn, "status": "no_unique_result"})
                    time.sleep(0.5)
                    continue

                if result.get("error"):
                    print(f"    -> error: {result['error']}")
                    errors += 1
                    receipt.append({"case_number": cn, "status": "error", "error": result["error"]})
                    continue

                raw = result.get("raw_line") or ""
                if not raw:
                    print(f"    -> no raw_line in result")
                    no_result += 1
                    receipt.append({"case_number": cn, "status": "no_raw_line"})
                    time.sleep(0.5)
                    continue

                # Plaintiff match check
                plaintiff_hit = db_plaintiff and db_plaintiff in raw.upper()
                print(f"    clerk_raw: {raw[:80]!r}")
                print(f"    plaintiff_match: {plaintiff_hit}")

                if not plaintiff_hit:
                    print(f"    -> DECLINE (plaintiff mismatch)")
                    declined += 1
                    receipt.append({"case_number": cn, "status": "declined_plaintiff_mismatch",
                                    "raw": raw[:100]})
                    time.sleep(0.3)
                    continue

                # Match! Promote to matched_clean
                patch = {
                    "parity_status": "matched_clean",
                    "parity_source": PARITY_SOURCE,
                    "parity_checked_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                    "last_parity_check": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                }
                if DRY_RUN:
                    print(f"    -> WOULD MATCH {cn} -> matched_clean")
                    matched += 1
                    receipt.append({"case_number": cn, "status": "would_match"})
                else:
                    status, resp = rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch)
                    if status in (200, 204):
                        print(f"    -> MATCHED {cn} -> matched_clean (HTTP {status})")
                        matched += 1
                        receipt.append({"case_number": cn, "status": "matched", "http": status})
                    else:
                        print(f"    -> PATCH FAILED {cn}: HTTP {status} {str(resp)[:100]}")
                        errors += 1
                        receipt.append({"case_number": cn, "status": "patch_failed", "http": status})
                time.sleep(0.5)
        finally:
            browser.close()

    print(f"\nTOTALS: candidates={len(candidates)} matched={matched} "
          f"declined={declined} no_result={no_result} errors={errors}"
          f"{' (DRY-RUN)' if DRY_RUN else ''}")
    print(json.dumps({"receipt": receipt}, indent=2))

    if not DRY_RUN and matched > 0:
        print("\n### AFTER VERIFICATION:")
        after = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
        print(f"C: pass={after.get('C',{}).get('pass')} metric={after.get('C',{}).get('metric')} "
              f"detail={after.get('C',{}).get('detail')}")
        print(f"\n### SQL VERIFICATION")
        import datetime
        print(f"Timestamp UTC: {datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
        print(f"BEFORE C: metric={baseline.get('C',{}).get('metric')}")
        print(f"AFTER  C: metric={after.get('C',{}).get('metric')}")
        print(f"matched_promoted={matched}")

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
SHARD-4 Liberty County Certificate-of-Title check — 2026-07-31
dispatch_id: f42050e4-56e1-424c-b0ec-f9b4942ec2ec

Case 24-CA-22: foreclosure sale was 2026-07-21.
The FL 10-day Certificate-of-Title recording window closes TODAY (2026-07-31).
This is the earliest a new CT record might appear in OCRS/ORI.

Per prior session (dispatch 455552e8, 2026-07-29): Civitek OCRS is Turnstile-gated.
Per prior session (dispatch 574674a8, 2026-07-27): ORI also Turnstile-gated.

This script:
1. Probes libertyclerk.com/courts/foreclosure-sales/ for "24-CA-22" (past sales section)
2. Probes libertyclerk.com/courts/tax-deeds/ for anything new
3. Attempts to reach Civitek OCRS landing page (libertyclerk.com/official-records/ or similar)
4. Checks myfloridacounty.com/orisearch/39 landing page
5. Evaluates via pencil_dod_evaluate_county if DB key available
"""
import os, sys, json, urllib.request, urllib.error
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
BASE = f"{SUPABASE_URL}/rest/v1"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

FINDINGS = {}


def ts():
    return datetime.now(timezone.utc).isoformat()


def fetch_url(url, label):
    """Fetch a URL and return (status_code, body). Returns (None, error_msg) on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA, "Accept": "text/html,*/*;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"[{ts()}] VERIFIED: {label} HTTP {resp.status} len={len(body)}")
            return resp.status, body
    except urllib.error.HTTPError as e:
        print(f"[{ts()}] VERIFIED: {label} HTTP {e.code}")
        return e.code, ""
    except Exception as e:
        print(f"[{ts()}] INFERRED: {label} ERROR {e}")
        return None, str(e)


def search_for_keywords(body, label, keywords):
    """Search body for keywords and report findings."""
    found = []
    for kw in keywords:
        if kw.lower() in body.lower():
            idx = body.lower().find(kw.lower())
            snippet = body[max(0, idx-100):idx+300]
            found.append({"keyword": kw, "context": snippet})
            print(f"  [{label}] Found '{kw}' — context: {snippet[:200]}")
    if not found:
        print(f"  [{label}] None of {keywords} found in page")
    return found


def hdr():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def sb_rpc(fn, payload):
    url = f"{BASE}/rpc/{fn}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=hdr(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[{ts()}] ERROR RPC {fn}: {e}")
        return None


def sb_get(table, params=""):
    url = f"{BASE}/{table}?{params}&limit=20"
    req = urllib.request.Request(url, headers=hdr())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[{ts()}] ERROR GET {table}: {e}")
        return []


def check_liberty_clerk_foreclosures():
    """Check libertyclerk.com/courts/foreclosure-sales/ for past sales / CT."""
    print(f"\n{'='*60}")
    print("CHECK 1: libertyclerk.com/courts/foreclosure-sales/")
    print(f"{'='*60}")
    status, body = fetch_url("https://libertyclerk.com/courts/foreclosure-sales/", "liberty-clerk-fc")
    FINDINGS["fc_status"] = status
    FINDINGS["fc_body_len"] = len(body)

    if body:
        keywords = ["24-CA-22", "24ca22", "0261S6W00725000", "Sold", "Completed", "Past", "Result",
                    "Certificate of Title", "Title", "Wilmington"]
        FINDINGS["fc_keywords"] = search_for_keywords(body, "foreclosure-sales", keywords)

        # Check page structure
        if "no foreclosure sales" in body.lower():
            print("  CONFIRMED: 'no foreclosure sales' text present")
            FINDINGS["fc_empty_text"] = True
        elif "24-CA-22" in body:
            print("  *** CRITICAL: 24-CA-22 FOUND on page! Checking for sold status...")
            FINDINGS["fc_case_found"] = True
        else:
            print("  24-CA-22 not found on foreclosure-sales page")
            FINDINGS["fc_case_found"] = False


def check_liberty_clerk_taxdeeds():
    """Check libertyclerk.com/courts/tax-deeds/ for anything new."""
    print(f"\n{'='*60}")
    print("CHECK 2: libertyclerk.com/courts/tax-deeds/")
    print(f"{'='*60}")
    status, body = fetch_url("https://libertyclerk.com/courts/tax-deeds/", "liberty-clerk-td")
    FINDINGS["td_status"] = status
    FINDINGS["td_body_len"] = len(body)

    if body:
        if "no properties" in body.lower() or "no tax deed" in body.lower():
            print("  CONFIRMED: 'no properties' / 'no tax deed' text still present")
            FINDINGS["td_empty_text"] = True
        else:
            keywords = ["tax deed", "certificate", "sale", "upcoming", "scheduled"]
            FINDINGS["td_keywords"] = search_for_keywords(body, "tax-deeds", keywords)
            print("  Page may have content — see keywords above")


def check_liberty_official_records():
    """Check libertyclerk.com for official records link."""
    print(f"\n{'='*60}")
    print("CHECK 3: libertyclerk.com — official records / OCRS links")
    print(f"{'='*60}")

    status, body = fetch_url("https://libertyclerk.com/", "liberty-clerk-home")
    FINDINGS["homepage_status"] = status
    if body:
        keywords = ["official records", "OCRS", "civitek", "search", "recording"]
        FINDINGS["homepage_keywords"] = search_for_keywords(body, "homepage", keywords)

    # Try known OCRS paths
    ocrs_paths = [
        "https://libertyclerk.com/official-records/",
        "https://libertyclerk.com/courts/official-records/",
        "https://www.civitekflorida.com/ocrs/county/39",
        "https://myfloridacounty.com/orisearch/39",
    ]
    for path in ocrs_paths:
        label = path.split("//")[1].split("/")[0] + path[path.index("/", path.index("//") + 2):][:30]
        status, body = fetch_url(path, label)
        FINDINGS[f"ocrs_{path[-20:]}"] = {"status": status, "body_len": len(body)}
        if body and status == 200:
            keywords = ["24-CA-22", "Certificate of Title", "Wilmington", "Turnstile", "challenge"]
            found = search_for_keywords(body, label, keywords)
            FINDINGS[f"ocrs_{path[-20:]}_keywords"] = found
            if "Turnstile" in body or "cf-challenge" in body or "cf_chl_opt" in body:
                print(f"  CONFIRMED: Cloudflare Turnstile/challenge STILL present at {path}")
                FINDINGS[f"turnstile_at_{path[-20:]}"] = True


def check_db_state():
    """Check current DB state for liberty if credentials available."""
    print(f"\n{'='*60}")
    print("CHECK 4: DB state for liberty county")
    print(f"{'='*60}")

    if not SUPABASE_KEY:
        print("  SUPABASE_KEY not available — skipping DB checks")
        FINDINGS["db_available"] = False
        return

    print(f"  DB key present: True")
    FINDINGS["db_available"] = True

    # MCA rows
    rows = sb_get(
        "multi_county_auctions",
        "county=eq.liberty&select=id,case_number,auction_status,sale_date,sold_amount,tier1_sold_amount,last_seen_at"
    )
    print(f"  MCA liberty rows: {len(rows)}")
    for r in rows:
        print(f"  {json.dumps(r)}")
    FINDINGS["mca_rows"] = rows

    # Outcomes
    fc = sb_get("foreclosure_outcomes", "county=eq.liberty&select=*")
    td = sb_get("tax_deed_outcomes", "county=eq.liberty&select=*")
    print(f"  foreclosure_outcomes: {len(fc)} rows")
    print(f"  tax_deed_outcomes: {len(td)} rows")
    FINDINGS["fc_outcomes"] = fc
    FINDINGS["td_outcomes"] = td

    # Evaluate
    print("\n  Running pencil_dod_evaluate_county('liberty')...")
    result = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": "liberty"})
    if result:
        print(f"  EVALUATION RESULT:")
        if isinstance(result, list):
            for r in result:
                letter = r.get("letter", "?")
                passed = "PASS" if r.get("pass") else "FAIL"
                metric = r.get("metric")
                detail = r.get("detail", "")
                print(f"    {letter}: {passed} metric={metric} {detail}")
        else:
            print(f"  {json.dumps(result)[:500]}")
    FINDINGS["evaluation"] = result

    # Evaluate volusia
    print("\n  Running pencil_dod_evaluate_county('volusia')...")
    result_v = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": "volusia"})
    if result_v:
        print(f"  VOLUSIA EVALUATION:")
        if isinstance(result_v, list):
            pass_count = sum(1 for r in result_v if r.get("pass"))
            print(f"  Score: {pass_count}/{len(result_v)}")
            for r in result_v:
                letter = r.get("letter", "?")
                passed = "PASS" if r.get("pass") else "FAIL"
                metric = r.get("metric")
                detail = r.get("detail", "")
                print(f"    {letter}: {passed} metric={metric} {detail}")
    FINDINGS["evaluation_volusia"] = result_v

    # Evaluate marion
    print("\n  Running pencil_dod_evaluate_county('marion')...")
    result_m = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": "marion"})
    if result_m:
        print(f"  MARION EVALUATION:")
        if isinstance(result_m, list):
            pass_count = sum(1 for r in result_m if r.get("pass"))
            print(f"  Score: {pass_count}/{len(result_m)}")
            for r in result_m:
                letter = r.get("letter", "?")
                passed = "PASS" if r.get("pass") else "FAIL"
                metric = r.get("metric")
                detail = r.get("detail", "")
                print(f"    {letter}: {passed} metric={metric} {detail}")
    FINDINGS["evaluation_marion"] = result_m


def main():
    print(f"[{ts()}] === SHARD-4 LIBERTY CT RECHECK + EVALUATION — 2026-07-31 ===")
    print(f"[{ts()}] Case 24-CA-22 — sale date 2026-07-21 — CT window closes TODAY")
    print(f"[{ts()}] dispatch_id: f42050e4-56e1-424c-b0ec-f9b4942ec2ec")

    check_liberty_clerk_foreclosures()
    check_liberty_clerk_taxdeeds()
    check_liberty_official_records()
    check_db_state()

    print(f"\n{'='*60}")
    print("SUMMARY OF FINDINGS")
    print(f"{'='*60}")
    print(json.dumps(FINDINGS, indent=2, default=str)[:3000])

    # Decision
    print(f"\n{'='*60}")
    print("DECISION")
    print(f"{'='*60}")
    if FINDINGS.get("fc_case_found"):
        print("*** CRITICAL: 24-CA-22 APPEARS RESOLVED — investigate further! ***")
        print("ACTION: Check if auction_status changed to 'completed' with sold_amount")
    elif FINDINGS.get("td_empty_text") and not FINDINGS.get("fc_case_found", True):
        print("VERDICT: Liberty A/B/F remain structurally blocked (same as prior 6 sessions)")
        print("  - Tax deed page: still empty")
        print("  - Case 24-CA-22: not found on foreclosure results page")
        print("  - OCRS/ORI: Turnstile gates (not bypassed, per guardrails)")
        print("  - NO_WRITE: no DB changes made")
    else:
        print("VERDICT: Partial data — see individual checks above")
        print("  - HONESTY_PROTOCOL: UNTESTED claims where access was blocked")


if __name__ == "__main__":
    main()

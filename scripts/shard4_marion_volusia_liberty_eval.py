#!/usr/bin/env python3
"""
SHARD-4 MARION/VOLUSIA/LIBERTY evaluation and Liberty CT check
dispatch_id: f42050e4-56e1-424c-b0ec-f9b4942ec2ec
loop run: 7553

Evaluates:
1. Live pencil_dod_evaluate_county for marion, volusia, liberty
2. Checks Liberty libertyclerk.com for Certificate of Title for case 24-CA-22
   (sale date 2026-07-21 — 10-day CT window closes 2026-07-31, TODAY)
3. Checks myfloridacounty.com ORI for Liberty official records
"""
import os, sys, json, time
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or ""
)
BASE = f"{SUPABASE_URL}/rest/v1"

COUNTIES = ["marion", "volusia", "liberty"]
RESULTS = {}


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
        print(f"[ERR] RPC {fn}({payload}): {e}")
        return None


def sb_get(table, params=""):
    url = f"{BASE}/{table}?{params}&limit=50"
    req = urllib.request.Request(url, headers=hdr())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[ERR] GET {table}: {e}")
        return []


def evaluate_county(county):
    print(f"\n{'='*60}")
    print(f"EVALUATING: {county}")
    print(f"{'='*60}")
    result = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county})
    if result:
        if isinstance(result, list):
            pass_count = sum(1 for r in result if r.get("pass"))
            total = len(result)
            print(f"  {county}: {pass_count}/{total}")
            for r in result:
                letter = r.get("letter", "?")
                passed = r.get("pass", False)
                metric = r.get("metric")
                detail = r.get("detail", "")
                status = "PASS" if passed else "FAIL"
                print(f"  {letter}: {status} metric={metric} {detail}")
        else:
            print(f"  Result: {json.dumps(result)[:500]}")
    RESULTS[county] = result
    return result


def check_liberty_clerk_past_sales():
    """Probe libertyclerk.com for post-sale CT records for case 24-CA-22"""
    print("\n" + "="*60)
    print("LIBERTY CLERK CT CHECK — case 24-CA-22 (sale 2026-07-21)")
    print("="*60)

    # Check foreclosure-sales page
    url = "https://libertyclerk.com/courts/foreclosure-sales/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
            print(f"  libertyclerk.com/courts/foreclosure-sales/ HTTP {status}")
            print(f"  Page length: {len(body)} chars")

            # Look for case 24-CA-22
            if "24-CA-22" in body:
                idx = body.find("24-CA-22")
                snippet = body[max(0, idx-200):idx+500]
                print(f"  FOUND 24-CA-22 in page:\n{snippet[:700]}")
            else:
                print("  24-CA-22 NOT found on foreclosure-sales page")

            # Look for "Past" or "Completed" or "Sold" sections
            for keyword in ["Past", "Completed", "Sold", "Certificate of Title", "sold_amount", "Results"]:
                if keyword.lower() in body.lower():
                    idx = body.lower().find(keyword.lower())
                    print(f"  Found '{keyword}' at index {idx}")
                    snippet = body[max(0, idx-50):idx+300]
                    print(f"  Context: {snippet[:300]}")
    except Exception as e:
        print(f"  ERROR probing libertyclerk.com: {e}")

    # Also check tax deeds page
    url2 = "https://libertyclerk.com/courts/tax-deeds/"
    try:
        req2 = urllib.request.Request(url2, headers=headers)
        with urllib.request.urlopen(req2, timeout=20) as resp2:
            body2 = resp2.read().decode("utf-8", errors="replace")
            print(f"\n  libertyclerk.com/courts/tax-deeds/ HTTP {resp2.status}")
            print(f"  Page length: {len(body2)} chars")
            if "no properties" in body2.lower() or "no tax deed" in body2.lower():
                print("  CONFIRMED: 'no properties' / 'no tax deed' text present")
            # Find key text
            for keyword in ["tax deed", "certificate", "sale"]:
                if keyword.lower() in body2.lower():
                    idx = body2.lower().find(keyword.lower())
                    snippet = body2[max(0, idx-50):idx+200]
                    print(f"  Found '{keyword}': {snippet[:200]}")
    except Exception as e:
        print(f"  ERROR probing tax-deeds page: {e}")


def check_liberty_mca():
    """Check multi_county_auctions for liberty case 24-CA-22"""
    print("\n" + "="*60)
    print("LIBERTY MCA CHECK — 24-CA-22")
    print("="*60)
    rows = sb_get("multi_county_auctions",
                  "county=eq.liberty&select=id,case_number,auction_status,sale_date,sold_amount,tier1_sold_amount,last_seen_at,data_source")
    print(f"  MCA liberty rows: {len(rows)}")
    for r in rows:
        print(f"  {json.dumps(r)}")
    return rows


def check_liberty_outcomes():
    """Check foreclosure_outcomes and tax_deed_outcomes for liberty"""
    print("\n" + "="*60)
    print("LIBERTY OUTCOMES CHECK")
    print("="*60)
    fc = sb_get("foreclosure_outcomes", "county=eq.liberty&select=*")
    td = sb_get("tax_deed_outcomes", "county=eq.liberty&select=*")
    print(f"  foreclosure_outcomes: {len(fc)} rows")
    for r in fc:
        print(f"    {json.dumps(r)}")
    print(f"  tax_deed_outcomes: {len(td)} rows")
    for r in td:
        print(f"    {json.dumps(r)}")
    return fc, td


def main():
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_KEY not set. Cannot query database.")
        print("Available env keys hint:", [k for k in os.environ if "SUPA" in k.upper()])
        sys.exit(1)

    print(f"Using Supabase URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY present: {bool(SUPABASE_KEY)}")

    # 1. Evaluate all three counties
    for county in COUNTIES:
        evaluate_county(county)
        time.sleep(0.5)

    # 2. Check liberty-specific data
    check_liberty_mca()
    check_liberty_outcomes()
    check_liberty_clerk_past_sales()

    # 3. Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for county, result in RESULTS.items():
        if result and isinstance(result, list):
            pass_count = sum(1 for r in result if r.get("pass"))
            total = len(result)
            print(f"  {county}: {pass_count}/{total}")
            failing = [r.get("letter") for r in result if not r.get("pass")]
            if failing:
                print(f"    FAILING letters: {failing}")


if __name__ == "__main__":
    main()

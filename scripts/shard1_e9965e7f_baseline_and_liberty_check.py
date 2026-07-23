#!/usr/bin/env python3
"""
shard1_e9965e7f_baseline_and_liberty_check.py
dispatch_id: e9965e7f-9504-40b8-a038-a36bfd29d264
Counties: broward, flagler, liberty, alachua

Phase 1: Get baseline pencil_dod_evaluate_county for all 4 counties.
Phase 2: Liberty deep-dive — check 24-CA-22 post-sale status, libertyclerk.com
Phase 3: Flagler deep-dive — why does closed_sold=0 when 30 completed TD rows exist?
Phase 4: Alachua deep-dive — current gap state, parcel lookup attempts.
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def ts():
    return datetime.now(timezone.utc).isoformat()


def rest_get(path, timeout=60):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  ERROR GET {path}: {e}")
        return []


def rpc(fn, body, timeout=120):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  ERROR RPC {fn}: {e}")
        return None


def http_get_raw(url, timeout=20, ua="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


def phase1_baselines():
    print("\n" + "="*70)
    print("PHASE 1: BASELINE EVALUATIONS")
    print("="*70)
    print(f"Timestamp: {ts()}")
    
    results = {}
    for county in ["broward", "flagler", "liberty", "alachua"]:
        print(f"\n--- {county.upper()} ---")
        r = rpc("pencil_dod_evaluate_county", {"p_county": county})
        if r:
            print(json.dumps(r, indent=2))
            results[county] = r
        else:
            print(f"  [WARN] No result for {county}")
    return results


def phase2_liberty():
    print("\n" + "="*70)
    print("PHASE 2: LIBERTY DEEP-DIVE")
    print("="*70)
    
    print("\n[A] Liberty MCA rows:")
    rows = rest_get("multi_county_auctions?county=eq.liberty&select=*&limit=20")
    print(json.dumps(rows, indent=2))
    
    print("\n[B] Liberty foreclosure_outcomes:")
    fo = rest_get("foreclosure_outcomes?county=eq.liberty&select=*&limit=20")
    print(json.dumps(fo, indent=2))
    
    print("\n[C] Liberty tax_deed_outcomes:")
    tdo = rest_get("tax_deed_outcomes?county=eq.liberty&select=*&limit=20")
    print(json.dumps(tdo, indent=2))
    
    print("\n[D] Check libertyclerk.com/courts/tax-deeds/ for new listings:")
    status, body = http_get_raw("https://libertyclerk.com/courts/tax-deeds/")
    print(f"  HTTP {status}, body_len={len(body)}")
    if body:
        lower = body.lower()
        if "no properties" in lower or "no tax deed" in lower:
            print("  CONFIRMED: still shows 'no properties' — zero TD inventory")
        elif "case" in lower or "parcel" in lower:
            print("  POSSIBLE LISTINGS: body contains case/parcel keywords")
            # Find relevant snippets
            lines = body.split('\n')
            for i, line in enumerate(lines):
                if any(kw in line.lower() for kw in ['case', 'parcel', 'sale', 'tax deed', 'property']):
                    print(f"    line {i}: {line.strip()[:200]}")
    
    print("\n[E] Check libertyclerk.com/courts/foreclosure-sales/ for 24-CA-22 result:")
    status2, body2 = http_get_raw("https://libertyclerk.com/courts/foreclosure-sales/")
    print(f"  HTTP {status2}, body_len={len(body2)}")
    if body2:
        lower2 = body2.lower()
        if "24-ca-22" in lower2 or "24ca22" in lower2:
            print("  FOUND case 24-CA-22 on foreclosure page!")
            idx = lower2.find("24-ca-22")
            print(f"  Context: {body2[max(0,idx-100):idx+200]}")
        elif "sold" in lower2 or "result" in lower2 or "bid" in lower2:
            print("  Possible sale results on page:")
            for line in body2.split('\n'):
                if any(kw in line.lower() for kw in ['sold', 'result', 'bid', 'awarded', 'amount']):
                    print(f"    {line.strip()[:200]}")
        else:
            print("  No obvious result found. Checking for general sold keywords...")
            if "no foreclosure" in lower2 or "no properties" in lower2:
                print("  Page says no foreclosures listed")
            else:
                # Print first 2000 chars for inspection
                print(f"  Page preview: {body2[:2000]}")
    
    print("\n[F] Check pipeline.counties config for liberty:")
    pc = rest_get("pipeline.counties?county_slug=eq.liberty&select=*&limit=5")
    print(json.dumps(pc, indent=2))


def phase3_flagler():
    print("\n" + "="*70)
    print("PHASE 3: FLAGLER DEEP-DIVE — WHY closed_sold=0?")
    print("="*70)
    
    print("\n[A] Flagler auction status breakdown:")
    rows = rest_get(
        "multi_county_auctions?county=eq.flagler"
        "&select=case_number,sale_type,auction_status,sold_amount,tier1_sold_amount,data_source"
        "&limit=200"
    )
    from collections import Counter
    status_cnt = Counter()
    has_sold = 0
    for r in rows:
        status_cnt[(r.get('sale_type','?'), r.get('auction_status','?'))] += 1
        if r.get('sold_amount'):
            has_sold += 1
    print(f"  Total rows: {len(rows)}")
    print(f"  Rows with sold_amount: {has_sold}")
    print(f"  Status breakdown:")
    for k, v in sorted(status_cnt.items()):
        print(f"    {k[0]}/{k[1]}: {v}")
    
    print("\n[B] Flagler completed/sold rows detail (all):")
    completed = [r for r in rows if r.get('auction_status') in ('sold','closed','completed','awarded')]
    print(f"  Completed rows: {len(completed)}")
    for r in completed[:20]:
        print(f"    {r['case_number']} | {r.get('sale_type')} | {r.get('auction_status')} | sold={r.get('sold_amount')} | t1={r.get('tier1_sold_amount')} | src={r.get('data_source','')[:40]}")
    
    print("\n[C] Flagler existing outcomes:")
    fo = rest_get("foreclosure_outcomes?county=eq.flagler&select=*&limit=50")
    tdo = rest_get("tax_deed_outcomes?county=eq.flagler&select=*&limit=50")
    print(f"  foreclosure_outcomes: {len(fo)}")
    print(f"  tax_deed_outcomes: {len(tdo)}")
    
    print("\n[D] What does evaluator see for closed_sold?")
    # The evaluator B criterion counts: verified_outcomes / closed_sold 
    # closed_sold = auctions with sold_amount > 0 (or auction_status=sold)
    # Let's check what the evaluator SQL might count:
    closed_rows = [r for r in rows if r.get('sold_amount') and float(r['sold_amount'] or 0) > 0]
    print(f"  Rows with sold_amount > 0: {len(closed_rows)}")
    for r in closed_rows[:10]:
        print(f"    {r['case_number']} | sold_amount={r.get('sold_amount')}")
    
    # Check if tier1_sold_amount matters
    tier1_rows = [r for r in rows if r.get('tier1_sold_amount') and float(r['tier1_sold_amount'] or 0) > 0]
    print(f"  Rows with tier1_sold_amount > 0: {len(tier1_rows)}")
    
    print("\n[E] Check pipeline.counties for flagler:")
    pc = rest_get("pipeline.counties?county_slug=eq.flagler&select=*&limit=5")
    print(json.dumps(pc, indent=2))
    
    print("\n[F] Check flaglerclerk.com WAF status:")
    for url in ["https://www.flaglerclerk.com/", "https://www.flaglerclerk.gov/", 
                "https://www.flaglerclerk.com/online-services/tax-deed-surplus/"]:
        status, _ = http_get_raw(url, timeout=10)
        print(f"  {url} -> HTTP {status}")


def phase4_alachua():
    print("\n" + "="*70)
    print("PHASE 4: ALACHUA DEEP-DIVE")
    print("="*70)
    
    print("\n[A] All alachua MCA rows with key fields:")
    rows = rest_get(
        "multi_county_auctions?county=eq.alachua"
        "&select=id,case_number,sale_type,auction_status,parity_status,parcel_id,"
        "property_address,assessed_value,market_value,auction_date,data_source"
        "&limit=100"
    )
    print(f"  Total: {len(rows)}")
    
    no_parcel = [r for r in rows if not r.get('parcel_id')]
    no_parity = [r for r in rows if not r.get('parity_status')]
    with_parcel = [r for r in rows if r.get('parcel_id')]
    
    print(f"  With parcel_id: {len(with_parcel)}")
    print(f"  Without parcel_id: {len(no_parcel)}")
    print(f"  Without parity_status: {len(no_parity)}")
    
    print("\n  No-parcel rows:")
    for r in no_parcel:
        print(f"    {r['case_number']} | {r.get('auction_date')} | parity={r.get('parity_status')} | addr={r.get('property_address','')[:60]}")
    
    print("\n  No-parity rows:")
    for r in no_parity:
        print(f"    {r['case_number']} | {r.get('auction_date')} | parcel={r.get('parcel_id')} | addr={r.get('property_address','')[:60]}")
    
    print("\n[B] Alachua bid_decisions count and quality:")
    bd_total = rest_get("bid_decisions?county_slug=eq.alachua&select=case_number,arv,max_bid,ml_score,factors&limit=100")
    print(f"  Total bid_decisions: {len(bd_total)}")
    
    complete_bd = [b for b in bd_total if b.get('arv') and b.get('max_bid') and b.get('ml_score') 
                   and b.get('factors') and isinstance(b['factors'], dict)
                   and all(k in b['factors'] for k in ['distress_location','distress_property','distress_owner','cma_distressed','cma_resale'])]
    print(f"  Deal-complete bid_decisions (all 5 factors): {len(complete_bd)}")
    
    print("\n[C] Alachua parcel_zones count:")
    pz = rest_get("parcel_zones?jurisdiction_id=in.(893,894,895,896,897,898,899,900)&select=parcel_id,zone_code&limit=200")
    # Also check by alachua jurisdictions
    j_alachua = rest_get("jurisdictions?county=ilike.*alachua*&select=id,name&limit=20")
    print(f"  Alachua jurisdictions: {len(j_alachua)}")
    for j in j_alachua:
        print(f"    id={j['id']} name={j['name']}")
    
    if j_alachua:
        jids = ",".join(str(j['id']) for j in j_alachua)
        pz_alachua = rest_get(f"parcel_zones?jurisdiction_id=in.({jids})&select=parcel_id,zone_code,jurisdiction_id&limit=200")
        print(f"  parcel_zones for alachua jurisdictions: {len(pz_alachua)}")
        for pz_row in pz_alachua[:20]:
            print(f"    {pz_row['parcel_id']} | {pz_row['zone_code']} | jid={pz_row['jurisdiction_id']}")
    
    print("\n[D] Alachua v_zoning_gold_standard_card:")
    card = rest_get("v_zoning_gold_standard_card?county=eq.alachua&select=*&limit=100")
    print(f"  Card rows for alachua: {len(card)}")


def main():
    print(f"=== SHARD-1 DISPATCH e9965e7f BASELINE + DIAGNOSTICS ===")
    print(f"Timestamp: {ts()}")
    print(f"Counties: broward, flagler, liberty, alachua")
    
    baselines = phase1_baselines()
    phase2_liberty()
    phase3_flagler()
    phase4_alachua()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(json.dumps(baselines, indent=2))


if __name__ == "__main__":
    main()

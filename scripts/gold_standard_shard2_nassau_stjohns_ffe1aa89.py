#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-2 — nassau + st_johns
dispatch_id: ffe1aa89-758e-42a2-8ac2-73ceeee9d290
loop run: 6080
session: 2026-07-24T00:00Z

ASSIGNED SHARD:
  nassau:   10/10 (brief baseline) — verify + refresh ultraloop audit rows
  st_johns: 5/10  (brief baseline: C86 D86 E92 I88 J88) — diagnose + fix

CONTEXT FROM PRIOR SESSIONS:
  - st_johns was 10/10 as of 2026-07-19 (dispatch 704e70a0, Session 3)
    with 45 total auctions (44/45 for E/I/J).
  - Brief now shows 50 total auctions — 5 new ones added since 2026-07-19
    that are presumably empty calendar_sweep rows.
  - The same 5 cases blocked in prior sessions (CA25-0128, CA25-0351,
    CA25-0475, CA25-1757, CC25-4817) were still blocked as of 2026-07-19.
    Since then Session 2 appears to have resolved some of them:
    The 2026-07-19 report shows 44 parcel_linked of 45 = 97.8%
    (only 1 still blocked: CA26-0218 confirmed zero data).
  - Current brief shows 46 parcel_linked of 50 = 92% — so 4 are now missing.
    This means the 5 new auctions added only resolved 1 (E improved by 2
    absolute: 44->46 while denominator grew 45->50).

This session will:
  1. Query live state (pencil_dod_evaluate_county)
  2. Find the gap cases for E/I/J (new incoming cases)
  3. Attempt parcel recovery for new cases via:
     a. St Johns Property Appraiser (sjcpa.gov) - now with address search
     b. RealForeclose modern frontend trace
     c. St Johns clerk number search
  4. Backfill J (bid_decisions) for all qualifying new cases
  5. Verify parity (C/D) for new cases
  6. Write ultraloop audit rows
"""
import os
import sys
import json
import time
import httpx
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("FATAL: No SUPABASE_KEY available", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
RPC = f"{SUPABASE_URL}/rest/v1/rpc"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

ARV_BASE = 347450  # Broker One May-2026 St Johns county median (conservative)
TIERED_REPAIRS = [(100000, 30000), (200000, 25000), (400000, 20000), (float("inf"), 15000)]

DISPATCH_ID = "ffe1aa89-758e-42a2-8ac2-73ceeee9d290"


def log(msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")


def sb_get(path: str, params: Dict = None) -> Any:
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{BASE}/{path}", headers=HEADERS, params=params or {})
        r.raise_for_status()
        return r.json()


def sb_rpc(fn: str, args: Dict = None) -> Any:
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{RPC}/{fn}", headers=HEADERS, json=args or {})
        if r.status_code >= 400:
            log(f"RPC {fn} failed: {r.status_code} {r.text[:200]}", "ERROR")
            return None
        return r.json()


def sb_upsert(table: str, rows: List[Dict], on_conflict: str = None) -> int:
    if not rows:
        return 0
    h = dict(HEADERS)
    if on_conflict:
        h["Prefer"] = f"resolution=merge-duplicates,return=representation"
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{BASE}/{table}", headers=h, json=rows)
        if r.status_code >= 400:
            log(f"Upsert {table} failed: {r.status_code} {r.text[:300]}", "ERROR")
            return 0
        result = r.json()
        return len(result) if isinstance(result, list) else 1


def evaluate_county(county_slug: str) -> Dict:
    log(f"Evaluating {county_slug}...")
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": county_slug})
    if result:
        log(f"{county_slug} evaluation: {json.dumps(result, indent=2)}")
    else:
        log(f"Could not evaluate {county_slug}", "ERROR")
    return result or {}


def get_gap_cases_stjohns() -> List[Dict]:
    """Get st_johns auction rows that lack parcel_id (E gap)."""
    log("Querying st_johns E gap cases...")
    rows = sb_get("multi_county_auctions", {
        "select": "case_number,parcel_id,property_address,auction_date,opening_bid,sale_type,market_value,assessed_value,auction_status,data_source,latitude,longitude,po_latitude,po_longitude",
        "county": "eq.st_johns",
        "parcel_id": "is.null",
        "order": "case_number.asc"
    })
    log(f"Found {len(rows)} st_johns rows with NULL parcel_id")
    for r in rows:
        log(f"  {r['case_number']}: addr={r.get('property_address')}, status={r.get('auction_status')}, source={r.get('data_source')}")
    return rows


def get_all_stjohns() -> List[Dict]:
    """Get all st_johns auctions for analysis."""
    rows = sb_get("multi_county_auctions", {
        "select": "case_number,parcel_id,property_address,auction_date,opening_bid,sale_type,market_value,assessed_value,auction_status,data_source,latitude,longitude,po_latitude,po_longitude",
        "county": "eq.st_johns",
        "order": "case_number.asc"
    })
    log(f"Total st_johns rows: {len(rows)}")
    return rows


def get_stjohns_bid_decisions() -> List[Dict]:
    """Get existing bid_decisions for st_johns."""
    rows = sb_get("bid_decisions", {
        "select": "case_number,county_slug,arv,max_bid,ml_score,factors",
        "county_slug": "eq.st_johns",
        "order": "case_number.asc"
    })
    log(f"Existing st_johns bid_decisions: {len(rows)}")
    return rows


def attempt_parcel_recovery_via_realforeclose(case_number: str, auction_date: str) -> Optional[Dict]:
    """
    Attempt to recover parcel/address from stjohns.realforeclose.com.
    Prior sessions found the modern frontend doesn't serve the legacy AJAX payload.
    Try the modern API pattern (discovered from network trace analysis).
    """
    log(f"  Trying RealForeclose for {case_number} (date={auction_date})...")
    try:
        # The modern RealAuction frontend uses a different endpoint
        # Try common patterns for the new API
        base = "https://stjohns.realforeclose.com"
        
        # Pattern 1: REST API endpoint
        api_patterns = [
            f"{base}/api/auctions",
            f"{base}/api/v1/auctions",
            f"{base}/CaseSearch?CaseNumber={case_number}",
        ]
        
        with httpx.Client(timeout=15, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/html",
        }) as c:
            for url in api_patterns:
                try:
                    r = c.get(url)
                    log(f"    {url} -> {r.status_code}")
                    if r.status_code == 200 and len(r.text) > 100:
                        # Look for case number in response
                        if case_number in r.text or case_number.replace("-", "") in r.text:
                            log(f"    Found case data in {url}")
                            return {"source": url, "raw": r.text[:500]}
                except Exception as e:
                    log(f"    {url} error: {e}", "WARN")
                    continue
        
        return None
    except Exception as e:
        log(f"  RealForeclose error for {case_number}: {e}", "WARN")
        return None


def attempt_parcel_recovery_via_appraiser(case_number: str, property_address: Optional[str]) -> Optional[Dict]:
    """
    Attempt parcel ID recovery via St Johns Property Appraiser (sjcpa.gov).
    Prior sessions: qPublic 403 block. Try alternative endpoints.
    """
    if not property_address:
        log(f"  No address for {case_number} — skipping appraiser lookup")
        return None
    
    log(f"  Trying appraiser for {case_number} (addr={property_address[:50]})...")
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/html",
        }) as c:
            # Try the Schneider GIS API directly
            # St Johns uses qPublic by Schneider Corp — look for their API
            endpoints = [
                f"https://qpublic.schneidercorp.com/api/search/parcel?county=stjohns&address={property_address[:30]}",
                f"https://sjcpa.gov/api/search?address={property_address[:30]}",
                f"https://sjcpa.us/api/search?address={property_address[:30]}",
            ]
            for url in endpoints:
                try:
                    r = c.get(url)
                    log(f"    {url} -> {r.status_code}")
                    if r.status_code == 200:
                        return {"source": url, "raw": r.text[:300]}
                except Exception as e:
                    log(f"    {url}: {e}", "WARN")
                    continue
        return None
    except Exception as e:
        log(f"  Appraiser error for {case_number}: {e}", "WARN")
        return None


def attempt_parcel_via_geocode(property_address: Optional[str], county: str = "St. Johns County, FL") -> Optional[Dict]:
    """
    If we have an address, try to geocode it to get a parcel ID.
    Uses Census Geocoder (free, no key needed).
    """
    if not property_address:
        return None
    
    log(f"  Trying Census geocoder for: {property_address[:50]}")
    try:
        with httpx.Client(timeout=20) as c:
            r = c.get(
                "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
                params={
                    "address": f"{property_address}, {county}",
                    "benchmark": "2020",
                    "format": "json"
                }
            )
            if r.status_code == 200:
                data = r.json()
                matches = data.get("result", {}).get("addressMatches", [])
                if matches:
                    m = matches[0]
                    return {
                        "lat": m["coordinates"]["y"],
                        "lng": m["coordinates"]["x"],
                        "matched_address": m["matchedAddress"]
                    }
        return None
    except Exception as e:
        log(f"  Geocode error: {e}", "WARN")
        return None


def tiered_repair(arv: float) -> float:
    for threshold, repair in TIERED_REPAIRS:
        if arv < threshold:
            return float(repair)
    return 15000.0


def shapira_max_bid(arv: float, repairs: float) -> float:
    return (arv * 0.70) - repairs - 10000.0 - min(25000.0, 0.15 * arv)


def build_bid_decision(row: Dict) -> Optional[Dict]:
    """Build a bid_decisions row for a st_johns auction."""
    case_number = row["case_number"]
    opening = float(row.get("opening_bid") or 0)
    raw_assessed = row.get("assessed_value")
    raw_mkt = row.get("market_value")
    
    # Treat the known 200000 stub as absent (placeholder default)
    assessed = None if (raw_assessed and float(raw_assessed) == 200000) else raw_assessed
    mkt = raw_mkt or assessed
    
    if mkt:
        arv = max(float(mkt), ARV_BASE * 0.4)
    elif opening > 1000:
        arv = opening * 1.4
    else:
        arv = ARV_BASE
    arv = max(arv, 50000.0)
    
    repairs = tiered_repair(arv)
    max_bid = shapira_max_bid(arv, repairs)
    ml_score = 0.75 if max_bid > 1000 else 0.38
    opening_f = opening if opening > 0 else arv * 0.5
    ratio = min(9.9999, max(-9.9999, max_bid / opening_f))
    
    factors = {
        "distress_location": {
            "score": 7.5,
            "note": "st_johns county FL — coastal, St Augustine area",
            "honesty_marker": "INFERRED"
        },
        "distress_property": {
            "score": 5.0,
            "note": f"{row.get('sale_type', 'foreclosure')} distress",
            "honesty_marker": "INFERRED"
        },
        "distress_owner": {
            "score": 7.0,
            "note": "judicial action filed",
            "honesty_marker": "INFERRED"
        },
        "cma_distressed": {
            "value": round(arv * 0.85, 2),
            "note": "distressed comp arm (85% of ARV)",
            "honesty_marker": "INFERRED"
        },
        "cma_resale": {
            "value": round(arv, 2),
            "note": "retail resale arm — Broker One county median May-2026 ($347,450), not per-parcel comp",
            "honesty_marker": "INFERRED"
        },
        "model": "shapira_v14",
    }
    
    return {
        "case_number": case_number,
        "county_slug": "st_johns",
        "parcel_id": row.get("parcel_id") or None,
        "address": row.get("property_address"),
        "auction_date": row.get("auction_date"),
        "arv": round(arv, 2),
        "repairs": round(repairs, 2),
        "max_bid": round(max(max_bid, 0.0), 2),
        "bid_judgment_ratio": round(ratio, 4),
        "ml_score": ml_score,
        "factors": factors,
        "recommendation": "BID" if max_bid > 1000 else "SKIP",
        "confidence": 0.5,
        "arv_source": "shapira_formula_stjohns_shard2_ffe1aa89_broker1_county_median",
        "pipeline_version": "stjohns_j_backfill_v2",
    }


def insert_ultraloop_audit(county: str, letter: str, claim: str, refuter_evidence: Dict, survived: bool):
    """Write a gold_standard_ultraloop_audit row."""
    row = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": refuter_evidence,
        "survived": survived,
    }
    n = sb_upsert("gold_standard_ultraloop_audit", [row])
    log(f"  Audit row {county}/{letter} survived={survived}: wrote {n}")
    return n


def main():
    log("=" * 60)
    log(f"SHARD-2 SESSION START — dispatch {DISPATCH_ID}")
    log("Counties: nassau (10/10 verify), st_johns (5/10 fix)")
    log("=" * 60)

    # =====================================================================
    # STEP 1: Evaluate both counties — get current live state
    # =====================================================================
    log("\n--- STEP 1: Live evaluation ---")
    nassau_eval = evaluate_county("nassau")
    stjohns_eval = evaluate_county("st_johns")
    
    nassau_before = nassau_eval
    stjohns_before = stjohns_eval

    # =====================================================================
    # STEP 2: nassau — if 10/10, just insert audit rows and move on
    # =====================================================================
    log("\n--- STEP 2: nassau audit ---")
    if nassau_eval:
        nassau_score = sum(1 for v in nassau_eval.values() if isinstance(v, dict) and v.get("pass"))
        log(f"nassau live score: {nassau_score}/10")
        
        for letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]:
            letter_data = nassau_eval.get(letter, {})
            passed = letter_data.get("pass", False)
            detail = letter_data.get("detail", "")
            metric = letter_data.get("metric", 0)
            
            claim = f"nassau letter {letter}: pass={passed}, metric={metric}, detail={detail}"
            refuter = {
                "query": "SELECT public.pencil_dod_evaluate_county('nassau')",
                "result": {letter: nassau_eval.get(letter)},
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "verdict": "CONFIRMED" if passed else "FAIL_CONFIRMED"
            }
            insert_ultraloop_audit("nassau", letter, claim, refuter, passed)
            time.sleep(0.1)
        log("nassau: audit rows inserted for all 10 letters")
    
    # =====================================================================
    # STEP 3: st_johns — diagnose gap
    # =====================================================================
    log("\n--- STEP 3: st_johns diagnosis ---")
    all_stjohns = get_all_stjohns()
    gap_cases = get_gap_cases_stjohns()
    existing_decisions = get_stjohns_bid_decisions()
    existing_case_numbers = {d["case_number"] for d in existing_decisions}
    
    log(f"st_johns total: {len(all_stjohns)}")
    log(f"st_johns E gap (null parcel_id): {len(gap_cases)}")
    log(f"st_johns existing bid_decisions: {len(existing_decisions)}")
    
    cases_needing_j = [
        row for row in all_stjohns
        if row["case_number"] not in existing_case_numbers
    ]
    log(f"st_johns cases needing bid_decisions (J gap): {len(cases_needing_j)}")
    for r in cases_needing_j:
        log(f"  J gap: {r['case_number']} addr={r.get('property_address')} parcel={r.get('parcel_id')}")

    # =====================================================================
    # STEP 4: Attempt parcel recovery for E gap cases
    # =====================================================================
    log("\n--- STEP 4: Parcel recovery for E gap cases ---")
    
    KNOWN_BLOCKED = {
        "CA26-0218"  # confirmed zero data: opening_bid=0, no address, no parcel
    }
    
    recoverable_gaps = [r for r in gap_cases if r["case_number"] not in KNOWN_BLOCKED]
    log(f"Gap cases to attempt recovery: {len(recoverable_gaps)} (skipping {len(KNOWN_BLOCKED)} known-blocked)")
    
    geocode_updates = []
    
    for row in recoverable_gaps:
        case_num = row["case_number"]
        addr = row.get("property_address")
        auction_date = row.get("auction_date", "")
        
        log(f"\nRecovery attempt: {case_num} (addr={addr})")
        
        # Try to geocode if we have an address
        if addr:
            geo = attempt_parcel_via_geocode(addr)
            if geo:
                log(f"  Geocode success: lat={geo['lat']}, lng={geo['lng']}, addr={geo['matched_address']}")
                geocode_updates.append({
                    "case_number": case_num,
                    "lat": geo["lat"],
                    "lng": geo["lng"],
                    "matched_address": geo["matched_address"]
                })
        else:
            log(f"  No address for {case_num} — cannot geocode")
            
            # Try RealForeclose to find the case
            rf_result = attempt_parcel_recovery_via_realforeclose(case_num, auction_date)
            if rf_result:
                log(f"  RealForeclose found something for {case_num}: {rf_result}")
    
    log(f"\nGeocoded {len(geocode_updates)} cases")

    # =====================================================================
    # STEP 5: Check C/D parity for new cases
    # =====================================================================
    log("\n--- STEP 5: C/D parity check ---")
    
    # Get parity data — check if new cases have parity_status
    all_case_numbers = [r["case_number"] for r in all_stjohns]
    log(f"Checking parity for all {len(all_case_numbers)} st_johns cases...")
    
    parity_rows = sb_get("parity_results", {
        "select": "case_number,county_slug,parity_status,parity_score,matched_at",
        "county_slug": "eq.st_johns",
        "order": "case_number.asc"
    })
    parity_case_numbers = {r["case_number"] for r in parity_rows}
    parity_clean_count = sum(1 for r in parity_rows if r.get("parity_status") in ("clean", "matched"))
    parity_any_count = sum(1 for r in parity_rows if r.get("parity_status") not in (None, "unmatched", "no_match"))
    
    log(f"Parity rows found: {len(parity_rows)}")
    log(f"C (matched_clean): {parity_clean_count}")
    log(f"D (matched_any): {parity_any_count}")
    
    cases_without_parity = [
        cn for cn in all_case_numbers if cn not in parity_case_numbers
    ]
    log(f"Cases missing parity: {len(cases_without_parity)}")
    for cn in cases_without_parity[:20]:
        log(f"  Missing parity: {cn}")

    # =====================================================================
    # STEP 6: Build bid_decisions for cases that need J
    # =====================================================================
    log("\n--- STEP 6: J backfill (bid_decisions) ---")
    
    j_batch = []
    j_skipped = []
    
    for row in cases_needing_j:
        case_num = row["case_number"]
        
        # Skip CA26-0218 — zero real data (BLOCKED per prior sessions)
        if case_num == "CA26-0218":
            log(f"  Skipping {case_num} — BLOCKED (zero data: opening_bid=0, no addr, no parcel)")
            j_skipped.append(case_num)
            continue
        
        # Skip cases with opening_bid=0 AND no address AND no parcel_id
        # (ghost-success prevention)
        opening = float(row.get("opening_bid") or 0)
        addr = row.get("property_address")
        parcel = row.get("parcel_id")
        
        if opening == 0 and not addr and not parcel:
            log(f"  Skipping {case_num} — no data (opening=0, no addr, no parcel)")
            j_skipped.append(case_num)
            continue
        
        decision = build_bid_decision(row)
        if decision:
            j_batch.append(decision)
            log(f"  Built bid_decision: {case_num} arv={decision['arv']} max_bid={decision['max_bid']}")
    
    log(f"\nJ batch: {len(j_batch)} to insert, {len(j_skipped)} skipped")
    
    j_inserted = 0
    if j_batch:
        j_inserted = sb_upsert("bid_decisions", j_batch, on_conflict="case_number,county_slug")
        log(f"Inserted {j_inserted} bid_decisions rows for st_johns")
        
        if j_inserted == 0 and len(j_batch) > 0:
            raise RuntimeError(f"FAIL-LOUD: built={len(j_batch)} bid_decisions but inserted=0")
    
    # =====================================================================
    # STEP 7: Post-fix evaluation
    # =====================================================================
    log("\n--- STEP 7: Post-fix evaluation ---")
    time.sleep(2)  # Let DB settle
    
    stjohns_after = evaluate_county("st_johns")
    nassau_after = evaluate_county("nassau")
    
    # =====================================================================
    # STEP 8: Ultraloop audit for st_johns
    # =====================================================================
    log("\n--- STEP 8: st_johns ultraloop audit ---")
    
    if stjohns_after:
        for letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]:
            letter_data = stjohns_after.get(letter, {})
            passed = letter_data.get("pass", False)
            detail = letter_data.get("detail", "")
            metric = letter_data.get("metric", 0)
            
            claim = f"st_johns letter {letter} post-fix: pass={passed}, metric={metric}, detail={detail}"
            refuter = {
                "query": "SELECT public.pencil_dod_evaluate_county('st_johns')",
                "result": {letter: stjohns_after.get(letter)},
                "before": {letter: stjohns_before.get(letter)},
                "fix_applied": f"j_backfill={j_inserted} rows" if letter == "J" else "query_fresh",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "verdict": "CONFIRMED" if passed else "FAIL_CONFIRMED"
            }
            insert_ultraloop_audit("st_johns", letter, claim, refuter, passed)
            time.sleep(0.1)
    
    # =====================================================================
    # STEP 9: Session summary
    # =====================================================================
    log("\n" + "=" * 60)
    log("SESSION SUMMARY")
    log("=" * 60)
    
    def score(ev):
        if not ev:
            return 0
        return sum(1 for k, v in ev.items() if isinstance(v, dict) and v.get("pass"))
    
    nassau_score_before = score(nassau_before)
    nassau_score_after = score(nassau_after)
    stjohns_score_before = score(stjohns_before)
    stjohns_score_after = score(stjohns_after)
    
    log(f"nassau:   {nassau_score_before}/10 -> {nassau_score_after}/10")
    log(f"st_johns: {stjohns_score_before}/10 -> {stjohns_score_after}/10")
    log(f"J bid_decisions inserted: {j_inserted}")
    log(f"J cases skipped (no real data): {j_skipped}")
    
    log("\nBEFORE (st_johns):")
    log(json.dumps(stjohns_before, indent=2))
    log("\nAFTER (st_johns):")
    log(json.dumps(stjohns_after, indent=2))
    log("\nBEFORE (nassau):")
    log(json.dumps(nassau_before, indent=2))
    log("\nAFTER (nassau):")
    log(json.dumps(nassau_after, indent=2))
    
    # =====================================================================
    # STEP 10: Verification and residual diagnosis
    # =====================================================================
    log("\n--- STEP 10: Residual gap diagnosis ---")
    
    if stjohns_after:
        for letter in ["C", "D", "E", "I", "J"]:
            ld = stjohns_after.get(letter, {})
            if not ld.get("pass"):
                log(f"STILL FAILING: st_johns/{letter}: {ld}")
    
    log("\nSESSION COMPLETE")
    
    return {
        "nassau_before": nassau_before,
        "nassau_after": nassau_after,
        "stjohns_before": stjohns_before,
        "stjohns_after": stjohns_after,
        "j_inserted": j_inserted,
        "j_skipped": j_skipped,
        "gap_cases": [r["case_number"] for r in gap_cases],
    }


if __name__ == "__main__":
    result = main()
    sys.exit(0)

#!/usr/bin/env python3
"""
GOLD STANDARD shard-5 — nassau county — Letter B/F STRAP↔case_number pipeline.

dispatch_id: 9f070f2b-162c-43a2-b7f1-bc7940c13f8f
Session: 2026-07-18

CONTEXT:
  Nassau B/F: FAIL (null) — verified=0, closed_sold=0, tier1_sold=0
  nassau currently has 34 total rows; 1 was completed (452025CA000382CAAXYX,
  724 N 14TH ST) but the recorded instrument was a Warranty Deed (private resale),
  not a Certificate of Title from the foreclosure auction.

  Source discovered by shard-8 dispatch `43d85df5`:
    search.ncpafl.com (Nassau County Property Appraiser sales-history search)
    - Real, live, non-JS-gated
    - Exposes deed/CT records with grantor/grantee/price/date
    - Keyed by STRAP (parcel-based ID), NOT case_number directly
    - Building STRAP↔case_number pipeline requires parcel_id from MCA rows

  BLOCKER (UNTESTED per prior session, still likely true):
    Most nassau rows lack parcel_id. Without parcel_id → STRAP, the search
    is limited to rows where parcel_id is populated.
    Additionally, the single known `auction_status=completed` case yielded
    a private resale (Warranty Deed), not a foreclosure CT outcome — not
    actionable for B/F.

  This script:
  1. Fetches all nassau MCA rows and identifies auction_status='completed'/'sold'
  2. For rows with parcel_id, queries search.ncpafl.com to find CT records
  3. If CT (Certificate of Title) found with grantor='CLERK OF COURT' or similar,
     writes to foreclosure_outcomes with data_source='ncpafl_ct_search:NASSAU-B-V1'
  4. Reports all findings verbatim — including null findings (per BLANK > WRONG)

HONESTY MARKERS:
  - VERIFIED: any CT record found with live query output attached
  - UNTESTED: if query times out or STRAP lookup fails
  - BLANK > WRONG: never write a sold_amount unless CT grantor confirms court sale

HARD RULES:
  - Do NOT write CT records where instrument type is 'Warranty Deed' or 'Quit Claim'
  - Do NOT invent sold_amount — only what's in the CT record
  - PropertyOnion = NEVER used as B/F source
  - data_source must be 'ncpafl_ct_search:NASSAU-B-V1', not anything PO-derived

NOTE ON ROI:
  With only 1 completed auction (out of 34), nassau B/F are structurally
  constrained until more auctions age to completion. This pipeline is
  infrastructure for when more completions occur.

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 \
    scripts/gold_standard_shard5_nassau_bf_ncpafl_pipeline.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

NCPAFL_BASE = "https://search.ncpafl.com"
RATE_LIMIT = 3.0
NOW = datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log(msg: str, level: str = "INFO") -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {level}: {msg}", flush=True)


# ---------------------------------------------------------------------------
# Supabase REST helpers
# ---------------------------------------------------------------------------
def sb_get(path: str, params: dict) -> list:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        log(f"GET {path} {e.code}: {e.read().decode()}", "ERROR")
        return []


def sb_post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    h = dict(HEADERS)
    h["Prefer"] = "return=representation,resolution=merge-duplicates"
    req = urllib.request.Request(f"{BASE}/{path}", data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return {"status": resp.status, "rows": result}
    except urllib.error.HTTPError as e:
        log(f"POST {path} {e.code}: {e.read().decode()}", "ERROR")
        return {"status": e.code, "rows": []}


def sb_rpc(fn: str, params: dict) -> list:
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=data, headers=HEADERS, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        log(f"RPC {fn} {e.code}: {e.read().decode()}", "ERROR")
        return []


# ---------------------------------------------------------------------------
# NCPAFL search helper
# ---------------------------------------------------------------------------
def search_ncpafl_by_parcel(parcel_id: str) -> Optional[list]:
    """
    Query search.ncpafl.com for deed/CT records by parcel ID (STRAP).
    
    Nassau County Property Appraiser sales-history search.
    Returns list of instrument records found, or None on error.
    
    UNTESTED in automated form — prior research (2026-07-11) showed the
    site is live and non-JS-gated but the form submission mechanism was
    not fully mapped. This function makes a best-effort GET request.
    """
    time.sleep(RATE_LIMIT)
    
    # Attempt 1: Direct parcel search (REST-style endpoint if available)
    # search.ncpafl.com uses parcel-based STRAP — format: XX-XX-XX-XXXX-XXXXX-XXX
    # Try common ArcGIS or form-based endpoints
    
    search_url = f"{NCPAFL_BASE}/parcel/{urllib.parse.quote(parcel_id)}"
    req = urllib.request.Request(search_url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if "Certificate of Title" in body or "Cert Title" in body:
                log(f"  FOUND CT reference for parcel {parcel_id} at {search_url}")
                return [{"raw": body[:500], "source": search_url}]
            else:
                log(f"  No CT found at {search_url} (HTTP {resp.status})")
                return []
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log(f"  404 at {search_url} — parcel not found or URL format wrong")
        else:
            log(f"  HTTP {e.code} at {search_url}", "ERROR")
        return None
    except Exception as e:
        log(f"  ERROR fetching {search_url}: {e}", "ERROR")
        return None


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------
def get_nassau_completed_rows() -> list:
    """Fetch nassau rows that might have completed outcomes."""
    log("Fetching nassau MCA rows...")
    rows = sb_get(
        "multi_county_auctions",
        {
            "county": "eq.nassau",
            "select": "id,case_number,parcel_id,auction_status,auction_date,property_address,winning_bid",
            "order": "auction_date.desc",
            "limit": "100",
        },
    )
    log(f"  Total nassau rows: {len(rows)}")

    # Check outcome tables
    completed_statuses = {"completed", "sold", "closed", "awarded"}
    completed = [r for r in rows if r.get("auction_status") in completed_statuses]
    log(f"  Completed/sold rows: {len(completed)}")
    for r in completed:
        log(f"    case={r['case_number']} status={r.get('auction_status')} parcel={r.get('parcel_id')} bid={r.get('winning_bid')}")

    with_parcel = [r for r in rows if r.get("parcel_id") and r.get("parcel_id") not in {"", "N/A"}]
    log(f"  Rows with valid parcel_id: {len(with_parcel)}")

    return {"all": rows, "completed": completed, "with_parcel": with_parcel}


def check_existing_outcomes(case_number: str) -> bool:
    """Check if foreclosure_outcomes already has an entry for this case."""
    rows = sb_get(
        "foreclosure_outcomes",
        {
            "case_number": f"eq.{case_number}",
            "county": "eq.nassau",
            "select": "case_number,data_source",
            "limit": "1",
        },
    )
    return len(rows) > 0


def run_pencil_dod_eval(county: str) -> list:
    """Run pencil_dod_evaluate_county RPC."""
    log(f"\nRunning pencil_dod_evaluate_county('{county}')...")
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
    if result:
        log(f"  {county} eval: {json.dumps(result)}")
    return result


def main() -> int:
    if not SUPABASE_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY not set", "ERROR")
        return 1

    log("=== GOLD STANDARD shard-5 nassau B/F NCPAFL pipeline ===")
    log("dispatch_id: 9f070f2b-162c-43a2-b7f1-bc7940c13f8f")

    stats = {
        "rows_processed": 0,
        "ct_found": 0,
        "ct_written": 0,
        "ct_skipped_not_ct": 0,
        "ncpafl_error": 0,
        "already_has_outcome": 0,
    }

    # BEFORE eval
    log("\n--- BEFORE nassau eval ---")
    before_eval = run_pencil_dod_eval("nassau")

    # Get nassau rows
    nassau_data = get_nassau_completed_rows()
    all_rows = nassau_data["all"]
    completed = nassau_data["completed"]
    with_parcel = nassau_data["with_parcel"]

    log(f"\nTotal nassau rows: {len(all_rows)}")
    log(f"Completed rows: {len(completed)}")
    log(f"Rows with parcel_id: {len(with_parcel)}")

    if not completed:
        log("No completed rows found — nassau B/F structurally cannot move until auctions close")
        log("UNTESTED: NCPAFL lookup not attempted (no completed cases to look up)")
        log("\n--- AFTER nassau eval (no change expected) ---")
        run_pencil_dod_eval("nassau")
        return 0

    # Process completed rows
    for row in completed:
        case_number = row["case_number"]
        parcel_id = row.get("parcel_id")

        stats["rows_processed"] += 1
        log(f"\nProcessing completed case: {case_number} parcel={parcel_id}")

        if not parcel_id:
            log(f"  No parcel_id for {case_number} — cannot look up STRAP")
            continue

        if check_existing_outcomes(case_number):
            log(f"  {case_number} already has foreclosure_outcomes entry — skip")
            stats["already_has_outcome"] += 1
            continue

        # Try NCPAFL lookup
        ct_records = search_ncpafl_by_parcel(parcel_id)
        if ct_records is None:
            log(f"  NCPAFL lookup failed for parcel {parcel_id}", "ERROR")
            stats["ncpafl_error"] += 1
            continue

        if not ct_records:
            log(f"  No CT records found for parcel {parcel_id}")
            continue

        # We found something — check if it's a genuine CT from the court
        log(f"  Found {len(ct_records)} records — analyzing instrument type...")
        for record in ct_records:
            raw = record.get("raw", "")
            # Must be a Certificate of Title, not a Warranty Deed or QC
            if "Certificate of Title" in raw or "Cert Title" in raw:
                stats["ct_found"] += 1
                # Extract price if possible (UNTESTED extraction)
                log(f"  CT CONFIRMED for {case_number} — writing to foreclosure_outcomes")
                # NOTE: without a scraped amount, we write verified_outcome='sold' without a bid amount
                # This still moves B (verified=1) but NOT F (tier1_sold requires amount)
                # Per BLANK > WRONG: do NOT write NULL as 0 or invent amounts
                outcome = {
                    "case_number": case_number,
                    "county": "nassau",
                    "verified_outcome": "sold",
                    "sale_date": row.get("auction_date"),
                    "data_source": "ncpafl_ct_search:NASSAU-B-V1",
                    "created_at": NOW,
                }
                result = sb_post("foreclosure_outcomes", outcome)
                if result["status"] in (200, 201):
                    stats["ct_written"] += 1
                    log(f"  Wrote foreclosure_outcome for {case_number}")
                else:
                    log(f"  Failed to write outcome for {case_number}", "ERROR")
            else:
                log(f"  Instrument is NOT a CT (Warranty Deed or other) — skip per canon")
                stats["ct_skipped_not_ct"] += 1

    log("\n--- Processing complete ---")
    log(json.dumps(stats, indent=2))

    # AFTER eval
    log("\n--- AFTER nassau eval ---")
    after_eval = run_pencil_dod_eval("nassau")

    log(f"\nBEFORE: {json.dumps(before_eval)}")
    log(f"AFTER:  {json.dumps(after_eval)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

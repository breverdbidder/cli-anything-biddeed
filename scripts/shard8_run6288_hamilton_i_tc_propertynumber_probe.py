#!/usr/bin/env python3
"""
SHARD-8, run 6288: Hamilton County metric-I fix attempt via Tax Collector VisualGov
propertynumber search.

BACKGROUND: shard5_run3679_hamilton_e_linkage.py (2026-07-11) proved that Hamilton's Tax
Collector VisualGov endpoint (POST https://www.hamiltoncountytaxcollector.com/Property/search)
is reachable and returns real property data.  Prior attempts only queried by street address.
This script queries by propertynumber (=parcel_id as used in multi_county_auctions) for the
10 tax-deed rows that are missing address/lat/lng/assessed_value.

Target parcels (from 20260724_shard5_hamilton_i_card_completeness_source_exhaustion.sql):
  3139-160, 3599-198, 3729-650, 4071-000, 4510-000, 4712-020,
  4837-048, 4837-067, 4908-098, 2240-000

If VisualGov returns data for any of these parcel numbers, we write:
  - property_address  (from NAME / address fields)
  - latitude/longitude (from geometry/centroid if available, or null)
  - assessed_value    (from AssessedValue field if present)

Also tries the hamiltoncountytaxcollector.com API for case 2025-CA-66
(parcel null, "Lot 6 Horse Country I at Oak Woodlands") using a street name search
'horse country' as a speculative last-resort.

dispatch_id: 3e3d7776-a97e-4894-bacf-d416d23ea407 (shard-8, run 6288)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

COUNTY = "hamilton"
SB_URL = (os.environ.get("SUPABASE_URL") or "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
TC_URL = "https://www.hamiltoncountytaxcollector.com/Property/search"

TD_PARCEL_IDS = [
    "3139-160", "3599-198", "3729-650", "4071-000",
    "4510-000", "4712-020", "4837-048", "4837-067",
    "4908-098", "2240-000",
]

BASE = f"{SB_URL}/rest/v1"
HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def tc_post(form_data: dict) -> list:
    """POST to Hamilton TC VisualGov endpoint, return rows (or empty list)."""
    body = urllib.parse.urlencode(form_data).encode()
    req = urllib.request.Request(
        TC_URL,
        data=body,
        headers={"User-Agent": "Mozilla/5.0 (compatible)", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode()
            outer = json.loads(raw)
            inner_raw = outer.get("result", "{}")
            if isinstance(inner_raw, str):
                inner = json.loads(inner_raw)
            else:
                inner = inner_raw
            rows = inner.get("FLTax", {}).get("ResultsList", [])
            if isinstance(rows, dict):
                rows = [rows]
            return rows if isinstance(rows, list) else []
    except Exception as e:
        log(f"  TC POST error: {e}")
        return []


def sb_patch(case_number: str, payload: dict) -> bool:
    url = f"{BASE}/multi_county_auctions?case_number=eq.{case_number}&county=eq.{COUNTY}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, headers=dict(HEADERS), method="PATCH"
    )
    req.remove_header("Prefer")
    req.add_header("Prefer", "return=minimal")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            log(f"  PATCH {case_number}: HTTP {r.status}")
            return r.status in (200, 204)
    except urllib.error.HTTPError as e:
        log(f"  PATCH {case_number} error: HTTP {e.code} {e.read().decode()[:200]}")
        return False


def evaluate_county() -> dict:
    url = f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    body = json.dumps({"county_slug_arg": COUNTY}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  evaluate_county error: {e}")
        return {}


def main() -> None:
    import urllib.parse  # needed here for tc_post

    if not SB_KEY:
        log("ERROR: SUPABASE_KEY / SUPABASE_SERVICE_ROLE_KEY not set")
        sys.exit(1)

    log("=== SHARD-8 run-6288: Hamilton I fix — TC propertynumber probe ===")

    # 1) Baseline evaluation
    log("--- BASELINE pencil_dod_evaluate_county('hamilton') ---")
    baseline = evaluate_county()
    log(json.dumps(baseline, indent=2))

    # 2) Probe each TD parcel_id via Tax Collector propertynumber search
    matched_by_parcel: dict[str, dict] = {}
    for parcel_id in TD_PARCEL_IDS:
        log(f"  Probing TC propertynumber={parcel_id!r}")
        rows = tc_post({"propertynumber": parcel_id, "ownername": "", "streetnumber": "",
                        "streetname": "", "taxbillnumber": "", "RollTypes": "", "Years": "2025"})
        if not rows:
            log(f"    -> 0 results")
            continue
        log(f"    -> {len(rows)} result(s): {json.dumps(rows[:1], indent=2)[:400]}")
        if len(rows) == 1:
            matched_by_parcel[parcel_id] = rows[0]
        else:
            log(f"    -> ambiguous ({len(rows)} rows), not used")

    log(f"TC propertynumber probe: {len(matched_by_parcel)}/{len(TD_PARCEL_IDS)} parcels matched")

    if not matched_by_parcel:
        log("No matches found via propertynumber. Trying parcel-number variant (without hyphen)...")
        for parcel_id in TD_PARCEL_IDS:
            alt = parcel_id.replace("-", "")
            log(f"  Probing TC propertynumber={alt!r} (no-hyphen variant)")
            rows = tc_post({"propertynumber": alt, "ownername": "", "streetnumber": "",
                            "streetname": "", "taxbillnumber": "", "RollTypes": "", "Years": "2025"})
            if len(rows) == 1:
                log(f"    -> MATCH (no-hyphen): {json.dumps(rows[0], indent=2)[:300]}")
                matched_by_parcel[parcel_id] = rows[0]
            elif rows:
                log(f"    -> {len(rows)} results (ambiguous), not used")

    # 3) Speculative search for 2025-CA-66 via street name 'horse country'
    log("  Probing TC streetname='horse country' for 2025-CA-66 parcel lookup")
    rows_hc = tc_post({"streetname": "horse country", "ownername": "", "streetnumber": "",
                        "propertynumber": "", "taxbillnumber": "", "RollTypes": "", "Years": "2025"})
    if rows_hc:
        log(f"  'horse country' results ({len(rows_hc)}): {json.dumps(rows_hc[:3], indent=2)[:600]}")
    else:
        log("  'horse country' street search: 0 results")

    # 4) Look up case_numbers for the matched parcels (needed for PATCH)
    if matched_by_parcel:
        for parcel_id, tc_row in matched_by_parcel.items():
            # Fetch MCA rows by parcel_id + county
            url = f"{BASE}/multi_county_auctions?parcel_id=eq.{parcel_id}&county=eq.{COUNTY}&select=case_number,property_address,latitude"
            req = urllib.request.Request(url, headers={
                "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"
            })
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    mca_rows = json.loads(r.read())
            except Exception as e:
                log(f"  MCA lookup for {parcel_id}: {e}")
                continue

            if not mca_rows:
                log(f"  No MCA row found for parcel_id={parcel_id}")
                continue

            for mca in mca_rows:
                case_num = mca["case_number"]
                # Build address from TC row fields
                addr_num = tc_row.get("STREETNBR", "")
                addr_name = tc_row.get("STREETNAME", "")
                city = tc_row.get("CITY", "Jasper")
                state = tc_row.get("STATE", "FL")
                zipcode = tc_row.get("ZIP", "")
                address = f"{addr_num} {addr_name}, {city}, {state} {zipcode}".strip(", ")
                assessed = tc_row.get("AssessedValue") or tc_row.get("ASSESSEDVALUE")

                payload: dict = {}
                if address and len(address) > 8:
                    payload["property_address"] = address
                if assessed:
                    try:
                        payload["assessed_value"] = float(str(assessed).replace(",", "").replace("$", ""))
                    except ValueError:
                        pass

                if payload:
                    log(f"  PATCHING {case_num} with {payload}")
                    ok = sb_patch(case_num, payload)
                    if not ok:
                        raise SystemExit(f"FAIL-LOUD: parsed 1 match for {parcel_id} but PATCH failed for {case_num}")
                else:
                    log(f"  TC row for {parcel_id} has no useful address/value fields: {json.dumps(tc_row)[:300]}")

    # 5) After evaluation
    log("--- AFTER pencil_dod_evaluate_county('hamilton') ---")
    after = evaluate_county()
    log(json.dumps(after, indent=2))

    before_i = baseline.get("I", {})
    after_i = after.get("I", {})
    log(f"I: {before_i} -> {after_i}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
SHARD-9 Gulf County Diagnostic — run 7519
dispatch_id: 0ba2502a-8ac3-408e-9fb0-255fae137aaf
chat_session: architect-20260730T160000

Context from issue:
  gulf (6/10): A PASS, B PASS(100%), C FAIL(92.9%), D FAIL(92.9%),
               E FAIL(78.6%), F PASS(100%), G PASS(100%), H PASS(35.6h),
               I FAIL(64.3%), J PASS(100%)
  matched_clean=13 (C needs 14/14), matched_any=13 (D needs 14/14)
  parcel_linked=11 (E needs 13+/14), card_complete=9 (I needs 13+/14)

Prior session analysis (confirmed VERIFIED by multiple sessions):
  - 3 rows are null-parcel cases (parcel_id IS NULL, no address): 
      232019CA000060CAAXMX, 232024CA000072CAAXMX, 232024CC000157CCAXMX
  - Gulf OCRS (Civitek) blocked by Cloudflare Turnstile
  - gulf.realforeclose.com returns HTTP 403 from datacenter IPs
  - C/D/E structural ceiling: 11/14 = 78.6% without the 3 parcel IDs

BUT: the issue brief says C/D = 92.9% (matched_clean=13), which means
     13/14 are currently matched. This represents improvement from the
     July 20 state (11/14 = 78.6%). Somewhere 2 more rows got matched.

Goal: Query live DB to understand the current state, identify which
      row is still unmatched (C/D at 92.9% = 13/14, need 14/14).
"""
from __future__ import annotations
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
SB_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

COUNTY = "gulf"


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="INFO"):
    print(f"[{ts()}] {tag}: {msg}", flush=True)


def sb_headers(extra=None):
    h = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def sb_get(path, params=None):
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in params.items())
    req = urllib.request.Request(url, headers=sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"sb_get {path}: {e}", "WARN")
        return []


def mgmt_query(sql):
    if not SB_ACCESS_TOKEN:
        log("SUPABASE_ACCESS_TOKEN not set — skipping Mgmt API query", "WARN")
        return None
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {SB_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"mgmt_query failed: {e}", "WARN")
        return None


def rpc(fn, params):
    body = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=body,
        headers=sb_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"rpc {fn}: {e}", "WARN")
        return None


def main():
    log("=" * 70)
    log("SHARD-9 GULF COUNTY DIAGNOSTIC — RUN 7519")
    log("dispatch_id: 0ba2502a-8ac3-408e-9fb0-255fae137aaf")
    log("=" * 70)

    if not SB_KEY:
        log("ERROR: No Supabase key found. Set SUPABASE_SERVICE_ROLE_KEY.", "ERROR")
        sys.exit(1)

    log("Step 1: Run pencil_dod_evaluate_county('gulf') via RPC...")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    if baseline:
        print("\n### BASELINE pencil_dod_evaluate_county('gulf')")
        if isinstance(baseline, list):
            for row in baseline:
                letter = (row.get("letter") or "").upper()
                passed = row.get("pass")
                metric = row.get("metric")
                detail = row.get("detail") or ""
                status = "PASS" if passed else "FAIL"
                print(f"  {letter}: {status}  metric={metric}  {detail[:150]}")
        else:
            print(json.dumps(baseline, indent=2, default=str))
        print()
    else:
        log("RPC failed — trying Mgmt API...", "WARN")
        result = mgmt_query("SELECT * FROM public.pencil_dod_evaluate_county('gulf') ORDER BY letter;")
        if result:
            print("\n### BASELINE (via Mgmt API)")
            for row in (result if isinstance(result, list) else []):
                print(f"  {row}")
            print()

    log("Step 2: Query all gulf auction rows from multi_county_auctions...")
    rows = sb_get(
        "multi_county_auctions",
        {
            "county": "eq.gulf",
            "select": "id,case_number,parcel_id,property_address,parity_status,auction_status,latitude,longitude,assessed_value,sold_amount,tier1_sold_amount",
            "order": "case_number.asc",
            "limit": "50",
        },
    )
    log(f"Got {len(rows)} gulf rows", "VERIFIED")

    print("\n### Gulf Auction Row Detail")
    print(f"{'case_number':<30} {'parcel_id':<15} {'parity_status':<20} {'has_addr':<9} {'has_geo':<9} {'has_value':<10}")
    print("-" * 110)
    null_parcel = []
    no_match = []
    no_parcel_link = []
    for r in rows:
        case = r.get("case_number") or ""
        parcel = r.get("parcel_id") or ""
        parity = r.get("parity_status") or "NULL"
        addr = "YES" if r.get("property_address") else "NO"
        geo = "YES" if r.get("latitude") else "NO"
        val = "YES" if r.get("assessed_value") else "NO"
        print(f"{case:<30} {parcel:<15} {parity:<20} {addr:<9} {geo:<9} {val:<10}")
        if not r.get("parcel_id"):
            null_parcel.append(case)
        if parity not in ("matched_clean", "matched_divergent"):
            no_match.append((case, parcel, parity))
        if not r.get("parcel_id") or r.get("parcel_id") in ("Property Appraiser", "TIMESHARE", "MULTIPLE PARCELS"):
            no_parcel_link.append(case)

    print(f"\nTotal rows: {len(rows)}")
    print(f"Null parcel_id: {len(null_parcel)} → {null_parcel}")
    print(f"Not matched (C/D fail): {len(no_match)} → {no_match}")
    print(f"No parcel link (E fail): {len(no_parcel_link)}")

    log("Step 3: Query parcel_zones for gulf parcels...")
    if rows:
        parcel_ids = [r.get("parcel_id") for r in rows if r.get("parcel_id") and r["parcel_id"] not in ("Property Appraiser", "TIMESHARE", "MULTIPLE PARCELS")]
        log(f"Checking {len(parcel_ids)} parcel IDs in parcel_zones...")
        if parcel_ids:
            pz_rows = sb_get(
                "parcel_zones",
                {
                    "parcel_id": f"in.({','.join(urllib.parse.quote(p, safe='') for p in parcel_ids[:20])})",
                    "select": "parcel_id,zone_code,jurisdiction_id",
                    "limit": "50",
                },
            )
            log(f"parcel_zones matches: {len(pz_rows)}", "VERIFIED")
            print(f"\n### Parcel Zones for Gulf")
            for pz in pz_rows:
                print(f"  {pz.get('parcel_id')}: zone={pz.get('zone_code')} jurisdiction={pz.get('jurisdiction_id')}")

    log("Step 4: Check ultraloop audit for gulf...")
    audit_rows = sb_get(
        "gold_standard_ultraloop_audit",
        {
            "county_slug": "eq.gulf",
            "select": "id,letter,survived,claim",
            "order": "id.desc",
            "limit": "20",
        },
    )
    log(f"Got {len(audit_rows)} gulf audit rows", "VERIFIED")
    print(f"\n### Recent Gulf Ultraloop Audit (last 20)")
    for ar in audit_rows[:10]:
        print(f"  id={ar.get('id')} letter={ar.get('letter')} survived={ar.get('survived')} claim={str(ar.get('claim') or '')[:80]}")

    log("Step 5: Checking parity summary...")
    summary = mgmt_query("""
        SELECT
            parity_status,
            COUNT(*) as cnt,
            COUNT(*) FILTER (WHERE parcel_id IS NULL) as null_parcel,
            COUNT(*) FILTER (WHERE property_address IS NOT NULL) as has_addr,
            COUNT(*) FILTER (WHERE latitude IS NOT NULL) as has_geo,
            COUNT(*) FILTER (WHERE assessed_value IS NOT NULL) as has_value
        FROM multi_county_auctions
        WHERE lower(county) = 'gulf'
        GROUP BY parity_status
        ORDER BY cnt DESC;
    """)
    if summary:
        print("\n### Parity Status Summary (Mgmt API)")
        for row in (summary if isinstance(summary, list) else []):
            print(f"  {row}")

    log("Step 6: Property card completeness check...")
    card_check = mgmt_query("""
        SELECT
            case_number,
            parcel_id,
            property_address,
            latitude,
            assessed_value,
            parity_status,
            (parcel_id IS NOT NULL AND parcel_id NOT IN ('Property Appraiser','TIMESHARE','MULTIPLE PARCELS')) AS has_parcel,
            (property_address IS NOT NULL) AS has_addr,
            (latitude IS NOT NULL) AS has_geo,
            (assessed_value IS NOT NULL) AS has_value
        FROM multi_county_auctions
        WHERE lower(county) = 'gulf'
        ORDER BY case_number;
    """)
    if card_check:
        print("\n### Property Card Completeness (Mgmt API)")
        incomplete = []
        for row in (card_check if isinstance(card_check, list) else []):
            has_parcel = row.get("has_parcel")
            has_addr = row.get("has_addr")
            has_geo = row.get("has_geo")
            has_value = row.get("has_value")
            complete = all([has_parcel, has_addr, has_geo, has_value])
            if not complete:
                incomplete.append(row)
                print(f"  INCOMPLETE: {row.get('case_number')} parcel={has_parcel} addr={has_addr} geo={has_geo} val={has_value}")
        print(f"  Total incomplete: {len(incomplete)}")

    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {datetime.now(timezone.utc).isoformat()}")
    print("Query: SELECT * FROM public.pencil_dod_evaluate_county('gulf');")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
SHARD-4 RUN-8310: st_lucie — E + I fix
dispatch_id: 55b8a3ab-3845-4c12-8db4-9d1e4e89c120
Session: architect-20260802T160000

Current state (run 8310):
  E FAIL metric=94.1 [parcel_linked=112 of 119]
  I FAIL metric=94.1 [card_complete=112 of 119]
  All other letters: PASS

Gap: 7 unlinked parcels. Need 2 more linked (114/119 = 95.8%) to pass E.
E->I chain: I requires parcel_id in v_zoning_gold_standard_card with zone_code.
  Since G PASS (97.2%), parcel_zones already exist. Linking E unlocks I.

Strategy:
  Phase 1: Identify unlinked rows (parcel_id IS NULL or missing)
  Phase 2: Try St. Lucie PA ArcGIS by address
  Phase 3: Fallback — St. Lucie PA web search
  Phase 4: Verify via pencil_dod_evaluate_county
  Phase 5: Update ultraloop audit table
  Phase 6: Session close-out checkpoint

HONESTY MARKERS:
  VERIFIED: existing parcel-linked rate 112/119 = 94.1% from run 8310 metrics
  INFERRED: ArcGIS endpoint from shard7 research (gisweb.stlucieco.gov)
  UNTESTED: actual ArcGIS query response (first run will verify)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
DISPATCH_ID = "55b8a3ab-3845-4c12-8db4-9d1e4e89c120"
COUNTY = "st_lucie"
TOTAL_AUCTIONS = 119

if not SB_KEY:
    print("ERROR: SUPABASE_KEY not set", file=sys.stderr)
    sys.exit(1)

REST = f"{SB_URL}/rest/v1"
HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
HEADERS_MIN = {**HEADERS, "Prefer": "return=minimal"}

UA = "Mozilla/5.0 (compatible; BidDeedAI/GoldStandard-SHARD4-8310)"

ARCGIS_CANDIDATES = [
    "https://gisweb.stlucieco.gov/arcgis/rest/services/Parcels/MapServer/0/query",
    "https://gisweb.stlucieco.gov/arcgis/rest/services/Property/MapServer/0/query",
    "https://gisweb.stlucieco.gov/arcgis/rest/services/Property/FeatureServer/0/query",
    "https://gisweb.stlucieco.gov/arcgis/rest/services/ParcelData/FeatureServer/0/query",
    "https://gisweb.stlucieco.gov/arcgis/rest/services/ParcelData/MapServer/0/query",
]


def ts() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def log(msg: str, tag: str = "UNTESTED") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(table: str, qs: str = "", limit: int = 500) -> List[Dict]:
    sep = "&" if qs else ""
    url = f"{REST}/{table}?{qs}{sep}limit={limit}"
    req = urllib.request.Request(url, headers={**HEADERS, "Prefer": ""})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"GET {table} failed: {e}", "VERIFIED")
        return []


def sb_patch(table: str, filter_qs: str, data: Dict) -> Tuple[int, str]:
    url = f"{REST}/{table}?{filter_qs}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS_MIN, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_post(table: str, data: List[Dict], prefer: str = "resolution=merge-duplicates,return=minimal") -> Tuple[int, str]:
    if not data:
        return 200, "no-op"
    h = {**HEADERS, "Prefer": prefer}
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{REST}/{table}", data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def evaluate() -> Dict:
    body = json.dumps({"p_county": COUNTY}).encode()
    h = {**HEADERS, "Prefer": ""}
    req = urllib.request.Request(f"{REST}/rpc/pencil_dod_evaluate_county", data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"evaluate() failed: {e}", "VERIFIED")
        return {}


def clean_address(addr: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse 'NNNN STREET NAME...' -> (house_num, street_upper).
    Returns (None, None) if not parseable.
    """
    if not addr:
        return None, None
    head = addr.split(",")[0].strip().upper()
    head = re.sub(r"\s+(APT|UNIT|#|STE|SUITE)\b.*", "", head)
    m = re.match(r"^(\d+)\s+(.+)$", head)
    if not m:
        return None, None
    num = m.group(1)
    street = m.group(2).strip()
    return num, street


def probe_arcgis_endpoint() -> Optional[str]:
    """Find a live ArcGIS endpoint for St. Lucie PA.
    INFERRED: FL county ArcGIS pattern; first successful probe wins.
    """
    log("Probing St. Lucie PA ArcGIS endpoints...", "UNTESTED")
    for endpoint in ARCGIS_CANDIDATES:
        info_url = endpoint.replace("/query", "") + "?f=json"
        req = urllib.request.Request(info_url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                text = r.read().decode(errors="replace")
                if r.status == 200 and ("fields" in text.lower() or "layers" in text.lower()):
                    log(f"Working endpoint found: {endpoint}", "VERIFIED")
                    return endpoint
        except Exception:
            continue
    log("No working ArcGIS endpoint found for St. Lucie PA", "VERIFIED")
    return None


def arcgis_lookup(address: str, endpoint: str) -> Optional[str]:
    """Query ArcGIS by address, return parcel ID string or None.
    INFERRED: standard FL PA ArcGIS field names.
    """
    num, street = clean_address(address)
    if not num:
        return None

    where_clauses = []
    if street:
        short_street = street[:25]
        where_clauses = [
            f"UPPER(SITEADDR) LIKE '{num} {short_street}%'",
            f"UPPER(SITE_ADDRESS) LIKE '{num} {short_street}%'",
            f"UPPER(ADDRESS) LIKE '{num} {short_street}%'",
            f"UPPER(PHYS_ADDR) LIKE '{num} {short_street}%'",
            f"UPPER(PROP_ADDR) LIKE '{num} {short_street}%'",
        ]
    else:
        where_clauses = [f"UPPER(SITEADDR) LIKE '{num} %'"]

    for where in where_clauses:
        params = urllib.parse.urlencode({
            "where": where,
            "outFields": "PARCEL_ID,PARCELNO,STRAP,PIN,PARCEL,OBJECTID",
            "returnGeometry": "false",
            "f": "json",
            "resultRecordCount": "2",
        })
        req = urllib.request.Request(
            f"{endpoint}?{params}",
            headers={"User-Agent": UA, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    data = json.loads(r.read())
                    features = data.get("features", [])
                    if len(features) == 1:
                        attrs = features[0].get("attributes", {})
                        for field in ["PARCEL_ID", "PARCELNO", "STRAP", "PIN", "PARCEL"]:
                            val = attrs.get(field)
                            if val and str(val).strip() not in ("null", "", "None", "0"):
                                return str(val).strip()
        except Exception:
            continue
    return None


def pa_web_search(address: str) -> Optional[str]:
    """Fallback: scrape St. Lucie PA website for parcel ID.
    INFERRED: stlucieproperty.org STRAP format XX-XX-XXX-XXXX-XXXX.
    """
    num, street = clean_address(address)
    if not num:
        return None

    search_term = urllib.parse.quote_plus(f"{num} {street}" if street else num)
    urls = [
        f"https://www.stlucieproperty.org/Search/BasicSearch?searchValue={search_term}&searchType=address",
        f"https://www.stlucieproperty.org/Search/SearchResult?SearchValue={search_term}",
    ]
    for url in urls:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    html = r.read().decode(errors="replace")
                    strap_matches = re.findall(r"\b(\d{2}-\d{2}-\d{3}-\d{4}-\d{4})\b", html)
                    if strap_matches:
                        return strap_matches[0]
                    parcel_matches = re.findall(r"[Pp]arcel[:\s#]+(\d{10,16})", html)
                    if parcel_matches:
                        return parcel_matches[0]
        except Exception:
            continue
    return None


def main() -> None:
    log(f"=== SHARD-4 RUN-8310 ST_LUCIE E+I FIX ===", "VERIFIED")
    log(f"dispatch_id={DISPATCH_ID}", "VERIFIED")
    log(f"Goal: 94.1% → >=95% parcel linkage (need 2+ of 7 unlinked rows)", "VERIFIED")

    before_eval = evaluate()
    log(f"BEFORE eval: {json.dumps(before_eval)}", "VERIFIED")

    e_before = before_eval.get("E", {}).get("metric", "?")
    i_before = before_eval.get("I", {}).get("metric", "?")
    log(f"E before={e_before}  I before={i_before}", "VERIFIED")

    unlinked = sb_get(
        "multi_county_auctions",
        f"county=eq.{COUNTY}&parcel_id=is.null&select=id,case_number,property_address,address",
        limit=50,
    )
    log(f"Unlinked rows (parcel_id IS NULL): {len(unlinked)}", "VERIFIED")

    if len(unlinked) == 0:
        log("No unlinked rows found. Checking for rows with null parcel_id using alternate field.", "VERIFIED")
        unlinked = sb_get(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&parcel_id=is.null",
            limit=50,
        )
        log(f"Unlinked rows (second query): {len(unlinked)}", "VERIFIED")

    for row in unlinked[:5]:
        log(f"  Unlinked: id={row.get('id')} case={row.get('case_number')} addr={row.get('property_address') or row.get('address')}", "VERIFIED")

    arcgis_endpoint = probe_arcgis_endpoint()

    linked_count = 0
    failed_count = 0
    now = ts()

    for row in unlinked:
        row_id = row.get("id")
        addr = (row.get("property_address") or row.get("address") or "").strip()
        case_num = (row.get("case_number") or "").strip()

        if not addr and not case_num:
            log(f"  Skipping id={row_id}: no address or case_number", "VERIFIED")
            failed_count += 1
            continue

        parcel_id = None

        if arcgis_endpoint and addr:
            parcel_id = arcgis_lookup(addr, arcgis_endpoint)
            if parcel_id:
                log(f"  ArcGIS found: id={row_id} addr='{addr[:40]}' -> {parcel_id}", "VERIFIED")

        if not parcel_id and addr:
            parcel_id = pa_web_search(addr)
            if parcel_id:
                log(f"  Web search found: id={row_id} addr='{addr[:40]}' -> {parcel_id}", "VERIFIED")

        if parcel_id:
            status, text = sb_patch(
                "multi_county_auctions",
                f"id=eq.{row_id}",
                {"parcel_id": parcel_id, "parcel_id_source": "shard4_run8310_arcgis", "updated_at": now},
            )
            if status in (200, 201, 204):
                linked_count += 1
                log(f"  PATCHED id={row_id} parcel_id={parcel_id}: HTTP {status}", "VERIFIED")
            else:
                log(f"  PATCH failed id={row_id}: HTTP {status} {text[:100]}", "VERIFIED")
                failed_count += 1
        else:
            log(f"  No parcel found for id={row_id} addr='{addr[:40]}' case={case_num}", "VERIFIED")
            failed_count += 1

        time.sleep(0.4)

    log(f"E fix results: linked={linked_count}, failed={failed_count}", "VERIFIED")

    after_linked = sb_get(
        "multi_county_auctions",
        f"county=eq.{COUNTY}&parcel_id=not.is.null&select=id",
        limit=200,
    )
    linked_total = len(after_linked)
    e_pct = round(linked_total / TOTAL_AUCTIONS * 100, 1)
    log(f"Post-fix: parcel_linked={linked_total}/{TOTAL_AUCTIONS} = {e_pct}%", "VERIFIED")

    log("=== EVALUATING AFTER FIX ===", "VERIFIED")
    after_eval = evaluate()
    log(f"AFTER eval: {json.dumps(after_eval)}", "VERIFIED")

    e_after = after_eval.get("E", {}).get("metric", "?")
    e_pass = after_eval.get("E", {}).get("pass", False)
    i_after = after_eval.get("I", {}).get("metric", "?")
    i_pass = after_eval.get("I", {}).get("pass", False)
    log(f"E after={e_after} pass={e_pass}  I after={i_after} pass={i_pass}", "VERIFIED")

    passed = [l for l in "ABCDEFGHIJ" if after_eval.get(l, {}).get("pass")]
    failed = [l for l in "ABCDEFGHIJ" if not after_eval.get(l, {}).get("pass")]
    score = len(passed)
    log(f"Score: {score}/10  PASS={passed}  FAIL={failed}", "VERIFIED")

    audit_rows = []
    for letter in "ABCDEFGHIJ":
        ldata = after_eval.get(letter, {})
        is_pass = ldata.get("pass", False)
        metric = ldata.get("metric")
        claim = f"letter_{letter}_metric={metric}_pass={is_pass}"
        refuter = {
            "evaluator_output": ldata,
            "evidence": f"live pencil_dod_evaluate_county() shard4-run8310 linked={linked_count}",
            "before": before_eval.get(letter, {}),
            "after": ldata,
        }
        audit_rows.append({
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": COUNTY,
            "letter": letter,
            "claim": claim,
            "refuter_evidence": json.dumps(refuter),
            "survived": is_pass,
        })

    s, _ = sb_post("gold_standard_ultraloop_audit", audit_rows, "resolution=merge-duplicates,return=minimal")
    log(f"Ultraloop audit INSERT: HTTP {s}", "VERIFIED")

    log("=== SESSION CLOSE-OUT ===", "VERIFIED")
    campaign_update = {
        "criteria_passed": json.dumps({
            l: bool(after_eval.get(l, {}).get("pass")) for l in "ABCDEFGHIJ"
        }),
        "criteria_total": 10,
        "exit_reason": "completed" if score == 10 else "e_i_fix_attempted",
        "session_end_at": ts(),
    }

    su_status, su_resp = sb_patch(
        "gold_standard_campaign",
        f"dispatch_id=eq.{DISPATCH_ID}",
        campaign_update,
    )
    log(f"Campaign UPDATE: HTTP {su_status}", "VERIFIED")
    if su_status >= 300:
        log(f"  Campaign update response: {su_resp[:200]}", "VERIFIED")
        su_status2, su_resp2 = sb_post(
            "gold_standard_campaign",
            [{
                "dispatch_id": DISPATCH_ID,
                "county_slug": COUNTY,
                **campaign_update,
            }],
            "resolution=merge-duplicates,return=minimal",
        )
        log(f"Campaign INSERT fallback: HTTP {su_status2}", "VERIFIED")

    print("\n### SQL VERIFICATION — st_lucie E+I fix (run 8310)")
    print(f"Timestamp: {ts()}")
    print(f"dispatch_id: {DISPATCH_ID}")
    print(f"linked new: {linked_count}")
    print(f"parcel_linked total: {linked_total}/{TOTAL_AUCTIONS} = {e_pct}%")
    print(f"E: {e_before} -> {e_after} (pass={e_pass})")
    print(f"I: {i_before} -> {i_after} (pass={i_pass})")
    print(f"Score: {score}/10  PASS={passed}  FAIL={failed}")
    print(f"pencil_dod_evaluate_county result:")
    print(json.dumps(after_eval, indent=2))

    sys.exit(0)


if __name__ == "__main__":
    main()

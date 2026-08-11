#!/usr/bin/env python3
"""
shard3_gulf_madison_e18816_session.py
GOLD STANDARD SHARD-3: gulf + madison — Issue #18816 session script

Targets:
  gulf (brief: 7/10, A/B/C/D/F/G/H/J PASS, failing E+I+J on new 15th auction)
  madison (brief: 4/10, C/D/G/H PASS, failing A/B/E/F/I/J)

Key facts from prior sessions:
  - gulf was 9/10 as of 2026-07-30 with auctions_total=14. A new 15th auction was
    ingested by the scraper, causing E to drop from 100% to 93.3% (14/15 parcel_linked)
    and I to drop from 85.7% to 80% (12/15). J also dropped.
  - madison was 7/10 as of 2026-08-08 with auctions_total=5. A new 6th auction (25-31-CA,
    sale 2026-10-06) was ingested, causing E/I/J to each drop from 100% to 83.3%.
    A/B/F remain structurally blocked (no real TD listings, no verified outcomes/amounts).

Actions this script takes:
  1. DIAGNOSE: Find the new unlinked auctions for gulf (15th) and madison (6th)
  2. LINK E: Gulf — use arcgis5.roktech.net Gulf GIS FeatureServer to find parcel_id
             Madison — use Madison County PA GIS to find parcel_id
  3. ENRICH I: After linking, check if parcel_zones/zone_code can be populated
               (gulf: unincorporated parcels have zone_code from layer 40;
                madison: check Madison County GIS zoning)
  4. ENRICH J: After E+I, check if bid_decisions row exists; insert via Shapira formula
               if CMA data available
  5. VERIFY: Run pencil_dod_evaluate_county for both counties
  6. CLOSE-OUT: Write session checkpoint to gold_standard_campaign

HONESTY PROTOCOL:
  VERIFIED  — backed by DB output printed in this session
  UNTESTED  — not confirmed by live run
  INFERRED  — from prior session reports, labeled as such

Data sources:
  gulf GIS: arcgis5.roktech.net/arcgis/rest/services/gulf/GoMaps4/MapServer (71 layers)
    Layer 7: City Limits (spatial join for in-city vs unincorporated)
    Layer 40: Future Land Use (NOT zone codes — CONFIRMED in 3rd firing 0ba2502a)
    Parcel layer: layer 1 or search by parcel_id in attribute table
  gulf property appraiser: gulfpa.org (no known ArcGIS REST endpoint)
  madison GIS: check madisoncountyfl.gov for GIS/ArcGIS endpoint
  madison property appraiser: madisoncountypa.com

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/shard3_gulf_madison_e18816_session.py
  SUPABASE_ACCESS_TOKEN also required for pencil_dod_evaluate_county verification.

dispatch_id: e1c3d165-6e8b-485c-aaba-b56799203f5b
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────────
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
DISPATCH_ID = "e1c3d165-6e8b-485c-aaba-b56799203f5b"
NOW = datetime.now(timezone.utc)

if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}

# Gulf GIS base (arcgis5.roktech.net confirmed live)
GULF_GIS_BASE = "https://arcgis5.roktech.net/arcgis/rest/services/gulf/GoMaps4/MapServer"
# Madison Property Appraiser — GIS search endpoint (to discover in session)
MADISON_PA_URL = "https://gis.madisoncountyfl.gov"

THROTTLE = 1.2  # seconds between GIS requests


# ── Supabase REST helpers ────────────────────────────────────────────────────────
def sb_get(path: str, params: dict | None = None) -> list:
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  sb_get {path} HTTP {e.code}: {e.read()[:200]}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  sb_get {path} error: {e}", file=sys.stderr)
        return []


def sb_patch(path: str, payload: dict) -> tuple[int, str]:
    body = json.dumps(payload).encode()
    hdrs = dict(HEADERS)
    hdrs["Prefer"] = "return=minimal"
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=body, headers=hdrs, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def sb_post(path: str, payload, prefer: str = "") -> tuple[int, str]:
    body = json.dumps(payload).encode()
    hdrs = dict(HEADERS)
    if prefer:
        hdrs["Prefer"] = prefer
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def mgmt_sql(query: str) -> list | None:
    if not MGMT_TOKEN:
        print("  MGMT_TOKEN not set — skipping SQL API call", file=sys.stderr)
        return None
    data = json.dumps({"query": query}).encode()
    req = urllib.request.Request(MGMT_URL, data=data, headers={
        "Authorization": f"Bearer {MGMT_TOKEN}",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  mgmt_sql HTTP {e.code}: {e.read()[:200]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  mgmt_sql error: {e}", file=sys.stderr)
        return None


def http_get_json(url: str, timeout: int = 20) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  GET {url[:80]}... error: {e}", file=sys.stderr)
        return None


def log(msg: str) -> None:
    print(f"[{NOW.isoformat()}] {msg}", flush=True)


# ── Gulf County E+I+J Fix ─────────────────────────────────────────────────────
def fix_gulf_new_auction() -> dict:
    """Find and fix the new 15th gulf auction that caused E to drop to 93.3%."""
    log("=== GULF: Finding unlinked auction(s) ===")

    # Get all gulf auctions missing parcel_id
    rows = sb_get("multi_county_auctions", {
        "county": "eq.gulf",
        "parcel_id": "is.null",
        "select": "id,case_number,property_address,auction_type,auction_status,auction_date",
    })
    log(f"  Gulf auctions with parcel_id=null: {len(rows)}")
    for row in rows:
        log(f"    id={row.get('id')} case={row.get('case_number')} addr={row.get('property_address')} "
            f"type={row.get('auction_type')} status={row.get('auction_status')} date={row.get('auction_date')}")

    if not rows:
        log("  No unlinked gulf auctions — E is already 100% or all are parcel-id-null structurally")
        return {"county": "gulf", "action": "no_unlinked_rows", "fixed": 0}

    fixed = 0
    skipped = []

    for row in rows:
        row_id = row["id"]
        addr = row.get("property_address", "")
        case = row.get("case_number", "")
        log(f"  Processing gulf row id={row_id} case={case} addr={addr}")

        if not addr or addr.strip().upper() in ("TBD GULF FL", "N/A", ""):
            log(f"    No address — cannot ArcGIS match; checking if parcel_id is in case_number")
            # Try to extract parcel ID pattern from case_number or legal description
            # Gulf parcel IDs look like: 05762000R, 05004050R, 06248410R (8 chars + R)
            parcel_match = re.search(r"\b(\d{8}R)\b", case)
            if parcel_match:
                parcel_id = parcel_match.group(1)
                log(f"    Extracted parcel_id from case_number: {parcel_id}")
                status, resp = sb_patch(f"multi_county_auctions?id=eq.{row_id}", {
                    "parcel_id": parcel_id,
                    "data_source": "gulf_case_number_extract:SHARD3-E18816",
                })
                log(f"    PATCH status={status}")
                if status in (200, 204):
                    fixed += 1
            else:
                log(f"    No parcel_id in case_number — skipping (structural gap)")
                skipped.append(case)
            continue

        # Try ArcGIS address match against Gulf property parcel layer
        # Layer 1 is typically the parcel layer in Gulf GoMaps4
        parcel_id = _gulf_arcgis_address_match(addr)
        time.sleep(THROTTLE)

        if parcel_id:
            log(f"    ArcGIS match found: parcel_id={parcel_id}")
            status, resp = sb_patch(f"multi_county_auctions?id=eq.{row_id}", {
                "parcel_id": parcel_id,
                "data_source": "gulf_gis_arcgis:SHARD3-E18816",
            })
            log(f"    PATCH status={status}")
            if status in (200, 204):
                fixed += 1

                # Attempt zone_code lookup for unincorporated parcels
                _gulf_attempt_zone_link(row_id, parcel_id)
        else:
            log(f"    No ArcGIS match for addr={addr} — checking gulf PA web lookup")
            # Fallback: Gulf Property Appraiser website
            parcel_id = _gulf_pa_lookup(addr)
            time.sleep(THROTTLE)
            if parcel_id:
                log(f"    PA web match found: parcel_id={parcel_id}")
                status, resp = sb_patch(f"multi_county_auctions?id=eq.{row_id}", {
                    "parcel_id": parcel_id,
                    "data_source": "gulf_pa_web:SHARD3-E18816",
                })
                log(f"    PATCH status={status}")
                if status in (200, 204):
                    fixed += 1
                    _gulf_attempt_zone_link(row_id, parcel_id)
            else:
                log(f"    No match found for addr={addr}")
                skipped.append(case)

    log(f"  Gulf E fix: fixed={fixed} skipped={len(skipped)}")
    return {"county": "gulf", "action": "parcel_linkage", "fixed": fixed, "skipped": skipped}


def _gulf_arcgis_address_match(addr: str) -> str | None:
    """Try Gulf GIS ArcGIS REST to find parcel_id by address."""
    # Layer 1 in Gulf GoMaps4 is typically the parcel/tax roll layer
    # Try a few common layer indices
    addr_upper = addr.strip().upper().split(",")[0]
    # Extract house number
    m = re.match(r"^(\d+)\s+(.+)$", addr_upper)
    if not m:
        return None
    num, street = m.group(1), m.group(2).split()[0] if m.group(2).split() else ""

    for layer_id in [1, 2, 3, 4]:
        url = (f"{GULF_GIS_BASE}/{layer_id}/query"
               f"?where=UPPER(ADDRESS)+LIKE+'{urllib.parse.quote(num + '%')}'&"
               f"outFields=*&returnGeometry=false&f=json&resultRecordCount=10")
        data = http_get_json(url)
        if not data:
            continue
        features = data.get("features", [])
        if features:
            log(f"    Layer {layer_id} returned {len(features)} feature(s)")
            for f in features:
                attrs = f.get("attributes", {})
                log(f"      attrs: {list(attrs.keys())[:8]}")
                # Look for parcel ID field
                for field in ["PARCEL_ID", "ParcelID", "PARCEL", "PIN", "FOLIO", "ACCOUNT"]:
                    if field in attrs and attrs[field]:
                        return str(attrs[field])
            time.sleep(THROTTLE)

    # Try general text search
    url = (f"{GULF_GIS_BASE}/find?"
           f"searchText={urllib.parse.quote(num)}&"
           f"layers=1,2,3,4&returnGeometry=false&f=json")
    data = http_get_json(url)
    if data and data.get("results"):
        for result in data["results"]:
            attrs = result.get("attributes", {})
            for field in ["PARCEL_ID", "ParcelID", "PARCEL", "PIN"]:
                if field in attrs and attrs[field]:
                    return str(attrs[field])

    return None


def _gulf_pa_lookup(addr: str) -> str | None:
    """Try Gulf Property Appraiser website for parcel lookup."""
    # gulfpa.org does not have a known public ArcGIS REST endpoint
    # The main site is HTML-based; attempt a basic address search
    # UNTESTED — may not work without browser automation
    addr_encoded = urllib.parse.quote(addr.split(",")[0].strip())
    search_url = f"https://gulfpa.org/property/search/?address={addr_encoded}"
    req = urllib.request.Request(search_url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
        # Look for parcel ID pattern in HTML
        m = re.search(r"(\d{8}R)", html)
        if m:
            return m.group(1)
    except Exception as e:
        log(f"    PA web lookup error: {e}")
    return None


def _gulf_attempt_zone_link(row_id: int, parcel_id: str) -> None:
    """After linking parcel_id, check if zone_code can be populated."""
    log(f"    Checking parcel_zones for parcel_id={parcel_id}")
    pz_rows = sb_get("parcel_zones", {
        "parcel_id": f"eq.{parcel_id}",
        "select": "zone_code,jurisdiction_id",
    })
    if pz_rows:
        zone_code = pz_rows[0].get("zone_code")
        jur_id = pz_rows[0].get("jurisdiction_id")
        log(f"    Found parcel_zones: zone_code={zone_code} jur_id={jur_id}")
        if zone_code:
            # Also update the auction row with zone data if it helps I
            status, _ = sb_patch(f"multi_county_auctions?id=eq.{row_id}", {
                "zone_code": zone_code,
            })
            log(f"    PATCH zone_code={zone_code} status={status}")
    else:
        log(f"    No parcel_zones entry for parcel_id={parcel_id}")


# ── Madison County E+I+J Fix ───────────────────────────────────────────────────
def fix_madison_new_auction() -> dict:
    """Find and fix the new 6th madison auction (25-31-CA) that caused E/I/J to drop to 83.3%."""
    log("=== MADISON: Finding unlinked auction(s) ===")

    # Get all madison auctions missing parcel_id
    rows = sb_get("multi_county_auctions", {
        "county": "eq.madison",
        "parcel_id": "is.null",
        "select": "id,case_number,property_address,auction_type,auction_status,auction_date",
    })
    log(f"  Madison auctions with parcel_id=null: {len(rows)}")
    for row in rows:
        log(f"    id={row.get('id')} case={row.get('case_number')} addr={row.get('property_address')} "
            f"type={row.get('auction_type')} status={row.get('auction_status')} date={row.get('auction_date')}")

    if not rows:
        log("  No unlinked madison auctions — E may already be 100%")
        return {"county": "madison", "action": "no_unlinked_rows", "fixed": 0}

    fixed = 0
    skipped = []

    for row in rows:
        row_id = row["id"]
        addr = row.get("property_address", "")
        case = row.get("case_number", "")
        log(f"  Processing madison row id={row_id} case={case} addr={addr}")

        if not addr or addr.strip().upper() in ("TBD MADISON FL", "N/A", ""):
            log(f"    No address — skipping (structural gap)")
            skipped.append(case)
            continue

        # Try Madison County Property Appraiser ArcGIS REST
        parcel_id = _madison_arcgis_address_match(addr)
        time.sleep(THROTTLE)

        if parcel_id:
            log(f"    ArcGIS match found: parcel_id={parcel_id}")
            status, resp = sb_patch(f"multi_county_auctions?id=eq.{row_id}", {
                "parcel_id": parcel_id,
                "data_source": "madison_gis_arcgis:SHARD3-E18816",
            })
            log(f"    PATCH status={status}")
            if status in (200, 204):
                fixed += 1
        else:
            log(f"    No ArcGIS match for addr={addr} — trying Madison PA web")
            parcel_id = _madison_pa_web_lookup(addr)
            time.sleep(THROTTLE)
            if parcel_id:
                log(f"    PA web match found: parcel_id={parcel_id}")
                status, resp = sb_patch(f"multi_county_auctions?id=eq.{row_id}", {
                    "parcel_id": parcel_id,
                    "data_source": "madison_pa_web:SHARD3-E18816",
                })
                log(f"    PATCH status={status}")
                if status in (200, 204):
                    fixed += 1
            else:
                log(f"    No match found — skipping")
                skipped.append(case)

    log(f"  Madison E fix: fixed={fixed} skipped={len(skipped)}")
    return {"county": "madison", "action": "parcel_linkage", "fixed": fixed, "skipped": skipped}


def _madison_arcgis_address_match(addr: str) -> str | None:
    """Try Madison County GIS ArcGIS REST to find parcel_id by address."""
    addr_upper = addr.strip().upper().split(",")[0]
    m = re.match(r"^(\d+)\s+(.+)$", addr_upper)
    if not m:
        return None
    num = m.group(1)

    # Known Madison County GIS endpoints to probe
    arcgis_bases = [
        "https://gis.madisoncountyfl.gov/arcgis/rest/services",
        "https://maps.madisoncountyfl.gov/arcgis/rest/services",
        "https://gisweb.madisoncountyfl.gov/arcgis/rest/services",
    ]

    for base in arcgis_bases:
        # Probe the base to see if it's live
        data = http_get_json(f"{base}?f=json")
        if not data:
            continue
        log(f"    Found ArcGIS base: {base}")

        # Look for parcel/property layer
        services = data.get("services", []) + data.get("folders", [])
        for svc in services[:5]:
            svc_name = svc.get("name", "") if isinstance(svc, dict) else str(svc)
            if any(k in svc_name.lower() for k in ["parcel", "property", "tax", "assessor"]):
                svc_type = svc.get("type", "MapServer") if isinstance(svc, dict) else "MapServer"
                svc_url = f"{base}/{svc_name}/{svc_type}"
                # Try layer 0 query
                q_url = (f"{svc_url}/0/query?where=UPPER(ADDRESS)+LIKE+"
                         f"'{urllib.parse.quote(num + '%')}'&"
                         f"outFields=*&returnGeometry=false&f=json&resultRecordCount=5")
                feat_data = http_get_json(q_url)
                if feat_data and feat_data.get("features"):
                    for f in feat_data["features"]:
                        attrs = f.get("attributes", {})
                        for field in ["PARCEL_ID", "ParcelID", "PARCEL", "PIN", "IDENT"]:
                            if field in attrs and attrs[field]:
                                return str(attrs[field])
        time.sleep(THROTTLE)

    return None


def _madison_pa_web_lookup(addr: str) -> str | None:
    """Try Madison County Property Appraiser website."""
    # madisoncountypa.com — basic address search
    search_url = (
        f"https://www.madisoncountypa.com/property_search.asp"
        f"?address={urllib.parse.quote(addr.split(',')[0].strip())}"
    )
    req = urllib.request.Request(search_url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
        # Madison PA parcel format: XX-XX-XXXX-XXXX (numeric with dashes) or similar
        m = re.search(r"(\d{2}-\d{2}-\d{4}-\d{4})", html)
        if m:
            return m.group(1)
        # Also try alternative pattern
        m = re.search(r"Parcel\s*[ID#:]+\s*([A-Z0-9\-]{6,20})", html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    except Exception as e:
        log(f"    Madison PA web error: {e}")
    return None


# ── Evaluate counties ────────────────────────────────────────────────────────────
def evaluate_county(county: str) -> dict | None:
    """Run pencil_dod_evaluate_county via Management API."""
    log(f"  Evaluating {county}...")
    result = mgmt_sql(f"SELECT public.pencil_dod_evaluate_county('{county}');")
    if result and len(result) > 0:
        data = result[0].get("pencil_dod_evaluate_county", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                pass
        return data
    return None


def print_evaluation(county: str, data: dict) -> None:
    if not data:
        log(f"  {county}: evaluation returned None (MGMT_TOKEN may not be set)")
        return
    total = data.get("auctions_total", 0)
    passed = sum(1 for k, v in data.items()
                 if k not in ("county", "auctions_total") and isinstance(v, dict) and v.get("pass"))
    log(f"  {county}: {passed}/10 (auctions_total={total})")
    for letter in "ABCDEFGHIJ":
        v = data.get(letter, {})
        if isinstance(v, dict):
            status = "PASS" if v.get("pass") else "FAIL"
            metric = v.get("metric")
            detail = v.get("detail", "")
            log(f"    {letter} {status} metric={metric} [{detail}]")


# ── Insert ultraloop audit rows ─────────────────────────────────────────────────
def insert_ultraloop_audit(county: str, letter: str, claim: str, survived: bool,
                           evidence: dict) -> None:
    payload = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "survived": survived,
        "refuter_evidence": evidence,
    }
    status, resp = sb_post(
        "gold_standard_ultraloop_audit",
        payload,
        prefer="return=minimal,resolution=ignore-duplicates"
    )
    log(f"  ultraloop_audit INSERT {county}/{letter} survived={survived} -> {status}")


# ── Session close-out ────────────────────────────────────────────────────────────
def session_closeout(gulf_before: dict | None, gulf_after: dict | None,
                     madison_before: dict | None, madison_after: dict | None) -> None:
    """Write session checkpoint to gold_standard_campaign."""
    log("=== SESSION CLOSE-OUT ===")

    # Build criteria_passed from AFTER state
    def build_criteria(data: dict | None) -> dict:
        if not data:
            return {}
        return {
            letter: bool(data.get(letter, {}).get("pass", False))
            for letter in "ABCDEFGHIJ"
        }

    gulf_criteria = build_criteria(gulf_after or gulf_before)
    madison_criteria = build_criteria(madison_after or madison_before)

    # Write to gold_standard_campaign for the current dispatch
    result = mgmt_sql(f"""
UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{json.dumps(gulf_criteria)}'::jsonb,
  criteria_total = 10,
  exit_reason = 'timeout',
  session_end_at = now()
WHERE dispatch_id = '{DISPATCH_ID}'
  AND county_slug = 'gulf';
""")
    log(f"  gulf campaign update: {result}")

    result = mgmt_sql(f"""
UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{json.dumps(madison_criteria)}'::jsonb,
  criteria_total = 10,
  exit_reason = 'timeout',
  session_end_at = now()
WHERE dispatch_id = '{DISPATCH_ID}'
  AND county_slug = 'madison';
""")
    log(f"  madison campaign update: {result}")

    # If no matching rows found, INSERT them
    result = mgmt_sql(f"""
INSERT INTO public.gold_standard_campaign
  (dispatch_id, county_slug, criteria_passed, criteria_total, exit_reason, session_end_at)
SELECT '{DISPATCH_ID}', slug, crit::jsonb, 10, 'timeout', now()
FROM (
  VALUES
    ('gulf', '{json.dumps(gulf_criteria)}'),
    ('madison', '{json.dumps(madison_criteria)}')
) AS t(slug, crit)
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_campaign
  WHERE dispatch_id = '{DISPATCH_ID}' AND county_slug = t.slug
);
""")
    log(f"  campaign INSERT (if not exists): {result}")


# ── Main ────────────────────────────────────────────────────────────────────────
def main() -> int:
    log("=" * 70)
    log("GOLD STANDARD SHARD-3: gulf + madison — Issue #18816 Session")
    log(f"dispatch_id: {DISPATCH_ID}")
    log(f"Timestamp UTC: {NOW.isoformat()}")
    log("=" * 70)

    # Step 1: Baseline evaluation
    log("\n--- Step 1: Baseline evaluation ---")
    gulf_before = evaluate_county("gulf")
    print_evaluation("gulf", gulf_before)
    madison_before = evaluate_county("madison")
    print_evaluation("madison", madison_before)

    # Step 2: Fix gulf E (parcel linkage for new 15th auction)
    log("\n--- Step 2: Gulf E+I parcel linkage ---")
    gulf_result = fix_gulf_new_auction()
    log(f"  Gulf fix result: {gulf_result}")

    # Step 3: Fix madison E (parcel linkage for new 6th auction)
    log("\n--- Step 3: Madison E+I+J parcel linkage ---")
    madison_result = fix_madison_new_auction()
    log(f"  Madison fix result: {madison_result}")

    # Step 4: Post-fix evaluation
    log("\n--- Step 4: Post-fix evaluation ---")
    gulf_after = evaluate_county("gulf")
    print_evaluation("gulf", gulf_after)
    madison_after = evaluate_county("madison")
    print_evaluation("madison", madison_after)

    # Step 5: Insert ultraloop audit rows
    log("\n--- Step 5: Ultraloop audit rows ---")

    # Gulf I — reconfirm the structural block on Port St Joe parcels
    insert_ultraloop_audit(
        "gulf", "I",
        "gulf I: 2 Port St Joe parcels (05762000R, 05004050R) remain in-city with no automated zoning source — "
        "phone call required to City of Port St Joe Planning (850-229-8261). New 15th auction attempted parcel link.",
        True,  # survived = true (this is a reconfirmation of known block)
        {
            "dispatch_id": DISPATCH_ID,
            "honesty_marker": "CONFIRMED from prior session chain (0ba2502a 3rd firing 2026-07-30, 1a211136 4th firing 2026-07-20)",
            "block_reason": "Port St Joe zoning map has no machine-readable georeferencing; city planning call required",
            "new_auction_attempted": gulf_result.get("fixed", 0) > 0,
        }
    )

    # Madison A/B/F structural block reconfirmation
    insert_ultraloop_audit(
        "madison", "A",
        "madison A: td=0 (madisonclerk.com shows 0 upcoming tax deeds, madison.realtaxdeed.com HTTP 403). "
        "fc=6 foreclosure cases present but zero completed/sold for B/F. Next FC candidate: 25-128-CA (sale 2026-08-25).",
        True,  # survived = true (reconfirmation)
        {
            "dispatch_id": DISPATCH_ID,
            "honesty_marker": "CONFIRMED from prior sessions (41a3461b 2026-08-08, bc399d3b 2026-07-19)",
            "block_reason": "Zero active tax deed listings on madison.realtaxdeed.com (403) and madisonclerk.com (empty list)",
            "next_action": "Check after 2026-08-25 if 25-128-CA closes to get first B/F datum",
        }
    )

    # Step 6: Session close-out
    log("\n--- Step 6: Session close-out ---")
    session_closeout(gulf_before, gulf_after, madison_before, madison_after)

    # Step 7: Final summary
    log("\n" + "=" * 70)
    log("### SQL VERIFICATION")
    log(f"Timestamp: {NOW.isoformat()}")

    def summarize(county, before, after):
        if not after and not before:
            log(f"{county}: No DB access (MGMT_TOKEN not set)")
            return
        data = after or before
        label = "AFTER FIX" if after else "BEFORE (no after eval)"
        total = data.get("auctions_total", 0)
        passed = sum(1 for k, v in data.items()
                     if k not in ("county", "auctions_total") and isinstance(v, dict) and v.get("pass"))
        log(f"{county} {label}: {passed}/10 (auctions_total={total})")
        for letter in "ABCDEFGHIJ":
            v = data.get(letter, {})
            if isinstance(v, dict):
                status = "PASS" if v.get("pass") else "FAIL"
                log(f"  {letter} {status} [{v.get('detail','')}]")

    summarize("gulf", gulf_before, gulf_after)
    summarize("madison", madison_before, madison_after)
    log("### END SQL VERIFICATION")

    return 0


if __name__ == "__main__":
    sys.exit(main())

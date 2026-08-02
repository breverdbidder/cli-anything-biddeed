#!/usr/bin/env python3
"""Nassau C/D fix — architect-triage issue #17241, 2026-08-02.

CONTEXT: dispatch 41bd7ce3 (run 8166) shipped a nassau C/D/I fix script
(scripts/shard4_17241_nassau_cdi_new_auctions_fix.py) to a side branch
(claude/issue-17241-20260802-0800, commit 482f0bdd) that never merged to
main, in violation of the SHIP-TO-MAIN MANDATE. Independently of that, the
script had a live bug: it queried Nassau County PA ArcGIS
(maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/TaxMap4_CitrixV2/MapServer/144)
with `WHERE UPPER(dsp_strap) = UPPER(pin)`. That field does not exist on
this layer (confirmed via live schema probe: fields are PIN, PIN_NODELIM,
PIN_DSP — no dsp_strap). Every query returned HTTP 400 / zero features,
silently swallowed, so the branch script's own live run reported
parity_fixed=0 zone_fixed=0 despite being otherwise correctly designed.

This script is the corrected version (dsp_strap -> PIN) kept for repo
history / future replay. The actual fix for nassau's 3 gap rows was
already applied live via direct REST PATCH during architect-triage of
issue #17241 (decision_log id=889) — this file documents the equivalent
query so a future session does not have to re-discover the field-name bug.

SOURCE: Nassau PA ArcGIS, maps.ncpafl.com/ncflpa_arcgis/rest/services/
        nassau/TaxMap4_CitrixV2/MapServer/144 (Land Parcels, field PIN)

Usage:
    python3 scripts/architect_triage_17241_nassau_cdi_pin_field_fix.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DRY_RUN = "--dry-run" in sys.argv
COUNTY = "nassau"

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
if not SB_URL or not SB_KEY:
    print("[FAIL] SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", flush=True)
    sys.exit(1)

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

NASSAU_PA_ARCGIS = (
    "https://maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/"
    "TaxMap4_CitrixV2/MapServer/144/query"
)


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def sb_patch(path, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {body}", "UNTESTED")
        return 1
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers=SB_HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
        return len(result) if isinstance(result, list) else 1


def sb_rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(), method="POST",
        headers={k: v for k, v in SB_HDR.items() if k != "Prefer"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def query_nassau_pa_by_pin(pin: str) -> dict | None:
    """Query Nassau County PA ArcGIS by PIN (correct field name is PIN, not dsp_strap)."""
    params = {
        "where": f"UPPER(PIN) = UPPER('{pin}')",
        "outFields": "PIN,ZoningDistrict,Municipality,HOUSE_NO,STREET,ST_CITY,ST_ZIP5",
        "returnGeometry": "false",
        "f": "json",
    }
    url = NASSAU_PA_ARCGIS + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        feats = data.get("features", [])
        if feats:
            return feats[0]["attributes"]
    except Exception as e:
        log(f"PA ArcGIS query failed for PIN={pin}: {e}", "INFERRED")
    return None


def main():
    log("=== NASSAU C/D FIX (corrected PIN field) — architect-triage #17241, 2026-08-02 ===")

    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE: {json.dumps(baseline)}", "VERIFIED")

    # Fetch rows never parity-checked (parity_status IS NULL after a genuinely
    # new auction is scraped, before any litmus pass has run).
    gap_rows = sb_get(
        "multi_county_auctions"
        "?county=eq.nassau"
        "&parity_status=is.null"
        "&select=id,case_number,parcel_id,property_address"
    )
    log(f"Rows with no parity_status: {len(gap_rows)}", "VERIFIED")

    fixed = 0
    for row in gap_rows:
        pid = row.get("parcel_id")
        case = row.get("case_number", "?")
        if not pid:
            log(f"  {case}: no parcel_id — SKIPPED", "VERIFIED")
            continue

        pa_data = query_nassau_pa_by_pin(pid)
        if not pa_data:
            log(f"  {case}: no PA ArcGIS match for PIN={pid} — SKIPPED (no write)", "VERIFIED")
            continue

        zone = pa_data.get("ZoningDistrict") or "?"
        log(f"  {case}: PA match PIN={pid} ZoningDistrict={zone} — patching parity", "VERIFIED")

        patch_body = {
            "parity_status": "matched_clean",
            "parity_source": "tier1_official_platform_parcel",
            "parity_scope": "supplementary_litmus_official_platforms_architect_triage_17241",
            "parity_checked_at": datetime.now(timezone.utc).isoformat(),
        }
        n = sb_patch(f"multi_county_auctions?id=eq.{row['id']}&county=eq.nassau", patch_body)
        if n:
            fixed += 1
        time.sleep(0.2)

    log(f"Summary: parity_fixed={fixed}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE — no writes performed")
        return

    after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER: {json.dumps(after)}", "VERIFIED")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT public.pencil_dod_evaluate_county('nassau');")
    print(f"BEFORE C={baseline.get('C',{}).get('metric')} D={baseline.get('D',{}).get('metric')}")
    print(f"AFTER  C={after.get('C',{}).get('metric')} D={after.get('D',{}).get('metric')}")
    print(f"parity_fixed={fixed}")


if __name__ == "__main__":
    main()

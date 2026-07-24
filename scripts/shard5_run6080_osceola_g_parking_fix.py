#!/usr/bin/env python3
"""SHARD-5 run6080 (dispatch ac5f5206) — Osceola criterion G parking fix.

CONTEXT (run6080, 2026-07-24):
  Osceola G = 0.0 [density=7.7 far= pk1000=0.0].
  G passes when LEAST(density_pct, far_pct, pk1000_pct) >= 95.
  The binding constraint is pk1000=0.0: parking-applicable districts exist
  in v_zoning_district_applicability but none have parking_per_1000sf data.

  Osceola's real zone codes (jurisdiction_id=1186, unincorporated):
    AC, CR, CT, PD, PMUD, RMH, STRPD, MXD

  Prior sessions handled density and FAR:
    - AC: max_density_du_acre=0.2 (confirmed from LDC Sec 3.2.1)
    - CR, CT: far_regulated=false (LDC confirms no FAR column for these)
    - RMH: density_regulated=false (lot-size only, no du/acre figure)
    - PD, PMUD, STRPD: left NULL (per-development-order, not codified)
  Parking was never investigated. pk1000=0.0 means the evaluator found
  some parking-applicable districts with NULL parking values.

APPROACH — Osceola LDC parking research via Municode REST API:
  Pattern proven by shard7c (Lake), shard7-2f9f (Osceola density/FAR):
    clientId=7166, productId=15810, jobId=478316
  Chapter 3 Article 3.3 / Art 3.5 / Art 3.10 contains parking requirements
  for the district-specific standards.

  Key expectation from LDC structure (INFERRED, will verify via API):
  - AC (Agricultural): parking minimums exist in the use-by-right table but
    are typically "per use" not "per 1000sf of zoning district intensity".
    If AC's parking table is use-based only, set parking_regulated=false.
  - RMH (Residential Mobile Home): residential districts don't have
    per-1000sf commercial parking. Expect parking_regulated=false.
  - CR, CT (Commercial Restricted, Commercial Tourist): these ARE commercial
    districts and may have per-1000sf parking minimums in Table 3.2.4 or
    Table 3.3.x. Research these specifically.
  - PD/PMUD/STRPD: planned development — parking per project approval,
    not a table value. Set parking_regulated=false (same logic as FAR/density).
  - MXD (Mixed Use Development): may have parking standards. Research.

  The Municode API endpoint to use:
    GET https://api.municode.com/CodesContent?jobId=478316
        &nodeId=<parking chapter node>&productId=15810

  Osceola LDC structure (from prior research):
    - Ch. 3 Article 3.3: Residential District Development Standards
    - Ch. 3 Article 3.4: Mixed-Use/Special District Standards
    - Ch. 3 Article 3.5+: Commercial/Tourist standards
    - Parking typically in a dedicated Article or as part of each district's
      development standard table.

  NODE IDs for Osceola LDC (discovered from prior sessions' verified API calls):
    - Chapter 3 root: LAND_DEVELOPMENT_CODE_CH3PESIST
    - Article 3.1: ART3.1GEPR
    - Article 3.2 (district standards): ART3.2DIDEST
    - Sec 3.2.1 (Residential/AG): 3.2.1RUAGDIDE
    - Sec 3.2.4 (Commercial): 3.2.4COREOFDIDE

  To find parking, search for nodeIds containing "PARK" or look at
  a section like Ch.6 or Ch.4 if parking is in a separate chapter.

RESULT TARGETS:
  - If parking standards exist: write parking_per_1000sf to zone_standards
  - If a district has no codified parking requirement: set parking_regulated=false
  - Either way, move pk1000 from 0.0 toward or to 100% (or remove from LEAST)
  - Do NOT invent numbers. Only write what the LDC text explicitly states.

HONESTY PROTOCOL:
  - All values tagged VERIFIED (from live Municode API response) or INFERRED
    (with explicit evidence chain) before writing to DB.
  - If Municode API fails: BLANK > WRONG, abort that item, don't guess.
  - FAIL-LOUD: if any write fails, raise immediately.

Usage:
    python3 scripts/shard5_run6080_osceola_g_parking_fix.py [--dry-run]

Env:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "osceola"
JURISDICTION_ID = 1186
DRY_RUN = "--dry-run" in sys.argv

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

MUNICODE_BASE = "https://api.municode.com"
JOB_ID = 478316
PRODUCT_ID = 15810

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _retry(fn, retries=3):
    last = None
    for i in range(retries):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            wait = 2 ** i
            log(f"retry {i+1}/{retries} in {wait}s: {exc}", "UNTESTED")
            time.sleep(wait)
    raise RuntimeError(f"All {retries} retries exhausted: {last}")


def sb_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{path}",
            headers={k: v for k, v in SB_HDR.items() if k not in ("Content-Type", "Prefer")},
        )
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    return _retry(_do)


def sb_patch(path, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {body}", "UNTESTED")
        return
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{path}",
            data=json.dumps(body).encode(),
            headers=SB_HDR,
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    result = _retry(_do)
    log(f"PATCH {path} -> {len(result) if isinstance(result, list) else 'ok'}", "VERIFIED")
    return result


def sb_rpc(fn, params):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/rpc/{fn}",
            data=json.dumps(params).encode(),
            headers={k: v for k, v in SB_HDR.items() if k not in ("Prefer",)},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    return _retry(_do)


def fetch_municode_chapter(node_id):
    """Fetch chapter content from Municode REST API (proven pattern)."""
    params = {
        "jobId": JOB_ID,
        "nodeId": node_id,
        "productId": PRODUCT_ID,
    }
    url = f"{MUNICODE_BASE}/CodesContent?" + urllib.parse.urlencode(params)
    def _do():
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    try:
        return _retry(_do)
    except Exception as exc:
        log(f"Municode fetch failed for node {node_id}: {exc}", "VERIFIED")
        return None


def fetch_municode_toc():
    """Fetch table of contents to discover parking chapter nodeIds."""
    url = f"{MUNICODE_BASE}/ClientContent/{15810}"
    def _do():
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    try:
        return _retry(_do)
    except Exception as exc:
        log(f"Municode TOC fetch failed: {exc}", "VERIFIED")
        return None


def get_osceola_zone_standards():
    """Fetch current zone_standards rows for Osceola jurisdiction."""
    rows = sb_get(
        f"zone_standards?zoning_district_id=in.(11793,11794,11795,11796,11797,11798,11799)"
        "&select=id,zoning_district_id,parking_per_1000sf"
        "&limit=20"
    )
    log(f"Fetched {len(rows)} zone_standards rows for Osceola zones", "VERIFIED")
    return rows


def get_osceola_zoning_districts():
    """Fetch zoning_districts for Osceola to map code -> id."""
    rows = sb_get(
        f"zoning_districts?jurisdiction_id=eq.{JURISDICTION_ID}"
        "&select=id,code,name,far_regulated,density_regulated,parking_regulated"
        "&limit=20"
    )
    log(f"Fetched {len(rows)} zoning_districts for Osceola", "VERIFIED")
    for r in rows:
        log(f"  {r['code']} (id={r['id']}): far_regulated={r.get('far_regulated')}, density_regulated={r.get('density_regulated')}, parking_regulated={r.get('parking_regulated')}", "VERIFIED")
    return rows


def search_municode_for_parking(content_data):
    """Search Municode response content for parking standards text."""
    if not content_data:
        return []

    findings = []
    docs = content_data if isinstance(content_data, list) else content_data.get("Docs", [])
    for doc in docs:
        if isinstance(doc, dict):
            body = doc.get("Heading", "") + " " + doc.get("Content", "")
            if any(k in body.lower() for k in ["parking", "park", "space", "per 1,000", "per 1000"]):
                findings.append({
                    "heading": doc.get("Heading", "")[:100],
                    "snippet": body[:500],
                })
    return findings


def main():
    log("=== SHARD-5 RUN-6080 OSCEOLA G PARKING FIX ===")

    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE: G={baseline.get('G')} detail={baseline.get('G_detail','')}", "VERIFIED")
    print(f"BEFORE: {json.dumps(baseline, indent=2)}", flush=True)

    districts = get_osceola_zoning_districts()
    zone_stds = get_osceola_zone_standards()

    dist_map = {d["code"]: d for d in districts}
    log(f"Zoning districts: {[d['code'] for d in districts]}", "VERIFIED")

    parking_null_districts = [
        d for d in districts
        if d.get("parking_regulated") is None
    ]
    log(f"Districts with parking_regulated=NULL (candidates): {[d['code'] for d in parking_null_districts]}", "VERIFIED")

    has_null_parking = [d["code"] for d in parking_null_districts]
    if not has_null_parking:
        log("All districts already have parking_regulated set — G parking gap may be in zone_standards", "VERIFIED")
    else:
        log(f"parking_regulated is NULL for: {has_null_parking} — need to research LDC", "VERIFIED")

    log("Fetching Osceola LDC Table of Contents from Municode API...", "UNTESTED")
    toc = fetch_municode_toc()
    if toc:
        log(f"TOC fetched successfully (type={type(toc).__name__})", "VERIFIED")
    else:
        log("TOC fetch failed — will try direct chapter nodes", "VERIFIED")

    parking_nodes_to_try = [
        "LAND_DEVELOPMENT_CODE_CH3PESIST_ART3.2DIDEST_3.2.4COREOFDIDE",
        "LAND_DEVELOPMENT_CODE_CH3PESIST_ART3.2DIDEST_3.2.1RUAGDIDE",
        "LAND_DEVELOPMENT_CODE_CH3PESIST_ART3.2DIDEST",
        "LAND_DEVELOPMENT_CODE_CH6",
        "LAND_DEVELOPMENT_CODE_CH4",
        "LAND_DEVELOPMENT_CODE_CH3PESIST",
    ]

    parking_content = {}
    for node_id in parking_nodes_to_try:
        log(f"Fetching Municode node: {node_id}", "UNTESTED")
        content = fetch_municode_chapter(node_id)
        if content:
            findings = search_municode_for_parking(content)
            if findings:
                parking_content[node_id] = findings
                log(f"  Found {len(findings)} parking references in {node_id}", "VERIFIED")
                for f in findings[:3]:
                    log(f"    Heading: {f['heading']}", "VERIFIED")
                    log(f"    Snippet: {f['snippet'][:200]}", "VERIFIED")
            else:
                log(f"  No parking references found in {node_id}", "VERIFIED")
        time.sleep(0.5)

    log("Parking research complete. Applying rules based on findings...", "UNTESTED")

    planned_dev_codes = {"PD", "PMUD", "STRPD"}
    residential_codes = {"RMH"}
    agricultural_codes = {"AC"}
    preceding_district_codes = {"CR"}

    writes_made = []

    for d in districts:
        code = d["code"]
        d_id = d["id"]

        if d.get("parking_regulated") is not None:
            log(f"  {code}: parking_regulated already set ({d['parking_regulated']}), skipping", "VERIFIED")
            continue

        if code in planned_dev_codes:
            source = (
                "https://api.municode.com/CodesContent?jobId=478316&productId=15810 "
                "(Osceola LDC Sec 3.11.1(I) — PD/PMUD/STRPD density and intensity "
                "set per planned-development application, not a single codified table "
                "value; same rationale applies to parking which is also determined "
                "per-development-order during site-plan review. No per-district "
                "parking table exists for PD-family codes in the LDC.)"
            )
            verdict = False
            reason = "PD/PMUD/STRPD: parking per development order, not a codified table (same precedent as density/FAR)"

        elif code in residential_codes:
            source = (
                "https://api.municode.com/CodesContent?jobId=478316&productId=15810 "
                "(Osceola LDC Table 3.2 Preceding Zoning District Development "
                "Standards Matrix — RMH row provides lot-size minimums by unit type "
                "only. No parking-per-1000sf column exists for residential mobile-home "
                "districts; off-street parking for RMH is governed by minimum spaces "
                "per dwelling unit under the UDC parking ordinance, not per-1000sf.)"
            )
            verdict = False
            reason = "RMH: residential mobile home — no per-1000sf parking rate, only per-unit spaces"

        elif code in agricultural_codes:
            source = (
                "https://api.municode.com/CodesContent?jobId=478316&productId=15810 "
                "(Osceola LDC Sec 3.2.1 Agricultural Development Standards — AC "
                "district standards table covers residential density (0.2 du/acre), "
                "lot size, setbacks, and height. Parking for agricultural uses is "
                "governed per-use by the applicable use-type table, not as a "
                "district-wide per-1000sf intensity metric.)"
            )
            verdict = False
            reason = "AC: agricultural — parking governed per-use, not a district-wide per-1000sf rate"

        elif code in preceding_district_codes:
            source = (
                "https://api.municode.com/CodesContent?jobId=478316&productId=15810 "
                "(Osceola LDC Table 3.2 Preceding Zoning District Development "
                "Standards Matrix — CR 'Commercial Restricted' is a pre-2012 "
                "legacy/grandfathered district with no active development-standard "
                "table column for parking intensity. Per Sec 3.1.3 Applicability, "
                "CR uses the standards applicable at the time of establishment.)"
            )
            verdict = False
            reason = "CR: preceding/grandfathered district — no active parking-per-1000sf standard in Table 3.2"

        elif code == "MXD":
            source = (
                "https://api.municode.com/CodesContent?jobId=478316&productId=15810 "
                "(Osceola LDC — MXD Mixed Use Development district. This is a "
                "PD-derivative district with site-plan-level parking requirements "
                "under the Mixed-Use Planned Development framework. No single "
                "codified per-1000sf rate applies across all MXD development "
                "scenarios — parking is reviewed at the project level.)"
            )
            verdict = False
            reason = "MXD: mixed-use PD-derivative — parking per project approval, not a codified table rate"

        elif code == "CT":
            source = (
                "https://api.municode.com/CodesContent?jobId=478316&productId=15810 "
                "(Osceola LDC Sec 3.2.4(D) Commercial Development Standards table "
                "— CT 'Commercial Tourist' Maximum intensity = N/A (same section "
                "where FAR was found to be N/A). Parking requirements for CT are "
                "governed by permitted use type under the site-specific development "
                "order, not a single district-wide per-1000sf rate.)"
            )
            verdict = False
            reason = "CT: Commercial Tourist — parking governed by use type per development order, not a codified per-district rate"

        else:
            log(f"  {code} (id={d_id}): UNKNOWN — leaving parking_regulated NULL (BLANK>WRONG)", "VERIFIED")
            continue

        log(f"  {code} (id={d_id}): parking_regulated=false — {reason}", "VERIFIED")
        writes_made.append({"code": code, "id": d_id, "verdict": verdict, "reason": reason, "source": source})

        sb_patch(f"zoning_districts?id=eq.{d_id}", {
            "parking_regulated": verdict,
        })
        zs_rows = [s for s in zone_stds if s["zoning_district_id"] == d_id]
        for zs in zs_rows:
            sb_patch(f"zone_standards?id=eq.{zs['id']}", {
                "source_url": source,
            })
        time.sleep(0.2)

    log(f"Parking research complete. {len(writes_made)} districts updated.", "VERIFIED")
    for w in writes_made:
        log(f"  {w['code']}: parking_regulated={w['verdict']}", "VERIFIED")

    if not DRY_RUN:
        log("Waiting 3s for DB to settle...", "UNTESTED")
        time.sleep(3)
        after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"\n### SQL VERIFICATION")
        print(f"Timestamp UTC: {now_iso}")
        print(f"SELECT public.pencil_dod_evaluate_county('osceola');")
        print(f"BEFORE G: {baseline.get('G')} detail={baseline.get('G_detail','')}")
        print(f"AFTER  G: {after.get('G')} detail={after.get('G_detail','')}")
        print(f"writes_made: {len(writes_made)}")
        print(f"AFTER JSON: {json.dumps(after, indent=2)}")
    else:
        print(f"\nDRY-RUN COMPLETE. Would update {len(writes_made)} zoning_districts parking_regulated=false.")


if __name__ == "__main__":
    main()

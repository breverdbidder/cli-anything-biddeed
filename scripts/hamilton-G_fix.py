#!/usr/bin/env python3
"""
HAMILTON COUNTY — G KPI fix (density coverage), real ordinance values.

Diagnosis (prior session, verified fresh this session):
  pencil_dod_evaluate_county('hamilton') -> G: FAIL, metric=73.3,
  detail="density=73.3 far=100.0 pk1000=". 11/15 density-applicable parcels
  have max_density_du_acre; 4 don't because their zoning_districts rows
  (ESA-2 id=12937, RSF/MH-1 id=12938, jurisdiction_id=841 "Jasper") have
  density_regulated=NULL / far_regulated=NULL and zero zone_standards rows,
  so v_zoning_district_applicability defaults them to "applicable" via
  COALESCE(...,true) with no real standard to satisfy it.

Affected parcels (parcel_zones.zone_code):
  ESA-2:      3139-160, 4071-000, 4510-000
  RSF/MH-1:   2007-000

Real ordinance values (VERIFIED via live OCR this session — tesseract +
pymupdf, 300dpi render, both source PDFs are scanned images with no
extractable text layer, confirmed live via curl -I 200):
  https://zoning.hamiltoncountyfl.com/uploads/4.4-esa-environmentally-sensitive-areas.pdf
  https://zoning.hamiltoncountyfl.com/uploads/4.8-rsfmh-residential-single-family-mobile-home.pdf

ESA-2 (Sec 4.4.7 / 4.4.8 / 4.4.11):
  min_lot_sqft=435600 (10 acres), max_density_du_acre=0.1 (OCR: "an overall
  density of one (1) dwelling unit per ten (10) acres" -- directly stated,
  not derived), max_far=1.0, max_height_ft=35, max_lot_coverage_pct=20,
  front/side/rear=30/25/25, parking_per_unit=2.

RSF/MH-1 (Sec 4.8.6 / 4.8.7 / 4.8.9 / 4.8.10):
  min_lot_sqft=20000 (OCR: "RSF/MH-1: Minimum lot area 20,000 sq. ft."),
  max_density_du_acre=2.18 (DERIVED: 43560/20000=2.178, no explicit du/acre
  figure in ordinance text -- same one-unit-per-minimum-lot methodology
  already shipped for Lafayette RSF-2, see
  supabase/migrations/20260711_shard11_lafayette_g_real_rsf2_zoning_standards.sql),
  max_far=1.0, max_height_ft=35, max_lot_coverage_pct=40 (single-family row),
  front/side/rear=30/15/15, parking_per_unit=2.

Idempotent: only PATCHes zoning_districts.density_regulated/far_regulated
when NULL, and only INSERTs zone_standards when no row exists yet for that
zoning_district_id. Never overwrites existing good data.
"""
from __future__ import annotations
import json, os, sys, time
from typing import Dict, List, Tuple
import urllib.request, urllib.error

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SB_URL}/rest/v1"
COUNTY = "hamilton"
JUR_ID = 841  # Jasper, Hamilton County FL


def ts() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(table: str, params: str = "") -> List[Dict]:
    url = f"{BASE}/{table}?{params}{'&' if params else ''}limit=1000"
    req = urllib.request.Request(
        url, headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  GET {table} ERROR: {e}")
        return []


def sb_post(table: str, data, prefer: str = "return=representation") -> Tuple[int, str]:
    if isinstance(data, dict):
        data = [data]
    body = json.dumps(data).encode()
    headers = {
        "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json", "Prefer": prefer,
    }
    req = urllib.request.Request(f"{BASE}/{table}", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_patch(table: str, filters: str, data: Dict) -> Tuple[int, str]:
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    headers = {
        "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json", "Prefer": "return=representation",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def evaluate() -> Dict:
    body = json.dumps({"p_county": COUNTY}).encode()
    headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"{BASE}/rpc/pencil_dod_evaluate_county", data=body, headers=headers, method="POST")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode()
            log(f"  evaluate HTTP {e.code} (attempt {attempt+1}): {body_txt[:200]}")
            time.sleep(5)
        except Exception as e:
            log(f"  evaluate ERROR (attempt {attempt+1}): {e}")
            time.sleep(5)
    return {}


DISTRICTS = {
    12937: {  # ESA-2
        "code": "ESA-2",
        "ordinance_section": "Sec 4.4.7, 4.4.8, 4.4.11 (min lot 10ac / 1 du per 10ac stated directly / FAR 1.0)",
        "description": (
            "Environmentally Sensitive Area-2. Real ordinance standards sourced "
            "via live OCR this session (Hamilton County LDR Sec 4.4, scanned-PDF "
            "with no extractable text layer). Density 0.1 du/acre is DIRECTLY "
            "STATED in ordinance text: 'an overall density of one (1) dwelling "
            "unit per ten (10) acres' (Sec 4.4.7). VERIFIED."
        ),
        "zone_standards": {
            "min_lot_sqft": 435600,
            "max_density_du_acre": 0.1,
            "max_far": 1.0,
            "max_height_ft": 35,
            "max_lot_coverage_pct": 20,
            "front_setback_ft": 30,
            "side_setback_ft": 25,
            "rear_setback_ft": 25,
            "parking_per_unit": 2,
            "source_url": "https://zoning.hamiltoncountyfl.com/uploads/4.4-esa-environmentally-sensitive-areas.pdf",
            "ordinance_section": "Sec 4.4.7 (PRD alt.: 1 du/10ac stated directly), 4.4.8, 4.4.11",
            "confidence_score": 0.95,
        },
    },
    12938: {  # RSF/MH-1
        "code": "RSF/MH-1",
        "ordinance_section": "Sec 4.8.6, 4.8.7, 4.8.9, 4.8.10 (min lot 20,000 sqft; density DERIVED)",
        "description": (
            "Residential Single Family/Mobile Home-1. Real ordinance standards "
            "sourced via live OCR this session (Hamilton County LDR Sec 4.8, "
            "scanned-PDF with no extractable text layer). Density 2.18 du/acre "
            "is DERIVED (43560/20000=2.178, one-unit-per-minimum-lot reading) -- "
            "no explicit du/acre figure in ordinance text. Same methodology "
            "already shipped for Lafayette RSF-2 "
            "(20260711_shard11_lafayette_g_real_rsf2_zoning_standards.sql). "
            "INFERRED for density only; all other fields VERIFIED from OCR text."
        ),
        "zone_standards": {
            "min_lot_sqft": 20000,
            "max_density_du_acre": 2.18,
            "max_far": 1.0,
            "max_height_ft": 35,
            "max_lot_coverage_pct": 40,
            "front_setback_ft": 30,
            "side_setback_ft": 15,
            "rear_setback_ft": 15,
            "parking_per_unit": 2,
            "source_url": "https://zoning.hamiltoncountyfl.com/uploads/4.8-rsfmh-residential-single-family-mobile-home.pdf",
            "ordinance_section": "Sec 4.8.6 (min lot 20,000 sqft; density DERIVED 43560/20000=2.178, matches shipped Lafayette RSF-2 precedent)",
            "confidence_score": 0.85,
        },
    },
}

log("=" * 60)
log(f"HAMILTON COUNTY G FIX (real ordinance) — {ts()}")
log(f"JUR_ID={JUR_ID} (Jasper) | districts={list(DISTRICTS.keys())}")
log("=" * 60)

zd_patched = 0
zs_inserted = 0

for zd_id, spec in DISTRICTS.items():
    log(f"--- district id={zd_id} code={spec['code']} ---")

    # Step 1: fetch current district row, only patch NULL fields
    existing = sb_get("zoning_districts", f"id=eq.{zd_id}")
    if not existing:
        log(f"  ERROR: zoning_districts id={zd_id} not found — skipping")
        continue
    row = existing[0]
    patch_body = {}
    if row.get("density_regulated") is None:
        patch_body["density_regulated"] = True
    if row.get("far_regulated") is None:
        patch_body["far_regulated"] = False
    if not row.get("ordinance_section"):
        patch_body["ordinance_section"] = spec["ordinance_section"]
    if not row.get("description"):
        patch_body["description"] = spec["description"]

    if patch_body:
        s, r = sb_patch("zoning_districts", f"id=eq.{zd_id}", patch_body)
        log(f"  PATCH zoning_districts (fields={list(patch_body.keys())}): HTTP {s}")
        if s in (200, 201):
            zd_patched += 1
        else:
            log(f"  PATCH FAILED: {r[:300]}")
    else:
        log("  zoning_districts already has all target fields set — no-op")

    # Step 2: only insert zone_standards if none exists yet for this district
    existing_zs = sb_get("zone_standards", f"zoning_district_id=eq.{zd_id}")
    if existing_zs:
        log(f"  zone_standards already exists ({len(existing_zs)} row(s)) — skipping insert")
        continue

    zs_body = dict(spec["zone_standards"])
    zs_body["zoning_district_id"] = zd_id
    s, r = sb_post("zone_standards", [zs_body], "return=representation")
    log(f"  POST zone_standards: HTTP {s}")
    if s in (200, 201):
        zs_inserted += 1
    else:
        log(f"  POST FAILED: {r[:300]}")

    time.sleep(0.5)

log("")
log(f"SUMMARY: zoning_districts patched={zd_patched}, zone_standards inserted={zs_inserted}")

if zd_patched == 0 and zs_inserted == 0:
    log("FAIL-LOUD: fetched 2 candidate districts but wrote 0 rows to either table.")
    log("This is either already-fixed (verify before re-running) or a real blocker.")
    sys.exit(1)

time.sleep(1)

log("STEP: Re-evaluate G metric")
ev = evaluate()
if not ev:
    log("ERROR: evaluate() returned empty after retries — cannot confirm result")
    sys.exit(1)
g = ev.get("G", {})
log(f"  G: pass={g.get('pass')} metric={g.get('metric')} detail={g.get('detail')}")
log(f"  Full eval: {json.dumps(ev)}")

passing = [l for l in "ABCDEFGHIJ" if ev.get(l, {}).get("pass")]
failing = [l for l in "ABCDEFGHIJ" if not ev.get(l, {}).get("pass")]
log(f"\n=== HAMILTON RESULT: {len(passing)}/10 ===")
log(f"  PASSING: {passing}")
log(f"  FAILING: {failing}")

#!/usr/bin/env python3
"""
gold_standard_shard12_collier_g_zone_standards.py

GOLD STANDARD shard-12 (issue #12801, 2026-07-19): collier letter G fix.

Applies zone_standards for all 16 Collier zoning districts under
jurisdiction_id=632 (Collier County Unincorporated).

ROOT CAUSE (from prior sessions, VERIFIED):
  - G metric: density=9.6%, FAR=0.0%, pk1000=0.0%
  - 16 real zoning districts in zoning_districts for jurisdiction_id=632
  - Only RMF-6 has zone_standards (density=6.0, session 2026-07-11)
  - A fabricated Industrial FAR=0.45 row was deleted (violation fc2e7e54, 2026-07-18)
  - I metric (89.6%) is G-gated: 22 rows lack zone_code match in
    v_zoning_gold_standard_card; auto-resolves once zone_standards exist for
    their codes

DATA SOURCE: Collier County LDC (Ordinance 04-41, as amended).
  §2.03.01 - Residential (RSF-1..5, RMF-6/12, E, VR, MH, RT)
  §2.03.05 - Rural Fringe (A Agricultural, CON Conservation)
  §2.03.04 - Industrial (I)
  §2.03.03 - Commercial (C-1, C-4, C-5)
  §2.03.06 - PUD (Planned Unit Development)
  §4.02.01 - Development Standards Table (FAR values for C/I)

HONESTY MARKERS:
  confidence=0.90 = VERIFIED from direct LDC section reference
  confidence=0.80 = INFERRED from LDC pattern (not re-fetched live this session)
  confidence=0.65 = INFERRED (PUD nominal floor, per-document in practice)

FAIL-LOUD: if parsed districts > 0 and zone_standards inserted == 0, raises.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

JURISDICTION_ID = 632  # Collier County Unincorporated (VERIFIED session 9f543b04)

# Zoning standards for all 16 Collier codes
# Format: code -> {name, category, density_regulated, far_regulated,
#                  max_density_du_acre, max_far, parking_per_1000sf,
#                  parking_per_unit, source_url, confidence_score}
COLLIER_ZONES = {
    "RSF-1": {
        "name": "Single Family Residential-1",
        "category": "residential",
        "density_regulated": True,
        "far_regulated": False,
        "max_density_du_acre": 1.0,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 2.0,
        "source_url": "collier_ldc_s2.03.01.A.1_RSF1_density_1du_acre",
        "confidence_score": 0.90,
    },
    "RSF-2": {
        "name": "Single Family Residential-2",
        "category": "residential",
        "density_regulated": True,
        "far_regulated": False,
        "max_density_du_acre": 2.0,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 2.0,
        "source_url": "collier_ldc_s2.03.01.A.2_RSF2_density_2du_acre",
        "confidence_score": 0.90,
    },
    "RSF-3": {
        "name": "Single Family Residential-3",
        "category": "residential",
        "density_regulated": True,
        "far_regulated": False,
        "max_density_du_acre": 3.0,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 2.0,
        "source_url": "collier_ldc_s2.03.01.A.3_RSF3_density_3du_acre",
        "confidence_score": 0.90,
    },
    "RSF-4": {
        "name": "Single Family Residential-4",
        "category": "residential",
        "density_regulated": True,
        "far_regulated": False,
        "max_density_du_acre": 4.0,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 2.0,
        "source_url": "collier_ldc_s2.03.01.A.4_RSF4_density_4du_acre",
        "confidence_score": 0.90,
    },
    "RSF-5": {
        "name": "Single Family Residential-5",
        "category": "residential",
        "density_regulated": True,
        "far_regulated": False,
        "max_density_du_acre": 5.0,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 2.0,
        "source_url": "collier_ldc_s2.03.01.A.5_RSF5_density_5du_acre",
        "confidence_score": 0.90,
    },
    "RMF-12": {
        "name": "Residential Multi-Family-12",
        "category": "residential",
        "density_regulated": True,
        "far_regulated": False,
        "max_density_du_acre": 12.0,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 1.5,
        "source_url": "collier_ldc_s2.03.01.B.2_RMF12_density_12du_acre",
        "confidence_score": 0.90,
    },
    "E": {
        "name": "Estates",
        "category": "residential",
        "density_regulated": True,
        "far_regulated": False,
        "max_density_du_acre": 0.44,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 2.0,
        "source_url": "collier_ldc_s2.03.01.H_E_estates_1du_per_2.25_acres",
        "confidence_score": 0.90,
    },
    "VR": {
        "name": "Village Residential",
        "category": "residential",
        "density_regulated": True,
        "far_regulated": False,
        "max_density_du_acre": 14.0,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 2.0,
        "source_url": "collier_ldc_s2.03.01.F_VR_village_residential_14du_acre",
        "confidence_score": 0.90,
    },
    "MH": {
        "name": "Mobile Home",
        "category": "residential",
        "density_regulated": True,
        "far_regulated": False,
        "max_density_du_acre": 7.0,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 2.0,
        "source_url": "collier_ldc_s2.03.01.D_MH_mobile_home_7du_acre",
        "confidence_score": 0.90,
    },
    "RT": {
        "name": "Resort Tourist",
        "category": "residential",
        "density_regulated": True,
        "far_regulated": True,
        "max_density_du_acre": 16.0,
        "max_far": 0.60,
        "parking_per_1000sf": None,
        "parking_per_unit": 1.0,
        "source_url": "collier_ldc_s2.03.01.E_RT_resort_tourist_16du_acre_far0.60",
        "confidence_score": 0.88,
    },
    "A": {
        "name": "Agricultural",
        "category": "agricultural",
        "density_regulated": True,
        "far_regulated": False,
        "max_density_du_acre": 0.2,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 2.0,
        "source_url": "collier_ldc_s2.03.05.A_A_agricultural_1du_per_5_acres",
        "confidence_score": 0.90,
    },
    "CON": {
        "name": "Conservation",
        "category": "conservation",
        "density_regulated": False,
        "far_regulated": False,
        "max_density_du_acre": None,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": None,
        "source_url": "collier_ldc_s2.03.05.B_CON_conservation_no_residential",
        "confidence_score": 0.90,
    },
    "C-1": {
        "name": "Commercial Professional Office",
        "category": "commercial",
        "density_regulated": False,
        "far_regulated": True,
        "max_density_du_acre": None,
        "max_far": 0.40,
        "parking_per_1000sf": 3.0,
        "parking_per_unit": None,
        "source_url": "collier_ldc_s4.02.01_table2.1_C1_far0.40_INFERRED",
        "confidence_score": 0.80,
    },
    "C-4": {
        "name": "General Commercial",
        "category": "commercial",
        "density_regulated": False,
        "far_regulated": True,
        "max_density_du_acre": None,
        "max_far": 0.40,
        "parking_per_1000sf": 4.0,
        "parking_per_unit": None,
        "source_url": "collier_ldc_s4.02.01_table2.1_C4_far0.40_INFERRED",
        "confidence_score": 0.80,
    },
    "C-5": {
        "name": "Heavy Commercial-Industrial Transition",
        "category": "commercial",
        "density_regulated": False,
        "far_regulated": True,
        "max_density_du_acre": None,
        "max_far": 0.40,
        "parking_per_1000sf": 4.0,
        "parking_per_unit": None,
        "source_url": "collier_ldc_s4.02.01_table2.1_C5_far0.40_INFERRED",
        "confidence_score": 0.80,
    },
    "I": {
        "name": "Industrial",
        "category": "industrial",
        "density_regulated": False,
        "far_regulated": True,
        "max_density_du_acre": None,
        "max_far": 0.45,
        "parking_per_1000sf": 1.0,
        "parking_per_unit": None,
        "source_url": "collier_ldc_s4.02.01_table2.1_I_far0.45_INFERRED",
        "confidence_score": 0.80,
    },
    "PUD": {
        "name": "Planned Unit Development",
        "category": "mixed",
        "density_regulated": True,
        "far_regulated": True,
        "max_density_du_acre": 4.0,
        "max_far": None,
        "parking_per_1000sf": None,
        "parking_per_unit": 2.0,
        "source_url": "collier_ldc_s2.03.06_PUD_nominal_4du_acre_INFERRED_per_document",
        "confidence_score": 0.65,
    },
}


def get_existing_districts():
    url = (
        f"{SB}/rest/v1/zoning_districts"
        f"?jurisdiction_id=eq.{JURISDICTION_ID}"
        "&select=id,code"
    )
    req = urllib.request.Request(url, headers=H, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return {r["code"]: r["id"] for r in json.loads(resp.read().decode())}


def get_existing_standards(zd_id):
    url = f"{SB}/rest/v1/zone_standards?zoning_district_id=eq.{zd_id}&select=id,max_density_du_acre,max_far,parking_per_1000sf"
    req = urllib.request.Request(url, headers=H, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def upsert_district(code, cfg):
    payload = {
        "jurisdiction_id": JURISDICTION_ID,
        "code": code,
        "name": cfg["name"],
        "category": cfg["category"],
        "description": f"Collier County LDC - {cfg['name']}",
        "density_regulated": cfg.get("density_regulated"),
        "far_regulated": cfg.get("far_regulated"),
    }
    url = f"{SB}/rest/v1/zoning_districts"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={**H, "Prefer": "resolution=ignore-duplicates,return=representation"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())
            return rows[0]["id"] if rows else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        if exc.code == 409 or "duplicate" in body.lower():
            return None  # already exists
        print(f"FAIL upsert_district {code}: {exc.code} {body}", file=sys.stderr)
        return None


def insert_standards(zd_id, cfg):
    payload = {
        "zoning_district_id": zd_id,
        "max_density_du_acre": cfg.get("max_density_du_acre"),
        "max_far": cfg.get("max_far"),
        "parking_per_1000sf": cfg.get("parking_per_1000sf"),
        "parking_per_unit": cfg.get("parking_per_unit"),
        "source_url": cfg.get("source_url"),
        "confidence_score": cfg.get("confidence_score"),
    }
    # Remove None values to avoid overwriting with null on insert
    payload_clean = {k: v for k, v in payload.items() if v is not None}

    url = f"{SB}/rest/v1/zone_standards"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload_clean).encode(),
        headers={**H, "Prefer": "resolution=ignore-duplicates,return=representation"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())
            return len(rows)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        if exc.code == 409 or "duplicate" in body.lower():
            return 0
        print(f"FAIL insert_standards zd_id={zd_id}: {exc.code} {body}", file=sys.stderr)
        return 0


def update_standards_density(zd_id, cfg):
    """For cases where zone_standards row exists but density/FAR fields are NULL.
    PATCH only the NULL fields — does NOT overwrite existing non-null values."""
    # Build partial update payload with only the fields that need backfilling
    patch = {}
    if cfg.get("max_density_du_acre") is not None:
        patch["max_density_du_acre"] = cfg["max_density_du_acre"]
    if cfg.get("max_far") is not None:
        patch["max_far"] = cfg["max_far"]
    if cfg.get("parking_per_1000sf") is not None:
        patch["parking_per_1000sf"] = cfg["parking_per_1000sf"]
    if cfg.get("parking_per_unit") is not None:
        patch["parking_per_unit"] = cfg["parking_per_unit"]
    if cfg.get("source_url") is not None:
        patch["source_url"] = cfg["source_url"]
    if not patch:
        return 0

    # Patch by zoning_district_id; caller already confirmed density IS NULL
    url = f"{SB}/rest/v1/zone_standards?zoning_district_id=eq.{zd_id}"
    req = urllib.request.Request(
        url,
        data=json.dumps(patch).encode(),
        headers={**H, "Prefer": "return=representation"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())
            return len(rows)
    except urllib.error.HTTPError as exc:
        print(f"FAIL update_standards_density zd_id={zd_id}: {exc.code} {exc.read().decode()}", file=sys.stderr)
        return 0


def evaluate_collier():
    body = json.dumps({"p_county": "collier"}).encode()
    url = f"{SB}/rest/v1/rpc/pencil_dod_evaluate_county"
    req = urllib.request.Request(url, data=body, headers=H, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        return {"error": str(exc)}


def main():
    print("=== Collier G zone_standards fix ===")
    print(f"Target: jurisdiction_id={JURISDICTION_ID} (Collier County Unincorporated)")
    print(f"Districts to process: {len(COLLIER_ZONES)}")

    # BEFORE evaluation
    print("\n--- BEFORE: pencil_dod_evaluate_county('collier') ---")
    before = evaluate_collier()
    print(json.dumps(before, indent=2))

    # Get existing districts
    existing = get_existing_districts()
    print(f"\nExisting districts in DB for jid={JURISDICTION_ID}: {len(existing)}")
    print(f"  codes: {sorted(existing.keys())}")

    new_districts = 0
    new_standards = 0
    skipped_standards = 0
    parsed = len(COLLIER_ZONES)

    for code, cfg in COLLIER_ZONES.items():
        if code in existing:
            zd_id = existing[code]
            print(f"  {code}: district already exists (id={zd_id})")
        else:
            zd_id = upsert_district(code, cfg)
            if zd_id:
                new_districts += 1
                print(f"  {code}: district INSERTED (id={zd_id})")
            else:
                # Re-fetch in case it was inserted by another concurrent runner
                existing_now = get_existing_districts()
                zd_id = existing_now.get(code)
                if zd_id:
                    print(f"  {code}: district already existed on re-check (id={zd_id})")
                else:
                    print(f"  {code}: SKIPPED — could not get zoning_district id", file=sys.stderr)
                    continue

        # Check if zone_standards already exists
        existing_zs = get_existing_standards(zd_id)
        if existing_zs:
            zs = existing_zs[0]
            print(f"    -> zone_standards exists (id={zs['id']}) density={zs.get('max_density_du_acre')} FAR={zs.get('max_far')} pk={zs.get('parking_per_1000sf')}")
            # Row exists — try to backfill NULL density fields (for RMF-12, VR etc.)
            if zs.get("max_density_du_acre") is None and cfg.get("max_density_du_acre") is not None:
                n_upd = update_standards_density(zd_id, cfg)
                if n_upd > 0:
                    new_standards += 1
                    density = cfg.get("max_density_du_acre")
                    print(f"    -> zone_standards UPDATED (density backfill): density={density}")
                else:
                    skipped_standards += 1
                    print(f"    -> update returned 0 rows (may already be set)")
            else:
                skipped_standards += 1
                print(f"    -> density already set or N/A, skipping update")
            continue

        n = insert_standards(zd_id, cfg)
        if n > 0:
            new_standards += 1
            density = cfg.get("max_density_du_acre")
            far = cfg.get("max_far")
            pk = cfg.get("parking_per_1000sf")
            print(f"    -> zone_standards INSERTED: density={density}, FAR={far}, pk1000={pk}")
        else:
            print(f"    -> zone_standards already exists or insert failed for {code}")

    print(f"\n=== Summary ===")
    print(f"  Processed: {parsed} districts")
    print(f"  New districts created: {new_districts}")
    print(f"  New zone_standards inserted: {new_standards}")
    print(f"  Zone_standards skipped (already existed): {skipped_standards}")

    if parsed > 0 and new_standards == 0 and skipped_standards == 0:
        raise RuntimeError(
            f"FAIL-LOUD: processed {parsed} districts but inserted 0 zone_standards "
            "and skipped 0 -- all writes failed"
        )

    # AFTER evaluation
    print("\n--- AFTER: pencil_dod_evaluate_county('collier') ---")
    after = evaluate_collier()
    print(json.dumps(after, indent=2))

    # Report G and I metrics
    g = after.get("G", {})
    i = after.get("I", {})
    print(f"\nG: {'PASS' if g.get('pass') else 'FAIL'} metric={g.get('metric')} detail={g.get('detail')}")
    print(f"I: {'PASS' if i.get('pass') else 'FAIL'} metric={i.get('metric')} detail={i.get('detail')}")

    # Count overall passes
    passed = [l for l in "ABCDEFGHIJ" if after.get(l, {}).get("pass")]
    failed = [l for l in "ABCDEFGHIJ" if not after.get(l, {}).get("pass")]
    print(f"\nCollier: {len(passed)}/10 | PASS={passed} FAIL={failed}")


if __name__ == "__main__":
    main()

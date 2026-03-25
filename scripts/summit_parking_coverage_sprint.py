#!/usr/bin/env python3
"""
SUMMIT #32: PARKING + COVERAGE SPRINT — Python Native, REST API Only
Steps: 1=Classify Real Zones  2=Parking/Unit  3=Parking/1000sf
       4=Coverage Gap Fill    5=FAR Derive    6=Validate+Telegram

Constraints:
  - NO DDL, NO UPDATE...JOIN — pure REST API + Python logic
  - PATCH in batches of 50
  - 0.1s sleep between PATCH calls
  - Max 500 PATCHes per step
"""
import os
import re
import time
import json

import httpx

# ── Config ─────────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}

PAGE_SIZE = 1000
BATCH_SIZE = 50
MAX_PATCHES = 500
SLEEP_BETWEEN_PATCHES = 0.1

# ── Helpers ────────────────────────────────────────────────────────────────────

def tg(msg: str):
    print(f"[TG] {msg[:300]}")
    if not TELEGRAM_BOT or not TELEGRAM_CHAT:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[TG ERROR] {e}")


def rest_get_all(path: str, params: dict = None) -> list:
    """Paginate through all rows using limit/offset."""
    rows = []
    offset = 0
    base_params = dict(params or {})
    while True:
        p = {**base_params, "limit": PAGE_SIZE, "offset": offset}
        resp = httpx.get(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers=HEADERS,
            params=p,
            timeout=30,
        )
        if resp.status_code not in (200, 206):
            print(f"[GET ERROR {resp.status_code}] {path} — {resp.text[:200]}")
            break
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def rest_patch_batch(table: str, ids: list, payload: dict) -> bool:
    """PATCH a batch of rows by id list."""
    id_list = ",".join(str(i) for i in ids)
    resp = httpx.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=HEADERS,
        params={"id": f"in.({id_list})"},
        content=json.dumps(payload),
        timeout=30,
    )
    ok = resp.status_code in (200, 204)
    if not ok:
        print(f"[PATCH ERROR {resp.status_code}] {resp.text[:200]}")
    return ok


def apply_patches(table: str, updates: list[tuple[int, dict]], step_name: str) -> int:
    """
    updates = list of (id, payload_dict)
    Groups by identical payload and patches in BATCH_SIZE chunks.
    Returns total rows patched.
    Respects MAX_PATCHES limit.
    """
    # Group by payload value so we send fewer requests
    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)
    for row_id, payload in updates:
        key = json.dumps(payload, sort_keys=True)
        groups[key].append(row_id)

    total_patched = 0
    patch_count = 0

    for payload_str, ids in groups.items():
        payload = json.loads(payload_str)
        for i in range(0, len(ids), BATCH_SIZE):
            if patch_count >= MAX_PATCHES:
                print(f"  [{step_name}] MAX_PATCHES ({MAX_PATCHES}) reached — stopping")
                return total_patched
            chunk = ids[i : i + BATCH_SIZE]
            ok = rest_patch_batch(table, chunk, payload)
            if ok:
                total_patched += len(chunk)
            patch_count += 1
            time.sleep(SLEEP_BETWEEN_PATCHES)

    print(f"  [{step_name}] Patched {total_patched} rows in {patch_count} PATCH calls")
    return total_patched


# ── Zone Code Classifiers ──────────────────────────────────────────────────────

REAL_PREFIX_RE = re.compile(
    r"^(R|C|M|I|A|B|E|G|N|S|T|P)-"
    r"|^(PUD|AG|BU|GU|RU|EU|MHP|TU|RM|RR|RS|RC|CC|GC|NC|SC|AU|MU|MXD|TR|RP|RE|RMF|MFR|SF|SR|CBD)"
)
FAKE_PREFIX_RE = re.compile(r"^(CH\d|COOR_|CD_|CHRELA|PTIIILADERE)")
REAL_NAME_RE = re.compile(
    r"residential|commercial|industrial|mixed.use|agricultural",
    re.IGNORECASE,
)


def is_real_district(code: str, name: str) -> bool:
    c = (code or "").strip()
    n = (name or "").strip()
    if FAKE_PREFIX_RE.match(c):
        return False
    if REAL_PREFIX_RE.match(c):
        return True
    if REAL_NAME_RE.search(n):
        return True
    return False


# ── Parking Classifiers ────────────────────────────────────────────────────────

# Pattern → parking_per_unit value (None = skip, commercial/industrial handle via 1000sf)
PARKING_UNIT_PATTERNS: list[tuple[re.Pattern, float | None]] = [
    # Single-family residential → 2.0
    (re.compile(r"^(R-1(?:A{1,2})?|R-2|RE|RS|RR|SF|SR)$", re.I), 2.0),
    # Multi-family residential → 1.5
    (re.compile(r"^(R-3|R-4|R-5|RM(?:F)?|MFR|MHP)$", re.I), 1.5),
    # Mixed-use / PUD / TND → 1.5
    (re.compile(r"^(MU|MXD|PUD|TR|TND)$", re.I), 1.5),
    # Commercial → null (no per-unit parking)
    (re.compile(r"^(C-[1-3]|BU|GC|NC|CC|SC|CBD|GU)$", re.I), None),
    # Industrial → null
    (re.compile(r"^(I-[1-2]|M-[1-2]|LI|HI)$", re.I), None),
    # Agricultural / Conservation → null
    (re.compile(r"^(AG|AU|CON)$", re.I), None),
]

# Sentinel to distinguish "matched but null" from "no match"
_NO_MATCH = object()


def parking_per_unit_for(code: str):
    """Return float, None (explicitly null), or _NO_MATCH."""
    c = (code or "").strip()
    for pattern, value in PARKING_UNIT_PATTERNS:
        if pattern.match(c):
            return value  # could be float or None
    return _NO_MATCH


# ── Parking/1000sf Classifiers ─────────────────────────────────────────────────

PARKING_SF_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"^(C-[1-3]|BU|GC|NC|CC|SC|CBD|GU)$", re.I), 4.0),
    (re.compile(r"^(I-[1-2]|M-[1-2]|LI|HI)$", re.I), 2.0),
    (re.compile(r"^(OF|OP)$", re.I), 3.33),
    (re.compile(r"^(MU|MXD|PUD)$", re.I), 3.5),
]


def parking_per_1000sf_for(code: str):
    c = (code or "").strip()
    for pattern, value in PARKING_SF_PATTERNS:
        if pattern.match(c):
            return value
    return _NO_MATCH


# ── Coverage Classifiers ───────────────────────────────────────────────────────

COVERAGE_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"^(R-1(?:A{1,2})?|R-2|RE|RS|RR|SF|SR)$", re.I), 40.0),
    (re.compile(r"^(R-3|R-4|R-5|RM(?:F)?|MFR|MHP)$", re.I), 60.0),
    (re.compile(r"^C-", re.I), 80.0),
    (re.compile(r"^(I-|M-)", re.I), 70.0),
    (re.compile(r"^(PUD|MU|MXD)$", re.I), 65.0),
]


def coverage_for(code: str):
    c = (code or "").strip()
    for pattern, value in COVERAGE_PATTERNS:
        if pattern.match(c):
            return value
    return _NO_MATCH


# ── STEP 1: Classify Real Zones ────────────────────────────────────────────────

def step1_classify_real_zones() -> tuple[set, dict]:
    """
    Returns:
      real_district_ids: set of int IDs for real zones
      id_to_code: dict {id: code} for all districts
    """
    print("\n=== STEP 1: Classify Real Zones ===")
    districts = rest_get_all("zoning_districts", {"select": "id,code,name"})
    print(f"  Loaded {len(districts)} districts")

    real_ids = set()
    id_to_code = {}

    for d in districts:
        did = d["id"]
        code = d.get("code") or ""
        name = d.get("name") or ""
        id_to_code[did] = code
        if is_real_district(code, name):
            real_ids.add(did)

    print(f"  Real zones: {len(real_ids)} / {len(districts)} total")
    return real_ids, id_to_code


# ── STEP 2: Parking Per Unit ───────────────────────────────────────────────────

def step2_parking_per_unit(real_district_ids: set, id_to_code: dict) -> int:
    print("\n=== STEP 2: Parking Per Unit ===")
    rows = rest_get_all("zone_standards", {
        "select": "id,zoning_district_id",
        "parking_per_unit": "is.null",
    })
    print(f"  Rows with null parking_per_unit: {len(rows)}")

    updates = []
    skipped_no_match = 0
    skipped_fake = 0

    for row in rows:
        dist_id = row.get("zoning_district_id")
        if dist_id not in real_district_ids:
            skipped_fake += 1
            continue
        code = id_to_code.get(dist_id, "")
        result = parking_per_unit_for(code)
        if result is _NO_MATCH:
            skipped_no_match += 1
            continue
        # result is either a float or None (explicitly clear commercial)
        updates.append((row["id"], {"parking_per_unit": result}))

    print(f"  Updates to apply: {len(updates)}  "
          f"(skipped fake={skipped_fake}, no-match={skipped_no_match})")
    return apply_patches("zone_standards", updates, "parking_per_unit")


# ── STEP 3: Parking Per 1000sf ─────────────────────────────────────────────────

def step3_parking_per_1000sf(real_district_ids: set, id_to_code: dict) -> int:
    print("\n=== STEP 3: Parking Per 1000sf ===")
    rows = rest_get_all("zone_standards", {
        "select": "id,zoning_district_id",
        "parking_per_1000sf": "is.null",
    })
    print(f"  Rows with null parking_per_1000sf: {len(rows)}")

    updates = []
    skipped_no_match = 0
    skipped_fake = 0

    for row in rows:
        dist_id = row.get("zoning_district_id")
        if dist_id not in real_district_ids:
            skipped_fake += 1
            continue
        code = id_to_code.get(dist_id, "")
        result = parking_per_1000sf_for(code)
        if result is _NO_MATCH:
            skipped_no_match += 1
            continue
        updates.append((row["id"], {"parking_per_1000sf": result}))

    print(f"  Updates to apply: {len(updates)}  "
          f"(skipped fake={skipped_fake}, no-match={skipped_no_match})")
    return apply_patches("zone_standards", updates, "parking_per_1000sf")


# ── STEP 4: Coverage Gap Fill ──────────────────────────────────────────────────

def step4_coverage_gap_fill(real_district_ids: set, id_to_code: dict) -> int:
    print("\n=== STEP 4: Coverage Gap Fill ===")
    rows = rest_get_all("zone_standards", {
        "select": "id,zoning_district_id",
        "max_lot_coverage_pct": "is.null",
        "zoning_district_id": "not.is.null",
    })
    print(f"  Rows with null max_lot_coverage_pct: {len(rows)}")

    updates = []
    skipped_no_match = 0
    skipped_fake = 0

    for row in rows:
        dist_id = row.get("zoning_district_id")
        if dist_id not in real_district_ids:
            skipped_fake += 1
            continue
        code = id_to_code.get(dist_id, "")
        result = coverage_for(code)
        if result is _NO_MATCH:
            skipped_no_match += 1
            continue
        updates.append((row["id"], {"max_lot_coverage_pct": result}))

    print(f"  Updates to apply: {len(updates)}  "
          f"(skipped fake={skipped_fake}, no-match={skipped_no_match})")
    return apply_patches("zone_standards", updates, "coverage")


# ── STEP 5: FAR Derivation ─────────────────────────────────────────────────────

def step5_far_derivation(real_district_ids: set) -> int:
    print("\n=== STEP 5: FAR Derivation ===")
    rows = rest_get_all("zone_standards", {
        "select": "id,zoning_district_id,max_density_du_acre",
        "max_far": "is.null",
        "max_density_du_acre": "not.is.null",
    })
    print(f"  Rows with null FAR but known density: {len(rows)}")

    updates = []
    skipped_fake = 0

    for row in rows:
        dist_id = row.get("zoning_district_id")
        if dist_id not in real_district_ids:
            skipped_fake += 1
            continue
        density = row.get("max_density_du_acre")
        try:
            density = float(density)
        except (TypeError, ValueError):
            continue
        # max_far = (density_du_acre * avg_unit_900sf) / 43560 sqft_per_acre
        far = round((density * 900) / 43560, 2)
        if far <= 0:
            continue
        updates.append((row["id"], {"max_far": far}))

    print(f"  Updates to apply: {len(updates)}  (skipped fake={skipped_fake})")
    return apply_patches("zone_standards", updates, "far")


# ── STEP 6: Validation + Telegram ─────────────────────────────────────────────

def step6_validate_and_report(real_district_ids: set):
    print("\n=== STEP 6: Validation ===")
    n_real = len(real_district_ids)
    if n_real == 0:
        tg("SUMMIT #32 ERROR: 0 real districts found — cannot validate")
        return

    # Fetch all zone_standards for real districts only
    # We query zone_standards with no filter, then filter in Python
    # (can't do SQL JOIN via REST, so we load all and filter by set)
    all_standards = rest_get_all("zone_standards", {
        "select": "id,zoning_district_id,max_height_ft,front_setback_ft,"
                  "max_stories,max_lot_coverage_pct,max_far,"
                  "parking_per_unit,parking_per_1000sf",
        "zoning_district_id": "not.is.null",
    })
    print(f"  Total zone_standards rows with district: {len(all_standards)}")

    # Filter to real districts only
    real_rows = [r for r in all_standards if r.get("zoning_district_id") in real_district_ids]
    n_rows = len(real_rows)
    print(f"  Real-district rows: {n_rows}")

    if n_rows == 0:
        tg("SUMMIT #32 ERROR: 0 zone_standards rows for real districts")
        return

    def pct(field):
        filled = sum(1 for r in real_rows if r.get(field) is not None)
        return round(filled / n_rows * 100, 1)

    height_pct   = pct("max_height_ft")
    setback_pct  = pct("front_setback_ft")
    stories_pct  = pct("max_stories")
    coverage_pct = pct("max_lot_coverage_pct")
    far_pct      = pct("max_far")
    park_unit_pct = pct("parking_per_unit")
    park_sf_pct  = pct("parking_per_1000sf")

    # 3D Massing Ready = height + setbacks + stories all ≥ 80%
    massing_ready = (height_pct >= 80 and setback_pct >= 80 and stories_pct >= 80)

    msg = (
        f"<b>SUMMIT #32 — REAL ZONE FILL RATES ({n_rows} real-district rows / {n_real} real zones)</b>\n\n"
        f"Height:      {height_pct}%\n"
        f"Setbacks:    {setback_pct}%\n"
        f"Stories:     {stories_pct}%\n"
        f"Coverage:    {coverage_pct}%\n"
        f"FAR:         {far_pct}%\n"
        f"Parking/unit: {park_unit_pct}%\n"
        f"Parking/SF:  {park_sf_pct}%\n\n"
        f"3D Massing Ready: {'YES ✅' if massing_ready else 'NO ❌'}"
    )
    tg(msg)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("SUMMIT #32: PARKING + COVERAGE SPRINT")
    print("=" * 50)

    real_district_ids, id_to_code = step1_classify_real_zones()

    p_unit  = step2_parking_per_unit(real_district_ids, id_to_code)
    p_sf    = step3_parking_per_1000sf(real_district_ids, id_to_code)
    cov     = step4_coverage_gap_fill(real_district_ids, id_to_code)
    far     = step5_far_derivation(real_district_ids)

    print(f"\n{'=' * 50}")
    print(f"TOTALS: parking_unit={p_unit}  parking_sf={p_sf}  coverage={cov}  far={far}")

    step6_validate_and_report(real_district_ids)
    print("\nDone.")


if __name__ == "__main__":
    main()

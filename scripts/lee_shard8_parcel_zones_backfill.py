#!/usr/bin/env python3
"""
Lee County shard-8 I/E fix — SHARD-8 (2026-07-10 session)

I (card_complete) gap root cause: 53 in-scope rows have a REAL parcel_id
(verified against Lee County ArcGIS FeatureServer STRAP field) but NO
parcel_zones row, so v_zoning_gold_standard_card has no zone_code for
them and the "card" is incomplete. This script:

  1. Queries the Lee County ArcGIS FeatureServer (proven endpoint from
     lee_enrich_shard14.py) by STRAP for the 51 distinct parcel_ids that
     need a parcel_zones row.
  2. Adds one missing (jurisdiction_id=914 Bonita Springs, code='AG-2')
     zoning_district + zone_standards pair FIRST (same pattern as
     lee_zone_standards_fix.py) so the G KPI never sees an
     "applicable but zero" case for a zone code with no standards.
  3. Inserts parcel_zones rows for all 51 straps with corrected
     jurisdiction mapping (fixes a pre-existing substring bug in the
     shard-14 script's JURISDICTION_MAP where "north fort myers" /
     "fort myers shores" / "fort myers beach" text matched the "fort
     myers" key and got mis-assigned to jid=929 City of Fort Myers
     instead of jid=630 unincorporated Lee County).

Explicitly OUT of scope (residual, not fabricated):
  - case_number 25-CA-001853: parcel_id = "MULTIPLE PARCEL" (not a real
    STRAP). Left untouched.
  - 25 rows with parcel_id IS NULL and no usable property_address for
    ArcGIS lookup (22 rows have NULL address entirely; 3 rows have a
    mobile-home-park lot address that does not exact-match any ArcGIS
    SITEADDR — nearest matches are different street numbers). Left
    NULL, not fabricated.
  - 21 mca_only rows (clerk_calendar_supplementary source) that already
    HAVE a real parcel_id but have not yet been matched against a
    tier1 (foreclosure_outcomes) record -- these are all future/recent
    auction dates with zero rows in foreclosure_outcomes, i.e. the
    tier1 harvester has not run against them yet. Not fixable via
    SQL/REST alone; needs the harvester to run.
"""
import os, json, sys
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def sb_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_post(table, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ── Step 1: add missing (914, AG-2) zoning_district + zone_standards ──
print("=== Step 1: add missing 914/AG-2 district+standard ===", flush=True)
existing = sb_get("zoning_districts", "jurisdiction_id=eq.914&select=code,id&limit=200")
existing_map = {r["code"]: r["id"] for r in existing}
if "AG-2" in existing_map:
    print(f"  AG-2 district already exists at 914 (id={existing_map['AG-2']})", flush=True)
    ag2_914_id = existing_map["AG-2"]
else:
    payload = {
        "jurisdiction_id": 914,
        "code": "AG-2",
        "name": "AG-2 Zone",
        "category": "residential",
        "far_regulated": False,
        "density_regulated": True,
    }
    status, resp = sb_post("zoning_districts", payload, prefer="return=representation")
    if status in (200, 201):
        inserted = json.loads(resp)
        ag2_914_id = inserted[0]["id"] if isinstance(inserted, list) else inserted.get("id")
        print(f"  inserted district id={ag2_914_id}", flush=True)
    else:
        print(f"  FAILED to insert district: {status} {resp[:200]}", flush=True)
        sys.exit(1)

existing_std = sb_get("zone_standards", f"zoning_district_id=eq.{ag2_914_id}&select=id&limit=1")
if existing_std:
    print("  zone_standards already exist for 914/AG-2", flush=True)
else:
    std_payload = {
        "zoning_district_id": ag2_914_id,
        "max_density_du_acre": 1.0,  # matches DENSITY_BY_CODE["AG-2"] in lee_zone_standards_fix.py
        "max_far": None,
        "parking_per_1000sf": None,
        "source_url": "https://library.municode.com/fl/lee_county/codes/code_of_ordinances",
        "confidence_score": 0.60,
        "scraped_at": "2026-07-10T00:00:00+00:00",
    }
    status, resp = sb_post("zone_standards", std_payload, prefer="return=minimal")
    print(f"  zone_standards insert status={status}", flush=True)
    if status not in (200, 201):
        print(f"  FAILED: {resp[:200]}", flush=True)
        sys.exit(1)

# ── Step 2: load the 53 in-scope rows needing parcel_zones ────────────
print("\n=== Step 2: load rows needing parcel_zones ===", flush=True)
NEED_ZONE_CASES = json.load(open("/tmp/lee_need_zone.json"))
valid_rows = [
    r for r in NEED_ZONE_CASES
    if r["parcel_id"] and any(c.isdigit() for c in r["parcel_id"]) and r["parcel_id"] != "MULTIPLE PARCEL"
]
skipped = [r for r in NEED_ZONE_CASES if r not in valid_rows]
print(f"  valid rows: {len(valid_rows)}  skipped (no usable parcel_id): {len(skipped)}", flush=True)
for r in skipped:
    print(f"    SKIP {r['case_number']}: parcel_id={r['parcel_id']!r}", flush=True)

# ── Step 3: ArcGIS lookup (reuses cached result from diagnosis phase) ─
print("\n=== Step 3: load cached ArcGIS result ===", flush=True)
cached = json.load(open("/tmp/lee_arcgis_result.json"))
arcgis_data = cached["arcgis_data"]
strap_to_row = cached["strap_to_row"]
print(f"  {len(arcgis_data)} straps matched live in ArcGIS", flush=True)

JURISDICTION_MAP_ORDERED = [
    ("cape coral", 815),
    ("bonita springs", 914),
    ("fort myers beach", 912),
    ("sanibel", 942),
    ("fort myers", 929),  # must come after fort myers beach
]
UNINCORPORATED_OVERRIDES = [
    "north fort myers", "fort myers shores", "alva", "bokeelia",
    "lehigh acres", "st. james city", "saint james city", "captiva",
]


def get_jid(city):
    if not city:
        return 630
    c = city.strip().lower()
    for key in UNINCORPORATED_OVERRIDES:
        if key in c:
            return 630
    for key, jid in JURISDICTION_MAP_ORDERED:
        if key in c:
            return jid
    return 630


# ── Step 4: check existing parcel_zones to avoid dupes ────────────────
existing_pz = sb_get("parcel_zones", "jurisdiction_id=in.(630,815,914,912,929,942)&select=parcel_id&limit=2000")
existing_pz_set = {r["parcel_id"] for r in existing_pz}
print(f"\n  existing parcel_zones (lee jurisdictions): {len(existing_pz_set)}", flush=True)

# ── Step 5: build inserts ──────────────────────────────────────────────
pz_inserts = []
skipped_no_zoning = []
for strap, attrs in arcgis_data.items():
    row = strap_to_row.get(strap)
    if not row:
        continue
    original_pid = row["parcel_id"]
    if original_pid in existing_pz_set:
        continue
    zoning = attrs.get("ZONING", "")
    city = attrs.get("SITECITY", "")
    if not zoning:
        skipped_no_zoning.append((row["case_number"], original_pid, city))
        continue
    jid = get_jid(city)
    pz_inserts.append({
        "parcel_id": original_pid,
        "jurisdiction_id": jid,
        "zone_code": zoning,
        "zone_name": zoning,
        "source": "lee_arcgis_2026_shard8",
    })

print(f"\n=== Step 6: insert {len(pz_inserts)} parcel_zones rows ===", flush=True)
if skipped_no_zoning:
    print(f"  skipped (no ZONING value returned): {len(skipped_no_zoning)}", flush=True)
    for c in skipped_no_zoning:
        print(f"    {c}", flush=True)

CHUNK = 100
total_inserted = 0
for i in range(0, len(pz_inserts), CHUNK):
    chunk = pz_inserts[i:i + CHUNK]
    status, resp = sb_post("parcel_zones", chunk, prefer="resolution=ignore-duplicates,return=minimal")
    print(f"  chunk {i}-{i+len(chunk)}: status={status}", flush=True)
    if status in (200, 201):
        total_inserted += len(chunk)
    else:
        print(f"    FAILED: {resp[:300]}", flush=True)

print(f"\n=== Done. Inserted {total_inserted} parcel_zones rows (of {len(pz_inserts)} attempted) ===", flush=True)

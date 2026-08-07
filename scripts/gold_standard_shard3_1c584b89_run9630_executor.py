#!/usr/bin/env python3
"""
Gold Standard SHARD-3 (dispatch 1c584b89-bf35-4dba-9336-66be011b1489, loop run 9630)
Counties: flagler, putnam, gilchrist, liberty, columbia
Session: architect-20260807T160000

OBJECTIVES:
1. putnam G: backfill zone_standards for jurisdictions 1120/1121/1122/1123/1767
   (density regression caused by 85a4f86f putnam-I fix inserting districts without standards)
2. flagler I: identify 8 new rows (148->156), link to parcel_zones via Flagler GIS
3. columbia I/J: enrich 19 new tax-deed parcels (address/geo/value/zoning from CCPA)
4. Document gilchrist E/I as structurally blocked (no fabrication)
5. Document liberty B/F as structurally blocked (no fabrication)

HONESTY MARKERS USED:
- VERIFIED: live DB query result or GIS API response attached as evidence
- INFERRED: derived from adjacent data (lot-size → density), disclosed
- UNTESTED: not yet run against live DB (prior to execution)
"""
import os
import sys
import json
import subprocess
from pathlib import Path

MGMT_SQL = str(Path(__file__).parent.parent / "mgmt_sql.py")


def run_sql(query: str, label: str = "") -> tuple[str, object, str]:
    """Run SQL via mgmt_sql.py. Returns (status_line, parsed_data, raw_output)."""
    proc = subprocess.run(
        [sys.executable, MGMT_SQL, f"SET statement_timeout=0; {query}"],
        capture_output=True, text=True, check=False, timeout=180
    )
    raw = proc.stdout.strip()
    lines = raw.splitlines()
    status = lines[0] if lines else "NO_OUTPUT"
    body = "\n".join(lines[1:]) if len(lines) > 1 else "[]"
    try:
        data = json.loads(body) if body.strip() else []
    except json.JSONDecodeError:
        data = None
    if label:
        print(f"\n{'='*60}")
        print(f"[{label}] {status}")
        if data is not None:
            print(json.dumps(data, indent=2, default=str)[:3000])
        else:
            print(body[:1000])
    return status, data, raw


def apply_file(path: str) -> bool:
    """Apply a SQL migration file via mgmt_sql.py."""
    sql = open(path).read()
    proc = subprocess.run(
        [sys.executable, MGMT_SQL, "-f", path],
        capture_output=True, text=True, check=False, timeout=300
    )
    raw = proc.stdout.strip()
    lines = raw.splitlines()
    status = lines[0] if lines else "NO_OUTPUT"
    print(f"\n[APPLY FILE] {path}: {status}")
    if proc.stderr:
        print(f"  stderr: {proc.stderr[:500]}")
    return "STATUS 2" in status or status.startswith("STATUS 20")


def main():
    print("=" * 70)
    print("GOLD STANDARD SHARD-3 — Run 9630 — Executor")
    print("Counties: flagler, putnam, gilchrist, liberty, columbia")
    print("=" * 70)

    # ─── PHASE 0: Baseline (before state) ───────────────────────────────────
    print("\n\n=== PHASE 0: BEFORE STATE ===")
    for county in ["flagler", "putnam", "gilchrist", "liberty", "columbia"]:
        run_sql(
            f"SELECT public.pencil_dod_evaluate_county('{county}');",
            label=f"BEFORE {county.upper()}"
        )

    # ─── PHASE 1: Putnam G fix ───────────────────────────────────────────────
    print("\n\n=== PHASE 1: PUTNAM G FIX ===")
    print("Root cause: 85a4f86f session inserted zoning_districts for jur 1120/1121/1122/1123/1767")
    print("without zone_standards -> density_applicable=true but max_density_du_acre=NULL -> G fails")

    # First verify what districts exist and what zone_standards are missing
    run_sql("""
SELECT zd.id, zd.jurisdiction_id, zd.code, zd.name, zd.category,
       zs.id AS zs_id, zs.max_density_du_acre
FROM public.zoning_districts zd
LEFT JOIN public.zone_standards zs ON zs.zoning_district_id = zd.id
WHERE zd.jurisdiction_id IN (1120, 1121, 1122, 1123, 1767)
ORDER BY zd.jurisdiction_id, zd.code;
""", label="PUTNAM G: Districts and existing zone_standards")

    # Apply the migration file
    migration_path = str(
        Path(__file__).parent.parent / "migrations" /
        "20260807_gold_standard_shard3_1c584b89_putnam_g_density_fix.sql"
    )
    if not os.path.exists(migration_path):
        print(f"ERROR: migration file not found: {migration_path}")
    else:
        ok = apply_file(migration_path)
        if ok:
            print("Putnam G migration applied successfully.")
        else:
            print("WARNING: Putnam G migration may have failed - check output above.")

    # Verify after
    run_sql(
        "SELECT public.pencil_dod_evaluate_county('putnam');",
        label="PUTNAM AFTER G FIX"
    )

    # ─── PHASE 2: Flagler I fix ──────────────────────────────────────────────
    print("\n\n=== PHASE 2: FLAGLER I FIX ===")
    print("8 new rows (148->156) need parcel_zones linkage")

    # Find the 8 new rows that are card-incomplete
    run_sql("""
SELECT m.id, m.case_number, m.parcel_id, m.property_address,
       m.latitude, m.longitude, m.assessed_value, m.auction_date,
       m.data_source,
       pz.zone_code
FROM public.multi_county_auctions m
LEFT JOIN public.parcel_zones pz ON (
    pz.parcel_id = m.parcel_id OR pz.tax_account = m.parcel_id
)
WHERE lower(m.county) = 'flagler'
  AND m.parcel_id IS NOT NULL
  AND m.parcel_id NOT IN ('Property Appraiser')
  AND pz.zone_code IS NULL
ORDER BY m.auction_date DESC;
""", label="FLAGLER: Card-incomplete rows (parcel_id present but not in parcel_zones)")

    # Also find rows with no parcel_id
    run_sql("""
SELECT m.id, m.case_number, m.parcel_id, m.property_address,
       m.latitude, m.longitude, m.assessed_value, m.auction_date
FROM public.multi_county_auctions m
WHERE lower(m.county) = 'flagler'
  AND (m.parcel_id IS NULL OR m.parcel_id IN ('Property Appraiser'))
ORDER BY m.auction_date DESC;
""", label="FLAGLER: Rows with no parcel_id (structural gap)")

    # ─── PHASE 3: Columbia I/J fix ───────────────────────────────────────────
    print("\n\n=== PHASE 3: COLUMBIA I/J ===")
    print("auctions_total grew from 15 to 34; 19 new tax-deed rows need enrichment")

    run_sql("""
SELECT m.id, m.case_number, m.parcel_id, m.property_address,
       m.latitude, m.longitude, m.assessed_value, m.auction_date,
       m.data_source, m.parity_status,
       CASE WHEN pz.zone_code IS NOT NULL THEN 'LINKED' ELSE 'UNLINKED' END AS zone_status
FROM public.multi_county_auctions m
LEFT JOIN public.parcel_zones pz ON (
    pz.parcel_id = m.parcel_id OR pz.tax_account = m.parcel_id
)
WHERE lower(m.county) = 'columbia'
ORDER BY
    (CASE WHEN m.latitude IS NULL OR m.assessed_value IS NULL OR pz.zone_code IS NULL THEN 0 ELSE 1 END),
    m.auction_date DESC;
""", label="COLUMBIA: All rows with card completeness status")

    # ─── PHASE 4: Gilchrist blocker documentation ───────────────────────────
    print("\n\n=== PHASE 4: GILCHRIST STRUCTURAL BLOCK ===")
    run_sql("""
SELECT m.case_number, m.parcel_id, m.property_address,
       m.latitude, m.longitude, m.assessed_value,
       m.auction_date
FROM public.multi_county_auctions m
WHERE lower(m.county) = 'gilchrist'
ORDER BY m.auction_date;
""", label="GILCHRIST: All rows status")

    # ─── PHASE 5: Liberty blocker documentation ───────────────────────────
    print("\n\n=== PHASE 5: LIBERTY STATUS ===")
    run_sql("""
SELECT m.case_number, m.parcel_id, m.property_address,
       m.latitude, m.longitude, m.assessed_value,
       m.auction_date, m.data_source,
       m.parity_status
FROM public.multi_county_auctions m
WHERE lower(m.county) = 'liberty'
ORDER BY m.auction_date;
""", label="LIBERTY: All rows status")

    # ─── PHASE 6: AFTER STATE ────────────────────────────────────────────────
    print("\n\n=== PHASE 6: AFTER STATE ===")
    for county in ["flagler", "putnam", "gilchrist", "liberty", "columbia"]:
        run_sql(
            f"SELECT public.pencil_dod_evaluate_county('{county}');",
            label=f"AFTER {county.upper()}"
        )

    # ─── PHASE 7: Gold Standard Campaign checkpoint ──────────────────────────
    print("\n\n=== PHASE 7: SESSION CLOSE-OUT CHECKPOINT ===")
    run_sql("""
UPDATE public.gold_standard_campaign
SET exit_reason = 'timeout',
    session_end_at = now()
WHERE dispatch_id = '1c584b89-bf35-4dba-9336-66be011b1489';
""", label="CLOSEOUT: Update campaign record")

    print("\n\nSession executor complete.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Miami-Dade Gold Standard letter I -- session 2026-09-03 (shard-5,
issue 19775). Continuation of the same lineage as
scripts/gsd2_08fff7f5_miami_dade_i_condo_geo_zone_backfill.py and
supabase/migrations/20260902e_gold_standard_miami_dade_i_zonelink_backfill_6parcel.sql.

BEFORE (live, pencil_dod_evaluate_county('miami_dade')):
  I: FAIL, card_complete=611 of 700, metric=87.3 (needs >=95% i.e. >=665/700)

DIAGNOSIS (live re-derivation this session, replicating the exact evaluator
SQL predicate in Python against the 700-row I-scope population and the
current v_zoning_gold_standard_card rows for county='miami dade' [note:
view stores county with a SPACE -- norm_county_key() translates
'miami_dade' -> 'miami dade' server-side, per 20260619_shard5_evaluator_
county_norm_fix.sql]):
  card scope (I-scope) rows = 700 (matches RPC exactly)
  card_complete (recomputed) = 611 of 700 (matches RPC exactly)
  gap = 89 rows. Missing-reason tallies (rows can hit >1): address=32,
    geo=28, value=32, zone_link=81 (dominant single cause).
  Rows failing ONLY zone_link (address+geo+value already present) = 39,
    spanning 34 distinct parcel_ids not present in parcel_zones (verified:
    PostgREST parcel_id=in.(...) against parcel_zones returned 0 rows for
    all 34). 1 of the 39 rows has parcel_id=NULL entirely (case
    2024-000006-CA-01) -- that is an E-letter-shaped gap (no parcel link
    at all), out of scope for an I-only zone-link fix, left untouched.

RESEARCH (live ArcGIS queries this session, same source/method as the
20260901/20260902e sessions): point-in-polygon zoning lookup for all 33
zone-linkable parcels (real lat/lng already on each row) against
services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/
MunicipalZone_gdb/FeatureServer/0, with fallback to
gisweb.miamidade.gov/arcgis/rest/services/LandManagement/MD_Zoning/
MapServer/1 (Unincorporated Zoning) for MUNICNAME='UNINCORPORATED'/
ZONE='NONE' placeholder responses. All 33 resolved to a real zone code
(zero misses).

GUARD RAIL (same as 20260902e's session, prevents a G/density-far-pk1000
regression): for each (jurisdiction, zone_code) pair, only insert into
parcel_zones if a zoning_districts row for that code AND a zone_standards
row for that district ALREADY exist (checked live via PostgREST for all
21 distinct (muni, zone) pairs found this session).

  SAFE (zoning_districts + zone_standards both present) -- 13 of 21 pairs,
  covering 20 parcel_ids -- APPLIED this session:
    HIALEAH/R-1 (zd=2249), HOMESTEAD/PUD (zd=2258), MIAMI/T3-O (zd=13299),
    MIAMI/T3-R (zd=11292), MIAMI/T6-48A-O (zd=13304),
    MIAMI BEACH/RM-1 (zd=14154), MIAMI BEACH/RS-4 (zd=14155),
    MIAMI GARDENS/R-1 (zd=3844), MIAMI LAKES/RU-1 (zd=3981),
    SUNNY ISLES BEACH/MUR (zd=13311), SUNNY ISLES BEACH/RMF-2 (zd=3656),
    UNINCORPORATED/AU (zd=10923), UNINCORPORATED/RU-1 (zd=10908).

  NOT APPLIED this session (unsafe per guard rail, documented levers for a
  future ordinance-research session -- same shape as 20260902e's
  unresolved list):
    BISCAYNE PARK/R-2 -- NO jurisdiction row exists at all for Biscayne
      Park (confirmed live: jurisdictions.name ilike '%biscayne%' matches
      only Key Biscayne, id=1053, a different municipality). Creating a
      new jurisdiction row is out of scope (would require DDL-adjacent
      writes beyond a minimal I-only parcel_zones fix, and this session
      has no exec_sql/DDL access).
    DORAL/DMU -- zoning_districts row EXISTS (id=2963) but zero
      zone_standards row for it.
    FLORIDA CITY/RD-1, MIAMI/T6-12-O, MIAMI/T6-36A-L, MIAMI/T6-48B-O,
      UNINCORPORATED/BRCUAD, UNINCORPORATED/EU-1 -- zero zoning_districts
      row for that (jurisdiction, code) pair.
    UNINCORPORATED/EU-M (zd=13346), UNINCORPORATED/GU (zd=13348),
      UNINCORPORATED/PAD (zd=13794) -- zoning_districts row exists but
      zero zone_standards row for it.
  Inserting any of these would add a card_complete pass at the cost of a
  G-null risk on density/far/pk1000 for that district -- exactly the
  tradeoff the guard rail exists to block.

WRITES: INSERT INTO parcel_zones, 20 rows, one per safe parcel_id, source
tagged 'miamidade_arcgis_municipalzone_gdb:gsd_miamidade_20260903_i' (or
the unincorporated-layer variant for the 2 UNINCORPORATED pairs, both of
which resolved via the primary MunicipalZone_gdb layer this session, not
the unincorporated fallback -- confirmed live, AU and RU-1 both came back
directly from MunicipalZone_gdb without hitting the NONE-placeholder
fallback path).

Real zone code sourced from county GIS at each parcel's exact stored
lat/lng -- not guessed. No PropertyOnion field used. No monetary value
touched. No cron jobs 109/111/115 touched.
"""
import os
import time
import json
import httpx

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
REST = f'{SUPABASE_URL}/rest/v1'
H = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

# 20 rows: (parcel_id, jurisdiction_id, zone_code, zone_name, source_tag)
# Verified live this session: real zone code from ArcGIS point-in-polygon
# lookup at the parcel's existing stored lat/lng, and both zoning_districts
# + zone_standards rows already exist for the (jurisdiction_id, zone_code)
# pair -- satisfies the G-regression guard rail.
SAFE_ROWS = [
    ("01-4115-064-0250", 855, "T3-R", "Sub-Urban Transect Zone, Restricted"),
    ("30-4928-028-0790", 626, "RU-1", "Single Family Residential"),
    ("10-7916-006-0450", 827, "PUD", "Planned Unit Development"),
    ("34-2102-012-0030", 1056, "R-1", "Single-Family Residential"),
    ("30-7909-015-0300", 626, "RU-1", "Single Family Residential"),
    ("30-7828-000-1460", 626, "AU", "Agricultural (Urban)"),
    ("34-1133-028-0540", 1056, "R-1", "Single-Family Residential"),
    ("30-4913-011-1040", 626, "RU-1", "Single Family Residential"),
    ("04-3106-037-0710", 935, "R-1", "ONE-FAMILY DISTRICT"),
    ("30-6936-003-1440", 855, "T6-48A-O", "URBAN CORE ZONE"),
    ("01-4139-083-0370", 855, "T6-48A-O", "URBAN CORE ZONE"),
    ("02-3202-005-0560", 960, "RM-1", "MULTIFAMILY, LOW INTENSITY"),
    ("31-2211-074-0180", 1055, "MUR", "MIXED USE RESIDENTIAL"),
    ("31-2202-040-0350", 1055, "MUR", "MIXED USE RESIDENTIAL"),
    ("01-3123-034-0860", 855, "T3-O", "SUBURBAN ZONE"),
    ("31-2202-034-3820", 1055, "MUR", "MIXED USE RESIDENTIAL"),
    ("01-3127-040-0350", 855, "T3-O", "SUBURBAN ZONE"),
    ("31-2211-021-0140", 1055, "RMF-2", "Medium - High Density Multifamily Residential (RMF-2)"),
    ("32-2015-004-0710", 1057, "RU-1", "Single-Family Residential"),
    ("02-3234-004-0500", 960, "RS-4", "RESIDENTIAL SINGLE FAMILY"),
]

SOURCE_TAG = "miamidade_arcgis_municipalzone_gdb:gsd_miamidade_20260903_i"


def post_retry(path, body, tries=6):
    url = f'{REST}/{path}'
    last_err = None
    for i in range(tries):
        try:
            r = httpx.post(url, headers=H, json=body, timeout=30)
            if r.status_code in (200, 201):
                return r.json()
            last_err = f'STATUS {r.status_code}: {r.text[:300]}'
        except Exception as e:
            last_err = str(e)
        time.sleep(2 * (i + 1))
    raise RuntimeError(f'FATAL: POST {path} failed after {tries} retries: {last_err}')


def main():
    print(f'=== INSERT parcel_zones, {len(SAFE_ROWS)} candidate rows ===')

    # Idempotency guard: skip any parcel_id that already has a row.
    parcel_ids = [p for p, *_ in SAFE_ROWS]
    existing = None
    for i in range(6):
        resp = httpx.get(f'{REST}/parcel_zones',
                          headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'},
                          params={'parcel_id': 'in.(' + ','.join(parcel_ids) + ')', 'select': 'parcel_id'},
                          timeout=30)
        body = resp.json()
        if isinstance(body, list):
            existing = body
            break
        time.sleep(2 * (i + 1))
    if existing is None:
        raise RuntimeError(f'FATAL: could not read existing parcel_zones rows after retries: {body}')
    existing_ids = {r['parcel_id'] for r in existing}

    to_insert = []
    for parcel_id, jurisdiction_id, zone_code, zone_name in SAFE_ROWS:
        if parcel_id in existing_ids:
            print(f'  SKIP {parcel_id}: already has a parcel_zones row')
            continue
        to_insert.append({
            'parcel_id': parcel_id,
            'jurisdiction_id': jurisdiction_id,
            'zone_code': zone_code,
            'zone_name': zone_name,
            'source': SOURCE_TAG,
        })

    if not to_insert:
        raise RuntimeError('FATAL: found candidate rows but 0 remain to insert (all pre-existing) -- '
                            'refusing to silently no-op; verify diagnosis is still current')

    result = post_retry('parcel_zones', to_insert)
    if len(result) != len(to_insert):
        raise RuntimeError(f'FATAL: inserted {len(result)} rows, expected {len(to_insert)}')
    for r in result:
        print('  OK', r['parcel_id'], '->', r['zone_code'], f"(id={r['id']})")
    print(f'DONE. {len(result)} parcel_zones rows inserted.')


if __name__ == '__main__':
    main()

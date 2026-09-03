#!/usr/bin/env python3
"""Miami-Dade Gold Standard letter I -- session 2026-09-03, part 2 (shard-5,
issue 19775). Continuation of gold_standard_miami_dade_20260903_i_zonelink_
backfill.py (which fixed the 20 zone-link-only rows, I: 611->631).

DIAGNOSIS (live, re-triage after part 1): of the remaining 58 incomplete
rows, 25 carry a real Miami-Dade folio-format parcel_id (NN-NNNN-NNN-NNNN)
but are missing address and/or geo and/or assessed/market value. Queried
live against the county's PaParcel cadastral layer
(gisweb.miamidade.gov/arcgis/rest/services/MD_LandInformation/MapServer/26)
for TRUE_SITE_ADDR / TOTAL_VAL_CUR / centroid geometry for all 25.

NEVER-LIE guard: TOTAL_VAL_CUR returned 0 for most of these (17 of 25,
mostly condo-unit folios resolved via the 9-digit master-parcel fallback --
the county's TOTAL_VAL_CUR is tracked per-unit but the fallback lookup hits
the building's master record, which correctly has no standalone assessed
value of its own). A total_val of 0 is NOT a real assessed value -- writing
assessed_value=0 would be a false "worthless property" claim, not a
faithful absence-of-data signal. Per guardrail 6 (real data only, BLANK >
WRONG), only strictly-positive TOTAL_VAL_CUR values were treated as usable;
zero/missing values were left untouched.

Of the 25, 17 had at least one genuinely real, positive field to add
(address and/or geo and/or a positive assessed value). Point-in-polygon
zoning lookup was then run for all 17 at their best-known lat/lng (existing
or newly geocoded) against the same MunicipalZone_gdb /
Unincorporated-Zoning-layer-6 sources used in part 1, with the same
zoning_districts+zone_standards existence guard rail.

RESULT: of the 17, only 3 rows have ALL FOUR card_complete conditions
(address, geo, value, zone_link) resolvable with real data this session --
the other 14 remain incomplete because they are also missing a positive
assessed_value (11), a real address (3, one of which additionally resolved
zone='NONE' with no polygon match), or a safe zoning_districts/
zone_standards pair (2 -- Sunny Isles Beach MUR/TCD/RMF-2 jurisdiction
exists but no district row for some codes, and 2026A00227's Sunny Isles
Beach RMF-2 pair IS safe but its assessed value is still 0/missing).
Writing only the resolvable fields on those 14 (e.g. geo without value)
does not move card_complete and is deferred as documented residual --
not written this session to avoid scope creep on writes that don't verify
against the metric.

3 rows fixed this session (full expected +3 to card_complete):
  2026A00211 (parcel 06-2228-058-0510): geo backfilled from PaParcel
    centroid (was missing lat/lng only; address/value already present).
    Zone: North Miami R-6 (zoning_districts id=13310, zone_standards
    confirmed present).
  2026A00205 (parcel 03-4120-065-0860): geo backfilled from PaParcel
    centroid (was missing lat/lng only; address/value already present).
    Zone: Coral Gables MX2 (zoning_districts id=13684, zone_standards
    confirmed present).
  2026A00255 (parcel 01-4105-038-0020): assessed_value=880110 backfilled
    from PaParcel TOTAL_VAL_CUR (real, positive, unit-level condo value;
    address/geo already present). Zone: Miami T3-R (zoning_districts
    id=11292, zone_standards confirmed present -- same district already
    used safely in part 1's script).

No PropertyOnion field used. No fabricated/zero-as-real values written.
No cron jobs 109/111/115 touched.
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

MCA_UPDATES = [
    # (case_number, {field: value})
    ('2026A00211', {'latitude': 25.8989968277634, 'longitude': -80.16217850596759}),
    ('2026A00205', {'latitude': 25.733987752297214, 'longitude': -80.26055748478115}),
    ('2026A00255', {'assessed_value': 880110}),
]

PARCEL_ZONE_INSERTS = [
    # (parcel_id, jurisdiction_id, zone_code, zone_name)
    ('06-2228-058-0510', 849, 'R-6', None),
    ('03-4120-065-0860', 964, 'MX2', None),
    ('01-4105-038-0020', 855, 'T3-R', 'Sub-Urban Transect Zone, Restricted'),
]
SOURCE_TAG = 'miamidade_arcgis_municipalzone_gdb:gsd_miamidade_20260903_i_part2'


def patch_retry(id_or_case, fields, key='case_number', tries=6):
    url = f'{REST}/multi_county_auctions?county=eq.miami_dade&{key}=eq.{id_or_case}'
    data = json.dumps(fields).encode()
    last_err = None
    for i in range(tries):
        try:
            r = httpx.patch(url, headers=H, content=data, timeout=30)
            if r.status_code == 200:
                body = r.json()
                if len(body) != 1:
                    raise RuntimeError(f'PATCH {id_or_case} matched {len(body)} rows, expected 1')
                return body[0]
            last_err = f'STATUS {r.status_code}: {r.text[:300]}'
        except Exception as e:
            last_err = str(e)
        time.sleep(2 * (i + 1))
    raise RuntimeError(f'FATAL: PATCH {id_or_case} failed after {tries} retries: {last_err}')


def zoning_district_name(jurisdiction_id, code):
    r = httpx.get(f'{REST}/zoning_districts',
                  headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'},
                  params={'jurisdiction_id': f'eq.{jurisdiction_id}', 'code': f'eq.{code}', 'select': 'name'},
                  timeout=30).json()
    return r[0]['name'] if r else None


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
    print('=== PATCH multi_county_auctions (geo/value backfill, 3 rows) ===')
    n_mca = 0
    for case_number, fields in MCA_UPDATES:
        r = patch_retry(case_number, fields)
        print('  OK', case_number, '->', fields)
        n_mca += 1
    if n_mca == 0:
        raise RuntimeError('FATAL: found candidate mca rows but wrote 0')

    print('\n=== INSERT parcel_zones (3 rows) ===')
    parcel_ids = [p for p, *_ in PARCEL_ZONE_INSERTS]
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
        raise RuntimeError(f'FATAL: could not read existing parcel_zones rows: {body}')
    existing_ids = {r['parcel_id'] for r in existing}

    to_insert = []
    for parcel_id, jurisdiction_id, zone_code, zone_name in PARCEL_ZONE_INSERTS:
        if parcel_id in existing_ids:
            print(f'  SKIP {parcel_id}: already has a parcel_zones row')
            continue
        if zone_name is None:
            zone_name = zoning_district_name(jurisdiction_id, zone_code) or zone_code
        to_insert.append({
            'parcel_id': parcel_id,
            'jurisdiction_id': jurisdiction_id,
            'zone_code': zone_code,
            'zone_name': zone_name,
            'source': SOURCE_TAG,
        })

    if not to_insert:
        raise RuntimeError('FATAL: found candidate parcel_zones rows but 0 remain to insert')

    result = post_retry('parcel_zones', to_insert)
    if len(result) != len(to_insert):
        raise RuntimeError(f'FATAL: inserted {len(result)} rows, expected {len(to_insert)}')
    for r in result:
        print('  OK', r['parcel_id'], '->', r['zone_code'], f"(id={r['id']})")

    print(f'\nDONE. {n_mca} multi_county_auctions rows patched, {len(result)} parcel_zones rows inserted.')


if __name__ == '__main__':
    main()

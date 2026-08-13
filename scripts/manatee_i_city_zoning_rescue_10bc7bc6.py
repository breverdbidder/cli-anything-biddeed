#!/usr/bin/env python3
"""
Manatee I: rescue the "CITY placeholder" residual left by shard_manatee_i_zoning.py.

That script queries the COUNTY's ZONEOFFICIAL layer only; for parcels inside an
incorporated city (Bradenton, Palmetto, Holmes Beach, Longboat Key, Anna Maria,
Bradenton Beach) it correctly returns ZONELABEL='CITY' (a placeholder -- the
county doesn't regulate zoning inside city limits) and skips the write rather
than guessing.

Discovered this session: Manatee's own GIS_PARCELS FeatureServer (already used
by scripts/shard_manatee_e_linkage.py for address matching) carries a genuine
per-parcel `ZONING` attribute sourced from each city's own zoning map (e.g.
"LBK_R-4SF" for Longboat Key, "BR_R-1" for Bradenton, "HB_R-3" for Holmes
Beach, "PL_RS-3" for Palmetto) -- verified live against several parcels. This
script re-queries GIS_PARCELS by PARCEL_ID (not address) for every manatee
auction parcel_id that (a) has no parcel_zones row yet and (b) is confirmed
CITY via ZONEOFFICIAL, and writes zone_code from GIS_PARCELS.ZONING when
present and non-null.

dispatch_id: 10bc7bc6-eefb-4073-8d69-18a6a83788a0
"""
import os
import json
import httpx

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}
ZONE_URL = 'https://services1.arcgis.com/t03WDvnSR7gSDOB2/arcgis/rest/services/ZONEOFFICIAL/FeatureServer/0/query'
PARCELS_URL = 'https://services1.arcgis.com/t03WDvnSR7gSDOB2/arcgis/rest/services/GIS_PARCELS/FeatureServer/0/query'

JURISDICTION_BY_CITY = {
    'BRADENTON': 888,
    'PALMETTO': 857,
    'HOLMES BEACH': 940,
    'LONGBOAT KEY': 1047,
    'ANNA MARIA': 890,
    'BRADENTON BEACH': 1046,
}


def fetch_candidates(client):
    """Manatee auction parcel_ids with lat/lon and no parcel_zones row yet."""
    existing = set()
    offset = 0
    while True:
        r = client.get(f'{BASE}/parcel_zones', headers=HEADERS,
                        params={'select': 'parcel_id', 'limit': '5000', 'offset': str(offset)})
        batch = r.json()
        for row in batch:
            existing.add(row['parcel_id'])
        if len(batch) < 5000:
            break
        offset += 5000

    rows, offset, page = [], 0, 1000
    while True:
        r = client.get(f'{BASE}/multi_county_auctions', headers=HEADERS, params={
            'select': 'case_number,parcel_id,latitude,longitude',
            'county': 'eq.manatee', 'parcel_id': 'not.is.null',
            'latitude': 'not.is.null', 'longitude': 'not.is.null',
            'offset': str(offset), 'limit': str(page),
        })
        batch = r.json()
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page

    seen = set()
    out = []
    for row in rows:
        pid = row['parcel_id']
        if pid in existing or pid in seen:
            continue
        seen.add(pid)
        out.append(row)
    return out


def main():
    with httpx.Client(timeout=30) as client:
        candidates = fetch_candidates(client)
        print(f'manatee: {len(candidates)} unlinked parcel_ids to check for CITY-placeholder rescue')

        to_insert = []
        checked = 0
        for row in candidates:
            checked += 1
            r = client.get(ZONE_URL, params={
                'geometry': f"{row['longitude']},{row['latitude']}",
                'geometryType': 'esriGeometryPoint', 'inSR': '4326',
                'spatialRel': 'esriSpatialRelIntersects',
                'outFields': 'ZONELABEL', 'f': 'json', 'returnGeometry': 'false',
            })
            if r.status_code != 200:
                continue
            feats = r.json().get('features', [])
            if not feats or feats[0]['attributes'].get('ZONELABEL') != 'CITY':
                continue  # not a city placeholder — shard_manatee_i_zoning.py already handles it

            r2 = client.get(PARCELS_URL, params={
                'where': f"PARCEL_ID='{row['parcel_id']}'",
                'outFields': 'PARCEL_ID,PROP_CITYNAME,ZONING',
                'f': 'json', 'returnGeometry': 'false',
            })
            if r2.status_code != 200:
                continue
            pfeats = r2.json().get('features', [])
            if not pfeats:
                continue
            a = pfeats[0]['attributes']
            city = (a.get('PROP_CITYNAME') or '').strip().upper()
            zoning = a.get('ZONING')
            jur_id = JURISDICTION_BY_CITY.get(city)
            if not zoning or not jur_id:
                print(f'  {row["parcel_id"]} ({city}): no ZONING value or unknown jurisdiction — skip')
                continue
            to_insert.append({
                'parcel_id': row['parcel_id'],
                'jurisdiction_id': jur_id,
                'zone_code': zoning,
                'source': 'Manatee GIS_PARCELS FeatureServer ZONING field (city zoning rescue for ZONEOFFICIAL CITY placeholder)',
            })

        print(f'manatee: checked={checked} city_zoning_found={len(to_insert)}')

        inserted = 0
        for i in range(0, len(to_insert), 200):
            chunk = to_insert[i:i + 200]
            r = client.post(f'{BASE}/parcel_zones', headers=HEADERS, content=json.dumps(chunk))
            if r.status_code in (200, 201):
                inserted += len(chunk)
            else:
                print(f'insert failed {r.status_code}: {r.text[:300]}')

        print(f'manatee: DONE inserted {inserted} parcel_zones rows (city zoning rescue)')

        ev = client.post(f'{BASE}/rpc/pencil_dod_evaluate_county', headers=HEADERS,
                          content=json.dumps({'p_county': 'manatee'})).json()
        print(json.dumps({'I': ev.get('I'), 'E': ev.get('E'), 'G': ev.get('G')}, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Manatee I: expand parcel_zones coverage via point-in-polygon query against
Manatee County's official unincorporated zoning layer (ZONEOFFICIAL FeatureServer),
for the parcel_ids linked by shard_manatee_e_linkage.py (which have lat/lon).

ZONEOFFICIAL is COUNTY zoning only: parcels inside city limits return ZONELABEL='CITY'
(a placeholder — the county doesn't regulate zoning inside incorporated cities). Those are
skipped, not guessed, since we do not have Bradenton/Palmetto/etc. city zoning layers.
Only genuine unincorporated-area zone codes are written, jurisdiction_id=1257
(Unincorporated Manatee County, verified in `jurisdictions` table).

dispatch_id: a22499ac-311b-4b6d-ad24-5d9422b2cee2
"""
import os, json, asyncio
import httpx

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}
ZONE_URL = 'https://services1.arcgis.com/t03WDvnSR7gSDOB2/arcgis/rest/services/ZONEOFFICIAL/FeatureServer/0/query'
UNINCORPORATED_JURISDICTION_ID = 1257
SEM = asyncio.Semaphore(10)


async def fetch_candidates(client):
    """Manatee auctions with parcel_id + lat/lon, whose parcel_id isn't already in parcel_zones."""
    existing = set()
    r = await client.get(f'{BASE}/parcel_zones', headers=HEADERS,
                          params={'select': 'parcel_id', 'jurisdiction_id': 'eq.1257', 'limit': '5000'})
    for row in r.json():
        existing.add(row['parcel_id'])

    rows, offset, page = [], 0, 1000
    while True:
        h = {**HEADERS, 'Range-Unit': 'items', 'Range': f'{offset}-{offset+page-1}'}
        r = await client.get(f'{BASE}/multi_county_auctions', headers=h, params={
            'select': 'case_number,parcel_id,latitude,longitude',
            'county': 'eq.manatee', 'parcel_id': 'not.is.null',
            'latitude': 'not.is.null', 'longitude': 'not.is.null',
        })
        batch = r.json()
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page

    seen_parcel = set()
    candidates = []
    for row in rows:
        pid = row['parcel_id']
        if pid in existing or pid in seen_parcel:
            continue
        seen_parcel.add(pid)
        candidates.append(row)
    return candidates


async def query_zone(client, row):
    async with SEM:
        r = await client.get(ZONE_URL, params={
            'geometry': f"{row['longitude']},{row['latitude']}",
            'geometryType': 'esriGeometryPoint',
            'inSR': '4326',
            'spatialRel': 'esriSpatialRelIntersects',
            'outFields': 'ZONELABEL,SPECIAL_DE',
            'f': 'json',
            'returnGeometry': 'false',
        }, timeout=30)
        if r.status_code != 200:
            return row, None
        feats = r.json().get('features', [])
        if not feats:
            return row, None
        label = feats[0]['attributes'].get('ZONELABEL')
        return row, label


async def main():
    async with httpx.AsyncClient() as client:
        candidates = await fetch_candidates(client)
        print(f'manatee: {len(candidates)} distinct parcel_ids to attempt zoning lookup')

        results = await asyncio.gather(*[query_zone(client, row) for row in candidates])

        to_insert = []
        city_placeholder, no_result = 0, 0
        for row, label in results:
            if label is None:
                no_result += 1
                continue
            if label == 'CITY':
                city_placeholder += 1
                continue
            to_insert.append({
                'parcel_id': row['parcel_id'],
                'jurisdiction_id': UNINCORPORATED_JURISDICTION_ID,
                'zone_code': label,
                'source': 'ArcGIS ZONEOFFICIAL live spatial query (manatee county unincorporated zoning)',
            })

        print(f'manatee: zone_code found={len(to_insert)} city_placeholder(skipped)={city_placeholder} no_result(skipped)={no_result}')

        inserted = 0
        for i in range(0, len(to_insert), 200):
            chunk = to_insert[i:i + 200]
            r = await client.post(f'{BASE}/parcel_zones', headers=HEADERS, content=json.dumps(chunk), timeout=60)
            if r.status_code in (200, 201):
                inserted += len(chunk)
            else:
                print(f'insert failed {r.status_code}: {r.text[:300]}')

        print(f'manatee: DONE inserted {inserted} parcel_zones rows')

        ev = (await client.post(f'{BASE}/rpc/pencil_dod_evaluate_county', headers=HEADERS,
                                 content=json.dumps({'p_county': 'manatee'}), timeout=30)).json()
        print(json.dumps({'I': ev.get('I'), 'G': ev.get('G')}, indent=2))


if __name__ == '__main__':
    asyncio.run(main())

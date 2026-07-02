#!/usr/bin/env python3
"""
Manatee E-linkage: parcel_id backfill via Manatee County GIS_PARCELS ArcGIS FeatureServer.

Endpoint VERIFIED live 2026-07-02 (ultraloop audit wf_34c2bebb-38d):
  https://services1.arcgis.com/t03WDvnSR7gSDOB2/arcgis/rest/services/GIS_PARCELS/FeatureServer/0
Fields: PARCEL_ID, PRIMARY_ADDRESS, PROP_HN, PROP_CITYNAME, LAT, LON.

Strategy: batch-query by (city, house_number), then require an EXACT normalized
address string match before writing parcel_id/lat/lon. No fuzzy/best-guess linkage —
a wrong parcel_id is worse than no parcel_id (E denominator is auctions_total, but a
false link poisons downstream I/G/J joins). Non-matches are left NULL and reported.

dispatch_id: a22499ac-311b-4b6d-ad24-5d9422b2cee2
"""
import os, re, json, sys
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
ARCGIS_URL = 'https://services1.arcgis.com/t03WDvnSR7gSDOB2/arcgis/rest/services/GIS_PARCELS/FeatureServer/0/query'

UNIT_RE = re.compile(r'\s+(APT|UNIT|STE|SUITE|#)\s*\S+$', re.IGNORECASE)


def normalize(addr: str, strip_unit: bool = True) -> str:
    """Uppercase, optionally strip trailing unit/apt tokens, collapse whitespace."""
    a = addr.upper().strip()
    if strip_unit:
        a = UNIT_RE.sub('', a)
    a = re.sub(r'\s+', ' ', a)
    return a.strip()


def parse_mca_address(full_address: str, city_hint: str):
    """MCA property_address is 'STREET LINE, CITY, FL, ZIP'. Extract street line + house number.
    Returns (house_number, city, norm_with_unit, norm_base_no_unit)."""
    if not full_address:
        return None, None, None, None
    street_line = full_address.split(',')[0].strip()
    norm_full = normalize(street_line, strip_unit=False)
    norm_base = normalize(street_line, strip_unit=True)
    m = re.match(r'^(\d+)\s', norm_base)
    if not m:
        return None, None, None, None
    hn = m.group(1)
    city = (city_hint or '').strip().upper()
    return hn, city, norm_full, norm_base


def fetch_unlinked(client):
    rows, offset, page = [], 0, 1000
    while True:
        headers = {**HEADERS, 'Range-Unit': 'items', 'Range': f'{offset}-{offset+page-1}'}
        params = {
            'select': 'case_number,property_address,city,zip,latitude,longitude',
            'county': 'eq.manatee',
            'parcel_id': 'is.null',
            'property_address': 'not.is.null',
        }
        r = client.get(f'{BASE}/multi_county_auctions', headers=headers, params=params, timeout=60)
        if r.status_code not in (200, 206):
            raise SystemExit(f'fetch failed {r.status_code}: {r.text[:200]}')
        batch = r.json()
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def query_arcgis_batch(client, city: str, house_numbers: list):
    hn_list = ','.join(f"'{hn}'" for hn in house_numbers)
    where = f"PROP_CITYNAME='{city}' AND PROP_HN IN ({hn_list})"
    r = client.post(ARCGIS_URL, data={
        'where': where,
        'outFields': 'PARCEL_ID,PRIMARY_ADDRESS,PROP_HN,PROP_CITYNAME,LAT,LON',
        'f': 'json',
        'returnGeometry': 'false',
        'resultRecordCount': '2000',
    }, timeout=90)
    if r.status_code != 200:
        print(f'  ArcGIS query failed {r.status_code} for city={city}', file=sys.stderr)
        return []
    d = r.json()
    if 'error' in d:
        print(f'  ArcGIS error for city={city}: {d["error"]}', file=sys.stderr)
        return []
    return d.get('features', [])


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main():
    with httpx.Client(timeout=120) as client:
        unlinked = fetch_unlinked(client)
        print(f'manatee: {len(unlinked)} unlinked rows with property_address to attempt')

        by_city = {}
        parsed = {}
        for row in unlinked:
            hn, city, norm_full, norm_base = parse_mca_address(row['property_address'], row.get('city'))
            if not hn or not city:
                continue
            parsed[row['case_number']] = (hn, city, norm_full, norm_base, row)
            by_city.setdefault(city, set()).add(hn)

        print(f'manatee: {len(parsed)} rows parsed with house_number+city; {len(by_city)} distinct cities')

        # candidate lookup: (city, house_number) -> [(norm_full, norm_base, PARCEL_ID, LAT, LON), ...]
        candidates = {}
        for city, hns in by_city.items():
            hns = sorted(hns)
            for chunk in chunked(hns, 40):
                feats = query_arcgis_batch(client, city, chunk)
                for f in feats:
                    a = f['attributes']
                    key = (city, a['PROP_HN'])
                    norm_full = normalize(a['PRIMARY_ADDRESS'], strip_unit=False)
                    norm_base = normalize(a['PRIMARY_ADDRESS'], strip_unit=True)
                    candidates.setdefault(key, []).append(
                        (norm_full, norm_base, a['PARCEL_ID'], a.get('LAT'), a.get('LON')))
            print(f'  {city}: queried {len(hns)} house numbers')

        matched, ambiguous, no_match = [], 0, 0
        for case_number, (hn, city, norm_full, norm_base, row) in parsed.items():
            cands = candidates.get((city, hn), [])
            # Pass 1: exact match INCLUDING unit suffix (unit-level parcel precision)
            exact_full = [c for c in cands if c[0] == norm_full]
            chosen = None
            if len(exact_full) >= 1 and len({c[2] for c in exact_full}) == 1:
                chosen = exact_full[0]
            else:
                # Pass 2: base address (no unit) match, only if ALL candidates
                # sharing that base address resolve to a single parcel_id
                exact_base = [c for c in cands if c[1] == norm_base]
                if exact_base and len({c[2] for c in exact_base}) == 1:
                    chosen = exact_base[0]
                elif exact_base:
                    ambiguous += 1
                    continue
            if chosen:
                _, _, parcel_id, lat, lon = chosen
                matched.append({
                    'case_number': case_number,
                    'parcel_id': parcel_id,
                    'latitude': row['latitude'] if row.get('latitude') is not None else lat,
                    'longitude': row['longitude'] if row.get('longitude') is not None else lon,
                })
            else:
                no_match += 1

        print(f'manatee: matched={len(matched)} ambiguous={ambiguous} no_match={no_match}')

        updated = 0
        for m in matched:
            payload = {'parcel_id': m['parcel_id']}
            if m['latitude'] is not None:
                payload['latitude'] = m['latitude']
            if m['longitude'] is not None:
                payload['longitude'] = m['longitude']
            r = client.patch(
                f'{BASE}/multi_county_auctions',
                headers=HEADERS,
                params={'case_number': f'eq.{m["case_number"]}', 'county': 'eq.manatee'},
                content=json.dumps(payload),
                timeout=30,
            )
            if r.status_code in (200, 204):
                updated += 1
            else:
                print(f'  update failed for {m["case_number"]}: {r.status_code} {r.text[:150]}', file=sys.stderr)

        print(f'manatee: DONE parcel_id updated for {updated} rows')

        ev = client.post(f'{BASE}/rpc/pencil_dod_evaluate_county', headers=HEADERS,
                          content=json.dumps({'p_county': 'manatee'}), timeout=30).json()
        print(json.dumps({'E': ev.get('E'), 'I': ev.get('I'), 'C': ev.get('C'), 'D': ev.get('D')}, indent=2))


if __name__ == '__main__':
    main()

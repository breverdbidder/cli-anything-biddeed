#!/usr/bin/env python3
"""
dod_rest_check.py — DoD verification via Supabase REST API (no Management API).

Paginates multi_county_auctions?select=county&auction_date=gte.TODAY&...
(Supabase caps REST responses at 1000 rows — must paginate to see all counties).
Normalizes county names to lowercase before counting distinct.

Env (required): SUPABASE_URL, SUPABASE_KEY, TODAY (YYYY-MM-DD)
Output: JSON {distinct: N, breakdown: [{county, n}], total_rows: N}
"""
import json, os, sys, urllib.request, collections

SB    = os.environ.get('SUPABASE_URL', '').rstrip('/')
KEY   = os.environ.get('SUPABASE_KEY', '')
TODAY = os.environ.get('TODAY', '')

if not SB or not KEY or not TODAY:
    print('ERROR: SUPABASE_URL, SUPABASE_KEY, TODAY all required', file=sys.stderr)
    sys.exit(1)

PAGE = 1000
data = []
offset = 0
while True:
    url = (
        f'{SB}/rest/v1/multi_county_auctions'
        '?select=county'
        f'&auction_date=gte.{TODAY}'
        '&source_platform=not.in.(propertyonion_orphan,po_api)'
        f'&order=id.asc&limit={PAGE}&offset={offset}'
    )
    req = urllib.request.Request(url)
    req.add_header('apikey', KEY)
    req.add_header('Authorization', f'Bearer {KEY}')
    req.add_header('Accept', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            page_data = json.loads(r.read())
    except Exception as e:
        print(f'ERROR: REST call failed at offset {offset}: {e}', file=sys.stderr)
        sys.exit(1)
    if not page_data:
        break
    data.extend(page_data)
    offset += len(page_data)
    print(f'INFO: fetched page offset={offset - len(page_data)}, got {len(page_data)} rows', file=sys.stderr)
    if len(page_data) < PAGE:
        break

# Normalize county to lowercase to deduplicate casing inconsistencies (e.g. 'Marion' vs 'marion')
counter = collections.Counter(row['county'].lower() for row in data)
distinct = len(counter)

DARK_39 = [
    'alachua', 'baker', 'bay', 'bradford', 'calhoun', 'citrus', 'clay',
    'columbia', 'escambia', 'flagler', 'gadsden', 'gilchrist', 'glades',
    'hamilton', 'hardee', 'hendry', 'hernando', 'highlands', 'jackson',
    'jefferson', 'lafayette', 'lake', 'leon', 'levy', 'liberty',
    'martin', 'monroe', 'okeechobee', 'pasco', 'putnam', 'santa_rosa',
    'seminole', 'st_johns', 'st_lucie', 'suwannee', 'taylor', 'union',
    'wakulla', 'walton',
]
breakdown = [{'county': c, 'n': counter.get(c, 0)} for c in DARK_39]

print(json.dumps({'distinct': distinct, 'breakdown': breakdown, 'total_rows': len(data)}))
print(f'INFO: {distinct} distinct counties across {len(data)} future auction rows', file=sys.stderr)

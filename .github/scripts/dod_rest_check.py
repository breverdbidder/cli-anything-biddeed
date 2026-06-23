#!/usr/bin/env python3
"""
dod_rest_check.py — DoD verification via Supabase REST API (no Management API).

Fetches multi_county_auctions?select=county&auction_date=gte.TODAY&...
and counts distinct counties. No Management API / no SUPABASE_ACCESS_TOKEN needed.

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

url = (
    f'{SB}/rest/v1/multi_county_auctions'
    '?select=county'
    f'&auction_date=gte.{TODAY}'
    '&source_platform=not.in.(propertyonion_orphan,po_api)'
    '&limit=100000'
)
req = urllib.request.Request(url)
req.add_header('apikey', KEY)
req.add_header('Authorization', f'Bearer {KEY}')
req.add_header('Accept', 'application/json')

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
except Exception as e:
    print(f'ERROR: REST call failed: {e}', file=sys.stderr)
    sys.exit(1)

counter = collections.Counter(row['county'] for row in data)
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

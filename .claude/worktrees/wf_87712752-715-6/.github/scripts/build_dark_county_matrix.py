#!/usr/bin/env python3
"""
build_dark_county_matrix.py — Build GHA matrix for 39 dark FL counties.

Reads /tmp/db_resp.json (realauction_subdomains query output) and the SLUGS
env var. Returns JSON {include: [...]} to stdout, merged with realtaxdeed
fallbacks for any county absent from the DB.

Env:
  SLUGS  — comma-separated county slugs
"""
import json, os, sys

SLUGS_ENV = os.environ.get('SLUGS', '')
if not SLUGS_ENV:
    print('ERROR: SLUGS env not set', file=sys.stderr)
    sys.exit(1)

slugs = [s.strip() for s in SLUGS_ENV.split(',') if s.strip()]

try:
    with open('/tmp/db_resp.json') as f:
        db = json.load(f)
    if not isinstance(db, list):
        db = []
except Exception as e:
    print(f'WARN: DB read failed ({e}), using all fallbacks', file=sys.stderr)
    db = []

db_set = {e['county_slug'] for e in db}
entries = []
for e in db:
    slug = e['county_slug']
    plat = e.get('platform') or 'realtaxdeed'
    entries.append({
        'county':    slug,
        'sale_type': e.get('sale_type') or 'tax_deed',
        'platform':  plat,
        'base_url':  e.get('base_url') or f'https://{slug}.{plat}.com',
    })

# Fallback: any county not in DB gets realtaxdeed / tax_deed
for slug in slugs:
    if slug not in db_set:
        entries.append({
            'county':    slug,
            'sale_type': 'tax_deed',
            'platform':  'realtaxdeed',
            'base_url':  f'https://{slug}.realtaxdeed.com',
        })

# Deduplicate by (county, sale_type) — DB entries win (appear first)
seen, deduped = set(), []
for e in entries:
    k = (e['county'], e['sale_type'])
    if k not in seen:
        seen.add(k)
        deduped.append(e)

print(json.dumps({'include': deduped}))
print(f'INFO: {len(db_set)} counties from DB, {len(slugs) - len(db_set)} fallbacks, {len(deduped)} total',
      file=sys.stderr)

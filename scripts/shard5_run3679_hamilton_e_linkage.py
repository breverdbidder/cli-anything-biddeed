#!/usr/bin/env python3
"""
Hamilton E-linkage: parcel_id backfill via Hamilton County Tax Collector property search.

Endpoint VERIFIED live 2026-07-11:
  POST https://www.hamiltoncountytaxcollector.com/Property/search
  (VisualGov platform, real Hamilton County government tax collector system)
  Fields: ownername, streetnumber, streetname, propertynumber, taxbillnumber,
  RollTypes, Years -> JSON envelope {"success":true,"result":"<json string>"}

Strategy: exact street-number + street-name match against the property_address already
on each MCA row (same standard as scripts/shard_manatee_e_linkage.py -- exact match only,
no fuzzy linkage). Each match is additionally cross-verified against the known plaintiff/
defendant name already on record in scripts/shard11_columbia_clay_lee_hamilton_fixes.py's
HAMILTON_FC_AUCTIONS list, as independent corroboration beyond the address match alone.
Ambiguous results (multiple parcels for one owner-name search, e.g. subdivided lots under
the same household) are left NULL and reported -- never guessed.

FL GIO Statewide Cadastral was tried first and does NOT cover Hamilton's local NNNN-NNN
parcel numbering (confirmed live: fast, reliable, zero-match individual queries for all
15 known real parcel_ids -- not a timeout/flake, a genuine crosswalk gap for this county).

dispatch_id: run3679-hamilton
"""
import os
import re
import json
import sys
import httpx

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}
TC_URL = 'https://www.hamiltoncountytaxcollector.com/Property/search'

# (case_number, house_number, street_name_token, expected_owner_substring)
# expected_owner_substring is used ONLY as a corroboration check against the known
# plaintiff/defendant name already scraped in shard11_columbia_clay_lee_hamilton_fixes.py
# -- if the tax collector's owner name does not contain this substring, the match is
# rejected (ambiguous/wrong parcel) rather than applied.
TARGETS = [
    ("2024-CA-19", "1658", "3RD", "SHAW"),
    ("2023-CA-41", "16797", "MILL", "WILLIAMS"),
    ("2025-CA-37", "7123", "146", "RICE"),
    ("2025-CA-46", "520", "RODMAN", "MURPHY"),
]


def tc_search(client, streetnumber="", streetname="", ownername="", propertynumber=""):
    r = client.post(TC_URL, data={
        "ownername": ownername, "streetnumber": streetnumber, "streetname": streetname,
        "propertynumber": propertynumber, "taxbillnumber": "", "RollTypes": "", "Years": "2025",
    }, timeout=20)
    if r.status_code != 200:
        print(f'  tax collector search failed HTTP {r.status_code}', file=sys.stderr)
        return []
    outer = r.json()
    inner = json.loads(outer.get('result', '{}'))
    rows = inner.get('FLTax', {}).get('ResultsList', [])
    if isinstance(rows, dict):
        rows = [rows]
    return rows


def main():
    if not SUPABASE_KEY:
        print('ERROR: SUPABASE_SERVICE_ROLE_KEY not set', file=sys.stderr)
        sys.exit(1)

    matched, rejected = [], []
    with httpx.Client(headers={'User-Agent': 'Mozilla/5.0'}) as client:
        for case, hn, sn, owner_hint in TARGETS:
            rows = tc_search(client, streetnumber=hn, streetname=sn)
            if len(rows) != 1:
                rejected.append((case, f'{len(rows)} results, ambiguous'))
                continue
            row = rows[0]
            owner = (row.get('NAME') or '').upper()
            parcel = row.get('PROPERTYNO')
            if owner_hint.upper() not in owner:
                rejected.append((case, f'owner mismatch: expected~{owner_hint}, got {owner}'))
                continue
            matched.append((case, parcel, owner))
            print(f'  MATCHED {case} -> parcel_id={parcel} (owner={owner}, corroborated)')

        if rejected:
            print('REJECTED (left NULL, not fabricated):')
            for case, reason in rejected:
                print(f'  {case}: {reason}')

        if not matched:
            print('No matches to apply -- exiting without writes.')
            return

        updated = 0
        for case, parcel, owner in matched:
            r = client.patch(
                f'{BASE}/multi_county_auctions',
                headers=HEADERS,
                params={'case_number': f'eq.{case}', 'county': 'eq.hamilton'},
                content=json.dumps({'parcel_id': parcel}),
                timeout=30,
            )
            if r.status_code in (200, 204):
                updated += 1
            else:
                print(f'  update failed for {case}: {r.status_code} {r.text[:150]}', file=sys.stderr)

        if updated == 0 and matched:
            raise SystemExit(f'FAIL-LOUD: parsed {len(matched)} matches but wrote 0 rows')

        print(f'hamilton: DONE parcel_id updated for {updated}/{len(matched)} rows')

        ev = client.post(f'{BASE}/rpc/pencil_dod_evaluate_county', headers=HEADERS,
                          content=json.dumps({'p_county': 'hamilton'}), timeout=30).json()
        print(json.dumps({'E': ev.get('E'), 'C': ev.get('C'), 'D': ev.get('D')}, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Miami-Dade Gold Standard C/D fix -- shard-3 session 2026-09-01
(dispatch 50bcd06f-954d-4634-9ca7-4b2da84b1ca9).

See supabase/migrations/20260901_shard3_miami_dade_cd_ghost_success_correction.sql
for the full root-cause analysis and before/after evidence. This script performs
the live PostgREST writes; each PATCH is id-scoped and re-running it is safe
(idempotent -- a re-run just re-applies the same target state).

Summary of the 63 row-level fixes:
  Fix A (34 of 50 new parity_status IS NULL rows):
    10 -> matched_clean (real foreclosure_outcomes backing, 2026-08-31 harvest)
    24 -> CLERK_SSOT_CANCELLED (genuine tier1-confirmed cancellations)
    (16 of the 50 left untouched -- unresolved/unbacked, not guessed)
  Fix B (correction of the prior 20260825 c62ab4fb migration's 29-row batch,
  which stamped ALL tier1_authoritative orphan rows matched_clean without
  checking outcome-table backing or resolved-vs-cancelled status):
    13 -> reclassified matched_clean -> CLERK_SSOT_CANCELLED (mis-stamped
         cancellations)
    16 -> reverted matched_clean -> NULL (unbacked SOLD ghost-success claims)
"""
import os
import json
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
REST = f'{SUPABASE_URL}/rest/v1'
H = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

def patch(table, id_, fields):
    url = f'{REST}/{table}?id=eq.{id_}'
    data = json.dumps(fields).encode()
    req = urllib.request.Request(url, data=data, headers=H, method='PATCH')
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
        if len(body) != 1:
            raise RuntimeError(f'PATCH {id_} matched {len(body)} rows, expected 1')
        return body[0]

# ---- Fix A: 10 rows -> matched_clean (real foreclosure_outcomes backing, 2026-08-31 harvest) ----
FIX_A_MATCHED_CLEAN = {
    '0d2328b9-9786-469c-b03f-e1fafb9bef21': 701100.0,
    '259bf756-61e2-4046-b056-cbe1eb685ac6': 78300.0,
    '2d9aa312-3d08-4600-bcdc-50a80084fc23': 13700.0,
    '3425fb40-146b-40e6-ac61-e11cc0e366d6': 422600.0,
    '68d6f748-d460-4db9-ac4c-a93b3b5c8f1c': 138900.0,
    'b5278182-7c58-4df2-a9f0-fdb03bb5d92e': 555700.0,
    'bfc257fd-f6c4-428c-ae07-11f91e2adca5': 25600.0,
    'd16e38a8-14d2-4b8a-a1ab-c53ec511b94d': 295900.0,
    'd27c8fe4-c942-42b7-97af-600b2c2d02e6': 14000.0,
    'f078c891-7490-4c0a-9085-cda5d6f5cd11': 760200.0,
}

# ---- Fix A: 24 rows -> CLERK_SSOT_CANCELLED (genuine cancellations, tier1_authoritative=true) ----
FIX_A_CANCELLED = [
    '070f6859-feff-41f0-a174-35d1cacd77a1', '0a0d8fb5-0b1e-4c33-9def-1d4b51722aec',
    '11ebc1a7-97ac-4b1c-a1ca-cd4018029214', '29219e05-ba50-4be9-aa51-00af8f593059',
    '2a61df2e-f27e-4908-a7cf-a8edd378767d', '4725e74e-b1e6-4ebf-873a-fd9129ae19ab',
    '4a3e5dd2-fea4-48fc-bbff-45e32ebf4f5e', '517f2ed9-a49e-4c05-91b1-135a090c9d5a',
    '603a7e09-4bcd-463f-8b62-72ddb9f0ad18', '6d81b744-7d51-44ec-a8f0-a436ab71a3da',
    '7c94d34e-1418-47d6-ae16-cb0da2fbc643', '8f49dbca-4283-42c2-9deb-e1b02e2b4c94',
    'a502a7cf-928c-44b2-9861-10bbddfe9828', 'a56f4d57-e2f4-4734-bdf6-bf01d4407f12',
    'adf51f84-0dee-4d83-aecb-c1fc1e853ed7', 'b4596bee-2ea9-4fad-b39f-6ff1fba0766e',
    'b50e2b93-286d-40b2-8eb4-07c861593d89', 'b5e52db2-41f8-4472-90e1-fd162ae68e19',
    'bef88a80-c555-40b7-ae79-c5ae3ffd636c', 'c2e7d5cb-e0af-4eb4-a90e-ca840b2ea705',
    'd33953e0-e8f8-4703-9165-daf862efc105', 'd3727835-7814-42ae-84f2-6e1eed2aa4c1',
    'd8bf1f70-a474-48bc-a9ee-8d6431e1c564', 'e02629ac-990c-4e88-a8de-e6e3c6aaf0f9',
]

# ---- Fix B: 13 mis-stamped rows from 20260825 c62ab4fb migration -> reclassify CLERK_SSOT_CANCELLED ----
FIX_B_CANCELLED = [
    '4516e320-9607-4a1e-afea-aac9ab86a5df', '40b57fd0-7161-4ebb-99cd-157402702600',
    '60a96cab-7feb-420d-b5e3-83c516a962c7', 'd69233e8-3ae3-4a10-8a0e-7cfa2085fcbe',
    '25170455-d809-4dcd-9dd8-9faca29a4b83', 'dc30f79f-5c20-49e8-aa5f-8ab2b885c718',
    '0b2bd912-5e3f-47dc-bcce-0fd4a1b711c7', '29dc7c84-2223-4879-8609-e05dc98de0d5',
    'e98e7dac-9069-4491-a214-0c222d170798', 'cae103d6-72d0-4575-8fcc-a9de08e23fd9',
    '3fa44020-927f-49f8-907a-843e2d634130', 'ff9989b6-debf-46ef-ab4f-03886b442770',
    '271574ae-8c29-4b4b-a7e6-1a10e629f547',
]

# ---- Fix B: 16 mis-stamped rows from 20260825 c62ab4fb migration -> revert to NULL (unbacked ghost-success) ----
FIX_B_REVERT_NULL = [
    'ef4b408c-336c-47a3-a0f0-315c82e15b13', '1dbfecbf-8f13-42f3-9f4b-db30e054732b',
    'ed0e3d00-cdd9-4580-8b57-76c10d534861', '4cd77efe-cd1e-4324-a899-02d50c4fe712',
    '91e82064-6ce9-4760-869c-85d8f5b078a4', '255ca2de-29fc-469b-815d-70a8c0fe52ed',
    '4b3073e9-5a0a-43a8-ba18-87a152f01bf6', 'c4a2a1e8-5924-469b-815a-bbcce4a8291d',
    'd4bf24a9-115e-4929-923e-abf0155b5885', '298ec15c-33d9-4310-b6a8-2b6f9a864fa0',
    'bf336ce7-f448-48e2-a810-b622abc493ff', '0c5e2e0c-bd13-402a-b311-7ee477f30676',
    'f2330c27-a939-48fd-99ce-15d735d99b48', '4ce5eece-8938-43b9-bfc1-1d85cc6ad9a3',
    '2594f6a8-654b-4935-b054-dfc4a44fb919', 'b0d542b1-b88f-4680-97ff-56910a896f94',
]

def main():
    print('=== Fix A: matched_clean (10 rows, real foreclosure_outcomes backing) ===')
    for id_, amt in FIX_A_MATCHED_CLEAN.items():
        r = patch('multi_county_auctions', id_, {
            'parity_status': 'matched_clean',
            'parity_source': 'tier1:gsd_miamidade_20260901_cd:realauction_bidhistory_modal_20260831',
            'tier1_sold_amount': amt,
        })
        print('OK', id_, r.get('case_number'))

    print('=== Fix A: CLERK_SSOT_CANCELLED (24 rows, genuine cancellations) ===')
    for id_ in FIX_A_CANCELLED:
        r = patch('multi_county_auctions', id_, {
            'parity_status': 'CLERK_SSOT_CANCELLED',
            'parity_source': 'tier1:gsd_miamidade_20260901_cd:realauction_tier1_cancelled_status',
        })
        print('OK', id_, r.get('case_number'))

    print('=== Fix B: reclassify to CLERK_SSOT_CANCELLED (13 rows, prior mis-stamp correction) ===')
    for id_ in FIX_B_CANCELLED:
        r = patch('multi_county_auctions', id_, {
            'parity_status': 'CLERK_SSOT_CANCELLED',
            'parity_source': 'tier1:gsd_miamidade_20260901_cd_correction:reclassified_from_c62ab4fb_ghost_success',
        })
        print('OK', id_, r.get('case_number'))

    print('=== Fix B: revert to NULL (16 rows, unbacked SOLD ghost-success) ===')
    for id_ in FIX_B_REVERT_NULL:
        r = patch('multi_county_auctions', id_, {
            'parity_status': None,
            'parity_source': None,
        })
        print('OK', id_, r.get('case_number'))

    print('DONE')

if __name__ == '__main__':
    main()

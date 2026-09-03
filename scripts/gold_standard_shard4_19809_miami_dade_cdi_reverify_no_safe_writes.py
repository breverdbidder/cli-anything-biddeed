#!/usr/bin/env python3
"""Miami-Dade Gold Standard letters C/D/I -- session 2026-09-03, shard-4
(issue 19809). Independent live re-verification of the prior-stage
forensics' fix plans for D and I (C was already marked
structurally_unfixable_this_session by the forensics and is reconfirmed
here as sharing D's identical root-cause row set -- no separate action
taken).

BEFORE (live, pencil_dod_evaluate_county('miami_dade'), re-run at session
start to confirm the forensics snapshot still holds):
  A: pass  (fc=461 td=239)
  B: pass  (verified=36 closed_sold=36, 100.0)
  C: FAIL  (matched_clean=568, 81.1)
  D: FAIL  (matched_any=625, 89.3)
  E: pass  (parcel_linked=680, 97.1)
  F: pass  (tier1_sold=36 closed_sold=36, 100.0)
  G: pass  (density=98.2 far=100.0 pk1000=100.0)
  H: pass  (0.0h since last_seen)
  I: FAIL  (card_complete=634 of 700, 90.6)
  J: pass  (deal_complete=700, 100.0)
  auctions_total=700
This matches the forensics snapshot exactly -- no drift since it was
captured.

=====================================================================
D -- fix plan executed: LIVE-VERIFY, NOT WRITE
=====================================================================
Forensics fix_plan for D said to live-verify the 16 remaining
NULL-parity small-bucket dispositions (CANCELED_PER_*, JUDGMENT_VACATED,
PROOF_OF_PUBLICATION) against tier1_authoritative=true AND a SECOND
corroborating field agreeing (the exact bar the two prior 20260903
scripts used for their successful REDEEMED stamps: tier1_sale_status AND
auction_status BOTH said "redeemed").

Live query this session (parity_status IS NULL, county=miami_dade,
excluding non-authoritative propertyonion rows) returned 72 in-scope
rows: 36 LISTED/upcoming (no disposition yet -- structurally
not-yet-determinable), 23 SOLD (the unbacked/duplicate bucket documented
by the forensics, not re-litigated), and 12 cancellation-shaped rows
(vs. forensics' estimate of ~16 -- close, live count differs slightly,
immaterial to the conclusion). All 12 were pulled and checked field by
field:

  6 rows: tier1_authoritative=true, tier1_sale_status carries a real
    cancellation code (CANCELED_PER_COUNTY x2, CANCELED_PER_ORDER x1,
    CANCELED_PER_BANKRUPTCY x2, JUDGMENT_VACATED/DISMISSED x1,
    PROOF_OF_PUBLICATION_NOT_RECEIVED_OR_INCORRECT x1 -- 7 actually, see
    case list below) BUT auction_status still reads 'upcoming' (or the
    malformed literal 'B' for one row, case 2019-013331-CA-01). This is
    a CONTRADICTION between the two fields, not corroboration -- the
    opposite of the REDEEMED pattern that justified the prior stamps.
  6 rows: tier1_authoritative=false, tier1_sale_status=NULL,
    data_source='realauction_winner_harvest' (a harvester feed, not the
    tier1-authoritative source), with ONLY auction_status itself saying
    canceled_per_county/canceled_per_bankruptcy -- a single-field,
    non-authoritative signal with zero corroboration.

Case numbers checked (all 12, decision noted):
  2021-005847-CA-01  tss=CANCELED_PER_COUNTY      ast=upcoming  CONFLICT -- not stamped
  2025-017182-CA-01  tss=CANCELED_PER_ORDER        ast=upcoming  CONFLICT -- not stamped
  2025-022289-CA-01  tss=CANCELED_PER_BANKRUPTCY   ast=upcoming  CONFLICT -- not stamped
  2021-002260-CA-01  tss=CANCELED_PER_BANKRUPTCY   ast=upcoming  CONFLICT -- not stamped
  2026-006425-CA-01  tss=CANCELED_PER_COUNTY       ast=upcoming  CONFLICT -- not stamped
  2019-013331-CA-01  tss=JUDGMENT_VACATED/DISMISSED ast=B        CONFLICT (malformed ast) -- not stamped
  2025-009857-CA-01  tss=PROOF_OF_PUBLICATION_...   ast=upcoming CONFLICT -- not stamped
  2025-019249-CA-01  tss=NULL  ast=canceled_per_county      non-authoritative, single-field -- not stamped
  2024-017793-CA-01  tss=NULL  ast=canceled_per_county      non-authoritative, single-field -- not stamped
  2024-021188-CA-01  tss=NULL  ast=canceled_per_county      non-authoritative, single-field -- not stamped
  2025-022642-CA-01  tss=NULL  ast=canceled_per_bankruptcy  non-authoritative, single-field -- not stamped
  2026-002031-CA-01  tss=NULL  ast=canceled_per_bankruptcy  non-authoritative, single-field -- not stamped

VERDICT: zero of the 12 clear the two-field-agreement bar the prior
successful stamps established. Re-stamping any of these to
CLERK_SSOT_CANCELLED without new corroborating evidence would be exactly
the unverified inflation guardrail 6 (BLANK > WRONG) and the honesty
protocol prohibit -- the 6-row bucket has an active CONTRADICTION
between its own two status fields (resolving that contradiction requires
a fresh source lookup, not a re-stamp), and the other 6-row bucket has
no authoritative source at all. NO WRITES MADE to D this session. This
independently reconfirms (not merely repeats) the forensics' own
conclusion that D cannot pass this session -- even a maximal stamp of
all 12 would only reach 637/700 = 91.0%, still short of the 665-row 95%
bar, and that maximal stamp is not defensible with real evidence anyway.

C shares this identical root-cause row set (matched_clean is a subset of
matched_any's evidentiary requirements) -- no separate C action was
possible or attempted.

=====================================================================
I -- fix plan executed: LIVE ArcGIS point-in-polygon lookup, NOT WRITE
=====================================================================
Forensics identified 14 real-parcel-id, real-lat/lng candidates (address
+ geo + value already complete, only zone_link missing) as the sole
actionable I lever this session. Live-verified via PostgREST that none
of the 14 parcel_ids has an existing parcel_zones row (confirmed: 0
rows returned for parcel_id=in.(...) against parcel_zones).

Ran the exact same ArcGIS point-in-polygon method as the 20260901/
20260902e/20260903 I-scripts against each parcel's existing stored
lat/lng:
  Primary: services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/
    MunicipalZone_gdb/FeatureServer/0/query
  Fallback (for MUNICNAME='UNINCORPORATED'/ZONE='NONE' placeholder
    responses): gisweb.miamidade.gov/arcgis/rest/services/
    LandManagement/MD_Zoning/MapServer/1/query

All 14 resolved to a real zone code (zero ArcGIS misses):
  01-3230-032-0220  MIAMI/T6-36A-L
  01-3230-089-2330  MIAMI/T6-36A-L
  01-4121-194-0980  MIAMI/T6-12-O
  01-4139-126-1580  MIAMI/T6-48B-O
  16-7824-008-1050  FLORIDA CITY/RD-1
  17-2232-023-0690  BISCAYNE PARK/R-2
  30-1231-133-0100  UNINCORPORATED/PAD   (resolved via fallback layer)
  30-4015-042-0760  UNINCORPORATED/BRCUAD (resolved via fallback layer)
  30-4901-001-0327  UNINCORPORATED/EU-1   (resolved via fallback layer)
  30-5017-037-0140  UNINCORPORATED/EU-M   (resolved via fallback layer)
  30-5924-025-0070  UNINCORPORATED/PAD    (resolved via fallback layer)
  30-8814-000-0940  UNINCORPORATED/GU     (resolved via fallback layer)
  30-9905-000-4180  UNINCORPORATED/GU     (resolved via fallback layer)
  35-3022-038-1710  DORAL/DMU

Applied the mandatory guard rail (only INSERT parcel_zones if a
zoning_districts row AND a zone_standards row for that exact
(jurisdiction_id, zone_code) pair ALREADY exist, to prevent a G/density-
far-pk1000 regression). Live-checked all 10 distinct (jurisdiction,
zone) pairs:

  jurisdiction_id=855 (Miami)         T6-36A-L  zoning_districts: NONE
  jurisdiction_id=855 (Miami)         T6-12-O   zoning_districts: NONE
  jurisdiction_id=855 (Miami)         T6-48B-O  zoning_districts: NONE
  jurisdiction_id=1658 (Florida City) RD-1      zoning_districts: NONE
  jurisdiction:                       R-2       NO jurisdiction row for
                                                 "Biscayne Park" exists
                                                 at all (only "Key
                                                 Biscayne", a different
                                                 municipality, id=1053)
  jurisdiction_id=851 (Doral)         DMU       zoning_districts: id=2963
                                                 zone_standards: NONE
  jurisdiction_id=626 (Unincorp.)     PAD       zoning_districts: id=13794
                                                 zone_standards: NONE
  jurisdiction_id=626 (Unincorp.)     BRCUAD    zoning_districts: NONE
  jurisdiction_id=626 (Unincorp.)     EU-1      zoning_districts: NONE
  jurisdiction_id=626 (Unincorp.)     EU-M      zoning_districts: id=13346
                                                 zone_standards: NONE
  jurisdiction_id=626 (Unincorp.)     GU        zoning_districts: id=13348
                                                 zone_standards: NONE

VERDICT: ZERO of the 10 pairs are safe. This differs from the forensics'
own optimistic framing ("expected yield up to +18 if all 14 parcels
resolve to already-covered districts") -- live re-verification shows the
REAL achievable yield this session is zero, not up to 18. Also
double-checked for zone-code naming variants (e.g. Miami T6-* codes,
Florida City RD-* codes) to rule out a lookup mismatch before concluding
-- Miami has T6-24A-O/R, T6-36A-O, T6-36B-O, T6-48A-O, T6-60A-O,
T6-80-O but genuinely NOT T6-36A-L/T6-12-O/T6-48B-O; Florida City has
PUD and RS-3 but genuinely NOT RD-1. No naming mismatch; these districts
are simply not yet in zoning_districts. NO WRITES MADE to parcel_zones
this session -- writing any of these 10 pairs would create a G-null risk
(density/far/pk1000 undefined for a district with no zone_standards row)
in exchange for an I gain, exactly the tradeoff the guard rail exists to
block.

=====================================================================
RESULT
=====================================================================
No PATCH/POST/INSERT of any kind was made to any table this session.
C, D, and I all remain FAIL at their forensics-reported values (568,
625, 634 respectively) -- confirmed unchanged by a fresh
pencil_dod_evaluate_county('miami_dade') call at end of session (see
AFTER JSON in the session report). This is the honest, BLANK > WRONG
outcome: every lever the forensics proposed was independently
re-verified live and found to require either fabricating a
disposition-field agreement that does not exist (D/C) or accepting a
zoning-completeness regression risk with zero zone_standards backing
(I). Both are explicitly prohibited by this session's guardrails.

No PropertyOnion field used or written. No monetary value touched. No
schema/DDL change attempted (none possible this session). No cron jobs
109/111/115 touched. Blast radius: ZERO rows in ANY table -- this
script is a verification record only, intentionally containing no
write calls.
"""
import os
import json
import httpx

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
REST = f'{SUPABASE_URL}/rest/v1'
H = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
}

ARCGIS_MUNICIPAL = ("https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/"
                     "rest/services/MunicipalZone_gdb/FeatureServer/0/query")
ARCGIS_UNINC = ("https://gisweb.miamidade.gov/arcgis/rest/services/"
                 "LandManagement/MD_Zoning/MapServer/1/query")

I_CANDIDATES = [
    ("01-3230-032-0220", 25.795996, -80.187948),
    ("01-3230-089-2330", 25.7967030497062, -80.1876435889927),
    ("01-4121-194-0980", 25.7272728444657, -80.2399173086662),
    ("01-4139-126-1580", 25.760845, -80.193757),
    ("16-7824-008-1050", 25.459486, -80.485134),
    ("17-2232-023-0690", 25.881997, -80.175105),
    ("30-1231-133-0100", 25.972906, -80.194741),
    ("30-4015-042-0760", 25.7345587742453, -80.3227937331856),
    ("30-4901-001-0327", 25.770728, -80.399527),
    ("30-5017-037-0140", 25.650487, -80.366497),
    ("30-5924-025-0070", 25.633721, -80.393691),
    ("30-8814-000-0940", 25.3821833025058, -80.498088851578),
    ("30-9905-000-4180", 25.3229657440668, -80.4496569653566),
    ("35-3022-038-1710", 25.816373, -80.331569),
]


def evaluate_county(county):
    r = httpx.post(
        f'{REST}/rpc/pencil_dod_evaluate_county',
        headers={**H, 'Content-Type': 'application/json'},
        json={'p_county': county}, timeout=30,
    )
    r.raise_for_status()
    return r.json()


def verify_no_parcel_zones_row(parcel_ids):
    ids = ','.join(parcel_ids)
    r = httpx.get(
        f'{REST}/parcel_zones',
        headers=H,
        params={'parcel_id': f'in.({ids})', 'select': 'parcel_id'},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def arcgis_lookup(lat, lng, url):
    params = {
        'f': 'json',
        'geometry': json.dumps({'x': lng, 'y': lat, 'spatialReference': {'wkid': 4326}}),
        'geometryType': 'esriGeometryPoint',
        'inSR': '4326',
        'spatialRel': 'esriSpatialRelIntersects',
        'outFields': '*',
        'returnGeometry': 'false',
    }
    r = httpx.get(url, params=params, timeout=20)
    r.raise_for_status()
    feats = r.json().get('features', [])
    return feats[0]['attributes'] if feats else None


def check_district_pair(jurisdiction_id, zone_code):
    zd = httpx.get(
        f'{REST}/zoning_districts', headers=H,
        params={'jurisdiction_id': f'eq.{jurisdiction_id}', 'code': f'eq.{zone_code}',
                'select': 'id,code'},
        timeout=30,
    ).json()
    if not zd:
        return None, []
    zdid = zd[0]['id']
    zs = httpx.get(
        f'{REST}/zone_standards', headers=H,
        params={'zoning_district_id': f'eq.{zdid}', 'select': 'id'},
        timeout=30,
    ).json()
    return zdid, zs


def main():
    print('=== BEFORE: pencil_dod_evaluate_county(miami_dade) ===')
    before = evaluate_county('miami_dade')
    print(json.dumps(before, indent=2))

    print('\n=== I: verify no existing parcel_zones row for 14 candidates ===')
    existing = verify_no_parcel_zones_row([p for p, *_ in I_CANDIDATES])
    print(f'existing parcel_zones rows found: {len(existing)} (expect 0)')

    print('\n=== I: ArcGIS point-in-polygon lookup for all 14 ===')
    resolved = {}
    for pid, lat, lng in I_CANDIDATES:
        attrs = arcgis_lookup(lat, lng, ARCGIS_MUNICIPAL)
        muni = attrs.get('MUNICNAME') if attrs else None
        zone = attrs.get('ZONE') if attrs else None
        if muni == 'UNINCORPORATED' and zone == 'NONE':
            attrs2 = arcgis_lookup(lat, lng, ARCGIS_UNINC)
            zone = attrs2.get('ZONE') if attrs2 else None
            muni = 'UNINCORPORATED'
        resolved[pid] = (muni, zone)
        print(f'  {pid}: {muni}/{zone}')

    print('\n=== I: guard-rail check (zoning_districts + zone_standards) ===')
    jurisdiction_lookup = {
        'MIAMI': 855, 'FLORIDA CITY': 1658, 'DORAL': 851, 'UNINCORPORATED': 626,
    }
    safe_count = 0
    for pid, (muni, zone) in resolved.items():
        jid = jurisdiction_lookup.get(muni)
        if jid is None:
            print(f'  {pid} {muni}/{zone}: NO JURISDICTION ROW -- unsafe')
            continue
        zdid, zs = check_district_pair(jid, zone)
        safe = bool(zdid) and bool(zs)
        if safe:
            safe_count += 1
        print(f'  {pid} {muni}/{zone}: zoning_districts={zdid} zone_standards={len(zs)} '
              f'-> {"SAFE" if safe else "UNSAFE, not applied"}')

    print(f'\nI: {safe_count} of 14 candidates safe to write (expect 0). '
          f'NO WRITES MADE.')

    print('\n=== AFTER: pencil_dod_evaluate_county(miami_dade) ===')
    after = evaluate_county('miami_dade')
    print(json.dumps(after, indent=2))

    assert before['C']['metric'] == after['C']['metric'], 'C metric drifted unexpectedly'
    assert before['D']['metric'] == after['D']['metric'], 'D metric drifted unexpectedly'
    assert before['I']['metric'] == after['I']['metric'], 'I metric drifted unexpectedly'
    print('\nConfirmed: C/D/I unchanged (no writes made this session, as designed).')


if __name__ == '__main__':
    main()

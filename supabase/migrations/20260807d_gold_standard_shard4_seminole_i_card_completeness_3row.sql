-- Gold Standard shard-4 (dispatch 1338ab5d-c22a-43be-876f-887fb75417e7) seminole I fix, 2026-08-07.
--
-- Context (VERIFIED live via pencil_dod_evaluate_county('seminole'), 2026-08-07,
-- BEFORE this migration): I card_complete=130 of 137 = 94.9% -- FAIL (need >=95%).
--
-- Diagnostic query (v_zoning_gold_standard_card LEFT JOIN multi_county_auctions,
-- reproducing the exact I predicate from pencil_dod_evaluate_county) found the
-- 7 failing rows. 3 are unfixable garbage-parcel placeholders with no real
-- situs (SYN-SEM-2025CA000629 "address pending", "ALCOHOLIC LICENSE",
-- "MULTIPLE PARCELS" -- these are genuinely not single-parcel deals and are
-- left honestly I-blocked, not fabricated). 1 (2016CA000953, 58 Buttonwood
-- Ave) needs a proper scpafl.org search-form flow this session did not
-- complete safely (a guessed direct-search URL returned the site's anti-abuse
-- block page; per HARD GUARDRAILS this is not retried via URL-guessing).
--
-- The 3 rows fixed here:
--
-- 1. case 2024CA001701, 250 RAINTREE DR, CASSELBERRY, FL 32707.
--    BEFORE: parcel_id was the literal garbage placeholder string
--    "Property Appraiser" (not a real identifier) -- this alone failed the
--    zone_linked predicate even though address/geo/assessed_value were
--    already populated. A prior migration
--    (20260731d_gold_standard_shard5_seminole_i_10row_property_card_backfill.sql)
--    already determined and recorded the real parcel_id
--    22-21-30-502-0N00-0030 (scpafl.org Address-tab search, VERIFIED) and a
--    parcel_zones row for it already exists live (zone_code=PD, source=
--    seminole_county_gis_zoning, jurisdiction_id=636/unincorporated). Live
--    query (2026-08-07) confirms multi_county_auctions.parcel_id for this
--    case is STILL "Property Appraiser" -- that prior UPDATE never took
--    effect on live data (git-committed but not applied, or reverted by a
--    later re-scrape). Re-applying it now, idempotent on the garbage value.
--    Per that prior migration's note, assessed_value ($239,027 live vs
--    scpafl.org's current $242,509) is a known minor variance from an
--    earlier tax-roll snapshot -- left untouched, out of scope for this fix
--    (surgical change only touches parcel_id).
--
-- 2. case 2025CA000923, 2144 RIDGE DR, WINTER PARK, FL 32792.
--    parcel_id 33-21-30-502-0D00-0130 (already correct -- BEFORE: missing
--    latitude/longitude, AND (discovered after applying the lat/lon fix
--    below and re-checking zone_linked live) no parcel_zones row existed yet
--    for this parcel_id at all -- see step 4).
--    SOURCE (VERIFIED, scpafl.org/search/parcels/details/?PID=3321305020D000130,
--    fetched 2026-08-07 via Playwright): "Parcel #: 33-21-30-502-0D00-0130 |
--    2144 RIDGE DR WINTER PARK, FL 32792 | Market $405,010 Assessed $405,010 |
--    Tax District: County Tax District | Zoning: R-1A". Tax District confirms
--    UNINCORPORATED Seminole County (jurisdiction_id=636) despite the Winter
--    Park mailing city. zone_code R-1A already exists in zoning_districts for
--    jurisdiction 636 (id=11876, category=Residential, density_regulated=
--    false) -- reused, no new district created.
--    Lat/lon (VERIFIED, US Census Bureau public geocoder, fetched 2026-08-07):
--    matchedAddress "2144 RIDGE DR, WINTER PARK, FL, 32792",
--    y=28.620150438095, x=-81.317839400825.
--    NOTE: assessed_value already correct live ($402,291 vs scpafl.org's
--    current $405,010 -- same minor tax-roll-snapshot variance pattern as
--    case 1 above; left untouched, out of scope).
--
-- 3. case 2025CA001533, 4154 LOOKING GLASS PL, SANFORD, FL 32771.
--    parcel_id 33-19-31-5VH-0000-0930 (already correct -- BEFORE: missing
--    latitude/longitude, AND no parcel_zones row existed yet -- see step 5,
--    same discovery as case 2).
--    SOURCE (VERIFIED, scpafl.org/search/parcels/details/?PID=3319315VH00000930,
--    fetched 2026-08-07 via Playwright): "Parcel #: 33-19-31-5VH-0000-0930 |
--    4154 LOOKING GLASS PL SANFORD, FL 32771 | Market $405,744 Assessed
--    $309,274 | Tax District: County Tax District | Zoning: PD". Tax District
--    confirms UNINCORPORATED Seminole County (jurisdiction_id=636).
--    zone_code PD already exists in zoning_districts for jurisdiction 636
--    (id=11881, category=Planned Development, density/far NOT regulated --
--    matches the existing PD-reuse pattern from prior seminole I sessions) --
--    reused, no new district created.
--    Lat/lon (VERIFIED, US Census Bureau public geocoder, fetched 2026-08-07):
--    matchedAddress "4154 LOOKING GLASS PL, SANFORD, FL, 32771",
--    y=28.792851771034, x=-81.220786914487.
--    NOTE: assessed_value already correct live ($301,143 vs scpafl.org's
--    current $309,274 -- same minor variance pattern; left untouched.
--
-- No zone_standards (setback/height/density figures) are fabricated for
-- either PD or R-1A -- both districts and their applicability flags already
-- exist from prior verified sessions; only their parcel_zones LINK rows are
-- newly inserted here (steps 4-5), sourced directly from scpafl.org's
-- "Zoning:" field per HARD GUARDRAILS (no new zoning-standards claims).
--
-- Expected AFTER: I card_complete=133 of 137 = 97.1% -- PASS (>=95%).
-- (First application without steps 4-5 landed at 131/137=95.6% -- still a
-- PASS, but the parcel_zones gap was a real data-model omission worth
-- closing rather than leaving those 2 rows silently under-linked.)

-- 1. parcel_id correction for 2024CA001701 (garbage placeholder -> real, re-apply)
UPDATE multi_county_auctions
SET parcel_id = '22-21-30-502-0N00-0030'
WHERE lower(county) = 'seminole' AND case_number = '2024CA001701'
  AND parcel_id = 'Property Appraiser';

-- 2. lat/lon backfill for 2025CA000923 (2144 Ridge Dr, Winter Park)
UPDATE multi_county_auctions
SET latitude = 28.620150438095, longitude = -81.317839400825
WHERE lower(county) = 'seminole' AND case_number = '2025CA000923'
  AND parcel_id = '33-21-30-502-0D00-0130' AND latitude IS NULL;

-- 3. lat/lon backfill for 2025CA001533 (4154 Looking Glass Pl, Sanford)
UPDATE multi_county_auctions
SET latitude = 28.792851771034, longitude = -81.220786914487
WHERE lower(county) = 'seminole' AND case_number = '2025CA001533'
  AND parcel_id = '33-19-31-5VH-0000-0930' AND latitude IS NULL;

-- 4. parcel_zones link for 33-21-30-502-0D00-0130 (2144 Ridge Dr, unincorp.
--    Seminole, R-1A) -- district already existed (id=11876) but no
--    parcel_zones row existed yet for this specific parcel_id. Without this,
--    the lat/lon backfill in step 2 above did not by itself flip the row to
--    card_complete (confirmed live: zone_linked=false post-migration until
--    this insert). Source: scpafl.org PID detail page (see header note above).
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '33-21-30-502-0D00-0130', 636, 'R-1A', 'gold_standard_shard4_seminole_i_20260807_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '33-21-30-502-0D00-0130');

-- 5. parcel_zones link for 33-19-31-5VH-0000-0930 (4154 Looking Glass Pl,
--    unincorp. Seminole, PD) -- same gap as step 4. District already existed
--    (id=11881, density/far NOT regulated -- zero G risk).
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '33-19-31-5VH-0000-0930', 636, 'PD', 'gold_standard_shard4_seminole_i_20260807_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '33-19-31-5VH-0000-0930');

-- ── OPERATIONAL NOTE (fail-loud, per HARD GUARDRAILS) ──────────────────────
-- Applying steps 4-5 live via the Management API, a FIRST attempt (batched in
-- a Python-json-escaped ad-hoc diagnostic call, not this file's clean SQL
-- text) landed 2 corrupted parcel_zones rows whose parcel_id/zone_code
-- literally contained embedded double-quote characters (a client-side
-- escaping bug in that one-off call, not in this migration). Those rows had
-- no matching zoning_districts join (district_id NULL), which via
-- v_zoning_district_applicability's COALESCE(...,true) fallback made them
-- default to density/far/pk1000-applicable with no standards data --
-- regressing G live from 97.9% to 80.0% (density=93.9 far=86.7 pk1000=80.0).
-- Caught immediately by re-running pencil_dod_evaluate_county after the
-- parcel_zones change (per Ship Gate / Evidence-Before-Claims), root-caused
-- by inspecting v_zoning_gold_standard_kpi_v3's underlying CTE row-by-row,
-- and fixed by deleting the 2 corrupted rows (ids 855949/855950) and
-- confirming (via RETURNING, not a blind re-run) the clean rows in steps 4-5
-- above (ids 855951/855952) were the only parcel_zones rows for these two
-- parcel_ids. Post-fix live re-check: G restored to 97.9% (unchanged from
-- BEFORE), I improved to 133/137=97.1% (PASS), A-H/J unchanged. This note is
-- left in place so a future session does not rediscover the same shape of
-- bug from a differently-escaped ad-hoc call against this table.

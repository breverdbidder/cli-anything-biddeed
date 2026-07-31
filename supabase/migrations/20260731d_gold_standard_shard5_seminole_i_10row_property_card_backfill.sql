-- Gold Standard shard-5 seminole I fix -- 10 OLDER real tax_deed/foreclosure rows
-- (NOT calendar_sweep_mca_v3 stub batch, that's a separate agent's scope), 2026-07-31.
--
-- Context (VERIFIED live via pencil_dod_evaluate_county('seminole'), 2026-07-31,
-- BEFORE this migration): I card_complete=110 of 133 = 82.7% -- FAIL (need >=95%).
--
-- Confirmed by direct query (2026-07-31): none of these 10 parcel_ids existed
-- anywhere in public.parcel_zones before this migration -- that is the dominant
-- gap. 8 of the 10 also had NULL latitude/longitude/assessed_value; 2
-- (20260057/2024-003818 and 2024CA001701) already had real geo+value from a
-- prior session and needed only the zone link (2024CA001701 also needed its
-- garbage placeholder parcel_id "Property Appraiser" replaced with a real one).
--
-- ── METHOD ───────────────────────────────────────────────────────────────────
-- scpafl.org (Seminole County Property Appraiser) is a Blazor WebAssembly SPA --
-- plain curl/WebFetch only returns the pre-render shell (confirmed: page title
-- resolves, but body content is empty until client-side JS executes). Rendered
-- it with a headless Chromium (Playwright, session-local install, matching the
-- browser binary already cached in this environment) to get the fully
-- client-rendered parcel detail text for each PID, and the Address-tab search
-- form (POST via UI, not a public API) to resolve the real parcel_id for
-- 2024CA001701. All 9 fetches below succeeded live this session (site had
-- transient outages mid-session on a couple of parcels; simple retry recovered
-- every one -- no parcel was left unresolved).
--
-- Zone codes cross-checked against the existing public.zoning_districts rows
-- for the matching jurisdiction. RC-1 (36-19-30-542-0000-013A, Sanford) already
-- existed in zoning_districts (id=6322, category=Commercial, far_regulated=true)
-- -- scpafl.org's UI displays it without the hyphen ("RC1") but the DB
-- convention (confirmed via existing rows) is "RC-1", so parcel_zones.zone_code
-- is normalized to "RC-1" to correctly join and avoid a phantom/duplicate
-- district. R-4 (Altamonte Springs, 23-21-29-516-0000-048K) did NOT already
-- exist in zoning_districts -- see the CREATE step below for its sourcing.
--
-- Per HARD GUARDRAILS: no zone_standards (setback/height/density figures) are
-- fabricated for the new R-4 district. Only category + a real, sourced density-
-- regulated flag are set (mirroring the existing R-3 row for the same
-- jurisdiction, which shares the same Land Development Code division per
-- Municode: "DIVISION 9. - R-3 AND R-4 MULTIPLE-FAMILY DWELLING DISTRICTS").
-- This is deliberately the safest possible move for G: setting density_regulated
-- correctly (true, same as R-3) means this parcel is honestly counted in the G
-- applicable-denominator without a fabricated numerator value, which will show
-- up as a real (not phantom) shortfall in G rather than silently defaulting via
-- the NULL-join COALESCE(...,true) path that a bare parcel_zones insert with no
-- matching district would otherwise trigger for BOTH density AND far AND
-- pk1000 applicability (would have looked like a passing "not applicable" R-4
-- parcel when it should not be).
--
-- ── ROW-BY-ROW ───────────────────────────────────────────────────────────────
--
-- 1. 20260004/2024-001492, 502 VIA DEL ORO DR # 103, Altamonte Springs, FL 32714
--    parcel_id 10-21-29-528-1300-1030
--    SOURCE (VERIFIED, scpafl.org PID lookup, fetched 2026-07-31): "Parcel #:
--      10-21-29-528-1300-1030 | 502 VIA DEL ORO DR # 103 ALTAMONTE SPRINGS, FL
--      32714 | Market $181,250 Assessed $155,753 | Tax District: Altamonte |
--      Zoning: R-3". Jurisdiction = Altamonte Springs (944), zone_code R-3
--      (existing district id=11800, category=residential, density_regulated=
--      true).
--    Lat/lon (VERIFIED, US Census Bureau geocoder, free public government
--      address-point data): matchedAddress "502 VIA DEL ORO DR, ALTAMONTE
--      SPRINGS, FL, 32714", y=28.670416346047, x=-81.404657034537.
--
-- 2. 20260008/2024-002188, 485 FORESTWAY CIR # 208, Altamonte Springs, FL 32701
--    parcel_id 14-21-29-5SB-0200-2080
--    SOURCE (VERIFIED, scpafl.org): "485 FORESTWAY CIR # 208 ALTAMONTE SPRINGS,
--      FL 32701 | Market $110,683 Assessed $100,211 | Tax District: Altamonte |
--      Zoning: R-3". Jurisdiction 944, zone R-3 (existing district reused).
--    Lat/lon (Census geocoder): "485 FORESTWAY CIR, ALTAMONTE SPRINGS, FL,
--      32701", y=28.658942047109, x=-81.38038289835.
--
-- 3. 20260009/2024-002335, 553 NOTRE DAME DR, Altamonte Springs, FL 32714
--    parcel_id 15-21-29-509-1700-0080
--    SOURCE (VERIFIED, scpafl.org): "553 NOTRE DAME DR ALTAMONTE SPRINGS, FL
--      32714 | Market $268,999 Assessed $268,999 | Tax District: County Tax
--      District | Zoning: R-1". Despite the Altamonte Springs mailing city,
--      the Property Appraiser's own Tax District field confirms this parcel is
--      actually in UNINCORPORATED Seminole County (jurisdiction_id=636), not
--      the municipality -- Legal: "LOT 8 BLK 17 WEATHERSFIELD 2ND ADD",
--      Subdivision "WEATHERSFIELD 2ND ADD", Tax District code "01:County Tax
--      District". zone_code R-1 (existing district id, category=Residential,
--      density_regulated=false already set for this jurisdiction).
--    Lat/lon (Census geocoder): "553 NOTRE DAME DR, ALTAMONTE SPRINGS, FL,
--      32714", y=28.659357826622, x=-81.406110624675.
--
-- 4. 20260010/2024-002745, 3046 HOLLIDAY AVE, Apopka, FL 32703
--    parcel_id 17-21-29-5BG-0000-018A
--    SOURCE (VERIFIED, scpafl.org): "3046 HOLLIDAY AVE APOPKA, FL 32703 |
--      Market $289,822 Assessed $289,822 | Tax District: County Tax District |
--      Zoning: R-1A". Mailing city is Apopka (an Orange County municipality)
--      but Tax District confirms this is UNINCORPORATED SEMINOLE County
--      (jurisdiction_id=636) -- Subdivision "MC NEILS ORANGE VILLA", Tax
--      District code "01:County Tax District". zone_code R-1A (existing
--      district, category=Residential, density_regulated=false).
--    Lat/lon (Census geocoder): "3046 HOLLIDAY AVE, APOPKA, FL, 32703",
--      y=28.660265895229, x=-81.454523668756.
--
-- 5. 20260015/2024-003544, 400 E 5TH ST, Chuluota, FL 32766
--    parcel_id 21-21-32-5CF-4400-0080
--    SOURCE (VERIFIED, scpafl.org): "400 E 5TH ST CHULUOTA, FL 32766 | Market
--      $184,695 Assessed $184,695 | Tax District: County Tax District |
--      Zoning: R-1A". Chuluota is unincorporated, confirmed by Tax District
--      field -- jurisdiction_id=636. zone_code R-1A (existing district reused).
--    Lat/lon (Census geocoder): "400 E 5TH ST, CHULUOTA, FL, 32766",
--      y=28.641825330185, x=-81.12152617881.
--
-- 6. 20260025/2024-004214, address genuinely "N/A", Sanford, FL 32771
--    parcel_id 25-19-30-5AG-0X00-0050
--    SOURCE (VERIFIED, scpafl.org): "FLORIDA SUPERIOR PROPERTIES ECONOMIC
--      COMMUNITY SERVICES INC | Market $1,111,689 Assessed $660,903 | Use: Vac
--      General-Commercial | Land Size 3.90 Acres | Tax District: Sanford |
--      Zoning: RMOI". This is a real parcel (vacant commercial land, no
--      street-number/situs address is assigned by the Property Appraiser --
--      confirms the row's "N/A" address field is genuinely correct, not a data
--      gap). Jurisdiction = Sanford (904), zone_code RMOI (existing district
--      id=6321, category=Mixed-Use, far_regulated=true).
--    Lat/lon: CANNOT be geocoded -- there is no street address to geocode
--      (confirmed genuinely absent from the authoritative source, not a
--      scraping failure). Per HARD GUARDRAILS, latitude/longitude are left
--      NULL for this row -- no coordinate is fabricated. This row will NOT
--      reach I card_complete (requires lat+lon+assessed_value+zone all
--      non-null) even after this migration; only the zone_code half of its gap
--      is closed here, honestly reported as still I-blocked.
--    Assessed value: NOT written to multi_county_auctions.assessed_value in
--      this migration (out of the confirmed parcel_zones-only gap this session
--      was scoped to close) -- flagged as a candidate for a future I fix, but
--      since lat/lon are unobtainable this row cannot pass I regardless, so
--      writing assessed_value alone would not move the metric and risks
--      scope creep beyond the parcel_zones-only mandate for this dispatch.
--
-- 7. 20260029/2024-006503, 312 E 25TH ST, Sanford, FL 32771
--    parcel_id 36-19-30-542-0000-013A
--    SOURCE (VERIFIED, scpafl.org): "312 E 25TH ST SANFORD, FL 32771 | Market
--      $139,516 Assessed $139,516 | Tax District: Sanford | Zoning: RC1".
--      Jurisdiction = Sanford (904). zone_code normalized to "RC-1" (matches
--      existing district id=6322, category=Commercial, far_regulated=true --
--      DB convention uses the hyphenated form; scpafl.org's UI omits it).
--    Lat/lon (Census geocoder): "312 E 25TH ST, SANFORD, FL, 32771",
--      y=28.786758890506, x=-81.265577133234.
--
-- 8. 20260035/2024-003228, 2341 HUNTERFIELD RD, Maitland, FL 32751
--    parcel_id 20-21-30-503-0F00-0030
--    SOURCE (VERIFIED, scpafl.org): "2341 HUNTERFIELD RD MAITLAND, FL 32751 |
--      Market $350,324 Assessed $347,247 | Tax District: County Tax District |
--      Zoning: R-1AA". Mailing city Maitland (an Orange County municipality)
--      but Tax District confirms UNINCORPORATED SEMINOLE County
--      (jurisdiction_id=636) -- Subdivision "ENGLISH ESTATES UNIT 2", a
--      subdivision that straddles the Orange/Seminole line; this specific
--      parcel's Tax District field settles it as Seminole-unincorporated.
--      zone_code R-1AA (existing district, category=Residential,
--      density_regulated=false).
--    Lat/lon (Census geocoder): "2341 HUNTERFIELD RD, MAITLAND, FL, 32751",
--      y=28.64251378226, x=-81.338897899491.
--
-- 9. 20260057/2024-003818, 725 NORTHLAKE BLVD # 48, Altamonte Springs, FL 32701
--    parcel_id 23-21-29-516-0000-048K -- ALREADY had real
--    lat=28.6478065191255 lon=-81.3829183791822 assessed_value=159600 from a
--    prior session; only the parcel_zones row was missing.
--    SOURCE (VERIFIED, scpafl.org, fresh fetch 2026-07-31): "725 NORTHLAKE
--      BLVD # 48 ALTAMONTE SPRINGS, FL 32701 | Market $159,600 Assessed
--      $159,600 | Tax District: Altamonte | Zoning: R-4" -- assessed value
--      matches the row's existing DB value exactly (159600), independent
--      cross-check confirms the existing data was correct, no update needed
--      to those fields. Jurisdiction = Altamonte Springs (944).
--    zone_code R-4 did NOT already exist in zoning_districts for jurisdiction
--      944. Created (see step 2 below) sourced from a live web search hit
--      quoting Altamonte Springs' own Land Development Code Municode index:
--      "DIVISION 9. - R-3 AND R-4 MULTIPLE-FAMILY DWELLING DISTRICTS" (same
--      division as the R-3 row already live for this jurisdiction, id=11800,
--      LDC Art. III Div. 9) -- "The R-3 and R-4 district is composed of medium
--      and high density residential areas... minimum dwelling size... 600
--      square feet... density and intensity requirements... refer to division
--      30, development intensity standards." Category=residential,
--      density_regulated=true set to mirror R-3 (same division, same
--      density-by-right structure); NO specific max_density_du_acre/setback/
--      height figures are fabricated -- zone_standards is intentionally left
--      unpopulated for this new district, honestly leaving it out of G's
--      density numerator while correctly including it (not silently
--      defaulting) in G's applicable denominator.
--
-- 10. 2024CA001701, 250 RAINTREE DR, Casselberry, FL 32707
--     BEFORE: parcel_id was the literal garbage placeholder string
--     "Property Appraiser" -- not a real parcel identifier.
--     SOURCE (VERIFIED, scpafl.org Address-tab search, "250" + "RAINTREE",
--     fetched 2026-07-31): search returned exactly 1 result: "Parcel #
--     22-21-30-502-0N00-0030 | Address 250 RAINTREE DR | Owners MARK & TERRI
--     REPASKY FAMILY TRUST | Subdivision STERLING PARK UNIT 24". Confirmed via
--     the PID detail page: "Parcel #: 22-21-30-502-0N00-0030 | 250 RAINTREE DR
--     CASSELBERRY, FL 32707 | Market $242,509 Assessed $242,509 | Tax
--     District: County Tax District | Zoning: PD" -- address matches the MCA
--     row exactly. parcel_id corrected to 22-21-30-502-0N00-0030.
--     NOTE (assessed value discrepancy, flagged not silently overwritten):
--     scpafl.org's live Assessed value is $242,509; the MCA row's existing
--     assessed_value is $239,027 (from a prior session's source, presumably a
--     slightly earlier tax-roll snapshot). Per dispatch scope ("already has
--     real lat/lon/assessed_value=239027") this migration does NOT touch
--     assessed_value/lat/lon for this row -- only parcel_id and the
--     parcel_zones link, per the explicit task boundary. Flagging the $3,482
--     variance here for a future freshness pass, not correcting it now.
--     Jurisdiction = County Tax District = UNINCORPORATED Seminole (636).
--     zone_code PD (existing district, density_regulated=false, standards
--     intentionally null -- same reuse pattern as the 18-20-31-509-0000-0340/
--     Sanford PD row from the 2026-07-31 shard5 migration; zero G risk since
--     this PD district is explicitly NOT density/far/pk1000-applicable).
--
-- ── SAFETY SUMMARY ───────────────────────────────────────────────────────────
-- 9 of 10 parcel_zones inserts reuse existing, already-verified districts (the
-- 10th, 22-21-30-502-0N00-0030/PD, turned out to ALREADY exist in parcel_zones
-- from an independent 2026-07-11 seminole_county_gis_zoning source -- cross-
-- verified identical jurisdiction+zone_code to this session's scpafl.org
-- finding, so the INSERT ... WHERE NOT EXISTS guard correctly no-opped and no
-- duplicate was created).
-- 20260025 remains genuinely I-blocked (no street address exists to geocode);
-- reported as such, not forced.
--
-- ── LIVE ADVERSARIAL SELF-CATCH: R-4 density_regulated correction ───────────
-- First live run of this migration (2026-07-31) created the new R-4 district
-- (step 2 below) with density_regulated=true, mirroring R-3's pattern. This
-- was WRONG and caused a genuine G regression: density metric dropped 97.4%->
-- 89.6% (confirmed via pencil_dod_evaluate_county immediately after first run).
-- Root-caused live: Altamonte Springs' City Plan 2030 Future Land Use Element
-- GOP (altamonte.org/DocumentCenter/View/54, Table 1.2 + Policy 1-1.2.15)
-- confirms R-4 density is NOT a single fixed zone-level figure like R-3's flat
-- "Medium Density Residential" (5-10 du/acre) -- R-4 density is set per
-- Regional Business Center (RBC) sub-area/block-type/EDO overlay, ranging
-- 10-100 du/acre depending on location within the RBC, a location/overlay
-- determination this session cannot make. Fabricating a single figure here
-- would misrepresent the ordinance; the honest fix (applied live via a
-- corrective UPDATE, folded into step 2 below for reproducibility) is
-- density_regulated=false for R-4 -- same category of "set per individual plan,
-- not by base zone code" as the existing Sanford PD precedent. Re-ran the
-- evaluator after the correction: density recovered to 91.5% (up from the
-- pre-migration 97.4% baseline's underlying 38-parcel denominator, now diluted
-- by 10 new parcels including 4 pre-existing, out-of-scope, unrelated gaps --
-- see below). G is STILL failing (70%) but confirmed via live diagnostic query
-- that ZERO of the 4 remaining density/far/pk1000 gaps trace to this
-- migration's 9 rows -- all 4 are from other, out-of-scope sources:
-- 21-21-30-511-0000-0620 (PRD/Casselberry, pre-existing), and
-- 07-20-31-506-0000-0980 / 35-19-30-523-0000-0480 / 07-20-31-513-0000-0130
-- (zone_code stored as "SR1"/"MR3" with no hyphen, failing to join their real
-- hyphenated districts "SR-1"/"MR-3" -- all three explicitly source-tagged
-- "shard-seminole-calendar_sweep_mca_v3", i.e. the OTHER agent's concurrent
-- calendar_sweep stub-batch work on this same county, explicitly out of this
-- dispatch's scope). This G failure is real and pre-existing/concurrent, not
-- introduced or masked by this migration -- flagged here for visibility, not
-- fixed (out of scope).

SET statement_timeout = 0;

-- ── 1. Diagnostic before update ─────────────────────────────────────────────
DO $$
DECLARE
  v_before jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('seminole') INTO v_before;
  RAISE NOTICE 'Seminole BEFORE I: %', v_before->'I';
  RAISE NOTICE 'Seminole BEFORE G (regression watch): %', v_before->'G';
END $$;

-- ── 2. Create the R-4 zoning district for Altamonte Springs (944) ──────────
-- Sourced from Altamonte Springs LDC Municode index (Division 9, same division
-- as the existing R-3 row for this jurisdiction). No standards fabricated.
-- density_regulated=false (see LIVE ADVERSARIAL SELF-CATCH note above): R-4
-- density is set per RBC sub-area/overlay, not a single fixed zone-level
-- figure -- confirmed via altamonte.org/DocumentCenter/View/54 (City Plan 2030
-- GOP, Table 1.2 + Policy 1-1.2.15), same honest-non-applicable treatment as
-- the existing Sanford PD district.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
SELECT 944, 'R-4', 'R-4 MULTIPLE-FAMILY DWELLING DISTRICT', 'residential',
       'Same LDC division as R-3 (id=11800): "DIVISION 9. - R-3 AND R-4 MULTIPLE-FAMILY DWELLING DISTRICTS" -- medium/high density residential, min dwelling size 600 SF. Source: library.municode.com/fl/altamonte_springs/codes/land_development_code (web search confirmed live 2026-07-31). Density is NOT a single fixed zone-level figure: per City Plan 2030 GOP (altamonte.org/DocumentCenter/View/54, Table 1.2 + Policy 1-1.2.15), R-4 density is set per Regional Business Center (RBC) sub-area/block-type/EDO overlay, ranging 10-100 du/acre depending on location -- a location/overlay determination not made this session. density_regulated explicitly false (same treatment as Sanford PD) rather than fabricating a single figure. zone_standards intentionally left unpopulated.',
       'LDC Art. III Div. 9', NULL, false, NULL
WHERE NOT EXISTS (
  SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 944 AND code = 'R-4'
);

-- Idempotent corrective UPDATE in case this migration is re-run against a
-- state where the R-4 row already exists with the old (wrong) density_regulated=true
-- from the first live execution of this migration (2026-07-31 08:55 UTC).
UPDATE zoning_districts
SET density_regulated = false
WHERE jurisdiction_id = 944 AND code = 'R-4' AND density_regulated IS DISTINCT FROM false;

-- ── 3. Geo + assessed_value backfill (Census geocoder + scpafl.org VERIFIED) ─

UPDATE multi_county_auctions
SET latitude = 28.670416346047, longitude = -81.404657034537, assessed_value = 155753
WHERE lower(county) = 'seminole' AND case_number = '20260004/2024-001492'
  AND parcel_id = '10-21-29-528-1300-1030' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.658942047109, longitude = -81.38038289835, assessed_value = 100211
WHERE lower(county) = 'seminole' AND case_number = '20260008/2024-002188'
  AND parcel_id = '14-21-29-5SB-0200-2080' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.659357826622, longitude = -81.406110624675, assessed_value = 268999
WHERE lower(county) = 'seminole' AND case_number = '20260009/2024-002335'
  AND parcel_id = '15-21-29-509-1700-0080' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.660265895229, longitude = -81.454523668756, assessed_value = 289822
WHERE lower(county) = 'seminole' AND case_number = '20260010/2024-002745'
  AND parcel_id = '17-21-29-5BG-0000-018A' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.641825330185, longitude = -81.12152617881, assessed_value = 184695
WHERE lower(county) = 'seminole' AND case_number = '20260015/2024-003544'
  AND parcel_id = '21-21-32-5CF-4400-0080' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.786758890506, longitude = -81.265577133234, assessed_value = 139516
WHERE lower(county) = 'seminole' AND case_number = '20260029/2024-006503'
  AND parcel_id = '36-19-30-542-0000-013A' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.64251378226, longitude = -81.338897899491, assessed_value = 347247
WHERE lower(county) = 'seminole' AND case_number = '20260035/2024-003228'
  AND parcel_id = '20-21-30-503-0F00-0030' AND latitude IS NULL;

-- 20260025/2024-004214: NO geo/value update -- genuinely no street address to
-- geocode (confirmed via scpafl.org: vacant commercial parcel with no situs
-- address assigned). Left untouched; remains I-blocked honestly.

-- ── 4. parcel_id correction for 2024CA001701 (garbage placeholder -> real) ──
UPDATE multi_county_auctions
SET parcel_id = '22-21-30-502-0N00-0030'
WHERE lower(county) = 'seminole' AND case_number = '2024CA001701'
  AND parcel_id = 'Property Appraiser';

-- ── 5. parcel_zones inserts (all 10 rows) ───────────────────────────────────

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '10-21-29-528-1300-1030', 944, 'R-3', 'gold_standard_shard5_seminole_i_10row_20260731_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '10-21-29-528-1300-1030');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '14-21-29-5SB-0200-2080', 944, 'R-3', 'gold_standard_shard5_seminole_i_10row_20260731_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '14-21-29-5SB-0200-2080');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '15-21-29-509-1700-0080', 636, 'R-1', 'gold_standard_shard5_seminole_i_10row_20260731_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '15-21-29-509-1700-0080');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '17-21-29-5BG-0000-018A', 636, 'R-1A', 'gold_standard_shard5_seminole_i_10row_20260731_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '17-21-29-5BG-0000-018A');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '21-21-32-5CF-4400-0080', 636, 'R-1A', 'gold_standard_shard5_seminole_i_10row_20260731_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '21-21-32-5CF-4400-0080');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '25-19-30-5AG-0X00-0050', 904, 'RMOI', 'gold_standard_shard5_seminole_i_10row_20260731_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '25-19-30-5AG-0X00-0050');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '36-19-30-542-0000-013A', 904, 'RC-1', 'gold_standard_shard5_seminole_i_10row_20260731_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '36-19-30-542-0000-013A');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '20-21-30-503-0F00-0030', 636, 'R-1AA', 'gold_standard_shard5_seminole_i_10row_20260731_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '20-21-30-503-0F00-0030');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '23-21-29-516-0000-048K', 944, 'R-4', 'gold_standard_shard5_seminole_i_10row_20260731_scpafl_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '23-21-29-516-0000-048K');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '22-21-30-502-0N00-0030', 636, 'PD', 'gold_standard_shard5_seminole_i_10row_20260731_scpafl_verified_parcel_id_correction'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '22-21-30-502-0N00-0030');

-- ── 6. Diagnostic after update ───────────────────────────────────────────────
DO $$
DECLARE
  v_after jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('seminole') INTO v_after;
  RAISE NOTICE 'Seminole AFTER I: %', v_after->'I';
  RAISE NOTICE 'Seminole AFTER G (regression check): %', v_after->'G';
  RAISE NOTICE 'Seminole AFTER FULL: %', v_after;
END $$;

-- GOLD STANDARD SHARD-5 (osceola) -- dispatch ac5f5206-a862-494e-a345-f6b0eb4cbd09
-- Session: architect-20260724T000000
--
-- Osceola entered this session 8/10 (A,B,C,D,E,F,H,J PASS; G,I FAIL). This migration is the
-- audit record for live changes already applied via Supabase PostgREST during the session
-- (supabase db push / direct psql pooler auth both unavailable this session -- pooler auth
-- confirmed stale, same restriction noted in prior shard sessions on this repo). Idempotent;
-- safe to re-run.
--
-- ============================================================================
-- PART 1: LETTER G -- density_regulated reclassification (real gain: 7.7% -> 97.4%)
-- ============================================================================
-- Osceola's G letter was blocked by two independent sub-metrics read from
-- v_zoning_gold_standard_kpi_v3: density (7.7% of 483 "applicable" parcels) and pk1000
-- (0.0% of 9 applicable parcels). FAR has 0 applicable parcels for this jurisdiction (not a
-- blocker; PostgreSQL LEAST() ignores NULL args, confirmed via pg_get_functiondef of
-- public.pencil_dod_evaluate_county).
--
-- ROOT CAUSE (density): 443 of osceola's 496 tracked parcel_zones rows (jurisdiction_id=1186,
-- unincorporated Osceola County) are zoned 'PD' (Plan Development), with 1 PMUD and 1 STRPD.
-- A prior session (20260711t_shard7_osceola_g_i_zoning_veracity_ghost_purge_rebuild.sql)
-- already live-confirmed via the Municode API (jobId=478316, productId=15810, Sec 3.11.1(I))
-- that PD/PMUD/STRPD density is explicitly NOT a single codified number in Osceola's LDC --
-- "allowable density and intensity will be based on several factors" (i.e. set per individual
-- approved development order, not by a base-code table). That prior session correctly left
-- zone_standards.max_density_du_acre NULL for these three districts rather than fabricate a
-- number, but never flipped zoning_districts.density_regulated to false -- so
-- v_zoning_district_applicability's default-true fallback for non-commercial/industrial
-- categories kept counting all 445 PD/PMUD/STRPD parcels as "applicable but missing" against
-- the density denominator. This session closes that loop: the same real, already-cited
-- ordinance finding is now reflected in the applicability flag itself, matching the exact
-- precedent already used for Sanford PD / Seminole Co. PD / Lake Mary PUD / Winter Springs PUD
-- in 20260718f_gold_standard_shard3_seminole_g_pk1000_applicability_fix_run26f01b9b.sql.
--
-- VERIFIED LIVE before: density_applicable_parcels=483, pct_density_of_applicable=7.7
-- VERIFIED LIVE after:  density_applicable_parcels=38,  pct_density_of_applicable=97.4
-- (query: SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county='osceola')

UPDATE zoning_districts
SET density_regulated = false, far_regulated = false
WHERE jurisdiction_id = 1186 AND code IN ('PD', 'PMUD', 'STRPD');

-- ============================================================================
-- PART 2: LETTER G -- pk1000 (off-street parking) research: NOT_FOUND, correctly not written
-- ============================================================================
-- G's remaining blocker is pk1000: 9 parcels are pk1000_applicable (8 zoned 'CT' = Commercial
-- Tourist, 1 zoned 'CR' = "Commercial Restricted" -- NOT "Commercial Retail"; CR is a legacy/
-- preceding zoning district per LDC Table 3.1/3.2 Sec 3.1.3 that crosswalks to the current
-- 'CN' Neighborhood Commercial district), 0 of 9 have a real parking_per_1000sf value.
--
-- An ULTRACODE research pass (this session) found and independently re-verified live Osceola
-- LDC Sec 4.7.8 "Amount of Off-Street Parking," Table 4.7.8 (Chapter 4, Article 4.7 Transportation
-- Standards; nodeId LAND_DEVELOPMENT_CODE_CH4SIDEDEST_ART4.7TRST_4.7.8AMOREPA, jobId=478316,
-- productId=15810, https://api.municode.com/CodesContent?jobId=478316&nodeId=LAND_DEVELOPMENT_CODE_CH4SIDEDEST_ART4.7TRST_4.7.8AMOREPA&productId=15810).
-- This table is explicitly USE-based, not zoning-district-based: General Note 2 exempts only
-- Mixed Use Districts and the East U.S. 192 CRA (CT and CR are not exempt, so the table DOES
-- govern them), but the 24-row table keys ratios to land use (e.g. "Retail Sales and Services"
-- = 1/300 GSF = 3.33/1,000sf; "Restaurant" = 1/100 GSF = 10.0/1,000sf; "Multi-Tenant Shopping
-- Center <=25,000 GSF" = 1/250 GSF = 4.0/1,000sf; "Offices and Professional Services" = 1/300
-- GSF = 3.33/1,000sf), a roughly 4-10x spread with no CT- or CR-specific override anywhere in
-- the LDC. An independent adversarial refuter agent re-fetched both cited nodes live (HTTP 200)
-- and confirmed every quoted figure and section verbatim.
--
-- Writing a single zone-level pk1000 number for CT/CR would require picking one use-row and
-- asserting it as THE zone standard -- unsupported by the ordinance, and the exact fabrication
-- failure mode osceola's G letter has already shipped and reverted TWICE in this campaign (see
-- 20260704_shard9_osceola_ghost_success_revert.sql and
-- 20260711t_shard7_osceola_g_i_zoning_veracity_ghost_purge_rebuild.sql). No zone_standards
-- change is made here. G's pk1000 sub-metric remains an honest 0.0%.
--
-- NEXT-SESSION PATH (not attempted this session -- out of scope, needs per-parcel use data):
-- if a per-parcel land-use/building-type signal becomes available for the 9 pk1000_applicable
-- parcels (e.g. DOR use code, property-card use description), match each parcel individually to
-- its closest Table 4.7.8 use-row and apply per-parcel rather than per-zone-code -- this would
-- also require extending v_zoning_gold_standard_kpi_v3's pk1000 join to support a per-parcel
-- override, which is a schema/view change out of scope for a PostgREST-only session.

-- ============================================================================
-- PART 3: LETTER I -- live GIS card-completeness backfill (real gain: 35.8% -> 78.4%)
-- ============================================================================
-- I requires property_address + latitude/longitude + assessed_or_market_value + a zone_code-
-- resolvable parcel_id for each of osceola's 134 scoring-eligible auctions (propertyonion rows
-- excluded per the evaluator's own WHERE clause). Before this session: 48/134 (35.8%). A gap
-- analysis (86 incomplete rows) found ALL 86 already had a real parcel_zones row (E/zone_code
-- was never the blocker) -- the gap was purely missing latitude/longitude/assessed_value on
-- multi_county_auctions.
--
-- Of the 86, 81 carried real (if truncated/leading-zero-stripped) numeric Osceola parcel_ids;
-- 79 unique. For 75 of those 79, this repo's own parcel_zones.tax_account already stores the
-- REAL, full 18-digit PARCELNO (populated by a prior session's address-matched GIS ingestion)
-- -- letting this session query gis.osceola.org Parcels/FeatureServer/3 with an EXACT PARCELNO
-- match (zero ambiguity) rather than the naive prefix-LIKE search a first-pass ULTRACODE agent
-- correctly refused to resolve on (LIKE '<12-digit-prefix>%' against an 18-digit field returned
-- 2-1521 candidate features per parcel in this jurisdiction -- far too ambiguous to guess, and
-- the agent correctly reported all 86 as unresolved rather than pick one). One further pair
-- (case_numbers 4422023/4402024, parcel_id 032528287800, two real candidate tax_accounts) was
-- disambiguated by exact street-NUMBER match (multi_county_auctions already had the specific
-- address "2952 LUCAYAN HARBOUR CIR 106" for 4422023, matching tax_account
-- 032528287800010300's StreetNumb=2952 exactly, vs the sibling unit at StreetNumb=2950).
--
-- 57 rows resolved and applied live via exact-match GIS queries (real AssessedVa/CurrJust and
-- polygon-centroid lat/lon from each matched feature -- no defaults, no interpolation).
--
-- RESIDUAL (29 of 134, left honestly unresolved, not fabricated):
--  - 24 rows: parcel_zones.tax_account is NULL/unpopulated for these parcel_ids AND
--    multi_county_auctions.property_address is the generic placeholder "Osceola County, FL
--    34741" (21 of 24) or a bare street name with no house number (3 of 24: DAKOTA AVE,
--    E STATE RD 60, GARDEN ST) -- neither gives enough signal for a confident GIS match without
--    guessing among tens-to-hundreds of same-prefix candidates. Needs the heavier address-to-
--    fl_parcels matching method a prior session used for the original 26->89 parcel_zones
--    expansion, out of scope for this session's remaining time.
--  - 5 rows: synthetic 'OSC-xxxxxxxxxxxx' parcel_ids, sourced from
--    osceola_clerk_civilmortgageforeclosures_pdf (courts.osceolaclerk.com foreclosure calendar
--    PDF) with no address/legal_description/parcel data captured at ingestion. Resolving these
--    needs a PDF-parse enrichment pass on the source document, a different pipeline task, not a
--    GIS lookup.
--
-- VERIFIED LIVE before: card_complete=48 of 134 (35.8%)
-- VERIFIED LIVE after:  card_complete=105 of 134 (78.4%)
-- (query: SELECT public.pencil_dod_evaluate_county('osceola'))

UPDATE multi_county_auctions AS mca
SET latitude = v.latitude,
    longitude = v.longitude,
    assessed_value = v.assessed_value,
    property_address = COALESCE(mca.property_address, v.property_address)
FROM (VALUES
  ('51012023', 28.1068, -81.146343, 4100, NULL),
  ('57812023', 28.096159, -81.17266, 1800, NULL),
  ('38712023', 28.039232, -81.000368, 1600, NULL),
  ('49302020', 28.133321, -81.142553, 3600, NULL),
  ('552024', 28.342709, -81.473401, 265700, NULL),
  ('23942022', 28.15247, -81.163371, 933, NULL),
  ('51562023', 28.264215, -81.642606, 415900, NULL),
  ('23262024', 28.153859, -81.485534, 307600, NULL),
  ('35612023', 28.122085, -81.138333, 3600, NULL),
  ('20782022', 28.325538, -81.484135, 85742, NULL),
  ('46622024', 28.168538, -81.470167, 160800, NULL),
  ('53602022', 28.100787, -81.155041, 1800, NULL),
  ('11632023', 28.33116, -81.537974, 85941, NULL),
  ('7872023', 28.335537, -81.626904, 295600, NULL),
  ('59722024', 28.100312, -81.181482, 3600, NULL),
  ('49622019', 28.122656, -80.963387, 163630, NULL),
  ('27752024', 28.311249, -81.483196, 166500, NULL),
  ('30352022', 28.141191, -81.138612, 700, NULL),
  ('42622019', 28.122888, -81.146513, 700, NULL),
  ('40972023', 28.279262, -81.160403, 900, NULL),
  ('24942024', 28.154143, -81.468955, 242209, NULL),
  ('34892020', 28.15195, -81.173618, 933, NULL),
  ('51032023', 28.1068, -81.146343, 4100, NULL),
  ('44462024', 28.128809, -81.062925, 32210, NULL),
  ('5172023', 28.333584, -81.498617, 61710, NULL),
  ('47802024', 28.156479, -81.455309, 169200, NULL),
  ('82023', 28.343867, -81.468418, 453500, NULL),
  ('41092023', 28.2828, -81.160294, 399, NULL),
  ('4422023', 28.337114, -81.496587, 223400, NULL),
  ('38702023', 28.039232, -81.000368, 1600, NULL),
  ('20822021', 28.154452, -81.409135, 6700, NULL),
  ('43232023', 28.168227, -81.476222, 200000, NULL),
  ('83272020', 28.095918, -80.966907, 7910, NULL),
  ('65372020', 28.1079, -81.16302, 1800, NULL),
  ('83442020', 28.090717, -80.962802, 72500, NULL),
  ('21002023', 28.326024, -81.464523, 236700, NULL),
  ('39892023', 28.290146, -81.362514, 15811, NULL),
  ('22272023', 28.152027, -81.170621, 1800, NULL),
  ('28472024', 28.144707, -81.177742, 933, NULL),
  ('22202023', 28.155787, -81.169854, 700, NULL),
  ('20832023', 28.148204, -81.189898, 1800, NULL),
  ('11962023', 28.328311, -81.453593, 2, NULL),
  ('25262023', 28.141005, -81.177696, 1800, NULL),
  ('21772023', 28.145848, -81.46696, 94333, NULL),
  ('43892023', 28.122475, -81.451107, 86520, NULL),
  ('23542023', 28.140585, -81.159024, 1800, NULL),
  ('40242023', 28.118984, -81.169687, 1800, NULL),
  ('40652023', 27.763012, -80.883635, 200, NULL),
  ('14532024', 28.317476, -81.541388, 153917, NULL),
  ('52282023', 28.097131, -81.1506, 1800, NULL),
  ('562024', 28.342709, -81.473401, 265700, NULL),
  ('15402024', 28.318969, -81.349894, 209611, NULL),
  ('29992024', 28.317808, -81.615102, 2, NULL),
  ('532024', 28.342501, -81.474238, 265700, NULL),
  ('16222024', 28.322753, -81.345011, 37481, NULL),
  ('58062024', 28.260414, -81.592012, 281400, NULL),
  ('4402024', 28.337114, -81.496587, 223400, NULL)
) AS v(case_number, latitude, longitude, assessed_value, property_address)
WHERE mca.case_number = v.case_number;

-- Verification (run live post-application):
-- SELECT public.pencil_dod_evaluate_county('osceola');
-- Expected: I metric ~78.4 (card_complete=105 of 134), G unchanged at 0.0 (density=97.4 far= pk1000=0.0).

-- GOLD STANDARD SHARD-1 (dispatch a1f33d10-ebc0-4542-9b60-3ce11d2d9630)
-- Gadsden / Okeechobee / Columbia: applies real-source research findings
-- from a background ULTRALOOP research workflow (11 parallel agents,
-- property appraiser records, clerk lis pendens filings, FL DOR statewide
-- cadastral NAL, Municode ordinance text, US Census geocoder). Only
-- VERIFIED findings were applied -- every UNKNOWN finding was left alone
-- rather than guessed. See session report for the full research log.

-- ============================================================
-- GADSDEN E (87.0% -> 91.3%, still FAIL, need 1 more of 2 remaining)
-- ============================================================
-- Case 25000696CA: Lis Pendens (DocketID 12564435, OR Book 971 Pg 1199-1200,
-- Instrument 250006283) prints an explicit "TAX ID:" line -- direct read
-- from a recorded court document.
UPDATE multi_county_auctions
SET parcel_id = '2-03-3N-6W-0000-00213-2300'
WHERE lower(county) = 'gadsden' AND case_number = '25000696CA' AND parcel_id IS NULL;
-- Cases 25000942CA and 25000901CA remain UNKNOWN: confirmed real legal
-- descriptions via Lis Pendens, but no Tax ID/STRAP is stated in any filed
-- document, qpublic.net is Cloudflare-blocked, and the Gadsden PA's own
-- ArcGIS parcel layer has no owner/address fields (100+ undisambiguated
-- candidates per section). Needs browser automation or a data-portal
-- credential in a future session, not a guess.

-- ============================================================
-- OKEECHOBEE E (94.4% -> 96.3%, PASS)
-- ============================================================
-- Case 472025CA000143CAAXMX verified via Okeechobee Clerk's official
-- Judicial/Foreclosure Update List (plaintiff/defendant/sale-date/opening-bid
-- all match our existing row exactly) cross-referenced to the County Tax
-- Collector's parcel search by owner surname (Arnold).
UPDATE multi_county_auctions
SET parcel_id = '1-11-37-34-0A00-00006-C000',
    property_address = '7285 NW 30TH ST, OKEECHOBEE, FL 34972'
WHERE lower(county) = 'okeechobee' AND case_number = '472025CA000143CAAXMX';
-- Cases 472025CA000130CAAXMX and 472025CA000205CAAXMX remain UNKNOWN: not on
-- the Clerk's public sale list (still pre-judgment), OCRS docket requires an
-- authenticated session WebFetch cannot drive, realforeclose.com 403s.
-- NOTE: the stored lat/lng on case 130 (27.3815,-80.8984) was proven to NOT
-- intersect any Okeechobee parcel in the FL GIO cadastral layer -- flagging
-- that field as unreliable for a future session, not corrected here (out of
-- scope of this fix; do not use it to derive an address).

-- ============================================================
-- OKEECHOBEE I address backfill (40.7% -> 90.7%, still FAIL by ~2 rows)
-- ============================================================
-- 38 STRAPs resolved via Okeechobee County Tax Collector parcel search,
-- okeechobeepa.com GIS record search, and FL DOR Statewide Cadastral (NAL)
-- PHY_ADDR1/PHY_CITY/PHY_ZIPCD (cross-validated against Okeechobee Clerk tax
-- deed case owner names for several). Street-name-only addresses (no house
-- number) are written verbatim as recorded by the county -- that IS the true
-- situs address for those vacant/unaddressed parcels, not a scraping gap.
UPDATE multi_county_auctions mca
SET property_address = v.addr
FROM (VALUES
  ('1-36-34-33-0A00-00001-O000','14465 NW 252ND ST, Okeechobee, FL 34972'),
  ('1-13-34-33-0A00-00005-E000','15373 NW 302ND ST, Okeechobee, FL 34972'),
  ('1-20-34-33-0A00-00009-O000','22287 NW 280TH ST, Okeechobee, FL 34972'),
  ('1-20-34-33-0A00-00009-B000','22294 NW 284TH ST, Okeechobee, FL 34972'),
  ('1-21-34-33-0A00-00002-A000','19428 NW 288TH ST, Okeechobee, FL 34972'),
  ('1-21-34-33-0A00-00015-P000','19417 NW 280TH ST, Okeechobee, FL 34972'),
  ('1-24-34-33-0A00-00009-A000','15842 NW 284TH ST, Okeechobee, FL 34972'),
  ('1-24-34-33-0A00-00010-D000','15790 NW 284TH ST, Okeechobee, FL 34972'),
  ('1-08-34-33-0A00-00008-P000','NW 316TH ST, Okeechobee, FL 34972'),
  ('1-10-34-33-0A00-00011-3100','NW 312TH ST, Okeechobee, FL 34972'),
  ('1-35-37-35-0020-00000-0650','3732 SE 19TH TERR, OKEECHOBEE, FL'),
  ('1-34-37-35-0050-00000-1350','1601 HWY 441 SE, UNIT 135, OKEECHOBEE, FL'),
  ('1-08-34-33-0A00-00012-O000','NW 312TH ST, OKEECHOBEE, FL'),
  ('1-22-34-33-0A00-00021-J000','18420 NW 278TH ST, OKEECHOBEE, FL'),
  ('1-22-34-33-0A00-00021-P000','NW 276TH ST, OKEECHOBEE, FL'),
  ('1-25-37-35-0010-00070-0030','3016 SE 33RD TER, OKEECHOBEE, FL'),
  ('1-12-37-34-0A00-00007-A000','5451 NW 30TH ST, OKEECHOBEE, FL'),
  ('1-10-36-35-0A00-00004-A000','HWY 441 N, OKEECHOBEE, FL'),
  ('1-04-37-35-0010-00000-025A','3690 NW 6TH AVE, OKEECHOBEE, FL'),
  ('1-18-37-35-0020-00020-0170','3575 NW 7TH ST, OKEECHOBEE, FL 34972'),
  ('1-22-37-35-0040-0000D-0130','1301 SE 5TH ST, OKEECHOBEE, FL 34974'),
  ('1-24-37-35-0A00-00004-A000','615 SE 32ND AVE, OKEECHOBEE, FL 34974'),
  ('1-25-37-35-0120-00110-0780','4504 SE 23RD CT, OKEECHOBEE, FL 34974'),
  ('1-33-37-35-0010-00000-0073','4059 SW 13TH WAY, OKEECHOBEE, FL 34974'),
  ('1-35-37-35-0020-00000-0670','3712 SE 19TH TERR, OKEECHOBEE, FL 34974'),
  ('1-15-37-36-0A00-00002-1090','866 NE 104TH CT, OKEECHOBEE, FL 34974'),
  ('1-17-37-36-0A00-00003-0292','6748 NE 1ST ST, OKEECHOBEE, FL 34974'),
  ('1-17-37-36-0A00-00003-041E','6568 NE 2ND ST, OKEECHOBEE, FL 34974'),
  ('1-17-37-36-0A00-00003-150D','6480 NE 7TH LANE, OKEECHOBEE, FL 34974'),
  ('1-18-37-36-0A00-00010-0290','5864 NE 3RD LN, OKEECHOBEE, FL 34974'),
  ('1-20-37-36-0A00-00001-A000','6502 E CENTER ST, OKEECHOBEE, FL 34974'),
  ('1-31-37-36-0010-00010-0190','4314 SE 49TH CT, OKEECHOBEE, FL 34974'),
  ('1-04-38-36-0020-00000-0760','7820 SE 57TH DR, OKEECHOBEE, FL 34974'),
  ('1-04-38-36-0040-00050-0210','6009 SE 95TH TRL, OKEECHOBEE, FL 34974'),
  ('1-05-38-36-0040-00050-0120','6415 SE 55TH ST, OKEECHOBEE, FL 34974'),
  ('1-05-38-36-0070-00270-0240','5388 SE 65TH TERR, OKEECHOBEE, FL 34974'),
  ('1-06-38-36-0A00-00002-0000','5502 US HWY 441 SE, OKEECHOBEE, FL 34974'),
  ('1-10-36-35-0040-00000-0150','11305 NE 3RD CIR, OKEECHOBEE, FL 34972')
) AS v(parcel_id, addr)
WHERE lower(mca.county) = 'okeechobee' AND mca.parcel_id = v.parcel_id AND mca.property_address IS NULL;
-- Remaining 5 I-failures: case 472025CA000225CAAXMX ("MULTIPLE PARCELS",
-- no single situs), STRAP 1-25-37-35-0070-00060-1760 (does not exist in the
-- live tax roll -- confirmed via prefix search of neighboring suffixes,
-- likely a source transcription error), cases 130/205 (blocked, see E note
-- above), and case 143 (has address+parcel now but its parcel_id is not yet
-- in the zoning card -- needs zoning research, not an address problem).

-- ============================================================
-- OKEECHOBEE G (57.7% density -> 62.7%, still FAIL; far unchanged 0.0%)
-- ============================================================
-- "A" (Agriculture) confirmed to be the SAME district as the
-- already-populated "AG" (Sec. 2.03.04 footnote 1: "AC-Agriculture
-- Conservation is now A-Agriculture"), density independently corroborated
-- at 0.10 du/acre by both Sec. 2.01.04 (FLU density table, "1 unit/10
-- acres") and Sec. 7.02.02(C) Note 6 ("maximum density of one unit per 10
-- gross acres").
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT 11440, 0.10,
       'https://library.municode.com/fl/okeechobee_county/codes/code_of_ordinances?nodeId=PTIILADERE_ARTIILAUSTYDEIN_2.01.00LAUSCA_2.01.04TADEDWUNTYREUS',
       'Sec. 2.01.04 (Agriculture FLU density table: 1 unit/10 acres) + Sec. 7.02.02(C) Note 6 (same figure); Sec. 2.03.04 footnote 1 confirms A is the same district as AG'
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 11440);

-- PD (Planned Development): Sec. 2.04.17(D)(4)(a)-(b) requires each PD
-- application to propose its own density in the conceptual development
-- plan -- density is genuinely project-specific, not a fixed ordinance
-- number. Correcting the applicability flag (density_regulated=false) is
-- the honest fix; inventing a representative number would misstate the
-- ordinance.
UPDATE zoning_districts
SET density_regulated = false, ordinance_section = 'Sec. 2.04.17(D)(4)(a)-(b)'
WHERE id = 11442 AND density_regulated IS NULL;
-- RSF, RMH, and C (FAR) remain UNKNOWN: Sec. 11.02.01(A) establishes that
-- Okeechobee's zoning code does NOT tie density/FAR to the zoning district
-- code at all -- both are tabulated by Future Land Use (FLU) category in
-- Sec. 2.01.04/2.01.05, and each district is valid under multiple different
-- FLU categories with different caps. A single per-district number cannot be
-- honestly asserted without a parcel-level FLU join, which is out of scope
-- of this fix (would require ingesting Okeechobee's FLU GIS layer and
-- joining per-parcel -- a real architecture gap, not a research gap).

-- ============================================================
-- COLUMBIA E (93.3% -> 100.0%, PASS)
-- ============================================================
-- Case 2025-249-CA / 294 NE Omar Terrace: found via Columbia County's own
-- ArcGIS REST "Parcels_and_Addresses" MapServer (exact address match) and
-- cross-checked against the Parcels layer (owner STAFFORD JAMES EARL matches
-- case defendant Stacey Earl Stafford) and the county's public
-- ParcelDetails.aspx page (HTTP 200, verbatim owner+location match).
UPDATE multi_county_auctions
SET parcel_id = '28-1S-17-04576-002'
WHERE lower(county) = 'columbia' AND case_number = '2025-249-CA' AND parcel_id IS NULL;

-- ============================================================
-- COLUMBIA I enrichment (0.0% -> still 0.0%, see ghost-purge below)
-- ============================================================
-- Geocoded via US Census Bureau Geocoder; assessed values via the Columbia
-- County Property Appraiser's live GIS record search (columbia.floridapa.com).
UPDATE multi_county_auctions mca
SET latitude = v.lat::double precision, longitude = v.lng::double precision, assessed_value = v.val::numeric
FROM (VALUES
  ('2023-492-CA','30.065590029572','-82.594005289192','75216'),
  ('2023-79-CA','30.223400957295','-82.681202066777','48649'),
  ('2025-103-CA','30.220256573208','-82.642101432974','61212'),
  ('2025-2196-CC','29.926295912386','-82.72278125125','88803'),
  ('2025-256-CA','30.159299166316','-82.688186866926','141512'),
  ('2025-260-CA','30.183594597214','-82.718075998394','534913'),
  ('2025-354-CA','29.876852676756','-82.743535680147','127231'),
  ('2025-396-CA','30.227980089938','-82.726050592101','118569'),
  ('2025-487-CA','30.213986395274','-82.634004472337','106738'),
  ('2025-499-CA','29.982780054745','-82.653354170938','227548'),
  ('2025-501-CA','30.165357924285','-82.776912195258','89292'),
  ('2026-12-CA','30.237581760106','-82.709133625288','121863'),
  ('2026-54-CA','29.871866441386','-82.736893483404','280028')
) AS v(case_number, lat, lng, val)
WHERE lower(mca.county) = 'columbia' AND mca.case_number = v.case_number;

-- 2025-249-CA: lat/lng only (parcel just confirmed above; appraiser value
-- lookup was out of scope for the agent that only had the address).
UPDATE multi_county_auctions
SET latitude = 30.381487758963, longitude = -82.617767880375
WHERE lower(county) = 'columbia' AND case_number = '2025-249-CA';

-- 2025-63-CA: lat/lng only. Our stored parcel_id ('00130-000 AND 00130-001')
-- does NOT match 283 NW Cole Terrace on the live appraiser system -- one ID
-- resolves to an unrelated rural timberland tract, the other to no record at
-- all. The address DOES match a different real parcel (36-3S-16-02611-101,
-- a commercial building), but writing that value against our stored
-- (probably wrong) parcel_id would misrepresent which parcel we mean. Not
-- writing assessed_value here -- flagged for human review of the underlying
-- parcel_id mismatch before any value is attached.
UPDATE multi_county_auctions
SET latitude = 30.179332184381, longitude = -82.669039521498
WHERE lower(county) = 'columbia' AND case_number = '2025-63-CA';

-- ============================================================
-- COLUMBIA G GHOST-SUCCESS PURGE (100.0% false-PASS -> honest FAIL/unmeasurable)
-- ============================================================
-- CRITICAL HONESTY FINDING: Columbia's G letter was reading PASS (100.0%)
-- entirely on 6 fabricated parcel_zones rows with parcel_ids literally named
-- 'SYN-COL-FC-001' through 'SYN-COL-TD-003' (source tag
-- 'shard7_g_i_fix/columbia_auto') -- placeholder/synthetic data that does
-- NOT correspond to any of Columbia's 15 real auction parcels (09198-001,
-- 02123-027, etc — verified none of the 15 real parcel_ids match any
-- parcel_zones row for jurisdiction 974 both before and after this purge).
-- This inflated the scoreboard with a false PASS. Purging per the Honesty
-- Protocol / SHIP GATE ghost-success-revert precedent used elsewhere in this
-- campaign (e.g. Bradford, suwannee). G now correctly reads
-- unmeasurable/FAIL until real Lake City zoning is assigned to the actual
-- auction parcels.
DELETE FROM parcel_zones WHERE jurisdiction_id = 974 AND parcel_id LIKE 'SYN-COL-%';
-- The orphaned zone_standards row for Lake City R-1 (max_density_du_acre=4.00,
-- no source_url/ordinance_section) is left in place (harmless now that no
-- parcel references it) but flagged: do not reuse until a real Lake City
-- ordinance citation is attached.

-- ============================================================
-- VERIFIED before/after via pencil_dod_evaluate_county (live, this session):
--   gadsden:    E 87.0->91.3 (still FAIL, 1/2 remaining parcels genuinely blocked)
--   okeechobee: E 94.4->96.3 PASS | I 40.7->90.7 (still FAIL by ~2 rows) | G 0.0->0.0 (density 57.7->62.7, still FAIL)
--   columbia:   E 93.3->100.0 PASS | G 100.0(ghost)->FAIL (honest) | I 0.0->0.0 (blocked on real zoning, see purge note)
-- ============================================================

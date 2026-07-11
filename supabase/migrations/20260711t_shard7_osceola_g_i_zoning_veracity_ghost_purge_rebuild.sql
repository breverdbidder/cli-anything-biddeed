-- GOLD STANDARD SHARD-7 (flagler/osceola) -- dispatch 2f9f6a3e-a24c-4638-bcd3-5fe8f031d830
-- item: osceola_G_I_zoning_veracity
--
-- osceola G/I: purge fabricated zone_code='R-1' seed (127 rows, source='shard5-loop472-seed',
-- single 5-min bulk-insert window 2026-06-25 08:18-08:23 UTC) and rebuild with REAL zoning
-- from gis.osceola.org Zoning_Parcels FeatureServer (live ArcGIS REST, field PARCELNO/PRIM_ZON).
--
-- VERIFICATION: 20-parcel exact-match sample (multi_county_auctions.parcel_id -> fl_parcels
-- co_no=59 phy_addr1 address match -> real 18-digit PARCELNO -> live GIS query) found 0/18
-- resolvable matches confirming R-1; real zones were PD(7) INCORP(5) AC(2) CT(1) CR(1)
-- NO_MATCH(2). Confirms fabrication fingerprint matching this campaign's martin/taylor/broward/
-- okeechobee/gadsden purges (uniform placeholder value, single bulk-insert timestamp, generic
-- source tag). ULTRALOOP audit row logged (gold_standard_ultraloop_audit id=5933).
--
-- REBUILD: of osceola's 124 distinct scoring-eligible auction parcel_ids, 35 carry a real street
-- address usable for exact fl_parcels match; all 35 resolved to a real 18-digit parcel_id (100%
-- hit rate); of those, 26 fall in unincorporated Osceola County jurisdiction with a specific real
-- zone code from the live GIS layer (9 more are 'INCORP' -- inside a municipality e.g. Kissimmee/
-- St Cloud -- correctly left unassigned since jurisdiction 1186 represents unincorporated county
-- only, and no per-city zoning layer was scraped this pass; 89 parcels have no street address in
-- multi_county_auctions at all -- 'Osceola County, FL 34741' or 'Land <legal>' placeholder text --
-- so cannot be address-matched to fl_parcels this pass; scoped out, not guessed).
--
-- zone_standards NOT populated with numeric setback/density/FAR values this pass: Osceola's Land
-- Development Code on library.municode.com returns HTTP 403 (WAF) to both curl and WebFetch in
-- this sandbox, and Firecrawl (which bypasses it) is confirmed absent from this environment.
-- Rather than fabricate density/setback numbers the way the purged seed did, zone_standards rows
-- are inserted with all numeric fields NULL and honest source_url/confidence_score=0 markers.
-- This means G's density/far/pk1000 metrics legitimately regress to near-zero coverage after
-- this fix (expected, correct outcome -- the fabricated 100.0 is replaced with an honest low
-- number, not hidden).

BEGIN;

-- 1) Purge fabricated seed chain: zone_standards -> parcel_zones -> zoning_districts
DELETE FROM zone_standards WHERE zoning_district_id IN (
  SELECT id FROM zoning_districts WHERE jurisdiction_id = 1186 AND code = 'R-1'
    AND created_at = '2026-06-25 08:18:10.481923+00'
);

DELETE FROM parcel_zones
WHERE jurisdiction_id = 1186 AND source = 'shard5-loop472-seed';

DELETE FROM zoning_districts
WHERE jurisdiction_id = 1186 AND code = 'R-1'
  AND created_at = '2026-06-25 08:18:10.481923+00';

-- 2) Insert REAL zoning_districts rows (verified live against gis.osceola.org Zoning_Parcels)
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, created_at) VALUES (1186, 'AC', 'Agricultural', 'agricultural', NULL, now())
ON CONFLICT (jurisdiction_id, code) DO NOTHING;
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, created_at) VALUES (1186, 'CR', 'Commercial Retail', 'commercial', NULL, now())
ON CONFLICT (jurisdiction_id, code) DO NOTHING;
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, created_at) VALUES (1186, 'CT', 'Commercial Tourist', 'commercial', NULL, now())
ON CONFLICT (jurisdiction_id, code) DO NOTHING;
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, created_at) VALUES (1186, 'PD', 'Plan Development', 'planned_development', NULL, now())
ON CONFLICT (jurisdiction_id, code) DO NOTHING;
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, created_at) VALUES (1186, 'PMUD', 'Plan Multi-Use Development', 'planned_development', NULL, now())
ON CONFLICT (jurisdiction_id, code) DO NOTHING;
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, created_at) VALUES (1186, 'RMH', 'Residential Mobile Home', 'residential', NULL, now())
ON CONFLICT (jurisdiction_id, code) DO NOTHING;
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, created_at) VALUES (1186, 'STRPD', 'Short Term Rental Planned Development', 'planned_development', NULL, now())
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- 3) Insert real zone_standards placeholder rows (honest NULLs, confidence_score=0, no fabricated numbers)
INSERT INTO zone_standards (zoning_district_id, source_url, confidence_score, scraped_at)
SELECT d.id, 'https://gis.osceola.org/hosting/rest/services/Zoning_Parcels/FeatureServer/0 (zone_code only -- ordinance standards blocked, library.municode.com/fl/osceola_county returns 403 WAF)', 0.00, now()
FROM zoning_districts d WHERE d.jurisdiction_id = 1186 AND d.code IN ('AC','CR','CT','PD','PMUD','RMH','STRPD')
ON CONFLICT (zoning_district_id) DO NOTHING;

-- 4) Insert real parcel_zones rows: 26 parcels verified live against gis.osceola.org PARCELNO
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, created_at) VALUES
('012530330800', '012530330800010130', 1186, 'AC', 'Agricultural', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('032528287800', '032528287800010300', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('032530420800', '032530420800010360', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('052527409900', '052527409900011210', 1186, 'STRPD', 'Short Term Rental Planned Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('052528466800', '052528466800011130', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('062527314100', '062527314100011010', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('062527469400010380', '062527469400010380', 1186, 'PMUD', 'Plan Multi-Use Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('072530267700780180', '072530267700780180', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('072530267700790060', '072530267700790060', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('102527339500', '102527339500010310', 1186, 'CT', 'Commercial Tourist', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('112528370000030050', '112528370000030050', 1186, 'RMH', 'Residential Mobile Home', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('112528370000150100', '112528370000150100', 1186, 'RMH', 'Residential Mobile Home', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('122528540500', '122528540500011340', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('122528540500011310', '122528540500011310', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('122528540500011360', '122528540500011360', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('132528000002620000', '132528000002620000', 1186, 'CT', 'Commercial Tourist', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('132528462400', '132528462400010140', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('182527494300', '182527494300015450', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('182527558700', '182527558700011670', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('182530291800', '182530291800011431', 1186, 'CR', 'Commercial Retail', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('202629307200', '202629307200012130', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('242528375600010910', '242528375600010910', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('252628610006', '252628610006000150', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('252628611614', '252628611614500140', 1186, 'PD', 'Plan Development', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('302527570400099030', '302527570400099030', 1186, 'CT', 'Commercial Tourist', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now()),
('302527571000', '302527571000181801', 1186, 'CT', 'Commercial Tourist', 'shard7-run-2f9f6a3e-gis-osceola-live-verified', now());

COMMIT;

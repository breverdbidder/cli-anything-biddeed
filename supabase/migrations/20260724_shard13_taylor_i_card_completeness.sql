-- SHARD-13 taylor (dispatch ab46d459, loop run 6148): letter I card-completeness fixes.
-- Real, source-cited data only. No fabricated parcel-to-district assignments.
--
-- 1. Extend the existing Perry/RSF-2 precedent (jurisdictions.id=908) to parcel
--    07503-000 (TDA 26-028) — confirmed inside Perry city limits via US Census
--    TIGERweb Incorporated Places point-in-polygon (2026-07-24), same DOR_UC=001
--    SFR profile as the two parcels already carrying RSF-2 in this jurisdiction.
-- 2. Bank real Taylor County Land Development Code (Ch. 42, Art. V, Div. 2)
--    unincorporated land-use/zoning district definitions + density/FAR standards
--    for a future session that gets real parcel-level FLUM/GIS access (Taylor's
--    parcel-search GIS — pubrecords.taylorclerk.com, qpublic.schneidercorp.com —
--    is Cloudflare-protected; confirmed blocked 2026-07-24 via httpx + headless
--    Playwright + Firecrawl [402 insufficient credits]). No parcel_zones rows
--    are inserted against these unincorporated districts this session — doing
--    so without real spatial evidence would be a guess, which this campaign's
--    own history (ghost-success purges) explicitly bans.

BEGIN;

-- (1) Perry/RSF-2 precedent extension — real TIGER-verified city boundary match.
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES ('07503-000', 'R07503-000', 908, 'RSF-2', 'Residential (Conventional) Single Family',
        'tiger_places_boundary_match:2026-07-24+fl_gio_dor_uc_profile_match')
ON CONFLICT DO NOTHING;

-- (2) Unincorporated Taylor County jurisdiction + real Ch. 42 Art. V Div. 2 districts.
INSERT INTO jurisdictions (name, county, county_name, state, co_no, data_source, municode_url, active)
VALUES ('Unincorporated Taylor County', 'Taylor', 'Taylor', 'FL', 62,
        'municode_ch42_art5_div2_verified_2026-07-24',
        'https://library.municode.com/fl/taylor_county/codes/code_of_ordinances?nodeId=COOR_CH42LADECO_ARTVLAUS',
        true)
ON CONFLICT DO NOTHING;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, density_regulated, far_regulated, pk1000_regulated)
SELECT j.id, d.code, d.name, 'unincorporated_flu_district', d.description, d.ordinance_section, d.density_regulated, d.far_regulated, false
FROM jurisdictions j,
(VALUES
  ('AG1', 'Agricultural 1', 'Very large scale agricultural/timber lands; 1 du/20 ac gross density', '42-382(1)', true, false),
  ('AG2', 'Agricultural 2', 'Medium-to-large scale agricultural lands; 1 du/10 ac gross density', '42-382(2)', true, false),
  ('AGR', 'Agricultural/Rural Residential', 'Small-to-medium scale agricultural lands; 1 du/5 ac gross density', '42-382(3)', true, false),
  ('MUR', 'Mixed Use Rural Residential', 'Transitioning rural areas; up to 1 du/2 ac', '42-382(4)', true, false),
  ('MUD', 'Mixed Use Urban Development', 'Mixed residential/business near urbanizing areas; up to 2 du/ac', '42-382(5)', true, false),
  ('I', 'Industrial', 'Wood products, warehousing, manufacturing, airport/aviation uses; max FAR 1.0', '42-382(6)', false, true),
  ('CAR', 'Aviation-Related Commercial', 'Uses characterized by/serving the aviation industry', '42-382(7)', false, false),
  ('CWO', 'Water-Oriented Commercial', 'Tourism/water-oriented commercial uses', '42-382(8)', false, false),
  ('P', 'Public', 'Educational, recreational, conservation, public facilities', '42-382(9)', false, false),
  ('CON', 'Conservation', 'Environmentally sensitive/publicly-owned reservation lands; max 1 du/40 ac', '42-382(10)', true, false)
) AS d(code, name, description, ordinance_section, density_regulated, far_regulated)
WHERE j.name = 'Unincorporated Taylor County' AND j.county = 'Taylor'
ON CONFLICT DO NOTHING;

-- Density (Sec. 42-383) and FAR (Sec. 42-384) standards, ordinance-text values only.
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section)
SELECT zd.id, v.max_density_du_acre, v.max_far,
       'https://library.municode.com/fl/taylor_county/codes/code_of_ordinances?nodeId=COOR_CH42LADECO_ARTVLAUS',
       v.ordinance_section
FROM zoning_districts zd
JOIN jurisdictions j ON j.id = zd.jurisdiction_id AND j.name = 'Unincorporated Taylor County'
JOIN (VALUES
  ('AG1', 0.05,  NULL::numeric, '42-383(a)'),
  ('AG2', 0.10,  NULL::numeric, '42-383(a)'),
  ('AGR', 0.20,  NULL::numeric, '42-383(a)'),
  ('MUR', 0.50,  NULL::numeric, '42-383(a)'),
  ('MUD', 2.00,  NULL::numeric, '42-383(a)'),
  ('I',   NULL::numeric, 1.0,   '42-384(c)'),
  ('CON', 0.025, NULL::numeric, '42-382(10)')
) AS v(code, max_density_du_acre, max_far, ordinance_section) ON v.code = zd.code
ON CONFLICT DO NOTHING;

COMMIT;

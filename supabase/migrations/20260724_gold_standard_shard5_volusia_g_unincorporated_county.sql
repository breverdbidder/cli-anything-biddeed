-- Gold Standard shard-5 (volusia) dispatch ee5042ee, letter G fix, part 1 of N:
-- unincorporated Volusia County (jurisdiction_id=1511), 30 zone codes, 235 of 361
-- zone-linked auction parcels (65%).
--
-- BASELINE (VERIFIED live 2026-07-24 via pencil_dod_evaluate_county('volusia')):
--   G: density=4.0 far=1.6 pk1000=1.6, FAIL (threshold 95% on each, LEAST() binds).
--
-- SOURCE: Volusia County Code of Ordinances via api.municode.com (ClientID=10989,
-- productId=11665 'Code of Ordinances', jobId=470107 'Supplement 107', codified
-- through Ordinance No. 2026-03, enacted 2026-01-20). Chapter 72 - LAND PLANNING,
-- Article II - ZONING:
--   Sec. 72-241 Classifications -- per-district Minimum lot size / Maximum density
--   Sec. 72-286 Off-street parking and loading -- per-use-category parking ratios
--   Sec. 72-289 Planned unit development regulations -- confirms PUD/PUDA/PUDEA
--     density is individually negotiated per master plan, no fixed base ratio
-- Fetched live via curl, no auth required, HTML content stripped and parsed with
-- BeautifulSoup; every value below traces to a specific Sec. 72-241 classification
-- block (verified against the actual header boundaries, not assumed offsets).
--
-- METHODOLOGY:
--   - Single-family / one-dwelling-per-lot districts (agricultural, forestry, RC,
--     rural, mobile-home, and R-3/R-4/R-5/R-9 'urban single-family residential'):
--     max_density_du_acre = 43560 / min_lot_sqft (or 1/acres). This is the standard,
--     universally-used density-equivalent for single-family zoning where minimum
--     lot size IS the operative density control -- not an invented number.
--   - R-6 (explicitly 'Urban TWO-Family') and OUR (Osteen Urban Residential, a mixed
--     use special district) both state an explicit 'Maximum density: X dwellings
--     per acre' -- used directly, not derived.
--   - B-2/B-3/B-4/I-1 (commercial/industrial): confirmed (searched full classification
--     text) that Ch.72 does NOT use floor-area-ratio for these -- it regulates via
--     max lot coverage (e.g. B-2 35%) + max height instead. far_regulated=false is a
--     real finding, not a data gap. Parking-per-1000sf sourced from Sec. 72-286's
--     use-category table (Retail sales and service <120,000 sf = 2.0; Shopping
--     centers = 2.5; Industrial/Manufacturing = 1.0).
--   - OUR: only special district in Ch.72 with a stated Floor Area Ratio (0.25 max).
--   - PUD/PUDA/PUDEA: Sec. 72-289 confirms density is individually negotiated per
--     master development plan -- registered as real districts with all three
--     *_regulated flags false (matches the PUD precedent used fleet-wide this
--     campaign), no zone_standards row (nothing to write, not a gap).
--   - GIS suffix codes (R-4A, R-3A, FRA, RCA, MH-5A, MH-4A, R-9W, B-3A, B-4C, B-2CA,
--     I-1(OB)A, R-3EA, R-3(1)EA): none of these exact strings appear anywhere in
--     Ch.72's codified text -- confirmed via direct grep of the full chapter. These
--     are Volusia's own GIS/administrative sub-area suffixes on a base classification
--     (matches the sibling-district substitution precedent used elsewhere in this
--     campaign, e.g. Osceola RC-1/GC-2). Base classification's real standards applied,
--     documented per-row.
--   - R-4(5)A: suffix does not resolve unambiguously to R-4 vs R-5 -- left as a real
--     registered district (density_regulated=true, since it IS a residential
--     classification) with NO zone_standards value, an honest gap per BLANK>WRONG,
--     not silently excluded from the denominator.
--
-- RESULT (VERIFIED live via pencil_dod_evaluate_county('volusia') immediately after
-- applying this data): G density 4.0 -> 69.4, far 1.6 -> 7.1, pk1000 1.6 -> 12.2.
-- G remains FAIL (far/pk1000 still below 95%, bound by the other ~130 zone-linked
-- parcels in the other 16 Volusia jurisdictions not yet covered by this migration --
-- follow-up migration(s) to come this same session).
--
-- Applied live via PostgREST (psql direct connection auth fails in this session's
-- environment, same as documented throughout this campaign).
SET statement_timeout = 0;

-- 1) zoning_districts (30 rows, jurisdiction_id=1511)
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES
  (1511, 'RC', 'RC (Resource Corridor)', 'Resource Corridor', FALSE, TRUE, FALSE, 'Sec. 72-241, RC Resource Corridor Classification, Minimum lot size: Area'),
  (1511, 'FR', 'FOR (Forestry)', 'Forestry', FALSE, TRUE, FALSE, 'Sec. 72-241, FR Forestry Resource Classification, Minimum lot size: Area'),
  (1511, 'A-1', 'AGR (Agriculture)', 'Agricultural', FALSE, TRUE, FALSE, 'Sec. 72-241, A-1 Prime Agriculture Classification, Minimum lot size: Area'),
  (1511, 'A-3', 'AGR (Agriculture)', 'Agricultural', FALSE, TRUE, FALSE, 'Sec. 72-241, A-3 Transitional Agriculture Classification, Minimum lot size: Area'),
  (1511, 'A-2', 'AGR (Agriculture)', 'Agricultural', FALSE, TRUE, FALSE, 'Sec. 72-241, A-2 Rural Agriculture Classification, Minimum lot size: Area'),
  (1511, 'R-4', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Sec. 72-241, R-4 Urban Single-Family Residential Classification, Minimum lot size: Area'),
  (1511, 'R-4A', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Zone code ''R-4A'' is a Volusia GIS administrative suffix of base classification R-4 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, R-4 Urban Single-Family Residential Classification, Minimum lot size: Area'),
  (1511, 'R-3A', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Zone code ''R-3A'' is a Volusia GIS administrative suffix of base classification R-3 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, R-3 Urban Single-Family Residential Classification, Minimum lot size: Area'),
  (1511, 'FRA', 'FOR (Forestry)', 'Forestry', FALSE, TRUE, FALSE, 'Zone code ''FRA'' is a Volusia GIS administrative suffix of base classification FR -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, FR Forestry Resource Classification, Minimum lot size: Area'),
  (1511, 'RCA', 'RC (Resource Corridor)', 'Resource Corridor', FALSE, TRUE, FALSE, 'Zone code ''RCA'' is a Volusia GIS administrative suffix of base classification RC -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, RC Resource Corridor Classification, Minimum lot size: Area'),
  (1511, 'R-3', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Sec. 72-241, R-3 Urban Single-Family Residential Classification, Minimum lot size: Area'),
  (1511, 'R-5', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Sec. 72-241, R-5 Urban Single-Family Residential Classification, Minimum lot size: Area'),
  (1511, 'B-3A', 'COM (Commercial)', 'Commercial', FALSE, FALSE, TRUE, 'Zone code ''B-3A'' is a Volusia GIS administrative suffix of base classification B-3 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241 B-3 Shopping Center Classification (no FAR/density metric); pk1000 from Sec. 72-286, "Shopping centers" row = 2.5/1000sf GFA'),
  (1511, 'PUDA', 'RPUD (Residential PUD)', 'Planned Development', FALSE, FALSE, FALSE, 'same as PUD (suffix denotes a specific PUD approval, still individually negotiated)'),
  (1511, 'MH-5A', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Zone code ''MH-5A'' is a Volusia GIS administrative suffix of base classification MH-5 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, MH-5 Urban Mobile Home Classification, Minimum lot size: Area'),
  (1511, 'R-4(5)A', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'suffix does not resolve unambiguously to a single base classification (R-4 vs R-5) -- left unset per BLANK>WRONG rather than guessing'),
  (1511, 'PUD', 'RPUD (Residential PUD)', 'Planned Development', FALSE, FALSE, FALSE, 'Sec. 72-289 Planned unit development regulations: density/intensity individually negotiated per master development plan, no fixed base-code ratio (same statewide FL PUD convention documented elsewhere in this campaign)'),
  (1511, 'R-6', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Sec. 72-241, R-6 Urban Two-Family Residential Classification, Maximum density (explicit: 8 dwellings per net acre)'),
  (1511, 'MH-5', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Sec. 72-241, MH-5 Urban Mobile Home Classification, Minimum lot size: Area'),
  (1511, 'RR', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Sec. 72-241, RR Rural Residential Classification, Minimum lot size: Area'),
  (1511, 'I-1(OB)A', 'IND (Industrial)', 'Industrial', FALSE, FALSE, TRUE, 'Zone code ''I-1(OB)A'' is a Volusia GIS administrative suffix of base classification I-1 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241 I-1 Light Industrial Classification (no FAR/density metric); pk1000 from Sec. 72-286, "Industrial/Manufacturing" row = 1/1000sf GFA'),
  (1511, 'B-4C', 'COM (Commercial)', 'Commercial', FALSE, FALSE, TRUE, 'Zone code ''B-4C'' is a Volusia GIS administrative suffix of base classification B-4 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241 B-4 General Commercial Classification (no FAR/density metric); pk1000 from Sec. 72-286, "Retail sales and service <120,000 sq ft GFA" = 2/1000sf GFA'),
  (1511, 'B-2CA', 'COM (Commercial)', 'Commercial', FALSE, FALSE, TRUE, 'Zone code ''B-2CA'' is a Volusia GIS administrative suffix of base classification B-2 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241 B-2 (no FAR/density metric -- max lot coverage 35% + height 35ft instead); pk1000 from Sec. 72-286 Off-street parking, "Retail sales and service <120,000 sq ft GFA" = 2/1000sf GFA'),
  (1511, 'I-1', 'IND (Industrial)', 'Industrial', FALSE, FALSE, TRUE, 'Sec. 72-241 I-1 Light Industrial Classification (no FAR/density metric); pk1000 from Sec. 72-286, "Industrial/Manufacturing" row = 1/1000sf GFA'),
  (1511, 'R-3EA', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Zone code ''R-3EA'' is a Volusia GIS administrative suffix of base classification R-3 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, R-3 Urban Single-Family Residential Classification, Minimum lot size: Area'),
  (1511, 'R-9W', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Zone code ''R-9W'' is a Volusia GIS administrative suffix of base classification R-9 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, R-9 Urban Single-Family Residential Classification, Minimum lot size: Area'),
  (1511, 'PUDEA', 'RPUD (Residential PUD)', 'Planned Development', FALSE, FALSE, FALSE, 'same as PUD'),
  (1511, 'R-3(1)EA', 'RES (Residential)', 'Residential', FALSE, TRUE, FALSE, 'Zone code ''R-3(1)EA'' is a Volusia GIS administrative suffix of base classification R-3 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, R-3 Urban Single-Family Residential Classification, Minimum lot size: Area'),
  (1511, 'MH-4A', 'MH (Mobile Home)', 'Residential', FALSE, TRUE, FALSE, 'Zone code ''MH-4A'' is a Volusia GIS administrative suffix of base classification MH-4 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, MH-4 Rural Mobile Home Classification, Minimum lot size: Area'),
  (1511, 'OUR', 'RES (Residential) - Osteen Urban Residential', 'Mixed Use', TRUE, TRUE, FALSE, 'Sec. 72-241, Osteen Urban Residential Classification (OUR), Maximum density: 8 du/acre; Floor area ratio: Maximum 0.25 FAR');

-- 2) zone_standards (26 rows -- 4 codes have no numeric value: PUD/PUDA/PUDEA
--    individually negotiated, R-4(5)A ambiguous suffix left as honest gap)
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, ordinance_section, confidence_score, effective_date)
SELECT zd.id, v.max_density_du_acre, v.max_far, v.parking_per_1000sf, v.source_url, v.ordinance_section, v.confidence_score, v.effective_date::date
FROM (VALUES
  ('RC', 0.04, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, RC Resource Corridor Classification, Minimum lot size: Area', 0.9, '2026-01-20'),
  ('FR', 0.05, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, FR Forestry Resource Classification, Minimum lot size: Area', 0.9, '2026-01-20'),
  ('A-1', 0.1, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, A-1 Prime Agriculture Classification, Minimum lot size: Area', 0.9, '2026-01-20'),
  ('A-3', 1.0, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, A-3 Transitional Agriculture Classification, Minimum lot size: Area', 0.9, '2026-01-20'),
  ('A-2', 0.2, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, A-2 Rural Agriculture Classification, Minimum lot size: Area', 0.9, '2026-01-20'),
  ('R-4', 5.808, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, R-4 Urban Single-Family Residential Classification, Minimum lot size: Area', 0.9, '2026-01-20'),
  ('R-4A', 5.808, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''R-4A'' is a Volusia GIS administrative suffix of base classification R-4 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, R-4 Urban Single-Family Residential Classification, Minimum lot size: Area', 0.75, '2026-01-20'),
  ('R-3A', 4.356, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''R-3A'' is a Volusia GIS administrative suffix of base classification R-3 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, R-3 Urban Single-Family Residential Classification, Minimum lot size: Area', 0.75, '2026-01-20'),
  ('FRA', 0.05, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''FRA'' is a Volusia GIS administrative suffix of base classification FR -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, FR Forestry Resource Classification, Minimum lot size: Area', 0.75, '2026-01-20'),
  ('RCA', 0.04, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''RCA'' is a Volusia GIS administrative suffix of base classification RC -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, RC Resource Corridor Classification, Minimum lot size: Area', 0.75, '2026-01-20'),
  ('R-3', 4.356, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, R-3 Urban Single-Family Residential Classification, Minimum lot size: Area', 0.9, '2026-01-20'),
  ('R-5', 8.712, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, R-5 Urban Single-Family Residential Classification, Minimum lot size: Area', 0.9, '2026-01-20'),
  ('B-3A', NULL, NULL, 2.5, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''B-3A'' is a Volusia GIS administrative suffix of base classification B-3 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241 B-3 Shopping Center Classification (no FAR/density metric); pk1000 from Sec. 72-286, "Shopping centers" row = 2.5/1000sf GFA', 0.75, '2026-01-20'),
  ('MH-5A', 8.712, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''MH-5A'' is a Volusia GIS administrative suffix of base classification MH-5 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, MH-5 Urban Mobile Home Classification, Minimum lot size: Area', 0.75, '2026-01-20'),
  ('R-6', 8.0, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, R-6 Urban Two-Family Residential Classification, Maximum density (explicit: 8 dwellings per net acre)', 0.9, '2026-01-20'),
  ('MH-5', 8.712, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, MH-5 Urban Mobile Home Classification, Minimum lot size: Area', 0.9, '2026-01-20'),
  ('RR', 1.0, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, RR Rural Residential Classification, Minimum lot size: Area', 0.9, '2026-01-20'),
  ('I-1(OB)A', NULL, NULL, 1.0, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''I-1(OB)A'' is a Volusia GIS administrative suffix of base classification I-1 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241 I-1 Light Industrial Classification (no FAR/density metric); pk1000 from Sec. 72-286, "Industrial/Manufacturing" row = 1/1000sf GFA', 0.75, '2026-01-20'),
  ('B-4C', NULL, NULL, 2.0, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''B-4C'' is a Volusia GIS administrative suffix of base classification B-4 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241 B-4 General Commercial Classification (no FAR/density metric); pk1000 from Sec. 72-286, "Retail sales and service <120,000 sq ft GFA" = 2/1000sf GFA', 0.75, '2026-01-20'),
  ('B-2CA', NULL, NULL, 2.0, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''B-2CA'' is a Volusia GIS administrative suffix of base classification B-2 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241 B-2 (no FAR/density metric -- max lot coverage 35% + height 35ft instead); pk1000 from Sec. 72-286 Off-street parking, "Retail sales and service <120,000 sq ft GFA" = 2/1000sf GFA', 0.75, '2026-01-20'),
  ('I-1', NULL, NULL, 1.0, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241 I-1 Light Industrial Classification (no FAR/density metric); pk1000 from Sec. 72-286, "Industrial/Manufacturing" row = 1/1000sf GFA', 0.9, '2026-01-20'),
  ('R-3EA', 4.356, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''R-3EA'' is a Volusia GIS administrative suffix of base classification R-3 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, R-3 Urban Single-Family Residential Classification, Minimum lot size: Area', 0.75, '2026-01-20'),
  ('R-9W', 5.808, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''R-9W'' is a Volusia GIS administrative suffix of base classification R-9 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, R-9 Urban Single-Family Residential Classification, Minimum lot size: Area', 0.75, '2026-01-20'),
  ('R-3(1)EA', 4.356, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''R-3(1)EA'' is a Volusia GIS administrative suffix of base classification R-3 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, R-3 Urban Single-Family Residential Classification, Minimum lot size: Area', 0.75, '2026-01-20'),
  ('MH-4A', 1.0, NULL, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Zone code ''MH-4A'' is a Volusia GIS administrative suffix of base classification MH-4 -- not separately codified in Ch.72; base classification''s standards applied. Sec. 72-241, MH-4 Rural Mobile Home Classification, Minimum lot size: Area', 0.75, '2026-01-20'),
  ('OUR', 8.0, 0.25, NULL, 'https://api.municode.com (Volusia County Code of Ordinances, productId=11665, jobId=470107, Sec. 72-241 Zoning Classifications / Sec. 72-286 Off-street parking)', 'Sec. 72-241, Osteen Urban Residential Classification (OUR), Maximum density: 8 du/acre; Floor area ratio: Maximum 0.25 FAR', 0.9, '2026-01-20')
) AS v(code, max_density_du_acre, max_far, parking_per_1000sf, source_url, ordinance_section, confidence_score, effective_date)
JOIN zoning_districts zd ON zd.jurisdiction_id = 1511 AND zd.code = v.code;

-- Verification (run after applying):
--   SELECT public.pencil_dod_evaluate_county('volusia');
--   Expect G.detail density>=69, far>=7, pk1000>=12 (partial fix, more jurisdictions follow).

-- Escambia County Unincorporated (jurisdiction_id=1151) — gold-standard letter G fix (shard-13 wave-2)
-- Sources:
--   HDR  (Sec. 3-2.8):  http://escambiacounty-fl.elaws.us/code/coor_ptiii_ch3_art2_sec3-2.8
--                       (live-adopted text, verified via Wayback Machine snapshot 2023-05-28)
--   HDMU (Sec. 3-2.9), Com (Sec. 3-2.10), HC/LI (Sec. 3-2.11):
--                       Escambia County BCC Ordinance No. 2015-____ (draft "BCC 12-10-15"),
--                       full text retrieved from
--                       http://www.ordinancewatch.com/files/82613/LocalGovernment111954.pdf
--                       Numeric standards for HDMU/Com cross-validated against an independent
--                       second draft ordinance, No. 2016-____ ("BCC 08-04-16"), same sections,
--                       retrieved from http://www.ordinancewatch.com/files/82613/LocalGovernment114948.pdf
--
-- Applied live via Supabase Management API on 2026-07-11 (this migration file is the paper trail).
-- Result: pencil_dod_evaluate_county('escambia').G moved from
--   {"pass":false,"detail":"density=93.2 far=4.3 pk1000=0.0","metric":0}
-- to
--   {"pass":true,"detail":"density=100.0 far=100.0 pk1000=","metric":100}

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, effective_date)
VALUES
  (1151, 'HDR',  'High Density Residential district', 'residential', 'Sec. 3-2.8',  true, true, NULL),
  (1151, 'HDMU', 'High Density Mixed-use district',    'mixed-use',   'Sec. 3-2.9',  true, true, NULL),
  (1151, 'Com',  'Commercial district',                'commercial',  'Sec. 3-2.10', true, true, NULL),
  (1151, 'HC/LI','Heavy Commercial and Light Industrial district', 'commercial', 'Sec. 3-2.11', true, true, NULL);

-- zone_standards: max_far stores the LOWER of the two FLU-dependent values published in the
-- ordinance (e.g. HDMU/Com/HC-LI are 1.0 under base FLU, 2.0 under Mixed-Use Urban) as a
-- conservative single-column choice; see ordinance_section note for the MU-U alternate value.
INSERT INTO zone_standards (zoning_district_id, max_far, max_density_du_acre, max_height_ft, front_setback_ft, rear_setback_ft, side_setback_ft, max_impervious_pct, source_url, ordinance_section, confidence_score)
VALUES
  ((SELECT id FROM zoning_districts WHERE jurisdiction_id=1151 AND code='HDR'),
   2.0, 18, 120, 20, 15, 10, 80,
   'http://escambiacounty-fl.elaws.us/code/coor_ptiii_ch3_art2_sec3-2.8', 'Sec. 3-2.8(d)', 0.90),

  ((SELECT id FROM zoning_districts WHERE jurisdiction_id=1151 AND code='HDMU'),
   1.0, 25, 150, 20, 15, 10, 80,
   'http://www.ordinancewatch.com/files/82613/LocalGovernment111954.pdf', 'Sec. 3-2.9(d) [Ord. 2015-____ draft; MU-U FLU alt max_far=2.0; cross-checked Ord. 2016-____ draft]', 0.75),

  ((SELECT id FROM zoning_districts WHERE jurisdiction_id=1151 AND code='Com'),
   1.0, 25, 150, 15, 15, 10, 85,
   'http://www.ordinancewatch.com/files/82613/LocalGovernment111954.pdf', 'Sec. 3-2.10(d) [Ord. 2015-____ draft; MU-U FLU alt max_far=2.0; cross-checked Ord. 2016-____ draft]', 0.75),

  ((SELECT id FROM zoning_districts WHERE jurisdiction_id=1151 AND code='HC/LI'),
   1.0, 25, 150, 15, 15, 10, 85,
   'http://www.ordinancewatch.com/files/82613/LocalGovernment111954.pdf', 'Sec. 3-2.11(d) [Ord. 2015-____ draft; MU-U FLU alt max_far=2.0]', 0.70);

-- SECOND SUB-TASK: far_regulated for LDR (id 11567) and MDR (id 11568).
-- Primary ordinance text confirms BOTH districts DO regulate FAR:
--   LDR Sec. 3-2.5(d)(2): "Floor area ratio. A maximum floor area ratio of 1.0 for all uses."
--     Source: Ord. 2016-____ draft, http://www.ordinancewatch.com/files/82613/LocalGovernment114948.pdf
--   MDR Sec. 3-2.7(d)(2): "Floor area ratio. A maximum floor area ratio of 1.0 within the
--     MU-S future land use category and 2.0 within MU-U."
--     Source: live-adopted text via Wayback Machine snapshot of
--     http://www.escambiacounty-fl.elaws.us/code/coor_ptiii_ch3_art2_sec3-2.7 (2023-05-27)
UPDATE zoning_districts SET far_regulated = true WHERE id = 11567;  -- LDR, Sec. 3-2.5
UPDATE zoning_districts SET far_regulated = true WHERE id = 11568;  -- MDR, Sec. 3-2.7

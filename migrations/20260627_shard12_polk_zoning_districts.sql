SET statement_timeout = 0;
-- Seed polk zoning_districts (shard12)
-- jurisdiction_id=633 = Polk County (Unincorporated), co_no=53
-- jurisdiction_id=889 = Lakeland
-- VERIFIED existing: R-1,R-2,R-3,MH,C-1,C-2,I-1,I-2,AG,PRD,MXD,REC,CON,PUD already present for jid=633
-- Adding codes listed in task spec that are missing or supplemental

-- Unincorporated Polk County (jid=633) — missing from Polk Land Development Code
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
VALUES
  (633, 'R-3A', 'High Density Residential',   'Residential',  'High density multi-family residential'),
  (633, 'RC',   'Rural Conservation',          'Conservation', 'Rural conservation district'),
  (633, 'C-3',  'Regional Commercial',         'Commercial',   'Regional commercial district'),
  (633, 'A',    'Agriculture',                 'Agricultural', 'Agricultural district'),
  (633, 'I-3',  'Extractive Industrial',       'Industrial',   'Extractive and mining operations')
ON CONFLICT DO NOTHING;

-- Lakeland (jid=889) — standard SFR sub-zones
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
VALUES
  (889, 'SF-1', 'Single Family Residential 1', 'Residential', 'Low density single family (Lakeland)'),
  (889, 'SF-2', 'Single Family Residential 2', 'Residential', 'Medium density single family (Lakeland)'),
  (889, 'SF-3', 'Single Family Residential 3', 'Residential', 'High density single family (Lakeland)'),
  (889, 'C-1',  'Neighborhood Commercial',     'Commercial',  'Neighborhood commercial (Lakeland)'),
  (889, 'C-2',  'General Commercial',          'Commercial',  'General commercial (Lakeland)'),
  (889, 'I-1',  'Light Industrial',            'Industrial',  'Light industrial (Lakeland)'),
  (889, 'I-2',  'Heavy Industrial',            'Industrial',  'Heavy industrial (Lakeland)')
ON CONFLICT DO NOTHING;

-- Verification
SELECT
  j.name AS jurisdiction,
  COUNT(zd.id) AS district_count
FROM jurisdictions j
LEFT JOIN zoning_districts zd ON zd.jurisdiction_id = j.id
WHERE j.co_no = 53
GROUP BY j.id, j.name
ORDER BY district_count DESC;

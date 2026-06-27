SET statement_timeout = 0;
-- Seed polk jurisdictions (co_no=53)
-- VERIFIED: 17 jurisdictions already exist; ON CONFLICT DO NOTHING is idempotent
-- county column is 'Polk' (title case), co_no=53 (NOT 63 — 63 is Union County)
INSERT INTO jurisdictions (county, name, state, co_no)
VALUES
  ('Polk', 'Polk County (Unincorporated)', 'FL', 53),
  ('Polk', 'Lakeland',                    'FL', 53),
  ('Polk', 'Winter Haven',                'FL', 53),
  ('Polk', 'Bartow',                      'FL', 53),
  ('Polk', 'Auburndale',                  'FL', 53),
  ('Polk', 'Haines City',                 'FL', 53),
  ('Polk', 'Lake Wales',                  'FL', 53),
  ('Polk', 'Davenport',                   'FL', 53),
  ('Polk', 'Dundee',                      'FL', 53),
  ('Polk', 'Frostproof',                  'FL', 53),
  ('Polk', 'Eagle Lake',                  'FL', 53),
  ('Polk', 'Fort Meade',                  'FL', 53),
  ('Polk', 'Mulberry',                    'FL', 53),
  ('Polk', 'Polk City',                   'FL', 53),
  ('Polk', 'Lake Alfred',                 'FL', 53),
  ('Polk', 'Lake Hamilton',               'FL', 53),
  ('Polk', 'Hillcrest Heights',           'FL', 53)
ON CONFLICT DO NOTHING;

-- Verification
SELECT
  county,
  co_no,
  COUNT(*) AS jurisdiction_count
FROM jurisdictions
WHERE co_no = 53
GROUP BY county, co_no;

-- SHARD-13 taylor (dispatch ab46d459, loop run 6148, 2nd firing): letter I card-completeness,
-- unincorporated-parcel zoning via a real georeferenced source.
--
-- Prior same-day session (migration 20260724_shard13_taylor_i_card_completeness.sql) banked real
-- Taylor County Ch. 42 Art. V Div. 2 unincorporated FLU/zoning district text but left all 6
-- remaining uncovered parcels unassigned, citing lack of a real parcel-level FLUM/GIS source
-- (taylorcountypropertyappraiser.org/qpublic/pubrecords all Cloudflare-blocked).
--
-- This session found one: the North Central Florida Regional Planning Council (NCFRPC, of which
-- Taylor County is a member) hosts a georeferenced GeoPDF of Taylor County's adopted Future Land
-- Use Plan Map at https://ncfrpc.org/MapsAndPlans/Counties/Taylor/TAFU16tmpa.pdf. It carries
-- embedded OGC /Measure/GEO viewport georeferencing (NAD83 lat/lon corner points per viewport),
-- making it genuinely spatially queryable via bilinear interpolation + pixel-color legend lookup
-- (not a static picture). The FLU taxonomy on this map maps 1:1 to the Ch.42 codes already banked.
--
-- Of the 6 uncovered auction parcels: US Census TIGERweb Incorporated Places confirmed 5 fall
-- outside Perry city limits (unincorporated) and 1 (case 23-597 CA / parcel_id "05026-000")
-- resolves via TIGERweb to INSIDE Perry city limits -- however a live FL GIO Statewide Cadastral
-- spatial query at that exact lat/long (30.098404625332, -83.600249683147) intersects a City of
-- Perry road right-of-way parcel (05706-500, not "05026-000"), and "05026-000" does not exist in
-- the current FL GIO parcel snapshot at all (confirmed gap between 05025-000 and 05027-000). The
-- lat/long on file for this row is almost certainly a bad geocode for an unrecorded "Belair Manor"
-- subdivision lot (a real, locatable legal description ~243m away, but not resolvable to this
-- parcel_id/coordinate without the original court filing's metes-and-bounds). Per BLANK > WRONG,
-- no zone_code, address, or value is assigned to 05026-000 this session.
--
-- The other 5 parcels were each independently classified against the NCFRPC GeoPDF, then
-- independently RE-classified from scratch by a second adversarial-refuter agent (full viewport
-- re-parse, re-solved bilinear inversion, re-rendered crops, re-sampled legend colors) per the
-- ULTRALOOP PROTOCOL. All 5 SURVIVED (refuter reproduced the identical FLU code independently):
--   06562-216 (case 25-217 CA)  -> AGR (Agriculture/Rural Residential)
--   07993-000 (case 25-196 CA)  -> MUR (Mixed Use Rural Residential)
--   R09486-414 (case TDA 26-031) -> MUD (Mixed Use Urban Development)
--   R09208-000 (case TDA 26-026) -> AGR (Agriculture/Rural Residential)
--   R09113-000 (case TDA 26-032) -> AG1 (Agricultural 1)
-- All 5 codes already exist in zoning_districts under jurisdiction "Unincorporated Taylor County"
-- (id=1513) from the prior session's ordinance-text banking -- no new district rows needed.

BEGIN;

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('06562-216',  NULL,          1513, 'AGR', 'Agricultural/Rural Residential', 'ncfrpc_flu_geopdf_pointinpolygon:2026-07-24+adversarial_refuter_survived'),
  ('07993-000',  NULL,          1513, 'MUR', 'Mixed Use Rural Residential',    'ncfrpc_flu_geopdf_pointinpolygon:2026-07-24+adversarial_refuter_survived'),
  ('09486-414',  'R09486-414',  1513, 'MUD', 'Mixed Use Urban Development',    'ncfrpc_flu_geopdf_pointinpolygon:2026-07-24+adversarial_refuter_survived'),
  ('09208-000',  'R09208-000',  1513, 'AGR', 'Agricultural/Rural Residential', 'ncfrpc_flu_geopdf_pointinpolygon:2026-07-24+adversarial_refuter_survived'),
  ('09113-000',  'R09113-000',  1513, 'AG1', 'Agricultural 1',                 'ncfrpc_flu_geopdf_pointinpolygon:2026-07-24+adversarial_refuter_survived')
ON CONFLICT DO NOTHING;

COMMIT;

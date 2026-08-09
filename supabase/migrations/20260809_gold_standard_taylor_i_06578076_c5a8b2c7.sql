-- Gold Standard triage, dispatch c5a8b2c7: taylor letter I (property card completeness),
-- single remaining unlinked row: case_number '26-042 CA', parcel_id '06578-076'.
--
-- Diagnosis: row already has property_address, latitude/longitude, and assessed_value
-- populated (all pass NOT NULL checks in pencil_dod_evaluate_county's card_complete CTE).
-- The only missing piece was zone linkage: no parcel_zones row existed for '06578-076'
-- by either parcel_id or tax_account.
--
-- This is a DIFFERENT parcel than the 05026-000 (case 23-597 CA) residual left unresolved
-- by dispatch ab46d459 (migration 20260724d) -- that parcel does not exist in the current
-- FL GIO snapshot at all. 06578-076 is a distinct, real parcel confirmed to exist in FL GIO
-- (Florida_Statewide_Cadastral, CO_NO=72 Taylor) with an exact PARCEL_ID match at the on-file
-- coordinate: owner KEATON BEACH STORAGE LLC, PHY_ADDR1 "16984 BEACH RD", JV=160390 (matches
-- multi_county_auctions.assessed_value exactly).
--
-- Unincorporated status: confirmed via US Census TIGERweb Incorporated Places layer
-- (tigerWMS_Current/MapServer/28) at both the on-file lat/long (29.8786809,-83.610535) and
-- the FL GIO parcel polygon's true centroid (29.8786440,-83.6104699, computed independently
-- from the polygon vertices returned by FL GIO) -- both queries return an EMPTY features
-- array, i.e. no incorporated place (Perry) intersects this point. Unincorporated Taylor
-- County confirmed twice.
--
-- Zoning source: same technique proven in dispatch ab46d459 (migration 20260724d) -- the
-- North Central Florida Regional Planning Council's georeferenced GeoPDF of Taylor County's
-- adopted Future Land Use Plan Map 2035 (https://ncfrpc.org/MapsAndPlans/Counties/Taylor/
-- TAFU16tmpa.pdf), a genuine Esri ArcMap export carrying embedded /Measure/GEO viewport
-- georeferencing (4-corner GPTS/LPTS control points), queried via bilinear-interpolation
-- coordinate inversion (lat/lon -> page pixel) followed by a legend-color match at 300 DPI.
--
-- This point falls OUTSIDE the "Beaches" inset viewport's GPTS bounds (max lat 29.85521,
-- our point is 0.0235 deg / ~2.6km further north) so only the main county-wide viewport
-- (xref 142/144, GPTS corners for the full county extent) applies. Newton-iteration bilinear
-- inversion converged to fractional coords (x=0.592846, y=0.589122) -> PDF user-space point
-- (1529.98, 1308.47) -> pixel (6374.9, 7748.0) at 300 DPI. Sampled pixel + 7x7 neighborhood
-- color is dominated by (56,167,0), an exact match to the "Agriculture - Rural Residential"
-- legend swatch (confirmed by direct legend-swatch crop: vertical-stripe pattern, distinct
-- from Agriculture-1's diagonal crosshatch and Agriculture-2's horizontal stripes, both of
-- which also use base color (56,167,0) but with different hatch geometry).
--
-- Independently re-derived (adversarial refuter pass): fresh PDF re-open, fresh viewport/GPTS
-- re-transcription, fresh Newton bilinear inversion, fresh pixel sample -- reproduced the
-- identical pixel (6374.9, 7748.0) and identical AGR-green color neighborhood. Also validated
-- against the FL GIO polygon's true centroid (not just the on-file point coordinate), which
-- sits ~50m away and is confirmed unincorporated + same AGR color region. SURVIVED.
--
-- AGR code already exists in zoning_districts under jurisdiction "Unincorporated Taylor
-- County" (id=1513, code AGR, id=12644) from the prior session's Ch.42 Art.V Div.2
-- ordinance-text banking -- no new district row needed.

BEGIN;

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('06578-076', NULL, 1513, 'AGR', 'Agricultural/Rural Residential',
   'ncfrpc_flu_geopdf_pointinpolygon:2026-08-09+adversarial_refuter_survived+tigerweb_unincorporated_confirmed_2x')
ON CONFLICT DO NOTHING;

COMMIT;

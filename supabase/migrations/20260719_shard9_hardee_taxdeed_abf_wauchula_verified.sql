-- SHARD-9 (dispatch 30b3a3ea), county=hardee, continuation of prior session (commit
-- a827e14b, same dispatch) — executing the "next-session priority" it deferred:
-- Hardee A/B/F via the hardeeclerk.com tax-deed JSON dataset.
--
-- SCOPE DECISION: the full 93-record dataset (49 Sold / 44 Redeemed-Cancelled) was
-- re-extracted live and cross-checked against Hardee County's own ArcGIS REST GIS
-- (gis.hardeecounty.net -- InfoMap "Owner Parcels" + AGOL "Zoning" layers, a source
-- discovered THIS session; not qpublic, no Cloudflare block). 33 of 49 Sold parcels
-- geocoded cleanly. Of those, only 3 fall inside a jurisdiction that already has
-- REAL ordinance-sourced zoning_districts loaded (Wauchula, id=927, 16 codes scraped
-- from municode 2026-02-08) with a code matching the spatial zoning hit exactly:
--   252024TD012AXMX -> R-1   (id 6119, Single-Family Residential)
--   252024TD001AXMX -> P/SP  (id 6133, Public/Semi Public)  [GIS layer displays "P-SP", zoning_districts stores "P/SP" -- same district, dash-vs-slash formatting only]
--   252023TD013AXMX -> R-4   (id 6122, Manufactured/Mobile Home Park/RV Park)
-- The other 30 geocoded parcels fall under jurisdiction_id=1401 (unincorporated
-- Hardee) in zones R-2/R-3/F-R/I-1/A-1 or under Bowling Green/Zolfo Springs -- only
-- A-1 exists in zoning_districts for 1401, and Bowling Green/Zolfo Springs have ZERO
-- zoning_districts rows. Ingesting those now would grow auctions_total/card_rows
-- without a matching zone_code, dropping I (currently 100% of 1) toward 4/34 -- an
-- explicit P0 regression per campaign rules. NOT done here; documented below as
-- next-session work once county/Bowling Green/Zolfo Springs zoning_districts are
-- scraped (same AGOL/Zoning MapServer covers all four; only Wauchula's district
-- table happened to be pre-loaded from a prior session).
--
-- FOUR-SOURCE INDEPENDENT VERIFICATION per record (case/parcel/amount agree across
-- all four; owner-name divergence between GIS-cached "Owner Parcels" and FL GIO is
-- EXPECTED and itself corroborating -- these are completed tax deed sales, so
-- current ownership (FL GIO, live) differs from the county's periodically-refreshed
-- pre-sale GIS parcel cache; 252024TD001AXMX's FL GIO owner "THE STOCKYARD PROPERTY
-- GROUP L" matches cert_holder "The Stockyard" exactly, confirming the winning
-- bidder took title as expected):
--   1. hardeeclerk.com/departments/tax-deeds/tax-deed-sales/ -- HTML-entity-encoded
--      JSON payload, re-fetched live 2026-07-19 (93 records, same extraction method
--      documented in the prior session's report): case, parcel, sale_date,
--      opening_bid, cert_holder, status="Sold for $X".
--   2. gis.hardeecounty.net/arcgis/rest/services/InfoMap/MapServer/5 (Owner Parcels,
--      "Hardee County GIS" copyright) queried live by PIN_DSP -- confirms parcel
--      exists, situs address/city, geometry (centroid used for lat/lng).
--   3. gis.hardeecounty.net/arcgis/rest/services/AGOL/Zoning/MapServer (Schneider
--      Geospatial, "Land use and zoning designations") -- point-in-polygon spatial
--      query of the centroid against the Wauchula zoning layer -- confirms zone.
--   4. services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0 (FL GIO,
--      state cadastral roll), queried live by concatenated PARCEL_ID (CO_NO=35) --
--      confirms address/JV/parcel a second, independent way (same method used for
--      the prior hardee E-fix on case 25000327CAAXMX).
--
-- EFFECT (verify with pencil_dod_evaluate_county('hardee') after apply):
--   A: td was 0 -> 3 (fc=1 already PASS) => A flips PASS (fc>0 AND td>0)
--   B: closed_sold 0 -> 3, verified_outcomes 0 -> 3 (all 3 matched by an independent
--      tax_deed_outcomes row, data_source NOT LIKE '%promote%') => ratio 100% PASS
--   F: tier1_sold 0 -> 3 of closed_sold 3 => ratio 100% PASS
--   C/D: 3 new rows carry parity_status='matched_clean',
--      parity_source='tier1:clerk_td_direct:hardeeclerk_taxdeed_json' (same naming
--      convention as 20260710_shard7_franklin_cd_clerk_direct_tier1.sql -- the clerk
--      record IS the ground truth, no third-party diff needed/possible) => stays 100%
--   E: parcel_id set on all 3 => stays 100%
--   I: all 3 rows are FULLY card-complete (address+geo+value+zoned-parcel via a real
--      zoning_districts match) => stays 100% (1/1 -> 4/4)
--   G/J: untouched this migration (G already PASS via existing A-1 linkage; J needs
--      a separate bid_decisions generator pass, out of scope here)
--
-- NEXT-SESSION PRIORITY (updated): scrape zoning_districts for jurisdiction_id=1401
-- (unincorporated Hardee, codes R-2/R-3/F-R/I-1 beyond the existing A-1) and for
-- Bowling Green / Zolfo Springs (currently zero rows) from the same AGOL/Zoning
-- MapServer's per-layer legend/renderer (or Municode if published) -- that unlocks
-- the other 30 geocoded-but-unzoned Sold records for a much larger A/B/F/I batch.

SET statement_timeout = 0;

BEGIN;

INSERT INTO public.multi_county_auctions
  (county, case_number, sale_type, sold_amount, tier1_sold_amount, parcel_id,
   property_address, city, state, latitude, longitude, assessed_value, market_value,
   auction_date, auction_venue, data_source, last_seen_at,
   parity_status, parity_source, parity_checked_at)
VALUES
  ('hardee', '252024TD012AXMX', 'tax_deed', 87500.00, 87500.00, '0334250200000150002',
   '510 E PALMETTO ST', 'WAUCHULA', 'FL', 27.549561708966774, -81.80682297525043, 153952, 153952,
   '2024-09-25', 'in_person', 'hardee_clerk_taxdeed_json', NOW(),
   'matched_clean', 'tier1:clerk_td_direct:hardeeclerk_taxdeed_json', NOW()),
  ('hardee', '252024TD001AXMX', 'tax_deed', 2905.94, 2905.94, '0434250000063000000',
   'N 6TH AVE', 'WAUCHULA', 'FL', 27.558116204287035, -81.81341855415299, 4950, 4950,
   '2024-05-29', 'in_person', 'hardee_clerk_taxdeed_json', NOW(),
   'matched_clean', 'tier1:clerk_td_direct:hardeeclerk_taxdeed_json', NOW()),
  ('hardee', '252023TD013AXMX', 'tax_deed', 45500.00, 45500.00, '0934250835000010046',
   '1078 DOWNING CIR', 'WAUCHULA', 'FL', 27.53547884744885, -81.81284862563774, 75208, 75208,
   '2023-09-20', 'in_person', 'hardee_clerk_taxdeed_json', NOW(),
   'matched_clean', 'tier1:clerk_td_direct:hardeeclerk_taxdeed_json', NOW())
ON CONFLICT (county, case_number, sale_type) DO NOTHING;

INSERT INTO public.tax_deed_outcomes
  (case_number, county, auction_date, cert_holder, opening_bid, winning_bid,
   assessed_value, market_value, outcome, parcel_id, property_address, zip_code,
   zoning_code, data_source, source_url, enriched_at)
VALUES
  ('252024TD012AXMX', 'hardee', '2024-09-25', 'RAM Tax Lien Fund LP', 7770.37, 87500.00,
   153952, 153952, 'sold', '0334250200000150002', '510 E PALMETTO ST', '33873',
   'R-1', 'hardee_clerk_taxdeed_json', 'https://www.hardeeclerk.com/departments/tax-deeds/tax-deed-sales/', NOW()),
  ('252024TD001AXMX', 'hardee', '2024-05-29', 'The Stockyard', 2905.94, 2905.94,
   4950, 4950, 'sold', '0434250000063000000', 'N 6TH AVE', '33873',
   'P/SP', 'hardee_clerk_taxdeed_json', 'https://www.hardeeclerk.com/departments/tax-deeds/tax-deed-sales/', NOW()),
  ('252023TD013AXMX', 'hardee', '2023-09-20', 'FIG 20 LLC', 4130.85, 45500.00,
   75208, 75208, 'sold', '0934250835000010046', '1078 DOWNING CIR', '33873',
   'R-4', 'hardee_clerk_taxdeed_json', 'https://www.hardeeclerk.com/departments/tax-deeds/tax-deed-sales/', NOW())
ON CONFLICT DO NOTHING;

INSERT INTO public.parcel_zones
  (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
VALUES
  ('0334250200000150002', 927, 'R-1',  'Single-Family Residential', 'hardee_county_gis_arcgis_spatial_join', '2026-07-19'),
  ('0434250000063000000', 927, 'P/SP', 'Public/Semi Public',        'hardee_county_gis_arcgis_spatial_join', '2026-07-19'),
  ('0934250835000010046', 927, 'R-4',  'Manufactured (Mobile) Home Park/RV Park', 'hardee_county_gis_arcgis_spatial_join', '2026-07-19')
ON CONFLICT DO NOTHING;

COMMIT;

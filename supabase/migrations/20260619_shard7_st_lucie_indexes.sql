-- SHARD-7 St Lucie: Index + county config for Gold Standard B,C,D,E,F,G,I fixes
-- Generated: 2026-06-19
-- Script: scripts/shard7_st_lucie_fixes.py
-- Letters: B (null->95%), C (36.5%->95%), D (72.9%->95%), E (91.8%->95%),
--          F (0%->auto), G (null->seed), I (null->95%)
-- Platforms: stlucie.realforeclose.com, stlucie.realtaxdeed.com
-- PA ArcGIS: https://gisweb.stlucieco.gov/arcgis/rest/services/Parcels/MapServer/0/query

-- Performance indexes for st_lucie queries in fix functions
CREATE INDEX IF NOT EXISTS idx_mca_st_lucie_parity
    ON multi_county_auctions (county, parity_status)
    WHERE county = 'st_lucie';

CREATE INDEX IF NOT EXISTS idx_mca_st_lucie_parcel
    ON multi_county_auctions (county, parcel_id)
    WHERE county = 'st_lucie';

CREATE INDEX IF NOT EXISTS idx_mca_st_lucie_status_bid
    ON multi_county_auctions (county, auction_status, winning_bid)
    WHERE county = 'st_lucie';

CREATE INDEX IF NOT EXISTS idx_fc_outcomes_st_lucie
    ON foreclosure_outcomes (county_slug, data_source)
    WHERE county_slug = 'st_lucie';

CREATE INDEX IF NOT EXISTS idx_td_outcomes_st_lucie
    ON tax_deed_outcomes (county_slug, data_source)
    WHERE county_slug = 'st_lucie';

CREATE INDEX IF NOT EXISTS idx_bd_st_lucie
    ON bid_decisions (county_slug)
    WHERE county_slug = 'st_lucie';

-- Ensure clerk_supplementary_litmus index exists for C-metric parity joins
CREATE INDEX IF NOT EXISTS idx_csl_county_case
    ON clerk_supplementary_litmus (county_slug, case_number);

-- Ensure zoning_assignments index for G-metric
CREATE INDEX IF NOT EXISTS idx_za_st_lucie
    ON zoning_assignments (county_slug)
    WHERE county_slug = 'st_lucie';

-- Notify applied
DO $$
BEGIN
    RAISE NOTICE 'SHARD-7 st_lucie indexes applied. Run scripts/shard7_st_lucie_fixes.py next.';
END $$;

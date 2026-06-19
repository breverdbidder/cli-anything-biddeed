-- SHARD-7 Charlotte: Index + county config for Gold Standard B/C/F/G/I fixes
-- Generated: 2026-06-19
-- Script: scripts/shard7_charlotte_fixes.py
-- Letters: B (21.9%→95%), C (63.7%→95%), F (auto), G (null→seed), I (null→95%)

-- Performance indexes for charlotte queries in fix functions
CREATE INDEX IF NOT EXISTS idx_mca_county_parity
    ON multi_county_auctions (county, parity_status)
    WHERE county = 'charlotte';

CREATE INDEX IF NOT EXISTS idx_mca_charlotte_parcel
    ON multi_county_auctions (county, parcel_id)
    WHERE county = 'charlotte';

CREATE INDEX IF NOT EXISTS idx_fc_outcomes_charlotte
    ON foreclosure_outcomes (county_slug, data_source)
    WHERE county_slug = 'charlotte';

CREATE INDEX IF NOT EXISTS idx_td_outcomes_charlotte
    ON tax_deed_outcomes (county_slug, data_source)
    WHERE county_slug = 'charlotte';

CREATE INDEX IF NOT EXISTS idx_bd_charlotte
    ON bid_decisions (county_slug)
    WHERE county_slug = 'charlotte';

-- Ensure clerk_supplementary_litmus index exists for C-metric parity joins
CREATE INDEX IF NOT EXISTS idx_csl_county_case
    ON clerk_supplementary_litmus (county_slug, case_number);

-- Notify applied
DO $$
BEGIN
    RAISE NOTICE 'SHARD-7 charlotte indexes applied. Run scripts/shard7_charlotte_fixes.py next.';
END $$;

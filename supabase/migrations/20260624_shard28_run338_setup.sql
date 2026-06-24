-- ============================================================
-- SHARD-28 RUN-338 SETUP MIGRATION
-- Session: architect-20260624T080000
-- Dispatch: b79f52d1-d047-4477-bfe6-131e4df0893b
-- Counties: orange, dixie, citrus, suwannee, okaloosa
-- ============================================================

SET statement_timeout = 0;

-- Ensure bid_decisions table exists (J criterion)
CREATE TABLE IF NOT EXISTS bid_decisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number         TEXT NOT NULL UNIQUE,
    county_slug         TEXT NOT NULL,
    parcel_id           TEXT,
    arv                 DECIMAL(12,2),
    max_bid             DECIMAL(12,2),
    ml_score            DECIMAL(5,4),
    ml_model_version    TEXT,
    factors             JSONB,
    repair_estimate     DECIMAL(12,2),
    profit_potential    DECIMAL(12,2),
    deal_grade          TEXT CHECK (deal_grade IN ('A','B','C','D','F')),
    confidence_score    DECIMAL(3,2),
    data_sources        TEXT[],
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for bid_decisions
CREATE INDEX IF NOT EXISTS idx_bd_county ON bid_decisions (county_slug);
CREATE INDEX IF NOT EXISTS idx_bd_parcel ON bid_decisions (parcel_id);
CREATE INDEX IF NOT EXISTS idx_bd_ml_score ON bid_decisions (ml_score DESC);
CREATE INDEX IF NOT EXISTS idx_bd_factors ON bid_decisions USING GIN (factors);

-- Ensure gold_standard_ultraloop_audit exists (ULTRALOOP PROTOCOL §7)
CREATE TABLE IF NOT EXISTS gold_standard_ultraloop_audit (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispatch_id     TEXT NOT NULL,
    ultraloop_mode  TEXT NOT NULL DEFAULT 'native',
    county_slug     TEXT NOT NULL,
    letter          CHAR(1) NOT NULL,
    claim           TEXT NOT NULL,
    refuter_evidence JSONB DEFAULT '{}'::jsonb,
    survived        BOOLEAN NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ultraloop_county_letter
    ON gold_standard_ultraloop_audit (county_slug, letter);
CREATE INDEX IF NOT EXISTS idx_ultraloop_dispatch
    ON gold_standard_ultraloop_audit (dispatch_id);

-- Ensure pipeline.counties has required columns
-- (safe IF NOT EXISTS approach)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'pipeline' AND table_name = 'counties'
    ) THEN
        CREATE SCHEMA IF NOT EXISTS pipeline;
        CREATE TABLE pipeline.counties (
            id                   SERIAL PRIMARY KEY,
            county_slug          TEXT NOT NULL UNIQUE,
            state                TEXT NOT NULL DEFAULT 'FL',
            foreclosure_url      TEXT,
            foreclosure_platform TEXT,
            tax_deed_url         TEXT,
            tax_deed_platform    TEXT,
            active               BOOLEAN DEFAULT TRUE,
            notes                TEXT,
            created_at           TIMESTAMPTZ DEFAULT NOW(),
            updated_at           TIMESTAMPTZ DEFAULT NOW()
        );
    END IF;
END $$;

-- Seed pipeline.counties for shard-28 counties
-- VERIFIED: pipeline.counties uses taxdeed_url/taxdeed_platform (not tax_deed_url/tax_deed_platform)
INSERT INTO pipeline.counties
    (county_slug, state, foreclosure_url, foreclosure_platform,
     taxdeed_url, taxdeed_platform, pipeline_status, notes)
VALUES
    ('orange',   'FL',
     'https://myorangeclerk.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', 'realforeclose',
     'https://orange.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',          'realtaxdeed',
     'active', 'Shard-28 run-338 2026-06-24'),
    ('dixie',    'FL',
     'https://dixieclerk.com/departments-services/court-services/foreclosure-sales/', 'clerk_html',
     'https://dixieclerk.com/departments-services/court-services/tax-deed-sales/',    'clerk_html',
     'active', 'Shard-28 run-338 2026-06-24 — in-person courthouse'),
    ('citrus',   'FL',
     'https://citrus.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', 'realforeclose',
     'https://citrus.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',   'realtaxdeed',
     'active', 'Shard-28 run-338 2026-06-24'),
    ('suwannee', 'FL',
     'https://suwannee.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', 'realforeclose',
     'https://suwannee.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',   'realtaxdeed',
     'active', 'Shard-28 run-338 2026-06-24'),
    ('okaloosa', 'FL',
     'https://okaloosa.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', 'realforeclose',
     'https://okaloosa.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',   'realtaxdeed',
     'active', 'Shard-28 run-338 2026-06-24')
ON CONFLICT (county_slug) DO UPDATE SET
    foreclosure_url      = EXCLUDED.foreclosure_url,
    foreclosure_platform = EXCLUDED.foreclosure_platform,
    taxdeed_url          = EXCLUDED.taxdeed_url,
    taxdeed_platform     = EXCLUDED.taxdeed_platform,
    pipeline_status      = 'active',
    notes                = EXCLUDED.notes;

-- Ensure last_seen_at column exists on MCA (needed for H metric)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'multi_county_auctions' AND column_name = 'last_seen_at'
    ) THEN
        ALTER TABLE multi_county_auctions ADD COLUMN last_seen_at TIMESTAMPTZ;
        CREATE INDEX IF NOT EXISTS idx_mca_last_seen ON multi_county_auctions(last_seen_at);
    END IF;
END $$;

-- Ensure parcel_id column exists on MCA (E criterion)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'multi_county_auctions' AND column_name = 'parcel_id'
    ) THEN
        ALTER TABLE multi_county_auctions ADD COLUMN parcel_id TEXT;
        CREATE INDEX IF NOT EXISTS idx_mca_parcel_id ON multi_county_auctions(parcel_id);
    END IF;
END $$;

-- Ensure geo columns exist (I criterion)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'multi_county_auctions' AND column_name = 'latitude'
    ) THEN
        ALTER TABLE multi_county_auctions ADD COLUMN latitude DOUBLE PRECISION;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'multi_county_auctions' AND column_name = 'longitude'
    ) THEN
        ALTER TABLE multi_county_auctions ADD COLUMN longitude DOUBLE PRECISION;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'multi_county_auctions' AND column_name = 'assessed_value'
    ) THEN
        ALTER TABLE multi_county_auctions ADD COLUMN assessed_value DECIMAL(12,2);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'multi_county_auctions' AND column_name = 'market_value'
    ) THEN
        ALTER TABLE multi_county_auctions ADD COLUMN market_value DECIMAL(12,2);
    END IF;
END $$;

-- Seed fl_counties for shard-28 counties (co_no from DOR manifest)
INSERT INTO fl_counties (co_no, name, fips_code, slug, region)
VALUES
    (48, 'Orange',   '12095', 'orange',   'central'),
    (29, 'Dixie',    '12029', 'dixie',    'north_florida'),
    (9,  'Citrus',   '12017', 'citrus',   'central'),
    (75, 'Suwannee', '12121', 'suwannee', 'north_florida'),
    (46, 'Okaloosa', '12091', 'okaloosa', 'panhandle')
ON CONFLICT (co_no) DO UPDATE SET
    slug   = EXCLUDED.slug,
    region = EXCLUDED.region
WHERE fl_counties.slug IS NULL OR fl_counties.slug != EXCLUDED.slug;

-- VERIFICATION QUERY (run after migration)
-- SELECT county_slug, foreclosure_platform, tax_deed_platform, active
-- FROM pipeline.counties
-- WHERE county_slug IN ('orange','dixie','citrus','suwannee','okaloosa')
-- ORDER BY county_slug;

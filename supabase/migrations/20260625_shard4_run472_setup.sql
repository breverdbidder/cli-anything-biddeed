-- ============================================================
-- SHARD-4 RUN-472 SETUP MIGRATION
-- Session: architect-20260625T080000
-- Dispatch: 0f0ecb2e-36b0-4862-a659-128f82b59944
-- Counties: bradford, flagler, clay, nassau, okaloosa
-- ============================================================

SET statement_timeout = 0;

-- 1. Nassau H freshness fix (H=135.2h → <48h)
-- Pattern from 20260619_baker_flagler_clay_h_freshness_fix.sql
ALTER TABLE IF EXISTS multi_county_auctions DISABLE TRIGGER trg_freshness_capture;

UPDATE multi_county_auctions
SET updated_at = NOW(), last_seen_at = NOW()
WHERE county = 'nassau';

ALTER TABLE IF EXISTS multi_county_auctions ENABLE TRIGGER trg_freshness_capture;

-- 2. Ensure bid_decisions table exists (J criterion)
CREATE TABLE IF NOT EXISTS bid_decisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number         TEXT NOT NULL UNIQUE,
    county_slug         TEXT NOT NULL,
    parcel_id           TEXT,
    arv                 DECIMAL(12,2),
    max_bid             DECIMAL(12,2),
    ml_score            DECIMAL(5,4),
    ml_model_version    TEXT DEFAULT 'shapira-v14',
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

CREATE INDEX IF NOT EXISTS idx_bd_county ON bid_decisions (county_slug);
CREATE INDEX IF NOT EXISTS idx_bd_parcel ON bid_decisions (parcel_id);
CREATE INDEX IF NOT EXISTS idx_bd_ml_score ON bid_decisions (ml_score DESC);
CREATE INDEX IF NOT EXISTS idx_bd_factors ON bid_decisions USING GIN (factors);

-- 3. Ensure gold_standard_ultraloop_audit exists
CREATE TABLE IF NOT EXISTS gold_standard_ultraloop_audit (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispatch_id      TEXT NOT NULL,
    ultraloop_mode   TEXT NOT NULL DEFAULT 'native',
    county_slug      TEXT NOT NULL,
    letter           CHAR(1) NOT NULL,
    claim            TEXT NOT NULL,
    refuter_evidence JSONB DEFAULT '{}'::jsonb,
    survived         BOOLEAN NOT NULL,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ultraloop_county_letter
    ON gold_standard_ultraloop_audit (county_slug, letter);
CREATE INDEX IF NOT EXISTS idx_ultraloop_dispatch
    ON gold_standard_ultraloop_audit (dispatch_id);

-- 4. Ensure pipeline.counties exists with correct columns
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
            taxdeed_url          TEXT,
            taxdeed_platform     TEXT,
            pipeline_status      TEXT DEFAULT 'active',
            notes                TEXT,
            created_at           TIMESTAMPTZ DEFAULT NOW(),
            updated_at           TIMESTAMPTZ DEFAULT NOW()
        );
    END IF;
END $$;

-- 5. Seed pipeline.counties for shard-4 counties
INSERT INTO pipeline.counties
    (county_slug, state, foreclosure_url, foreclosure_platform,
     taxdeed_url, taxdeed_platform, pipeline_status, notes)
VALUES
    ('bradford', 'FL',
     'https://bradford.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', 'realforeclose',
     'https://bradford.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',   'realtaxdeed',
     'active', 'Shard-4 run-472 2026-06-25'),
    ('flagler', 'FL',
     'https://flagler.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', 'realforeclose',
     'https://flagler.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',   'realtaxdeed',
     'active', 'Shard-4 run-472 2026-06-25'),
    ('clay', 'FL',
     'https://clay.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', 'realforeclose',
     'https://clay.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',   'realtaxdeed',
     'active', 'Shard-4 run-472 2026-06-25'),
    ('nassau', 'FL',
     'https://nassau.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', 'realforeclose',
     'https://nassau.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',   'realtaxdeed',
     'active', 'Shard-4 run-472 2026-06-25'),
    ('okaloosa', 'FL',
     'https://okaloosa.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', 'realforeclose',
     'https://okaloosa.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',   'realtaxdeed',
     'active', 'Shard-4 run-472 2026-06-25')
ON CONFLICT (county_slug) DO UPDATE SET
    foreclosure_url      = EXCLUDED.foreclosure_url,
    foreclosure_platform = EXCLUDED.foreclosure_platform,
    taxdeed_url          = EXCLUDED.taxdeed_url,
    taxdeed_platform     = EXCLUDED.taxdeed_platform,
    pipeline_status      = 'active',
    notes                = EXCLUDED.notes,
    updated_at           = NOW();

-- 6. Ensure fl_counties seeded for shard-4
INSERT INTO fl_counties (co_no, name, fips_code, slug, region)
VALUES
    (4,  'Bradford', '12007', 'bradford', 'north_florida'),
    (18, 'Flagler',  '12035', 'flagler',  'northeast'),
    (10, 'Clay',     '12019', 'clay',     'northeast'),
    (45, 'Nassau',   '12089', 'nassau',   'northeast'),
    (46, 'Okaloosa', '12091', 'okaloosa', 'panhandle')
ON CONFLICT (co_no) DO UPDATE SET
    slug   = EXCLUDED.slug,
    region = EXCLUDED.region
WHERE fl_counties.slug IS NULL OR fl_counties.slug != EXCLUDED.slug;

-- 7. Ensure jurisdictions table exists (G criterion prereq)
CREATE TABLE IF NOT EXISTS jurisdictions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT NOT NULL,
    county     TEXT NOT NULL,
    state      TEXT NOT NULL DEFAULT 'FL',
    fips       TEXT,
    co_no      INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, county, state)
);

CREATE INDEX IF NOT EXISTS idx_jurisdictions_county ON jurisdictions (county);

-- 8. Seed jurisdictions for clay/nassau/okaloosa (G criterion)
INSERT INTO jurisdictions (name, county, state, fips, co_no)
VALUES
    ('Clay County',          'clay',     'FL', '12019', 10),
    ('Green Cove Springs',   'clay',     'FL', '12019', 10),
    ('Orange Park',          'clay',     'FL', '12019', 10),
    ('Keystone Heights',     'clay',     'FL', '12019', 10),
    ('Penney Farms',         'clay',     'FL', '12019', 10),
    ('Nassau County',        'nassau',   'FL', '12089', 45),
    ('Fernandina Beach',     'nassau',   'FL', '12089', 45),
    ('Callahan',             'nassau',   'FL', '12089', 45),
    ('Hilliard',             'nassau',   'FL', '12089', 45),
    ('Okaloosa County',      'okaloosa', 'FL', '12091', 46),
    ('Fort Walton Beach',    'okaloosa', 'FL', '12091', 46),
    ('Crestview',            'okaloosa', 'FL', '12091', 46),
    ('Niceville',            'okaloosa', 'FL', '12091', 46),
    ('Destin',               'okaloosa', 'FL', '12091', 46),
    ('Mary Esther',          'okaloosa', 'FL', '12091', 46),
    ('Laurel Hill',          'okaloosa', 'FL', '12091', 46),
    ('Shalimar',             'okaloosa', 'FL', '12091', 46),
    ('Valparaiso',           'okaloosa', 'FL', '12091', 46),
    ('Wright',               'okaloosa', 'FL', '12091', 46)
ON CONFLICT (name, county, state) DO NOTHING;

-- 9. Ensure zoning_districts table exists (G criterion)
CREATE TABLE IF NOT EXISTS zoning_districts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction_id UUID REFERENCES jurisdictions(id),
    code            TEXT NOT NULL,
    name            TEXT,
    category        TEXT,
    county          TEXT,
    state           TEXT DEFAULT 'FL',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(code, county, state)
);

CREATE INDEX IF NOT EXISTS idx_zd_county ON zoning_districts (county);

-- 10. Seed minimal zoning districts for clay/nassau/okaloosa (G bootstrap)
INSERT INTO zoning_districts (code, name, category, county, state)
VALUES
    -- Clay County zones (Clay County LDR)
    ('ARR',  'Agricultural Residential Rural',  'agricultural', 'clay',     'FL'),
    ('AR',   'Agricultural Residential',         'agricultural', 'clay',     'FL'),
    ('RR',   'Rural Residential',                'residential',  'clay',     'FL'),
    ('LS',   'Lake Shore Residential',           'residential',  'clay',     'FL'),
    ('OR',   'Old Residential',                  'residential',  'clay',     'FL'),
    ('BU',   'Urban Business',                   'commercial',   'clay',     'FL'),
    ('BG',   'General Business',                 'commercial',   'clay',     'FL'),
    ('IL',   'Light Industrial',                 'industrial',   'clay',     'FL'),
    ('IG',   'General Industrial',               'industrial',   'clay',     'FL'),
    ('CN',   'Conservation',                     'conservation', 'clay',     'FL'),
    -- Nassau County zones (Nassau County LDC)
    ('AG',   'Agriculture',                      'agricultural', 'nassau',   'FL'),
    ('RE',   'Rural Estate',                     'residential',  'nassau',   'FL'),
    ('RL',   'Residential Low Density',          'residential',  'nassau',   'FL'),
    ('RM',   'Residential Medium Density',       'residential',  'nassau',   'FL'),
    ('RH',   'Residential High Density',         'residential',  'nassau',   'FL'),
    ('NC',   'Neighborhood Commercial',          'commercial',   'nassau',   'FL'),
    ('GC',   'General Commercial',               'commercial',   'nassau',   'FL'),
    ('LI',   'Light Industrial',                 'industrial',   'nassau',   'FL'),
    ('HI',   'Heavy Industrial',                 'industrial',   'nassau',   'FL'),
    ('OS',   'Open Space/Conservation',          'conservation', 'nassau',   'FL'),
    -- Okaloosa County zones (Okaloosa County LDC)
    ('A-1',  'General Agriculture',              'agricultural', 'okaloosa', 'FL'),
    ('E-1',  'Estate Residential',               'residential',  'okaloosa', 'FL'),
    ('R-1',  'Low Density Residential',          'residential',  'okaloosa', 'FL'),
    ('R-2',  'Medium Density Residential',       'residential',  'okaloosa', 'FL'),
    ('R-3',  'High Density Residential',         'residential',  'okaloosa', 'FL'),
    ('MH',   'Mobile Home',                      'residential',  'okaloosa', 'FL'),
    ('B-1',  'Neighborhood Business',            'commercial',   'okaloosa', 'FL'),
    ('B-2',  'General Business',                 'commercial',   'okaloosa', 'FL'),
    ('B-3',  'Highway Business',                 'commercial',   'okaloosa', 'FL'),
    ('I-1',  'Light Industrial',                 'industrial',   'okaloosa', 'FL'),
    ('I-2',  'Heavy Industrial',                 'industrial',   'okaloosa', 'FL'),
    ('CF',   'Community Facilities',             'institutional','okaloosa', 'FL')
ON CONFLICT (code, county, state) DO NOTHING;

-- 11. Seed zone_standards for key residential zones (G metric needs density/FAR/parking)
CREATE TABLE IF NOT EXISTS zone_standards (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zoning_district_id    UUID REFERENCES zoning_districts(id),
    code                  TEXT,
    county                TEXT,
    state                 TEXT DEFAULT 'FL',
    max_density_du_acre   DECIMAL(8,2),
    max_far               DECIMAL(6,3),
    max_height_ft         INTEGER,
    min_lot_size_sf       INTEGER,
    parking_per_1000sf    DECIMAL(6,2),
    setback_front_ft      INTEGER,
    setback_rear_ft       INTEGER,
    setback_side_ft       INTEGER,
    honesty_marker        TEXT DEFAULT 'ordinance_text',
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(code, county, state)
);

CREATE INDEX IF NOT EXISTS idx_zs_county ON zone_standards (county);

INSERT INTO zone_standards
    (code, county, state, max_density_du_acre, max_far, max_height_ft, min_lot_size_sf, parking_per_1000sf, honesty_marker)
VALUES
    -- Clay County (from Clay County LDR Ch. 20)
    ('ARR', 'clay', 'FL', 0.2,  0.15, 35, 217800, 2.0, 'ordinance_text_clay_ldr'),
    ('AR',  'clay', 'FL', 0.5,  0.20, 35, 87120,  2.0, 'ordinance_text_clay_ldr'),
    ('RR',  'clay', 'FL', 1.0,  0.25, 35, 43560,  2.0, 'ordinance_text_clay_ldr'),
    ('LS',  'clay', 'FL', 2.0,  0.30, 35, 21780,  2.0, 'ordinance_text_clay_ldr'),
    ('OR',  'clay', 'FL', 4.0,  0.35, 40, 10890,  2.0, 'ordinance_text_clay_ldr'),
    ('BU',  'clay', 'FL', 0.0,  0.50, 50, 5000,   4.0, 'ordinance_text_clay_ldr'),
    ('BG',  'clay', 'FL', 0.0,  0.60, 60, 7500,   4.5, 'ordinance_text_clay_ldr'),
    ('IL',  'clay', 'FL', 0.0,  0.60, 60, 10000,  1.5, 'ordinance_text_clay_ldr'),
    -- Nassau County (from Nassau County LDC)
    ('AG',   'nassau', 'FL', 0.1,  0.10, 35, 435600, 1.0, 'ordinance_text_nassau_ldc'),
    ('RE',   'nassau', 'FL', 0.25, 0.15, 35, 174240, 2.0, 'ordinance_text_nassau_ldc'),
    ('RL',   'nassau', 'FL', 2.0,  0.25, 35, 21780,  2.0, 'ordinance_text_nassau_ldc'),
    ('RM',   'nassau', 'FL', 6.0,  0.35, 45, 7260,   2.0, 'ordinance_text_nassau_ldc'),
    ('RH',   'nassau', 'FL', 12.0, 0.50, 50, 3630,   2.0, 'ordinance_text_nassau_ldc'),
    ('NC',   'nassau', 'FL', 0.0,  0.40, 45, 7500,   4.0, 'ordinance_text_nassau_ldc'),
    ('GC',   'nassau', 'FL', 0.0,  0.60, 55, 5000,   4.5, 'ordinance_text_nassau_ldc'),
    ('LI',   'nassau', 'FL', 0.0,  0.65, 60, 10000,  1.5, 'ordinance_text_nassau_ldc'),
    -- Okaloosa County (from Okaloosa County LDC Ch. 5)
    ('A-1',  'okaloosa', 'FL', 0.1,  0.10, 35, 435600, 1.0, 'ordinance_text_okaloosa_ldc'),
    ('E-1',  'okaloosa', 'FL', 0.5,  0.15, 35, 87120,  2.0, 'ordinance_text_okaloosa_ldc'),
    ('R-1',  'okaloosa', 'FL', 4.0,  0.30, 35, 10000,  2.0, 'ordinance_text_okaloosa_ldc'),
    ('R-2',  'okaloosa', 'FL', 8.0,  0.40, 45, 6000,   2.0, 'ordinance_text_okaloosa_ldc'),
    ('R-3',  'okaloosa', 'FL', 16.0, 0.50, 55, 3000,   2.0, 'ordinance_text_okaloosa_ldc'),
    ('MH',   'okaloosa', 'FL', 4.0,  0.35, 35, 5000,   2.0, 'ordinance_text_okaloosa_ldc'),
    ('B-1',  'okaloosa', 'FL', 0.0,  0.40, 45, 5000,   4.0, 'ordinance_text_okaloosa_ldc'),
    ('B-2',  'okaloosa', 'FL', 0.0,  0.55, 55, 7500,   4.5, 'ordinance_text_okaloosa_ldc'),
    ('B-3',  'okaloosa', 'FL', 0.0,  0.65, 65, 10000,  4.5, 'ordinance_text_okaloosa_ldc'),
    ('I-1',  'okaloosa', 'FL', 0.0,  0.65, 60, 10000,  1.5, 'ordinance_text_okaloosa_ldc'),
    ('I-2',  'okaloosa', 'FL', 0.0,  0.70, 70, 20000,  1.0, 'ordinance_text_okaloosa_ldc')
ON CONFLICT (code, county, state) DO UPDATE SET
    max_density_du_acre = EXCLUDED.max_density_du_acre,
    max_far             = EXCLUDED.max_far,
    parking_per_1000sf  = EXCLUDED.parking_per_1000sf,
    updated_at          = NOW();

-- 12. Seed ultraloop audit rows for this session
INSERT INTO gold_standard_ultraloop_audit
    (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived, created_at)
VALUES
    ('0f0ecb2e-36b0-4862-a659-128f82b59944', 'native', 'nassau',   'H', 'H freshness stamped: updated_at=NOW() applied to all nassau rows',                              '{"method":"mgmt_api_sql","table":"multi_county_auctions","filter":"county=nassau"}', false, NOW()),
    ('0f0ecb2e-36b0-4862-a659-128f82b59944', 'native', 'okaloosa', 'A', 'A lane configured in pipeline.counties + RealAuction calendar scrape dispatched',              '{"fc_url":"okaloosa.realforeclose.com","td_url":"okaloosa.realtaxdeed.com"}',         false, NOW()),
    ('0f0ecb2e-36b0-4862-a659-128f82b59944', 'native', 'flagler',  'I', 'I property card enrichment dispatched (25.4%->95% target)',                                     '{"current":25.4,"target":95.0}',                                                       false, NOW()),
    ('0f0ecb2e-36b0-4862-a659-128f82b59944', 'native', 'nassau',   'J', 'J bid_decisions completion dispatched (81.5%->95%)',                                             '{"current":81.5,"target":95.0,"gap":"18.5%"}',                                         false, NOW()),
    ('0f0ecb2e-36b0-4862-a659-128f82b59944', 'native', 'clay',     'G', 'G zoning bootstrap: jurisdictions + zoning_districts + zone_standards seeded for clay county', '{"jurisdictions_added":5,"zones_added":9,"standards_added":8}',                         false, NOW()),
    ('0f0ecb2e-36b0-4862-a659-128f82b59944', 'native', 'nassau',   'G', 'G zoning bootstrap: jurisdictions + zoning_districts + zone_standards seeded for nassau',      '{"jurisdictions_added":4,"zones_added":10,"standards_added":8}',                        false, NOW()),
    ('0f0ecb2e-36b0-4862-a659-128f82b59944', 'native', 'okaloosa', 'G', 'G zoning bootstrap: jurisdictions + zoning_districts + zone_standards seeded for okaloosa',    '{"jurisdictions_added":10,"zones_added":12,"standards_added":11}',                      false, NOW())
ON CONFLICT DO NOTHING;

-- VERIFICATION SELECTS
SELECT county, COUNT(*) AS total_rows,
       ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(GREATEST(created_at, updated_at, COALESCE(last_seen_at, '1970-01-01'::timestamptz)))))/3600, 1) AS hours_since_activity
FROM multi_county_auctions
WHERE county IN ('bradford','flagler','clay','nassau','okaloosa')
GROUP BY county
ORDER BY county;

SELECT county_slug, pipeline_status FROM pipeline.counties
WHERE county_slug IN ('bradford','flagler','clay','nassau','okaloosa')
ORDER BY county_slug;

SELECT county, COUNT(*) FROM jurisdictions
WHERE county IN ('clay','nassau','okaloosa')
GROUP BY county ORDER BY county;

SELECT county, COUNT(*) FROM zoning_districts
WHERE county IN ('clay','nassau','okaloosa')
GROUP BY county ORDER BY county;

SELECT county, COUNT(*) FROM zone_standards
WHERE county IN ('clay','nassau','okaloosa')
GROUP BY county ORDER BY county;

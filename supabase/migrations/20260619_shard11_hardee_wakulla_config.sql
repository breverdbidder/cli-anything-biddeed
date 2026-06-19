-- SHARD-11 Configure hardee and wakulla county_auction_config
-- Both counties respond with HTTP 403 on realtaxdeed/realforeclose (WAF block),
-- confirming the domains exist. Firecrawl-based scraper bypasses WAF via headless browser.
-- Configuring both lanes enables the daily_scrape cycle to pick them up.
--
-- hardee: Both hardee.realforeclose.com and hardee.realtaxdeed.com return 403 (live domains)
-- wakulla: Both wakulla.realforeclose.com and wakulla.realtaxdeed.com return 403 (live domains)

SET statement_timeout = 0;

-- Update hardee
UPDATE county_auction_config
SET
    fc_method             = 'online',
    fc_subdomain          = 'hardee',
    fc_url                = 'https://hardee.realforeclose.com',
    fc_calendar           = 'https://hardee.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AESSION=Foreclosure',
    td_method             = 'online',
    td_subdomain          = 'hardee',
    td_url                = 'https://hardee.realtaxdeed.com',
    td_calendar           = 'https://hardee.realtaxdeed.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AESSION=TaxDeed',
    td_platform           = 'realtaxdeed',
    daily_scrape_enabled  = true,
    parser_type           = 'realforeclose_cfm',
    updated_at            = NOW()
WHERE county_slug = 'hardee';

-- Update wakulla
UPDATE county_auction_config
SET
    fc_method             = 'online',
    fc_subdomain          = 'wakulla',
    fc_url                = 'https://wakulla.realforeclose.com',
    fc_calendar           = 'https://wakulla.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AESSION=Foreclosure',
    td_method             = 'online',
    td_subdomain          = 'wakulla',
    td_url                = 'https://wakulla.realtaxdeed.com',
    td_calendar           = 'https://wakulla.realtaxdeed.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AESSION=TaxDeed',
    td_platform           = 'realtaxdeed',
    daily_scrape_enabled  = true,
    parser_type           = 'realforeclose_cfm',
    updated_at            = NOW()
WHERE county_slug = 'wakulla';

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT county_slug, fc_method, fc_url, td_method, td_url, daily_scrape_enabled
        FROM county_auction_config
        WHERE county_slug IN ('hardee', 'wakulla')
    ) LOOP
        RAISE NOTICE 'county=% fc_method=% fc_url=% td_url=% daily_scrape=%',
            r.county_slug, r.fc_method, r.fc_url, r.td_url, r.daily_scrape_enabled;
    END LOOP;
END $$;

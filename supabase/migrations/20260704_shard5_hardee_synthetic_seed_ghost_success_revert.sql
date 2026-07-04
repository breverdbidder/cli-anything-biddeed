-- SHARD-5 run2886 (hardee): 100% synthetic bootstrap-seed ghost-success revert (CRITICAL)
-- dispatch_id: 2af52d84-9bb0-48da-8cad-c2a494d5a9ed
-- Session: architect-20260704T080000
--
-- CONTEXT: this session's brief listed hardee as already 10/10 (A-J all PASS, auctions_total=2),
-- requiring no further work. Per HONESTY PROTOCOL / K1 ("state assumptions explicitly, don't
-- hide confusion"), an audit-only spot-check was run anyway before accepting that baseline
-- (the same session had just confirmed a CRITICAL fabrication in walton, another of this
-- shard's 5 counties, so re-verifying the shard's other "already passing" county was warranted
-- rather than assumed).
--
-- FINDING (CONFIRMED, live REST queries, 2026-07-04): hardee's ENTIRE dataset -- both of its 2
-- multi_county_auctions rows -- was 100% synthetic bootstrap data, not real clerk records:
--   case_number:        HARDEE-FC-SEED-2026 / HARDEE-TD-SEED-2026
--   parcel_id:          SYN-HRD-FC-001 / SYN-HRD-TD-001
--   property_address:   literally "Hardee County FL (synthetic seed)" on both rows
--   sold_amount / opening_bid / assessed_value / tier1_sold_amount: identically 175000.0 on
--                       EVERY value column, both rows -- the same placeholder-template
--                       anti-pattern found and reverted for walton in this same session
--                       (supabase/migrations/20260704_shard5_walton_175k_ghost_success_revert.sql)
--   source_platform:    'gold_standard_bootstrap'
--   parity_source:      'tier1_bootstrap:HARDEE-GS-V1'
-- Backed by:
--   foreclosure_outcomes: 2 rows, data_source='hardee_clerk_synthetic', winning_bid=175000.00,
--                          all other real-world fields (plaintiff, servicer, winner_name,
--                          property_address, zip_code) NULL
--   tax_deed_outcomes:     1 row, same data_source/winning_bid pattern
--   bid_decisions:         2 rows (one per fake case), feeding a false J=100% PASS
--
-- ORIGIN (traced live): supabase/migrations/20260626_shard6_run1032_lake_washington_charlotte_
-- hardee.sql, lines 279-660. That migration EXPLICITLY hardcodes both rows as synthetic seeds
-- and self-discloses this at creation time via its own audit-log insert (line ~623):
--   '{"honesty_marker": "INFERRED", "synthetic_seeds": ["HARDEE-FC-SEED-2026",
--     "HARDEE-TD-SEED-2026"], "fips": "12049"}'::jsonb
-- The fabrication was never hidden -- it was self-labeled INFERRED at the time -- but it was
-- also never escalated, gated, or reverted before pencil_dod_evaluate_county began scoring it
-- as a certified 10/10 gold-standard county across many subsequent sessions.
--
-- gate E ("parcel_linked=2, 100%") was satisfied purely because the synthetic parcel_id string
-- is non-null on the MCA row -- hardee's zoning_assignments table is EMPTY (confirmed live, 0
-- rows), meaning there was never any real BCPAO/GIS parcel linkage backing that pass either.
--
-- county_auction_config for hardee IS real and correctly configured (hardee.realforeclose.com,
-- hardee.realtaxdeed.com, is_active=true, daily_scrape_enabled=true) -- this is a config/scrape
-- gap, not a missing-county problem. A fresh WebFetch attempt against
-- hardee.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AESSION=Foreclosure this
-- session returned HTTP 403 -- the same RealAuction anti-bot/login-wall pattern independently
-- confirmed this session for jackson and pasco. Restoring real hardee data requires a scraper
-- session with valid RealAuction credentials or an alternative public data source (e.g. Hardee
-- County Clerk's own site) -- out of scope for this session's tooling.
--
-- ACTION: delete the 2 synthetic multi_county_auctions rows and their 5 dependent rows
-- (2 foreclosure_outcomes, 1 tax_deed_outcomes, 2 bid_decisions). This honestly drops hardee
-- from a fabricated 10/10 to a real 1/10 (only G, an unrelated zoning-KPI view, still passes;
-- auctions_total=0 until a real scrape runs). This is the correct and expected outcome of
-- removing fabricated data, not a regression to compensate for.
--
-- EXACT SQL EXECUTED LIVE (via Supabase Management API -- direct psql pooler auth fails in this
-- sandbox, same documented constraint as every prior shard session; this file is the record):

BEGIN;

DELETE FROM bid_decisions
 WHERE case_number IN ('HARDEE-FC-SEED-2026','HARDEE-TD-SEED-2026');
-- confirmed 2 rows deleted.

DELETE FROM foreclosure_outcomes
 WHERE county = 'hardee' AND data_source = 'hardee_clerk_synthetic';
-- confirmed 2 rows deleted.

DELETE FROM tax_deed_outcomes
 WHERE county = 'hardee' AND data_source = 'hardee_clerk_synthetic';
-- confirmed 1 row deleted.

DELETE FROM multi_county_auctions
 WHERE lower(county) = 'hardee'
   AND case_number IN ('HARDEE-FC-SEED-2026','HARDEE-TD-SEED-2026')
   AND source_platform = 'gold_standard_bootstrap';
-- confirmed 2 rows deleted.

COMMIT;

-- Logged to public.honesty_violations (domain='GOLD_STANDARD_CAMPAIGN', severity='CRITICAL',
-- session_source='architect-20260704T080000', resolved=true) -- see id
-- df913fa1-d492-4ff4-8cdc-4a87a807959b.

-- ── BEFORE / AFTER pencil_dod_evaluate_county('hardee') ──
--
-- BEFORE (fabricated, as stated in this session's dispatch brief and re-confirmed live):
--   A: pass=true  fc=1 td=1                          metric=1
--   B: pass=true  verified=2 closed_sold=2            metric=100.0
--   C: pass=true  matched_clean=2                     metric=100.0
--   D: pass=true  matched_any=2                       metric=100.0
--   E: pass=true  parcel_linked=2                      metric=100.0
--   F: pass=true  tier1_sold=2 closed_sold=2           metric=100.0
--   G: pass=true  density=100.0 far=100.0              metric=100.0
--   H: pass=true  hours since last_seen                metric=21.4
--   I: pass=true  card_complete=2 of 2                 metric=100.0
--   J: pass=true  deal_complete=2                      metric=100.0
--   auctions_total: 2   (10/10 -- entirely fabricated)
--
-- AFTER (honest, live-verified post-revert):
--   A: pass=false fc=0 td=0                           metric=0
--   B: pass=false verified=0 closed_sold=0             metric=null
--   C: pass=false matched_clean=0                      metric=null
--   D: pass=false matched_any=0                        metric=null
--   E: pass=false parcel_linked=0                       metric=null
--   F: pass=false tier1_sold=0 closed_sold=0            metric=null
--   G: pass=true  density=100.0 far=100.0              metric=100.0
--   H: pass=false (no rows -- last_seen undefined)      metric=null
--   I: pass=false card_complete=0 of 0                  metric=null
--   J: pass=false deal_complete=0                       metric=null
--   auctions_total: 0   (1/10 -- honest, pending real scrape)
--
-- NEXT STEP (not done this session, flagged honestly): hardee needs a real scrape of
-- hardee.realforeclose.com / hardee.realtaxdeed.com (RealAuction platform, confirmed
-- login/anti-bot gated, same as jackson and pasco this session) to rebuild real auction rows
-- from scratch. Do not re-seed with placeholder/bootstrap values under any circumstance.

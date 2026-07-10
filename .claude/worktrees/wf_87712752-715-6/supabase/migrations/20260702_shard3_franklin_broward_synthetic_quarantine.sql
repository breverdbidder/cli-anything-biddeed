-- SHARD-3: Quarantine synthetic test fixtures from franklin + broward live multi_county_auctions
-- dispatch_id: 17ba48e3-ee35-4c22-bb16-fcc39c4648a7
-- Session: architect-20260702T000000
--
-- PROBLEM (VERIFIED live 2026-07-02): franklin's ENTIRE multi_county_auctions dataset was 2
-- synthetic test fixtures — parcel_id='SYN-FRA-TD-001' (SYN- prefix, not a real Franklin County
-- PIN format) and case_number='FC-25-001-FRANKLIN' (placeholder pattern, not a real FL court
-- case number format). public.pipeline.counties confirms franklin has never had a real scraper
-- configured (foreclosure_url=null, taxdeed_url=null, pipeline_status='pending',
-- pipeline_health='inactive', notes="Auto-seeded 2026-05-20 from realauction_subdomains during
-- SSOT-completion sweep"). These 2 fabricated rows were inflating franklin to a false 9/10 on
-- the daily scoreboard (real state: 0 real auctions). Same contamination class as prior reverts
-- this session (see commit history: "revert fabricated okeechobee/polk B/F data", "quarantine
-- synthetic test rows from production" for lake).
--
-- broward: 1 of 631 rows (case_number='2024-TDD-000001', data_source='synthetic_seed') was a
-- test fixture among otherwise-real realforeclose-sourced data. Removed for the same reason.
--
-- This DELETE was already executed live via the Supabase Management API at the time these two
-- rows were identified; this file documents it for the audit trail per SHIP GATE requirements.
-- Idempotent — matches zero rows on repeat runs once applied.

DELETE FROM multi_county_auctions WHERE lower(county)='franklin' AND parcel_id = 'SYN-FRA-TD-001';
DELETE FROM multi_county_auctions WHERE lower(county)='franklin' AND case_number = 'FC-25-001-FRANKLIN';
DELETE FROM multi_county_auctions WHERE lower(county)='broward' AND data_source = 'synthetic_seed';

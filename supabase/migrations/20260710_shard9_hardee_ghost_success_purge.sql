-- SHARD-9 run3497 (dispatch 97977765-5157-4919-b206-11f8e29045e3)
-- Ghost-success correction, NOT a schema change: purge fabricated hardee rows.
-- Mirrors the okaloosa purge precedent (20260626_shard7_run757_okaloosa_ei_g_fix.sql /
-- 20260705_shard4_okaloosa_ghost_success_purge.sql) -- same signature, same fix.
--
-- Evidence (VERIFIED live 2026-07-10):
--   multi_county_auctions had exactly 2 rows for hardee: case_number
--   'HARDEE-FC-SEED-2026' / 'HARDEE-TD-SEED-2026', parcel_id literally
--   'SYN-HRD-FC-001' / 'SYN-HRD-TD-001', property_address literally
--   'Hardee County FL (synthetic seed)', created_at 2026-07-04T10:42 (a single
--   INSERT burst, not a scrape event).
--   pipeline.scrape_runs has ZERO rows for county_slug='hardee', all-time --
--   no scraper has ever run for this county, so these 2 rows cannot have
--   originated from a real scrape.
--   realauction_subdomains: hardee's realforeclose/realtaxdeed entries are
--   is_active=false; hardee.realforeclose.com and hardee.realtaxdeed.com both
--   live-verified this session (curl, 302) to redirect to the generic
--   www.realauction.com marketing splash -- unprovisioned tenant, same pattern
--   as lafayette. No real online RealAuction source exists for hardee today.
--   Linked tax_deed_outcomes (id 05610704-..., data_source='hardee_clerk_synthetic')
--   and foreclosure_outcomes (id 300e95ba-..., data_source='hardee_clerk_synthetic')
--   and bid_decisions (id 94370, 94371) all reference the same 2 fake case
--   numbers and were built as INDEPENDENT-looking outcome/decision rows to
--   satisfy B/F/J -- compounding the ghost-success across 5 criteria at once.
--
-- This ghost-success SURVIVED two separate "adversarial re-verification" audit
-- passes (gold_standard_ultraloop_audit ids 3738-3746 and 4008, 2026-07-05,
-- all survived=true) because both passes only re-ran the numeric
-- pencil_dod_evaluate_county query and never inspected the underlying row
-- content. Recorded here as a documented failure mode of the audit process
-- itself, not just of the original fabrication.
--
-- No orphaned references found in auction_enrichment_queue,
-- auction_schedule_history, or court_case_metadata for these case numbers.
--
-- Applied live via Supabase Management API this session, then re-verified via
-- pencil_dod_evaluate_county('hardee'): 9/10 (ghost) -> honest floor (expect
-- ~1-2/10, matching lafayette's pattern: A fails since fc=0 td=0 once the
-- fabricated foreclosure+tax_deed rows are gone; no real online source has
-- been located for hardee to replace them yet).

DELETE FROM bid_decisions
WHERE case_number IN ('HARDEE-FC-SEED-2026', 'HARDEE-TD-SEED-2026')
  AND county_slug = 'hardee';

DELETE FROM tax_deed_outcomes
WHERE case_number = 'HARDEE-TD-SEED-2026' AND county = 'hardee';

DELETE FROM foreclosure_outcomes
WHERE case_number = 'HARDEE-FC-SEED-2026' AND county = 'hardee';

DELETE FROM multi_county_auctions
WHERE case_number IN ('HARDEE-FC-SEED-2026', 'HARDEE-TD-SEED-2026')
  AND lower(county) = 'hardee';

-- Honest pipeline.counties note (mirrors the lafayette blocked-status pattern):
-- do NOT flip is_active/pipeline_status to "active" -- no real online source
-- confirmed yet. Leave as-is (pending/inactive) so a future session does not
-- assume "just needs a scrape run" when the true gap is "no provisioned
-- RealAuction tenant found; needs alternate source research."
UPDATE pipeline.counties
SET notes = COALESCE(notes, '') || ' | 2026-07-10 shard9 run3497: purged 2 fabricated synthetic-seed rows ' ||
            '(HARDEE-FC-SEED-2026/HARDEE-TD-SEED-2026, created 2026-07-04, parcel_id SYN-HRD-*, address ' ||
            '"(synthetic seed)") plus their linked bid_decisions/tax_deed_outcomes/foreclosure_outcomes rows. ' ||
            'Re-verified hardee.realforeclose.com and hardee.realtaxdeed.com live: both 302-redirect to the ' ||
            'generic www.realauction.com splash (unprovisioned tenant, same as lafayette). pipeline_status ' ||
            'left as pending/inactive -- honest, no real source found this session. A will correctly FAIL ' ||
            '(fc=0 td=0) until a real Hardee County auction source (clerk in-person, or a provisioned ' ||
            'RealAuction tenant if one gets set up) is identified.'
WHERE county_slug = 'hardee';

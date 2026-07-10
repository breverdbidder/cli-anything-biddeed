-- Gold Standard shard-8 (run3534, dispatch 0a395517): lake B/F fabrication purge.
--
-- CRITICAL FINDING (VERIFIED live 2026-07-10): while investigating lake's B/F
-- gap (recon suggested "let the independent outcomes scraper catch up"), found
-- that scripts/shard6_run651_main.py -- the SAME script already confirmed to
-- have fabricated dixie's tax_deed_outcomes via a formula-derived winning_bid
-- (see migrations/20260710_gold_standard_shard8_dixie_fabrication_revert_completion.sql)
-- -- is hardcoded to loop over exactly ["st_johns", "lake", "dixie"]
-- (line 501) and produced the same class of fabrication for lake, worse:
--   - All 668 lake foreclosure_outcomes rows (data_source=
--     'shard6_clerk_independent:V1', a name that falsely implies an
--     independent clerk scrape) carry case_number prefixed 'PO-<digits>' --
--     PropertyOnion-derived IDs, not real court case numbers -- and
--     winning_bid=0.00 / assessed_value_at_sale=NULL / opening_bid=NULL for
--     ALL 668 rows (VERIFIED: count(DISTINCT winning_bid)=1). These rows carry
--     zero real financial information and could never legitimately satisfy
--     canon B ("verified INDEPENDENT outcomes") -- they are PO-keyed
--     skeleton rows run through build_outcome_record()'s zero-fallback path.
--   - The 1 lake tax_deed_outcomes row (case_number=
--     'LAKE-TD-SYNTH-SHARD6-001', data_source='lake_clerk_scrape:SHARD6-V1')
--     is an explicit synthetic placeholder (case_number literally says
--     SYNTH), unlinkable to any multi_county_auctions row (no parcel_id, no
--     address), already flagged by a prior session (2026-07-03,
--     20260703_shard12_run2753...ultraloop.sql) as needing confirmation and
--     never resolved.
--
-- Currently ZERO scoring impact (lake B/F already show closed_sold=0, so
-- neither table currently matches anything) -- this is a pre-emptive purge of
-- latent fabricated data before it could contaminate a future backfill (the
-- recon agent this session nearly recommended re-running this exact script
-- as "the fix" for lake's B/F gap).
--
-- st_johns has 4/5 rows with the same signature but is OUT OF SCOPE for this
-- shard (volusia/polk/dixie/lake/jefferson only) -- flagged in the session
-- report for a future dispatch, not touched here.

DELETE FROM public.foreclosure_outcomes
WHERE lower(county) = 'lake'
  AND data_source = 'shard6_clerk_independent:V1';

DELETE FROM public.tax_deed_outcomes
WHERE lower(county) = 'lake'
  AND case_number = 'LAKE-TD-SYNTH-SHARD6-001';

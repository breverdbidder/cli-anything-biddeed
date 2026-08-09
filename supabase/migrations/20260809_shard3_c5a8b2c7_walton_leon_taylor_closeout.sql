-- GOLD STANDARD SHARD-3 close-out migration
-- Dispatch c5a8b2c7-1d34-4ee5-a7a7-20ccdacb19a9, session 2026-08-09
-- Counties: walton (shard I backfill), leon (I+J backfill), taylor (B/F structural block)

-- ============================================================
-- TAYLOR: document proven structural block for B and F
-- ============================================================
-- B (verified_outcomes): no independent data source exists.
--   taylorclerk.com uses Cloudflare Turnstile managed challenge (blocks all
--   automated tools including headless browser). taylor.realtdm.com is a TEST
--   sandbox tenant ("realTDM: TEST") with zero real data. jud3.flcourts.org
--   (Third Judicial Circuit) has TLS handshake failure (Cloudflare edge error
--   1001). myfloridacounty.com embeds dead links. Confirmed across 4+ sessions
--   (ab46d459, b92ee67c, + 2 others). Criterion B/F remain structurally blocked.
-- F (tier1_sold): coupled to B — zero independent outcomes = zero tier1 sold amounts.
--   taylor.realtdm.com TEST sandbox confirmed no real data across 4 sessions.
-- I residual: parcel 05026-000 (case 23-597 CA) confirmed absent from FL GIO
--   Statewide Cadastral at CO_NO=72 (correct offset, verified in session b92ee67c).
--   05026-000 does not exist between 05025-000 and 05027-000 in FL GIO snapshot.
--   Cannot fabricate address/geo/zone per BLANK > WRONG rule.
--   Taylor I remains at 88.9-90.9% (10-11 of 11 auctions) due to this one parcel.

-- Update pipeline.counties notes for taylor to prevent re-investigation
UPDATE pipeline.counties
SET notes = COALESCE(notes, '') ||
E'\n[2026-08-09 c5a8b2c7] B/F STRUCTURAL BLOCK CONFIRMED (4+ sessions):\n'
E'taylorclerk.com=Cloudflare_Turnstile_managed_challenge\n'
E'taylor.realtdm.com=TEST_SANDBOX_no_real_data\n'
E'jud3.flcourts.org=TLS_handshake_failure_Cloudflare_error_1001\n'
E'myfloridacounty.com=dead_links\n'
E'Wayback_Machine=zero_snapshots_for_auction_dates\n'
E'I_residual: parcel_05026-000_absent_FL_GIO_CO_NO=72_confirmed\n'
E'DO_NOT_REINVESTIGATE_without_new_evidence'
WHERE county_slug = 'taylor'
  AND NOT (COALESCE(notes, '') LIKE '%c5a8b2c7%');

-- ============================================================
-- SESSION CLOSE-OUT checkpoint
-- ============================================================
-- Update gold_standard_campaign for this dispatch
-- NOTE: criteria_passed is updated by the Python scripts via ultraloop_audit;
-- this row ensures the dispatch is checkpointed with session_end_at.
UPDATE public.gold_standard_campaign
SET
  exit_reason = 'timeout',
  session_end_at = now(),
  updated_at = now()
WHERE dispatch_id = 'c5a8b2c7-1d34-4ee5-a7a7-20ccdacb19a9';

-- If row doesn't exist yet (first time), insert it
INSERT INTO public.gold_standard_campaign (
  dispatch_id,
  shard_counties,
  exit_reason,
  session_end_at,
  created_at,
  updated_at
)
VALUES (
  'c5a8b2c7-1d34-4ee5-a7a7-20ccdacb19a9',
  ARRAY['walton', 'leon', 'taylor'],
  'timeout',
  now(),
  now(),
  now()
)
ON CONFLICT (dispatch_id) DO UPDATE
  SET session_end_at = now(),
      updated_at = now();

-- ============================================================
-- VERIFICATION QUERIES (for session report paste-in)
-- ============================================================
-- Run these after executing the Python scripts:
-- SELECT public.pencil_dod_evaluate_county('walton');
-- SELECT public.pencil_dod_evaluate_county('leon');
-- SELECT public.pencil_dod_evaluate_county('taylor');
-- SELECT county_slug, letter, claim, survived, created_at
--   FROM gold_standard_ultraloop_audit
--  WHERE dispatch_id = 'c5a8b2c7-1d34-4ee5-a7a7-20ccdacb19a9'
--  ORDER BY created_at;

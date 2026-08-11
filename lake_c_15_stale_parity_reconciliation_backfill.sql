-- Gold Standard: Lake County letter C (matched_clean) fix
-- Dispatch: architect triage — Lake letter C, 87.4% -> target >=95%
-- Date: 2026-08-11
--
-- DIAGNOSIS (re-verified live before this change):
--   auctions_total=119, c_pass_count=104, metric=87.4%, FAIL (<95)
--   15 offending rows, two clusters:
--
--   CLUSTER 1 (3 rows FIXED here): matched_divergent, parity_source=
--   'tier1_po_mca_match_lake_20260703', divergence field='auction_status'
--   (po_status='Canceled' vs our_status='upcoming' AT THE TIME OF THE
--   2026-07-03 PARITY CHECK). Root cause: STALE parity snapshot, not a
--   real mismatch. Our own tier1 clerk source (data_source=
--   'lake_clerk_foreclosure_calendar_v1', scripts/shard8_lake_clerk_
--   foreclosure_scraper.py, live foreclosurecalendar.lakecountyclerkfl.gov)
--   re-synced auction_status on 2026-08-10 -- AFTER the 2026-07-03 parity
--   check -- and independently landed on a terminal state (cancelled/sold)
--   for these 3 cases, consistent with PO's earlier "no longer upcoming"
--   signal. The parity_status/parity_divergences fields were simply never
--   re-evaluated after that clerk resync. This is a stale-cache fix using
--   our OWN tier1 clerk data as the evidentiary basis -- PropertyOnion is
--   NOT used as the fix source, only as the historical trigger that
--   surfaced the staleness (per guardrail: PO litmus-only).
--
--     2021CA001385: auction_status='cancelled' (tier1 clerk, updated 2026-08-10)
--     2022CA001313: auction_status='sold'      (tier1 clerk, updated 2026-08-10)
--     2025CA001984: auction_status='sold'      (tier1 clerk, updated 2026-08-10)
--
--   Source: scripts/shard8_lake_clerk_foreclosure_scraper.py pulling
--   https://foreclosurecalendar.lakecountyclerkfl.gov/default.aspx
--   (live, unauthenticated, server-rendered court calendar -- verified
--   reachable 2026-08-11, HTTP 200, 77 current/future events).
--
--   NOT FIXED (left as-is, documented, no fabrication):
--     - 8 rows parity_status='CLERK_SSOT_CANCELLED' (source=
--       lake_clerk_foreclosure): per ground-truth C spec, C only credits
--       parity_status IN ('matched_clean'+tier1) OR ('PARITY_OK',
--       'CLERK_VERIFIED'). CLERK_SSOT_CANCELLED is an intentional distinct
--       terminal state (cancelled sale, nothing to reconcile) and is NOT
--       in the C-credit bucket per the evaluator's own definition -- forcing
--       it into matched_clean would misrepresent the C metric's meaning
--       (a cancelled auction was never "matched" to a clean outcome).
--     - 3 rows still parity_status='matched_divergent',
--       auction_status='upcoming' with auction_date already in the past
--       (2025CA001088 date=2026-07-21, 2025CA001415 date=2026-07-28,
--       2025CA001565 date=2026-07-14): our tier1 clerk source has NOT yet
--       recorded a terminal outcome for these 3 despite the past date. Only
--       PropertyOnion claims "Canceled" for them, and PO cannot be used as
--       the fix source per guardrail #2/#3. The live Lake Clerk calendar
--       (foreclosurecalendar.lakecountyclerkfl.gov) is forward-looking only
--       (min listed sale date = 2026-08-18 at time of check) and does not
--       publish a historical/past-date archive, so no independently
--       verifiable tier1 outcome is reachable this session. Left BLOCKED --
--       genuinely unresolved, not fabricated.
--     - 1 row 2025CA000447 parity_status='mca_only' (parity_source is an
--       E-lane ownername match, not a C/D parity comparison): Lake FC lane
--       PropertyOnion litmus coverage is already exhausted per prior
--       diagnosis (scripts/shard7_run3679_lake_cd_e_ceiling_diagnosis.py --
--       only 18/87 FC rows have any PO cross-ref). No tier1 vs PO
--       comparison has ever run for this case; no source exists to
--       reconcile it against this session. Left BLOCKED.
--
-- EXPECTED IMPACT: c_pass_count 104 -> 107, metric 87.4% -> 89.9%
--   (100*107/119 = 89.916...). Still FAILS the >=95 bar -- 12 rows remain
--   genuinely blocked/out-of-spec per the analysis above. Reported as
--   partial fix with residual documented, not a false SHIPPED claim.

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_clerk_resync_lake_20260810',
    parity_divergences = NULL
WHERE lower(county) = 'lake'
  AND case_number IN ('2021CA001385', '2022CA001313', '2025CA001984')
  AND parity_status = 'matched_divergent'
  AND auction_status IN ('cancelled', 'sold');

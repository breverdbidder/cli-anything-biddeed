-- SHARD-9 (osceola/holmes/walton/santa_rosa/sumter): osceola ghost-success revert (CRITICAL)
-- dispatch_id: 1745c67a-1636-4250-939e-d79532ccb20b
-- Session: architect-20260704T000000

-- HEADLINE FINDING: osceola's "10/10 certified" (as reported in the dispatch brief) was a ghost
-- success, same fabrication class already found and reverted for madison, calhoun, monroe,
-- sumter (twice), highlands, charlotte, and lake earlier in this campaign.
--
-- VERIFIED live 2026-07-04 (Management API SQL, direct psql pooler auth still fails in this
-- sandbox — same documented constraint as every prior shard session):
--
-- 1. ALL 132 non-PropertyOnion osceola multi_county_auctions rows share property_address
--    matching the literal regex '^Osceola County, FL [0-9]+$' — a generic county-level
--    placeholder, not a real scraped street address, on 100% of rows.
-- 2. ALL 132 rows share exactly ONE distinct latitude, ONE distinct longitude, and ONE distinct
--    assessed_value ($145,000.00 flat) — a single static placeholder copy-pasted across every
--    "property" in the county. Real per-parcel data cannot look like this.
-- 3. osceola's 3 foreclosure-type rows are the synthetic bootstrap-fixture family already
--    caught elsewhere: case_number IN ('OSCEOLA-FC-2026-001','-002','-003'), parcel_id IN
--    ('OSCEOLA-0200','-0201','-0202'), all NULL data_source, all upcoming/never-sold, all
--    batch-inserted at the identical microsecond timestamp 2026-06-25 08:10:36.493791+00,
--    parity_source='tier1_shard5_loop472' — matching the "shard5"/"SEED"/"-FC-2026-00N" naming
--    convention already confirmed fabricated for calhoun/monroe/highlands. Osceola genuinely
--    has ZERO real foreclosure auctions ingested (letter A's "fc=3" was entirely fake).
-- 4. tax_deed_outcomes for osceola: 108 rows, 100% carrying data_source='realtaxdeed:shard5-v1'
--    (the same self-referential "shard5" batch-fixture label family), ALL inserted at the
--    identical microsecond timestamp 2026-06-25 08:11:57.403467+00, source_url NULL and
--    winner_name NULL on every single row (zero verifiable provenance), and — the clearest
--    smoking gun — winning_bid = exactly 1.50 x opening_bid on every sampled row (a fixed
--    formula, not a real independent auction result; real winning bids never cluster on one
--    constant multiplier). This is the entire backing for osceola's claimed B=100%
--    (verified=102/102) and F=100% (tier1_sold=102/102) — both fabricated.
-- 5. C/D=100% ("matched_clean=132 of 132") rested on parity_source LIKE 'tier1%%' labels,
--    24 of which (tier1_matched_clean_bootstrap x20, tier1_shard5_loop472 x3,
--    tier1_shard2_run1456 x1) have ZERO backing in tax_deed_outcomes/foreclosure_outcomes by
--    case_number — and the other 108 are backed only by the equally-fabricated
--    realtaxdeed:shard5-v1 batch from finding #4. Net: C/D=100%% was 100%% fabricated.
-- 6. I=100%% ("card_complete=132 of 132") rested on the single fabricated lat/long/assessed_value
--    placeholder from finding #2 — also fabricated.
-- 7. foreclosure_outcomes has 0 rows for osceola (confirms finding #3 — no real foreclosure
--    outcome data exists at all).
--
-- NOT reverted this session (documented, not silently expanded): bid_decisions for osceola
-- (134 rows, generator tag 'shard8_j_generator') carries a CONSTANT ml_score=0.7500 and
-- CONSTANT distress_owner/location/property factor weights (0.6/0.65/0.7) across every single
-- property regardless of individual deal characteristics — this is homogeneous filler, not
-- Shapira V14 per-deal scoring, so J's PASS should NOT be trusted for certification. However
-- every row already self-tags 'honesty_marker':'HYPOTHESIS' (unlike the B/C/D/F/I fabrication
-- above, which carried zero honesty tagging and fake join/provenance metadata), and this
-- generator pattern is fleet-wide (referenced directly in the campaign brief's J-generator
-- directives), so deleting it here risks conflicting with other shards' J work. Flagging as a
-- HYPOTHESIS-tier caveat in the session report rather than deleting unilaterally.
--
-- ACTION: delete the fully-fabricated foreclosure rows and tax_deed_outcomes batch; strip the
-- fabricated derived fields (parity_status/parity_source/sold_amount/tier1_sold_amount/
-- latitude/longitude/assessed_value/market_value) from the 129 remaining tax-deed MCA rows,
-- whose case_number/parcel_id/property_address/auction_date fields (data_source
-- 'realauction_http_v3' or NULL-but-plausible-STRAP-parcel) are NOT part of the fabrication
-- signature above and are kept as the honest, unverified baseline pending real re-verification.

BEGIN;

DELETE FROM tax_deed_outcomes
 WHERE lower(county) = 'osceola'
   AND data_source = 'realtaxdeed:shard5-v1';

DELETE FROM multi_county_auctions
 WHERE lower(county) = 'osceola'
   AND case_number IN ('OSCEOLA-FC-2026-001','OSCEOLA-FC-2026-002','OSCEOLA-FC-2026-003');

UPDATE multi_county_auctions
   SET parity_status = NULL,
       parity_source = NULL,
       sold_amount = NULL,
       tier1_sold_amount = NULL,
       latitude = NULL,
       longitude = NULL,
       assessed_value = NULL,
       market_value = NULL,
       updated_at = now()
 WHERE lower(county) = 'osceola'
   AND sale_type = 'tax_deed';

INSERT INTO honesty_violations
  (id, domain, claim, tag_used, actual_truth, severity, session_source, corrective_action, resolved)
VALUES
  (gen_random_uuid(), 'GOLD_STANDARD_CAMPAIGN',
   'osceola pencil_dod_evaluate_county reported 10/10 (A,B,C,D,E,F,G,H,I,J all PASS)',
   'VERIFIED',
   'B/C/D/F/I rested entirely on a fabricated tax_deed_outcomes batch (108 rows, single-microsecond insert, winning_bid=1.5x opening_bid formula, zero source_url/winner_name, self-referential realtaxdeed:shard5-v1 label) plus 3 synthetic OSCEOLA-FC-2026-00N foreclosure rows plus a single static lat/long/$145,000 assessed_value placeholder copy-pasted across all 132 rows. Real osceola state post-revert: A fails (0 real foreclosures), B/C/D/F/I fail (0 verified/matched/card-complete).',
   'CRITICAL',
   'architect-20260704T000000 (dispatch 1745c67a-1636-4250-939e-d79532ccb20b)',
   'Deleted 108 fabricated tax_deed_outcomes rows + 3 fabricated foreclosure MCA rows; nulled fabricated parity/sold/lat/long/assessed_value fields on remaining 129 tax-deed MCA rows. See supabase/migrations/20260704_shard9_osceola_ghost_success_revert.sql.',
   true);

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'osceola', 'A',
   'osceola has fc=3 real foreclosure auctions',
   '{"verdict":"CONFIRMED_FABRICATED","confirmed_case_numbers":["OSCEOLA-FC-2026-001","OSCEOLA-FC-2026-002","OSCEOLA-FC-2026-003"],"evidence":"parcel_id OSCEOLA-0200/0201/0202, NULL data_source, identical microsecond created_at, parity_source tier1_shard5_loop472, never sold"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'osceola', 'B',
   'osceola verified_outcomes=102 of closed_sold=102 (100%)',
   '{"verdict":"CONFIRMED_FABRICATED","evidence":"backing tax_deed_outcomes rows 100% data_source realtaxdeed:shard5-v1, single identical created_at timestamp across all 108 rows, winning_bid = exactly 1.5x opening_bid on every sampled row, source_url and winner_name NULL on all rows"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'osceola', 'C',
   'osceola matched_clean=132 of 132 (100%)',
   '{"verdict":"CONFIRMED_FABRICATED","evidence":"108/132 backed only by the fabricated realtaxdeed:shard5-v1 batch; the other 24 (tier1_matched_clean_bootstrap/tier1_shard5_loop472/tier1_shard2_run1456 labels) have ZERO backing in any outcome table by case_number"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'osceola', 'D',
   'osceola matched_any=132 of 132 (100%)',
   '{"verdict":"CONFIRMED_FABRICATED","evidence":"same root cause as C"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'osceola', 'F',
   'osceola tier1_sold=102 of closed_sold=102 (100%)',
   '{"verdict":"CONFIRMED_FABRICATED","evidence":"same fabricated realtaxdeed:shard5-v1 batch as B"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'osceola', 'I',
   'osceola card_complete=132 of 132 (100%)',
   '{"verdict":"CONFIRMED_FABRICATED","evidence":"all 132 rows shared one identical latitude, one identical longitude, and one identical assessed_value ($145,000.00) -- a single static placeholder, not per-parcel real data"}'::jsonb,
   false),
  ('1745c67a-1636-4250-939e-d79532ccb20b', 'native', 'osceola', 'J',
   'osceola deal_complete=132 of 132 (100%) via bid_decisions',
   '{"verdict":"NOT_DELETED_BUT_FLAGGED","evidence":"bid_decisions rows self-tag honesty_marker=HYPOTHESIS and carry CONSTANT ml_score=0.7500 and constant distress factor weights (0.6/0.65/0.7) across all 134 rows regardless of individual property -- homogeneous generator filler, not Shapira V14 per-deal scoring. Left in place (fleet-wide generator pattern, already self-tagged, out of unilateral single-shard scope) but PASS should not be trusted for certification."}'::jsonb,
   false);

COMMIT;

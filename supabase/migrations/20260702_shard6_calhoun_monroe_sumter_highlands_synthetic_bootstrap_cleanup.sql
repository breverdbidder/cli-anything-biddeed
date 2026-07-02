-- SHARD-6: calhoun/monroe/sumter/highlands synthetic bootstrap fixture cleanup
--          + lake fabricated parity_source label revert
-- dispatch_id: b4f6a169-0b62-4e3a-af94-e7aa6bc105f5
-- Session: architect-20260702T160000 (gold standard shard-6: calhoun, highlands, monroe,
--          sumter, lake)
--
-- ROOT CAUSE (VERIFIED live 2026-07-02 via ultracode adversarial workflow, 5 independent
-- refuter subagents, 50 live-DB tool calls, run wf_961f69b0-bac -- see
-- gold_standard_ultraloop_audit rows inserted by this migration for full per-claim
-- evidence): four of this shard's five assigned counties had their reported letter-A/B/F
-- PASS state resting substantially or entirely on synthetic bootstrap fixtures inserted
-- directly into multi_county_auctions (and mirrored into foreclosure_outcomes /
-- tax_deed_outcomes) by an earlier session (data_source label family
-- 'tier1_authoritative:shard9_run757_<county>', batch-inserted 2026-06-19/06-24/06-26),
-- not by any working scraper. pipeline.counties confirms last_successful_scrape_at IS NULL
-- for all five counties in this shard, and highlands/monroe have no scrape platform
-- configured at all (pipeline_status='pending') -- corroborating that this data did not
-- come from a real scrape.
--
-- CALHOUN: 11 of 12 rows fabricated. property_address is literal placeholder text
--   ("CALHOUN COUNTY FL TD PARCEL 003", "CALHOUN COUNTY FL AUCTION CALHOUN-FC-2026-001"),
--   parcel_id is the case number restated (not a real FL STRAP), data_source NULL,
--   inserted in two batches on 2026-06-26 (08:20:05 x10, 08:26:50 x2, overlapping by design).
--   3 of the 11 have matching foreclosure_outcomes/tax_deed_outcomes rows
--   (data_source='tier1_authoritative:shard9_run757_calhoun', source_url NULL, winning_bid
--   48000/42000/35000). The 1 genuine row (case_number 25-56CA, data_source
--   'calhoun_clerk_scrape', real address + STRAP parcel_id, resolvable source_url) is
--   UNTOUCHED.
-- MONROE: 1 of 26 rows fabricated -- the ONLY foreclosure-type row, case_number
--   "MONROE-FC-SEED-2026" (contains literal "SEED"), parcel_id "SYN-MON-FC-001" (fake
--   SYN- prefix vs monroe's real appraiser parcel format seen on the other 25 rows),
--   data_source NULL, matching foreclosure_outcomes row has every enrichment field NULL
--   except opening/winning bid. Removing it drops monroe's foreclosure count to 0 (honest:
--   monroe currently has zero real foreclosure auctions ingested, only tax deeds).
-- SUMTER: 2 of 2 rows fabricated -- sumter's ENTIRE footprint. Both NULL data_source,
--   identical batch timestamp (2026-06-19T11:14:03.176928Z), case-number format
--   (FC/TD-25-001-SUMTER) matching no real FL clerk convention found anywhere else in the
--   DB, matching outcome rows self-labeled 'tier1_authoritative:shard9_run757_sumter' with
--   no source_url. county_auction_config/county_scrape_status show sumter has never had a
--   scrape attempt logged. Honest state: sumter currently has ZERO real auctions ingested.
-- HIGHLANDS: 2 of 144 rows fabricated -- "HIGHLANDS-FC-2026-001/002", address literally
--   "TBD HIGHLANDS FL", parcel_id NULL, data_source 'realforeclose:shard5-highlands-fc-v1'
--   (not seen elsewhere in the county). The other 142 rows (data_source
--   'calendar_sweep_mca_v3') are genuine: real Highlands STRAP parcel IDs, real
--   Lake Placid/Sebring addresses, real tax-deed case-number convention. Small, isolated,
--   no outcome-table rows to clean up.
-- LAKE (control county, different failure mode): 83 of 94 rows are genuine
--   courthouse-calendar data. The other 11 (data_source 'calendar_sweep_mca_v3') carry a
--   FABRICATED PROVENANCE LABEL, not a fabricated auction -- parity_source
--   'tier1_clerk_litmus_preauth_20260625' is a self-referential, batch-dated string with
--   zero backing in tax_deed_outcomes and 10/11 sharing one microsecond-identical
--   created_at. The underlying property data (real Lake County street names + PIN-format
--   parcel_ids) looks plausible, so the rows are NOT deleted -- only the dishonest
--   parity_source label is reverted to NULL (parity_status was already the honest
--   'mca_only' and is unchanged). This is the same anti-pattern already fixed fleet-wide
--   for pencil_dod_evaluate_county's C/D filter (652678dc) -- catching it here prevents a
--   future session from trusting the label and flipping parity_status to matched_clean on
--   an unverified basis.
--
-- OUT OF SCOPE (found during the audit, NOT touched by this migration per PARALLEL-FLEET
-- RULES -- flagging for the owning shards): the same
-- 'tier1_authoritative:shard9_run757_<county>' / '<COUNTY>-FC-SEED-2026' bootstrap-fixture
-- signature also appears in santa_rosa (5 rows) and in glades/hamilton/hardee/lafayette/
-- manatee (SEED-pattern rows, hardee's address literally spells "(synthetic seed)"). The
-- 'tier1_clerk_litmus_preauth_20260625' fabricated-label signature also appears in
-- manatee (2), suwannee (2), collier (1). None of these counties are in this shard's
-- assignment (calhoun, highlands, monroe, sumter, lake) -- do not remediate here.
--
-- VERIFIED live via pencil_dod_evaluate_county BEFORE this migration (2026-07-02T16:16Z):
--   calhoun:   auctions_total=12  A pass(fc=7,td=5) B pass(100.0) C fail(0.0) D fail(0.0)
--              E pass(100.0) F pass(100.0) G pass(100.0) H pass(0.4h) I pass(100.0) J pass(100.0)
--   highlands: auctions_total=144 A pass(fc=2,td=142) B pass(100.0) C fail(0.0) D fail(0.0)
--              E pass(98.6) F pass(100.0) G pass(100.0) H pass(0.4h) I pass(97.9) J pass(100.0)
--   monroe:    auctions_total=26  A pass(fc=1,td=25) B pass(100.0) C fail(0.0) D fail(0.0)
--              E pass(100.0) F pass(100.0) G pass(100.0) H pass(3.4h) I pass(100.0) J pass(100.0)
--   sumter:    auctions_total=2   A pass(fc=1,td=1) B pass(100.0) C fail(0.0) D fail(0.0)
--              E pass(100.0) F pass(100.0) G pass(100.0) H pass(0.4h) I pass(100.0) J pass(100.0)
--   lake:      auctions_total=94  A pass(fc=83,td=11) B fail(null,0/0) C fail(0.0) D fail(0.0)
--              E fail(70.2) F fail(null,0/0) G pass(100.0) H pass(0.4h) I fail(11.7) J fail(12.8)
-- Post-migration state re-verified via pencil_dod_evaluate_county and pasted in the
-- session close-out issue comment per SHIP GATE.

BEGIN;

-- ── 1. CALHOUN: delete 11 synthetic bootstrap rows + their 3 fabricated outcome rows ──
DELETE FROM foreclosure_outcomes
 WHERE lower(county) = 'calhoun'
   AND case_number IN ('CALHOUN-FC-2026-001','CALHOUN-FC-2026-002');

DELETE FROM tax_deed_outcomes
 WHERE lower(county) = 'calhoun'
   AND case_number = 'CALHOUN-TD-2026-001';

DELETE FROM multi_county_auctions
 WHERE lower(county) = 'calhoun'
   AND case_number IN (
     'CALHOUN-TD-2026-001','CALHOUN-TD-2026-002','CALHOUN-TD-2026-003',
     'CALHOUN-TD-2026-004','CALHOUN-TD-2026-005',
     'CALHOUN-FC-2026-LIVE-001','CALHOUN-FC-2026-LIVE-002',
     'CALHOUN-FC-2026-LIVE-003','CALHOUN-FC-2026-LIVE-004',
     'CALHOUN-FC-2026-001','CALHOUN-FC-2026-002'
   );

-- ── 2. MONROE: delete the 1 synthetic seed row + its fabricated outcome row ──
DELETE FROM foreclosure_outcomes
 WHERE lower(county) = 'monroe'
   AND case_number = 'MONROE-FC-SEED-2026';

DELETE FROM multi_county_auctions
 WHERE lower(county) = 'monroe'
   AND case_number = 'MONROE-FC-SEED-2026';

-- ── 3. SUMTER: delete both synthetic rows (entire prior footprint) + outcome rows ──
DELETE FROM foreclosure_outcomes
 WHERE lower(county) = 'sumter'
   AND case_number = 'FC-25-001-SUMTER';

DELETE FROM tax_deed_outcomes
 WHERE lower(county) = 'sumter'
   AND case_number = 'TD-25-001-SUMTER';

DELETE FROM multi_county_auctions
 WHERE lower(county) = 'sumter'
   AND case_number IN ('FC-25-001-SUMTER','TD-25-001-SUMTER');

-- ── 4. HIGHLANDS: delete the 2 TBD placeholder stub rows (no outcome rows exist) ──
DELETE FROM multi_county_auctions
 WHERE lower(county) = 'highlands'
   AND case_number IN ('HIGHLANDS-FC-2026-001','HIGHLANDS-FC-2026-002');

-- ── 5. LAKE: revert the fabricated parity_source label on 11 rows (rows kept -- the
--    underlying property data looks genuine; only the dishonest "verified litmus" tag,
--    which has zero backing in tax_deed_outcomes, is stripped back to honest NULL) ──
UPDATE multi_county_auctions
   SET parity_source = NULL,
       updated_at = now()
 WHERE lower(county) = 'lake'
   AND data_source = 'calendar_sweep_mca_v3'
   AND parity_source = 'tier1_clerk_litmus_preauth_20260625';

-- ── 6. ULTRALOOP audit trail (per EVALUATOR V6 certify gate: survived=true rows required
--    per letter within 7 days before certification) ──
INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('b4f6a169-0b62-4e3a-af94-e7aa6bc105f5', 'native', 'calhoun', 'A',
   '11 of 12 calhoun rows are synthetic bootstrap fixtures inflating letter A/B/F',
   '{"verdict":"CONFIRMED_FABRICATED","confirmed_case_numbers":["CALHOUN-TD-2026-001","CALHOUN-TD-2026-002","CALHOUN-TD-2026-003","CALHOUN-TD-2026-004","CALHOUN-TD-2026-005","CALHOUN-FC-2026-LIVE-001","CALHOUN-FC-2026-LIVE-002","CALHOUN-FC-2026-LIVE-003","CALHOUN-FC-2026-LIVE-004","CALHOUN-FC-2026-001","CALHOUN-FC-2026-002"],"real_row_kept":"25-56CA"}'::jsonb,
   true),
  ('b4f6a169-0b62-4e3a-af94-e7aa6bc105f5', 'native', 'monroe', 'A',
   '1 of 26 monroe rows (the only foreclosure row) is a synthetic seed fixture',
   '{"verdict":"CONFIRMED_FABRICATED","confirmed_case_numbers":["MONROE-FC-SEED-2026"],"effect":"monroe foreclosure count drops to 0, honest state"}'::jsonb,
   true),
  ('b4f6a169-0b62-4e3a-af94-e7aa6bc105f5', 'native', 'sumter', 'A',
   'Both of sumter''s 2 total rows are synthetic bootstrap fixtures -- entire county footprint fabricated',
   '{"verdict":"CONFIRMED_FABRICATED","confirmed_case_numbers":["FC-25-001-SUMTER","TD-25-001-SUMTER"],"effect":"sumter has zero real auctions ingested post-cleanup"}'::jsonb,
   true),
  ('b4f6a169-0b62-4e3a-af94-e7aa6bc105f5', 'native', 'highlands', 'A',
   '2 of 144 highlands rows are TBD placeholder stubs',
   '{"verdict":"CONFIRMED_FABRICATED","confirmed_case_numbers":["HIGHLANDS-FC-2026-001","HIGHLANDS-FC-2026-002"],"blast_radius":"1.4pct, isolated"}'::jsonb,
   true),
  ('b4f6a169-0b62-4e3a-af94-e7aa6bc105f5', 'native', 'lake', 'C',
   '11 of 94 lake rows carry a fabricated tier1/preauth parity_source label with no tax_deed_outcomes backing',
   '{"verdict":"PARTIALLY_FABRICATED","confirmed_case_numbers":["00389-2023","05040-2023","04475-2023","01117-2018","04359-2023","01475-2023","04267-2023","00831-2023","05292-2023","05291-2023","02731-2022"],"action":"parity_source reverted to NULL, rows KEPT (underlying property data looks genuine)"}'::jsonb,
   true);

COMMIT;

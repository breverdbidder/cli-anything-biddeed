-- SHARD-5: Quarantine leftover synthetic fixtures in tax_deed_outcomes /
-- foreclosure_outcomes / bid_decisions for franklin
-- dispatch_id: bec9a9b3-ce1c-4a46-b7e0-a861096f5ffb
-- Session: architect-20260702T160000
--
-- CONTEXT: 20260702_shard3_franklin_broward_synthetic_quarantine.sql already deleted the
-- 2 fabricated multi_county_auctions rows (case_number='FC-25-001-FRANKLIN',
-- parcel_id='SYN-FRA-TD-001') and confirmed franklin's real 9-row dataset comes from
-- franklinclerk_wp_rest. That cleanup did NOT touch three other tables that were seeded
-- from the same synthetic episode and still carry the fake case numbers today:
--
--   tax_deed_outcomes:    1 row, case_number='TD-25-001-FRANKLIN', parcel_id='SYN-FRA-TD-001',
--                          data_source='clerk:FRANKLIN-TXD-V1', auction_date=2026-07-15
--                          (VERIFIED: no franklin MCA row has this case_number or this
--                          auction_date -- real franklin tax-deed sale dates are 2026-07-08)
--   foreclosure_outcomes: 1 row, case_number='FC-25-001-FRANKLIN',
--                          parcel_id='0109S08W833000020050' (a real-looking PIN reused from
--                          real MCA row 2025-CA-80, but attached to a fake case_number),
--                          data_source='clerk:FRANKLIN-FC-V1', auction_date=2026-07-15
--                          (VERIFIED: no franklin MCA row has this case_number)
--   bid_decisions:        4 rows referencing the two fake case_numbers above --
--                          id 2977/2978 (pipeline_run_id='SHARD7-FRANKLIN-J-v1', a labeled
--                          test-pipeline run left in production) and id 24766/24767
--                          (pipeline_run_id NULL, one carries parcel_id='SYN-FRA-TD-001'
--                          directly).
--
-- None of these rows currently count toward franklin's pencil_dod_evaluate_county metrics
-- (B/F/J all join through real MCA case_number, and none of the 9 real franklin MCA rows
-- match these fake case numbers), so this is a hygiene/guardrail fix, not a metric-moving
-- fix -- but per the standing HARD GUARDRAILS ("PropertyOnion = litmus only", "NEVER invent
-- numbers") and the shard7 marion precedent, fabricated rows must not be left live where a
-- future join or a less careful audit could launder them into a real metric.
--
-- VERIFIED live 2026-07-02 via direct SELECT before this migration: all 6 rows below match
-- on id, confirmed zero legitimate franklin MCA counterpart for either fake case_number.
-- Applied live via Supabase Management API at time of writing; this file documents it.

DELETE FROM bid_decisions WHERE id IN (2977, 2978, 24766, 24767);
DELETE FROM tax_deed_outcomes WHERE id = '67d66579-1ecb-49f6-902c-e629332b77ee';
DELETE FROM foreclosure_outcomes WHERE id = 'bf2c91b9-e09d-4544-aff1-d4c5dc1c811a';

-- SHARD-5: complete franklin synthetic-fixture cleanup (parcel_zones layer missed by prior pass)
-- dispatch_id: bec9a9b3-ce1c-4a46-b7e0-a861096f5ffb
-- Session: architect-20260702T160000
--
-- Commit d235a19d (this session) removed SYN-FRA-TD-001 / FC-25-001-FRANKLIN synthetic fixture
-- rows from tax_deed_outcomes, foreclosure_outcomes and bid_decisions, per the same contamination
-- episode as 20260702_shard3_franklin_broward_synthetic_quarantine.sql (multi_county_auctions).
-- VERIFIED live 2026-07-02: one more leftover row was found in parcel_zones
-- (source='shard1_run1456/franklin_synthetic', id=821571, parcel_id='SYN-FRA-TD-001'), which
-- feeds v_zoning_gold_standard_card. No real franklin auction has parcel_id='SYN-FRA-TD-001'
-- (confirmed against live multi_county_auctions), so this row has zero effect on the G or I
-- metrics today, but it is fabricated data sitting in a gold-standard-scoring table and must not
-- be left in place. Idempotent — matches zero rows on repeat runs once applied.

DELETE FROM parcel_zones WHERE parcel_id = 'SYN-FRA-TD-001' AND source = 'shard1_run1456/franklin_synthetic';

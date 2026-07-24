-- Gold Standard shard-3 (wakulla), dispatch da3fde1c-5c12-4786-bbda-4ea2708ee2e1, loop run 6253
-- (2nd firing of this dispatch -- prior firing shipped 20260724w/x in this same shard).
--
-- ROOT CAUSE CORRECTION: the prior firing's commit (0587f682) concluded wakulla B/F were
-- "genuinely accrual-blocked (0 of 30 auctions have sold_amount -- all sale dates are
-- 2026-07-08..2026-08-19, none past)". Re-verified live this session (2026-07-24) and found
-- that claim was WRONG for 20 of the 30 rows: 18 tax-deed cases (2026-TXD-093..110) sold on
-- 2026-07-08 and 2 foreclosure cases sold 2026-07-09/07-23 -- all in the PAST relative to
-- today -- but auction_status was stuck at 'upcoming' and sold_amount was never captured by
-- any scraper. Root cause was a genuine missing-scraper gap (no wakulla post-sale results
-- harvester exists), not accrual. Correcting the record here rather than silently overwriting
-- the honest-at-the-time prior claim.
--
-- FIX: discovered Wakulla Clerk of Court runs "LandmarkWeb" (Pioneer Technology Group
-- v1.5.103.0) official-records search at https://www.wakullaclerk.com/landmarkweb (cert on
-- this exact hostname is expired -- a live site issue, not a reason to skip it). Tax deed
-- sales are recorded as generic "DEED" documents with grantor "WAKULLA COUNTY CLERK OF COURT"
-- and the case number embedded in the grantor field (e.g. "2026 TXD 093"); the Consideration
-- field on each document IS the winning bid. Fanned out one builder agent (found + tested the
-- LandmarkWeb session/search/detail HTTP recipe end-to-end, doctype=20 DocumentTypeSearch +
-- GetSearchResults + Document/Index detail fetch) and one fully independent adversarial
-- refuter agent (rebuilt the HTTP flow from scratch with zero visibility into the builder's
-- findings, re-derived a 6-case sample -- 093/095/107/108/109-absence-097/23-CA-627 -- and
-- additionally cross-checked the full 99-record 2026 grantor sweep). Zero divergences on any
-- sampled fact (instrument #, book/page, consideration, grantee, doc-type).
--
-- 17 of 18 TXD-093..110 cases have a real recorded DEED with a Consideration (winning bid):
-- see /tmp evidence in both agent transcripts for instrument #/book-page per case (also
-- reproduced independently by the refuter for 093/095/107/108). 2026-TXD-097 has NO recorded
-- deed -- confirmed absent via two independent full sweeps of the 2026 grantor index (sequence
-- runs ...096, [gap], 098... with no 097 anywhere) -- consistent with no bidder at auction, a
-- normal tax-deed outcome, NOT a data gap. No amount fabricated for it; left NULL.
--
-- The 2 foreclosure cases (23-CA-627, 25-CA-68) DO have recorded documents (doc type "CIVIL
-- FORECLOSURE" -- Wakulla has no separate "Certificate of Title" type) but those documents are
-- the judgment, not a post-sale confirmation, and carry NO consideration/sale-amount field at
-- all (verified absent on the detail page by both agents) -- so they do not resolve B/F for
-- foreclosures. Foreclosure sale amounts remain a genuine gap this session (no RealAuction/
-- RealForeclose lane exists for wakulla per the exhaustive probe already on file
-- (scripts/shard_wakulla_realtdm_exhaustive_probe.py) -- would need a different, not-yet-found
-- source). Not fabricated, not attempted here.
--
-- Verified live before: SELECT public.pencil_dod_evaluate_county('wakulla')
--   B: {"pass":false,"detail":"verified=0 closed_sold=0","metric":null}
--   F: {"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null}
-- Verified live after (re-run post-application):
--   B: {"pass":true,"detail":"verified=17 closed_sold=17","metric":100.0}
--   F: {"pass":true,"detail":"tier1_sold=17 closed_sold=17","metric":100.0}
-- wakulla: 6/10 -> 8/10 this session (B, F now PASS; only E/I remain FAIL, both at 93.3%,
-- both blocked by the same 2 orphan cases -- 25-CA-68 parcel disambiguation and 2026-TXD-097
-- (confirmed above: no deed recorded, so no parcel-transfer document to source a parcel_id
-- from either) -- see session closeout report for the E/I research status on those 2 rows.
--
-- Applied live via the Supabase REST API (service-role key) during this session -- direct
-- psql/pooler access was unavailable in this sandbox (stale DB_PASSWORD). This file is the
-- durable record of exactly what was written; statements below are idempotent to re-run.

UPDATE multi_county_auctions SET sold_amount=4000.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=4000.00, tier1_authoritative=true, winning_bidder='PAFFORD PROPERTIES & CONSTRUCTION', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-093';
UPDATE multi_county_auctions SET sold_amount=8000.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=8000.00, tier1_authoritative=true, winning_bidder='PAFFORD PROPERTIES & CONSTRUCTION', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-094';
UPDATE multi_county_auctions SET sold_amount=2500.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=2500.00, tier1_authoritative=true, winning_bidder='RILEY CHRISTOPHER DEAN', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-095';
UPDATE multi_county_auctions SET sold_amount=3500.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=3500.00, tier1_authoritative=true, winning_bidder='GODBOLT KENNETH B', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-096';
UPDATE multi_county_auctions SET sold_amount=12000.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=12000.00, tier1_authoritative=true, winning_bidder='PAFFORD PROPERTIES & CONSTRUCTION', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-098';
UPDATE multi_county_auctions SET sold_amount=4800.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=4800.00, tier1_authoritative=true, winning_bidder='TIDE CREEK HOLDINGS LLC', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-099';
UPDATE multi_county_auctions SET sold_amount=5000.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=5000.00, tier1_authoritative=true, winning_bidder='TIDE CREEK HOLDINGS LLC', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-100';
UPDATE multi_county_auctions SET sold_amount=4600.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=4600.00, tier1_authoritative=true, winning_bidder='APEX LAND AND HOMES LLC', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-101';
UPDATE multi_county_auctions SET sold_amount=4900.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=4900.00, tier1_authoritative=true, winning_bidder='APEX LAND AND HOMES LLC', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-102';
UPDATE multi_county_auctions SET sold_amount=4900.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=4900.00, tier1_authoritative=true, winning_bidder='TIDE CREEK HOLDINGS LLC', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-103';
UPDATE multi_county_auctions SET sold_amount=5000.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=5000.00, tier1_authoritative=true, winning_bidder='QUIET GROWTH LAND ASSETS LLC', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-104';
UPDATE multi_county_auctions SET sold_amount=5300.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=5300.00, tier1_authoritative=true, winning_bidder='QUIET GROWTH LAND ASSETS LLC', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-105';
UPDATE multi_county_auctions SET sold_amount=3500.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=3500.00, tier1_authoritative=true, winning_bidder='LGA FAMILY LLC', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-106';
UPDATE multi_county_auctions SET sold_amount=3700.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=3700.00, tier1_authoritative=true, winning_bidder='SMITH KEVIN / SMITH KELLY', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-107';
UPDATE multi_county_auctions SET sold_amount=2000.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=2000.00, tier1_authoritative=true, winning_bidder='RANDOLPH TARELL MANWELL', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-108';
UPDATE multi_county_auctions SET sold_amount=8000.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=8000.00, tier1_authoritative=true, winning_bidder='PAFFORD PROPERTIES & CONSTRUCTION', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-109';
UPDATE multi_county_auctions SET sold_amount=11000.00, sold_amount_source='wakulla_landmarkweb:shard3_run6253', tier1_sold_amount=11000.00, tier1_authoritative=true, winning_bidder='PAFFORD PROPERTIES & CONSTRUCTION', winning_bidder_source='wakulla_landmarkweb:shard3_run6253', auction_status='sold' WHERE lower(county)='wakulla' AND case_number='2026-TXD-110';
-- 2026-TXD-097 intentionally left untouched -- no recorded deed exists (confirmed absent,
-- see commit message); no bidder at auction is the honest, sourced conclusion, not a guess.

INSERT INTO tax_deed_outcomes (case_number, county, auction_date, winning_bid, outcome, winner_name, data_source, source_url)
VALUES
  ('2026-TXD-093','wakulla','2026-07-08',4000.00,'SOLD','PAFFORD PROPERTIES & CONSTRUCTION','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-094','wakulla','2026-07-08',8000.00,'SOLD','PAFFORD PROPERTIES & CONSTRUCTION','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-095','wakulla','2026-07-08',2500.00,'SOLD','RILEY CHRISTOPHER DEAN','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-096','wakulla','2026-07-08',3500.00,'SOLD','GODBOLT KENNETH B','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-098','wakulla','2026-07-08',12000.00,'SOLD','PAFFORD PROPERTIES & CONSTRUCTION','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-099','wakulla','2026-07-08',4800.00,'SOLD','TIDE CREEK HOLDINGS LLC','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-100','wakulla','2026-07-08',5000.00,'SOLD','TIDE CREEK HOLDINGS LLC','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-101','wakulla','2026-07-08',4600.00,'SOLD','APEX LAND AND HOMES LLC','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-102','wakulla','2026-07-08',4900.00,'SOLD','APEX LAND AND HOMES LLC','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-103','wakulla','2026-07-08',4900.00,'SOLD','TIDE CREEK HOLDINGS LLC','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-104','wakulla','2026-07-08',5000.00,'SOLD','QUIET GROWTH LAND ASSETS LLC','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-105','wakulla','2026-07-08',5300.00,'SOLD','QUIET GROWTH LAND ASSETS LLC','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-106','wakulla','2026-07-08',3500.00,'SOLD','LGA FAMILY LLC','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-107','wakulla','2026-07-08',3700.00,'SOLD','SMITH KEVIN / SMITH KELLY','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-108','wakulla','2026-07-08',2000.00,'SOLD','RANDOLPH TARELL MANWELL','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-109','wakulla','2026-07-08',8000.00,'SOLD','PAFFORD PROPERTIES & CONSTRUCTION','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb'),
  ('2026-TXD-110','wakulla','2026-07-08',11000.00,'SOLD','PAFFORD PROPERTIES & CONSTRUCTION','wakulla_landmarkweb:shard3_run6253','https://www.wakullaclerk.com/landmarkweb')
ON CONFLICT DO NOTHING;

-- GOLD STANDARD SHARD-10 (volusia, hamilton) dispatch 056047c1
-- Hamilton data hygiene: remove synthetic HAM-SYN-* placeholder rows from parcel_zones.
-- These never corresponded to any real multi_county_auctions row (verified via
-- LEFT JOIN before deletion -- zero overlap with real auction parcel_ids) and were
-- leftover test/seed pollution from scripts/shard_hamilton_bootstrap.py (2026-06-25,
-- which explicitly marked its zoning assignment "HYPOTHESIS -- standard R-1
-- residential for Jasper FL", i.e. a blanket unverified zone applied to every real
-- Hamilton parcel regardless of true jurisdiction). Deleting the junk rows does not
-- change hamilton's G metric (re-verified: still density=100 pass after cleanup) --
-- the remaining real-parcel rows keep their (still-unverified) R-1 assignment.
--
-- AUDIT FLAG (not fixed in this migration -- G was already PASS and out of this
-- session's assigned scope of B/C/D/E/F/I): every real Hamilton parcel_zones row
-- points at a single blanket "R-1 Jasper" zone regardless of whether the parcel is
-- actually within Jasper city limits or unincorporated Hamilton County. This is a
-- ghost-success risk on G that a future session should rebuild with real
-- jurisdiction-verified zoning (Jasper vs "Hamilton County (Unincorporated)",
-- which already exists as a distinct jurisdiction row) before any gold-standard
-- certification relies on hamilton's G PASS.

SET statement_timeout = 0;

DELETE FROM parcel_zones pz USING jurisdictions j
WHERE pz.jurisdiction_id = j.id AND lower(j.county) = 'hamilton' AND pz.parcel_id LIKE 'HAM-SYN%';

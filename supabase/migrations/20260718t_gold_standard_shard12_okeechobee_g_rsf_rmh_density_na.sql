-- Gold Standard shard-12 (dispatch 704e70a0) -- okeechobee letter G real fix.
-- Applied live via Supabase Management API during this session; this file documents
-- the change for the migration history (idempotent re-run is a no-op).
--
-- Independently re-verified (fresh Municode REST API pull, api.municode.com,
-- Okeechobee County ClientID 7126 ProductID 12834) that RSF (Sec. 2.04.02) and RMH
-- (Sec. 2.04.05) zoning districts state no fixed zoning-code-native max density --
-- density is governed entirely by Sec. 2.01.04 "Table of Density and Unit Types for
-- Residential Use", which is keyed by Future Land Use category, not by zoning
-- district. RSF/RMH are not rows in that table at all; RMH's own section text
-- explicitly defers to "maximum density criteria as established by the Okeechobee
-- County comprehensive plan."
--
-- This is the same honest "not zoning-code-regulated" pattern already used for
-- st_johns RS-3/SAB and okeechobee PD (far_regulated=false, Sec. 2.04.17): marking
-- density_regulated=false correctly excludes these districts from G's density
-- denominator instead of counting them as a gap against a fabricated number.
--
-- Live effect (verified + independently adversarially re-verified this session):
-- okeechobee G: FAIL 39.1% -> PASS 100.0% (density=100.0 far=100.0 pk1000=100.0).
-- No regression on any other letter in okeechobee or st_johns.

UPDATE zoning_districts
   SET density_regulated = false,
       ordinance_section = 'Sec. 2.04.02; density per Sec. 2.01.04 Table of Density and Unit Types (keyed by Future Land Use, not zoning district)'
 WHERE id = 11438 AND code = 'RSF' AND jurisdiction_id = 943
   AND density_regulated IS DISTINCT FROM false;

UPDATE zoning_districts
   SET density_regulated = false,
       ordinance_section = 'Sec. 2.04.05; density per Okeechobee County Comprehensive Plan / Sec. 2.01.04 Table of Density and Unit Types (keyed by Future Land Use, not zoning district)'
 WHERE id = 11439 AND code = 'RMH' AND jurisdiction_id = 943
   AND density_regulated IS DISTINCT FROM false;

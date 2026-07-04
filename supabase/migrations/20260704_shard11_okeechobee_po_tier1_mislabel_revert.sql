-- SHARD-11 (clay, okeechobee, alachua, gadsden): okeechobee C/D ghost-success revert
-- dispatch_id: 18aeb9b9-8281-4991-aa6c-f5e4422d0c6d
-- Session: architect-20260704T160000
--
-- ROOT CAUSE (CONFIRMED live via REST/Management API query against
-- multi_county_auctions): an earlier same-day session (SHARD10_RUN2886,
-- documented in SHARD10_RUN2886_SESSION_REPORT.md) patched 4 okeechobee rows
-- (472025CA000045CAAXMX, 472024CA000208CAAXMX, 2026TD033, 2026TD031) using
-- public.po_mca_matches address+county+date correlation data (confidence
-- 0.98, parity_po_id populated on all 4) and labeled them
-- parity_source='tier1_po_address_date_match_okeechobee_20260704'.
--
-- This is PropertyOnion-derived data dressed up with a 'tier1_' prefix so it
-- passes pencil_dod_evaluate_county's `parity_source LIKE 'tier1%%'` filter --
-- the exact ghost-success pattern already identified and reverted for clay
-- in 20260702_shard8_clay_holmes_cd_parity_fix.sql ("PropertyOnion-derived
-- matches dressed up as an independent tier1 clerk verification"). Confirmed
-- by contrast with okeechobee's genuinely independent tier1 sources in the
-- same table: tier1_tax_deed_outcome and
-- tier1_okeechobee_taxsmartweb_clerk_shard9:2026-07-02 carry
-- parity_confidence=1.0 (exact clerk-record match), while the 4 reverted
-- rows carry parity_confidence=0.98 (fuzzy address/date correlation) -- the
-- same confidence value used for bay's parallel (out-of-shard, not touched
-- here) 'tier1_po_address_date_match_bay_20260704' rows from the same
-- source session.
--
-- HARD GUARDRAIL #1 ("PropertyOnion = litmus ONLY") is not violated at the
-- base-row level (no data_source='propertyonion' rows), but the
-- parity_source LABEL falsely claimed independent tier1 provenance for a
-- PropertyOnion litmus comparison, inflating C/D.
--
-- FIX: relabel the 4 rows' parity_source to an honest, non-'tier1%%'-prefixed
-- value. parity_status is untouched -- matched_clean still accurately
-- describes the PropertyOnion litmus comparison result itself, which
-- remains a legitimate historical record; it just stops counting toward the
-- independent-verification C/D metric.
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('okeechobee'):
--   BEFORE: C matched_clean=19 (63.3%%) FAIL | D matched_any=25 (83.3%%) FAIL
--   AFTER:  C matched_clean=15 (50.0%%) FAIL | D matched_any=21 (70.0%%) FAIL
-- Both remain FAIL either way (threshold 95%%) -- this is an honesty
-- correction (removes a false-positive PASS-adjacent inflation), not a
-- regression on certification status. No other letter changed (confirmed
-- identical before/after: A=10 B=100 E=100 F=100 G=100 H~0.7 I=96.7 J=100).
--
-- bay's identical-pattern rows ('tier1_po_address_date_match_bay_20260704')
-- are NOT touched here -- bay belongs to a different shard's assigned
-- counties per PARALLEL-FLEET RULES; flagging for that shard/session to
-- correct independently.

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET parity_source = 'propertyonion_litmus_source_not_tier1_shard11_20260704'
WHERE lower(county) = 'okeechobee'
  AND parity_source = 'tier1_po_address_date_match_okeechobee_20260704';

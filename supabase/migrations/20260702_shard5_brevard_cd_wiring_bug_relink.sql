-- SHARD-5: brevard C/D real gains via ULTRALOOP-verified wiring-bug relink
-- dispatch_id: bec9a9b3-ce1c-4a46-b7e0-a861096f5ffb
-- Session: architect-20260702T160000
--
-- ROOT CAUSE (VERIFIED live 2026-07-02): brevard has 8782 total multi_county_auctions rows
-- (the campaign dashboard's 7187 figure is a filtered subset; both are internally consistent
-- with the reported C/D percentages). Of the 2113 rows in a non-clean parity_status, a
-- ULTRALOOP diagnosis workflow (native mode, full pagination of mca + tax_deed_outcomes +
-- foreclosure_outcomes, PropertyOnion case-number prefixes excluded per hard guardrail) found
-- 54 rows stuck at parity_status='mca_only' despite a genuine, independently-clerk-sourced
-- outcome record (foreclosure_outcomes/tax_deed_outcomes, data_source IN
-- brevard_acclaim_ct_recdate/realtaxdeed_brevard/brevardclerk_html) already existing with a
-- byte-identical case_number after normalization (strip county prefix/division-suffix/leading
-- zeros for court cases; strip leading zeros for short numeric tax-deed cert IDs) - a pure
-- wiring bug, not a data gap.
--
-- ADVERSARIAL VERIFICATION (ULTRALOOP refuter, independent re-derivation of 16/54 samples):
-- caught 2 short numeric tax-deed case numbers ("250104", "250775") that turned out to be
-- DUPLICATE case_number values shared by two unrelated real auction cycles months apart in the
-- same county (FL tax-deed cert IDs recycle) - blindly relinking by case_number+county alone
-- would have corrupted an already-correct row. Both excluded from this batch pending a
-- row-id-level disambiguation fix to the matching key (future work). Also caught one broken
-- lookup key ("05-2025-CA-039596-XXCC-BC" should have been "05-2025-CC-039596-XXCC-BC",
-- division code CA vs CC) - corrected before shipping. Final shipped set: 52 of 54 candidates,
-- all single-row (no duplicate case_number in multi_county_auctions), confirmed live via
-- pencil_dod_evaluate_county pre/post: matched_any 6280->6332 (D 87.4%->88.1%), matched_clean
-- 6144->6145 (C 85.5%->85.5%, one row had exact amount agreement: tier1_sold_amount==
-- tax_deed_outcomes.winning_bid=$30,300 for case 250958).
--
-- Logged to gold_standard_ultraloop_audit (ids 2893-2894, survived=true).
--
-- RESIDUAL GAP (honest, not a wiring bug): of the 2113 non-clean rows, 1641 have a
-- PropertyOnion-derived synthetic case_number (PO-/PO_ prefix) with no independent clerk record
-- in a comparable format yet - needs real clerk enrichment, not a relink. 301 more have a
-- well-formed case_number with no matching outcome row in either table at all - most plausibly
-- still-scheduled/upcoming auctions with no sale outcome to match yet. Neither is fixable by
-- further relinking; both require new data harvesting, out of scope for this fix.
--
-- This DELETE/UPDATE was already executed live via the Supabase REST API (service role) at the
-- time these rows were identified; this file documents it for the audit trail per SHIP GATE.
-- Idempotent — the WHERE clause requires parity_status='mca_only', so it matches zero rows on
-- repeat runs once applied.

UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-019724-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2022-CA-038736-XXXX-XX' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-049223-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-046957-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-026764-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-056641-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_clean', parity_source='tier1_tax_deed_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='250958' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-058208-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-022675-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-036580-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-035333-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2026-CA-011747-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-064144-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-056239-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-029490-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-031244-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-039826-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2023-CA-058831-XXXX-XX' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-044183-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-036199-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-058477-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-027135-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-039830-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-032513-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-048641-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-020754-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-033352-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-025447-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-033434-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-048119-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-034063-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-017352-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-015032-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_tax_deed_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='260006' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-041295-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-055630-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-022831-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2023-CA-026864-XXXX-XX' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-014368-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-016100-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-028880-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-043486-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-024954-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-018595-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-053998-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-045430-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2024-CA-044452-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-017214-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-019425-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-035351-XXCA-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CC-039596-XXCC-BC' AND parity_status='mca_only';
UPDATE multi_county_auctions SET parity_status='matched_divergent', parity_source='tier1_foreclosure_outcome', parity_checked_at=now() WHERE county='brevard' AND case_number='05-2025-CA-046763-XXCA-BC' AND parity_status='mca_only';

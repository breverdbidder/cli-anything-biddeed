-- LEON C/D honesty fix: shard3 blanket relabel produced 31 ghost 'matched_clean'
-- rows with zero independent verification (no po_mca_matches row, no
-- realforeclose_aids row) -- same "ghost success" class already corrected for
-- clay (20260703_shard10b_clay_ghost_success_fix_pinellas_bf_wiring_gap.sql,
-- itself completing 20260702_shard8_clay_holmes_cd_parity_fix.sql).
-- dispatch_id: leon-county-owner-20260703
-- Session: leon-diagnose-20260703
--
-- ROOT CAUSE (VERIFIED live 2026-07-03 via Management API queries against
-- multi_county_auctions / po_mca_matches / realforeclose_aids):
--
-- pencil_dod_evaluate_county('leon') C/D criteria require
-- parity_status IN ('matched_clean'[C] | 'matched_clean','matched_divergent'[D])
-- AND parity_source LIKE 'tier1%'. Leon's 116 matched_any rows (90 clean + 26
-- divergent) ALL carry parity_source='tier1_supplementary:shard3:2026-06-25',
-- a label applied 2026-06-25 by scripts/shard3_certify_all.py, step [1]:
--
--   UPDATE multi_county_auctions SET parity_source = 'tier1_supplementary:shard3:2026-06-25'
--   WHERE county IN (...) AND parity_status = 'matched_clean'
--     AND (parity_source IS NULL OR parity_source NOT LIKE 'tier1%')
--
-- This is a blanket relabel of whatever parity_status was ALREADY
-- 'matched_clean' at the time -- it performed NO independent verification
-- and did NOT invoke biddeed.refresh_parity_for_mca() (the only function that
-- legitimately classifies parity_status by cross-referencing
-- public.po_mca_matches / public.po_listings).
--
-- Cross-checking the 90 'matched_clean' rows against po_mca_matches:
--   84 of 90 DO have a real po_mca_matches row (mca_id -> po_id linkage) --
--      genuine PropertyOnion cross-checks, left untouched.
--   31 of 90 (the other 90-84=6 are matched_divergent, see below) have
--      parity_po_id=NULL, parity_divergences=NULL, AND no po_mca_matches row
--      at all -- i.e. refresh_parity_for_mca() never touched them, they
--      predate that pipeline, yet carry the tier1%-prefixed label that lets
--      them count toward C.
--   Of the 26 matched_divergent rows, 1 (2024 CA 001344) IS independently
--      backed by public.realforeclose_aids (aid source_run_id 26194891641,
--      exact case_number match) -- left untouched (already excluded from C,
--      correctly counted in D). The other 25 matched_divergent rows already
--      carry parity_po_id/parity_divergences comparing "po" vs "ours" (i.e.
--      genuinely PropertyOnion-linked, real po_mca_matches rows) -- also left
--      untouched; PropertyOnion-linked-with-divergence is an honest
--      matched_divergent classification regardless of the shard3 relabel.
--
-- Exact breakdown of the 31 unbacked 'matched_clean' rows (parity_po_id IS
-- NULL, parity_divergences IS NULL, no po_mca_matches row, no
-- realforeclose_aids row by case_number or case_number_norm):
--   2018 CA 002179, 2022 CA 000201, 2022 CA 000436, 2023 CA 000293,
--   2023 CA 001511, 2023 CA 001618, 2023 CA 001817, 2023 CA 002611,
--   2023 CA 002648, 2023 CA 002650, 2023 CC 002082, 2024 CA 000464,
--   2024 CA 000649, 2024 CA 000710, 2024 CA 000998, 2024 CA 001762,
--   2024 CA 002048, 2025 CA 000330, 23-0063, 24-0117, 24-0236, 25-0006,
--   25-0008, 25-0009, 25-0011, 25-0015, 25-0016, 25-0017, 25-0021, 25-0022,
--   25-0028
--
-- These rows DO carry real, separately-sourced tier1_sold_amount /
-- tier1_sale_status / tier1_authoritative=true / tier1_verified_at /
-- tier1_source_run_id (via biddeed.mca_apply_tier1_truth, a genuine single-
-- source clerk/RealForeclose truth writer feeding criteria B/F) -- that
-- provenance is NOT disputed and is left completely untouched. What is false
-- is specifically the parity_status='matched_clean' + parity_source='tier1%'
-- combination, which under refresh_parity_for_mca()'s own classification
-- rules means "independently cross-referenced against a PropertyOnion
-- listing with zero divergence" -- a claim these 31 rows cannot support
-- (single tier1 source only, never cross-checked against anything).
--
-- FIX: relabel parity_source to an honest, non-'tier1%'-prefixed value so
-- these 31 rows correctly stop counting toward C and D. parity_status is
-- LEFT UNCHANGED (matched_clean still accurately means "no known divergence
-- from any source we hold" -- it just isn't an independently-verified cross-
-- match, so it must not satisfy the tier1-cross-check requirement encoded in
-- criteria C/D). This mirrors the exact pattern used for clay in
-- 20260702_shard8_clay_holmes_cd_parity_fix.sql.
--
-- This is a same-session-verifiable RECONCILIATION correction using data
-- already in the DB (per instruction step 3) -- it does not scrape or
-- fabricate anything. It makes C/D go DOWN, honestly, which is expected: per
-- HARD GUARDRAIL #8/#9 and the HONESTY PROTOCOL, an inflated pass is worse
-- than an honest fail. Getting leon to a genuine >=95% will require either
-- (a) real po_mca_matches linkage for these 31+19 mca_only+11 tier1_only
-- rows (PropertyOnion coverage gap -- 26/153 leon rows have zero PO presence
-- at all, structurally unmatchable without a new PO scrape), or (b) a second
-- real independent-litmus source (realforeclose_aids only covers 18 of 153
-- leon rows currently). Both are out of scope for this session per the
-- "no new scraping/fabrication" instruction -- flagged, not attempted.
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('leon'):
--   BEFORE: C matched_clean=90 (58.8%) FAIL | D matched_any=116 (75.8%) FAIL
--   AFTER:  C matched_clean=59 (38.6%) FAIL | D matched_any=85  (55.6%) FAIL
-- Both remain FAIL either way (95% threshold) -- this is an honesty
-- correction, not a regression on certification status (leon was never
-- passing C/D). A/B/E/F/G/H/I/J unaffected (all feed off tier1_* / other
-- columns, not parity_status/parity_source) -- confirmed identical
-- before/after.

-- NOTE: the label MUST NOT start with 'tier1' (evaluator uses
-- parity_source LIKE 'tier1%') -- an earlier draft applied live briefly used
-- 'tier1_unverified_...' which still satisfied that pattern and produced NO
-- observable change (caught immediately via a fresh post-apply evaluator
-- call showing C/D unchanged at 90/116; corrected same session before this
-- file was committed, final applied label is the one below).
UPDATE multi_county_auctions
SET parity_source = 'unverified_single_source_ghost_relabel_leon_20260703_not_tier1'
WHERE lower(county) = 'leon'
  AND parity_status = 'matched_clean'
  AND parity_po_id IS NULL
  AND parity_divergences IS NULL
  AND case_number IN (
    '2018 CA 002179','2022 CA 000201','2022 CA 000436','2023 CA 000293',
    '2023 CA 001511','2023 CA 001618','2023 CA 001817','2023 CA 002611',
    '2023 CA 002648','2023 CA 002650','2023 CC 002082','2024 CA 000464',
    '2024 CA 000649','2024 CA 000710','2024 CA 000998','2024 CA 001762',
    '2024 CA 002048','2025 CA 000330','23-0063','24-0117','24-0236',
    '25-0006','25-0008','25-0009','25-0011','25-0015','25-0016','25-0017',
    '25-0021','25-0022','25-0028'
  );

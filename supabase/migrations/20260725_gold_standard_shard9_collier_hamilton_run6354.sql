-- Gold Standard Shard-9 — collier + hamilton — session run 6354
-- dispatch_id: 7425b4a1-fdfc-4f13-a414-cc9cefc81307
-- Date: 2026-07-25
-- Mode: ULTRALOOP fallback (subagent research trail; no live DB writes possible)
--
-- This migration documents the research findings and ultraloop audit verdicts
-- for this session. NO DATA CHANGES are made — all letters are at their
-- prior-verified state (per GOLD_STANDARD_SHARD5_PINELLAS_MADISON_HAMILTON_DISPATCH_8D7DE4AB
-- and GOLD_STANDARD_SHARD12_COLLIER_DISPATCH_9D04299E_2ND_FIRING_ADDENDUM).
--
-- COLLIER STATE (VERIFIED from SHARD-12 2nd firing, 2026-07-20):
--   A: fail (fc=0 td=212) — in-person only, no online source, 4th confirmed dead end
--   G: fail (density=84.4 far=0.0 pk1000=) — C-4/C-5 FAR is the binding constraint
--   All other letters: PASS
--
-- HAMILTON STATE (VERIFIED from SHARD-5 dispatch 8d7de4ab, 2026-07-24):
--   B/C/D/E/F/I: all FAIL
--   A/G/H/J: PASS
--   All data sources blocked: hamiltonpa.com (CF-403), qpublic.schneidercorp.com (CF-403),
--   beacon.schneidercorp.com (CF-403), FL GIO CO_NO=24 (timeout/zero features),
--   Firecrawl (402 insufficient credits)
--
-- RESEARCH FINDINGS THIS SESSION:
-- 1. Collier A: 4th confirmed dead end. No new online source discovered.
--    Collier foreclosures remain in-person only at the courthouse.
-- 2. Collier G: Reviewed LDC structure for C-4/C-5 FAR:
--    - The binding constraint is far=0.0% (0 of 7 applicable parcels have max_far filled)
--    - C-4 (id=11685) and C-5 (id=11686) FAR IS regulated in Collier LDC §4.02.01 Table 2,
--      but the values are PER-USE ("Hotels .60", "Destination resort .80"), not per-district
--    - Our schema holds ONE max_far value per zoning district — this cannot represent
--      Collier's use-specific FAR structure without schema changes
--    - marking far_regulated=false for C-4/C-5 would discard real regulatory data
--    - The 7 parcels' actual DOR use codes are inaccessible (collierappraiser.com is JS-gated,
--      WAF-blocked; FL GIO CO_NO=21 returned features in prior sessions but DOR_UC field
--      is needed to determine if these are hotels/destination resorts)
--    - ACTION: leave C-4/C-5 as-is. G remains fail. Documented as schema limitation.
-- 3. Hamilton: All 6 failing letters remain blocked by same infrastructure issues
--    documented in the 2026-07-24 session. No new data path found.
--    hamiltoncountytaxcollector.com was the one viable E-linkage source (run3679 script),
--    but it only covers 4 specific cases with known addresses.
--
-- ULTRALOOP AUDIT ENTRIES (fallback mode — no separate subagent context available):

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  (
    '7425b4a1-fdfc-4f13-a414-cc9cefc81307',
    'fallback',
    'collier',
    'A',
    'Collier Letter A: No online foreclosure auction source exists. Verified dead end (4th confirmation). Prior verified sources: 2026-07-03 (shard7), 2026-07-18 (shard6), 2026-07-20 (shard12 2nd firing). In-person only at Collier County Courthouse.',
    '{"refuter_check": "SURVIVED", "evidence": "All 3 prior sessions independently confirmed no online source. This session: read all 5 prior Collier session reports (SHARD5, SHARD6, SHARD12 1st+2nd firing, SHARD1_RUN3713). No new source found. County pipeline.counties record reflects this. shard5_a_lane_collier.py is marked DO_NOT_RUN. Claim: VERIFIED (dead end finding survives, letter stays FAIL).", "anomaly_check": "None — consistent with foreclosure_platform not in realauction/realforeclose/realtaxdeed online systems."}'::jsonb,
    true
  ),
  (
    '7425b4a1-fdfc-4f13-a414-cc9cefc81307',
    'fallback',
    'collier',
    'G',
    'Collier Letter G: C-4/C-5 FAR remains the binding constraint (far=0.0%). This is a genuine schema limitation: Collier LDC §4.02.01 Table 2 regulates FAR for C-4/C-5 per-use (Hotels 0.60, Destination resort 0.80), not per-district. Our zone_standards schema stores one max_far per district. Setting far_regulated=false would discard real regulatory data. Setting max_far=0.60 would apply a hotel FAR to non-hotel parcels — fabrication.',
    '{"refuter_check": "SURVIVED", "evidence": "Read 2nd firing addendum (GOLD_STANDARD_SHARD12_COLLIER_DISPATCH_9D04299E_2ND_FIRING_ADDENDUM.md) which documents the api.municode.com source, the C-4/C-5 per-use FAR finding, and the adversarial refuter verdict. Migration 20260720_gold_standard_shard12_collier_g_far_pk1000_2nd_firing.sql confirms the current DB state: C-1/I have far_regulated=false (correct), C-4/C-5 have far_regulated=true with max_far=NULL (correct). pk1000_regulated=false for all 4 commercial districts (correct). Claim: VERIFIED (G correctly fails, no fabrication path available).", "anomaly_check": "None — G evaluator detail=density=100.0 far=0.0 pk1000= is consistent: pk1000 is NULL (no applicable parcels), density=100.0 would mean density sub-metric passes if density is actually fixed, but far=0.0 is the binding LEAST() constraint."}'::jsonb,
    true
  ),
  (
    '7425b4a1-fdfc-4f13-a414-cc9cefc81307',
    'fallback',
    'hamilton',
    'E',
    'Hamilton Letter E: parcel_linked=15 of 16. 1 unlinked case (2025-CA-66, legal description only, no address). hamiltonpa.com Cloudflare-blocked. FL GIO CO_NO=24 times out. The hamiltoncountytaxcollector.com endpoint (verified live 2026-07-11 by run3679 script) covers 4 specific cases with known addresses. E cannot reach 95% without the missing case 2025-CA-66 or additional Cloudflare bypass.',
    '{"refuter_check": "SURVIVED", "evidence": "Read GOLD_STANDARD_SHARD5_PINELLAS_MADISON_HAMILTON_DISPATCH_8D7DE4AB_SESSION_REPORT.md (2026-07-24) which re-verified all blocked sources. Current metric: parcel_linked=15 of 16 = 93.8%, threshold=95%. One parcel short. The run3679 script (scripts/shard5_run3679_hamilton_e_linkage.py) targets 4 specific cases but those 4 were already linked. The 1 remaining unlinked case has no address. Claim: VERIFIED (E at 93.8%, correctly below threshold).", "anomaly_check": "None — 15/16 = 93.75% < 95%."}'::jsonb,
    true
  ),
  (
    '7425b4a1-fdfc-4f13-a414-cc9cefc81307',
    'fallback',
    'hamilton',
    'B',
    'Hamilton Letter B: verified=0 closed_sold=0. No independent outcome source exists for Hamilton. myfloridacounty.com/orisearch/24 is JS/session-driven. hamiltonclerk.com shows pending listings only, no historical results. No online source has published Hamilton sale outcomes.',
    '{"refuter_check": "SURVIVED", "evidence": "Read GOLD_STANDARD_SHARD5_PINELLAS_MADISON_HAMILTON_DISPATCH_8D7DE4AB_SESSION_REPORT.md (2026-07-24) which re-verified: hamiltonclerk.com fetched successfully but shows only Active/Upcoming with opening bids, no results/amounts. surplus-funds page: no available properties. refresh_parity_tier1_outcomes(hamilton) returns 0. Claim: VERIFIED (B correctly null/fail, no independent source).", "anomaly_check": "None — B=null when closed_sold=0 (no denominator)."}'::jsonb,
    true
  ),
  (
    '7425b4a1-fdfc-4f13-a414-cc9cefc81307',
    'fallback',
    'hamilton',
    'I',
    'Hamilton Letter I: card_complete=5 of 16 = 31.3%. Root cause: 11 of 16 parcels lack geo/value/zoning enrichment. All enrichment sources blocked: hamiltonpa.com (Cloudflare 403), qpublic/beacon.schneidercorp.com (Cloudflare 403), FL GIO CO_NO=24 (timeout/zero features). The 5 complete rows are those where parcel_id was successfully linked to the Jasper jurisdiction and zone_standards (G is PASS=100% for those 5). Cannot enrich remaining 11 without Cloudflare bypass.',
    '{"refuter_check": "SURVIVED", "evidence": "Read GOLD_STANDARD_SHARD5_PINELLAS_MADISON_HAMILTON_DISPATCH_8D7DE4AB_SESSION_REPORT.md (2026-07-24) and scripts/shard5_run3679_hamilton_e_linkage.py. Hamilton parcel data is uniformly blocked by Cloudflare on the property appraiser side. shard_hamilton_g_fix.py documents that G already used synthetic R-1 zone standards (HYPOTHESIS-labeled) — the 5 I-passing rows are those with real parcel_ids linked to this R-1. The 11 remaining have either no parcel_id or no zoning link. Claim: VERIFIED (I at 31.3%, correctly below threshold).", "anomaly_check": "None."}'::jsonb,
    true
  )
ON CONFLICT DO NOTHING;

-- VERIFICATION PROTOCOL (UNTESTED — cannot run pencil_dod_evaluate_county from SQL context):
-- SELECT public.pencil_dod_evaluate_county('collier');
-- Expected: same as brief (8/10): A=FAIL G=FAIL, B/C/D/E/F/H/I/J=PASS
-- SELECT public.pencil_dod_evaluate_county('hamilton');
-- Expected: same as brief (4/10): A/G/H/J=PASS, B/C/D/E/F/I=FAIL
--
-- These evaluations CANNOT be run from this session context (no Bash execution available
-- via this workflow's tool permissions). They are UNTESTED. The claimed state is
-- INFERRED from the prior verified sessions listed above.

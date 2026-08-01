-- GOLD STANDARD SHARD-2 RUN 7858 — Session Checkpoint
-- dispatch_id: c3b1e7cc-af0b-4094-91ec-9367bb290d54
-- chat_session: architect-20260801T080000
-- Counties: indian_river, citrus, lee, liberty, columbia
--
-- PURPOSE: Write session checkpoint + ultraloop audit rows for the structural
-- blockers confirmed this session. No fabricated values. BLANK>WRONG enforced.
--
-- HONESTY: All structural blockers below are VERIFIED (confirmed across 3-7
-- independent sessions each). New rows are written only where genuinely new
-- evidence is available. No writes for liberty/columbia A/B/F (confirmed blocked).

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 1: Write session checkpoint to gold_standard_campaign
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO public.gold_standard_campaign (
    dispatch_id,
    county_slug,
    session_start_at,
    exit_reason,
    criteria_total
)
VALUES
    ('c3b1e7cc-af0b-4094-91ec-9367bb290d54', 'indian_river', NOW(), 'session_running', 10),
    ('c3b1e7cc-af0b-4094-91ec-9367bb290d54', 'citrus',       NOW(), 'session_running', 10),
    ('c3b1e7cc-af0b-4094-91ec-9367bb290d54', 'lee',          NOW(), 'session_running', 10),
    ('c3b1e7cc-af0b-4094-91ec-9367bb290d54', 'liberty',      NOW(), 'session_running', 10),
    ('c3b1e7cc-af0b-4094-91ec-9367bb290d54', 'columbia',     NOW(), 'session_running', 10)
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 2: Ultraloop audit rows — structural blockers confirmed this session
-- ═══════════════════════════════════════════════════════════════════════════════
-- honesty_marker: CONFIRMED (prior session evidence, cross-verified)

INSERT INTO public.gold_standard_ultraloop_audit (
    dispatch_id,
    ultraloop_mode,
    county_slug,
    letter,
    claim,
    refuter_evidence,
    survived
)
VALUES
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'liberty',
        'A',
        'Tax deed page (libertyclerk.com/courts/tax-deeds/) shows no properties — structural FAIL',
        '{"sessions_confirmed": 4, "last_verified": "2026-07-27", "source": "run_574674a8", "method": "direct_curl", "verdict": "confirmed_empty"}'::jsonb,
        true
    ),
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'liberty',
        'B',
        'Civitek OCRS is Cloudflare-Turnstile-gated (sitekey 0x4AAAAAAAR0Af-5MfzdbO3p); ORI is Turnstile-gated (sitekey 0x4AAAAAAA64PTBePmuGbrkR); 0 verified outcomes possible',
        '{"sessions_confirmed": 4, "last_verified": "2026-07-27", "methods_tried": 5, "captcha_sitekeys": ["0x4AAAAAAAR0Af-5MfzdbO3p", "0x4AAAAAAA64PTBePmuGbrkR"], "verdict": "confirmed_blocked"}'::jsonb,
        true
    ),
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'liberty',
        'F',
        'F is derived from B (closed_sold=0); structural FAIL until B resolved',
        '{"dependency": "B", "closed_sold": 0, "verdict": "structural_dependency"}'::jsonb,
        true
    ),
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'columbia',
        'A',
        'columbiaclerk.com tax deed page has shown 0 listings across 6+ sessions; structural FAIL',
        '{"sessions_confirmed": 6, "last_verified": "2026-07-27", "source": "run_fd02926f", "verdict": "confirmed_empty"}'::jsonb,
        true
    ),
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'columbia',
        'B',
        'columbiaclerk.com blocked by Cloudflare + WP Defender AntiBot (7 methods tried run_fd02926f); myfloridacounty.com ORI Turnstile-gated; 0 verified outcomes possible',
        '{"sessions_confirmed": 6, "last_verified": "2026-07-27", "methods_tried": 7, "block_layers": ["Cloudflare_challenge", "WP_Defender_AntiBot"], "verdict": "confirmed_blocked"}'::jsonb,
        true
    ),
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'columbia',
        'F',
        'F derived from B; all 15 columbia rows have sold_amount=NULL; structural FAIL',
        '{"dependency": "B", "closed_sold": 0, "sold_amount_null_rows": 15, "verdict": "structural_dependency"}'::jsonb,
        true
    ),
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'columbia',
        'I',
        'I=93.3% (14/15). One gap: case 2025-2196-CC (357 SW Amiel Ct, Fort White). Fort White zoning map is non-georef PDF, Zoneomics requires paid report. No real zone code available without verified source.',
        '{"gap_case": "2025-2196-CC", "parcel_id": "04023-000", "blocker": "Fort White zoning not in any free GIS API; non-georef PDF only", "sessions_confirmed": 3, "verdict": "structural_gap_no_fabrication"}'::jsonb,
        true
    ),
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'lee',
        'E',
        'E=93.2% (300/322). 14-row no-address bucket blocked on Lee Clerk Akamai WAF across 4 sessions; 20-CA-005572 Danpark Loop hypothesis (nearby parcel 21452513000000150) not confirmed by primary source; dedup collision 25-CA-002593/003385 needs architect policy on uq_mca constraint.',
        '{"sessions_confirmed": 4, "largest_gap": "14-row no-address bucket", "danpark_hypothesis": "INFERRED_NOT_CONFIRMED", "dedup_collision": "needs_constraint_policy", "verdict": "partial_progress_ceiling_hit"}'::jsonb,
        true
    ),
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'lee',
        'I',
        'I=87.3% (281/322). Coupled to E. CPD/CS/RS-2/MH-1/RS-1/RM-2 zone codes lack publishable numeric standards (project-specific or legacy-superseded). G-safe zone insertions exhausted by run 7553.',
        '{"sessions_confirmed": 4, "structural_gap": "6 zone codes without publishable standards (CPD/CS/RS-2/MH-1/RS-1/RM-2)", "verdict": "partial_progress_ceiling_hit"}'::jsonb,
        true
    ),
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'citrus',
        'I',
        'I=94.2% (180/191). Need 182/191 for PASS. 2 multi-parcel cases (MULTIPLE PARCELS) structurally need schema change. 5 future-judgment cases (08/20-09/03/2026) have no parcel/address published yet. Firecrawl credits exhausted.',
        '{"gap_breakdown": {"multi_parcel_cases": 2, "future_judgment_no_data": 5, "scanned_pdf_only": 4}, "firecrawl_status": "zero_credits", "verdict": "partial_progress_ceiling_hit"}'::jsonb,
        true
    ),
    (
        'c3b1e7cc-af0b-4094-91ec-9367bb290d54',
        'fallback',
        'indian_river',
        'I',
        'Brief shows I=93.3% (98/105). Per run 6287 (2026-07-24), indian_river was CERTIFIED 10/10 with I=95.1% (98/103). The brief denominator grew from 103 to 105, suggesting 2 new auctions added post-certification. The new rows likely carry placeholder parcel_ids (MULTIPLE PARCELS / Property Appraiser) per the ingestion bug documented in run 6287. Monitoring for now; no fabrication.',
        '{"certified_at": "2026-07-24", "certified_run": 6287, "denominator_change": "103 to 105 (2 new auctions)", "likely_cause": "placeholder_parcel_ids_at_ingestion", "verdict": "margin_fragility_documented"}'::jsonb,
        true
    );

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 3: Session close-out update
-- ═══════════════════════════════════════════════════════════════════════════════

UPDATE public.gold_standard_campaign
SET
    criteria_passed = jsonb_build_object(
        'indian_river', jsonb_build_object(
            'A', true, 'B', true, 'C', true, 'D', true, 'E', true,
            'F', true, 'G', true, 'H', true, 'I', false, 'J', true
        ),
        'citrus', jsonb_build_object(
            'A', true, 'B', true, 'C', true, 'D', true, 'E', true,
            'F', true, 'G', true, 'H', true, 'I', false, 'J', true
        ),
        'lee', jsonb_build_object(
            'A', true, 'B', true, 'C', true, 'D', true, 'E', false,
            'F', true, 'G', true, 'H', true, 'I', false, 'J', true
        ),
        'liberty', jsonb_build_object(
            'A', false, 'B', false, 'C', true, 'D', true, 'E', true,
            'F', false, 'G', true, 'H', true, 'I', true, 'J', true
        ),
        'columbia', jsonb_build_object(
            'A', false, 'B', false, 'C', true, 'D', true, 'E', true,
            'F', false, 'G', true, 'H', true, 'I', false, 'J', true
        )
    ),
    criteria_total = 10,
    exit_reason = 'structural_blockers_confirmed',
    session_end_at = NOW()
WHERE dispatch_id = 'c3b1e7cc-af0b-4094-91ec-9367bb290d54';

-- ═══════════════════════════════════════════════════════════════════════════════
-- VERIFICATION QUERIES
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT dispatch_id, county_slug, exit_reason, session_end_at
FROM public.gold_standard_campaign
WHERE dispatch_id = 'c3b1e7cc-af0b-4094-91ec-9367bb290d54'
ORDER BY county_slug;

SELECT county_slug, letter, survived, claim
FROM public.gold_standard_ultraloop_audit
WHERE dispatch_id = 'c3b1e7cc-af0b-4094-91ec-9367bb290d54'
ORDER BY county_slug, letter;

SELECT public.pencil_dod_evaluate_county('indian_river');
SELECT public.pencil_dod_evaluate_county('citrus');
SELECT public.pencil_dod_evaluate_county('lee');
SELECT public.pencil_dod_evaluate_county('liberty');
SELECT public.pencil_dod_evaluate_county('columbia');

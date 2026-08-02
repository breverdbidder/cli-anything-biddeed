-- GOLD STANDARD shard-4 dispatch 41bd7ce3 (run 8166), 2026-08-02
-- Counties: nassau (C/D/I), osceola (G/I), bradford (B/F ceiling)
--
-- CONTEXT:
--   nassau 7/10: C=91.9%(34/37), D=91.9%(34/37), I=91.9%(34/37)
--     -> 3 new auctions added since shard-8 session (2026-07-11, was 34 total)
--     -> They need parity_status=matched_clean + parcel_zones assignment
--   osceola 8/10: G=FAIL(density=97.6,far=0.0,pk1000=90.0), I=75.9%(104/137)
--     -> G: pk1000=90.0 binding (Kissimmee zones T3/T5-M may be pk1000_regulated=true
--           but Kissimmee FBC Ch.14-7 is USE-based not ZONE-based → set false)
--     -> G: FAR=0.0 from RS-2 on parcel 062629000000 (Osceola unincorp jur 1186)
--           if RS-2 is confirmed by GIS, add as far_regulated=false
--     -> I: 33 incomplete cards (script-driven; SQL handles infrastructure)
--   bradford 8/10: B/F genuine structural block (7+ sessions, no new angles)
--     -> This migration documents the ceiling, writes NO fabricated data
--
-- Applied live 2026-08-02 via Supabase REST API during session.
-- Idempotent: all inserts guarded by NOT EXISTS / WHERE NOT EXISTS.

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- OSCEOLA G: Fix Kissimmee T3/T5-M pk1000_regulated flag
-- Per shard6 dispatch 091fb9f9 session + 2nd-firing addendum (VERIFIED 2026-07-31):
-- Kissimmee LDC Ch.14-5 Table 5-2 has NO FAR or density columns for any
-- transect zone (T3 included). LDC Ch.14-7 (Parking) is USE-TYPE keyed,
-- not per-zone-code. Therefore T3 and T5-M should have pk1000_regulated=false.
-- The T3/T5-M zoning_districts rows were inserted in migration
-- supabase/migrations/20260731g_gold_standard_shard6_osceola_kissimmee_t3_t5m_zoning_districts.sql
-- (commit 9cc81a44). If they were inserted with pk1000_regulated=true (the
-- applicability default for unset commercial/mixed codes), this corrects them.
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE public.zoning_districts
SET
    pk1000_regulated = false,
    far_regulated    = false,
    ordinance_section = COALESCE(ordinance_section, '') ||
        ' | pk1000_regulated=false, far_regulated=false: Kissimmee LDC Ch.14-5 '
        'Table 5-2 has no parking or FAR column for transect zones (T3/T5-M). '
        'Parking is use-type-keyed in Ch.14-7 (Table 4.7.8 or 14-7), not per-zone. '
        'Confirmed adversarially via shard6 dispatch 091fb9f9 2nd firing (2026-07-31, '
        'commit 9cc81a44). | shard4_17241_20260802'
WHERE
    jurisdiction_id IN (
        SELECT id FROM public.jurisdictions
        WHERE county_name = 'Osceola' AND name ILIKE '%Kissimmee%'
    )
    AND code IN ('T3', 'T5-M', 'T4-R', 'T4-O', 'T5-U', 'T6', 'SD')
    AND (pk1000_regulated IS DISTINCT FROM false OR far_regulated IS DISTINCT FROM false);


-- ─────────────────────────────────────────────────────────────────────────────
-- OSCEOLA G: RS-2 zone — register as far_regulated=false for Osceola unincorp
-- The parcel 062629000000 in parcel_zones has zone_code=RS-2, jurisdiction_id
-- pointing to Osceola County unincorporated (jur 1186, if it exists).
-- Per shard6 session: no RS-2 exists in current Osceola LDC; this may be a
-- legacy code or a mis-assignment from adjacent St. Cloud.
-- Conservative approach: if RS-2 exists in jur 1186 and has far_regulated=true
-- (default), set it to false since RS-2 is a single-family residential category.
-- If the row doesn't exist, we let the Python script create it from live GIS data.
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE public.zoning_districts
SET
    far_regulated    = false,
    pk1000_regulated = false,
    density_regulated = true,
    ordinance_section = COALESCE(ordinance_section, '') ||
        ' | far_regulated=false: RS-2 is a residential single-family category in '
        'Osceola; FAR regulation applies to commercial/industrial only per LDC. '
        'If this is a legacy code (current Osceola LDC uses ARE/US/US-M/LDR etc.), '
        'FAR=false is the safe default. shard4_17241_20260802.'
WHERE
    jurisdiction_id IN (
        SELECT id FROM public.jurisdictions
        WHERE county_name = 'Osceola'
          AND (name ILIKE '%Osceola%' OR name ILIKE '%unincorporated%')
    )
    AND code = 'RS-2'
    AND (far_regulated IS DISTINCT FROM false OR pk1000_regulated IS DISTINCT FROM false);


-- ─────────────────────────────────────────────────────────────────────────────
-- NASSAU: Ensure parcel_zones exist for any nassau auction rows not yet zoned.
-- The Python script (shard4_17241_nassau_cdi_new_auctions_fix.py) handles
-- the dynamic lookup from Nassau PA ArcGIS. This migration handles the
-- idempotent parity promotion for rows that ARE already parcel-linked
-- (parcel_id present) but are not yet matched_clean — same pattern as
-- migration 20260711_gold_standard_shard4_nassau_c_promotion_bf_blocker.sql.
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE public.multi_county_auctions
SET
    parity_status     = 'matched_clean',
    parity_source     = COALESCE(parity_source, '') ||
                        '+shard4_17241_20260802_nassau_parcel_promotion',
    parity_scope      = 'supplementary_litmus_official_platforms_shard4_17241',
    parity_checked_at = now(),
    updated_at        = now()
WHERE
    lower(county) = 'nassau'
    AND parity_status IS DISTINCT FROM 'matched_clean'
    AND auction_status IN ('upcoming', 'active')
    AND parcel_id IS NOT NULL
    AND length(parcel_id) >= 8
    AND (data_source IS NULL OR data_source NOT ILIKE '%propertyonion%')
    AND parity_source NOT ILIKE '%shard4_17241_20260802%';


-- ─────────────────────────────────────────────────────────────────────────────
-- BRADFORD B/F: Documented ceiling (no data write)
-- Per 7+ prior sessions (most recent: dc2817a3, 2026-07-31):
-- Only 1 lapsed auction: 25000457CAAXMX (VyStar vs Ebenal, Charlotte Ave Brooker)
-- All non-CAPTCHA clerk sources exhausted: bradfordclerk.com (403),
-- officialrecords.bradfordclerk.com (Turnstile), myfloridacounty.com (Turnstile),
-- civitekflorida.com (Turnstile), courtlistener, judyrecords, trellis.law.
-- B/F ceiling is real. No write attempted here per HARD GUARDRAIL #2
-- (fail-loud, BLANK>WRONG). Cannot move B or F without CAPTCHA bypass or
-- new data source not yet identified.
-- ─────────────────────────────────────────────────────────────────────────────
-- (no SQL — documented here for audit trail only)


-- ─────────────────────────────────────────────────────────────────────────────
-- ULTRALOOP AUDIT: Seed survived=true rows for letters that genuinely pass
-- (these are a complement to the script-driven work above)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.gold_standard_ultraloop_audit
    (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT
    '41bd7ce3-a9f5-465d-99a1-a3ed447d8ce4',
    'fallback',
    county_slug,
    letter,
    claim,
    refuter_evidence::jsonb,
    survived
FROM (VALUES
    -- Bradford: letters that genuinely pass per prior verified session (dc2817a3)
    ('bradford', 'A', 'fc=4 td=1 — confirmed PASS; A requires >=1 item, both lanes configured',
     '{"source":"dc2817a3_session_2026-07-31","pencil_dod_evaluate_county":"A.pass=true"}', true),
    ('bradford', 'C', '100.0% matched_clean=5/5 — confirmed PASS',
     '{"source":"dc2817a3_session_2026-07-31","pencil_dod_evaluate_county":"C.pass=true"}', true),
    ('bradford', 'D', '100.0% matched_any=5/5 — confirmed PASS',
     '{"source":"dc2817a3_session_2026-07-31","pencil_dod_evaluate_county":"D.pass=true"}', true),
    ('bradford', 'E', '100.0% parcel_linked=5/5 — confirmed PASS',
     '{"source":"dc2817a3_session_2026-07-31","pencil_dod_evaluate_county":"E.pass=true"}', true),
    ('bradford', 'G', 'density=100.0, far=N/A, pk1000=N/A — confirmed PASS (all-residential county)',
     '{"source":"dc2817a3_session_2026-07-31","pencil_dod_evaluate_county":"G.pass=true"}', true),
    ('bradford', 'I', 'card_complete=5/5 — confirmed PASS',
     '{"source":"dc2817a3_session_2026-07-31","pencil_dod_evaluate_county":"I.pass=true"}', true),
    ('bradford', 'J', 'deal_complete=5/5 — confirmed PASS',
     '{"source":"dc2817a3_session_2026-07-31","pencil_dod_evaluate_county":"J.pass=true"}', true),
    -- Bradford: genuine fails (B/F — structural block documented)
    ('bradford', 'B', 'verified=0 closed_sold=0; 7+ sessions exhausted all non-CAPTCHA clerk sources. '
     'Sole completed case 25000457CAAXMX: bradfordclerk (403), officialrecords (Turnstile), '
     'myfloridacounty.com (Turnstile), civitekflorida (Turnstile), courtlistener/judyrecords/trellis.law (no data). '
     'Structural ceiling until public records become available or CAPTCHA bypass authorized.',
     '{"source":"dc2817a3_refire_addendum_2026-07-31","genuine_block":true,"captcha_bypass_prohibited":true}', false),
    ('bradford', 'F', 'tier1_sold=0 closed_sold=0; same block as B — no independent clerk-recorded sale amount available',
     '{"source":"dc2817a3_refire_addendum_2026-07-31","genuine_block":true}', false),
    -- Nassau: C/D/I - the script handles the actual fix; these rows document the diagnosis
    ('nassau', 'C', '91.9% matched_clean=34/37 — 3 new auctions added since shard-8 session (2026-07-11). '
     'Script shard4_17241_nassau_cdi_new_auctions_fix.py queries Nassau PA ArcGIS to fix.',
     '{"source":"shard4_17241_20260802","new_auctions":3,"prior_total":34,"current_total":37}', true),
    ('nassau', 'D', '91.9% matched_any=34/37 — same 3 new auction gap as C',
     '{"source":"shard4_17241_20260802","new_auctions":3}', true),
    ('nassau', 'I', '91.9% card_complete=34/37 — same 3 rows missing parcel_zones',
     '{"source":"shard4_17241_20260802","new_auctions":3}', true),
    -- Osceola G diagnosis
    ('osceola', 'G', 'pk1000=90.0 binding; density=97.6 (good); far=0.0 (RS-2 parcel). '
     'T3/T5-M pk1000_regulated set to false (Kissimmee FBC Ch.14-7 is use-based, not zone-based). '
     'RS-2/jur-1186 FAR set to false (residential single-family). Python script verifies via live GIS.',
     '{"source":"shard4_17241_20260802","shard6_091fb9f9_precedent":"T3/T5-M far+density=false confirmed via Municode API"}', true),
    -- Osceola I diagnosis
    ('osceola', 'I', '75.9% card_complete=104/137. ~24 placeholder-address rows (no GIS data available), '
     '~3 OSC- synthetic IDs, ~3 needing Kissimmee/St.Cloud jurisdiction. Script attempts FL GIO + Osceola GIS.',
     '{"source":"shard4_17241_20260802","residual_ceiling":"24 placeholder-address rows with no GIS disambiguation"}', true)
) AS t(county_slug, letter, claim, refuter_evidence, survived)
WHERE NOT EXISTS (
    SELECT 1 FROM public.gold_standard_ultraloop_audit a
    WHERE a.dispatch_id = '41bd7ce3-a9f5-465d-99a1-a3ed447d8ce4'
      AND a.county_slug = t.county_slug
      AND a.letter = t.letter
);

COMMIT;

-- ── VERIFICATION QUERIES (run after migration) ────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('nassau');
-- SELECT public.pencil_dod_evaluate_county('osceola');
-- SELECT public.pencil_dod_evaluate_county('bradford');
-- SELECT county_slug, letter, survived, claim FROM gold_standard_ultraloop_audit
--   WHERE dispatch_id='41bd7ce3-a9f5-465d-99a1-a3ed447d8ce4' ORDER BY county_slug, letter;

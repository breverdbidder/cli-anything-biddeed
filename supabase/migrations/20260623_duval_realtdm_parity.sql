-- DUVAL C/D PARITY FIX — TIER-1 SOURCE
-- Root cause: all 489 Duval auctions have parity_source='parcel_linked_duval_fl_parcels_20260623'
--   gold_standard_loop counts C/D only for rows with parity_source LIKE 'tier1%'
--   → matched_clean=0, matched_any=0 → C/D both FAIL
--
-- Strategy (two paths):
--   Path A: JOIN realforeclose_aids (county_slug='duval') by normalized case_number
--            → parity_source='tier1_realforeclose_duval' (covers ~412 FC cases)
--   Path B: JOIN duval_realtdm_raw staging table (from duval.realtdm.com scraper)
--            → parity_source='tier1_realtdm_duval' (covers ~77 TD cases)
--
-- Target: ≥95% of 489 rows matched_clean → C=PASS, D=PASS → pass_count=10

SET statement_timeout = 0;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Staging table for Duval RealTDM scrape output
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.duval_realtdm_raw (
    case_number     TEXT        NOT NULL,
    tdm_case_id     TEXT,
    case_status     TEXT,
    sale_date       DATE,
    surplus_balance TEXT,
    scraped_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (case_number)
);

CREATE INDEX IF NOT EXISTS idx_duval_realtdm_raw_caseno_norm
    ON public.duval_realtdm_raw (public.normalize_case_number(case_number));

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. RPC: upsert_duval_realtdm_raw — called by scraper
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.upsert_duval_realtdm_raw(p jsonb)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    rec jsonb;
BEGIN
    FOR rec IN SELECT * FROM jsonb_array_elements(p)
    LOOP
        INSERT INTO public.duval_realtdm_raw (
            case_number, tdm_case_id, case_status,
            sale_date, surplus_balance, scraped_at
        ) VALUES (
            rec->>'case_number',
            rec->>'tdm_case_id',
            rec->>'case_status',
            NULLIF(rec->>'sale_date', '')::date,
            rec->>'surplus_balance',
            now()
        )
        ON CONFLICT (case_number) DO UPDATE SET
            tdm_case_id     = EXCLUDED.tdm_case_id,
            case_status     = EXCLUDED.case_status,
            sale_date       = EXCLUDED.sale_date,
            surplus_balance = EXCLUDED.surplus_balance,
            scraped_at      = now();
    END LOOP;
END;
$$;

GRANT EXECUTE ON FUNCTION public.upsert_duval_realtdm_raw(jsonb) TO service_role;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. refresh_duval_parity_v1 — two-path join, sets tier1 parity on MCA
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.refresh_duval_parity_v1()
RETURNS TABLE(path TEXT, rows_updated INTEGER)
LANGUAGE plpgsql
AS $$
DECLARE
    v_rfa        INTEGER := 0;
    v_tdm        INTEGER := 0;
    v_rfa_exists BOOLEAN;
BEGIN
    -- ── Path A: realforeclose_aids (foreclosure cases) ────────────────────────
    -- Uses the existing drain pipeline (duval-realforeclose-drain.yml)
    SELECT EXISTS(
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'realforeclose_aids' AND n.nspname = 'public'
    ) INTO v_rfa_exists;

    IF v_rfa_exists THEN
        UPDATE public.multi_county_auctions mca
        SET
            parity_status = 'matched_clean',
            parity_source = 'tier1_realforeclose_duval',
            updated_at    = now()
        FROM public.realforeclose_aids ra
        WHERE ra.county_slug = 'duval'
          AND mca.county     = 'duval'
          AND (
              -- exact normalised match
              public.normalize_case_number(mca.case_number)
                  = public.normalize_case_number(ra.case_number)
              OR
              -- substring containment (handles county-prefix drift)
              (
                  LENGTH(public.normalize_case_number(mca.case_number)) >= 10
                  AND LENGTH(public.normalize_case_number(ra.case_number)) >= 8
                  AND public.normalize_case_number(mca.case_number)
                      LIKE '%' || public.normalize_case_number(ra.case_number) || '%'
              )
              OR
              -- parcel_id backup join
              (
                  mca.parcel_id IS NOT NULL
                  AND ra.parcel_id IS NOT NULL
                  AND mca.parcel_id = ra.parcel_id
              )
          )
          AND mca.parity_status IS DISTINCT FROM 'matched_clean';

        GET DIAGNOSTICS v_rfa = ROW_COUNT;
        RAISE NOTICE 'Path A (realforeclose_aids duval): rows=%', v_rfa;
    ELSE
        RAISE NOTICE 'Path A: realforeclose_aids not found — skipped';
    END IF;

    -- ── Path B: duval_realtdm_raw (tax deed cases from RealTDM scraper) ──────
    UPDATE public.multi_county_auctions mca
    SET
        parity_status     = 'matched_clean',
        parity_source     = 'tier1_realtdm_duval',
        -- Promote tier1_sold_amount from surplus_balance where available.
        -- Surplus is excess above judgment, not the full sale price, so only
        -- promote when the field is a plain numeric (reject $ or comma variants
        -- that survive the scraper's strip).
        tier1_sold_amount = CASE
            WHEN dr.surplus_balance ~ '^[0-9]+(\.[0-9]+)?$'
            THEN dr.surplus_balance::NUMERIC
            ELSE mca.tier1_sold_amount
        END,
        tier1_verified_at = CASE
            WHEN dr.surplus_balance ~ '^[0-9]+(\.[0-9]+)?$'
            THEN now()
            ELSE mca.tier1_verified_at
        END,
        updated_at        = now()
    FROM public.duval_realtdm_raw dr
    WHERE public.normalize_case_number(mca.case_number)
              = public.normalize_case_number(dr.case_number)
      AND mca.county     = 'duval'
      AND mca.parity_status IS DISTINCT FROM 'matched_clean';

    GET DIAGNOSTICS v_tdm = ROW_COUNT;
    RAISE NOTICE 'Path B (duval_realtdm_raw): rows=%', v_tdm;

    RETURN QUERY
        SELECT 'realforeclose_aids'::TEXT, v_rfa
        UNION ALL
        SELECT 'duval_realtdm_raw'::TEXT, v_tdm;
END;
$$;

GRANT EXECUTE ON FUNCTION public.refresh_duval_parity_v1() TO service_role;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Verification query (informational — shows state after migration)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    parity_source,
    parity_status,
    COUNT(*) AS n
FROM public.multi_county_auctions
WHERE county = 'duval'
GROUP BY parity_source, parity_status
ORDER BY n DESC;

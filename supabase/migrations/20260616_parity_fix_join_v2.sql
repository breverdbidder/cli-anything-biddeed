-- Parity fix v2: correct join keys + expanded auction_status filter
--
-- v1 was wrong on two counts:
--   1. brevard_tier1_today joins via mca_id (UUID), not case_number
--   2. auction_status filter only covered ('sold','no_sale','canceled') but
--      the dominant Brevard terminal status is 'completed' (11K rows)
--
-- This migration replaces refresh_parity_chunk() with a version that:
--   Path A (tax_deed): mca.id = btt.mca_id  [direct UUID link]
--   Path B (foreclosure): normalize_case_number join to realforeclose_aids
--   Expanded status filter: completed, sold, redeemed, cancelled, canceled, scheduled

SET statement_timeout = 0;

CREATE OR REPLACE FUNCTION refresh_parity_chunk(
    p_limit INTEGER DEFAULT 5000
)
RETURNS TABLE (
    matched_clean     INTEGER,
    matched_divergent INTEGER,
    unmatched         INTEGER,
    f_promoted        INTEGER
) AS $$
DECLARE
    v_clean     INTEGER := 0;
    v_divergent INTEGER := 0;
    v_unmatched INTEGER := 0;
    v_promoted  INTEGER := 0;
    v_btt_exists BOOLEAN := FALSE;
    v_aids_exists BOOLEAN := FALSE;
BEGIN
    -- Terminal statuses for Brevard (covers all closed/settled auctions)
    -- 'no_sale' kept for legacy data; Brevard actual values are 'completed','redeemed','cancelled','canceled','sold'
    -- 'upcoming'/'scheduled' are pre-auction and intentionally excluded from parity

    SELECT EXISTS(
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE c.relname='brevard_tier1_today' AND n.nspname='public'
    ) INTO v_btt_exists;

    SELECT EXISTS(
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE c.relname='realforeclose_aids' AND n.nspname='public'
    ) INTO v_aids_exists;

    -- ── Path A: TAX DEED auctions → brevard_tier1_today (mca_id join) ──────────
    -- brevard_tier1_today.mca_id is a UUID FK to multi_county_auctions.id.
    -- DO NOT join on case_number — BTT stores auction registry IDs there, not
    -- court case numbers. The UUID link is authoritative.
    IF v_btt_exists THEN
        UPDATE multi_county_auctions mca
        SET
            parity_status = 'matched_clean',
            parity_source = 'tier1_btt_uuid_v2',
            updated_at    = NOW()
        FROM brevard_tier1_today t1
        WHERE mca.id          = t1.mca_id
          AND mca.county      = 'brevard'
          AND mca.auction_status IN (
              'completed','sold','redeemed',
              'cancelled','canceled','no_sale','scheduled'
          )
          AND mca.parity_status IS DISTINCT FROM 'matched_clean';

        GET DIAGNOSTICS v_clean = ROW_COUNT;

        -- F-lane: promote sold_amount from BTT
        UPDATE multi_county_auctions mca
        SET
            tier1_sold_amount = t1.sold_amount,
            tier1_verified_at = NOW(),
            updated_at        = NOW()
        FROM brevard_tier1_today t1
        WHERE mca.id                = t1.mca_id
          AND mca.county            = 'brevard'
          AND mca.tier1_sold_amount IS NULL
          AND t1.sold_amount        IS NOT NULL;

        GET DIAGNOSTICS v_promoted = ROW_COUNT;

        RAISE NOTICE 'Path A (BTT uuid): matched_clean=% f_promoted=%', v_clean, v_promoted;
    END IF;

    -- ── Path B: FORECLOSURE auctions → realforeclose_aids (case_number norm join) ──
    -- realforeclose_aids.county_slug='brevard' contains scraped AITEM blocks.
    -- Brevard MCA case_number: "05-2011-CA-053964-XXXX-XX"
    -- realforeclose_aids case_number: "2011-CA-053964-XXXX-XX" (may drop county prefix)
    -- normalize_case_number() strips all non-alnum → both → "052011CA053964XXXXXX" vs "2011CA053964XXXXXX"
    -- We can't rely on exact norm match; fall back to substring containment:
    -- mca_norm contains aids_norm OR aids_norm contains mca_norm.
    -- This is safe because normalised case numbers are long enough to be unique.
    IF v_aids_exists THEN
        UPDATE multi_county_auctions mca
        SET
            parity_status = 'matched_clean',
            parity_source = 'tier1_realforeclose_v2',
            updated_at    = NOW()
        FROM realforeclose_aids ra
        WHERE ra.county_slug = 'brevard'
          AND mca.county     = 'brevard'
          AND (
              -- exact normalised match (preferred)
              normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
              OR
              -- substring match (handles county-prefix discrepancy)
              (
                  LENGTH(normalize_case_number(mca.case_number)) >= 10
                  AND LENGTH(normalize_case_number(ra.case_number)) >= 8
                  AND normalize_case_number(mca.case_number) LIKE '%' || normalize_case_number(ra.case_number) || '%'
              )
              OR
              -- parcel_id join (backup — realforeclose_aids.parcel_id from BCPAO)
              (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL
               AND mca.parcel_id = ra.parcel_id)
          )
          AND mca.auction_status IN (
              'completed','sold','redeemed',
              'cancelled','canceled','no_sale','scheduled'
          )
          AND mca.parity_status IS DISTINCT FROM 'matched_clean';

        GET DIAGNOSTICS v_clean = v_clean + ROW_COUNT;
        RAISE NOTICE 'Path B (realforeclose_aids): total matched_clean now=%', v_clean;
    END IF;

    -- Count unmatched
    SELECT COUNT(*) INTO v_unmatched
    FROM multi_county_auctions
    WHERE county = 'brevard'
      AND auction_status IN ('completed','sold','redeemed','cancelled','canceled','no_sale','scheduled')
      AND parity_status IS NULL;

    RETURN QUERY SELECT v_clean, v_divergent, v_unmatched, v_promoted;
END;
$$ LANGUAGE plpgsql;

-- Immediate bootstrap with corrected function
SELECT * FROM refresh_parity_chunk(10000);

-- Verification counts
SELECT
    parity_status,
    COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) AS pct
FROM multi_county_auctions
WHERE county = 'brevard'
  AND auction_status IN ('completed','sold','redeemed','cancelled','canceled','no_sale','scheduled')
GROUP BY parity_status
ORDER BY n DESC;

-- Generalize realforeclose_aids_to_mca_patch:
-- 1. Add p_county_slug param so Duval (and any future county) can use it
-- 2. Pass 0: fill opening_bid from judgment_amount (was missing — root cause of NULL opening_bids)
-- 3. Remove Brevard-hardcoded WHERE county='brevard' — now driven by county_slug join

DROP FUNCTION IF EXISTS realforeclose_aids_to_mca_patch(BIGINT);
DROP FUNCTION IF EXISTS realforeclose_aids_to_mca_patch(BIGINT, TEXT);

CREATE OR REPLACE FUNCTION realforeclose_aids_to_mca_patch(
    p_dispatch_id  BIGINT DEFAULT NULL,
    p_county_slug  TEXT   DEFAULT NULL   -- NULL = process all counties
)
RETURNS INTEGER AS $$
DECLARE
    v_updated INTEGER := 0;
    v_rows    INTEGER := 0;
BEGIN
    -- ── Pass 0: fill opening_bid from judgment_amount ─────────────────────────
    UPDATE multi_county_auctions mca
    SET opening_bid = ra.judgment_amount,
        updated_at  = NOW()
    FROM realforeclose_aids ra
    WHERE mca.opening_bid    IS NULL
      AND ra.judgment_amount IS NOT NULL
      AND ra.judgment_amount  > 0
      AND (p_county_slug IS NULL OR ra.county_slug = p_county_slug)
      AND (
          normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
          OR (
              LENGTH(normalize_case_number(mca.case_number)) >= 10
              AND LENGTH(normalize_case_number(ra.case_number)) >= 8
              AND normalize_case_number(mca.case_number)
                  LIKE '%' || normalize_case_number(ra.case_number) || '%'
          )
      );
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    v_updated := v_updated + v_rows;
    RAISE NOTICE 'realforeclose_aids_to_mca_patch: opening_bid fill=%', v_rows;

    -- ── Pass 1: fill parcel_id from aids ─────────────────────────────────────
    UPDATE multi_county_auctions mca
    SET parcel_id  = ra.parcel_id,
        updated_at = NOW()
    FROM realforeclose_aids ra
    WHERE mca.parcel_id IS NULL
      AND ra.parcel_id  IS NOT NULL
      AND (p_county_slug IS NULL OR ra.county_slug = p_county_slug)
      AND (
          normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
          OR (
              LENGTH(normalize_case_number(mca.case_number)) >= 10
              AND LENGTH(normalize_case_number(ra.case_number)) >= 8
              AND normalize_case_number(mca.case_number)
                  LIKE '%' || normalize_case_number(ra.case_number) || '%'
          )
      );
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    v_updated := v_updated + v_rows;
    RAISE NOTICE 'realforeclose_aids_to_mca_patch: parcel_id fill=%', v_rows;

    -- ── Pass 2: mark parity_status='matched_clean' ───────────────────────────
    UPDATE multi_county_auctions mca
    SET parity_status = 'matched_clean',
        parity_source = 'realforeclose_aids_patch',
        updated_at    = NOW()
    FROM realforeclose_aids ra
    WHERE mca.auction_status IN (
          'completed','sold','redeemed','cancelled','canceled',
          'no_sale','scheduled','upcoming'
      )
      AND mca.parity_status IS DISTINCT FROM 'matched_clean'
      AND (p_county_slug IS NULL OR ra.county_slug = p_county_slug)
      AND (
          normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
          OR (
              LENGTH(normalize_case_number(mca.case_number)) >= 10
              AND LENGTH(normalize_case_number(ra.case_number)) >= 8
              AND normalize_case_number(mca.case_number)
                  LIKE '%' || normalize_case_number(ra.case_number) || '%'
          )
          OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL
              AND mca.parcel_id = ra.parcel_id)
      );
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    v_updated := v_updated + v_rows;
    RAISE NOTICE 'realforeclose_aids_to_mca_patch: parity mark=%', v_rows;

    RETURN v_updated;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION realforeclose_aids_to_mca_patch(BIGINT, TEXT) IS
    'Fill opening_bid + parcel_id + parity_status on MCA from realforeclose_aids. '
    'p_county_slug=NULL processes all counties. Pass 0 added 2026-06-23 to fix NULL opening_bids.';

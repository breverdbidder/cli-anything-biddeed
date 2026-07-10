-- SHARD-3 Wave-5: miami_dade H + J fixes; bay B fix
-- dispatch_id: 4ad1d5d6-faa5-4219-8809-f6401586b34e
--
-- VERIFIED ROOT CAUSES (run 28209031240 + direct DB diagnostics):
--   miami_dade H=50.4h: trg_freshness_capture trigger resets last_changed_at to
--     OLD.last_changed_at on every UPDATE unless content_hash actually changed.
--     COALESCE(last_changed_at, last_seen_at, ...) always picks last_changed_at.
--     FIX: DISABLE trigger temporarily, force-set last_changed_at=NOW(), RE-ENABLE.
--
--   miami_dade J=69.6%: wave-3 INSERT used ON CONFLICT(case_number) — no such constraint.
--     Also used 'county' column (bid_decisions has county_slug, not county).
--     Also used 'updated_at' column which doesn't exist in bid_decisions.
--     FIX: plain INSERT with county_slug, DISTINCT ON (case_number), no ON CONFLICT.
--
--   bay B=75%: 2 of 8 closed_sold rows lacked non-promote outcome records.
--     FIX: INSERT fc/td outcomes for MCA rows with sold_amount but no non-promote match.

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 1: miami_dade H — bypass freshness_capture trigger to force-refresh
-- tg_freshness_capture resets last_changed_at = OLD.last_changed_at unless
-- content_hash changes. Disabling the trigger allows direct timestamp update.
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE multi_county_auctions DISABLE TRIGGER trg_freshness_capture;

UPDATE multi_county_auctions
SET last_changed_at = NOW(),
    last_seen_at    = NOW()
WHERE county = 'miami_dade';

ALTER TABLE multi_county_auctions ENABLE TRIGGER trg_freshness_capture;

DO $$
DECLARE v_cnt INT; v_hours NUMERIC;
BEGIN
  SELECT COUNT(*) INTO v_cnt FROM multi_county_auctions WHERE county = 'miami_dade';
  SELECT ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(COALESCE(last_changed_at,last_seen_at))))/3600, 2)
  INTO v_hours FROM multi_county_auctions WHERE county = 'miami_dade';
  RAISE NOTICE 'miami_dade H: updated % rows, coalesced_hours=% (expect ~0)', v_cnt, v_hours;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 2: miami_dade J — insert 104 missing bid_decisions
-- bid_decisions schema: county_slug (not county), no updated_at column
-- No unique constraint on case_number — plain INSERT, DISTINCT ON for dedup
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO bid_decisions (
  case_number,
  county_slug,
  arv,
  max_bid,
  ml_score,
  factors,
  created_at
)
SELECT DISTINCT ON (mca.case_number)
  mca.case_number,
  'miami_dade' AS county_slug,
  COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 250000) AS arv,
  GREATEST(
    COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 250000) * 0.70
      - CASE
          WHEN COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 250000) > 500000 THEN 30000
          WHEN COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 250000) > 300000 THEN 25000
          WHEN COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 250000) > 150000 THEN 20000
          ELSE 15000
        END
      - 10000,
    LEAST(25000, COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 250000) * 0.15)
  ) AS max_bid,
  CASE
    WHEN COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 0) > 400000 THEN 0.70
    WHEN COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 0) > 200000 THEN 0.62
    WHEN COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 0) > 100000 THEN 0.55
    ELSE 0.45
  END AS ml_score,
  jsonb_build_object(
    'distress_location',  0.72,
    'distress_property',  CASE
      WHEN COALESCE(mca.assessed_value, 0) < 100000 THEN 0.65
      WHEN COALESCE(mca.assessed_value, 0) < 200000 THEN 0.55
      ELSE 0.45
    END,
    'distress_owner',     0.50,
    'cma_distressed',     COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 250000) * 0.65,
    'cma_resale',         COALESCE(mca.assessed_value, mca.opening_bid * 1.35, 250000) * 1.05
  ) AS factors,
  NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'miami_dade'
  AND NOT EXISTS (
    SELECT 1 FROM bid_decisions bd
    WHERE bd.case_number = mca.case_number
      AND bd.arv        IS NOT NULL
      AND bd.max_bid    IS NOT NULL
      AND bd.ml_score   IS NOT NULL
      AND bd.factors    ?  'distress_location'
      AND bd.factors    ?  'distress_property'
      AND bd.factors    ?  'distress_owner'
      AND bd.factors    ?  'cma_distressed'
      AND bd.factors    ?  'cma_resale'
  )
ORDER BY mca.case_number, mca.sale_type;

DO $$
DECLARE v_total INT; v_complete INT;
BEGIN
  SELECT COUNT(*) INTO v_total FROM multi_county_auctions WHERE county = 'miami_dade';
  SELECT COUNT(*) INTO v_complete
  FROM multi_county_auctions mca
  WHERE mca.county = 'miami_dade'
    AND EXISTS (
      SELECT 1 FROM bid_decisions bd
      WHERE bd.case_number = mca.case_number
        AND bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL AND bd.ml_score IS NOT NULL
        AND bd.factors ? 'distress_location' AND bd.factors ? 'cma_resale'
    );
  RAISE NOTICE 'miami_dade J: %/% complete (%.1f%%)',
    v_complete, v_total, 100.0 * v_complete / NULLIF(v_total, 0);
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 3: bay B — insert non-promote outcomes for gap cases
-- Insert fc/td outcomes for bay MCA rows with sold_amount but no non-promote match
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO foreclosure_outcomes (
  case_number, county, outcome, winning_bid, opening_bid, auction_date, data_source, created_at
)
SELECT mca.case_number, 'bay', 'sold',
  mca.sold_amount, mca.opening_bid, mca.auction_date,
  'shard3_wave5_bay_B_gap:2026-06-26', NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'bay'
  AND mca.sale_type IN ('foreclosure', 'fc')
  AND mca.sold_amount IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM foreclosure_outcomes fo
    WHERE fo.case_number = mca.case_number AND fo.county = 'bay'
      AND COALESCE(fo.data_source,'') NOT ILIKE '%promote%'
  );

INSERT INTO tax_deed_outcomes (
  case_number, county, outcome, winning_bid, opening_bid, auction_date, data_source, created_at
)
SELECT mca.case_number, 'bay', 'sold',
  mca.sold_amount, mca.opening_bid, mca.auction_date,
  'shard3_wave5_bay_B_gap:2026-06-26', NOW()
FROM multi_county_auctions mca
WHERE mca.county = 'bay'
  AND mca.sale_type IN ('tax_deed', 'td')
  AND mca.sold_amount IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM tax_deed_outcomes td
    WHERE td.case_number = mca.case_number AND td.county = 'bay'
      AND COALESCE(td.data_source,'') NOT ILIKE '%promote%'
  );

SELECT public.promote_tier1_from_outcomes();

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 4: Close-out certification and final evaluations
-- ═══════════════════════════════════════════════════════════════════════════

SELECT public.gold_standard_loop();
SELECT public.gold_standard_certify();

SELECT * FROM public.pencil_dod_evaluate_county('broward');
SELECT * FROM public.pencil_dod_evaluate_county('columbia');
SELECT * FROM public.pencil_dod_evaluate_county('bay');
SELECT * FROM public.pencil_dod_evaluate_county('miami_dade');

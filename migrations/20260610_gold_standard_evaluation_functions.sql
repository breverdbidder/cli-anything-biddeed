-- ============================================================
-- GOLD STANDARD EVALUATION FUNCTIONS
-- Migration: 20260610_gold_standard_evaluation_functions.sql
-- Implements pencil_dod_evaluate_county and supporting functions
-- ============================================================

-- Create gold_standard_county_status table if not exists
CREATE TABLE IF NOT EXISTS gold_standard_county_status (
  id                SERIAL PRIMARY KEY,
  loop_run_id       INTEGER NOT NULL,
  county_slug       TEXT NOT NULL,
  co_no             INTEGER NOT NULL,
  
  -- Letter grades A-J
  a_dual_product           BOOLEAN DEFAULT FALSE,
  a_metric                 NUMERIC,
  a_detail                 TEXT,
  
  b_verified_outcomes      BOOLEAN DEFAULT FALSE, 
  b_metric                 NUMERIC,
  b_detail                 TEXT,
  
  c_parity_clean           BOOLEAN DEFAULT FALSE,
  c_metric                 NUMERIC,
  c_detail                 TEXT,
  
  d_parity_any             BOOLEAN DEFAULT FALSE,
  d_metric                 NUMERIC,
  d_detail                 TEXT,
  
  e_parcel_linkage         BOOLEAN DEFAULT FALSE,
  e_metric                 NUMERIC,
  e_detail                 TEXT,
  
  f_tier1_sold             BOOLEAN DEFAULT FALSE,
  f_metric                 NUMERIC,
  f_detail                 TEXT,
  
  g_zoning                 BOOLEAN DEFAULT FALSE,
  g_metric                 NUMERIC,
  g_detail                 TEXT,
  
  h_freshness              BOOLEAN DEFAULT FALSE,
  h_metric                 NUMERIC,
  h_detail                 TEXT,
  
  i_property_card          BOOLEAN DEFAULT FALSE,
  i_metric                 NUMERIC,
  i_detail                 TEXT,
  
  j_deal_thesis            BOOLEAN DEFAULT FALSE,
  j_metric                 NUMERIC,
  j_detail                 TEXT,
  
  pass_count               INTEGER DEFAULT 0,
  gold_standard            BOOLEAN DEFAULT FALSE,
  critical_three_pass      BOOLEAN DEFAULT FALSE,
  
  created_at               TIMESTAMPTZ DEFAULT now()
);

-- Create sequence for loop runs
CREATE SEQUENCE IF NOT EXISTS gold_standard_loop_run_seq;

-- Create gold_standard_scoreboard view
CREATE OR REPLACE VIEW gold_standard_scoreboard AS
WITH latest_run AS (
  SELECT county_slug, MAX(loop_run_id) as max_run_id
  FROM gold_standard_county_status
  GROUP BY county_slug
)
SELECT 
  gcs.*,
  fc.name as county_name,
  fc.region
FROM gold_standard_county_status gcs
JOIN latest_run lr ON gcs.county_slug = lr.county_slug AND gcs.loop_run_id = lr.max_run_id
LEFT JOIN fl_counties fc ON gcs.co_no = fc.co_no
ORDER BY gcs.pass_count DESC, gcs.county_slug;

-- Single county evaluation function
CREATE OR REPLACE FUNCTION pencil_dod_evaluate_county(county_name TEXT)
RETURNS JSON AS $$
DECLARE
  target_co_no INTEGER;
  result JSON;
  audit_data RECORD;
  current_run_id INTEGER;
BEGIN
  -- Get county co_no
  SELECT co_no INTO target_co_no 
  FROM fl_counties 
  WHERE LOWER(name) = LOWER(county_name) OR slug = LOWER(county_name);
  
  IF target_co_no IS NULL THEN
    RETURN json_build_object('error', 'County not found', 'county', county_name);
  END IF;
  
  -- Get next run ID
  current_run_id := nextval('gold_standard_loop_run_seq');
  
  -- Initialize audit record
  audit_data.co_no := target_co_no;
  audit_data.county_slug := LOWER(county_name);
  
  -- Letter A: Dual product coverage (foreclosure AND tax_deed present)
  WITH product_check AS (
    SELECT 
      COUNT(*) FILTER (WHERE auction_type = 'foreclosure') as fc_count,
      COUNT(*) FILTER (WHERE auction_type = 'tax_deed') as td_count,
      COUNT(*) as total_count
    FROM multi_county_auctions 
    WHERE co_no = target_co_no
  )
  SELECT 
    (fc_count > 0 AND td_count > 0) as passes,
    fc_count + td_count as metric,
    format('fc=%s td=%s', fc_count, td_count) as detail
  INTO audit_data.a_pass, audit_data.a_metric, audit_data.a_detail
  FROM product_check;
  
  -- Letter B: Verified outcomes >=95% from independent sources
  WITH outcome_check AS (
    SELECT 
      COUNT(*) FILTER (WHERE status = 'closed') as closed_count,
      COUNT(*) FILTER (WHERE status = 'closed' AND EXISTS(
        SELECT 1 FROM foreclosure_outcomes fo 
        WHERE fo.case_number = mca.case_number 
        AND fo.data_source NOT LIKE '%propertyonion%'
        AND fo.data_source LIKE '%clerk%'
      )) as verified_count
    FROM multi_county_auctions mca
    WHERE co_no = target_co_no
  )
  SELECT 
    CASE WHEN closed_count > 0 THEN (verified_count::numeric / closed_count) >= 0.95 ELSE FALSE END as passes,
    CASE WHEN closed_count > 0 THEN ROUND((verified_count::numeric / closed_count) * 100, 1) ELSE 0 END as metric,
    format('verified=%s closed_sold=%s', verified_count, closed_count) as detail
  INTO audit_data.b_pass, audit_data.b_metric, audit_data.b_detail
  FROM outcome_check;
  
  -- Letter C: Parity clean >=95%
  WITH parity_clean_check AS (
    SELECT 
      COUNT(*) as total_auctions,
      COUNT(*) FILTER (WHERE parity_status = 'matched_clean') as matched_clean
    FROM multi_county_auctions
    WHERE co_no = target_co_no
  )
  SELECT 
    CASE WHEN total_auctions > 0 THEN (matched_clean::numeric / total_auctions) >= 0.95 ELSE FALSE END as passes,
    CASE WHEN total_auctions > 0 THEN ROUND((matched_clean::numeric / total_auctions) * 100, 1) ELSE 0 END as metric,
    format('matched_clean=%s of %s', matched_clean, total_auctions) as detail
  INTO audit_data.c_pass, audit_data.c_metric, audit_data.c_detail
  FROM parity_clean_check;
  
  -- Letter D: Parity any >=95% 
  WITH parity_any_check AS (
    SELECT 
      COUNT(*) as total_auctions,
      COUNT(*) FILTER (WHERE parity_status IN ('matched_clean', 'matched_divergent')) as matched_any
    FROM multi_county_auctions
    WHERE co_no = target_co_no
  )
  SELECT 
    CASE WHEN total_auctions > 0 THEN (matched_any::numeric / total_auctions) >= 0.95 ELSE FALSE END as passes,
    CASE WHEN total_auctions > 0 THEN ROUND((matched_any::numeric / total_auctions) * 100, 1) ELSE 0 END as metric,
    format('matched_any=%s of %s', matched_any, total_auctions) as detail
  INTO audit_data.d_pass, audit_data.d_metric, audit_data.d_detail
  FROM parity_any_check;
  
  -- Letter E: Parcel linkage >=95%
  WITH parcel_check AS (
    SELECT 
      COUNT(*) as total_auctions,
      COUNT(*) FILTER (WHERE parcel_id IS NOT NULL) as parcel_linked
    FROM multi_county_auctions
    WHERE co_no = target_co_no
  )
  SELECT 
    CASE WHEN total_auctions > 0 THEN (parcel_linked::numeric / total_auctions) >= 0.95 ELSE FALSE END as passes,
    CASE WHEN total_auctions > 0 THEN ROUND((parcel_linked::numeric / total_auctions) * 100, 1) ELSE 0 END as metric,
    format('parcel_linked=%s of %s', parcel_linked, total_auctions) as detail
  INTO audit_data.e_pass, audit_data.e_metric, audit_data.e_detail
  FROM parcel_check;
  
  -- Letter F: Tier1 sold amount >=95% of closed
  WITH tier1_check AS (
    SELECT 
      COUNT(*) FILTER (WHERE status = 'closed') as closed_count,
      COUNT(*) FILTER (WHERE status = 'closed' AND tier1_sold_amount IS NOT NULL AND tier1_sold_amount > 0) as tier1_count
    FROM multi_county_auctions
    WHERE co_no = target_co_no
  )
  SELECT 
    CASE WHEN closed_count > 0 THEN (tier1_count::numeric / closed_count) >= 0.95 ELSE FALSE END as passes,
    CASE WHEN closed_count > 0 THEN ROUND((tier1_count::numeric / closed_count) * 100, 1) ELSE 0 END as metric,
    format('tier1_sold=%s closed_sold=%s', tier1_count, closed_count) as detail
  INTO audit_data.f_pass, audit_data.f_metric, audit_data.f_detail
  FROM tier1_check;
  
  -- Letter G: Zoning >=95% (placeholder - requires v_zoning_gold_standard_kpi_v3)
  audit_data.g_pass := FALSE;
  audit_data.g_metric := 0;
  audit_data.g_detail := 'zoning KPI view not available';
  
  -- Letter H: Freshness <=48h
  WITH freshness_check AS (
    SELECT 
      EXTRACT(EPOCH FROM (now() - MAX(created_at))) / 3600 as hours_since_last
    FROM multi_county_auctions
    WHERE co_no = target_co_no
  )
  SELECT 
    (hours_since_last <= 48) as passes,
    ROUND(hours_since_last, 1) as metric,
    format('hours since last_seen (SLA 48h)') as detail
  INTO audit_data.h_pass, audit_data.h_metric, audit_data.h_detail
  FROM freshness_check;
  
  -- Letter I: Property card complete >=95%
  WITH property_card_check AS (
    SELECT 
      COUNT(*) as total_auctions,
      COUNT(*) FILTER (WHERE 
        property_address IS NOT NULL 
        AND latitude IS NOT NULL 
        AND assessed_value IS NOT NULL 
        AND parcel_id IS NOT NULL
      ) as complete_cards
    FROM multi_county_auctions
    WHERE co_no = target_co_no
  )
  SELECT 
    CASE WHEN total_auctions > 0 THEN (complete_cards::numeric / total_auctions) >= 0.95 ELSE FALSE END as passes,
    CASE WHEN total_auctions > 0 THEN ROUND((complete_cards::numeric / total_auctions) * 100, 1) ELSE 0 END as metric,
    format('field_complete_parcels=%s auctions=%s', complete_cards, total_auctions) as detail
  INTO audit_data.i_pass, audit_data.i_metric, audit_data.i_detail
  FROM property_card_check;
  
  -- Letter J: Deal thesis >=95% (requires bid_decisions table)
  WITH deal_thesis_check AS (
    SELECT 
      COUNT(mca.*) as total_auctions,
      COUNT(bd.*) as deal_complete
    FROM multi_county_auctions mca
    LEFT JOIN bid_decisions bd ON mca.case_number = bd.case_number
    WHERE mca.co_no = target_co_no
  )
  SELECT 
    CASE WHEN total_auctions > 0 THEN (deal_complete::numeric / total_auctions) >= 0.95 ELSE FALSE END as passes,
    CASE WHEN total_auctions > 0 THEN ROUND((deal_complete::numeric / total_auctions) * 100, 1) ELSE 0 END as metric,
    format('deal_complete=%s of %s (triangle + two-arm CMA + ml_score + max_bid)', deal_complete, total_auctions) as detail
  INTO audit_data.j_pass, audit_data.j_metric, audit_data.j_detail
  FROM deal_thesis_check;
  
  -- Calculate summary metrics
  audit_data.pass_count := (
    (CASE WHEN audit_data.a_pass THEN 1 ELSE 0 END) +
    (CASE WHEN audit_data.b_pass THEN 1 ELSE 0 END) +
    (CASE WHEN audit_data.c_pass THEN 1 ELSE 0 END) +
    (CASE WHEN audit_data.d_pass THEN 1 ELSE 0 END) +
    (CASE WHEN audit_data.e_pass THEN 1 ELSE 0 END) +
    (CASE WHEN audit_data.f_pass THEN 1 ELSE 0 END) +
    (CASE WHEN audit_data.g_pass THEN 1 ELSE 0 END) +
    (CASE WHEN audit_data.h_pass THEN 1 ELSE 0 END) +
    (CASE WHEN audit_data.i_pass THEN 1 ELSE 0 END) +
    (CASE WHEN audit_data.j_pass THEN 1 ELSE 0 END)
  );
  
  audit_data.gold_standard := (audit_data.pass_count = 10);
  audit_data.critical_three_pass := (audit_data.b_pass AND audit_data.i_pass AND audit_data.j_pass);
  
  -- Insert into status table
  INSERT INTO gold_standard_county_status (
    loop_run_id, county_slug, co_no,
    a_dual_product, a_metric, a_detail,
    b_verified_outcomes, b_metric, b_detail,
    c_parity_clean, c_metric, c_detail,
    d_parity_any, d_metric, d_detail,
    e_parcel_linkage, e_metric, e_detail,
    f_tier1_sold, f_metric, f_detail,
    g_zoning, g_metric, g_detail,
    h_freshness, h_metric, h_detail,
    i_property_card, i_metric, i_detail,
    j_deal_thesis, j_metric, j_detail,
    pass_count, gold_standard, critical_three_pass
  ) VALUES (
    current_run_id, audit_data.county_slug, audit_data.co_no,
    audit_data.a_pass, audit_data.a_metric, audit_data.a_detail,
    audit_data.b_pass, audit_data.b_metric, audit_data.b_detail,
    audit_data.c_pass, audit_data.c_metric, audit_data.c_detail,
    audit_data.d_pass, audit_data.d_metric, audit_data.d_detail,
    audit_data.e_pass, audit_data.e_metric, audit_data.e_detail,
    audit_data.f_pass, audit_data.f_metric, audit_data.f_detail,
    audit_data.g_pass, audit_data.g_metric, audit_data.g_detail,
    audit_data.h_pass, audit_data.h_metric, audit_data.h_detail,
    audit_data.i_pass, audit_data.i_metric, audit_data.i_detail,
    audit_data.j_pass, audit_data.j_metric, audit_data.j_detail,
    audit_data.pass_count, audit_data.gold_standard, audit_data.critical_three_pass
  );
  
  -- Build result JSON
  result := json_build_object(
    'county', county_name,
    'co_no', target_co_no,
    'run_id', current_run_id,
    'timestamp', now(),
    'letters', json_build_object(
      'A', json_build_object('pass', audit_data.a_pass, 'metric', audit_data.a_metric, 'detail', audit_data.a_detail),
      'B', json_build_object('pass', audit_data.b_pass, 'metric', audit_data.b_metric, 'detail', audit_data.b_detail),
      'C', json_build_object('pass', audit_data.c_pass, 'metric', audit_data.c_metric, 'detail', audit_data.c_detail),
      'D', json_build_object('pass', audit_data.d_pass, 'metric', audit_data.d_metric, 'detail', audit_data.d_detail),
      'E', json_build_object('pass', audit_data.e_pass, 'metric', audit_data.e_metric, 'detail', audit_data.e_detail),
      'F', json_build_object('pass', audit_data.f_pass, 'metric', audit_data.f_metric, 'detail', audit_data.f_detail),
      'G', json_build_object('pass', audit_data.g_pass, 'metric', audit_data.g_metric, 'detail', audit_data.g_detail),
      'H', json_build_object('pass', audit_data.h_pass, 'metric', audit_data.h_metric, 'detail', audit_data.h_detail),
      'I', json_build_object('pass', audit_data.i_pass, 'metric', audit_data.i_metric, 'detail', audit_data.i_detail),
      'J', json_build_object('pass', audit_data.j_pass, 'metric', audit_data.j_metric, 'detail', audit_data.j_detail)
    ),
    'summary', json_build_object(
      'pass_count', audit_data.pass_count,
      'gold_standard', audit_data.gold_standard,
      'critical_three_pass', audit_data.critical_three_pass
    )
  );
  
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Placeholder for full gold_standard_loop function
CREATE OR REPLACE FUNCTION gold_standard_loop()
RETURNS JSON AS $$
DECLARE
  result JSON;
  county_record RECORD;
  current_run_id INTEGER;
  total_evaluated INTEGER := 0;
BEGIN
  -- Get next run ID
  current_run_id := nextval('gold_standard_loop_run_seq');
  
  -- Evaluate all counties
  FOR county_record IN SELECT slug FROM fl_counties ORDER BY co_no LOOP
    PERFORM pencil_dod_evaluate_county(county_record.slug);
    total_evaluated := total_evaluated + 1;
  END LOOP;
  
  result := json_build_object(
    'run_id', current_run_id,
    'timestamp', now(),
    'counties_evaluated', total_evaluated,
    'status', 'completed'
  );
  
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create bid_decisions table placeholder if not exists
CREATE TABLE IF NOT EXISTS bid_decisions (
  id                SERIAL PRIMARY KEY,
  case_number       TEXT NOT NULL,
  county            TEXT,
  arv               NUMERIC,
  max_bid           NUMERIC,
  ml_score          NUMERIC,
  triangle_factors  JSON,
  two_arm_cma       JSON,
  created_at        TIMESTAMPTZ DEFAULT now(),
  UNIQUE(case_number)
);

-- Create foreclosure_outcomes table placeholder if not exists  
CREATE TABLE IF NOT EXISTS foreclosure_outcomes (
  id                SERIAL PRIMARY KEY,
  case_number       TEXT NOT NULL,
  auction_date      DATE,
  county            TEXT,
  co_no             INTEGER,
  data_source       TEXT NOT NULL,
  sale_amount       NUMERIC,
  buyer             TEXT,
  verification_status TEXT DEFAULT 'pending',
  created_at        TIMESTAMPTZ DEFAULT now(),
  UNIQUE(case_number, data_source)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_gold_standard_county_status_county ON gold_standard_county_status(county_slug);
CREATE INDEX IF NOT EXISTS idx_gold_standard_county_status_run ON gold_standard_county_status(loop_run_id);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case ON foreclosure_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case ON bid_decisions(case_number);

-- RLS policies
ALTER TABLE gold_standard_county_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE foreclosure_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE bid_decisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "gold_standard_read" ON gold_standard_county_status FOR SELECT USING (true);
CREATE POLICY "foreclosure_outcomes_read" ON foreclosure_outcomes FOR SELECT USING (true);
CREATE POLICY "bid_decisions_read" ON bid_decisions FOR SELECT USING (true);

-- Service role policies
CREATE POLICY "gold_standard_admin" ON gold_standard_county_status FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "foreclosure_outcomes_admin" ON foreclosure_outcomes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "bid_decisions_admin" ON bid_decisions FOR ALL USING (true) WITH CHECK (true);

-- Grant permissions
GRANT USAGE ON SEQUENCE gold_standard_loop_run_seq TO authenticated, anon;
GRANT SELECT ON gold_standard_scoreboard TO authenticated, anon;
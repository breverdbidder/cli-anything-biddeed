-- Enricher
CREATE TABLE IF NOT EXISTS property_profiles (
  id BIGSERIAL PRIMARY KEY,
  parcel_id TEXT UNIQUE NOT NULL,
  owner_name TEXT, owner_type TEXT,
  assessed_value BIGINT, market_value BIGINT,
  delinquent BOOLEAN DEFAULT FALSE,
  sale_type TEXT, action TEXT, max_bid BIGINT,
  motivation_score INT, confidence FLOAT,
  enriched_at TIMESTAMPTZ, raw_json JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pp_action ON property_profiles(action);

-- Forecaster
CREATE TABLE IF NOT EXISTS rehab_projects (
  id BIGSERIAL PRIMARY KEY,
  parcel_id TEXT, project_name TEXT, template TEXT,
  total_budget NUMERIC, total_spent NUMERIC DEFAULT 0,
  total_forecast NUMERIC, variance_pct FLOAT,
  status TEXT DEFAULT 'ACTIVE',
  start_date DATE, projected_weeks INT, arv NUMERIC,
  alerts_json JSONB, scenarios_json JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rp_parcel ON rehab_projects(parcel_id);

CREATE TABLE IF NOT EXISTS rehab_spend_log (
  id BIGSERIAL PRIMARY KEY,
  project_id BIGINT, parcel_id TEXT,
  category TEXT NOT NULL, amount NUMERIC NOT NULL,
  description TEXT, vendor TEXT, spend_date DATE DEFAULT CURRENT_DATE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rsl_parcel ON rehab_spend_log(parcel_id);

-- TrendPredictor
CREATE TABLE IF NOT EXISTS market_trends (
  id BIGSERIAL PRIMARY KEY,
  zip_code TEXT NOT NULL, submarket_name TEXT,
  direction_score FLOAT, direction_label TEXT,
  timing_action TEXT, cycle_phase TEXT,
  vacancy_rate FLOAT, median_sale_price BIGINT,
  foreclosure_trend TEXT, signal_breakdown JSONB,
  geojson_feature JSONB, confidence FLOAT,
  horizon_months INT, analyzed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(zip_code, analyzed_at)
);
CREATE INDEX IF NOT EXISTS idx_mt_zip ON market_trends(zip_code);

-- SiteManager
CREATE TABLE IF NOT EXISTS rehab_site_reports (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT UNIQUE NOT NULL, parcel_id TEXT, address TEXT,
  site_health_score INT, schedule_health INT,
  safety_score INT, quality_score INT,
  status TEXT DEFAULT 'ACTIVE', overall_pct INT DEFAULT 0,
  action_count INT DEFAULT 0, budget NUMERIC, template TEXT,
  gc_name TEXT, projected_completion DATE,
  geojson_feature JSONB, report_json JSONB,
  reported_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rsr_parcel ON rehab_site_reports(parcel_id);
CREATE INDEX IF NOT EXISTS idx_rsr_health ON rehab_site_reports(site_health_score);

CREATE TABLE IF NOT EXISTS rehab_site_photos (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT, phase TEXT, filename TEXT,
  storage_url TEXT, notes TEXT, analysis_json JSONB,
  uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

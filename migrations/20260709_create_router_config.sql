-- Create certify_router_config table (required by certify router workflow)
CREATE TABLE IF NOT EXISTS public.certify_router_config (
  id BIGSERIAL PRIMARY KEY,
  router_name VARCHAR(100) NOT NULL DEFAULT 'primary',
  max_concurrent_counties INTEGER DEFAULT 10,
  retry_attempts INTEGER DEFAULT 3,
  enable_shadow_audit BOOLEAN DEFAULT true,
  certification_criteria JSONB DEFAULT '{"consecutive_gold_min": 10, "false_positive_threshold": 0.01, "data_freshness_hours": 24}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(router_name)
);

-- Insert default config if not exists
INSERT INTO public.certify_router_config (router_name, max_concurrent_counties)
VALUES ('primary', 10)
ON CONFLICT (router_name) DO NOTHING;

SELECT 'Router config initialized' as result;

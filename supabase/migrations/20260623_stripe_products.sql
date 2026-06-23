-- Migration: stripe_products — BidDeed subscription tiers
-- Created: 2026-06-23

CREATE TABLE IF NOT EXISTS stripe_products (
  id                      BIGSERIAL PRIMARY KEY,
  tier_id                 TEXT NOT NULL UNIQUE,
  name                    TEXT NOT NULL,
  product_id              TEXT NOT NULL DEFAULT 'PENDING',
  stripe_price_id_monthly TEXT,
  stripe_price_id_annual  TEXT,
  stripe_s5_price_id      TEXT,
  live_mode               BOOLEAN NOT NULL DEFAULT FALSE,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stripe_products_tier ON stripe_products(tier_id);

CREATE OR REPLACE FUNCTION update_stripe_products_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_stripe_products_updated_at ON stripe_products;
CREATE TRIGGER trg_stripe_products_updated_at
  BEFORE UPDATE ON stripe_products
  FOR EACH ROW EXECUTE FUNCTION update_stripe_products_updated_at();

INSERT INTO stripe_products (tier_id, name) VALUES
  ('investor',   'BidDeed Investor'),
  ('pro',        'BidDeed Pro'),
  ('proplus',    'BidDeed Pro Plus'),
  ('enterprise', 'BidDeed Enterprise')
ON CONFLICT (tier_id) DO NOTHING;

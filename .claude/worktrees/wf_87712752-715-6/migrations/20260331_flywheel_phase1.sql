-- =============================================================
-- FLYWHEEL PHASE 1: Data Layer
-- Issue: breverdbidder/cli-anything-biddeed#122
-- Date: 2026-03-31
-- =============================================================

-- ── customer_buyboxes ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer_buyboxes (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users(id),
  name text NOT NULL,
  target_zips text[] NOT NULL,
  property_types text[],
  auction_types text[] DEFAULT '{foreclosure,tax_deed}',
  min_arv numeric,
  max_bid_budget numeric,
  min_roi_pct numeric DEFAULT 15,
  min_profit numeric DEFAULT 20000,
  active boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- ── customer_behavior ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer_behavior (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id uuid NOT NULL,
  event_type text NOT NULL,
  zip_code text,
  property_type text,
  price_range numrange,
  auction_type text,
  session_id text,
  created_at timestamptz DEFAULT now()
);

-- ── customer_alerts ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer_alerts (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id uuid NOT NULL,
  buybox_id uuid REFERENCES customer_buyboxes(id),
  case_number text NOT NULL,
  auction_date date NOT NULL,
  channel text NOT NULL,
  alert_content jsonb NOT NULL,
  predicted_price numeric,
  predicted_third_party_prob numeric,
  predicted_win_prob numeric,
  predicted_profit numeric,
  customer_action text,
  actual_outcome jsonb,
  reward_score numeric,
  sent_at timestamptz DEFAULT now()
);

-- ── Indexes ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_buybox_user     ON customer_buyboxes(user_id);
CREATE INDEX IF NOT EXISTS idx_buybox_active   ON customer_buyboxes(user_id, active) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_behavior_user   ON customer_behavior(user_id);
CREATE INDEX IF NOT EXISTS idx_behavior_event  ON customer_behavior(user_id, event_type);
CREATE INDEX IF NOT EXISTS idx_alerts_user     ON customer_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_auction  ON customer_alerts(auction_date);
CREATE INDEX IF NOT EXISTS idx_alerts_buybox   ON customer_alerts(buybox_id);

-- ── customer_accuracy view ──────────────────────────────────
CREATE OR REPLACE VIEW customer_accuracy AS
SELECT
  user_id,
  count(*)                                                                          AS total_alerts,
  count(*) FILTER (WHERE customer_action = 'bid')                                  AS bids_placed,
  avg(reward_score) FILTER (WHERE reward_score IS NOT NULL)                        AS avg_accuracy,
  sum(CASE WHEN reward_score > 0 THEN 1 ELSE 0 END)::float /
    NULLIF(count(*) FILTER (WHERE reward_score IS NOT NULL), 0)                    AS win_rate,
  avg(predicted_profit) FILTER (WHERE customer_action = 'bid'
    AND reward_score > 0)                                                           AS avg_profit_on_wins
FROM customer_alerts
GROUP BY user_id;

-- ── RLS ─────────────────────────────────────────────────────
ALTER TABLE customer_buyboxes  ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_behavior  ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_alerts    ENABLE ROW LEVEL SECURITY;

-- customer_buyboxes policies
DROP POLICY IF EXISTS "Users own their buyboxes"   ON customer_buyboxes;
DROP POLICY IF EXISTS "Users insert their buyboxes" ON customer_buyboxes;
DROP POLICY IF EXISTS "Users update their buyboxes" ON customer_buyboxes;
DROP POLICY IF EXISTS "Users delete their buyboxes" ON customer_buyboxes;

CREATE POLICY "Users own their buyboxes"
  ON customer_buyboxes FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users insert their buyboxes"
  ON customer_buyboxes FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update their buyboxes"
  ON customer_buyboxes FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users delete their buyboxes"
  ON customer_buyboxes FOR DELETE
  USING (auth.uid() = user_id);

-- customer_behavior policies
DROP POLICY IF EXISTS "Users own their behavior"   ON customer_behavior;
DROP POLICY IF EXISTS "Users insert their behavior" ON customer_behavior;

CREATE POLICY "Users own their behavior"
  ON customer_behavior FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users insert their behavior"
  ON customer_behavior FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- customer_alerts policies
DROP POLICY IF EXISTS "Users own their alerts"   ON customer_alerts;

CREATE POLICY "Users own their alerts"
  ON customer_alerts FOR SELECT
  USING (auth.uid() = user_id);

-- Service role bypass (for backend/match engine writes)
-- Service role always bypasses RLS — no policy needed.

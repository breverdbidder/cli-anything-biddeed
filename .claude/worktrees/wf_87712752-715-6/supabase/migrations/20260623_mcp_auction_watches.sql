-- Migration: auction_watches — S4 monitoring subscriptions
-- Created: 2026-06-23 | Idempotent

CREATE TABLE IF NOT EXISTS auction_watches (
  id            BIGSERIAL PRIMARY KEY,
  case_number   TEXT NOT NULL,
  county        TEXT NOT NULL,
  customer_id   TEXT NOT NULL DEFAULT '',
  notify_email  TEXT,
  notify_phone  TEXT,
  alert_types   TEXT[] NOT NULL DEFAULT '{}',
  max_bid       NUMERIC(14,2),
  sale_date     DATE,
  status        TEXT NOT NULL DEFAULT 'active',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_notified_at TIMESTAMPTZ
);

ALTER TABLE auction_watches ADD COLUMN IF NOT EXISTS customer_id       TEXT NOT NULL DEFAULT '';
ALTER TABLE auction_watches ADD COLUMN IF NOT EXISTS last_notified_at  TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_auction_watches_case    ON auction_watches(case_number);
CREATE INDEX IF NOT EXISTS idx_auction_watches_cust    ON auction_watches(customer_id);
CREATE INDEX IF NOT EXISTS idx_auction_watches_date    ON auction_watches(sale_date) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS idx_auction_watches_unique ON auction_watches(case_number, customer_id);

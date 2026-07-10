-- SPRINT3 P1: Connector Directory readiness tracking
-- dispatch_id: 039f7a54-c74d-4850-b925-137ad225db02
--
-- Two new tables:
--   directory_readiness  — one row per Claude Connectors Directory submission
--                           requirement (annotations, transport, oauth, assets, ...)
--   review_test_account  — reviewer credentials metadata (hash + prefix only,
--                           never the raw bd_ key — see mcp_api_keys for that pattern)

CREATE TABLE IF NOT EXISTS directory_readiness (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item        text NOT NULL,
  status      text NOT NULL CHECK (status IN ('pass', 'fail', 'human_needed')),
  evidence    text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_test_account (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id       uuid NOT NULL,
  email             text NOT NULL,
  key_prefix        text NOT NULL,
  key_hash          text NOT NULL,
  tier              text NOT NULL,
  credentials_doc   text NOT NULL,
  expires_at        timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now()
);

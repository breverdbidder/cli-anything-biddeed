-- Sunbiz bulk SFTP sync: fresh table for FL DOS/Division of Corporations
-- corporate-entity records, hydrated from the public SFTP bulk-download
-- service (sftp.floridados.gov, doc/quarterly/cor/cordata.zip baseline +
-- doc/cor/<YYYYMMDD>c.txt daily deltas -- NOT doc/daily/cor as originally
-- briefed; that path does not exist on the server, see sync script header).
--
-- Additive data source for buyer/owner corporate-entity piercing in the
-- Winner Data / BidDeed pipeline. NOT wired into any live query path yet --
-- follow-up once spot-checked. service_role only: this table is not on the
-- anon-readable allowlist and must not be added to it without Ariel's
-- sign-off (per issue scope).

BEGIN;

CREATE TABLE IF NOT EXISTS public.sunbiz_entities (
  document_number text PRIMARY KEY,
  entity_name text NOT NULL,
  entity_type text,
  status text,
  date_filed date,
  last_transaction_date date,
  more_than_six_officers boolean,
  state_of_formation text,
  fei_ein text,

  principal_address_line1 text,
  principal_city text,
  principal_state text,
  principal_zip text,
  principal_country text,

  mailing_address_line1 text,
  mailing_city text,
  mailing_state text,
  mailing_zip text,
  mailing_country text,

  registered_agent_name text,
  registered_agent_address text,

  officers jsonb DEFAULT '[]'::jsonb,

  source_file text NOT NULL,
  last_synced_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sunbiz_entities_entity_name_idx
  ON public.sunbiz_entities USING gin (to_tsvector('english', entity_name));

CREATE INDEX IF NOT EXISTS sunbiz_entities_registered_agent_name_idx
  ON public.sunbiz_entities (registered_agent_name);

ALTER TABLE public.sunbiz_entities ENABLE ROW LEVEL SECURITY;

-- service_role only -- no anon/authenticated policy, matching the issue's
-- explicit instruction that this table is not anon-readable.
REVOKE ALL ON public.sunbiz_entities FROM anon, authenticated;

CREATE POLICY service_role_all ON public.sunbiz_entities
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

COMMIT;

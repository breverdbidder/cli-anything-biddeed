-- Issue #19712: FF billable-loop -- per-lead enrichment state machine + attempt ledger.
--
-- Replaces the single-pass FF enrichment (0 provider attempts logged on any
-- of the 37 rows as of 2026-09-02, 22/37 non-billable) with a resumable state
-- machine on the existing winnerdata.ff_batch_leads.row_enrichment_status
-- column, backed by a new attempt ledger that gives every provider call an
-- evidence row (Honesty Protocol M4 -- a stage with no ledger row did not
-- happen).
--
-- Scope pre-approved by Ariel 2026-09-02 in docs/intent/19712.md: new ledger
-- table + CHECK constraints are in scope; nothing beyond them.

BEGIN;

-- ============================================================
-- 0. Unique key the claim protocol and the ledger FK key off (SSOT per
--    intent: "winnerdata.ff_batch_leads keyed (batch_date, case_number)").
--    No duplicate (batch_date, case_number) pairs exist today (verified) so
--    this is safe. Added first -- the ledger table's FK below needs it.
-- ============================================================

ALTER TABLE winnerdata.ff_batch_leads
  ADD CONSTRAINT ff_batch_leads_batch_date_case_number_key
  UNIQUE (batch_date, case_number);

-- ============================================================
-- 1. Attempt ledger -- one row per provider call, no exceptions.
-- ============================================================

CREATE TABLE IF NOT EXISTS winnerdata.ff_enrichment_attempts (
  id            bigint generated always as identity primary key,
  batch_date    date NOT NULL,
  case_number   text NOT NULL,
  stage         text NOT NULL CHECK (stage IN (
                  'stage1_identity', 'stage2_sunbiz_chain', 'stage3_skiptrace',
                  'stage4_web', 'stage5_dnc'
                )),
  provider      text NOT NULL,
  input_json    jsonb NOT NULL DEFAULT '{}'::jsonb,
  output_json   jsonb NOT NULL DEFAULT '{}'::jsonb,
  outcome       text NOT NULL CHECK (outcome IN ('hit', 'miss', 'error', 'skipped_gate')),
  credits_used  integer NOT NULL DEFAULT 0,
  attempted_at  timestamptz NOT NULL DEFAULT now(),
  run_id        text NOT NULL,
  FOREIGN KEY (batch_date, case_number)
    REFERENCES winnerdata.ff_batch_leads (batch_date, case_number)
);

CREATE INDEX IF NOT EXISTS ff_enrichment_attempts_lead_idx
  ON winnerdata.ff_enrichment_attempts (batch_date, case_number);
CREATE INDEX IF NOT EXISTS ff_enrichment_attempts_stage_idx
  ON winnerdata.ff_enrichment_attempts (stage, outcome);
CREATE INDEX IF NOT EXISTS ff_enrichment_attempts_run_idx
  ON winnerdata.ff_enrichment_attempts (run_id);

ALTER TABLE winnerdata.ff_enrichment_attempts ENABLE ROW LEVEL SECURITY;
-- No anon policy (M2): only service_role/postgres can read or write this
-- ledger. This is internal evidence, never a client-facing surface.

COMMENT ON TABLE winnerdata.ff_enrichment_attempts IS
  'Issue #19712: one row per enrichment provider call the billable-loop '
  'runner makes for a lead. A stage with no row here did not happen -- '
  'required evidence for EXHAUSTED (every applicable stage must have a '
  'miss/error row) and for the Honesty Protocol M4 evidence standard.';

-- ============================================================
-- 2. row_enrichment_status: replace the old 4-value CHECK with the
--    9-value state machine. The 2 rows currently 'running' never had a
--    provider attempt logged (enrichment_provider_status_json is empty on
--    all 37) so they are not mid-flight -- map them to 'not_started' so the
--    claim protocol (which claims from not_started/retry_due) picks them up.
-- ============================================================

UPDATE winnerdata.ff_batch_leads
SET row_enrichment_status = 'not_started'
WHERE row_enrichment_status = 'running';

ALTER TABLE winnerdata.ff_batch_leads
  DROP CONSTRAINT IF EXISTS ff_batch_leads_row_enrichment_status_check;

ALTER TABLE winnerdata.ff_batch_leads
  ADD CONSTRAINT ff_batch_leads_row_enrichment_status_check
  CHECK (row_enrichment_status IN (
    'not_started', 'stage1_identity', 'stage2_sunbiz_chain', 'stage3_skiptrace',
    'stage4_web', 'stage5_dnc', 'BILLABLE', 'EXHAUSTED', 'retry_due'
  ));

-- ============================================================
-- 3. contact_confidence: canonical 5-string CHECK + migrate existing values.
--    'VERIFIED-CROSS-CHECKED' (11 rows, hyphen variant) and
--    'VERIFIED_CROSS_CHECKED' (1 row, underscore variant) both collapse to
--    the canonical 'VERIFIED·CROSS-CHECKED'; 'LIKELY-SINGLE-SOURCE'
--    (2 rows) to 'LIKELY·SINGLE SOURCE'; the 8 NULLs to 'NOT AVAILABLE'
--    (no confidence was ever assigned -- 'not available' is the honest
--    default until a stage produces evidence). 'NOT AVAILABLE' (15 rows) is
--    already canonical.
-- ============================================================

UPDATE winnerdata.ff_batch_leads
SET contact_confidence = 'VERIFIED·CROSS-CHECKED'
WHERE contact_confidence IN ('VERIFIED-CROSS-CHECKED', 'VERIFIED_CROSS_CHECKED');

UPDATE winnerdata.ff_batch_leads
SET contact_confidence = 'LIKELY·SINGLE SOURCE'
WHERE contact_confidence = 'LIKELY-SINGLE-SOURCE';

UPDATE winnerdata.ff_batch_leads
SET contact_confidence = 'NOT AVAILABLE'
WHERE contact_confidence IS NULL;

ALTER TABLE winnerdata.ff_batch_leads
  ADD CONSTRAINT ff_batch_leads_contact_confidence_check
  CHECK (contact_confidence IN (
    'VERIFIED·PRIMARY', 'VERIFIED·CROSS-CHECKED',
    'LIKELY·SINGLE SOURCE', 'UNCONFIRMED CLAIM', 'NOT AVAILABLE'
  ));

COMMIT;

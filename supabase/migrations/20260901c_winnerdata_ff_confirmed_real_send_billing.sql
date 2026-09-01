-- Issue #19659: real producer emails are now on file (Mariam, Adina, Colleen
-- -- winnerdata.producers.email populated 2026-09-01). This ships the parts
-- of #19659 that were blocked on that data gap:
--   1. recipient_kind on winnerdata.ff_digest_log (item 2) so a send can be
--      tagged 'producer' (real, billable-eligible) / 'internal_qa' (real,
--      never billable) / 'sandbox' (Resend test address, never a real send).
--   2. A hard DB-side backstop (trigger) that refuses to ever let a
--      status='sent' row persist with a *.resend.dev recipient, even if a
--      caller bypasses the Python-side guard in
--      scripts/winnerdata_ff_digest_lib.py.
--   3. winnerdata.has_confirmed_real_send(batch_date) -- the single source
--      of truth for "did a real, non-sandbox send actually happen for this
--      seller_digest batch" -- and rewiring both the billable-events
--      backfill and the revenue_ledger trigger to require it (item 3).
--   4. New-row billing switched to Ariel's Aug 31 decision: $12.50 flat per
--      billable FF, no success fee (item 5). Historical scenario_a/
--      scenario_b columns are untouched -- this only changes what future
--      inserts bill.
--
-- Reconciliation (item 4) is NOT schema work -- see the session's SQL
-- verification for the actual query/counts. This migration only voids the
-- one artifact that was actively wrong under the new standard: a $27.00
-- DRAFT invoice (finance.invoices id 09a07ba8-efca-4dfc-91f9-5912e7e76d6e,
-- never sent/paid) built off 3 of the 13 backfilled billable_ff_events rows,
-- none of which have ever had a confirmed real send. Voiding a still-draft
-- invoice and its 3 revenue_ledger lines is a straight correction, not a
-- policy call -- it was wrong the moment it was created, this just makes
-- that visible instead of leaving a collectible-looking artifact on file.

BEGIN;

-- ============================================================
-- 1. recipient_kind + expanded status vocabulary
-- ============================================================

ALTER TABLE winnerdata.ff_digest_log
  ADD COLUMN IF NOT EXISTS recipient_kind text
    CHECK (recipient_kind IN ('producer', 'internal_qa', 'sandbox'));

COMMENT ON COLUMN winnerdata.ff_digest_log.recipient_kind IS
  'issue #19659: producer = real send to a producer email on file, billable-eligible. '
  'internal_qa = real send to an internal Everest/BidDeed address (Ariel QA/review), '
  'never billable. sandbox = Resend test address (*.resend.dev) -- always blocked '
  'from status=sent, never a real delivery regardless of what Resend reports.';

ALTER TABLE winnerdata.ff_digest_log DROP CONSTRAINT ff_digest_log_status_check;
ALTER TABLE winnerdata.ff_digest_log
  ADD CONSTRAINT ff_digest_log_status_check
  CHECK (status IN ('sent', 'no_leads_sent', 'blocked_no_email', 'blocked_sandbox_recipient', 'error'));

-- Backfill recipient_kind for the 4 pre-existing rows so the reconciliation
-- query below (and any future audit) has an honest historical answer, not a
-- NULL gap. Same domain rule as scripts/winnerdata_ff_digest_lib.py's
-- classify_recipient() -- kept in exact sync, see the trigger below.
UPDATE winnerdata.ff_digest_log
SET recipient_kind = CASE
  WHEN recipient IS NULL THEN NULL
  WHEN lower(split_part(recipient, '@', 2)) = 'resend.dev'
    OR lower(split_part(recipient, '@', 2)) LIKE '%.resend.dev' THEN 'sandbox'
  WHEN lower(split_part(recipient, '@', 2)) IN ('biddeed.ai', 'everestcapitalusa.com') THEN 'internal_qa'
  ELSE 'producer'
END
WHERE recipient_kind IS NULL;

-- ============================================================
-- 2. DB-side backstop: a sandbox recipient can never persist as 'sent'.
--    Defense in depth behind the Python-side guard in
--    winnerdata_ff_send_approved.py -- if anything ever bypasses that
--    script and inserts directly, this still holds the line.
-- ============================================================

CREATE OR REPLACE FUNCTION winnerdata.enforce_ff_digest_log_real_send()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_domain text := lower(split_part(NEW.recipient, '@', 2));
BEGIN
  IF NEW.status = 'sent' AND NEW.recipient IS NOT NULL
     AND (v_domain = 'resend.dev' OR v_domain LIKE '%.resend.dev') THEN
    RAISE EXCEPTION 'winnerdata.ff_digest_log: refusing to persist status=sent for sandbox recipient %', NEW.recipient;
  END IF;

  IF NEW.recipient_kind IS NULL AND NEW.recipient IS NOT NULL THEN
    NEW.recipient_kind := CASE
      WHEN v_domain = 'resend.dev' OR v_domain LIKE '%.resend.dev' THEN 'sandbox'
      WHEN v_domain IN ('biddeed.ai', 'everestcapitalusa.com') THEN 'internal_qa'
      ELSE 'producer'
    END;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ff_digest_log_real_send ON winnerdata.ff_digest_log;
CREATE TRIGGER trg_ff_digest_log_real_send
  BEFORE INSERT OR UPDATE ON winnerdata.ff_digest_log
  FOR EACH ROW
  EXECUTE FUNCTION winnerdata.enforce_ff_digest_log_real_send();

-- ============================================================
-- 3. has_confirmed_real_send() -- single source of truth for "a real send
--    happened for this batch". Scoped to batch_kind='seller_digest'
--    because that is the only pipeline with a send step that writes to
--    ff_digest_log at all (scripts/winnerdata_ff_send_approved.py) --
--    the nine_case_portfolio pipeline (issue #19531) has no send/logging
--    step today, so it can never produce a confirmed real send and never
--    should silently inherit one from an unrelated seller_digest batch
--    that happens to share the same calendar date.
-- ============================================================

CREATE OR REPLACE FUNCTION winnerdata.has_confirmed_real_send(p_batch_date date)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM winnerdata.ff_digest_log dl
    JOIN winnerdata.ff_batches fb
      ON fb.batch_date = dl.batch_date AND fb.batch_kind = 'seller_digest'
    WHERE dl.batch_date = p_batch_date
      AND dl.status = 'sent'
      AND dl.recipient_kind = 'producer'
  );
$$;

COMMENT ON FUNCTION winnerdata.has_confirmed_real_send(date) IS
  'issue #19659 item 3: true only if a real (non-sandbox, non-internal-QA) '
  'send actually landed for this seller_digest batch_date, per '
  'winnerdata.ff_digest_log. This is the sole gate for billable_ff_events '
  'creation and revenue_ledger auto-write -- no other path may mark a batch billable.';

-- ============================================================
-- 4. Rewire the billable-events backfill to require it.
-- ============================================================

CREATE OR REPLACE FUNCTION winnerdata.winnerdata_billable_backfill()
RETURNS TABLE(out_batch_date date, out_auction_id uuid, out_case_number text, out_action text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_org_id uuid := '032f4717-545f-4a18-b48b-28ea4257699d'; -- Protection Partners (winnerdata.organizations)
BEGIN
  RETURN QUERY
  INSERT INTO winnerdata.billable_ff_events (
    org_id, delivered_at, monetization_tier_met, monetization_basis,
    source_batch_date, source_auction_id
  )
  SELECT
    v_org_id,
    fbl.created_at,
    true,
    jsonb_build_object(
      'source', 'winnerdata_billable_backfill',
      'case_number', fbl.case_number,
      'qa_status', fbl.qa_status,
      'billability_rule', 'qa_status = CONTACT_ENRICHED (FF_DAILY_SOP.md sec 2) AND confirmed real send (#19659)'
    ),
    fbl.batch_date,
    fbl.auction_id
  FROM winnerdata.ff_batch_leads fbl
  WHERE fbl.qa_status = 'CONTACT_ENRICHED'
    AND winnerdata.has_confirmed_real_send(fbl.batch_date)
  ON CONFLICT (source_batch_date, source_auction_id) WHERE source_batch_date IS NOT NULL DO NOTHING
  RETURNING
    billable_ff_events.source_batch_date,
    billable_ff_events.source_auction_id,
    (billable_ff_events.monetization_basis ->> 'case_number'),
    'inserted'::text;
END;
$$;

-- ============================================================
-- 5. Revenue-ledger trigger: require confirmed real send (belt-and-
--    suspenders even though step 4 already gates creation), and bill
--    new rows at Ariel's Aug 31 decision -- $12.50 flat, no success fee.
--    scenario_a_*/scenario_b_* columns stay on the row unchanged for
--    historical comparison (winnerdata.v_billable_ff_comparison); only
--    what actually gets billed changes.
-- ============================================================

CREATE OR REPLACE FUNCTION finance.fn_billable_ff_events_to_revenue_ledger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_amount_cents integer;
BEGIN
  v_amount_cents := NEW.scenario_b_flat_fee_cents;

  INSERT INTO finance.revenue_ledger (
    occurred_on, entity_code, customer, source, ref_table, ref_id,
    amount_cents, status, notes
  ) VALUES (
    COALESCE(NEW.delivered_at::date, current_date),
    'protection_partners',
    'Protection Partners (Mariam)',
    'ff_billing',
    'winnerdata.billable_ff_events',
    NEW.id,
    v_amount_cents,
    'pending',
    format(
      'Scenario B (flat fee, Ariel decision 2026-08-31, issue #19659) billed: $%s. '
      'Scenario A (delivery+success fee, retired for new billing) = $%s (not billed, comparison only).',
      to_char(v_amount_cents / 100.0, 'FM999999990.00'),
      to_char(
        (NEW.scenario_a_delivery_fee_cents
          + CASE WHEN NEW.bound_at IS NOT NULL THEN NEW.scenario_a_success_fee_cents ELSE 0 END) / 100.0,
        'FM999999990.00'
      )
    )
  );
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_billable_ff_events_revenue_ledger ON winnerdata.billable_ff_events;
CREATE TRIGGER trg_billable_ff_events_revenue_ledger
  AFTER INSERT ON winnerdata.billable_ff_events
  FOR EACH ROW
  WHEN (NEW.monetization_tier_met = true
        AND NEW.source_batch_date IS NOT NULL
        AND winnerdata.has_confirmed_real_send(NEW.source_batch_date))
  EXECUTE FUNCTION finance.fn_billable_ff_events_to_revenue_ledger();

-- ============================================================
-- 6. Reconciliation fix: void the one artifact that was already wrong
--    under this standard -- a still-DRAFT invoice built off 3 of the 13
--    pre-#19659 backfilled events, none of which have a confirmed real
--    send. Never sent/paid, so voiding it has zero external effect.
-- ============================================================

UPDATE finance.invoices
SET status = 'void'
WHERE id = '09a07ba8-efca-4dfc-91f9-5912e7e76d6e'
  AND status = 'draft';

UPDATE finance.revenue_ledger
SET status = 'void',
    notes = notes || ' [VOIDED 2026-09-01 per issue #19659: source billable_ff_events row lacks a confirmed real send -- was backfilled off qa_status alone, pre-dates the confirmed-send billing standard.]'
WHERE ref_table = 'winnerdata.billable_ff_events'
  AND status IN ('pending', 'invoiced')
  AND ref_id IN (
    SELECT bfe.id
    FROM winnerdata.billable_ff_events bfe
    WHERE bfe.source_batch_date IS NOT NULL
      AND NOT winnerdata.has_confirmed_real_send(bfe.source_batch_date)
  );

-- Read-only visibility view for the reconciliation report -- not required
-- by any code path, kept so this state stays queryable after this session.
CREATE OR REPLACE VIEW winnerdata.v_billable_ff_events_confirmation_status AS
SELECT
  bfe.id,
  bfe.source_batch_date,
  bfe.source_auction_id,
  bfe.monetization_basis ->> 'case_number' AS case_number,
  bfe.delivered_at,
  winnerdata.has_confirmed_real_send(bfe.source_batch_date) AS confirmed_real_send
FROM winnerdata.billable_ff_events bfe
ORDER BY bfe.delivered_at;

COMMIT;

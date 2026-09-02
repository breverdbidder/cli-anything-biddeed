-- Issue #19738 CP6: synthetic bank_transactions fixture, used only while #19737's real
-- Plaid ingestion has 0 rows in finance.bank_transactions. Tagged via
-- finance.bank_connections.status='fixture' (propagates to bank_accounts/bank_transactions
-- via the join finance.recon_run() and finance.v_recon_summary already use, and is what the
-- CFO dashboard's REAL/FIXTURE badge keys off). Built from REAL stripe.payouts and
-- finance.expense_ledger rows so recon_run() is exercised against real amounts/dates.
--
-- Idempotent: guarded on "does a fixture connection already exist for this entity".
-- Safe to delete wholesale once #19737 lands real rows: `delete from finance.bank_connections
-- where status = 'fixture'` cascades nothing on its own (no FK cascade defined), so also
-- clean bank_accounts/bank_transactions rows tied to fixture connection ids -- see
-- PORTING_NOTES.md "removing the fixture" section.

do $$
declare
  v_biddeed_conn uuid;
  v_biddeed_acct uuid;
  v_biddeed_bank_account_id uuid;
  v_everest_conn uuid;
  v_everest_acct uuid;
  v_everest_bank_account_id uuid;
  p record;
begin
  if exists (select 1 from finance.bank_connections where entity_code = 'biddeed' and status = 'fixture') then
    raise notice 'biddeed fixture connection already exists, skipping';
  else
    select id into v_biddeed_bank_account_id from finance.accounts where entity_code = 'biddeed' and code = '1000';

    insert into finance.bank_connections (plaid_item_id, entity_code, institution_name, status)
    values ('fixture-item-biddeed', 'biddeed', 'Wells Fargo (SYNTHETIC FIXTURE -- #19738 CP6, not a real bank feed)', 'fixture')
    returning id into v_biddeed_conn;

    insert into finance.bank_accounts (connection_id, plaid_account_id, name, mask, subtype, currency, ledger_account_id)
    values (v_biddeed_conn, 'fixture-acct-biddeed', 'Business Checking (FIXTURE)', '0000', 'checking', 'usd', v_biddeed_bank_account_id)
    returning id into v_biddeed_acct;

    -- one bank credit row per real Stripe payout (should match R1 exactly)
    for p in select payout_id, amount, arrival_date from finance.v_stripe_payouts loop
      insert into finance.bank_transactions (bank_account_id, plaid_transaction_id, amount_cents, posted_on, pending, name, merchant_name, raw)
      values (v_biddeed_acct, 'fixture-txn-' || p.payout_id, p.amount, p.arrival_date::date, false,
              'STRIPE TRANSFER', 'Stripe', jsonb_build_object('source', 'fixture', 'fixture_of', 'stripe_payout', 'payout_id', p.payout_id));
    end loop;

    -- one bank debit row matching the real ElevenLabs expense_ledger row (should match R2)
    insert into finance.bank_transactions (bank_account_id, plaid_transaction_id, amount_cents, posted_on, pending, name, merchant_name, raw)
    select v_biddeed_acct, 'fixture-txn-elevenlabs', -el.amount_cents, el.incurred_on, false, 'ELEVENLABS.IO', 'ElevenLabs',
      jsonb_build_object('source', 'fixture', 'fixture_of', 'expense_ledger', 'expense_id', el.id)
    from finance.expense_ledger el where el.entity_code = 'biddeed' and el.vendor = 'ElevenLabs';

    -- one deliberately unmatched bank debit row (no ledger/payout counterpart) -- exercises
    -- the unmatched_debit exception path (negative test: this row must NOT match any rule)
    insert into finance.bank_transactions (bank_account_id, plaid_transaction_id, amount_cents, posted_on, pending, name, merchant_name, raw)
    values (v_biddeed_acct, 'fixture-txn-unmatched', -4321, '2026-08-15', false, 'UNKNOWN VENDOR FIXTURE', 'Unknown',
            jsonb_build_object('source', 'fixture', 'fixture_of', 'none_intentional_unmatched'));
  end if;

  if exists (select 1 from finance.bank_connections where entity_code = 'everest_capital' and status = 'fixture') then
    raise notice 'everest_capital fixture connection already exists, skipping';
  else
    select id into v_everest_bank_account_id from finance.accounts where entity_code = 'everest_capital' and code = '1000';

    insert into finance.bank_connections (plaid_item_id, entity_code, institution_name, status)
    values ('fixture-item-everest', 'everest_capital', 'Wells Fargo (SYNTHETIC FIXTURE -- #19738 CP6, not a real bank feed)', 'fixture')
    returning id into v_everest_conn;

    insert into finance.bank_accounts (connection_id, plaid_account_id, name, mask, subtype, currency, ledger_account_id)
    values (v_everest_conn, 'fixture-acct-everest', 'Business Checking (FIXTURE)', '1111', 'checking', 'usd', v_everest_bank_account_id)
    returning id into v_everest_acct;

    -- matches the real GitHub expense_ledger row (litigation-gated entity -- exercises the
    -- draft-posting path if/when R3/R4 ever apply to this entity; R2 itself isn't gated)
    insert into finance.bank_transactions (bank_account_id, plaid_transaction_id, amount_cents, posted_on, pending, name, merchant_name, raw)
    select v_everest_acct, 'fixture-txn-github', -el.amount_cents, el.incurred_on, false, 'GITHUB.COM', 'GitHub',
      jsonb_build_object('source', 'fixture', 'fixture_of', 'expense_ledger', 'expense_id', el.id)
    from finance.expense_ledger el where el.entity_code = 'everest_capital' and el.vendor = 'GitHub';
  end if;
end $$;

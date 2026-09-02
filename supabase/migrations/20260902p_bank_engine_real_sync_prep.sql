-- Issue #19753: prep for the first real SimpleFIN sync.
--
-- 1. Chart of accounts seed for the two entities the real WF accounts map to
--    (everest_capital_brevard, ariel_personal) -- finance.accounts had zero rows for either.
-- 2. Bug fix: finance._litigation_gated() checked entity_code = 'everest_capital' but the
--    entity finance.entities itself documents as litigation-flagged is 'everest_capital_brevard'
--    ("Everest Capital of Brevard LLC (litigation-flagged: Abreu 05-2025-CA-014890 -- Tier 1
--    drafts only)"). 'everest_capital' ("Everest Capital USA / Development") carries no such
--    note. Fixing the check to the entity that's actually gated per its own row comment. Not
--    retroactively touching existing finance.journal_entries.posted_at rows this may have
--    affected -- flagged as a finding for Ariel, not silently backfilled.
-- 3. New R5 transfer-matching rule in finance.recon_run(): matches a debit bank_transaction to
--    a credit bank_transaction on a *different* bank_account (same or cross entity) so a card
--    payment (checking -> credit card) or an owner draw (business -> personal) records as
--    matched_type='transfer' instead of falling through to recon_exceptions or a coincidental
--    R2 expense match. Runs once per recon_run() call, before the per-entity loop, because
--    transfers are inherently cross-entity -- entity-scoping it inside the loop would break the
--    brevard-> personal owner-draw case. Match-only (writes finance.recon_matches), no journal
--    posting: issue #19753 asked to verify transfers "match as transfer" and gave
--    "count of transfer-type matches in finance.recon_matches" as the closing evidence, not a
--    new double-entry posting path against a litigation-flagged entity's books -- building that
--    unrequested was judged out of scope (K2/K3).

begin;

-- --------------------------------------------------------------------------------------------
-- 1. matched_type CHECK constraint: allow 'transfer'
-- --------------------------------------------------------------------------------------------
alter table finance.recon_matches drop constraint recon_matches_matched_type_check;
alter table finance.recon_matches add constraint recon_matches_matched_type_check
  check (matched_type = any (array['ledger_entry','stripe_payout','stripe_charge','expense','revenue','transfer']));

-- --------------------------------------------------------------------------------------------
-- 2. Chart of accounts seed
-- --------------------------------------------------------------------------------------------
insert into finance.accounts (entity_code, code, name, type, is_bank) values
  ('everest_capital_brevard', '1000', 'Bank – WF 3519', 'ASSET', true),
  ('everest_capital_brevard', '1001', 'Bank – WF 9264', 'ASSET', true),
  ('everest_capital_brevard', '1200', 'Accounts Receivable', 'ASSET', false),
  ('everest_capital_brevard', '2000', 'Accounts Payable', 'LIABILITY', false),
  ('everest_capital_brevard', '3000', 'Owner Equity', 'EQUITY', false),
  ('everest_capital_brevard', '4000', 'Revenue – Property/Investment', 'REVENUE', false),
  ('everest_capital_brevard', '5000', 'Operating Expenses', 'EXPENSE', false),
  ('everest_capital_brevard', '5900', 'Other Expense', 'EXPENSE', false),
  ('ariel_personal', '1000', 'Bank – WF Everyday 1130', 'ASSET', true),
  ('ariel_personal', '2100', 'Credit Card', 'LIABILITY', true),
  ('ariel_personal', '3000', 'Personal Equity', 'EQUITY', false),
  ('ariel_personal', '4000', 'Other Income', 'REVENUE', false),
  ('ariel_personal', '5900', 'Other Expense', 'EXPENSE', false)
on conflict (entity_code, code) do nothing;

-- --------------------------------------------------------------------------------------------
-- 3. Litigation-gate bug fix
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION finance._litigation_gated(p_entity_code text)
 RETURNS boolean
 LANGUAGE sql
 IMMUTABLE
AS $function$
  select p_entity_code = 'everest_capital_brevard';
$function$;

-- --------------------------------------------------------------------------------------------
-- 4. finance.recon_run(): add R5 transfer-matching ahead of the per-entity loop
-- --------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION finance.recon_run(p_entity_code text DEFAULT NULL::text, p_from date DEFAULT '2026-01-01'::date)
 RETURNS TABLE(entity_code text, bank_rows integer, matched integer, exceptions_opened integer)
 LANGUAGE plpgsql
AS $function$
declare
  v_entity text;
  v_bank_rows int;
begin
  -- R5: inter-account transfers (same or cross entity). Debit on one bank_account matched to a
  -- credit on a DIFFERENT bank_account, equal magnitude, posted within +-3d. Mutual-nearest-match
  -- guard, same shape as R1/R2. Two recon_matches rows per matched pair (one per leg) so both
  -- bank_transaction_ids are excluded from recon_exceptions and from R1-R3's own
  -- "not exists (select 1 from finance.recon_matches ...)" guards below.
  with candidates as (
    select
      d.id as debit_id, c.id as credit_id,
      row_number() over (partition by d.id order by abs(d.posted_on - c.posted_on)) as debit_rank,
      row_number() over (partition by c.id order by abs(d.posted_on - c.posted_on)) as credit_rank
    from finance.bank_transactions d
    join finance.bank_transactions c
      on c.amount_cents = -d.amount_cents
      and c.bank_account_id <> d.bank_account_id
      and c.posted_on between (d.posted_on - 3) and (d.posted_on + 3)
    where d.amount_cents < 0
      and d.posted_on >= p_from
      and c.posted_on >= p_from
      and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = d.id)
      and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = c.id)
  )
  insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
  select debit_id, 'transfer', credit_id::text, 'R5', 0.85 from candidates where debit_rank = 1 and credit_rank = 1
  union all
  select credit_id, 'transfer', debit_id::text, 'R5', 0.85 from candidates where debit_rank = 1 and credit_rank = 1;

  for v_entity in
    select code from finance.entities where (p_entity_code is null or code = p_entity_code) order by code
  loop
    -- R1: Stripe payout <-> bank credit (amount equal, posted within arrival_date +-3d,
    -- descriptor mentions stripe). confidence 0.95.
    -- Mutual-nearest-match: when the +-3d window lets one bank row qualify for more than
    -- one payout (e.g. two same-amount payouts a few days apart), only accept a pair where
    -- each side's #1 choice (smallest date distance) is the other -- prevents the same
    -- bank_transaction_id or payout_id being claimed twice.
    with candidates as (
      select
        bt.id as bt_id, p.payout_id,
        row_number() over (partition by bt.id order by abs(bt.posted_on - p.arrival_date::date)) as bt_rank,
        row_number() over (partition by p.payout_id order by abs(bt.posted_on - p.arrival_date::date)) as payout_rank
      from finance.bank_transactions bt
      join finance.bank_accounts ba on ba.id = bt.bank_account_id
      join finance.bank_connections bc on bc.id = ba.connection_id
      join finance.v_stripe_payouts p
        on p.amount = bt.amount_cents
        and bt.posted_on between (p.arrival_date::date - 3) and (p.arrival_date::date + 3)
      where bc.entity_code = v_entity
        and bt.amount_cents > 0
        and bt.posted_on >= p_from
        and (bt.name ilike '%stripe%' or bt.merchant_name ilike '%stripe%')
        and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt.id)
        and not exists (select 1 from finance.recon_matches m where m.matched_type = 'stripe_payout' and m.matched_id = p.payout_id)
    )
    insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
    select bt_id, 'stripe_payout', payout_id, 'R1', 0.95
    from candidates where bt_rank = 1 and payout_rank = 1;

    -- R2a: expense ledger <-> bank debit, amount+date+vendor token match. confidence 0.9.
    -- Same mutual-nearest-match guard as R1.
    with candidates as (
      select
        bt.id as bt_id, el.id as expense_id,
        row_number() over (partition by bt.id order by abs(bt.posted_on - el.incurred_on)) as bt_rank,
        row_number() over (partition by el.id order by abs(bt.posted_on - el.incurred_on)) as expense_rank
      from finance.bank_transactions bt
      join finance.bank_accounts ba on ba.id = bt.bank_account_id
      join finance.bank_connections bc on bc.id = ba.connection_id
      join finance.expense_ledger el
        on el.entity_code = v_entity
        and el.amount_cents = abs(bt.amount_cents)
        and bt.posted_on between (el.incurred_on - 3) and (el.incurred_on + 3)
        and (bt.merchant_name ilike '%' || el.vendor || '%' or bt.name ilike '%' || el.vendor || '%')
      where bc.entity_code = v_entity
        and bt.amount_cents < 0
        and bt.posted_on >= p_from
        and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt.id)
        and not exists (select 1 from finance.recon_matches m where m.matched_type = 'expense' and m.matched_id = el.id::text)
    )
    insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
    select bt_id, 'expense', expense_id::text, 'R2', 0.9
    from candidates where bt_rank = 1 and expense_rank = 1;

    -- R2b: amount-only fallback within +-3d, no vendor match -- lower confidence, flagged
    -- for review (0.6). Only fires for rows R2a didn't already claim. Same mutual-nearest
    -- guard.
    with candidates as (
      select
        bt.id as bt_id, el.id as expense_id,
        row_number() over (partition by bt.id order by abs(bt.posted_on - el.incurred_on)) as bt_rank,
        row_number() over (partition by el.id order by abs(bt.posted_on - el.incurred_on)) as expense_rank
      from finance.bank_transactions bt
      join finance.bank_accounts ba on ba.id = bt.bank_account_id
      join finance.bank_connections bc on bc.id = ba.connection_id
      join finance.expense_ledger el
        on el.entity_code = v_entity
        and el.amount_cents = abs(bt.amount_cents)
        and bt.posted_on between (el.incurred_on - 3) and (el.incurred_on + 3)
      where bc.entity_code = v_entity
        and bt.amount_cents < 0
        and bt.posted_on >= p_from
        and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt.id)
        and not exists (select 1 from finance.recon_matches m where m.matched_type = 'expense' and m.matched_id = el.id::text)
    )
    insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
    select bt_id, 'expense', expense_id::text, 'R2_amount_only', 0.6
    from candidates where bt_rank = 1 and expense_rank = 1;

    -- R3: Stripe processing fee per payout -> DR 5200 Stripe Fees / CR 1100 Stripe Clearing.
    -- Auto-posts (posted_at=now()) unless the entity is litigation-gated, in which case it
    -- posts as a draft (posted_at=null) and logs Tier-1 (propose-only) to finance_ops_log.
    -- Idempotent: unique index on journal_entries(ref_table, ref_id); ref_id is a
    -- deterministic uuid derived from the payout id (md5 output is 32 hex chars = valid
    -- uuid literal), since stripe payout ids are text, not native uuids.
    insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
    select
      v_entity, p.arrival_date::date,
      format('Stripe processing fee for payout %s', p.payout_id),
      'stripe_payout_fee', 'stripe.payouts.fee', md5(p.payout_id || ':fee')::uuid,
      case when finance._litigation_gated(v_entity) then null else now() end,
      'finance.recon_run'
    from finance.v_stripe_payouts p
    where p.total_fees_cents > 0
      and p.arrival_date::date >= p_from
      and not exists (
        select 1 from finance.journal_entries je
        where je.ref_table = 'stripe.payouts.fee' and je.ref_id = md5(p.payout_id || ':fee')::uuid
      )
    on conflict (ref_table, ref_id) where ref_table is not null and ref_id is not null do nothing;

    insert into finance.postings (entry_id, account_id, debit_cents, memo)
    select je.id, acc5200.id, p.total_fees_cents, 'Stripe fee'
    from finance.journal_entries je
    join finance.v_stripe_payouts p on md5(p.payout_id || ':fee')::uuid = je.ref_id and je.ref_table = 'stripe.payouts.fee'
    join finance.accounts acc5200 on acc5200.entity_code = v_entity and acc5200.code = '5200'
    where je.entity_code = v_entity
      and not exists (select 1 from finance.postings po where po.entry_id = je.id and po.debit_cents > 0);

    insert into finance.postings (entry_id, account_id, credit_cents, memo)
    select je.id, acc1100.id, p.total_fees_cents, 'Stripe fee'
    from finance.journal_entries je
    join finance.v_stripe_payouts p on md5(p.payout_id || ':fee')::uuid = je.ref_id and je.ref_table = 'stripe.payouts.fee'
    join finance.accounts acc1100 on acc1100.entity_code = v_entity and acc1100.code = '1100'
    where je.entity_code = v_entity
      and not exists (select 1 from finance.postings po where po.entry_id = je.id and po.credit_cents > 0);

    insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
    select '19738', v_entity, 'recon_run.R3_stripe_fee',
      case when finance._litigation_gated(v_entity) then 'PARTIAL' else 'VERIFIED' end,
      p.payout_id,
      jsonb_build_object('rule', 'R3', 'fee_cents', p.total_fees_cents, 'tier', case when finance._litigation_gated(v_entity) then '1_propose_only' else '2_autonomous' end),
      case when finance._litigation_gated(v_entity) then 'warn' else 'info' end
    from finance.v_stripe_payouts p
    join finance.journal_entries je on je.ref_table = 'stripe.payouts.fee' and je.ref_id = md5(p.payout_id || ':fee')::uuid
    where je.entity_code = v_entity and je.created_at >= now() - interval '5 seconds';

    -- R4: payout journal DR 1000 Bank / CR 1100 Stripe Clearing, per R1-matched payout.
    -- Same idempotency pattern as R3 (deterministic uuid ref_id, unique on ref_table/ref_id).
    insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
    select distinct
      v_entity, p.arrival_date::date,
      format('Stripe payout %s landed in bank', p.payout_id),
      'stripe_payout', 'stripe.payouts', md5(p.payout_id)::uuid,
      case when finance._litigation_gated(v_entity) then null else now() end,
      'finance.recon_run'
    from finance.recon_matches m
    join finance.v_stripe_payouts p on p.payout_id = m.matched_id and m.matched_type = 'stripe_payout'
    where m.rule = 'R1'
      and not exists (
        select 1 from finance.journal_entries je
        where je.ref_table = 'stripe.payouts' and je.ref_id = md5(p.payout_id)::uuid
      )
    on conflict (ref_table, ref_id) where ref_table is not null and ref_id is not null do nothing;

    insert into finance.postings (entry_id, account_id, debit_cents, memo)
    select je.id, acc1000.id, p.amount, 'Payout received'
    from finance.journal_entries je
    join finance.v_stripe_payouts p on md5(p.payout_id)::uuid = je.ref_id and je.ref_table = 'stripe.payouts'
    join finance.accounts acc1000 on acc1000.entity_code = v_entity and acc1000.code = '1000'
    where je.entity_code = v_entity
      and not exists (select 1 from finance.postings po where po.entry_id = je.id and po.debit_cents > 0);

    insert into finance.postings (entry_id, account_id, credit_cents, memo)
    select je.id, acc1100.id, p.amount, 'Payout clears Stripe holding'
    from finance.journal_entries je
    join finance.v_stripe_payouts p on md5(p.payout_id)::uuid = je.ref_id and je.ref_table = 'stripe.payouts'
    join finance.accounts acc1100 on acc1100.entity_code = v_entity and acc1100.code = '1100'
    where je.entity_code = v_entity
      and not exists (select 1 from finance.postings po where po.entry_id = je.id and po.credit_cents > 0);

    insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
    select '19738', v_entity, 'recon_run.R4_payout_journal',
      case when finance._litigation_gated(v_entity) then 'PARTIAL' else 'VERIFIED' end,
      p.payout_id,
      jsonb_build_object('rule', 'R4', 'amount_cents', p.amount, 'tier', case when finance._litigation_gated(v_entity) then '1_propose_only' else '2_autonomous' end),
      case when finance._litigation_gated(v_entity) then 'warn' else 'info' end
    from finance.v_stripe_payouts p
    join finance.journal_entries je on je.ref_table = 'stripe.payouts' and je.ref_id = md5(p.payout_id)::uuid
    where je.entity_code = v_entity and je.created_at >= now() - interval '5 seconds';

    -- Unmatched bank rows -> recon_exceptions
    insert into finance.recon_exceptions (bank_transaction_id, reason, status)
    select bt.id, case when bt.amount_cents > 0 then 'unmatched_credit' else 'unmatched_debit' end, 'open'
    from finance.bank_transactions bt
    join finance.bank_accounts ba on ba.id = bt.bank_account_id
    join finance.bank_connections bc on bc.id = ba.connection_id
    where bc.entity_code = v_entity
      and bt.posted_on >= p_from
      and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt.id)
      and not exists (select 1 from finance.recon_exceptions e where e.bank_transaction_id = bt.id);

    -- Unmatched ledger rows (posted expense journal entries with no bank-side match) ->
    -- no_bank_evidence
    insert into finance.recon_exceptions (bank_transaction_id, entry_id, reason, status)
    select null, je.id, 'no_bank_evidence', 'open'
    from finance.expense_ledger el
    join finance.journal_entries je on je.ref_table = 'finance.expense_ledger' and je.ref_id = el.id
    where el.entity_code = v_entity
      and el.incurred_on >= p_from
      and not exists (
        select 1 from finance.recon_matches m
        where m.matched_type = 'expense' and m.matched_id = el.id::text
      )
      and not exists (select 1 from finance.recon_exceptions e where e.entry_id = je.id);

    select count(*) into v_bank_rows
    from finance.bank_transactions bt
    join finance.bank_accounts ba on ba.id = bt.bank_account_id
    join finance.bank_connections bc on bc.id = ba.connection_id
    where bc.entity_code = v_entity and bt.posted_on >= p_from;

    entity_code := v_entity;
    bank_rows := v_bank_rows;
    select count(*) into matched from finance.recon_matches m2
      join finance.bank_transactions bt2 on bt2.id = m2.bank_transaction_id
      join finance.bank_accounts ba2 on ba2.id = bt2.bank_account_id
      join finance.bank_connections bc2 on bc2.id = ba2.connection_id
      where bc2.entity_code = v_entity and bt2.posted_on >= p_from;
    select count(*) into exceptions_opened
      from finance.recon_exceptions e
      left join finance.bank_transactions bt3 on bt3.id = e.bank_transaction_id
      left join finance.bank_accounts ba3 on ba3.id = bt3.bank_account_id
      left join finance.bank_connections bc3 on bc3.id = ba3.connection_id
      left join finance.journal_entries je3 on je3.id = e.entry_id
      where e.status = 'open'
        and coalesce(bc3.entity_code, je3.entity_code) = v_entity;
    return next;
  end loop;
end;
$function$;

commit;

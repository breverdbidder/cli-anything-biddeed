-- CFO v1 Issue H, issue #19762: categorization cleanup -- resolve 186 uncategorized
-- bank_transactions (long-tail merchants + WF PURCHASE/RECURRING wrappers), split business
-- vs personal, add finance.normalize_descriptor() for clean vendor display.
--
-- Pre-flight (live, 2026-09-02/03): 186 open finance.recon_exceptions with
-- reason='uncategorized'. merchant_name is NULL on all 186 (SimpleFIN never populated it) --
-- the merchant is embedded in bank_transactions.name (the raw WF descriptor). Confirmed the
-- issue's other cited number: finance.accounts 'everest_capital_brevard'/'1002' (WF Savings
-- 6160) already exists -- it was created in the prior 20260902q migration's chart-of-accounts
-- block, not actually missing live despite the issue title. No open recon_exceptions reference
-- 6160/OVERDRAFT PROTECTION either, confirmed both before and after this migration.
--
-- Design note: adding the ~55 new category_rules rows below resolves 184/186 purely via the
-- EXISTING raw-name ILIKE matching (WF's column padding doesn't break single-token substrings
-- like "PUBLIX" or "7-ELEVEN"). finance.normalize_descriptor() is still implemented and wired
-- into finance.categorize_bank_txn per the issue's explicit ask (used additively -- a rule
-- matches on raw OR normalized text, verified zero-diff against all 616 live transactions
-- before promotion) and is the real fix for finance.v_commingled_business_costs, whose
-- vendor_description column showed the raw "PURCHASE AUTHORIZED ON ..." wrapper instead of a
-- real vendor name (the issue's "$895.47/43 PURCHASE" / "$2,243.95/26 RECURRING PAYMENT"
-- figures, reproduced exactly live by grouping journal_entries.memo prefix within that view's
-- own filter -- confirmed these are display-layer labels, not literally unmatched rows).
--
-- Because post_bank_txn() is idempotent on (ref_table, ref_id), simply re-running
-- categorization does nothing for the 186 rows, which were already posted (to the 5900/4000
-- fallback account) by the original 20260902q backfill. finance.recategorize_bank_txn() below
-- corrects the EXISTING posting's account_id in place instead (debit/credit amounts untouched,
-- so the deferred balance trigger still holds) and resolves the matching recon_exception.
--
-- Result (live, re-verified before writing this file): 186 -> 2 open uncategorized, both
-- genuinely ambiguous single-occurrence charges ("SQ *FAST" $6.50, "THE LAW OFFICES OF" $75.00)
-- left uncategorized on purpose per the issue's own "small honest tail beats wrong categories"
-- instruction, rather than guessed. finance.assert_balanced() = 0 rows throughout.

begin;

-- ============================================================
-- 1. finance.normalize_descriptor -- strips the WF PURCHASE/RECURRING PAYMENT wrapper, the
--    date, trailing card/ref numbers, city/state, and common payment-processor prefixes.
-- ============================================================

create or replace function finance.normalize_descriptor(p_text text)
returns text
language plpgsql immutable as $$
declare
  v text;
begin
  v := coalesce(p_text, '');

  -- Strip the WF card-activity wrapper + date. Handles all 3 observed variants:
  -- "PURCHASE AUTHORIZED ON MM/DD ...", "RECURRING PAYMENT AUTHORIZED ON MM/DD ...",
  -- "RECURRING PAYMENT REVERSAL ON MM/DD ..." (no "AUTHORIZED").
  v := regexp_replace(
    v,
    '^\s*(PURCHASE|RECURRING PAYMENT REVERSAL|RECURRING PAYMENT)\s+(?:AUTHORIZED\s+)?ON\s+\d{2}/\d{2}\s*',
    '', 'i'
  );

  if v ~ '\s{2,}' then
    -- Fixed-width wrapper column padding survived: merchant is the first column, city/state/
    -- ref/card live in later columns and are dropped entirely.
    v := (regexp_split_to_array(v, '\s{2,}'))[1];
  else
    -- Unwrapped short form (e.g. "GOOGLE *Swimmetry 855-836-3987 CA"): strip a trailing
    -- 2-letter state code, then a trailing phone/reference digit run.
    v := regexp_replace(v, '\s+[A-Z]{2}\s*$', '');
    v := regexp_replace(v, '\s+[\d-]{7,}\s*$', '');
  end if;

  -- Best-effort: a single-space (not double-space) city/state gap can survive the column split
  -- above when a long merchant name ate the padding -- strip a trailing state code left from
  -- that case too.
  v := regexp_replace(v, '\s+[A-Z]{2}$', '', 'i');

  -- Strip trailing CARD #### / WF reference token if any survived.
  v := regexp_replace(v, '\s*CARD\s+\d{3,4}\s*$', '', 'i');
  v := regexp_replace(v, '\s+[A-Z]\d{12,18}\s*$', '', 'i');

  -- Strip common payment-processor / marketplace prefixes.
  v := regexp_replace(v, '^(SQ \*|IC\* |GOOGLE \*|TST\* |PY \*|SP |AMZN Mktp)', '', 'i');

  v := trim(regexp_replace(v, '\s+', ' ', 'g'));

  return nullif(v, '');
end;
$$;

grant execute on function finance.normalize_descriptor(text) to service_role, cfo_agent_ro;

-- ============================================================
-- 2. Wire normalize_descriptor into matching, additively: a rule now matches if its pattern is
--    found in EITHER the raw descriptor OR the normalized one. Strict superset of the old
--    raw-only matching (normalize_descriptor only ever REMOVES characters, never adds), so
--    nothing that matched before can stop matching. Verified empirically: zero-diff comparison
--    of old vs. new engine output across all 616 live simplefin bank_transactions before this
--    was promoted (via a temporary finance.categorize_bank_txn_test() staging function, not
--    persisted).
-- ============================================================

create or replace function finance.categorize_bank_txn(p_bank_transaction_id uuid)
returns table(
  account_code text, rule_id uuid, is_transfer boolean,
  likely_business_entity text, matched boolean, note text
)
language plpgsql stable as $$
declare
  v_bt finance.bank_transactions;
  v_entity text;
  v_rule finance.category_rules;
  v_dir text;
  v_norm_name text;
  v_norm_merchant text;
begin
  select bt.* into v_bt from finance.bank_transactions bt where bt.id = p_bank_transaction_id;

  select bc.entity_code into v_entity
  from finance.bank_accounts ba join finance.bank_connections bc on bc.id = ba.connection_id
  where ba.id = v_bt.bank_account_id;

  v_dir := case when v_bt.amount_cents > 0 then 'out' else 'in' end;
  v_norm_name := finance.normalize_descriptor(v_bt.name);
  v_norm_merchant := finance.normalize_descriptor(v_bt.merchant_name);

  select r.* into v_rule
  from finance.category_rules r
  where (r.entity_scope is null or r.entity_scope = v_entity)
    and (r.direction = 'any' or r.direction = v_dir)
    and (
      (r.match_field = 'name' and (v_bt.name ilike '%' || r.pattern || '%' or coalesce(v_norm_name,'') ilike '%' || r.pattern || '%'))
      or (r.match_field = 'merchant_name' and v_bt.merchant_name is not null and (v_bt.merchant_name ilike '%' || r.pattern || '%' or coalesce(v_norm_merchant,'') ilike '%' || r.pattern || '%'))
    )
  order by r.priority asc, r.id asc
  limit 1;

  if found then
    account_code := v_rule.account_code;
    rule_id := v_rule.id;
    is_transfer := v_rule.is_transfer;
    likely_business_entity := v_rule.likely_business_entity;
    matched := true;
    note := v_rule.note;
  else
    account_code := case when v_dir = 'out' then '5900' else '4000' end;
    rule_id := null;
    is_transfer := false;
    likely_business_entity := null;
    matched := false;
    note := null;
  end if;
  return next;
end;
$$;

grant execute on function finance.categorize_bank_txn(uuid) to service_role, cfo_agent_ro;

-- ============================================================
-- 3. Chart-of-accounts + rules-table idempotency guard
-- ============================================================

-- ariel_personal had no Family & Kids bucket. Issue #19762 explicitly calls out Swimmetry /
-- XV XIII PERFORMANCE / SwimOutlet / SwimCloud as likely Michael's swim training.
insert into finance.accounts (entity_code, code, name, type, is_bank) values
  ('ariel_personal', '5400', 'Family & Kids', 'EXPENSE', false)
on conflict (entity_code, code) do nothing;

create unique index if not exists category_rules_pattern_scope_dir_uniq
  on finance.category_rules (pattern, coalesce(entity_scope, ''), direction, match_field);

-- Bugfix: this pattern never matched anything live -- the real WF descriptor truncates to
-- "Workspace_zone" (no "wise" suffix), verified against the live uncategorized dump.
-- Narrowing text this way only ever ADDS matches (any raw name containing the old longer
-- string still contains this shorter one) -- confirmed zero regression against the 2
-- previously-matched rows for this pattern.
update finance.category_rules
set pattern = 'Workspace_zone'
where pattern = 'Google Workspace_zonewise';

-- Reverse-commingling / wrong-entity-scope fixes: pattern already exists for the OTHER entity.
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('ACH Claim#', 'everest_capital_brevard', 'in', '4000', 20, 'Bank dispute claim credit (brevard account) -- same pattern already exists for ariel_personal'),
  ('T-MOBILE', 'everest_capital_brevard', 'out', '5900', 20, 'Personal cell phone (Ariel Shapira) paid from BUSINESS checking -- reverse-commingling, same shape as the existing ROCKET MONEY finding')
on conflict (pattern, coalesce(entity_scope, ''), direction, match_field) do nothing;

-- Business infra / SaaS paid personally, entity unclear (mirrors the existing
-- ANTHROPIC/SUPABASE/CLOUDFLARE/etc. block).
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, likely_business_entity, note) values
  ('GITHUB', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- source-code hosting, entity unclear'),
  ('Transcribe', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- Google AI transcription tooling (matches Transcribe/Transcriber variants), entity unclear'),
  ('GOOGLE *CLOUD', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- Google Cloud Platform usage, entity unclear'),
  ('Google CLOUD', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- Google Cloud Platform usage (no-asterisk descriptor variant), entity unclear'),
  ('GOOGLE *WORKSPACE', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- generic Google Workspace billing (no _zone suffix distinguishing which workspace), entity unclear'),
  ('NAME-CHEAP.COM', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- domain registration, entity unclear')
on conflict (pattern, coalesce(entity_scope, ''), direction, match_field) do nothing;

-- Contra-expense: refund/reversal of a business-infra charge already categorized 5100
-- (existing VERCEL rule only covers direction=out; this is the inflow/refund leg).
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('VERCEL', 'ariel_personal', 'in', '5100', 20, 'Refund/reversal of a Vercel charge (contra-expense) -- companion to the existing out-direction VERCEL rule')
on conflict (pattern, coalesce(entity_scope, ''), direction, match_field) do nothing;

-- Business-compliance vendor paid personally (mirrors the existing NIC*-FL SUNBIZ.ORG rule).
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, likely_business_entity, note) values
  ('TAX1099.COM', 'ariel_personal', 'out', '5900', 20, null, 'Business 1099 tax-filing compliance cost paid personally -- entity unclear (mirrors NIC*-FL SUNBIZ.ORG precedent)')
on conflict (pattern, coalesce(entity_scope, ''), direction, match_field) do nothing;

-- Judgment call per issue #19762 scope #2: recurs monthly, Israel-facing descriptor -- flagged
-- as *possible* business rather than auto-assigned to a specific entity (likely_business_entity
-- = null routes it into v_commingled_business_costs for Ariel's review, same mechanism already
-- used by the ANTHROPIC/SUPABASE/etc. ariel_personal rows).
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, likely_business_entity, note) values
  ('GOOGLE *Screen', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED possible business (Israel-facing service, recurs monthly) -- NOT auto-assigned to an entity, flagged for Ariel to confirm per issue #19762 scope #2')
on conflict (pattern, coalesce(entity_scope, ''), direction, match_field) do nothing;

-- Family & Kids (5400) -- issue #19762 explicitly flags these as likely Michael's swim training.
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('Swimmetry', 'ariel_personal', 'out', '5400', 20, 'Swim-team subscription app -- likely Michael''s training per issue #19762'),
  ('XV XIII PERF', 'ariel_personal', 'out', '5400', 20, 'Square-processed swim/performance training vendor (matches truncated "XV XIII PERFOR" too) -- likely Michael''s training per issue #19762'),
  ('SWIMOUTLET', 'ariel_personal', 'out', '5400', 20, 'Swim gear retailer'),
  ('SWIMCLOUD', 'ariel_personal', 'out', '5400', 20, 'Swim-meet results tracking service')
on conflict (pattern, coalesce(entity_scope, ''), direction, match_field) do nothing;

-- Personal living-expense tier (groceries/fuel/dining/subscriptions/travel/health/misc),
-- mirrors the existing INSTACART/AMAZON/UBER/SUNOCO/TURO/PRICELN priority-30 block. Every
-- pattern below was taken from the live uncategorized descriptor dump, not invented.
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('PUBLIX', 'ariel_personal', 'any', '5900', 30, 'Personal groceries (any direction -- observed live refund/return inflow, issue #19762)'),
  ('WM SUPERCENTER', 'ariel_personal', 'out', '5900', 30, 'Personal groceries (Walmart Supercenter)'),
  ('WAL-MART', 'ariel_personal', 'out', '5900', 30, 'Personal groceries/retail (Walmart, hyphenated descriptor variant)'),
  ('WALMART', 'ariel_personal', 'out', '5900', 30, 'Personal groceries/retail (Walmart, no-hyphen descriptor variant)'),
  ('WINN-DIXIE', 'ariel_personal', 'out', '5900', 30, 'Personal groceries'),
  ('GIANT ', 'ariel_personal', 'out', '5900', 30, 'Personal groceries (Giant Food Store)'),
  ('METRO FOOD MART', 'ariel_personal', 'out', '5900', 30, 'Personal groceries/convenience'),
  ('THE PRODUCE PLACE', 'ariel_personal', 'out', '5900', 30, 'Personal groceries (produce market)'),
  ('7-ELEVEN', 'ariel_personal', 'out', '5900', 30, 'Personal fuel/convenience'),
  ('WAWA', 'ariel_personal', 'out', '5900', 30, 'Personal fuel/convenience'),
  ('SHELL', 'ariel_personal', 'out', '5900', 30, 'Personal fuel'),
  ('EXXON', 'ariel_personal', 'out', '5900', 30, 'Personal fuel'),
  ('CHEVRON', 'ariel_personal', 'out', '5900', 30, 'Personal fuel'),
  ('BP#', 'ariel_personal', 'out', '5900', 30, 'Personal fuel (BP-branded station)'),
  ('CIRCLE K', 'ariel_personal', 'out', '5900', 30, 'Personal fuel/convenience'),
  ('Circlek', 'ariel_personal', 'out', '5900', 30, 'Personal fuel/convenience (no-space descriptor variant)'),
  ('RACETRAC', 'ariel_personal', 'out', '5900', 30, 'Personal fuel'),
  ('MARATHON', 'ariel_personal', 'out', '5900', 30, 'Personal fuel'),
  ('CUMBERLAND FARMS', 'ariel_personal', 'out', '5900', 30, 'Personal fuel/convenience'),
  ('FLORIDAFAST.COM', 'ariel_personal', 'out', '5900', 30, 'Personal fuel/convenience'),
  ('SEBASTIAN MART', 'ariel_personal', 'out', '5900', 30, 'Personal fuel/convenience'),
  ('KREMBO CAFE', 'ariel_personal', 'out', '5900', 30, 'Personal dining'),
  ('DABUSH', 'ariel_personal', 'out', '5900', 30, 'Personal dining'),
  ('CURIOSITY STREAM', 'ariel_personal', 'out', '5900', 30, 'Personal media subscription'),
  ('USATODAY', 'ariel_personal', 'out', '5900', 30, 'Personal media subscription'),
  ('USAT MEDIA', 'ariel_personal', 'out', '5900', 30, 'Personal media subscription (USA Today, alt descriptor)'),
  ('SMARTYPLUS', 'ariel_personal', 'out', '5900', 30, 'Personal subscription (matches FINDSMARTYPLUS.COM and SMARTYPLUS.NET variants)'),
  ('GOOGLE *Google One', 'ariel_personal', 'out', '5900', 30, 'Personal cloud storage subscription'),
  ('GOOGLE *Medium', 'ariel_personal', 'out', '5900', 30, 'Personal reading subscription'),
  ('BOOKSY', 'ariel_personal', 'out', '5900', 30, 'Personal grooming/salon booking subscription'),
  ('AIRBNB', 'ariel_personal', 'out', '5900', 30, 'Personal Airbnb stay (guest) -- distinct from the existing brevard host-income AIRBNB rule (different entity_scope+direction)'),
  ('STAYBRIDGE SUITES', 'ariel_personal', 'out', '5900', 30, 'Personal hotel stay'),
  ('METROPOLIS PARKING', 'ariel_personal', 'out', '5900', 30, 'Personal parking (Metropolis app)'),
  ('VERRAMOBILITY', 'ariel_personal', 'out', '5900', 30, 'Personal toll/violation processing fee (Verra Mobility)'),
  ('MISTER CAR WASH', 'ariel_personal', 'out', '5900', 30, 'Personal auto'),
  ('CLEARME.COM', 'ariel_personal', 'out', '5900', 30, 'Personal travel/security expedite (CLEAR)'),
  ('LA Fitness', 'ariel_personal', 'out', '5900', 30, 'Personal gym membership'),
  ('BEST BUY', 'ariel_personal', 'out', '5900', 30, 'Personal retail'),
  ('EVERGREEN CLEANERS', 'ariel_personal', 'out', '5900', 30, 'Personal dry cleaning'),
  ('CTLP*DBS VENDING', 'ariel_personal', 'out', '5900', 30, 'Personal vending machine purchase (travel)'),
  ('ATM WITHDRAWAL', 'ariel_personal', 'out', '5900', 30, 'Personal cash withdrawal'),
  ('OMNITELECOM', 'ariel_personal', 'out', '5900', 30, 'Personal Israel telecom/mobile service'),
  ('IFIXANDREPAIR', 'ariel_personal', 'out', '5900', 30, 'Personal device repair')
on conflict (pattern, coalesce(entity_scope, ''), direction, match_field) do nothing;

-- COSTCO: priority 40 (below the existing INSTACART rule's 30) so the ~44 already-correctly-
-- matched "IC* COSTCO BY INST...INSTACART.COM..." rows keep matching INSTACART unchanged (same
-- account 5900 either way -- this only avoids an unnecessary rule_id/note flip on rows that
-- already worked; verified live via a collision check before this migration). This rule exists
-- only to catch the 2 truncated variants that do NOT contain "INSTACART" ("IC* COSTCO BY IN
-- CAR", "IC* COSTCO BY INSTACAR" -- missing the final "T") and so never match INSTACART.
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('COSTCO', 'ariel_personal', 'out', '5900', 40, 'Personal groceries (Costco) -- fallback for truncated descriptor variants that do not contain "INSTACART"; the INSTACART rule (priority 30) wins for rows that do')
on conflict (pattern, coalesce(entity_scope, ''), direction, match_field) do nothing;

-- ============================================================
-- 4. finance.recategorize_bank_txn -- post_bank_txn() is idempotent on ref_table/ref_id, so
--    re-running categorization does nothing for a bank_transaction that already has a
--    journal_entry. This corrects the EXISTING posting's account in place instead. Debit/
--    credit amounts are untouched (only account_id changes), so the deferred
--    trg_postings_balance trigger still passes. Skips transfer-shaped entries -- out of scope
--    for this categorization-only pass.
-- ============================================================

create or replace function finance.recategorize_bank_txn(p_bank_transaction_id uuid)
returns table(entry_id uuid, old_account_code text, new_account_code text, changed boolean, newly_matched boolean)
language plpgsql as $$
declare
  v_bt finance.bank_transactions;
  v_entity text;
  v_bank_ledger_account uuid;
  v_cat record;
  v_entry finance.journal_entries;
  v_old_posting finance.postings;
  v_new_account uuid;
  v_old_account_code text;
begin
  select bt.* into v_bt from finance.bank_transactions bt where bt.id = p_bank_transaction_id;

  select je.* into v_entry from finance.journal_entries je
  where je.ref_table = 'finance.bank_transactions' and je.ref_id = p_bank_transaction_id;
  if not found then
    return;
  end if;

  select bc.entity_code, ba.ledger_account_id into v_entity, v_bank_ledger_account
  from finance.bank_accounts ba join finance.bank_connections bc on bc.id = ba.connection_id
  where ba.id = v_bt.bank_account_id;

  select p.* into v_old_posting
  from finance.postings p
  where p.entry_id = v_entry.id and p.account_id <> v_bank_ledger_account
  limit 1;
  if not found then
    return;
  end if;

  select a.code into v_old_account_code from finance.accounts a where a.id = v_old_posting.account_id;

  select * into v_cat from finance.categorize_bank_txn(p_bank_transaction_id);

  if v_cat.is_transfer then
    return;
  end if;

  select id into v_new_account from finance.accounts where entity_code = v_entity and code = v_cat.account_code;

  entry_id := v_entry.id;
  old_account_code := v_old_account_code;
  new_account_code := v_cat.account_code;
  changed := (v_old_account_code is distinct from v_cat.account_code);
  newly_matched := v_cat.matched;

  if changed then
    update finance.postings
    set account_id = v_new_account, memo = coalesce(v_cat.note, memo)
    where id = v_old_posting.id;
  end if;

  if v_cat.matched then
    update finance.recon_exceptions
    set status = 'resolved', resolved_at = now(),
        resolution = format('recategorized via finance.normalize_descriptor + expanded category_rules pass (issue #19762) -- matched rule_id %s (%s)', v_cat.rule_id, coalesce(v_cat.note,''))
    where bank_transaction_id = p_bank_transaction_id and reason = 'uncategorized' and status = 'open';
  end if;

  insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
  values (
    '19762', v_entity, 'recategorize_bank_txn',
    case when changed then 'VERIFIED' else 'SKIPPED' end,
    p_bank_transaction_id::text,
    jsonb_build_object('entry_id', v_entry.id, 'old_account_code', v_old_account_code, 'new_account_code', v_cat.account_code, 'changed', changed, 'newly_matched', v_cat.matched),
    'info'
  );

  return next;
end;
$$;

grant execute on function finance.recategorize_bank_txn(uuid) to service_role;

create or replace function finance.recategorize_open_exceptions()
returns table(processed int, changed int, resolved int)
language plpgsql as $$
declare
  r record;
  v_result record;
  v_processed int := 0;
  v_changed int := 0;
  v_resolved int := 0;
begin
  for r in
    select distinct bank_transaction_id
    from finance.recon_exceptions
    where reason = 'uncategorized' and status = 'open'
  loop
    select * into v_result from finance.recategorize_bank_txn(r.bank_transaction_id);
    if v_result.entry_id is not null then
      v_processed := v_processed + 1;
      if v_result.changed then v_changed := v_changed + 1; end if;
      if v_result.newly_matched then v_resolved := v_resolved + 1; end if;
    end if;
  end loop;
  processed := v_processed;
  changed := v_changed;
  resolved := v_resolved;
  return next;
end;
$$;

grant execute on function finance.recategorize_open_exceptions() to service_role;

-- ============================================================
-- 5. Run the correction batch.
-- ============================================================

select * from finance.recategorize_open_exceptions();

-- ============================================================
-- 6. finance.v_commingled_business_costs -- vendor_description now shows the cleaned merchant
--    name via finance.normalize_descriptor() instead of the raw WF wrapper text.
-- ============================================================

create or replace view finance.v_commingled_business_costs
with (security_invoker = true) as
select
  bt.posted_on as txn_date,
  coalesce(finance.normalize_descriptor(bt.name), bt.name) as vendor_description,
  round(p.debit_cents / 100.0, 2) as amount_dollars,
  cr.likely_business_entity,
  coalesce(cr.note, 'business infra/SaaS paid from ariel_personal') as note,
  format(
    'Suggested reclass: owner contribution of $%s to %s (DR %s 3000 Owner/Personal Equity, CR ariel_personal 3000 Personal Equity) -- Tier 1 propose-only, Ariel to confirm entity + approve',
    to_char(p.debit_cents / 100.0, 'FM999999990.00'),
    coalesce(cr.likely_business_entity, '<entity unclear -- Ariel to assign>'),
    coalesce(cr.likely_business_entity, '<entity>')
  ) as suggested_reclass,
  bt.id as bank_transaction_id,
  je.id as journal_entry_id
from finance.bank_transactions bt
join finance.bank_accounts ba on ba.id = bt.bank_account_id
join finance.bank_connections bc on bc.id = ba.connection_id
join finance.journal_entries je on je.ref_table = 'finance.bank_transactions' and je.ref_id = bt.id
join finance.postings p on p.entry_id = je.id and p.debit_cents > 0
join finance.accounts a on a.id = p.account_id and a.code = '5100' and a.entity_code = 'ariel_personal'
left join finance.category_rules cr on cr.id = (
  select r.id from finance.category_rules r
  where r.account_code = '5100' and r.entity_scope = 'ariel_personal' and r.direction in ('out', 'any')
    and r.match_field = 'name' and (bt.name ilike '%' || r.pattern || '%' or coalesce(finance.normalize_descriptor(bt.name),'') ilike '%' || r.pattern || '%')
  order by r.priority asc, r.id asc limit 1
)
where bc.status = 'simplefin' and bc.entity_code = 'ariel_personal'
order by bt.posted_on;

grant select on finance.v_commingled_business_costs to cfo_agent_ro;

-- finance.v_recurring_costs: no logic change needed (vendor already = cr.pattern), but
-- re-issued so it's provably current against the now-expanded category_rules set -- more
-- matched EXPENSE rows means more/different vendors surface here automatically.
create or replace view finance.v_recurring_costs
with (security_invoker = true) as
with matched_expenses as (
  select
    bc.entity_code,
    cr.pattern as vendor,
    a.code as account_code,
    a.name as account_name,
    bt.posted_on,
    p.debit_cents as amount_cents
  from finance.bank_transactions bt
  join finance.bank_accounts ba on ba.id = bt.bank_account_id
  join finance.bank_connections bc on bc.id = ba.connection_id
  join finance.journal_entries je on je.ref_table = 'finance.bank_transactions' and je.ref_id = bt.id
  join finance.postings p on p.entry_id = je.id and p.debit_cents > 0
  join finance.accounts a on a.id = p.account_id and a.type = 'EXPENSE' and a.entity_code = bc.entity_code
  join finance.category_rules cr on cr.id = (
    select r.id from finance.category_rules r
    where (r.entity_scope is null or r.entity_scope = bc.entity_code)
      and r.is_transfer = false
      and r.is_recurring_eligible = true
      and (r.direction = 'any' or r.direction = 'out')
      and r.match_field = 'name' and (bt.name ilike '%' || r.pattern || '%' or coalesce(finance.normalize_descriptor(bt.name),'') ilike '%' || r.pattern || '%')
    order by r.priority asc, r.id asc limit 1
  )
  where bc.status = 'simplefin'
),
agg as (
  select
    entity_code, vendor, account_code, account_name,
    count(*) as occurrences,
    min(posted_on) as first_seen,
    max(posted_on) as last_seen,
    (max(posted_on) - min(posted_on))::numeric / nullif(count(*) - 1, 0) as avg_gap_days,
    (array_agg(amount_cents order by posted_on desc))[1] as last_amount_cents,
    avg(amount_cents) as avg_amount_cents
  from matched_expenses
  group by entity_code, vendor, account_code, account_name
)
select
  entity_code, vendor, account_code, account_name,
  occurrences, first_seen, last_seen,
  case
    when occurrences < 2 then 'single_occurrence'
    when avg_gap_days between 25 and 35 then 'monthly'
    when avg_gap_days between 5 and 9 then 'weekly'
    when avg_gap_days between 85 and 95 then 'quarterly'
    else 'irregular'
  end as cadence,
  round(last_amount_cents / 100.0, 2) as last_amount_dollars,
  round(
    (case
      when avg_gap_days between 25 and 35 then avg_amount_cents
      when avg_gap_days between 5 and 9 then avg_amount_cents * 4.33
      when avg_gap_days between 85 and 95 then avg_amount_cents / 3.0
      when occurrences >= 2 and avg_gap_days > 0 then avg_amount_cents * 30.0 / avg_gap_days
      else null
    end) / 100.0, 2
  ) as monthly_runrate_dollars
from agg
order by entity_code, monthly_runrate_dollars desc nulls last;

grant select on finance.v_recurring_costs to cfo_agent_ro;

-- ============================================================
-- 7. Re-run the standard categorize -> post -> recon pipeline (idempotent; catches any
--    not-yet-posted rows) and assert the ledger is still balanced.
-- ============================================================

select * from finance.process_bank_transactions();
select * from finance.recon_run(null, '2026-01-01');
select * from finance.assert_balanced();

commit;

-- CFO v1 Issue G (CP6b), issue #19755: categorize + post all real WF bank transactions,
-- transfer/commingling rules, recurring-cost register.
--
-- Pre-flight finding (see docs/spec/19755.md): live finance.bank_transactions for the 4
-- SimpleFIN-linked accounts held 954 rows, not the 338 the issue cites. Root cause: an
-- earlier sync wrote 338 rows with plaid_transaction_id NOT prefixed 'simplefin:', a stub
-- raw={"src":"simplefin"}, and the OPPOSITE sign convention (raw amount not negated) from a
-- later, complete sync that wrote 616 rows (prefixed 'simplefin:', full raw payload, correct
-- sign per the table's documented convention: amount_cents>0=outflow, <0=inflow). All 338
-- stub rows exact-matched a row in the 616 by (name, posted_on, abs(amount)) -- confirmed via
-- a 1:1 join with no fan-out. Deleted the 338 duplicate/wrong-sign rows (and their 338
-- recon_exceptions children) in 20260902p_cfo_bank_dedup_simplefin_stub_rows.sql, which MUST
-- run before this migration.
-- True population processed by this migration: 616 real WF transactions (421 ariel_personal,
-- 195 everest_capital_brevard).

begin;

-- ============================================================
-- 1. Chart-of-accounts additions (additive only, per K3/3.4)
-- ============================================================

insert into finance.accounts (entity_code, code, name, type, is_bank) values
  ('everest_capital_brevard', '1002', 'Bank – WF Savings 6160 (unlinked; also used for WF Overdraft Protection sweep, INFERRED)', 'ASSET', true),
  ('everest_capital_brevard', '5100', 'Data Vendors / SaaS & PropTech', 'EXPENSE', false),
  ('everest_capital_brevard', '5300', 'Bank & Wire Fees', 'EXPENSE', false),
  ('everest_capital_brevard', '5400', 'Debt Service (mortgage / SBA EIDL)', 'EXPENSE', false),
  ('ariel_personal', '5100', 'Data Vendors / SaaS (business infra paid personally)', 'EXPENSE', false),
  ('ariel_personal', '5300', 'Bank Fees & Interest Charges', 'EXPENSE', false)
on conflict (entity_code, code) do nothing;

-- ============================================================
-- 2. Wire up bank_accounts.ledger_account_id -- the issue states this mapping was "done by
--    chat" but it was never actually persisted (verified live: all 4 null pre-migration).
-- ============================================================

update finance.bank_accounts ba set ledger_account_id = a.id
from finance.accounts a
where ba.name = 'BUSINESS CHECKING ...3519 (3519)' and a.entity_code = 'everest_capital_brevard' and a.code = '1000';

update finance.bank_accounts ba set ledger_account_id = a.id
from finance.accounts a
where ba.name = 'BUSINESS CHECKING ...9264 (9264)' and a.entity_code = 'everest_capital_brevard' and a.code = '1001';

update finance.bank_accounts ba set ledger_account_id = a.id
from finance.accounts a
where ba.name = 'EVERYDAY CHECKING ...1130 (1130)' and a.entity_code = 'ariel_personal' and a.code = '1000';

update finance.bank_accounts ba set ledger_account_id = a.id
from finance.accounts a
where ba.name ilike 'WELLS FARGO AUTOGRAPH VISA%CARD ...2308 (2308)' and a.entity_code = 'ariel_personal' and a.code = '2100';

-- ============================================================
-- 3. finance.category_rules
-- ============================================================

create table finance.category_rules (
  id uuid primary key default gen_random_uuid(),
  pattern text not null,
  match_field text not null default 'name' check (match_field in ('name', 'merchant_name')),
  entity_scope text references finance.entities(code),
  direction text not null default 'any' check (direction in ('in', 'out', 'any')),
  account_code text not null,
  priority int not null default 100,
  note text,
  is_transfer boolean not null default false,
  likely_business_entity text references finance.entities(code),
  created_at timestamptz not null default now()
);

comment on table finance.category_rules is
  'direction: in = inflow (amount_cents<0, money entering the account), out = outflow (amount_cents>0). '
  'account_code=''TRANSFER'' is a sentinel: post_bank_transactions() routes is_transfer rows to '
  'finance.post_bank_transfer() instead of posting account_code as a real ledger account. '
  'likely_business_entity is set only on ariel_personal-scoped SaaS/infra rules where the vendor '
  'clearly services one entity; NULL means genuinely shared/ambiguous (Ariel to assign) -- see '
  'finance.v_commingled_business_costs.';

alter table finance.category_rules enable row level security;
create policy cfo_agent_ro_select on finance.category_rules for select to cfo_agent_ro using (true);
grant select on finance.category_rules to cfo_agent_ro;

-- --- Transfers (priority 10, checked first) ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, is_transfer, note) values
  ('ONLINE TRANSFER', null, 'any', 'TRANSFER', 10, true, 'WF online transfer between linked accounts -- paired via mask+amount+/-3d'),
  ('ONLINE PAYMENT THANK YOU', 'ariel_personal', 'in', 'TRANSFER', 10, true, 'Visa 2308 payment received -- counterpart is the ONLINE TRANSFER...TO WELLS FARGO...2308 leg'),
  ('RECURRING TRANSFER TO EVEREST CAPITAL OF BREVARD LLC BUSINESS MARKET RATE SAVINGS', 'everest_capital_brevard', 'out', 'TRANSFER', 10, true, 'Sweep to unlinked WF Savings 6160'),
  ('OVERDRAFT PROTECTION XFER', 'everest_capital_brevard', 'in', 'TRANSFER', 10, true, 'WF overdraft protection sweep -- routed through unlinked 1002 (INFERRED companion account, DEP ACT not separately synced)');

-- --- Debt service (brevard) ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('WF Direct Pay', 'everest_capital_brevard', 'out', '5400', 20, 'WF Direct Pay mortgage (~$3,221.51/mo) -- matches both the "mortgage" and bare "Tran ID" description variants'),
  ('SBA EIDL LOAN', 'everest_capital_brevard', 'out', '5400', 20, 'SBA EIDL loan payment'),
  ('DIRECT PAY MONTHLY BASE', 'everest_capital_brevard', 'out', '5400', 20, 'WF Direct Pay monthly base fee (loan servicing)'),
  ('NONWF BUS PYMT', 'everest_capital_brevard', 'out', '5400', 20, 'WF Direct Pay non-WF business payment transaction fee');

-- --- Utilities (brevard property) ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('SPECTRUM', 'everest_capital_brevard', 'out', '5000', 20, 'Internet/cable utility for the Brevard property'),
  ('FPL DIRECT DEBIT', 'everest_capital_brevard', 'out', '5000', 20, 'Electric utility for the Brevard property'),
  ('PALM BAY', 'everest_capital_brevard', 'out', '5000', 20, 'Water utility for the Brevard property (City of Palm Bay -- covers both "CITY OF PALM BAY UTILITY" and "PALM BAY FL UTILITY" descriptor variants)');

-- --- Bank/wire fees (both entities where applicable) ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('MONTHLY SERVICE FEE', 'everest_capital_brevard', 'out', '5300', 20, 'WF monthly account service fee'),
  ('MONTHLY SERVICE FEE', 'ariel_personal', 'out', '5300', 20, 'WF monthly account service fee'),
  ('Monthly Service Fee for', 'ariel_personal', 'out', '5300', 20, 'WF monthly account service fee (dated descriptor variant)'),
  ('OVERDRAFT FEE', 'everest_capital_brevard', 'out', '5300', 20, 'WF overdraft fee'),
  ('WIRE TRANS SVC CHARGE', 'everest_capital_brevard', 'out', '5300', 20, 'WF wire transfer service charge'),
  ('INTEREST CHARGE ON PURCHASES', 'ariel_personal', 'out', '5300', 20, 'Wells Fargo Visa credit card interest charge');

-- --- Interest earned (tiny, both entities use code 4000 for generic revenue) ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('INTEREST PAYMENT', null, 'in', '4000', 20, 'Bank-paid interest earned (inflow)');

-- --- Personal cell / utility on personal account ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('T-MOBILE', 'ariel_personal', 'out', '5900', 20, 'Personal cell phone');

-- --- SaaS/infra vendors correctly already in a business entity''s own books (not commingled) ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('ANTHROPIC', 'everest_capital_brevard', 'out', '5100', 20, 'AI/dev tooling (Claude Code) charged directly to brevard -- see findings: brevard checking is funding shared BidDeed.AI-stack infra, not just property costs'),
  ('BIDDEED.AI', 'everest_capital_brevard', 'out', '5100', 20, 'BUSINESS TO BUSINESS ACH to biddeed.ai -- cross-entity/self-dealing flag, see findings'),
  ('ELEVENLABS', 'everest_capital_brevard', 'out', '5100', 20, 'AI voice/content tooling charged directly to brevard'),
  ('TRACERFY', 'everest_capital_brevard', 'out', '5100', 20, 'BidDeed.AI skip-trace vendor charged directly to brevard -- cross-entity flag'),
  ('Link.com', 'everest_capital_brevard', 'out', '5100', 20, 'Skip-trace vendor (Tracerfy/Link.com) charged directly to brevard'),
  ('ROCKET MONEY', 'everest_capital_brevard', 'out', '5900', 20, 'Personal-finance subscription app charged to BUSINESS checking -- possible reverse-commingling flag, see findings'),
  ('MRI SOFTWARE', 'everest_capital_brevard', 'out', '5100', 20, 'Property-management PropTech software for the Brevard rental property');

-- --- SaaS/infra vendors paid from ariel_personal -- THE commingling set (issue scope #4) ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, likely_business_entity, note) values
  ('ANTHROPIC', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- Claude Code usage spans biddeed/zonewise/winnerdata, entity unclear'),
  ('SUPABASE', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- shared DB platform, entity unclear'),
  ('CLOUDFLARE', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- shared hosting/CDN, entity unclear'),
  ('MINDSTUDIO', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- AI agent tooling, entity unclear'),
  ('RAILWAY', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- app hosting, entity unclear'),
  ('Manus', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- GOOGLE *Manus AI, entity unclear'),
  ('SCRIBD', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- content/research tooling, entity unclear'),
  ('VERCEL', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- app hosting, entity unclear'),
  ('AGENTQL', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- web-agent/scraping tooling, entity unclear'),
  ('HOSTAWAY', 'ariel_personal', 'out', '5100', 20, 'everest_capital_brevard', 'INFERRED, well-grounded: short-term-rental management SaaS for the Airbnb listing whose income lands in everest_capital_brevard'),
  ('NIC*-FL SUNBIZ.ORG', 'ariel_personal', 'out', '5900', 20, null, 'Florida Sunbiz LLC annual-report filing fee paid personally -- business compliance cost, entity unclear (5 near-identical same-day charges suggest multiple LLCs filed at once)');

-- --- Property income (brevard) ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('AIRBNB', 'everest_capital_brevard', 'in', '4000', 20, 'Airbnb host payout income'),
  ('STRIPE', 'everest_capital_brevard', 'in', '4000', 20, 'Stripe payout income'),
  ('WT FED#', 'everest_capital_brevard', 'in', '4000', 15, 'Title-company closing wire -- property sale proceeds (Seller proceeds / closing disbursement). LARGE $ amounts, flagged for Ariel review in findings.'),
  ('WT 26', 'everest_capital_brevard', 'out', '5900', 15, 'Large outbound wire to named individual (Bank Hapoalim / Bank Yahav, Israel) -- INFERRED Other Expense; likely investor/family distribution or loan repayment tied to a property sale. Flagged for Ariel review given size.');

-- --- Zelle: income on personal, contractor/maintenance expense on brevard ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('ZELLE FROM', 'ariel_personal', 'in', '4000', 20, 'Zelle income received (Mariam / tenants / property managers)'),
  ('ZELLE TO SHAPIRA MARIAM', 'everest_capital_brevard', 'out', '5000', 15, 'Property maintenance/cleaning paid to Mariam (contractor-style) for the Brevard rental');

-- --- Personal living expenses (not commingled -- genuine personal spend) ---
insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, note) values
  ('INSTACART', 'ariel_personal', 'out', '5900', 30, 'Personal groceries'),
  ('AMAZON', 'ariel_personal', 'out', '5900', 30, 'Personal retail'),
  ('UBER', 'ariel_personal', 'out', '5900', 30, 'Personal rideshare'),
  ('UBR', 'ariel_personal', 'out', '5900', 30, 'Personal rideshare (short descriptor variant)'),
  ('SUNOCO', 'ariel_personal', 'out', '5900', 30, 'Personal gas'),
  ('TURO', 'ariel_personal', 'out', '5900', 30, 'Personal car rental'),
  ('PRICELN', 'ariel_personal', 'out', '5900', 30, 'Personal travel booking'),
  ('WELLS FARGO REWARDS', 'ariel_personal', 'in', '4000', 20, 'Credit card rewards redemption'),
  ('Provisional Credit for Claim', 'ariel_personal', 'in', '4000', 20, 'Bank dispute provisional credit'),
  ('ACH Claim#', 'ariel_personal', 'in', '4000', 20, 'ACH dispute claim credit');


-- ============================================================
-- 4. Mask extraction + linked-account lookup helpers
-- ============================================================

create or replace function finance._extract_mask4(p_name text)
returns text language sql immutable as $$
  select coalesce(
    substring(p_name from 'X{4,}(\d{4})'),
    case when trim(p_name) = 'ONLINE PAYMENT THANK YOU' then '2308' else null end,
    case when p_name ilike '%OVERDRAFT PROTECTION XFER%' then '6160' else null end
  );
$$;

create or replace function finance._linked_account_by_mask(p_mask text)
returns table(bank_account_id uuid, ledger_account_id uuid, entity_code text)
language sql stable as $$
  select ba.id, ba.ledger_account_id, bc.entity_code
  from finance.bank_accounts ba
  join finance.bank_connections bc on bc.id = ba.connection_id
  where bc.status = 'simplefin' and ba.name ilike '%' || p_mask || '%'
  limit 1;
$$;

-- ============================================================
-- 5. finance.categorize_bank_txn
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
begin
  select bt.* into v_bt from finance.bank_transactions bt where bt.id = p_bank_transaction_id;

  select bc.entity_code into v_entity
  from finance.bank_accounts ba join finance.bank_connections bc on bc.id = ba.connection_id
  where ba.id = v_bt.bank_account_id;

  v_dir := case when v_bt.amount_cents > 0 then 'out' else 'in' end;

  select r.* into v_rule
  from finance.category_rules r
  where (r.entity_scope is null or r.entity_scope = v_entity)
    and (r.direction = 'any' or r.direction = v_dir)
    and (
      (r.match_field = 'name' and v_bt.name ilike '%' || r.pattern || '%')
      or (r.match_field = 'merchant_name' and v_bt.merchant_name is not null and v_bt.merchant_name ilike '%' || r.pattern || '%')
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
    -- Deviation from issue's literal "4100" default: ariel_personal and
    -- everest_capital_brevard have no 4100 account (4100 means "Revenue - Fact
    -- Finder" on the other 5 entities -- irrelevant here). Both entities' generic
    -- revenue bucket is 4000, verified live. Documented in docs/spec/19755.md.
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
-- 6. finance.post_bank_txn -- single-leg (non-transfer) posting
-- ============================================================

create or replace function finance.post_bank_txn(p_bank_transaction_id uuid)
returns uuid language plpgsql as $$
declare
  v_bt finance.bank_transactions;
  v_entity text;
  v_bank_ledger_account uuid;
  v_cat record;
  v_other_account uuid;
  v_entry_id uuid;
  v_posted_at timestamptz;
begin
  select bt.* into v_bt from finance.bank_transactions bt where bt.id = p_bank_transaction_id;

  select id into v_entry_id from finance.journal_entries
  where ref_table = 'finance.bank_transactions' and ref_id = p_bank_transaction_id;
  if found then
    return v_entry_id;
  end if;

  select bc.entity_code, ba.ledger_account_id into v_entity, v_bank_ledger_account
  from finance.bank_accounts ba join finance.bank_connections bc on bc.id = ba.connection_id
  where ba.id = v_bt.bank_account_id;

  if v_bank_ledger_account is null then
    raise exception 'post_bank_txn: bank_account % has no ledger_account_id mapped', v_bt.bank_account_id;
  end if;

  select * into v_cat from finance.categorize_bank_txn(p_bank_transaction_id);

  select id into v_other_account from finance.accounts
  where entity_code = v_entity and code = v_cat.account_code;
  if v_other_account is null then
    raise exception 'post_bank_txn: account code % not found for entity %', v_cat.account_code, v_entity;
  end if;

  v_posted_at := case when finance._litigation_gated(v_entity) then null else now() end;

  insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
  values (
    v_entity, v_bt.posted_on,
    format('Bank txn: %s', left(v_bt.name, 120)),
    'bank_transaction', 'finance.bank_transactions', p_bank_transaction_id, v_posted_at, 'finance.post_bank_txn'
  ) returning id into v_entry_id;

  if v_bt.amount_cents > 0 then
    insert into finance.postings (entry_id, account_id, debit_cents, memo)
      values (v_entry_id, v_other_account, v_bt.amount_cents, coalesce(v_cat.note, 'categorized expense'));
    insert into finance.postings (entry_id, account_id, credit_cents, memo)
      values (v_entry_id, v_bank_ledger_account, v_bt.amount_cents, 'bank outflow');
  else
    insert into finance.postings (entry_id, account_id, debit_cents, memo)
      values (v_entry_id, v_bank_ledger_account, -v_bt.amount_cents, 'bank inflow');
    insert into finance.postings (entry_id, account_id, credit_cents, memo)
      values (v_entry_id, v_other_account, -v_bt.amount_cents, coalesce(v_cat.note, 'categorized income'));
  end if;

  insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
  values (p_bank_transaction_id, 'ledger_entry', v_entry_id::text, 'post_bank_txn', 1.0);

  if not v_cat.matched then
    insert into finance.recon_exceptions (bank_transaction_id, entry_id, reason, status)
    values (p_bank_transaction_id, v_entry_id, 'uncategorized', 'open');
  end if;

  insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
  values (
    '19755', v_entity, 'post_bank_txn',
    case when finance._litigation_gated(v_entity) then 'PARTIAL' else 'VERIFIED' end,
    p_bank_transaction_id::text,
    jsonb_build_object('journal_entry_id', v_entry_id, 'amount_cents', v_bt.amount_cents, 'account_code', v_cat.account_code, 'matched_rule', v_cat.matched),
    case when finance._litigation_gated(v_entity) then 'warn' else 'info' end
  );

  return v_entry_id;
end;
$$;

grant execute on function finance.post_bank_txn(uuid) to service_role;

-- Note: 'ONLINE PAYMENT THANK YOU' (mask hardcoded '2308') extracts a mask that IS the
-- transaction's own account (the Visa itself), so _linked_account_by_mask resolves to
-- v_bt.bank_account_id. The self-mask branch below broadens the search to any OTHER
-- linked account instead of bailing out -- an earlier version that bailed out produced 6
-- false 'transfer_no_counterpart' exceptions (later silently overwritten with a real match
-- when the opposite/checking-side leg was processed and found this row directly).

create or replace function finance.post_bank_transfer(p_bank_transaction_id uuid)
returns uuid language plpgsql as $$
declare
  v_bt finance.bank_transactions;
  v_own_entity text;
  v_own_ledger_account uuid;
  v_mask text;
  v_cp record;
  v_cp_bt finance.bank_transactions;
  v_entry_id uuid;
  v_entry_id2 uuid;
  v_own_equity uuid;
  v_cp_equity uuid;
  v_synthetic_ref_id uuid;
  v_1002 uuid;
begin
  select bt.* into v_bt from finance.bank_transactions bt where bt.id = p_bank_transaction_id;

  if exists (select 1 from finance.journal_entries where ref_table = 'finance.bank_transactions' and ref_id = p_bank_transaction_id)
     or exists (select 1 from finance.recon_matches where bank_transaction_id = p_bank_transaction_id) then
    return null;
  end if;

  select bc.entity_code, ba.ledger_account_id into v_own_entity, v_own_ledger_account
  from finance.bank_accounts ba join finance.bank_connections bc on bc.id = ba.connection_id
  where ba.id = v_bt.bank_account_id;

  v_mask := finance._extract_mask4(v_bt.name);
  if v_mask is null then
    return null;
  end if;

  if v_mask = '6160' then
    select id into v_1002 from finance.accounts where entity_code = 'everest_capital_brevard' and code = '1002';

    if v_own_entity = 'everest_capital_brevard' then
      insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
      values (v_own_entity, v_bt.posted_on, format('Internal transfer (WF Savings 6160 / overdraft sweep): %s', left(v_bt.name, 100)),
              'bank_transfer', 'finance.bank_transactions', p_bank_transaction_id, null, 'finance.post_bank_transfer')
      returning id into v_entry_id;

      if v_bt.amount_cents > 0 then
        insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id, v_1002, v_bt.amount_cents, 'to unlinked 6160/overdraft sweep');
        insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id, v_own_ledger_account, v_bt.amount_cents, 'from own checking');
      else
        insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id, v_own_ledger_account, -v_bt.amount_cents, 'to own checking');
        insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id, v_1002, -v_bt.amount_cents, 'from unlinked 6160/overdraft sweep');
      end if;

      insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
      values (p_bank_transaction_id, 'ledger_entry', v_entry_id::text, 'post_bank_transfer_6160_intra', 1.0);

      insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
      values ('19755', v_own_entity, 'post_bank_transfer.6160_intra', 'PARTIAL', p_bank_transaction_id::text,
        jsonb_build_object('journal_entry_id', v_entry_id, 'amount_cents', v_bt.amount_cents), 'warn');

      return v_entry_id;
    else
      select id into v_own_equity from finance.accounts where entity_code = v_own_entity and code = '3000';
      select id into v_cp_equity from finance.accounts where entity_code = 'everest_capital_brevard' and code = '3000';
      v_synthetic_ref_id := md5(p_bank_transaction_id::text || ':6160_counterpart')::uuid;

      insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
      values (v_own_entity, v_bt.posted_on, format('Inter-entity transfer via brevard WF Savings 6160: %s', left(v_bt.name, 100)),
              'bank_transfer', 'finance.bank_transactions', p_bank_transaction_id, now(), 'finance.post_bank_transfer')
      returning id into v_entry_id;

      if v_bt.amount_cents > 0 then
        insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id, v_own_equity, v_bt.amount_cents, 'contribution to brevard via 6160');
        insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id, v_own_ledger_account, v_bt.amount_cents, 'own account outflow');
      else
        insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id, v_own_ledger_account, -v_bt.amount_cents, 'own account inflow');
        insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id, v_own_equity, -v_bt.amount_cents, 'draw from brevard via 6160');
      end if;

      insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
      values ('everest_capital_brevard', v_bt.posted_on,
              format('Inter-entity transfer via WF Savings 6160 (synthetic counterpart of ariel_personal bank txn %s -- 6160 is not synced to SimpleFIN, no real bank row exists on this side)', p_bank_transaction_id),
              'bank_transfer_synthetic', 'finance.bank_transactions:6160_counterpart', v_synthetic_ref_id, null, 'finance.post_bank_transfer')
      on conflict (ref_table, ref_id) where ref_table is not null and ref_id is not null do nothing
      returning id into v_entry_id2;

      if v_entry_id2 is not null then
        if v_bt.amount_cents > 0 then
          insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id2, v_cp_equity, -v_bt.amount_cents, 'owner draw (synthetic counterpart)');
          insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id2, v_1002, -v_bt.amount_cents, 'unlinked 6160 outflow (synthetic)');
        else
          insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id2, v_1002, v_bt.amount_cents * -1, 'unlinked 6160 inflow (synthetic)');
          insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id2, v_cp_equity, v_bt.amount_cents * -1, 'owner contribution (synthetic)');
        end if;
      end if;

      insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
      values (p_bank_transaction_id, 'ledger_entry', v_entry_id::text, 'post_bank_transfer_6160_inter', 1.0);

      insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
      values ('19755', v_own_entity, 'post_bank_transfer.6160_inter', 'VERIFIED', p_bank_transaction_id::text,
        jsonb_build_object('journal_entry_id', v_entry_id, 'brevard_synthetic_entry_id', v_entry_id2, 'amount_cents', v_bt.amount_cents), 'info');

      return v_entry_id;
    end if;
  end if;

  -- Linked-account mask path. Self-mask ('ONLINE PAYMENT THANK YOU' resolves to its own
  -- Visa account) -> broaden to any OTHER linked account instead of bailing out.
  select * into v_cp from finance._linked_account_by_mask(v_mask);

  if v_cp.bank_account_id is null then
    return null;
  end if;

  if v_cp.bank_account_id = v_bt.bank_account_id then
    select bt2.* into v_cp_bt
    from finance.bank_transactions bt2
    join finance.bank_accounts ba2 on ba2.id = bt2.bank_account_id
    join finance.bank_connections bc2 on bc2.id = ba2.connection_id
    where bc2.status = 'simplefin'
      and bt2.bank_account_id <> v_bt.bank_account_id
      and bt2.amount_cents = -v_bt.amount_cents
      and bt2.posted_on between v_bt.posted_on - 3 and v_bt.posted_on + 3
      and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt2.id)
      and not exists (select 1 from finance.journal_entries je where je.ref_table = 'finance.bank_transactions' and je.ref_id = bt2.id)
    order by abs(bt2.posted_on - v_bt.posted_on) asc
    limit 1;

    if v_cp_bt.id is not null then
      select ba2.id, ba2.ledger_account_id, bc2.entity_code
      into v_cp.bank_account_id, v_cp.ledger_account_id, v_cp.entity_code
      from finance.bank_accounts ba2 join finance.bank_connections bc2 on bc2.id = ba2.connection_id
      where ba2.id = v_cp_bt.bank_account_id;
    end if;
  else
    select bt2.* into v_cp_bt
    from finance.bank_transactions bt2
    where bt2.bank_account_id = v_cp.bank_account_id
      and bt2.amount_cents = -v_bt.amount_cents
      and bt2.posted_on between v_bt.posted_on - 3 and v_bt.posted_on + 3
      and not exists (select 1 from finance.recon_matches m where m.bank_transaction_id = bt2.id)
      and not exists (select 1 from finance.journal_entries je where je.ref_table = 'finance.bank_transactions' and je.ref_id = bt2.id)
    order by abs(bt2.posted_on - v_bt.posted_on) asc
    limit 1;
  end if;

  if v_cp_bt.id is null then
    return null;
  end if;

  if v_own_entity = v_cp.entity_code then
    insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
    values (v_own_entity, v_bt.posted_on, format('Internal transfer: %s', left(v_bt.name, 100)),
            'bank_transfer', 'finance.bank_transactions', p_bank_transaction_id,
            case when finance._litigation_gated(v_own_entity) then null else now() end, 'finance.post_bank_transfer')
    returning id into v_entry_id;

    if v_bt.amount_cents > 0 then
      insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id, v_own_ledger_account, v_bt.amount_cents, 'transfer out');
      insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id, v_cp.ledger_account_id, v_bt.amount_cents, 'transfer in');
    else
      insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id, v_own_ledger_account, -v_bt.amount_cents, 'transfer in');
      insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id, v_cp.ledger_account_id, -v_bt.amount_cents, 'transfer out');
    end if;

    insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
    values (p_bank_transaction_id, 'ledger_entry', v_entry_id::text, 'post_bank_transfer_intra', 1.0);
    insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
    values (v_cp_bt.id, 'ledger_entry', v_entry_id::text, 'post_bank_transfer_intra', 1.0);

    insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
    values ('19755', v_own_entity, 'post_bank_transfer.intra', 'VERIFIED', p_bank_transaction_id::text,
      jsonb_build_object('journal_entry_id', v_entry_id, 'counterpart_bt_id', v_cp_bt.id, 'amount_cents', v_bt.amount_cents), 'info');

    return v_entry_id;
  else
    select id into v_own_equity from finance.accounts where entity_code = v_own_entity and code = '3000';
    select id into v_cp_equity from finance.accounts where entity_code = v_cp.entity_code and code = '3000';

    insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
    values (v_own_entity, v_bt.posted_on, format('Inter-entity transfer: %s', left(v_bt.name, 100)),
            'bank_transfer', 'finance.bank_transactions', p_bank_transaction_id,
            case when finance._litigation_gated(v_own_entity) then null else now() end, 'finance.post_bank_transfer')
    returning id into v_entry_id;

    if v_bt.amount_cents > 0 then
      insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id, v_own_ledger_account, v_bt.amount_cents, 'inter-entity transfer out');
      insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id, v_own_equity, v_bt.amount_cents, 'owner draw/contribution');
    else
      insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id, v_own_ledger_account, -v_bt.amount_cents, 'inter-entity transfer in');
      insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id, v_own_equity, -v_bt.amount_cents, 'owner draw/contribution');
    end if;

    insert into finance.journal_entries (entity_code, entry_date, memo, source, ref_table, ref_id, posted_at, created_by)
    values (v_cp.entity_code, v_cp_bt.posted_on, format('Inter-entity transfer: %s', left(v_cp_bt.name, 100)),
            'bank_transfer', 'finance.bank_transactions', v_cp_bt.id,
            case when finance._litigation_gated(v_cp.entity_code) then null else now() end, 'finance.post_bank_transfer')
    returning id into v_entry_id2;

    if v_cp_bt.amount_cents > 0 then
      insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id2, v_cp.ledger_account_id, v_cp_bt.amount_cents, 'inter-entity transfer out');
      insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id2, v_cp_equity, v_cp_bt.amount_cents, 'owner draw/contribution');
    else
      insert into finance.postings (entry_id, account_id, debit_cents, memo) values (v_entry_id2, v_cp.ledger_account_id, -v_cp_bt.amount_cents, 'inter-entity transfer in');
      insert into finance.postings (entry_id, account_id, credit_cents, memo) values (v_entry_id2, v_cp_equity, -v_cp_bt.amount_cents, 'owner draw/contribution');
    end if;

    insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
    values (p_bank_transaction_id, 'ledger_entry', v_entry_id::text, 'post_bank_transfer_inter', 1.0);
    insert into finance.recon_matches (bank_transaction_id, matched_type, matched_id, rule, confidence)
    values (v_cp_bt.id, 'ledger_entry', v_entry_id2::text, 'post_bank_transfer_inter', 1.0);

    insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
    values ('19755', v_own_entity, 'post_bank_transfer.inter', 'VERIFIED', p_bank_transaction_id::text,
      jsonb_build_object('own_entry_id', v_entry_id, 'cp_entry_id', v_entry_id2, 'cp_entity', v_cp.entity_code, 'amount_cents', v_bt.amount_cents), 'info');

    return v_entry_id;
  end if;
end;
$$;

grant execute on function finance.post_bank_transfer(uuid) to service_role;

-- ============================================================
-- 8. finance.process_bank_transactions -- orchestrator
-- ============================================================

create or replace function finance.process_bank_transactions(p_entity_code text default null)
returns table(processed int, categorized int, transferred int, uncategorized int, errored int)
language plpgsql as $$
declare
  r record;
  v_result uuid;
  v_processed int := 0;
  v_categorized int := 0;
  v_transferred int := 0;
  v_uncategorized int := 0;
  v_errored int := 0;
  v_is_transfer boolean;
begin
  for r in
    select bt.id, bt.name
    from finance.bank_transactions bt
    join finance.bank_accounts ba on ba.id = bt.bank_account_id
    join finance.bank_connections bc on bc.id = ba.connection_id
    where bc.status = 'simplefin'
      and (p_entity_code is null or bc.entity_code = p_entity_code)
    order by bt.posted_on, bt.id
  loop
    if exists (select 1 from finance.recon_matches where bank_transaction_id = r.id)
       or exists (select 1 from finance.journal_entries where ref_table = 'finance.bank_transactions' and ref_id = r.id) then
      continue;
    end if;

    begin
      select is_transfer into v_is_transfer from finance.categorize_bank_txn(r.id);

      if v_is_transfer then
        v_result := finance.post_bank_transfer(r.id);
        if v_result is not null then
          v_transferred := v_transferred + 1;
        else
          if not exists (select 1 from finance.recon_exceptions where bank_transaction_id = r.id and status = 'open') then
            insert into finance.recon_exceptions (bank_transaction_id, reason, status)
            values (r.id, 'transfer_no_counterpart', 'open');
          end if;
          v_uncategorized := v_uncategorized + 1;
        end if;
      else
        v_result := finance.post_bank_txn(r.id);
        v_categorized := v_categorized + 1;
        if exists (select 1 from finance.recon_exceptions where bank_transaction_id = r.id and reason = 'uncategorized') then
          v_uncategorized := v_uncategorized + 1;
        end if;
      end if;

      v_processed := v_processed + 1;
    exception when others then
      v_errored := v_errored + 1;
      insert into public.finance_ops_log (dispatch_id, entity, task, status, source_event_id, evidence, severity)
      values ('19755', coalesce(p_entity_code, 'unknown'), 'process_bank_transactions.error', 'BLOCKED', r.id::text,
        jsonb_build_object('error', sqlerrm, 'name', r.name), 'blocker');
    end;
  end loop;

  processed := v_processed;
  categorized := v_categorized;
  transferred := v_transferred;
  uncategorized := v_uncategorized;
  errored := v_errored;
  return next;
end;
$$;

grant execute on function finance.process_bank_transactions(text) to service_role, cfo_agent_ro;

-- Reconcile any 'transfer_no_counterpart' exception that in fact got matched by the
-- counterpart leg's own pairing pass (the self-mask bug fixed above, pre-existing data only).
update finance.recon_exceptions e
set status = 'resolved',
    resolved_at = now(),
    resolution = 'matched_on_counterpart_pass -- self-mask false-negative in an earlier post_bank_transfer() pass; counterpart leg later found and paired this row correctly'
where e.reason = 'transfer_no_counterpart'
  and e.status = 'open'
  and exists (select 1 from finance.recon_matches m where m.bank_transaction_id = e.bank_transaction_id);

-- ============================================================
-- 9. finance.v_commingled_business_costs (issue scope #4: business infra paid from the
--    PERSONAL account only -- NOT the reverse case of brevard paying biddeed-stack vendors,
--    which is documented as a separate finding in docs/spec/19755.md, not a schema deliverable).
--    Reads back the ACTUAL posted ledger (journal_entries/postings) rather than re-deriving
--    categorization, so it can never drift from what was really posted.
-- ============================================================

create or replace view finance.v_commingled_business_costs
with (security_invoker = true) as
select
  bt.posted_on as txn_date,
  bt.name as vendor_description,
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
    and r.match_field = 'name' and bt.name ilike '%' || r.pattern || '%'
  order by r.priority asc, r.id asc limit 1
)
where bc.status = 'simplefin' and bc.entity_code = 'ariel_personal'
order by bt.posted_on;

grant select on finance.v_commingled_business_costs to cfo_agent_ro;

-- ============================================================
-- 10. finance.v_recurring_costs
-- ============================================================
-- is_recurring_eligible: false = one-off/non-subscription pattern (e.g. large wire
-- distributions, property-sale proceeds) that should never feed this view's run-rate math
-- even if it happens to recur a few times by coincidence. Without this, 3 large one-off
-- distribution wires ('WT 26...') 8-10 days apart get classified 'weekly' cadence ->
-- $125,310.79/mo phantom run-rate, which would badly corrupt burn/runway.

alter table finance.category_rules add column is_recurring_eligible boolean not null default true;

update finance.category_rules
set is_recurring_eligible = false
where pattern in ('WT 26', 'WT FED#');

comment on column finance.category_rules.is_recurring_eligible is
  'false = one-off/non-subscription pattern (e.g. large wire distributions, property-sale '
  'proceeds) that should never feed finance.v_recurring_costs run-rate math even if it '
  'happens to recur a few times by coincidence.';

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
      and r.match_field = 'name' and bt.name ilike '%' || r.pattern || '%'
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

insert into finance.category_rules (pattern, entity_scope, direction, account_code, priority, likely_business_entity, note) values
  ('Hetzner', 'ariel_personal', 'out', '5100', 20, null, 'INFERRED business infra paid personally -- Hetzner compute (CLIProxyAPI host per CLAUDE.md stack), entity unclear'),
  ('Google Workspace_zonewise', 'ariel_personal', 'out', '5100', 15, 'zonewise', 'CONFIRMED by descriptor: ZoneWise.AI Google Workspace billing paid personally');

commit;

-- CFO v1 Issue G (CP6b), issue #19755: pre-flight cleanup, run before
-- 20260902q_cfo_bank_categorization_posting_v1.sql.
--
-- Finding: live finance.bank_transactions for the 4 SimpleFIN-linked accounts
-- (…3519, …9264 everest_capital_brevard; …1130, …2308 ariel_personal) held 954 rows, not
-- the 338 the issue's brief cites as "338 real WF transactions loaded, trailing 90 days."
--
-- Root cause: an earlier finance.simplefin_sync() run wrote 338 rows with
-- plaid_transaction_id NOT prefixed 'simplefin:' (bare 'TRN-...'), a stub
-- raw = {"src":"simplefin"}, and the OPPOSITE sign of the table's documented convention
-- (finance.bank_transactions.amount_cents: positive = outflow, negative = inflow -- see
-- 20260902_finance_ledger_v1.sql). A later, complete sync wrote 616 rows: prefixed
-- 'simplefin:', full raw SimpleFIN JSON payload, and the correct sign (verified against the
-- raw payload: SimpleFIN's own convention is positive=inflow, so the sync correctly negates
-- it on write -- e.g. Anthropic ACH raw amount "-10.99" -> stored amount_cents=+1099 outflow;
-- Airbnb payout raw amount "441.09" -> stored amount_cents=-44109 inflow).
--
-- Verified live: every one of the 338 stub rows exact-matches exactly one row in the 616 by
-- (name, posted_on, abs(amount_cents)) -- a clean 1:1 join, no fan-out, no orphans on either
-- side (old_count=338, old_distinct_keys=338, raw_join_rows=338, old_ids_matched=338,
-- new_ids_matched=338). They are pure duplicates of a subset of the correct 616, not
-- additional real transactions. Categorizing/posting both sets would double-count every
-- shared transaction and get the DR/CR direction backwards for the 338 stub-sign rows.
--
-- True population: 616 real WF transactions (421 ariel_personal, 195 everest_capital_brevard).

begin;

delete from finance.recon_exceptions
where bank_transaction_id in (
  select o.id
  from finance.bank_transactions o
  join finance.bank_accounts ba on ba.id = o.bank_account_id
  join finance.bank_connections bc on bc.id = ba.connection_id
  join finance.bank_transactions n
    on n.name = o.name and n.posted_on = o.posted_on and abs(n.amount_cents) = abs(o.amount_cents)
    and n.plaid_transaction_id ilike 'simplefin:%'
  where bc.status = 'simplefin' and o.plaid_transaction_id not ilike 'simplefin:%'
);

delete from finance.recon_matches
where bank_transaction_id in (
  select o.id
  from finance.bank_transactions o
  join finance.bank_accounts ba on ba.id = o.bank_account_id
  join finance.bank_connections bc on bc.id = ba.connection_id
  join finance.bank_transactions n
    on n.name = o.name and n.posted_on = o.posted_on and abs(n.amount_cents) = abs(o.amount_cents)
    and n.plaid_transaction_id ilike 'simplefin:%'
  where bc.status = 'simplefin' and o.plaid_transaction_id not ilike 'simplefin:%'
);

delete from finance.bank_transactions o
using finance.bank_accounts ba, finance.bank_connections bc, finance.bank_transactions n
where ba.id = o.bank_account_id
  and bc.id = ba.connection_id
  and n.name = o.name and n.posted_on = o.posted_on and abs(n.amount_cents) = abs(o.amount_cents)
  and n.plaid_transaction_id ilike 'simplefin:%'
  and bc.status = 'simplefin'
  and o.plaid_transaction_id not ilike 'simplefin:%';

commit;

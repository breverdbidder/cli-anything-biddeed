"""finance_plaid_expense_ingest.py -- TODO / NOT EXECUTABLE / BLOCKED ON ARIEL

Purpose (once activated): pull transactions from a Plaid-connected bank
account and write finance.expense_ledger rows (source='plaid_bank_feed'),
alongside the existing manual path (finance.record_expense(), source='manual').

BLOCKED on (Ariel-only, cannot be done by an agent):
  1. Ariel connects a bank account via the Plaid Developer Tools connector
     he has available, and supplies PLAID_CLIENT_ID / PLAID_SECRET /
     PLAID_ACCESS_TOKEN as GitHub secrets (or Supabase vault entries pulled
     through the sanctioned accessors in CLAUDE.md's CREDENTIAL HANDLING
     section -- never inline, never log, never echo).
  2. Ariel decides which account(s) feed which finance.entities.code (e.g.
     does one bank account cover multiple entities, or one per entity?).

This file intentionally contains no live Plaid client calls, no requests
session, and is not wired into any .github/workflows/*.yml cron. Running it
today does nothing -- see main() below.

Intended shape once unblocked:
  1. plaid_client.transactions_sync(access_token, cursor) per bank account
     on file, paginating via `next_cursor` until has_more=False.
  2. For each new transaction:
       - map Plaid category -> finance.expense_ledger.category (needs a
         crosswalk table or CASE list -- not designed yet)
       - map the connected account -> finance.entities.code (see blocker #2)
       - INSERT via finance.record_expense(), but with source='plaid_bank_feed'
         instead of 'manual' -- record_expense() as written in
         supabase/migrations/20260831d_cfo_bookkeeping_billable_ff_wiring.sql
         hardcodes source='manual', so this WILL need either a new
         finance.record_expense_from_feed() RPC or a source parameter added
         to the existing one -- do not silently repurpose the manual path.
  3. Persist the Plaid `cursor` per account (new table or a column on a
     bank-account-registry table that does not exist yet) so re-runs are
     incremental, not full re-pulls.
  4. Idempotency: Plaid transaction_id should be stored (needs a new nullable
     column on finance.expense_ledger, e.g. plaid_transaction_id, with a
     unique index) so a re-run does not double-insert.

None of the above is implemented. This file exists so the next session that
picks up Plaid work has a concrete starting shape instead of a blank page.
"""


def main() -> None:
    raise SystemExit(
        "finance_plaid_expense_ingest.py is a scaffold, not a working "
        "integration. It requires Ariel to connect a Plaid-linked bank "
        "account and supply PLAID_CLIENT_ID/PLAID_SECRET/PLAID_ACCESS_TOKEN "
        "before any code here can run. See the module docstring."
    )


if __name__ == "__main__":
    main()

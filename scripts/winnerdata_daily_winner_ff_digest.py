#!/usr/bin/env python3
""""The Daily Winner FFs" -- BUILD step (issue #19482, Aug 27 scope change).

Computes that day's guard-passed (#19481), routed leads for Protection
Partners and writes/upserts a winnerdata.ff_batches row with
status='pending_approval'. This script NEVER sends email and NEVER touches
Resend -- sending only happens in scripts/winnerdata_ff_send_approved.py,
and only for a batch Ariel has explicitly approved via
public.ff_approve_batch(). See that migration
(supabase/migrations/20260827_winnerdata_ff_batches_approval_gate.sql) for
the full design rationale.

Zero-lead days still get a batch row (lead_count=0, status=pending_approval)
so Ariel's 7 AM Cowork report always has something to show -- the pipeline
never goes silent.

If a batch row for this date already exists, this script leaves it alone
(does not reset an approved/sent batch back to pending_approval on a
workflow rerun) and just reports its current state.

Run:
  python scripts/winnerdata_daily_winner_ff_digest.py [--dry-run]
    [--batch-date YYYY-MM-DD]
"""
import argparse
import sys

from winnerdata_ff_digest_lib import get_batch_leads, run_sql, sql_str


def upsert_pending_batch(batch_date, lead_count, dry_run):
    if dry_run:
        print(f"[DRY-RUN] Would upsert winnerdata.ff_batches({batch_date}, pending_approval, lead_count={lead_count})")
        return "dry_run_pending_approval"

    run_sql(f"""
        insert into winnerdata.ff_batches (batch_date, status, lead_count)
        values ({sql_str(batch_date)}, 'pending_approval', {lead_count})
        on conflict (batch_date) do nothing;
    """)
    rows = run_sql(f"select status, lead_count from winnerdata.ff_batches where batch_date = {sql_str(batch_date)};")
    return rows[0] if rows else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch-date", default=None, help="YYYY-MM-DD, defaults to yesterday (UTC)")
    args = ap.parse_args()

    if args.batch_date:
        batch_date = args.batch_date
    else:
        batch_date = run_sql("select (current_date - interval '1 day')::date::text as d;")[0]["d"]

    print(f"Batch date: {batch_date}")

    leads = get_batch_leads(batch_date)
    print(f"{len(leads)} qualifying lead(s) for {batch_date}.")

    result = upsert_pending_batch(batch_date, len(leads), args.dry_run)
    print(f"ff_batches state: {result}")

    if isinstance(result, dict) and result.get("status") != "pending_approval":
        print(f"NOTE: batch already {result.get('status')} -- did not overwrite (workflow rerun, not a new build).")

    sys.exit(0)


if __name__ == "__main__":
    main()

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

Issue #19619 fix: persists the actual lead rows into
winnerdata.seller_digest_leads immediately after upserting the batch row,
so enrichment + PDF render have something to read before approval.

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

    # #19727: a rerun for a batch_date that already has a row used to be a
    # pure no-op (on conflict do nothing), so a batch stuck at lead_count=0
    # because routing failed earlier that day could never be refreshed once
    # routing was fixed -- only a NEW batch_date row ever got the real count.
    # Still never touches an approved/sent batch (status guard below) --
    # only refreshes the count while it's still pending_approval.
    run_sql(f"""
        insert into winnerdata.ff_batches (batch_date, status, lead_count, batch_kind)
        values ({sql_str(batch_date)}, 'pending_approval', {lead_count}, 'seller_digest')
        on conflict (batch_date) do update
          set lead_count = excluded.lead_count
          where winnerdata.ff_batches.status = 'pending_approval';
    """)
    rows = run_sql(f"select status, lead_count from winnerdata.ff_batches where batch_date = {sql_str(batch_date)};")
    return rows[0] if rows else None


def persist_seller_digest_leads(batch_date, leads, dry_run):
    """Write the actual lead rows into winnerdata.seller_digest_leads.

    This is the fix for issue #19619: previously only the count was stored.
    Uses insert ... on conflict do nothing so rerunning the build step on the
    same batch_date is safe -- already-persisted rows (possibly enriched) are
    not overwritten.
    """
    if dry_run:
        print(f"[DRY-RUN] Would persist {len(leads)} lead row(s) into winnerdata.seller_digest_leads for {batch_date}.")
        return len(leads)

    if not leads:
        print("Zero leads -- no rows to persist.")
        return 0

    written = 0
    skipped = 0
    for lead in leads:
        lead_id = lead.get("lead_id")
        if not lead_id:
            print(f"  WARN: lead row missing lead_id, skipping: {lead}", file=sys.stderr)
            skipped += 1
            continue
        sold_amount = lead.get("sold_amount")
        sold_amount_lit = str(float(sold_amount)) if sold_amount is not None else "null"
        unresolved = sum([
            1 if not lead.get("email_tier") else 0,
            1 if not lead.get("phone_tier") else 0,
        ])
        run_sql(f"""
            insert into winnerdata.seller_digest_leads (
                batch_date, lead_id, entity_name, county, sale_type, case_number,
                sold_amount, property_address, routed_at, email_tier, phone_tier,
                unresolved_field_count
            ) values (
                {sql_str(batch_date)},
                '{lead_id}'::uuid,
                {sql_str(lead.get('entity_name'))},
                {sql_str(lead.get('county'))},
                {sql_str(lead.get('sale_type'))},
                {sql_str(lead.get('case_number'))},
                {sold_amount_lit},
                {sql_str(lead.get('property_address'))},
                {sql_str(lead.get('routed_at'))},
                {sql_str(lead.get('email_tier'))},
                {sql_str(lead.get('phone_tier'))},
                {unresolved}
            )
            on conflict (batch_date, lead_id) do nothing;
        """)
        written += 1

    print(f"seller_digest_leads: {written} row(s) inserted (on conflict do nothing), {skipped} skipped.")
    verify = run_sql(f"select count(*) as n from winnerdata.seller_digest_leads where batch_date = {sql_str(batch_date)};")
    actual = verify[0]["n"] if verify else "unknown"
    print(f"seller_digest_leads verification: {actual} row(s) in DB for {batch_date}.")
    return written


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

    persist_seller_digest_leads(batch_date, leads, args.dry_run)

    sys.exit(0)


if __name__ == "__main__":
    main()

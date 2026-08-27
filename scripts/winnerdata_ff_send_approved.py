#!/usr/bin/env python3
""""The Daily Winner FFs" -- SEND step (issue #19482, Aug 27 scope change).

Sends via Resend for any winnerdata.ff_batches row with status='approved'
and sent_at is null, then flips it to status='sent'. Never touches
pending_approval rows -- the only path to 'approved' is Ariel calling
public.ff_approve_batch() (typically via the Cowork task), so this script
sending is gated entirely on that RPC having already run.

Invoked two ways (see winnerdata-ff-send-approved.yml):
  1. Immediately, by the winnerdata.ff_batches_notify_approved trigger firing
     a workflow_dispatch with --batch-date set to the just-approved date.
  2. As a bounded-morning-window backstop poll with no --batch-date filter,
     in case the trigger's outbound dispatch call ever fails -- safe to run
     redundantly since it only touches status='approved' rows.

Recomputes the lead list live at send time (does not trust build-time
lead_count) so a routing/guard correction made between build and approval
is reflected in what actually ships.

BLOCKING: if no email is on file for Mariam Shapira in
winnerdata.producers, this logs 'blocked_no_email' to
winnerdata.ff_digest_log and does NOT flip the batch to 'sent' (so a fixed
email can re-trigger a send later) -- never fabricates a recipient.

Run:
  python scripts/winnerdata_ff_send_approved.py [--dry-run]
    [--batch-date YYYY-MM-DD] [--test-send-to EMAIL]

--test-send-to overrides the recipient with a known-safe test address
(never Mariam's) so the Resend mechanism/template can be proven live
without depending on a real producer email.
"""
import argparse
import sys

from winnerdata_ff_digest_lib import (
    get_batch_leads,
    get_producer_email,
    log_digest,
    render_email,
    run_sql,
    send_resend,
    sql_str,
)


def get_approved_batches(batch_date):
    # batch_kind='seller_digest' is required: winnerdata.ff_batches is shared
    # with the nine-case third-party-auction portfolio batches (issue #19531),
    # whose leads live in winnerdata.ff_batch_leads and whose send step is a
    # separate, explicit, enrichment-gated action -- never this generic
    # digest sender. Without this filter the */15 backstop poll below would
    # pick up a portfolio batch the instant it's approved (before enrichment
    # even starts), query the wrong lead source (winnerdata.leads), get zero
    # rows, and still call mark_sent() -- burning the 'sent' terminal state
    # on a batch that was never actually delivered.
    where = "where status = 'approved' and batch_kind = 'seller_digest'"
    if batch_date:
        where += f" and batch_date = {sql_str(batch_date)}"
    return run_sql(f"select batch_date, lead_count from winnerdata.ff_batches {where} order by batch_date;")


def mark_sent(batch_date):
    run_sql(f"""
        update winnerdata.ff_batches
        set status = 'sent', sent_at = now(), updated_at = now()
        where batch_date = {sql_str(batch_date)} and status = 'approved';
    """)


def process_batch(batch, test_send_to, dry_run):
    batch_date = batch["batch_date"]
    print(f"--- Processing approved batch {batch_date} ---")

    recipient = test_send_to or get_producer_email()
    if not recipient:
        print("BLOCKED: no email on file for Mariam Shapira (winnerdata.producers.email is null). "
              "Not sending -- never fabricating a recipient. Batch stays 'approved' for retry once fixed.")
        if not dry_run:
            log_digest(batch_date, None, 0, None, "blocked_no_email")
        return

    leads = get_batch_leads(batch_date)
    print(f"{len(leads)} qualifying lead(s) for {batch_date} at send time.")

    subject, text, html = render_email(batch_date, leads)
    print(f"Subject: {subject}")

    msg_id, err = send_resend(recipient, subject, text, html, dry_run)

    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        if not dry_run:
            log_digest(batch_date, recipient, len(leads), None, "error", error=err)
        return

    print(f"{'[DRY-RUN] ' if dry_run else ''}Sent to {recipient} (msg_id={msg_id}).")
    if not dry_run:
        status = "no_leads_sent" if not leads else "sent"
        log_digest(batch_date, recipient, len(leads), msg_id, status)
        mark_sent(batch_date)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch-date", default=None, help="YYYY-MM-DD; omit to process all approved-unsent batches")
    ap.add_argument("--test-send-to", default=None, help="Safe test recipient override -- never Mariam's")
    args = ap.parse_args()

    batches = get_approved_batches(args.batch_date)
    if not batches:
        print(f"No approved, unsent batches found{' for ' + args.batch_date if args.batch_date else ''}. Nothing to do.")
        sys.exit(0)

    for batch in batches:
        process_batch(batch, args.test_send_to, args.dry_run)


if __name__ == "__main__":
    main()

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

BLOCKING (issue #19659 item 2): if the resolved recipient is a Resend
sandbox/test address (*.resend.dev), this logs 'blocked_sandbox_recipient'
and does NOT send or flip the batch to 'sent' -- a sandbox address always
reports delivered without actually delivering anything, so it can never be
allowed to masquerade as a real send. Internal Everest/BidDeed QA sends
(@biddeed.ai / @everestcapitalusa.com) are still allowed and logged
recipient_kind='internal_qa', but never flip the batch to 'sent' and are
never eligible to back a winnerdata.billable_ff_events row -- only a
recipient_kind='producer' send does that.

BLOCKING (LMS FF Batch Review + Approval screen, 2026-09-01): even once a
batch is 'approved', a lead only ships if it has a decision='approved' row
in winnerdata.ff_batch_lead_review, set from the LMS's per-lead
approve/reject/request-improvement UI (see workers/winnerdata-lms). A lead
with no review row is treated as excluded, not as an implicit approval --
Ariel's explicit conservative default. If qualifying leads exist but none
are approved, this logs 'blocked_unreviewed_leads' and does NOT send or
flip the batch to 'sent'.

BLOCKING (unforgeable approval gate, issue #19745, 2026-09-02): status=
'approved' alone is no longer trusted. Before doing anything else, this
verifies a winnerdata.ff_batch_approvals row exists for the batch whose
snapshot_hash matches the batch's CURRENT (batch_date, batch_kind,
lead_count) -- i.e. an authenticated LMS click approved exactly this batch
state (see get_verified_approval() in winnerdata_ff_digest_lib.py and
supabase/migrations/20260902i_winnerdata_ff_batch_approvals_gate.sql). No
matching row -> logs 'blocked_unverified_approval' and refuses to send, a
hard error, never a silent skip. This is what makes the 2026-09-01 incident
(service-role approval with no human click) structurally impossible: even
if something still flips ff_batches.status via the legacy
public.ff_approve_batch() RPC, there is no way to also forge a matching
ff_batch_approvals row without a real, allow-listed admin's Supabase Auth
JWT.

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
    classify_recipient,
    get_batch_lead_reviews,
    get_batch_leads,
    get_producer_email,
    get_verified_approval,
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
    return run_sql(f"select batch_date, batch_kind, lead_count from winnerdata.ff_batches {where} order by batch_date;")


def mark_sent(batch_date):
    run_sql(f"""
        update winnerdata.ff_batches
        set status = 'sent', sent_at = now(), updated_at = now()
        where batch_date = {sql_str(batch_date)} and status = 'approved';
    """)


def process_batch(batch, test_send_to, dry_run):
    batch_date = batch["batch_date"]
    print(f"--- Processing approved batch {batch_date} ---")

    # issue #19745, item 2: verify, don't trust. status='approved' alone is
    # not enough -- it can still be set by the pre-existing service-role
    # public.ff_approve_batch() RPC, which proves nothing about who/what
    # called it (the exact 2026-09-01 incident this issue closes). Refuse to
    # send unless a matching winnerdata.ff_batch_approvals row exists whose
    # snapshot_hash matches this batch's CURRENT (batch_date, batch_kind,
    # lead_count) -- a hard error, logged, never a silent skip.
    approval = get_verified_approval(batch_date, batch["batch_kind"], batch["lead_count"])
    if not approval:
        print(f"BLOCKED: no verified LMS approval found for {batch_date} matching the batch's "
              f"current state (batch_kind={batch['batch_kind']!r}, lead_count={batch['lead_count']}). "
              "Refusing to send. This is a hard error, not a silent skip -- approve via the LMS "
              "(/ff-batches) to create a matching winnerdata.ff_batch_approvals row. Batch stays "
              "'approved' for retry once a verified approval exists.")
        if not dry_run:
            log_digest(batch_date, None, 0, None, "blocked_unverified_approval")
        return
    print(f"Verified approval: {approval['approved_by_email']} at {approval['approved_at']}.")

    recipient = test_send_to or get_producer_email()
    if not recipient:
        print("BLOCKED: no email on file for Mariam Shapira (winnerdata.producers.email is null). "
              "Not sending -- never fabricating a recipient. Batch stays 'approved' for retry once fixed.")
        if not dry_run:
            log_digest(batch_date, None, 0, None, "blocked_no_email")
        return

    # issue #19659 item 2: Resend's test sandbox (delivered@resend.dev and
    # any other *.resend.dev address) always reports "sent" without
    # delivering anything real -- hard-block it from ever reaching
    # status='sent' so it can never be mistaken for (or feed) a billable
    # event. Real internal-QA sends (Ariel, @biddeed.ai/@everestcapitalusa.com)
    # stay allowed but never flip the batch's terminal state or count billable.
    recipient_kind = classify_recipient(recipient)
    if recipient_kind == "sandbox":
        print(f"BLOCKED: {recipient} is a Resend sandbox/test address -- refusing to mark 'sent'. "
              "Batch stays 'approved' for retry with a real recipient.")
        if not dry_run:
            log_digest(batch_date, recipient, 0, None, "blocked_sandbox_recipient", recipient_kind=recipient_kind)
        return

    leads = get_batch_leads(batch_date)
    print(f"{len(leads)} qualifying lead(s) for {batch_date} at send time.")

    # LMS FF Batch Review + Approval screen (2026-09-01): Ariel now reviews
    # each lead individually (approve/reject/request-improvement) instead of
    # approving the whole batch sight-unseen in chat. Conservative default
    # per his explicit instruction: a lead with NO decision recorded is
    # treated the same as rejected -- it is excluded here, not sent by
    # default. Only winnerdata.ff_batch_lead_review rows with
    # decision='approved' make it into the send.
    if leads:
        reviews = get_batch_lead_reviews(batch_date)
        approved_leads = [l for l in leads if reviews.get(l.get("case_number")) == "approved"]
        excluded = len(leads) - len(approved_leads)
        print(f"Per-lead review: {len(approved_leads)} of {len(leads)} approved for send "
              f"({excluded} excluded as rejected/unreviewed).")
        if not approved_leads:
            print("BLOCKED: qualifying leads exist but none are marked decision='approved' in "
                  "winnerdata.ff_batch_lead_review -- refusing to send. Review each lead in the "
                  "LMS (/ff-batches) then re-approve. Batch stays 'approved' for retry.")
            if not dry_run:
                log_digest(batch_date, recipient, 0, None, "blocked_unreviewed_leads", recipient_kind=recipient_kind)
            return
        leads = approved_leads

    subject, text, html = render_email(batch_date, leads)
    print(f"Subject: {subject}")

    msg_id, err = send_resend(recipient, subject, text, html, dry_run)

    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        if not dry_run:
            log_digest(batch_date, recipient, len(leads), None, "error", error=err, recipient_kind=recipient_kind)
        return

    print(f"{'[DRY-RUN] ' if dry_run else ''}Sent to {recipient} (msg_id={msg_id}, recipient_kind={recipient_kind}).")
    if not dry_run:
        status = "no_leads_sent" if not leads else "sent"
        log_digest(batch_date, recipient, len(leads), msg_id, status, recipient_kind=recipient_kind)
        # Only a genuine producer delivery (not an internal-QA --test-send-to
        # override) consumes the batch's terminal 'sent' state -- a QA send
        # must leave the batch 'approved' so the real producer send can still
        # happen.
        if recipient_kind == "producer":
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

#!/usr/bin/env python3
"""Backfill seller_digest lead rows for the Aug 28 and Aug 29 stuck batches (issue #19619).

These batches have ff_batches rows (built by winnerdata_daily_winner_ff_digest.py)
but NO seller_digest_leads rows because the build step only wrote the count.
This script replays the exact get_batch_leads() query for each date and inserts
the rows into winnerdata.seller_digest_leads, which existed as a concept in the
code but was never populated until this fix.

After running this script, run seller_digest_enrichment.py for each date, then
seller_digest_pdf_render.py for each date.

Usage:
  SUPABASE_ACCESS_TOKEN=... python scripts/seller_digest_backfill.py
  SUPABASE_ACCESS_TOKEN=... python scripts/seller_digest_backfill.py --dates 2026-08-28 2026-08-29

Verification: the script prints exact DB row counts before and after for each
date. NEVER reports success without confirming the count from the DB.
"""
from __future__ import annotations

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from winnerdata_ff_digest_lib import get_batch_leads, run_sql, sql_str  # noqa: E402
from winnerdata_daily_winner_ff_digest import persist_seller_digest_leads  # noqa: E402

BACKFILL_DATES = ["2026-08-28", "2026-08-29"]


def check_ff_batches_row(batch_date: str) -> dict | None:
    rows = run_sql(f"""
        select batch_date, status, lead_count, batch_kind, enrichment_status
        from winnerdata.ff_batches
        where batch_date = {sql_str(batch_date)}
    """)
    return rows[0] if rows else None


def check_existing_leads(batch_date: str) -> int:
    rows = run_sql(f"""
        select count(*) as n from winnerdata.seller_digest_leads
        where batch_date = {sql_str(batch_date)}
    """)
    return int(rows[0]["n"]) if rows else 0


def ensure_ff_batches_row(batch_date: str, lead_count: int) -> None:
    """Insert a ff_batches row for this date if it does not exist yet.
    Uses on conflict do nothing -- if the row exists (even with a different
    lead_count), leave it alone to avoid overwriting any existing state."""
    run_sql(f"""
        insert into winnerdata.ff_batches (batch_date, status, lead_count, batch_kind)
        values ({sql_str(batch_date)}, 'pending_approval', {lead_count}, 'seller_digest')
        on conflict (batch_date) do nothing;
    """)


def backfill_date(batch_date: str, dry_run: bool) -> dict:
    print(f"\n=== Backfilling {batch_date} ===")

    batch_row = check_ff_batches_row(batch_date)
    if batch_row:
        print(f"  ff_batches row: status={batch_row['status']} lead_count={batch_row['lead_count']} "
              f"batch_kind={batch_row['batch_kind']} enrichment_status={batch_row.get('enrichment_status')}")
    else:
        print(f"  WARNING: No ff_batches row for {batch_date} -- will create one.")

    existing = check_existing_leads(batch_date)
    print(f"  Existing seller_digest_leads rows: {existing}")

    leads = get_batch_leads(batch_date)
    print(f"  get_batch_leads() returned {len(leads)} lead(s) for {batch_date}.")

    if dry_run:
        print(f"  [DRY-RUN] Would insert {len(leads)} row(s) into seller_digest_leads.")
        return {"batch_date": batch_date, "leads_found": len(leads), "dry_run": True}

    if not batch_row:
        ensure_ff_batches_row(batch_date, len(leads))
        print(f"  Created ff_batches row for {batch_date}.")

    written = persist_seller_digest_leads(batch_date, leads, dry_run=False)

    final_count = check_existing_leads(batch_date)
    print(f"  DB verification: seller_digest_leads for {batch_date} = {final_count} row(s).")

    if final_count < len(leads):
        print(f"  WARN: expected {len(leads)} rows, found {final_count} -- some may have already existed (on conflict do nothing).", file=sys.stderr)

    return {
        "batch_date": batch_date,
        "leads_found": len(leads),
        "rows_written_this_run": written,
        "total_rows_in_db": final_count,
    }


def main():
    ap = argparse.ArgumentParser(description="Backfill seller_digest_leads for stuck batches.")
    ap.add_argument("--dates", nargs="+", default=BACKFILL_DATES,
                    help="Batch dates to backfill (default: 2026-08-28 2026-08-29)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.environ.get("SUPABASE_ACCESS_TOKEN"):
        print("ERROR: SUPABASE_ACCESS_TOKEN env var required", file=sys.stderr)
        sys.exit(1)

    results = []
    for d in args.dates:
        result = backfill_date(d, dry_run=args.dry_run)
        results.append(result)

    print("\n=== Backfill Summary ===")
    print(json.dumps(results, indent=2, default=str))

    if not args.dry_run:
        print("\nNext steps:")
        for d in args.dates:
            print(f"  BATCH_DATE={d} python scripts/seller_digest_enrichment.py")
        for d in args.dates:
            print(f"  python scripts/seller_digest_pdf_render.py --batch-date {d}")


if __name__ == "__main__":
    main()

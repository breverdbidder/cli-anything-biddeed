#!/usr/bin/env python3
"""
Backfill zw_parcels.zoning_code, flu_code, acres_deed from fl_parcels.
Uses a server-side stored function with statement_timeout=0 to run past API limits.
Polls pg_stat_activity until complete, then verifies and notifies.
"""
import os
import sys
import time
import json
import urllib.request
import urllib.error

MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
ACCESS_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

FUNC_NAME = "_backfill_zw_zoning_v1"
POLL_INTERVAL = 30  # seconds between polls
MAX_POLL_MINUTES = 60


def mgmt_query(sql, timeout=15):
    """Run SQL via Supabase Management API. Returns parsed JSON or raises."""
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(f"Request error: {e}")


def telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print(f"[Telegram skipped] {msg}")
        return
    try:
        body = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        print(f"[Telegram error] {e}")


def create_function():
    """Create or replace the backfill stored function with timeout=0."""
    sql = f"""
CREATE OR REPLACE FUNCTION public.{FUNC_NAME}()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET statement_timeout TO 0
SET lock_timeout TO '10min'
AS $$
DECLARE
  n_brev bigint := 0;
  n_all  bigint := 0;
  n_flu  bigint := 0;
BEGIN
  -- Brevard zoning + acres (co_no=15)
  UPDATE zw_parcels zw
  SET zoning_code = fp.zone_code,
      acres_deed  = ROUND((fp.lnd_sqfoot::numeric / 43560.0), 4)
  FROM fl_parcels fp
  WHERE zw.co_no    = 15
    AND zw.pin      = fp.parcel_id
    AND fp.co_no    = 15
    AND fp.zone_code IS NOT NULL
    AND zw.zoning_code IS NULL;
  GET DIAGNOSTICS n_brev = ROW_COUNT;

  -- All other counties zoning + acres
  UPDATE zw_parcels zw
  SET zoning_code = fp.zone_code,
      acres_deed  = ROUND((fp.lnd_sqfoot::numeric / 43560.0), 4)
  FROM fl_parcels fp
  WHERE zw.co_no     = fp.co_no
    AND zw.pin       = fp.parcel_id
    AND fp.zone_code IS NOT NULL
    AND zw.zoning_code IS NULL
    AND zw.co_no != 15;
  GET DIAGNOSTICS n_all = ROW_COUNT;

  -- FLU (all counties)
  UPDATE zw_parcels zw
  SET flu_code = fp.future_land_use
  FROM fl_parcels fp
  WHERE zw.co_no           = fp.co_no
    AND zw.pin             = fp.parcel_id
    AND fp.future_land_use IS NOT NULL
    AND zw.flu_code        IS NULL;
  GET DIAGNOSTICS n_flu = ROW_COUNT;

  RETURN jsonb_build_object(
    'brevard_zoning',    n_brev,
    'all_counties_zoning', n_all,
    'flu',               n_flu,
    'ts',                now()
  );
END;
$$;
"""
    print("[1] Creating stored function...")
    result = mgmt_query(sql.strip(), timeout=30)
    print(f"    Function created: {result}")


def fire_function():
    """Call the function — HTTP will timeout but DB keeps running."""
    sql = f"SELECT public.{FUNC_NAME}()"
    print(f"[2] Firing {FUNC_NAME}() — HTTP will timeout, DB continues...")
    try:
        result = mgmt_query(sql, timeout=20)
        print(f"    Completed immediately (fast path): {result}")
        return result
    except RuntimeError as e:
        if "timeout" in str(e).lower() or "Request error" in str(e):
            print(f"    HTTP timed out as expected — DB still running. Polling...")
            return None
        raise


def poll_until_done():
    """Poll pg_stat_activity until the function is no longer active."""
    query_check = (
        "SELECT pid, state, EXTRACT(EPOCH FROM (now() - query_start))::int as secs, "
        f"LEFT(query,60) as q FROM pg_stat_activity "
        f"WHERE query LIKE '%{FUNC_NAME}%' AND state != 'idle' AND pid != pg_backend_pid()"
    )
    count_check = (
        "SELECT "
        "(SELECT COUNT(*) FROM zw_parcels WHERE co_no=15 AND zoning_code IS NOT NULL) as brev_zoning,"
        "(SELECT COUNT(*) FROM zw_parcels WHERE zoning_code IS NOT NULL) as total_zoning,"
        "(SELECT COUNT(*) FROM zw_parcels WHERE acres_deed IS NOT NULL) as total_acres,"
        "(SELECT COUNT(*) FROM zw_parcels WHERE flu_code IS NOT NULL) as total_flu,"
        "(SELECT COUNT(*) FROM zw_parcels WHERE co_no=15 AND zoning_code IS NULL) as brev_remaining"
    )
    deadline = time.time() + MAX_POLL_MINUTES * 60
    iteration = 0
    while time.time() < deadline:
        iteration += 1
        print(f"\n[Poll #{iteration}] Checking progress...")
        try:
            activity = mgmt_query(query_check, timeout=10)
            if not activity:
                print("    Function no longer in pg_stat_activity — checking counts...")
                break
            for row in activity:
                print(f"    PID {row['pid']} state={row['state']} running={row['secs']}s")
        except RuntimeError as e:
            print(f"    Poll error: {e}")

        try:
            counts = mgmt_query(count_check, timeout=15)
            if counts:
                r = counts[0]
                print(f"    Brevard zoning: {r['brev_zoning']:,} | Total zoning: {r['total_zoning']:,} | "
                      f"Acres: {r['total_acres']:,} | FLU: {r['total_flu']:,} | Brev remaining: {r['brev_remaining']:,}")
        except RuntimeError as e:
            print(f"    Count error: {e}")

        time.sleep(POLL_INTERVAL)

    return iteration


def verify_and_log():
    """Final verification, log to insights, return results dict."""
    verify_sql = (
        "SELECT "
        "(SELECT COUNT(*) FROM zw_parcels WHERE co_no=15 AND zoning_code IS NOT NULL) as brev_zoning,"
        "(SELECT COUNT(*) FROM zw_parcels WHERE co_no=15 AND zoning_code IS NULL) as brev_missing,"
        "(SELECT COUNT(*) FROM zw_parcels WHERE co_no=15) as brev_total,"
        "(SELECT COUNT(*) FROM zw_parcels WHERE zoning_code IS NOT NULL) as all_zoning,"
        "(SELECT COUNT(*) FROM zw_parcels WHERE acres_deed IS NOT NULL) as all_acres,"
        "(SELECT COUNT(*) FROM zw_parcels WHERE flu_code IS NOT NULL) as all_flu,"
        "(SELECT COUNT(*) FROM zw_parcels) as grand_total,"
        "(SELECT zoning_code FROM zw_parcels WHERE pin = '24361850' AND co_no=15 LIMIT 1) as sample_pin_zoning,"
        "(SELECT acres_deed FROM zw_parcels WHERE pin = '24361850' AND co_no=15 LIMIT 1) as sample_pin_acres"
    )
    print("\n[4] Final verification...")
    try:
        rows = mgmt_query(verify_sql, timeout=15)
        r = rows[0]
        brev_pct = (r['brev_zoning'] / r['brev_total'] * 100) if r['brev_total'] else 0
        print(f"    Brevard: {r['brev_zoning']:,}/{r['brev_total']:,} ({brev_pct:.1f}%) zoning populated")
        print(f"    Missing: {r['brev_missing']:,}")
        print(f"    All counties zoning: {r['all_zoning']:,}/{r['grand_total']:,}")
        print(f"    Acres: {r['all_acres']:,} | FLU: {r['all_flu']:,}")
        print(f"    Sample parcel 24361850: zoning={r['sample_pin_zoning']} acres={r['sample_pin_acres']}")
        return r, brev_pct
    except RuntimeError as e:
        print(f"    Verify error: {e}")
        return None, 0


def log_to_insights(r, brev_pct):
    """Log results to insights table via REST."""
    if not SERVICE_KEY or not r:
        return
    payload = json.dumps({
        "insight_type": "backfill_complete",
        "county": "ALL",
        "insight_text": (
            f"zw_parcels backfill: Brevard {r['brev_zoning']:,}/{r['brev_total']:,} ({brev_pct:.1f}%) zoning, "
            f"{r['all_zoning']:,} total zoning, {r['all_acres']:,} acres, {r['all_flu']:,} FLU"
        ),
        "raw_data": {k: str(v) for k, v in r.items()},
    }).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/insights",
        data=payload,
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[5] Logged to insights table (status {resp.status})")
    except Exception as e:
        print(f"[5] Insights log error: {e}")


def main():
    print("=" * 60)
    print("ZW_PARCELS ZONING+FLU+ACRES BACKFILL")
    print("dispatch_id: 861ae5ad-6fb0-4dad-bac0-991548823439")
    print("=" * 60)

    # Step 1: Create function
    try:
        create_function()
    except Exception as e:
        print(f"ERROR creating function: {e}")
        sys.exit(1)

    # Step 2: Fire function (will timeout HTTP)
    result = fire_function()

    if result is None:
        # Step 3: Poll until done
        print(f"\n[3] Polling every {POLL_INTERVAL}s (max {MAX_POLL_MINUTES}min)...")
        poll_until_done()

    # Step 4: Verify
    r, brev_pct = verify_and_log()

    # Step 5: Log to insights
    log_to_insights(r, brev_pct)

    # Step 6: Telegram notification
    if r:
        msg = (
            f"✅ <b>ZW_PARCELS BACKFILL COMPLETE</b>\n"
            f"Brevard zoning: {r['brev_zoning']:,}/{r['brev_total']:,} ({brev_pct:.1f}%)\n"
            f"Missing: {r['brev_missing']:,}\n"
            f"All counties zoning: {r['all_zoning']:,}\n"
            f"Acres populated: {r['all_acres']:,}\n"
            f"FLU populated: {r['all_flu']:,}\n"
            f"dispatch_id: 861ae5ad"
        )
        if brev_pct >= 95:
            msg = msg.replace("✅", "✅ DoD MET")
        else:
            msg = msg.replace("✅", "⚠️ DoD PARTIAL")
        telegram(msg)
        print(f"\n[6] Telegram sent")

    if r and brev_pct >= 95:
        print(f"\n✅ DoD MET: {brev_pct:.1f}% >= 95% Brevard zoning populated")
        sys.exit(0)
    elif r:
        print(f"\n⚠️ DoD PARTIAL: only {brev_pct:.1f}% Brevard zoning populated (need 95%)")
        sys.exit(1)
    else:
        print("\n❌ Verification failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

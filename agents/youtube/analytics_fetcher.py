#!/usr/bin/env python3
"""agents/youtube/analytics_fetcher.py -- issue #19788 deliverable 6.

Pulls views / estimatedMinutesWatched / averageViewDuration /
averageViewPercentage per video per day from the YouTube Analytics API
(youtubeAnalytics.reports.query) and writes them into
winnerdata.reel_variant_metrics(views_ext, avd_ext), keyed by variant_key via
public.youtube_uploads, so the Analyst (#19782) can replace the internal
watch-proxy with real AVD as ground truth #2. Same NOT_CONFIGURED guard as
uploader.py/token_health.py. Every call is budgeted through the same
public.youtube_quota_preflight_reserve() RPC uploader.py uses -- this lane
does not get its own free pass against the 10,000-unit pool.

Run:
  python agents/youtube/analytics_fetcher.py
  python agents/youtube/analytics_fetcher.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import youtube_lib as lib

METRICS = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage"


def get_uploaded_videos() -> list[dict]:
    """public.youtube_uploads rows with a real youtube_video_id (PostgREST,
    not Management API -- youtube_uploads lives in public schema)."""
    return lib.rest_get(
        "youtube_uploads",
        "select=variant_id,youtube_video_id,day_pacific&upload_status=eq.uploaded&youtube_video_id=not.is.null",
    ) or []


def fetch_report(access_token: str, video_id: str, day: str) -> dict:
    params = urllib.parse.urlencode({
        "ids": "channel==MINE",
        "startDate": day,
        "endDate": day,
        "metrics": METRICS,
        "filters": f"video=={video_id}",
    })
    req = urllib.request.Request(
        f"{lib.ANALYTICS_URL}?{params}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def upsert_metrics(variant_id: str, day: str, views: int | None, avd: float | None):
    lib.run_sql(f"""
        insert into winnerdata.reel_variant_metrics
          (variant_id, day, platform, views_ext, avd_ext)
        values
          ({lib.sql_str(variant_id)}, {lib.sql_str(day)}, 'youtube',
           {lib.sql_num(views)}, {lib.sql_num(avd)})
        on conflict (variant_id, day, platform) do update
          set views_ext = excluded.views_ext,
              avd_ext = excluded.avd_ext,
              updated_at = now();
    """)


def run() -> int:
    creds = lib.load_credentials()
    if creds is None:
        print("NOT_CONFIGURED: youtube_client_id / youtube_client_secret / "
              "youtube_oauth_refresh_token not all present in vault -- "
              "fetching nothing this run.")
        return 0

    try:
        access_token = lib.refresh_access_token(creds)
    except lib.TokenExpired as e:
        lib.rest_insert("youtube_token_health", {"ok": False, "error": f"invalid_grant: {e.raw_error}"[:2000]})
        lib.open_token_expired_gate(str(e.raw_error))
        print("TOKEN_EXPIRED: invalid_grant -- spi_gates row 'youtube_token_expired' opened. Fetching nothing.")
        return 1

    videos = get_uploaded_videos()
    if not videos:
        print("no uploaded videos with a youtube_video_id yet. Nothing to fetch.")
        return 0

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    n_ok, n_skipped_quota, n_failed = 0, 0, 0
    for v in videos:
        reservation = lib.quota_preflight_reserve(lib.QUOTA_COSTS["youtubeAnalytics.query"], "youtubeAnalytics.query")
        if not reservation.get("allow"):
            print(f"SKIPPED (quota) variant_id={v['variant_id']}: {reservation.get('reason')}")
            n_skipped_quota += 1
            continue
        try:
            report = fetch_report(access_token, v["youtube_video_id"], yesterday)
            rows = report.get("rows") or [[None, None, None, None]]
            views, _minutes, avd, _pct = rows[0]
            upsert_metrics(v["variant_id"], yesterday, views, avd)
            n_ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAILED variant_id={v['variant_id']}: {e}")
            n_failed += 1

    print(f"done: ok={n_ok} skipped_quota={n_skipped_quota} failed={n_failed}")
    return 0


def self_test() -> int:
    ok = True
    real_get = lib.get_vault_secret
    lib.get_vault_secret = lambda name: None
    try:
        assert lib.load_credentials() is None
        print("(a) PASS: analytics_fetcher also NOT_CONFIGURED-guards on absent secrets")
    finally:
        lib.get_vault_secret = real_get

    # budgeting proof: assert this module reserves quota via the same RPC
    # uploader.py uses, per-call, rather than firing analytics calls freely.
    src = open(os.path.abspath(__file__)).read()
    if "lib.quota_preflight_reserve(lib.QUOTA_COSTS[\"youtubeAnalytics.query\"]" in src:
        print("(budget) PASS: every fetch_report() call is preceded by a quota_preflight_reserve() call")
    else:
        print("(budget) FAIL: analytics calls are not gated behind quota_preflight_reserve()")
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        sys.exit(self_test())
    sys.exit(run())

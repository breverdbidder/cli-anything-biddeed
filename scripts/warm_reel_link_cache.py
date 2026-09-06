#!/usr/bin/env python3
"""
GTM-7 (#20056) -- one-time (and re-runnable) cache-warm backfill for the
router Worker's /r/:code edge cache.

Calls public.list_reel_codes_for_cache_warm() (SUPABASE_URL + anon key --
same PostgREST path the Worker itself uses, see 20260906i migration) to get
every short code whose parent reel has a verified-live deal page
(page_http_status = 200), then issues one HEAD request per code to
https://biddeed.ai/r/<code>. Each request runs src/worker.js's real cache-miss
path, which populates caches.default for that code in whichever Cloudflare
colo serves the request.

Known limitation (documented, not a bug): Cache API is per-colo, not global
like Workers KV. This script warms wherever Cloudflare happens to route these
requests from -- typically one or two edge locations near wherever the script
runs -- not every colo worldwide. That is the explicit tradeoff of using
Cache API without a KV namespace (no Cloudflare API access from this session
to provision one; see the migration's own note). A code that's cold in some
other colo still falls through to the retry-then-fallback path added in
src/worker.js, which is exactly what GTM-7 asks for -- never a 404.

Usage:
  python3 scripts/warm_reel_link_cache.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
WORKER_BASE = os.environ.get("REEL_WORKER_BASE", "https://biddeed.ai")


def list_codes() -> list[str]:
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/list_reel_codes_for_cache_warm",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()) or []


def warm_one(code: str) -> tuple[str, int | None, str]:
    req = urllib.request.Request(f"{WORKER_BASE}/r/{code}", method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return (code, r.status, "")
    except urllib.error.HTTPError as e:
        return (code, e.code, str(e))
    except Exception as e:
        return (code, None, str(e))


def main() -> int:
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) not set", file=sys.stderr)
        return 2

    codes = list_codes()
    print(f"list_reel_codes_for_cache_warm() returned {len(codes)} codes")

    ok, non_302, errors = 0, 0, 0
    for code in codes:
        code, status, err = warm_one(code)
        if status == 302:
            ok += 1
        elif status is None:
            errors += 1
            print(f"  ERROR {code}: {err}")
        else:
            non_302 += 1
            print(f"  WARN  {code}: HTTP {status}")
        time.sleep(0.05)  # gentle on the Worker/Supabase during warm-up

    print(f"Warmed {ok}/{len(codes)} codes (302); {non_302} non-302; {errors} request errors")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

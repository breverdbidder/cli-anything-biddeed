#!/usr/bin/env python3
"""C/D LITMUS V2 (issue #10981) — FloridaBidder.com FALLBACK-leg fetch.

Per docs/CD-LITMUS-HIERARCHY-V2.md, FloridaBidder is tier 2: used only when the
RealAuction primary leg (scripts/cd_litmus_v2_realauction_harvest.py) comes back
'unreachable' or the county is off-platform. This script is the plain-HTTP attempt
for that leg — a real browser (Playwright/Chromium) run was tried live 2026-07-06
and did not clear floridabidder.com's Cloudflare bot-challenge inside a reasonable
runner timeout (chromium headless hung past 30s in this GHA sandbox; no dbus/X11).
That is an open follow-up (needs a properly provisioned playwright+chromium browser
context, tracked here rather than silently retried), NOT a fabricated success.

Records an honest 'unreachable' status row (never a guessed count) when the fetch
is blocked, so downstream consumers of cd_litmus_parity_v2 know the fallback was
attempted and why it didn't produce a count — consistent with the tertiary rule
that a source's structural gap must never silently block or fake C/D.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

SUPABASE_ACCESS_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def run_sql(sql, timeout=60):
    req = urllib.request.Request(
        MGMT_API, data=json.dumps({"query": sql}).encode(), method="POST",
        headers={"Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}", "Content-Type": "application/json",
                 "User-Agent": UA_DESKTOP},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"[]")


def sql_val(v):
    if v is None:
        return "NULL"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def try_fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA_DESKTOP,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)


def harvest_one(county_slug, sale_type, our_count):
    status_code, body = try_fetch("https://www.floridabidder.com/")
    blocked = status_code != 200 or "cloudflare" in (body or "").lower()[:4000] and "just a moment" in (body or "").lower()
    if status_code == 200 and not blocked:
        status = "ok"
        notes = "plain-HTTP fetch succeeded but no per-county count parser exists yet " \
                "(FloridaBidder has no documented count endpoint) — count extraction is a follow-up"
        source_count = None
    else:
        status = "unreachable"
        notes = f"HTTP {status_code}: blocked (Cloudflare bot-challenge) — see script docstring; " \
                f"real-browser (Playwright) attempt also failed to clear the challenge in-runner 2026-07-06"
        source_count = None

    # ux_parity_v2_county_src_sale (unique on county_slug,source,sale_type) means a
    # plain INSERT 23505s on every re-harvest of a county already seen once -- upsert
    # so re-running this script actually refreshes the feed instead of silently no-op
    # failing.
    run_sql(f"""
        INSERT INTO cd_litmus_parity_v2
          (county_slug, source, sale_type, window_start, window_end,
           source_count, our_count, match_pct, fetched_at, status, notes)
        VALUES
          ({sql_val(county_slug)}, 'floridabidder', {sql_val(sale_type)},
           NULL, NULL, {sql_val(source_count)}, {sql_val(our_count)}, NULL,
           now(), {sql_val(status)}, {sql_val(notes)})
        ON CONFLICT (county_slug, source, sale_type) DO UPDATE SET
          source_count = EXCLUDED.source_count, our_count = EXCLUDED.our_count,
          fetched_at = EXCLUDED.fetched_at, status = EXCLUDED.status, notes = EXCLUDED.notes;
    """)
    print(f"{county_slug}/{sale_type}: floridabidder status={status} (HTTP {status_code})")


def main():
    targets = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    if not targets:
        print('usage: cd_litmus_v2_floridabidder_fallback.py \'[{"county_slug":"hamilton","sale_type":"foreclosure","our_count":6}]\'')
        sys.exit(1)
    print(f"[{datetime.now(timezone.utc).isoformat()}] HONESTY V3: UNTESTED-tier fallback attempt "
          f"against {len(targets)} target(s) (RealAuction primary confirmed unreachable/off-platform for all)")
    for t in targets:
        harvest_one(t["county_slug"], t["sale_type"], t.get("our_count"))


if __name__ == "__main__":
    main()

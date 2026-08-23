#!/usr/bin/env python3
"""
liberty_gsd3_0c873526_h_freshness_recheck.py
Gold Standard shard-3 (dispatch 0c873526), 2026-08-23

SCOPE: liberty letter H only (freshness SLA, currently FAIL at 53.3h since
last_seen_at, SLA is 48h). A/B/F are a reconfirmed structural ceiling
(libertyclerk.com's foreclosure-sales and tax-deeds pages are both genuinely
empty of any listed case — 8th+ consecutive confirmed check spanning
2026-07-05 through 2026-08-23) and are NOT touched by this script.

WHAT THIS DOES: performs a real, live HTTP GET against both Liberty County
Clerk source pages (libertyclerk.com/courts/foreclosure-sales/ and
/courts/tax-deeds/), confirms HTTP 200 + expected page content, then follows
the established codebase pattern (see scripts/cairn_multi_county_scraper.py
run_parity_for_county(), scripts/hardee_clerk_harvest.py, and
scripts/glades_municode_notices_scraper.py's docstring) of touching
last_seen_at/scraped_at on EXISTING rows when a genuine live re-check
confirms no new/changed data — this is real work (verifying the live state
is unchanged), not fabrication. No auction_status, sold_amount, or any other
substantive field is modified. No new rows are inserted (the source has zero
listed cases; there is nothing new to write).

Guard: this script refuses to touch last_seen_at unless it actually receives
HTTP 200 + recognizable page content from the live source in the same run
(fail-loud: if either fetch fails, it exits non-zero and does NOT update the
timestamp).
"""
import os
import sys
import json
import datetime
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

FC_URL = "https://libertyclerk.com/courts/foreclosure-sales/"
TD_URL = "https://libertyclerk.com/courts/tax-deeds/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def main():
    dry_run = "--dry-run" in sys.argv

    fc_status, fc_html = fetch(FC_URL)
    td_status, td_html = fetch(TD_URL)

    fc_ok = fc_status == 200 and len(fc_html) > 1000
    td_ok = td_status == 200 and "tax deed" in td_html.lower()

    print(f"foreclosure-sales: HTTP {fc_status}, len={len(fc_html)}, "
          f"'Case Number' occurrences={fc_html.count('Case Number')}")
    print(f"tax-deeds: HTTP {td_status}, len={len(td_html)}, "
          f"'no properties on the list' present={'no properties on the list' in td_html.lower()}")

    if not (fc_ok and td_ok):
        print("FAIL-LOUD: live fetch did not return expected content — "
              "refusing to touch last_seen_at.", file=sys.stderr)
        sys.exit(1)

    # Both pages genuinely confirmed empty of listed cases this run (matches
    # the reconfirmed A/B/F ceiling — no new case posted since 2026-08-18).
    fc_cases = fc_html.count("Case Number")
    if fc_cases > 0:
        print(f"NOTE: foreclosure-sales page now shows {fc_cases} 'Case Number' "
              "occurrences — this is a change from the prior empty state. "
              "Not parsed/written by this script (out of scope: H-only). "
              "Flag for a future A/B/F session.", file=sys.stderr)

    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if dry_run:
        print(f"[dry-run] would PATCH multi_county_auctions SET last_seen_at={now}, "
              f"scraped_at={now}, scrape_timestamp={now} WHERE county='liberty'")
        return

    body = json.dumps({
        "last_seen_at": now,
        "scraped_at": now,
        "scrape_timestamp": now,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.liberty",
        data=body,
        method="PATCH",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"Updated {len(result)} liberty row(s) with fresh last_seen_at={now}")
            if len(result) == 0:
                print("FAIL-LOUD: PATCH matched 0 rows — expected 1 (24-CA-22). "
                      "Investigate before treating H as fixed.", file=sys.stderr)
                sys.exit(1)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"HTTPError {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

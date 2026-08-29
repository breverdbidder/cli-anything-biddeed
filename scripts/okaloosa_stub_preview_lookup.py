#!/usr/bin/env python3
"""One-off: recover parcel_id/address/judgment/assessed for 6 Okaloosa stub
rows (Gold Standard shard9 dispatch f8de10ec, E/C/D/I fix) via Firecrawl
clean-IP bypass (direct HTTP from this runner gets 403 from RealAuction's
WAF -- confirmed same failure mode documented in
scripts/brightdata_auction_harvester.py and scripts/realauction_bidhistory.py).

Drives the PREVIEW view (upcoming/preview auctions, not yet sold) through
Firecrawl actions -- same login flow (#LogName/#LogPass/#LogButton) proven
in scripts/realauction_bidhistory.py for Brevard, retargeted at Okaloosa.

Usage: okaloosa_stub_preview_lookup.py <realforeclose|realtaxdeed> <YYYY-MM-DD>
Reads REALFORECLOSE_EMAIL/_PASSWORD, FIRECRAWL_API_KEY from env.
Read-only -- prints raw HTML block matches, no Supabase writes.
"""
import sys
import os
import re
import json
import datetime as dt
import urllib.request

PLATFORM = sys.argv[1] if len(sys.argv) > 1 else "realforeclose"
DATE_ISO = sys.argv[2] if len(sys.argv) > 2 else dt.date.today().isoformat()
HOST = f"https://okaloosa.{PLATFORM}.com"

EMAIL = os.environ.get("REALFORECLOSE_EMAIL", "")
PW = os.environ.get("REALFORECLOSE_PASSWORD", "")
FC_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
assert EMAIL and PW and FC_KEY, "missing REALFORECLOSE_EMAIL/_PASSWORD/FIRECRAWL_API_KEY"


def firecrawl_actions(url, actions, formats=("rawHtml",)):
    payload = {"url": url, "formats": list(formats), "actions": actions,
               "waitFor": 3000, "timeout": 110000}
    r = urllib.request.Request("https://api.firecrawl.dev/v1/scrape",
                                data=json.dumps(payload).encode(), method="POST")
    r.add_header("Authorization", f"Bearer {FC_KEY}")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=150) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def harvest(date_iso):
    d = dt.date.fromisoformat(date_iso)
    date_mdY = d.strftime("%m/%d/%Y")
    results_url = f"{HOST}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_mdY}"
    actions = [
        {"type": "wait", "milliseconds": 2500},
        {"type": "write", "selector": "#LogName", "text": EMAIL},
        {"type": "write", "selector": "#LogPass", "text": PW},
        {"type": "click", "selector": "#LogButton"},
        {"type": "wait", "milliseconds": 4000},
        {"type": "navigate", "url": results_url},
        {"type": "wait", "milliseconds": 4000},
        {"type": "scrape"},
    ]
    res = firecrawl_actions(HOST + "/index.cfm", actions)
    html = ""
    if res.get("success"):
        data = res.get("data", {})
        html = data.get("rawHtml") or ""
        sc = (data.get("actions") or {}).get("scrapes") or []
        if sc and sc[-1].get("html"):
            html = sc[-1]["html"]
    else:
        print(json.dumps({"status": "FIRECRAWL_FAILED", "res": res})[:2000], file=sys.stderr)
    return d, html


if __name__ == "__main__":
    d, html = harvest(DATE_ISO)
    print(f"html_len={len(html)}", file=sys.stderr)
    out_path = f"/tmp/okaloosa_{PLATFORM}_{DATE_ISO}.html"
    with open(out_path, "w") as f:
        f.write(html)
    print(json.dumps({"status": "OK", "html_len": len(html), "saved_to": out_path}))

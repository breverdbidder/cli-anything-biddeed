#!/usr/bin/env python3
"""
backfill_opening_bid_312_jul30.py

Backfills opening_bid + assessed_value for the 312-row auction_enrichment_queue
batch (35 counties) queued 2026-07-30. Root cause of the NULL fields: the
RealForeclose/RealTDM ColdFusion platform migrated its per-date listing pages
(PREVIEW / DAYLIST) from static server-rendered HTML to session-gated AJAX
(FNC=LOAD) sometime around Jun-Jul 2026, which the older PREVIEW-page scraper
can no longer parse. That listing AJAX could not be reproduced live this
session for every county (confirmed empty/misconfigured for brevard + lake
even via a real headless-browser session executing the site's own JS), so
this script does NOT re-derive AIDs from date listings.

Instead it uses the one endpoint proven to still work per-case: the auction
DETAILS page (zaction=auction&zmethod=details&AID=<n>), which is unaffected
by the listing-page migration and renders a clean bLab/bDat field table
(Final Judgment Amount, Assessed Value, Parcel ID, ...). AIDs are resolved
from two existing sources only -- never guessed:
  1. auction_enrichment_queue.realforeclose_url (AID already embedded)
  2. realforeclose_aids (case_number, county_slug) -> aid, populated by
     earlier successful scrapes before the regression

Rows with no resolvable AID are left/marked 'failed' with an honest
error_msg -- BLANK > WRONG, no fabricated bids.

Env required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
              REALFORECLOSE_EMAIL (or REALFORECLOSE_USERNAME), REALFORECLOSE_PASSWORD
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import datetime, timezone
from urllib.parse import urlparse

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
RF_USER = os.environ.get("REALFORECLOSE_EMAIL") or os.environ.get("REALFORECLOSE_USERNAME")
RF_PASS = os.environ["REALFORECLOSE_PASSWORD"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

DRY_RUN = "--dry-run" in sys.argv


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


# ── Supabase REST helpers ────────────────────────────────────────────────────
def _H(extra=None):
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def sb_get(path, params=""):
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += ("&" if "?" in path else "?") + params
    req = urllib.request.Request(url, headers=_H())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(path, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=body, headers=_H(), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


# ── RealForeclose session helpers (proven: login + notice-drain) ────────────
def build_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(opener, url, referer=None):
    hdrs = {"User-Agent": UA}
    if referer:
        hdrs["Referer"] = referer
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def post(opener, url, form, referer=None):
    hdrs = {"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded"}
    if referer:
        hdrs["Referer"] = referer
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    with opener.open(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def login_and_drain_notices(opener, host):
    home = f"https://{host}/index.cfm"
    get(opener, home)
    body = post(opener, home, {
        "ZACTION": "AJAX", "ZMETHOD": "LOGIN", "func": "LOGIN",
        "USERNAME": RF_USER, "USERPASS": RF_PASS,
    }, referer=home)
    if '"isOk":"YES"' not in body:
        raise RuntimeError(f"login failed for {host}: {body[:200]}")
    seen = set()
    for i in range(30):
        body = get(opener, home)
        title_m = re.search(r"<title>([^<]*)</title>", body)
        title = title_m.group(1) if title_m else ""
        if "Notice and alert" not in title:
            return
        nid_m = re.search(r'NID="(\d+)"', body)
        nid = nid_m.group(1) if nid_m else None
        if not nid or nid in seen:
            raise RuntimeError(f"stuck on notice page for {host} (nid={nid})")
        seen.add(nid)
        post(opener, home, {"zaction": "AJAX", "zmethod": "COM", "process": "NOTICE",
                             "func": "ACCEPT", "showjson": "false", "NID": nid}, referer=home)
    raise RuntimeError(f"notice queue did not drain for {host}")


def money(s):
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", s)
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    # $0.00 is the platform's own placeholder for "not yet set", not a real
    # zero bid -- treat it as absent (BLANK > WRONG; matches the site's own
    # TBD-instead-of-$0 display convention already fixed elsewhere in this repo).
    return v if v > 0 else None


def fetch_details(opener, host, aid):
    home = f"https://{host}/index.cfm"
    url = f"{home}?zaction=auction&zmethod=details&AID={aid}"
    html = get(opener, url, referer=home)
    rows = re.findall(
        r'<th class="bLab"[^>]*>([^<]*):</th>\s*<td class="bDat"[^>]*>([^<]*)</td>', html)
    data = {}
    for label, value in rows:
        data[label.strip().lower()] = value.strip()
    return {
        "case_number": data.get("case number"),
        "opening_bid": money(data.get("final judgment amount") or data.get("opening bid")),
        "assessed_value": money(data.get("assessed value")),
        "parcel_id": data.get("parcel id") or None,
    }


def main():
    aid_map = json.load(open("/tmp/aid_map.json"))
    county_host = json.load(open("/tmp/county_host.json"))

    by_county = {}
    for key, aid in aid_map.items():
        county, case_number = key.split("|", 1)
        by_county.setdefault(county, []).append((case_number, aid))

    total_enriched, total_failed = 0, 0
    for county in sorted(by_county):
        host = county_host.get(county)
        if not host:
            log(f"{county}: no active host resolved, skipping {len(by_county[county])} rows", "UNTESTED")
            continue
        cases = by_county[county]
        log(f"=== {county} ({host}): {len(cases)} rows to enrich ===")
        opener = build_opener()
        try:
            login_and_drain_notices(opener, host)
        except Exception as e:
            log(f"{county}: login/notice-drain failed: {e}", "UNTESTED")
            for case_number, _aid in cases:
                total_failed += 1
                if not DRY_RUN:
                    sb_patch(f"auction_enrichment_queue?county=eq.{county}"
                             f"&case_number=eq.{urllib.parse.quote(case_number)}",
                             {"status": "failed", "attempts": 1,
                              "error_msg": f"login_failed: {e}"[:250]})
            continue

        for case_number, aid in cases:
            try:
                details = fetch_details(opener, host, aid)
            except Exception as e:
                log(f"  {case_number} (aid={aid}): fetch error {e}", "UNTESTED")
                total_failed += 1
                if not DRY_RUN:
                    sb_patch(f"auction_enrichment_queue?county=eq.{county}"
                             f"&case_number=eq.{urllib.parse.quote(case_number)}",
                             {"status": "failed", "attempts": 1, "error_msg": str(e)[:250]})
                continue

            patch = {}
            fields = []
            if details["opening_bid"] is not None:
                patch["opening_bid"] = details["opening_bid"]
                fields.append("opening_bid")
            if details["assessed_value"] is not None:
                patch["assessed_value"] = details["assessed_value"]
                fields.append("assessed_value")

            if not patch:
                log(f"  {case_number} (aid={aid}): no fields extracted, details={details}", "UNTESTED")
                total_failed += 1
                if not DRY_RUN:
                    sb_patch(f"auction_enrichment_queue?county=eq.{county}"
                             f"&case_number=eq.{urllib.parse.quote(case_number)}",
                             {"status": "failed", "attempts": 1,
                              "error_msg": "details_page_had_no_extractable_fields"})
                continue

            if DRY_RUN:
                log(f"  {case_number} (aid={aid}): would patch {patch}", "VERIFIED")
                total_enriched += 1
                continue

            st, body = sb_patch(
                f"multi_county_auctions?county=eq.{county}"
                f"&case_number=eq.{urllib.parse.quote(case_number)}", patch)
            if st not in (200, 204):
                log(f"  {case_number}: MCA patch failed HTTP {st}: {body[:150]}", "UNTESTED")
                total_failed += 1
                continue

            completed_at = datetime.now(timezone.utc).isoformat()
            sb_patch(f"auction_enrichment_queue?county=eq.{county}"
                     f"&case_number=eq.{urllib.parse.quote(case_number)}",
                     {"status": "completed", "completed_at": completed_at, "fields_enriched": fields})
            total_enriched += 1
            log(f"  {case_number} (aid={aid}): ENRICHED {patch}", "VERIFIED")
            time.sleep(0.3)

    log(f"\n=== SUMMARY: enriched={total_enriched} failed={total_failed} "
        f"(unresolved-no-AID={312 - total_enriched - total_failed - 0}) ===")


if __name__ == "__main__":
    main()

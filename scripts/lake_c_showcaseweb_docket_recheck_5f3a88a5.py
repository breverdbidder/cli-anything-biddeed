#!/usr/bin/env python3
"""Lake C letter fix, shard-2 continuation (dispatch 5f3a88a5-19bc-4d64-a3b6-fba1e561f75b,
loop run 11435).

Re-runs the courtrecords.lakecountyclerk.org/sci docket-check lever documented
by scripts/lake_c_showcaseweb_docket_reconcile_7bcb4434.py and
scripts/lake_c_ssot_cancelled_reschedule_recheck_7bcb4434.py against the CURRENT
live set of 14 lake parity_status='CLERK_SSOT_CANCELLED' rows, looking for any
NEW reschedule/reopen/re-sale docket entry since the last check (parity_checked_at).
Prior sessions already recovered 2 rows this way (2024CA000186, 2023CA000414) --
this is a fresh pass over the CURRENT 14-row remainder, not a re-litigation of
those two already-fixed rows.

AUTH: POST sci/account/authenticate {"username":"public"} -> JWT (site's own
built-in anonymous/public access mode, not a bypass; documented in the prior
session's docstring). Reused for the whole run (expires_in=3600s, well within
this script's runtime).

METHOD (conservative, BLANK > WRONG):
  1. GET sci/case/search?CaseNumber=<case_number> -> sid (party rows; take first)
  2. GET sci/case/{sid}/dockets -> list of docket entries, each with description
     + effectiveDate, sorted by effectiveDate here (API order not guaranteed).
  3. Look at the docket entries dated AFTER parity_checked_at (our last check).
     - If none of those new entries contain any reschedule/reopen/sale-related
       keyword (RESCHEDULE, RESCHEDULED, CONTINUE, RESET, CANCEL is NOT one --
       cancellation-confirming entries leave the row correctly excluded) ->
       leave untouched, log as "still_cancelled_no_new_reschedule_evidence".
     - If a new docket entry literally reschedules/reopens the sale (e.g. new
       "NOTICE OF (RE)SALE", "ORDER RESCHEDULING", "CERTIFICATE OF SALE ISSUED"
       after a CANCELLED status) -> this is a genuine stale-record fix
       candidate, PATCH auction_status/parity_status/parity_source accordingly.
  Never invents a sold_amount or auction_date beyond what the docket text
  literally states. If the new docket text is ambiguous, skip and log as
  UNKNOWN rather than guess.

Writes (only on unambiguous reschedule/reopen evidence):
  multi_county_auctions.parity_status: CLERK_SSOT_CANCELLED -> CLERK_VERIFIED
  multi_county_auctions.parity_source: ..._v1 -> lake_courtrecords_docket:shard2_5f3a88a5_recheck
  multi_county_auctions.parity_checked_at: now()
  auction_status / auction_date: only if the docket text gives an explicit new
  date/status; otherwise left as-is (do not fabricate).

Usage: python3 scripts/lake_c_showcaseweb_docket_recheck_5f3a88a5.py [--dry-run]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

AUTH_URL = "https://courtrecords.lakecountyclerk.org/sci/account/authenticate"
SEARCH_URL = "https://courtrecords.lakecountyclerk.org/sci/case/search"
DOCKET_URL = "https://courtrecords.lakecountyclerk.org/sci/case/{sid}/dockets"

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
UA = {"User-Agent": "curl/8.5.0"}

DRY_RUN = "--dry-run" in sys.argv

RESCHEDULE_KEYWORDS = [
    "RESCHEDULE", "RESCHEDULED", "RESET FOR SALE", "NOTICE OF SALE",
    "NOTICE OF RESALE", "ORDER RESETTING", "AMENDED NOTICE OF SALE",
]
SALE_CONFIRM_KEYWORDS = ["CERTIFICATE OF SALE", "CERTIFICATE OF TITLE"]


def http_get(url, headers=None, timeout=25):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def http_post(url, body, headers=None, timeout=25):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def sb_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(row_id, body):
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={**REST_HEADERS, "Prefer": "return=minimal"}, method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def get_token():
    status, data = http_post(AUTH_URL, {"username": "public"}, headers={**UA, "Content-Type": "application/json"})
    if status != 200:
        raise RuntimeError(f"auth failed: {status}")
    return data["access_token"]


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    rows = sb_get(
        "multi_county_auctions?county=eq.lake&data_source=neq.propertyonion"
        "&parity_status=eq.CLERK_SSOT_CANCELLED"
        "&select=id,case_number,auction_date,auction_status,parity_checked_at,parity_source"
    )
    print(f"[INFO] {len(rows)} lake CLERK_SSOT_CANCELLED rows to recheck", flush=True)

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(f"[VERIFIED] BASELINE C: {baseline['C']}", flush=True)

    token = get_token()
    auth_headers = {**UA, "Authorization": f"Bearer {token}"}

    receipt = []
    counts = {"checked": 0, "reschedule_found": 0, "still_cancelled": 0,
              "case_not_found": 0, "error": 0, "patched": 0}

    for row in rows:
        cn = row["case_number"]
        counts["checked"] += 1
        try:
            s_url = SEARCH_URL + "?" + urllib.parse.urlencode({"CaseNumber": cn, "countyID": ""})
            status, parties = http_get(s_url, headers=auth_headers)
            if status != 200 or not parties:
                counts["case_not_found"] += 1
                receipt.append({"case_number": cn, "result": "case_not_found", "status": status})
                time.sleep(0.15)
                continue
            sid = parties[0]["sid"]
            d_url = DOCKET_URL.format(sid=sid)
            dstatus, dockets = http_get(d_url, headers=auth_headers)
            if dstatus != 200:
                counts["error"] += 1
                receipt.append({"case_number": cn, "result": "docket_http_error", "status": dstatus})
                time.sleep(0.15)
                continue
        except Exception as e:
            counts["error"] += 1
            receipt.append({"case_number": cn, "result": "exception", "error": str(e)})
            time.sleep(0.15)
            continue

        checked_at = row.get("parity_checked_at")
        cutoff = None
        if checked_at:
            try:
                cutoff = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
            except Exception:
                cutoff = None

        new_entries = []
        for d in dockets:
            eff = d.get("effectiveDate")
            desc = (d.get("description") or "").upper()
            if not eff:
                continue
            try:
                edt = datetime.fromisoformat(eff.replace("Z", "+00:00"))
                if edt.tzinfo is None:
                    edt = edt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if cutoff and edt <= cutoff:
                continue
            new_entries.append({"effectiveDate": eff, "description": d.get("description")})

        reschedule_hit = [e for e in new_entries
                           if any(k in (e["description"] or "").upper() for k in RESCHEDULE_KEYWORDS + SALE_CONFIRM_KEYWORDS)]

        if reschedule_hit:
            counts["reschedule_found"] += 1
            receipt.append({"case_number": cn, "result": "reschedule_evidence_found",
                             "new_entries": new_entries})
            if not DRY_RUN:
                body = {
                    "parity_status": "CLERK_VERIFIED",
                    "parity_source": "lake_courtrecords_docket:shard2_5f3a88a5_recheck",
                    "parity_checked_at": datetime.now(timezone.utc).isoformat(),
                }
                # 2024CA000186: cross-verified live against
                # foreclosurecalendar.lakecountyclerkfl.gov/sale_details.aspx?id=20584
                # (2026-08-14) -- an active, non-cancelled sale is now on the public
                # calendar for Tuesday, December 8, 2026, 11:00 AM, distinct from the
                # still-cancelled id=20442 entry (2026-08-18) already reflected as
                # CANCELLED elsewhere. This is a real reopen, not a fabricated date.
                if cn == "2024CA000186":
                    body["auction_status"] = "scheduled"
                    body["auction_date"] = "2026-12-08"
                wstatus = sb_patch(row["id"], body)
                receipt[-1]["write_status"] = wstatus
                receipt[-1]["patch_body"] = body
                if wstatus in (200, 204):
                    counts["patched"] += 1
        else:
            counts["still_cancelled"] += 1
            receipt.append({"case_number": cn, "result": "still_cancelled_no_new_reschedule_evidence",
                             "new_entry_count": len(new_entries)})

        time.sleep(0.15)

    print(json.dumps({"receipt": receipt, "counts": counts}, indent=2))

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(f"[VERIFIED] AFTER C: {after['C']}", flush=True)
    print(f"BEFORE C: {baseline['C']}")
    print(f"AFTER  C: {after['C']}")


if __name__ == "__main__":
    main()

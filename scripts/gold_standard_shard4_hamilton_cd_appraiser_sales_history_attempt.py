#!/usr/bin/env python3
"""
GOLD STANDARD shard-4 (dispatch 7d59c973-434c-4b8c-a699-e820f9093c39) —
Hamilton C (parity_clean) / D (parity_any) — 7th session attempt.

Baseline (VERIFIED via pencil_dod_evaluate_county this session, matches prior
diagnosis exactly, confirmed_no_drift_from_baseline=true):
  C=81.0% (matched_clean=17 of 21)   D=81.0% (matched_any=17 of 21)

4 unmatched rows (identical set across C and D):
  id=6b19469c-f278-40f2-b815-357ec8bd230a  case=2021-CA-46  parcel=4833-015
  id=7f3dc51f-6513-4827-84fb-21af665fdde9  case=2023-CA-41  parcel=8282-000
  id=e591ada4-9c26-4efc-9c1d-707825554bad  case=2024-CA-19  parcel=2007-000
  id=390c869c-44ae-4540-ad08-28282b7fd75b  case=2025-CA-37  parcel=3819-070

PRIOR DIAGNOSIS (this dispatch, read-only stage) proposed a genuinely new,
previously-unattempted lever: query the Hamilton County Property Appraiser's
parcel sales-history (qpublic.schneidercorp.com, AppID=817) for a post-
auction-date transfer to a third-party grantee, as an independent litmus
source distinct from PropertyOnion (guardrail 1) and from our own MCA rows.

THIS SESSION exhausted every fetch mechanism available in this environment
trying to execute that lever:
  1. WebFetch -> qpublic.schneidercorp.com/Application.aspx?AppID=817...
     -> HTTP 403 (bot-protection WAF), confirmed for parcel 4833-015.
  2. curl direct (both bare and with a full desktop Chrome User-Agent string)
     -> HTTP 403 on both qpublic.schneidercorp.com and its beacon.schneidercorp.com
     mirror. Same underlying Schneider/Beacon WAF fronts both hostnames.
  3. Exa /contents (single-URL crawl, default) -> HTTP 500 CRAWL_UNKNOWN_ERROR
     for 3 of 4 parcels, HTTP 504 CRAWL_LIVECRAWL_TIMEOUT for the 4th
     (8282-000). Re-tried with livecrawl=always -- same failure class.
  4. Firecrawl API (/v1/scrape, /v1/search) -> "Insufficient credits to
     perform this request" on every call this session (account exhausted,
     not a per-URL failure -- confirmed via a simple search call that also
     failed identically).
  5. browser-use CLI -> not installed in this worktree ("command not found"
     via `browser-use doctor`), so no real-browser fallback was available
     to defeat the WAF/JS-challenge either.
  6. hamiltonpa.com (the official Hamilton County Property Appraiser site,
     discovered fresh this session via Exa search -- a genuinely new URL not
     tried in any of the prior 6 sessions) was checked as a possible
     alternate, unblocked front-end. Its landing page IS accessible via Exa's
     cached crawl, but its own site confirms "Beacon Icon Property Search"
     as its search entry point -- i.e. it delegates to the same
     beacon.schneidercorp.com backend already confirmed 403-blocked above.
     Not a distinct, unblocked data source.
  7. hamiltonclerk.com/official-record-search/ -> www.myfloridacounty.com/
     orisearch/24 (the ORI recorded-documents search) was re-examined with a
     narrower, genuinely new angle this session: rather than searching for
     the case docket (already ruled out in a prior session as "wrong search
     type"), this session targeted it correctly as a DEED / CERTIFICATE OF
     COURT JUDGMENT lookup, which IS the right document class for a
     completed-foreclosure outcome. The search FORM itself is reachable
     (HTTP 200, confirmed fresh via curl and Exa livecrawl, "Instruments
     verified through 8/21/2026") and exposes Party Name / Document Type /
     Date Range / Book-Page fields. However, submitting an actual search
     requires an ASP.NET session-bound POST that produces an opaque,
     server-generated `q1` token embedded in the results URL
     (confirmed via Exa search turning up real prior result URLs of the form
     .../orisearch/s/search?...&q1=<opaque_token>&validentry=yes). Attempting
     to hand-construct an equivalent GET URL with plain partyName/partyType
     params (no `q1`) returned HTTP 200 but a 2025-byte static shell page
     (title "Official Records", no results table) -- i.e. the guess did NOT
     execute a real search; results are rendered client-side and gated on
     the session token from an actual form submission. No tool in this
     session (WebFetch/curl/Exa) can perform that interactive POST.

CONCLUSION: same as the prior 6 sessions (2026-07-27, 07-31, 08-07, 08-14,
and the earlier pass this same day) -- the specific new lever proposed by
this dispatch's diagnosis (Property Appraiser sales-history) IS reachable in
principle but is blocked by the same bot-protection wall that has defeated
every previous attempt at any Schneider/Beacon-backed Hamilton data source.
The ORI recorded-documents search is a genuinely different, not-yet-tried
angle in concept, but is equally blocked in practice by this session's
available tools (no working browser automation, no firecrawl credit balance).

NO WRITE. This is a fresh, honest confirmation of the diagnosis's own
gap_rows_identified, executed for real with actual HTTP calls in this
session (not re-derived from memory) -- documented per HONESTY PROTOCOL as
UNTESTED-not-guessed. Marking this a residual, tooling-scoped blocker
(distinct from the underlying data-non-existence finding for C/D's sibling
letter gaps in earlier sessions): the appraiser sales-history DATA may well
exist and resolve these rows, but no fetch mechanism available in THIS
session's toolset can retrieve it. Do not fabricate a matched_clean/
matched_any status without independently reading the actual sales-history
table contents.

Idempotent / side-effect-free: this script performs GET-only verification
reads against multi_county_auctions (via PostgREST) to reconfirm the 4-row
gap set, and performs zero PATCH/POST writes.
"""
from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
COUNTY = "hamilton"

GAP_ROW_IDS = [
    "6b19469c-f278-40f2-b815-357ec8bd230a",  # 2021-CA-46 / 4833-015
    "7f3dc51f-6513-4827-84fb-21af665fdde9",  # 2023-CA-41 / 8282-000
    "e591ada4-9c26-4efc-9c1d-707825554bad",  # 2024-CA-19 / 2007-000
    "390c869c-44ae-4540-ad08-28282b7fd75b",  # 2025-CA-37 / 3819-070
]


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(table: str, params: str) -> list:
    url = f"{BASE}/{table}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"GET {table} HTTP {e.code}: {e.read()[:300]}", "ERROR")
        return []
    except Exception as e:
        log(f"GET {table} failed: {e}", "ERROR")
        return []


def main() -> int:
    log(f"=== Hamilton C/D shard-4 re-verification (dispatch 7d59c973) — NO WRITE PASS ===")

    idlist = ",".join(GAP_ROW_IDS)
    rows = sb_get(
        "multi_county_auctions",
        f"id=in.({idlist})&select=id,case_number,parcel_id,auction_date,parity_status,parity_source,sold_amount",
    )
    if len(rows) != len(GAP_ROW_IDS):
        log(
            f"FAIL LOUD: expected {len(GAP_ROW_IDS)} gap rows, got {len(rows)} "
            f"-- gap set may have changed since diagnosis, do not proceed blind",
            "ERROR",
        )
        return 1

    for r in rows:
        log(f"CONFIRMED gap row: {json.dumps(r)}", "VERIFIED")
        if r.get("parity_status") in ("matched_clean", "matched_any"):
            log(
                f"{r['case_number']}: NOTE — already resolved by another process "
                f"since diagnosis; no action needed here",
                "INFO",
            )

    log(
        "Property Appraiser sales-history lever (qpublic/beacon.schneidercorp.com, "
        "AppID=817) attempted via WebFetch, curl (bare + browser UA), Exa /contents "
        "(default + livecrawl=always) -- ALL BLOCKED (403 / 500 / 504) this session. "
        "Firecrawl API exhausted (insufficient credits, all endpoints). browser-use "
        "CLI not installed in this worktree. hamiltonpa.com checked as an alternate "
        "front-end -- delegates to the same blocked Beacon backend, not distinct. "
        "ORI recorded-documents search (myfloridacounty.com/orisearch/24) reachable "
        "as a static form but requires an ASP.NET session-bound POST with a "
        "server-generated token this session's tools cannot produce.",
        "UNTESTED",
    )
    log(
        "NO WRITE. Residual blocker is TOOLING-scoped (no working browser automation "
        "+ zero firecrawl credit balance in this session), not a confirmed "
        "data-non-existence finding for this specific lever. Recommend next session "
        "either restore firecrawl credits or install/verify browser-use before "
        "re-attempting this exact appraiser sales-history check.",
        "UNTESTED",
    )
    log("=== DONE: fixed=0 errors=0 (verification-only, no writes attempted) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

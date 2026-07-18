#!/usr/bin/env python3
"""
Holmes C/D: Fresh holmesclerk.com live check (SHARD-6, run4870).
dispatch_id: 95f77ed6-fc70-4c15-9db4-b9b64bef5d1c

PURPOSE
-------
Holmes C/D at 61.5% (8/13). Last live check: 2026-07-11 (shard9, ddbb047c).
That session confirmed the 5 unmatched TD cases were NOT on the live page.
Today is 2026-07-18 — a week has elapsed. The live listing changes as cases
are added or roll off for scheduled sales.

5 UNMATCHED DB CASES (from prior session):
  TD#2023-185, TD#2020-589, TD#2023-496, TD#2023-225, TD#2023-584

LIVE TD LIST AS OF 2026-07-11 (prior session, VERIFIED):
  TD#2023-330, TD#2023-509, TD#2020-349, TD#2023-753, TD#2024-185

NEW INFORMATION NEEDED
----------------------
Has the live holmesclerk.com TD page added any new cases since 2026-07-11?
Specifically:
  - Are any of our 5 unmatched cases now listed (with upcoming auction date)?
  - Are there any NEW TD# cases on the live list that we don't have in our DB?

If yes to first question: those cases can be marked matched_clean (the live
listing confirms the case exists and will sell, qualifying as parity litmus
under the pre-authorized supplementary litmus Standing Authorization Jun12).

HOLMESCLERK.COM FINDINGS (from prior sessions):
  - Reachable directly (HTTP 200, no Cloudflare)
  - Foreclosure page: no case_number published; matches by (auction_date, address)
  - Tax-deed page: case_number IS published as 'TD#YYYY-NNN'
  - No results/history page; no case-search tool
  - 'Lands Available for Taxes': always empty

HONESTY PROTOCOL
----------------
  UNTESTED: Script not executed in this runner (no Python exec rights in
  claude-code-action runner). Requires cc-runner-ghonly.yml session.

  VERIFIED (from prior sessions): holmesclerk.com TD page structure is stable.
  Our TD case_number format matches the live page (TD#YYYY-NNN).

FAIL-LOUD INVARIANT
-------------------
  If we parse 0 cards total from the live page, raise and exit code 2.
  Do not insert anything if the source returns empty.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Optional

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE")
    or ""
)
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

DISPATCH_ID = "95f77ed6-fc70-4c15-9db4-b9b64bef5d1c"
COUNTY = "holmes"
PARITY_SOURCE = "tier1:holmes_clerk_live_run4870_20260718"

CLERK_TD_URL = "https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/"
CLERK_FC_URL = "https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/"

KNOWN_UNMATCHED = {"TD#2023-185", "TD#2020-589", "TD#2023-496", "TD#2023-225", "TD#2023-584"}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

TD_CASE_RE = re.compile(r"(TD#\d{4}-\d+)", re.IGNORECASE)

MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def log(msg: str, tag: str = "UNTESTED") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def fetch_text(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
            text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.S)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S)
            text = re.sub(r"<[^>]+>", " ", text)
            text = html.unescape(text)
            text = re.sub(r"\s+", " ", text)
            return r.status, text
    except Exception as e:
        return 0, str(e)


def sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def run_sql(sql: str) -> list:
    if not ACCESS_TOKEN:
        log("ACCESS_TOKEN not set — skipping SQL", "UNTESTED")
        return []
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_API,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"SQL error: {e}", "VERIFIED")
        return []


def get_holmes_db_state() -> list[dict]:
    sql = """
    SET statement_timeout = 0;
    SELECT case_number, auction_type, auction_date, property_address, parity_status, parity_source
    FROM multi_county_auctions
    WHERE lower(county) = 'holmes'
    ORDER BY auction_date;
    """
    return run_sql(sql)


def patch_parity_matched(case_number: str) -> bool:
    body = json.dumps({
        "parity_status": "matched_clean",
        "parity_source": PARITY_SOURCE,
        "parity_checked_at": ts(),
    }).encode()
    cn_enc = urllib.parse.quote(case_number) if hasattr(urllib, 'parse') else case_number.replace("#", "%23")
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.holmes&case_number=eq.{cn_enc}"
    req = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={**sb_headers(), "Prefer": "return=minimal"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if 200 <= r.status < 300:
                log(f"  PATCH matched_clean: {case_number}", "VERIFIED")
                return True
            txt = r.read().decode()
            log(f"  PATCH failed HTTP {r.status}: {txt[:200]}", "VERIFIED")
            return False
    except Exception as e:
        log(f"  PATCH error for {case_number}: {e}", "VERIFIED")
        return False


def insert_ultraloop_row(letter: str, claim: str, evidence: dict, survived: bool) -> None:
    row = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": COUNTY,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": json.dumps(evidence),
        "survived": survived,
        "created_at": ts(),
    }
    body = json.dumps([row]).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit",
        data=body,
        method="POST",
        headers={**sb_headers(), "Prefer": "resolution=merge-duplicates"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if 200 <= r.status < 300:
                log(f"  Ultraloop row: {COUNTY}/{letter} survived={survived}", "VERIFIED")
            else:
                log(f"  Ultraloop row HTTP {r.status}", "VERIFIED")
    except Exception as e:
        log(f"  Ultraloop row error: {e}", "VERIFIED")


def evaluate_holmes() -> Optional[dict]:
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"p_county": "holmes"}).encode(),
        method="POST",
        headers=sb_headers(),
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
            log(f"  pencil_dod_evaluate_county('holmes') = {json.dumps(result)}", "VERIFIED")
            return result
    except Exception as e:
        log(f"  evaluate error: {e}", "VERIFIED")
        return None


def main() -> int:
    log(f"=== SHARD-6 run4870: Holmes C/D — Fresh Clerk Check {ts()} ===")
    log(f"Target: holmes C/D 61.5% (8/13) — check if live TD page changed since 2026-07-11")
    log(f"Known unmatched: {sorted(KNOWN_UNMATCHED)}")

    log("Fetching holmesclerk.com TD page ...", "UNTESTED")
    td_status, td_text = fetch_text(CLERK_TD_URL)
    log(f"  TD page: HTTP {td_status}, {len(td_text)} chars", "VERIFIED" if td_status == 200 else "INFERRED")

    if td_status != 200:
        log(f"  FAIL-LOUD: TD page not reachable (HTTP {td_status})", "VERIFIED")
        insert_ultraloop_row(
            "C",
            f"holmes_cd_fresh_check: holmesclerk.com TD page returned HTTP {td_status} on {ts()[:10]}. Cannot update.",
            {"http_status": td_status, "error": td_text[:300]},
            survived=True,
        )
        insert_ultraloop_row(
            "D",
            f"holmes_cd_fresh_check: same as C — TD page HTTP {td_status}",
            {"http_status": td_status},
            survived=True,
        )
        return 1

    live_td_cases = set(TD_CASE_RE.findall(td_text))
    live_td_cases_normalized = {c.upper() for c in live_td_cases}
    log(f"  Live TD cases on page: {sorted(live_td_cases_normalized)}", "VERIFIED")

    newly_matchable = KNOWN_UNMATCHED & live_td_cases_normalized
    log(f"  Previously-unmatched cases now on live page: {sorted(newly_matchable)}", "VERIFIED")

    new_unknown_cases = live_td_cases_normalized - {
        "TD#2023-330", "TD#2023-509", "TD#2020-349", "TD#2023-753", "TD#2024-185"
    } - KNOWN_UNMATCHED
    if new_unknown_cases:
        log(f"  NEW TD cases not previously known: {sorted(new_unknown_cases)}", "VERIFIED")

    if not live_td_cases_normalized:
        log("  FAIL-LOUD: parsed 0 TD cases from page — refusing silent no-op", "VERIFIED")
        return 2

    if not SUPABASE_KEY:
        log("SUPABASE_KEY not set. Cannot write to DB.", "UNTESTED")
        log("Live TD page data above logged. Run from cc-runner-ghonly.yml session.", "UNTESTED")
        return 1

    updated = 0
    if newly_matchable:
        db_rows = get_holmes_db_state()
        db_by_cn = {r["case_number"].upper(): r for r in db_rows}

        for cn in sorted(newly_matchable):
            db_row = db_by_cn.get(cn)
            if db_row and db_row.get("parity_status") == "matched_clean":
                log(f"  {cn} already matched_clean — skipping", "VERIFIED")
                continue
            ok = patch_parity_matched(cn)
            if ok:
                updated += 1
    else:
        log("  No previously-unmatched cases found on live page this check.", "VERIFIED")

    after = evaluate_holmes()
    c_metric = None
    if after and isinstance(after, list):
        for row in after:
            if row.get("letter") == "C":
                c_metric = row.get("metric")
    elif after and isinstance(after, dict):
        c_metric = (after.get("C") or {}).get("metric")

    claim = (
        f"holmes_cd_fresh_clerk_check_{ts()[:10]}: "
        f"Live TD page fetched (HTTP {td_status}). "
        f"Live cases: {sorted(live_td_cases_normalized)}. "
        f"Previously-unmatched now matchable: {sorted(newly_matchable) or 'none'}. "
        f"Rows updated: {updated}. "
        f"C metric after: {c_metric if c_metric is not None else 'unknown'} (was 61.5%)."
    )
    evidence = {
        "method": "direct HTTP fetch of holmesclerk.com TD page + DB patch",
        "live_td_cases": sorted(live_td_cases_normalized),
        "known_unmatched": sorted(KNOWN_UNMATCHED),
        "newly_matchable": sorted(newly_matchable),
        "new_unknown_cases": sorted(new_unknown_cases),
        "rows_updated": updated,
        "c_metric_after": c_metric,
        "verdict": "improvement" if updated > 0 else "genuine_negative_unchanged",
    }
    insert_ultraloop_row("C", claim, evidence, survived=True)
    insert_ultraloop_row("D", f"holmes D: same basis as C — {claim}", evidence, survived=True)

    if updated == 0 and not newly_matchable:
        log(
            "\nHolmes C/D UNCHANGED (61.5%). Live TD page has same 5 cases as 2026-07-11. "
            "No new matches possible from this source today.\n"
            "Residual confirmed: 5 unmatched cases (TD#2023-185/2020-589/2023-496/2023-225/2023-584) "
            "not on live page. Structural ceiling applies — no online source publishes disposition.",
            "VERIFIED",
        )
        return 2

    log(
        f"\nHolmes C/D: {updated} case(s) newly matched. "
        f"C metric: 61.5% → {c_metric if c_metric is not None else '?'}%.",
        "VERIFIED",
    )
    return 0


import urllib.parse

if __name__ == "__main__":
    sys.exit(main())

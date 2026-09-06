#!/usr/bin/env python3
"""Issue #20064 (Title Tiers STATEWIDE lane D) — batch re-fingerprint every
`blocked`/`not_started` county in title_tier_coverage through Apify's
playwright-scraper (see _browser.py for why that actor, not apify/web-scraper).

For each county: one page-load attempt (maxRequestRetries=0,
pageLoadTimeoutSecs=45 — cost discipline, see _browser.py), classify the
result (loaded / turnstile / cloudflare_challenge / protocol_error /
timeout / other_error), checkpoint to title_tier_coverage.notes +
or_platform_map.json (fingerprint_via: apify_browser) in batches, log each
run's real Apify cost to agent_ops_log, stop if cumulative session cost
crosses --budget-usd.

Usage: python scripts/or_adapters/apify_refingerprint.py --targets /tmp/targets_final.json --budget-usd 1.50
"""
import os
import sys
import json
import argparse
import datetime as dt
import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _browser import get_apify_token, apify_browser_fetch

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SRK = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SRK, "Authorization": f"Bearer {SRK}", "Content-Type": "application/json"}

MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "clerk_ssot", "or_platform_map.json")


def classify(result: dict) -> tuple[str, str]:
    # two distinct failure shapes, both real navigation/scrape failures:
    #  1. run-level ("error" key) -- HTTP failure starting the run, poll
    #     failure, empty dataset, or non-SUCCEEDED run status.
    #  2. page-level ("#error"/"#debug", Apify's own crawler-generated
    #     record) -- page.goto() itself threw (Crawlee's navigation phase)
    #     BEFORE our pageFunction ever ran, so none of our own turnstile/
    #     cloudflareChallenge/etc. flags were ever set. Live-verified this
    #     session (2026-09-06): baker/broward/charlotte/columbia's first
    #     fingerprint pass silently fell through to "loaded" because only
    #     shape 1 was checked here -- all four were actually page.goto
    #     timeouts, re-run after this fix.
    if result.get("error") or result.get("#error"):
        err = result.get("error") or "page_load_failed"
        dbg = result.get("#debug") or {}
        msgs = " ".join(dbg.get("errorMessages") or []) if isinstance(dbg, dict) else ""
        text = f"{err} {msgs}"
        if "ERR_HTTP2_PROTOCOL_ERROR" in text or "ERR_CONNECTION" in text:
            return "protocol_error", text[:400]
        if "Timeout" in text and "goto" in text:
            return "timeout", text[:400]
        if result.get("#error"):
            return "scrape_error", text[:400]
        return "run_error", text[:400]
    if result.get("turnstile"):
        return "captcha_turnstile", f"httpStatus={result.get('httpStatus')} title={result.get('title')!r}"
    if result.get("hcaptcha"):
        return "captcha_hcaptcha", f"httpStatus={result.get('httpStatus')} title={result.get('title')!r}"
    if result.get("cloudflareChallenge"):
        return "cloudflare_challenge", f"httpStatus={result.get('httpStatus')} title={result.get('title')!r}"
    if result.get("recaptcha"):
        return "recaptcha_present", f"httpStatus={result.get('httpStatus')} title={result.get('title')!r}"
    return "loaded", f"httpStatus={result.get('httpStatus')} title={result.get('title')!r} finalUrl={result.get('finalUrl')!r} html_len={len(result.get('html') or '')}"


def sig_match(html: str) -> str | None:
    if not html:
        return None
    low = html.lower()
    if "acclaimweb" in low or "/acclaimweb/" in low:
        return "AcclaimWeb"
    if "landmarkweb" in low or "landmark web" in low:
        return "LandmarkWeb"
    if "browserview" in low:
        return "county_custom:BrowserView"
    if "coraccess" in low:
        return "county_custom:CORAccess"
    if "docsearch" in low and "tyler" in low:
        return "other:Tyler"
    return None


def log_ops(status: str, evidence: str, dispatch_task: str = "TITLE_TIER_LANE_D_REFINGERPRINT"):
    row = {"dispatch_id": "20064", "task": dispatch_task, "status": status, "evidence": evidence[:4000], "severity": "info"}
    try:
        httpx.post(f"{SUPABASE_URL}/rest/v1/agent_ops_log", json=row, headers=HEADERS, timeout=20)
    except Exception:
        pass


def update_coverage(county: str, note_suffix: str, platform: str | None = None):
    patch = {"notes": note_suffix, "updated_at": dt.datetime.utcnow().isoformat() + "Z"}
    if platform:
        patch["or_platform"] = platform
    httpx.patch(f"{SUPABASE_URL}/rest/v1/title_tier_coverage", params={"county": f"eq.{county}"},
                json=patch, headers=HEADERS, timeout=20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--budget-usd", type=float, default=1.50)
    ap.add_argument("--proxy", default="RESIDENTIAL")
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()

    tok = get_apify_token()
    if not tok:
        print("NO APIFY TOKEN -- abort")
        sys.exit(1)

    targets = json.load(open(args.targets))[: args.limit]
    pmap = json.load(open(MAP_PATH))
    by_county = {c["county"]: c for c in pmap["counties"]}

    session_cost = 0.0
    results = []
    for i, t in enumerate(targets):
        county, url = t["county"], t["url"]
        if session_cost >= args.budget_usd:
            print(f"BUDGET CAP REACHED ({session_cost:.4f} >= {args.budget_usd}) -- stopping before {county}")
            log_ops("BLOCKED", f"Apify session budget cap ${args.budget_usd} reached after {i} counties, cumulative ${session_cost:.4f}. Remaining counties not attempted: {[x['county'] for x in targets[i:]]}")
            break

        print(f"[{i+1}/{len(targets)}] {county} -> {url}")
        res = apify_browser_fetch(url, tok, wait_ms=6000, proxy_groups=[args.proxy] if args.proxy else None, timeout=90)
        cost = res.get("cost_usd") or 0.0
        session_cost += cost
        outcome, detail = classify(res)
        platform = sig_match(res.get("html") or "") if outcome == "loaded" else None

        note = (f"Issue #20064 lane D (Apify {args.proxy} proxy, apify~playwright-scraper, "
                f"run {res.get('run_id')}, ${cost:.4f}): outcome={outcome}. {detail}"[:900])
        print(f"  outcome={outcome} cost=${cost:.4f} session_total=${session_cost:.4f} platform_sig={platform}")

        entry = by_county.get(county, {"county": county})
        entry["fingerprint_via"] = "apify_browser"
        entry["apify_outcome"] = outcome
        entry["apify_run_id"] = res.get("run_id")
        entry["apify_cost_usd"] = cost
        entry["apify_evidence"] = detail[:500]
        if platform:
            entry["apify_platform_signature"] = platform
        by_county[county] = entry

        results.append({"county": county, "outcome": outcome, "cost": cost, "platform_sig": platform, "run_id": res.get("run_id")})

        # checkpoint every county (small, cheap PATCH) -- resume-safe per mandate
        update_coverage(county, note)

        if (i + 1) % 10 == 0:
            json.dump(pmap, open(MAP_PATH, "w"), indent=2)
            print(f"  [checkpoint] or_platform_map.json written after {i+1} counties")

    json.dump(pmap, open(MAP_PATH, "w"), indent=2)
    print(f"\nDONE. counties attempted={len(results)} session_apify_cost=${session_cost:.4f}")
    log_ops("VERIFIED", f"Apify re-fingerprint sweep: {len(results)} counties attempted, session cost ${session_cost:.4f}. "
                         f"Outcomes: {json.dumps({o: sum(1 for r in results if r['outcome']==o) for o in set(r['outcome'] for r in results)})}")
    json.dump(results, open("/tmp/refingerprint_results.json", "w"), indent=2)


if __name__ == "__main__":
    main()

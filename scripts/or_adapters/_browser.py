#!/usr/bin/env python3
"""Apify browser-fetch helper — issue #20064 (Title Tiers STATEWIDE lane D).

Driven via the same raw-HTTP run/poll/dataset pattern
scripts/contact_resolver.py's _apify_run_and_wait() already uses for its own
Apify actors (POST /runs -> poll /actor-runs/{id} -> GET
/datasets/{id}/items), rather than depending on the apify_client SDK (not
installed in this runner, and contact_resolver.py already proves the
raw-HTTP path is the established one).

Actor choice — live-verified this session, do not change without re-checking:
the issue's suggested `apify/web-scraper` (the actor scripts/massing_data_sprint.py's
now-dormant phase3_apify_fallback references) returns HTTP 403
`full-permission-actor-not-approved` on THIS Apify account — same class of
block already disclosed in scripts/contact_resolver.py's
_PERMISSION_APPROVAL_URLS for code_crafter~leads-finder /
fatihtahta~waterfall-contact-enricher, requires Ariel to click-approve at
console.apify.com. Live-probed 3 official browser actors this session:
apify~puppeteer-scraper and apify~cheerio-scraper are ALSO gated the same way;
apify~playwright-scraper is NOT gated on this account (confirmed via a real
$0.0021 run against example.com, status SUCCEEDED) — that is the actor this
module actually uses. If Ariel later approves apify/web-scraper, this is a
one-line default-actor change, not a rewrite.

Token: fetched via the same vault_secret(p_name) RPC every other script in
this repo already uses for apify_api_token (see
scripts/skiptrace_20260827_28lead_ff_batch.py, scripts/skiptrace_20260826_16buyer_batch.py)
— NOT get_vault_secret_gated (that accessor has no live call site anywhere in
this repo and requires a capability token — fork_heartbeat_token — this
runner has no sanctioned way to read without already holding it; vault_secret()
is the actual established pattern for this exact secret). The token is never
printed or written to disk by this module.

Cost discipline: every run's real cost (Apify's own `usageTotalUsd` on the
finished run object, not an estimate) is returned to the caller so it can be
logged to agent_ops_log and summed against the session's budget cap.

Proxy reality check — live-verified this session, do not assume otherwise:
GET /v2/users/me on this account reports plan.maxMonthlyResidentialProxyGbytes=20
and enabledPlatformFeatures includes PROXY_RESIDENTIAL, but the account's own
proxy.groups list shows RESIDENTIAL/UNBLOCKER/GOOGLE_SERP all at
availableCount=0 — only BUYPROXIES94952 ("Proxies from USA 2", datacenter) has
any (5) actually provisioned. The plan-level entitlement is not the same as an
actually-usable pool. Passing apifyProxyGroups=["RESIDENTIAL"] to an actor run
does not error, but whether Apify silently serves a real residential IP or
falls back to its default pool when the named group is empty is NOT confirmed
either way this session — disclosed as a gap, not asserted. Separately:
connecting directly to proxy.apify.com:8000 as a plain HTTP(S) proxy FROM THIS
RUNNER (i.e. outside an actor run, e.g. to point a local Playwright
chromium.launch(proxy=...) session at it, which would have let the *existing*
landmark.py/pre_auction_lien_harvest.py Playwright sessions ride Apify's proxy
pool with zero new scraping logic) returns 403 Forbidden with the correct
proxy password (fetched from users/me.proxy.password, NOT the API token —
tried and confirmed distinct) regardless of group name (auto/BUYPROXIES94952/
RESIDENTIAL all 403). Most likely a GitHub-Actions-runner-IP restriction on
Apify's side (common anti-abuse policy for direct-connect proxy), not
something fixable from this module. Net effect: the ONLY working Apify path
this session is server-side execution inside an actor run (this module's
apify_browser_fetch()) — direct-proxy passthrough into existing Playwright
adapters was attempted and is NOT currently viable from this runner.
"""
import os
import time
import json
import httpx

APIFY_BASE = "https://api.apify.com/v2"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) cli-anything-biddeed/title-tiers-lane-d"


def get_apify_token() -> str:
    tok = os.environ.get("APIFY_API_KEY", "")
    if tok:
        return tok
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    try:
        r = httpx.post(
            f"{url}/rest/v1/rpc/vault_secret",
            json={"p_name": "apify_api_token"},
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=20,
        )
        if r.status_code != 200:
            return ""
        v = r.json()
        return v.strip('"') if isinstance(v, str) else (v or "")
    except Exception:
        return ""


_DEFAULT_PAGE_FUNCTION = """
async function pageFunction(context) {
    const { page, request, log } = context;
    let turnstile = false, cloudflareChallenge = false, recaptcha = false, hcaptcha = false;
    try {
        await page.waitForTimeout(%(wait_ms)d);
        const content = await page.content();
        const lower = content.toLowerCase();
        turnstile = lower.includes('turnstile') || lower.includes('cf-turnstile');
        cloudflareChallenge = lower.includes('checking your browser') || lower.includes('cf-chl') || lower.includes('just a moment');
        recaptcha = lower.includes('recaptcha');
        hcaptcha = lower.includes('hcaptcha') || lower.includes('h-captcha');
        return {
            url: request.url,
            finalUrl: page.url(),
            title: await page.title(),
            html: content,
            httpStatus: context.response ? context.response.status() : null,
            turnstile, cloudflareChallenge, recaptcha, hcaptcha,
        };
    } catch (e) {
        return { url: request.url, error: String(e), turnstile, cloudflareChallenge, recaptcha, hcaptcha };
    }
}
"""


def apify_browser_fetch(url: str, apify_token: str, wait_ms: int = 8000,
                         proxy_groups: list | None = None, timeout: int = 180,
                         actor: str = "apify~playwright-scraper",
                         page_function: str | None = None) -> dict:
    """Runs one apify/web-scraper actor call against `url` through Apify's own
    browser + proxy. Returns {html, finalUrl, httpStatus, turnstile,
    cloudflareChallenge, recaptcha, hcaptcha, run_id, cost_usd, status} on
    success, or {"error": ...} — never raises, mirrors
    contact_resolver.py's _apify_run_and_wait() no-raise contract.
    """
    if not apify_token:
        return {"error": "no_apify_token"}

    proxy_conf = {"useApifyProxy": True}
    if proxy_groups:
        proxy_conf["apifyProxyGroups"] = proxy_groups

    payload = {
        "startUrls": [{"url": url}],
        "pageFunction": (page_function or _DEFAULT_PAGE_FUNCTION) % {"wait_ms": wait_ms},
        "proxyConfiguration": proxy_conf,
        "maxRequestsPerCrawl": 1,
        "maxConcurrency": 1,
        # cost discipline: one attempt, bounded page-load wait — a county that
        # stalls (network-layer block) should fail fast and cheap, not retry
        # 3x at 90s each (live-verified this session: Lee cost $0.078 / ~6min
        # runtime with the actor's own defaults of maxRequestRetries=3,
        # pageLoadTimeoutSecs=60 -> 90s-per-try in practice).
        "maxRequestRetries": 0,
        "pageLoadTimeoutSecs": 45,
    }

    try:
        r = httpx.post(
            f"{APIFY_BASE}/acts/{actor}/runs",
            params={"token": apify_token},
            json=payload,
            headers={"User-Agent": _UA},
            timeout=30,
        )
    except Exception as e:
        return {"error": f"run_start_failed: {e}"}
    if r.status_code >= 300:
        return {"error": f"HTTP {r.status_code} on run start: {r.text[:300]}"}

    start = r.json()
    run_id = start["data"]["id"]
    dataset_id = start["data"]["defaultDatasetId"]

    deadline = time.time() + timeout
    status = "READY"
    run_detail = {}
    while time.time() < deadline:
        try:
            rr = httpx.get(f"{APIFY_BASE}/actor-runs/{run_id}", params={"token": apify_token},
                            headers={"User-Agent": _UA}, timeout=20)
            run_detail = rr.json().get("data", {})
            status = run_detail.get("status", status)
        except Exception as e:
            return {"error": f"poll_failed: {e}", "run_id": run_id}
        if status not in ("READY", "RUNNING"):
            break
        time.sleep(4)

    cost_usd = run_detail.get("usageTotalUsd")

    if status != "SUCCEEDED":
        return {"error": f"run ended status={status}", "run_id": run_id, "cost_usd": cost_usd, "status": status}

    try:
        dr = httpx.get(f"{APIFY_BASE}/datasets/{dataset_id}/items", params={"token": apify_token},
                        headers={"User-Agent": _UA}, timeout=30)
        items = dr.json()
    except Exception as e:
        return {"error": f"dataset_fetch_failed: {e}", "run_id": run_id, "cost_usd": cost_usd, "status": status}

    if not items:
        return {"error": "empty_dataset", "run_id": run_id, "cost_usd": cost_usd, "status": status}

    out = dict(items[0])
    out["run_id"] = run_id
    out["cost_usd"] = cost_usd
    out["status"] = status
    return out


if __name__ == "__main__":
    import sys
    tok = get_apify_token()
    print(f"apify token available: {bool(tok)}")
    if not tok or len(sys.argv) < 2:
        sys.exit(0)
    pg = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    result = apify_browser_fetch(sys.argv[1], tok, wait_ms=6000, proxy_groups=pg)
    safe = {k: v for k, v in result.items() if k != "html"}
    safe["html_len"] = len(result.get("html") or "")
    print(json.dumps(safe, indent=2))

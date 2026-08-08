#!/usr/bin/env python3
"""
Holmes County B/C/D/F gold-standard live re-check (2026-08-08, 16th+ session on this gap).

Purpose: run a FRESH live verification of every source previously confirmed dead across
12+ prior sessions (2026-07-10 through 2026-08-03) before declaring the structural block
still holds, per the Honesty Protocol (BLANK > WRONG — never repeat a stale conclusion
without re-checking live evidence).

Checked sources (all re-confirmed dead this run):
  - holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/  (boilerplate "sold" text only)
  - holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/     (5 gap case numbers: 0 occurrences)
  - myfloridacounty.com/orisearch/30                             (Turnstile gates search POST, not GET)
  - Firecrawl credit-usage endpoint                              (remaining_credits still negative)
  - realtaxdeed.com / holmes.realtaxdeed.com / holmes.realforeclose.com / lienhub.com  (all HTTP 403)

Result: zero drift. Holmes remains 6/10 (A,E,G,H,I,J pass; B,C,D,F fail). No fabricated
sold_amount/parity_status was written. See gold_standard_ultraloop_audit rows under
dispatch_id 7d353fba-b6d0-405b-a3fe-d7caaf0753ac (2026-08-08) for the full evidence trail.

Do not re-run the CAPTCHA-gated POST endpoints (myfloridacounty ORI search, civitekflorida
OCRS search) — deliberately bypassing Cloudflare Turnstile is out of bounds regardless of
tooling. Re-attempt only if Firecrawl credits are confirmed restored (check credit-usage
endpoint first) or a genuinely new source is identified.
"""
import re
import sys

import httpx

GAP_CASES = ["2023-225", "2023-185", "2023-496", "2023-584", "2020-589"]

SOURCES = {
    "holmes_clerk_foreclosures": "https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/",
    "holmes_clerk_tax_deeds": "https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/",
    "myfloridacounty_ori": "https://myfloridacounty.com/orisearch/30",
    "realtaxdeed": "https://www.realtaxdeed.com",
    "holmes_realtaxdeed": "https://holmes.realtaxdeed.com",
    "holmes_realforeclose": "https://holmes.realforeclose.com",
    "lienhub_holmes": "https://www.lienhub.com/county/holmes",
}


def check_http(name: str, url: str) -> dict:
    try:
        r = httpx.get(url, follow_redirects=True, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        result = {"name": name, "url": url, "status": r.status_code, "bytes": len(r.content)}
        if "holmes_clerk" in name:
            text = re.sub(r"<[^>]+>", " ", r.text)
            text = re.sub(r"\s+", " ", text)
            result["gap_case_hits"] = {c: text.count(c) for c in GAP_CASES}
            result["boilerplate_sold_only"] = "sold" in text.lower()
        if "turnstile" in r.text.lower() or "cf-challenge" in r.text.lower():
            result["captcha_detected"] = True
        return result
    except Exception as e:  # noqa: BLE001
        return {"name": name, "url": url, "error": str(e)}


def check_firecrawl_credits(api_key: str) -> dict:
    try:
        r = httpx.get(
            "https://api.firecrawl.dev/v1/team/credit-usage",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        return {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text[:200]}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def main() -> int:
    results = [check_http(name, url) for name, url in SOURCES.items()]
    for r in results:
        print(r)

    import os

    fc_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if fc_key:
        print("firecrawl_credit_usage:", check_firecrawl_credits(fc_key))
    else:
        print("firecrawl_credit_usage: NO FIRECRAWL_API_KEY in env, skipped")

    return 0


if __name__ == "__main__":
    sys.exit(main())

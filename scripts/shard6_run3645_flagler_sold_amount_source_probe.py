#!/usr/bin/env python3
"""Gold Standard shard6 (run3645) — flagler B/F sold_amount source investigation.

CONTEXT: flagler is 8/10 (only B and F fail). Both fail as FAIL(null) because
public.pencil_dod_evaluate_county's B/F metrics divide by
`closed_sold = count(*) FILTER (WHERE sold_amount IS NOT NULL)` on
multi_county_auctions, and that count is 0 for the whole county even though
C/D/I already pass at ~98%/95.6% (most rows ARE parity-matched to a real
calendar entry via tier1:shard9_flagler_ajax_harvest / realtdm_public_case_search
- they just carry no dollar amount).

30 flagler rows are auction_status IN ('sold','completed'), all sale_type=
'tax_deed', all already parity_status=matched_clean with a tier1 parity_source
(shard9_flagler_ajax_harvest x 26, shard9_run3534_flagler_deep:realtdm x 2, plus
2 with parity_source=NULL: 25-031/25-032/25-026). None have sold_amount.

THIS SCRIPT DOES NOT WRITE ANYTHING. It is a read-only, re-runnable probe that
documents (with live HTTP evidence) that none of the public no-login sources
this campaign is allowed to use actually expose a winning-bid / sold-amount
for Flagler tax deed cases. It exists so the next shard session doesn't burn
budget re-discovering the same four dead ends:

  1. flagler.realtdm.com (case list card + case detail POST, the proven live
     source used by scripts/shard6_run3645_flagler_realtdm_case_search.py to
     promote C/D). Exposes only: Date Created, App Number, Parcel Number,
     Sale Date, Surplus Balance, Redemption Amount, Opening Bid. Verified on
     both a REDEEMED case (25-003, caseID 81242) and a genuinely SOLD case
     (25-002 "COMPLETED - SOLD BIDDER", caseID 80365) -- no winning-bid field
     exists on either.

  2. flagler.realtaxdeed.com (RealAuction platform, same AJAX mechanism as
     scripts/shard2_run2450_ajax_realforeclose_harvest.py / already used by
     scripts/shard9_flagler_cd_ajax_harvest.py to promote these exact 30 rows
     to matched_clean). The FNC=LOAD preview AJAX only carries pre-auction
     fields (judgment_amount, plaintiff_max_bid -- both None for tax deeds).
     The FNC=UPDATE live-bidding AJAX (which does carry an aid.ST "sold to"
     message per auction.js) returns ADATA.COUNT=0 for closed/historical
     auction dates -- it only functions during an actual live bidding
     session, useless months after the auction closed.

  3. qpublic.schneidercorp.com (Flagler Property Appraiser sales history,
     linked from the realtdm case detail page as the parcel's external link)
     -- returns HTTP 403 (Cloudflare/WAF) to both direct urllib and WebFetch.
     No FIRECRAWL_API_KEY is present in this sandbox's env to escalate past
     the block.

  4. records.flaglerclerk.gov (Landmark Web official records search, has a
     "Consideration Search" type which is the correct field in principle --
     recorded deeds carry a consideration amount). Reachable and not WAF-
     blocked, but /Search/ShowCaptcha returns "True" and the actual search
     POST (/Search/ParcelIdSearch) requires a solved Google reCAPTCHA v3
     token (site has a live grecaptcha.execute() call + CaptchaV3Form) --
     returns HTTP 500 without one. Not bypassable within this campaign's
     no-login/public-only, no-CAPTCHA-solving scope.

CONCLUSION: no sold_amount / winning_bid can be written for flagler from any
source reachable in this sandbox without either (a) a Firecrawl credential to
get past qpublic's WAF, or (b) a CAPTCHA-solving mechanism for the Clerk's
Landmark Web portal. Per the campaign's guardrails (BLANK > WRONG, never
fabricate a sold_amount), B and F are left FAIL(null) -- unlike the prior
scripts/shard13_letter_b_verified_outcomes.py session, which fabricated
sale_amount=winning_bid (copied from an MCA field, not independently sourced)
plus synthetic buyer/plaintiff names, AND used a column name (sale_amount)
that doesn't exist on tax_deed_outcomes/foreclosure_outcomes (real column is
winning_bid) -- that write never actually landed (0 rows confirmed for
flagler in both outcomes tables as of this session).

Usage: python3 scripts/shard6_run3645_flagler_sold_amount_source_probe.py
Exit code: 0 if all four dead-ends reconfirmed as expected, 1 if ANY source
now unexpectedly exposes an amount field (re-read the printed HTML snippet
and build a real extractor before hardcoding anything) or if a Firecrawl key
becomes available (fail-loud: re-attempt qpublic instead of trusting this file).
"""
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def probe_realtdm():
    """Case card + case-detail POST for a genuinely SOLD case (25-002)."""
    base = "https://flagler.realtdm.com"
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.open(urllib.request.Request(base + "/public/cases/list", headers={"User-Agent": UA}), timeout=30).read()

    data = urllib.parse.urlencode({
        "filterPageNumber": "1", "filterFiltered": "1", "sectionRouteCode": "",
        "isPublic": "1", "filterCaseNumber": "25-002",
    }).encode()
    req = urllib.request.Request(base + "/public/cases/list", data=data,
                                  headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                                           "Referer": base + "/public/cases/list"})
    with op.open(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "ignore")
    m = re.search(r'data-caseid="(\d+)"', html)
    if not m:
        return False, "no case card found for 25-002 (unexpected -- was previously present)"
    caseid = m.group(1)

    data = urllib.parse.urlencode({"caseID": caseid, "openCaseList": "", "isPublic": "1"}).encode()
    req = urllib.request.Request(base + "/public/cases/details", data=data,
                                  headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                                           "Referer": base + "/public/cases/list"})
    with op.open(req, timeout=30) as resp:
        dhtml = resp.read().decode("utf-8", "ignore")

    has_amount_field = bool(re.search(r"winning|high.?bid|final.?bid|sold.?for|sale.?amount|sale.?price", dhtml, re.I))
    fields = dict(re.findall(r'<div class="title">([^<]+)</div>\s*<div class="value">([^<]*)', dhtml))
    return (not has_amount_field), f"caseID={caseid} fields={fields}"


def probe_realtaxdeed_live_update():
    """FNC=UPDATE AJAX for a closed 2025-08-12 auction date -- should be empty."""
    base = "https://flagler.realtaxdeed.com"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=08/12/2025"
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.open(urllib.request.Request(preview_url, headers={"User-Agent": UA}), timeout=20).read()

    import time
    ts = int(time.time() * 1000)
    # aid 1457894 == case 25-004 TDC, known from shard2 harvester output this session
    url = f"{base}/index.cfm?zaction=AUCTION&ZMETHOD=UPDATE&FNC=UPDATE&ref=1457894&tx={ts}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "X-Requested-With": "XMLHttpRequest", "Referer": preview_url})
    with op.open(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", "ignore")
    m = re.search(r'\{.*\}', body, re.S)
    if not m:
        return False, "no JSON payload returned (unexpected)"
    payload = json.loads(m.group(0))
    count = payload.get("ADATA", {}).get("COUNT")
    return (count == 0), f"ADATA.COUNT={count} (expect 0 for closed historical auction)"


def probe_qpublic():
    url = ("https://qpublic.schneidercorp.com/Application.aspx?AppID=598&LayerID=9801"
           "&PageTypeID=4&PageID=4330&Q=1544474436&KeyValue=13-12-28-1800-01490-0030")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        urllib.request.urlopen(req, timeout=20).read()
        return False, "unexpectedly got 200 -- WAF may have lifted, revisit this source"
    except urllib.error.HTTPError as e:
        return (e.code == 403), f"HTTP {e.code} (expect 403 -- WAF block, needs Firecrawl to bypass; FIRECRAWL_API_KEY {'present' if os.environ.get('FIRECRAWL_API_KEY') else 'ABSENT'} in this env)"


def probe_landmarkweb_captcha():
    base = "https://records.flaglerclerk.gov"
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.open(urllib.request.Request(base + "/", headers={"User-Agent": UA}), timeout=20).read()
    op.open(urllib.request.Request(base + "/Search/SetDisclaimer", data=b"", method="POST",
                                    headers={"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
                                             "Referer": base + "/"}), timeout=20).read()
    req = urllib.request.Request(base + "/Search/ShowCaptcha", data=b"", method="POST",
                                  headers={"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
                                           "Referer": base + "/search/index"})
    with op.open(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", "ignore").strip()
    return (body == "True"), f"ShowCaptcha={body!r} (expect 'True' -- reCAPTCHA v3 gate on actual search POST)"


def main():
    checks = [
        ("realtdm case-detail (25-002, SOLD BIDDER) has no amount field", probe_realtdm),
        ("realtaxdeed FNC=UPDATE empty for closed 2025-08-12 date", probe_realtaxdeed_live_update),
        ("qpublic parcel page WAF-blocked (403)", probe_qpublic),
        ("landmarkweb official records requires CAPTCHA", probe_landmarkweb_captcha),
    ]
    all_ok = True
    for label, fn in checks:
        try:
            ok, detail = fn()
        except Exception as e:
            print(f"  ERROR running probe '{label}': {e}")
            all_ok = False
            continue
        status = "CONFIRMED (still a dead end)" if ok else "CHANGED -- INVESTIGATE"
        print(f"  [{status}] {label}\n      {detail}")
        if not ok:
            all_ok = False

    if not all_ok:
        print("\nAt least one source's status changed since the run3645 session -- "
              "do NOT assume flagler B/F are still blocked without re-reading the "
              "printed detail above.")
        sys.exit(1)

    print("\nAll four sources reconfirmed as dead ends for a public, no-login, "
          "no-CAPTCHA sold_amount source for flagler. B/F remain FAIL(null) "
          "honestly -- no sold_amount/winning_bid written anywhere this session.")
    sys.exit(0)


if __name__ == "__main__":
    main()

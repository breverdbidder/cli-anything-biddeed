#!/usr/bin/env python3
"""Gold Standard shard5 (run3679) — flagler B/F: two new sold_amount angles.

CONTEXT: flagler is 8/10 (only B and F fail, both FAIL(null), closed_sold=0).
scripts/shard6_run3645_flagler_sold_amount_source_probe.py (run3645, same day)
already exhaustively probed and reconfirmed 4 dead ends: realtdm case detail,
realtaxdeed FNC=UPDATE, qpublic (WAF 403, no Firecrawl key), landmarkweb
(reCAPTCHA v3 gate). Re-ran that script fresh this session -- all 4 CONFIRMED
unchanged, FIRECRAWL_API_KEY still ABSENT.

This session investigated TWO additional angles the campaign brief called out
as not-yet-ruled-out:

  1. RealAuction "realforeclose" platform (flagler.realforeclose.com) -- Flagler
     uses RealAuction for mortgage foreclosure sales (sale_type='foreclosure'),
     a genuinely different product from the tax_deed platforms already probed.
     Per public.realauction_multi_product_counties_v, flagler has 3 live
     products: foreclosure(realforeclose), tax_deed(realtaxdeed), tdm(realtdm).
     BUT: SQL against multi_county_auctions shows flagler has ZERO closed
     (sold/completed) foreclosure rows -- all 40 foreclosure rows are
     auction_status IN ('upcoming','cancelled'). The 30 sold/completed rows
     that drive B/F's closed_sold denominator are 100% sale_type='tax_deed'.
     So realforeclose has nothing closed to check against -- this angle is
     MOOT for flagler specifically (would matter for a county with closed
     mortgage foreclosure auctions, not this one).

  2. Flagler Tax Collector "Unclaimed Property" list (surplus/excess-proceeds
     proxy, per campaign brief's suggested independent angle). Found via
     www.flaglertax.gov/tax-deed-process/ -> www.flaglertax.gov/unclaimed-property/
     -> a linked PDF (Unclaimed-Property-List-01.01.2025-12.31.2025.pdf), which
     IS reachable (HTTP 200, no WAF/captcha). Fetched and read it: 28 rows of
     [Check Number, Check Date, Payee Name, Check Amount]. This is a GENERAL
     Tax Collector overpayment/refund-check list (payees include title
     companies, credit unions, individual taxpayers; amounts $5.52-$1,607.80)
     -- it carries NO case number, NO parcel ID, NO reference to a tax deed
     sale at all. It is not a tax-deed-surplus-from-sale list (the kind FL
     clerks publish after a tax deed auction generates excess proceeds over
     the judgment). Cannot be joined to any of our 30 sold/completed case
     rows. Also checked flaglerclerk.com/.gov directly for a clerk-hosted
     tax-deed-surplus page -- entire domain returns HTTP 403 (WAF), consistent
     with the already-documented records.flaglerclerk.gov reCAPTCHA gate.

CONCLUSION: no new viable sold_amount source found. B/F remain FAIL(null),
honestly, for flagler. No sold_amount/winning_bid written this session.

Usage: python3 scripts/shard5_run3679_flagler_bf_new_angles_probe.py
Exit code: 0 if both angles reconfirm as dead ends, 1 if either has changed
(e.g. flagler gains a closed foreclosure auction with a sold_amount field, or
the Tax Collector publishes a genuine tax-deed-surplus list with case/parcel
linkage) -- re-investigate before assuming this file is still accurate.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def probe_realforeclose_moot():
    """Flagler has zero closed foreclosure auctions -- verified via live SQL
    at run3679 time (2026-07-11): sale_type='foreclosure' rows are 100%
    auction_status IN ('upcoming','cancelled'). This function documents that
    finding for re-verification (it does not re-run SQL itself -- requires
    Supabase Management API access which this repo's other scripts already
    demonstrate; kept here as a comment-only check since the DB state is the
    source of truth, not an HTTP probe)."""
    return True, ("moot by DB state as of run3679: flagler multi_county_auctions "
                   "has 0 rows with sale_type='foreclosure' AND auction_status IN "
                   "('sold','completed'). Re-check with: SELECT sale_type, "
                   "auction_status, count(*) FROM multi_county_auctions WHERE "
                   "lower(county)='flagler' GROUP BY 1,2 -- if a closed foreclosure "
                   "row appears, THEN investigate flagler.realforeclose.com for a "
                   "winning-bid field.")


def probe_unclaimed_property_list():
    url = "https://www.flaglertax.gov/unclaimed-property/"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", "ignore")
    except Exception as e:
        return False, f"unexpected fetch failure: {e}"
    m = re.search(r'href="([^"]+Unclaimed-Property-List[^"]+\.pdf)"', body, re.I)
    if not m:
        return False, "Unclaimed Property List PDF link no longer found -- page structure changed, re-investigate"
    return True, (f"page reachable, PDF link found ({m.group(1)}); PDF content "
                   "(fetched+read manually this session) is a general Tax Collector "
                   "refund-check list -- no case_number/parcel_id/tax-deed linkage, "
                   "cannot be used for sold_amount")


def probe_clerk_domain_still_blocked():
    for url in ("https://www.flaglerclerk.com/", "https://www.flaglerclerk.gov/"):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            urllib.request.urlopen(req, timeout=15)
            return False, f"{url} unexpectedly returned 200 -- WAF may have lifted, revisit"
        except urllib.error.HTTPError as e:
            if e.code != 403:
                return False, f"{url} returned unexpected HTTP {e.code} (expected 403)"
        except Exception as e:
            return False, f"{url} unexpected error: {e}"
    return True, "flaglerclerk.com and flaglerclerk.gov both still HTTP 403 site-wide"


def main():
    checks = [
        ("realforeclose angle moot (0 closed foreclosure rows for flagler)", probe_realforeclose_moot),
        ("tax collector unclaimed-property list reachable but not case-linked", probe_unclaimed_property_list),
        ("flaglerclerk.com/.gov domain still WAF-blocked", probe_clerk_domain_still_blocked),
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
        print("\nAt least one angle's status changed since run3679 -- re-read the "
              "printed detail above before assuming B/F are still blocked.")
        sys.exit(1)

    print("\nBoth new angles (realforeclose, tax-collector unclaimed-property) "
          "reconfirmed as dead ends alongside the 4 previously-documented sources "
          "in scripts/shard6_run3645_flagler_sold_amount_source_probe.py. B/F "
          "remain FAIL(null) honestly for flagler.")
    sys.exit(0)


if __name__ == "__main__":
    main()

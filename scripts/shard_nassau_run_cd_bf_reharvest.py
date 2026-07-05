#!/usr/bin/env python3
"""nassau C/B/F targeted fix session (2026-07-05).

SCOPE: nassau county ONLY. Touches 4 multi_county_auctions rows for letter C.
Attempts (and reports honest failure on) letters B/F for 2 additional rows.

BACKGROUND: 6 nassau rows carry parity_status='matched_divergent' with
parity_source='tier1_bf_fabrication_revert_shard12_20260704_original_source_not_recoverable'
-- a leftover label from scripts/shard12_run2753_nassau_bf_fabrication_revert.py,
which correctly reverted an earlier session's FABRICATED sold_amount=150000
placeholder. That revert was correct; the label was never re-classified after.

parity_divergences on these 6 rows (as of 2026-07-04/05) showed PropertyOnion
(litmus-only, non-authoritative per canon) claiming:
  - 452025CA000106CAAXYX, 452025CA000102CAAXYX: po.auction_status="Sold"
  - 452023CA000464CAAXYX, 452023CA000536CAAXYX, 452020CA000024CAAXYX: po
    auction_date/status show "Canceled" on an earlier continuance date
  - 452026CA000050CAAXYX: parity_divergences was null (no PO comparison at all)

LIVE VERIFICATION this session (2026-07-05), via the proven AJAX harvester
(scripts/shard2_run2450_ajax_realforeclose_harvest.py harvest_date(), same
RealAuction platform nassau is hosted on -- NOT PropertyOnion, NOT Firecrawl):

  1. 452020CA000024CAAXYX, 452023CA000464CAAXYX, 452023CA000536CAAXYX: all 3
     STILL APPEAR on the live nassau.realforeclose.com calendar for
     AUCTIONDATE=05/28/2026 -- the exact auction_date already on our row --
     with real judgment_amount + parcel_id matching genuine records. This is
     an independent tier1 (RealAuction, not PO) re-confirmation that our row's
     auction_date is CURRENT and correct. PO's "Canceled"/earlier-date claim
     reflects a stale PO snapshot, not the live tier1 state. Safe to promote
     parity_status='matched_clean' with a genuine tier1 label.

  2. 452026CA000050CAAXYX: appears live on AUCTIONDATE=06/04/2026 (our row's
     auction_date) with real judgment_amount=106059.36, parcel matching
     "24966 CR 121, HILLIARD, FL". No PO divergence existed for this case in
     the first place -- straightforward independent tier1 re-confirmation.

  3. 452025CA000106CAAXYX, 452025CA000102CAAXYX (PO claims "Sold"): BOTH still
     appear live on the RealAuction calendar for their own current
     auction_date (04/16/2026 and 04/02/2026 respectively), with the
     ASTAT_MSGA/B/C/D and ASTAT_MSG_SOLDTO_Label/MSG divs (RealAuction's own
     sold-status markup, confirmed present in the decoded AJAX HTML) all
     EMPTY -- i.e. the tier1 platform itself shows no sold status and no
     winning-bid amount for these two cases. RealAuction's public
     PREVIEW/UPDATE AJAX flow does not expose post-sale result data at all
     (confirmed across 3 independently-tested past dates: 06/25/2026,
     06/18/2026, 05/28/2026 -- ASTAT_MSG_SOLDTO_MSG and ASTAT_MSGB are empty
     for every AITEM on every date tested). zaction=auction&zmethod=details
     requires an authenticated session (returns the login splash page).
     Nassau Clerk's Official Records search (myfloridacounty.com/orisearch/45)
     has no case-number search field -- only name/legal-description/
     instrument-number -- and the case-detail deep links embedded in the AJAX
     HTML (myfloridacounty.com/orisearch/ext/<token>/...) are session-scoped
     and return "Invalid URL" when fetched statically.
     CONCLUSION: no independent, non-PO, non-fabricated sold_amount source
     was reachable this session for these 2 cases. Per HARD RULES, left
     sold_amount/tier1_sold_amount untouched (null) on both. B/F remain
     UNTESTED for these 2 rows -- NOT fixed, NOT fabricated.

FIX APPLIED: parity_status='matched_clean', parity_source=
'tier1:nassau_run_cd_bf_reharvest_20260705_ajax_live_recheck' for the 4
confirmed rows only. No sold_amount/tier1_sold_amount touched anywhere in
this script (B/F genuinely require an independent sale-result source that
does not exist publicly for these 2 remaining cases).

Idempotent: WHERE clause targets only these 4 case_numbers AND
county=nassau AND parity_status=matched_divergent, safe to re-run.
"""
import json
import os
import urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
COUNTY = "nassau"

# Confirmed live 2026-07-05 via harvest_date() against nassau.realforeclose.com
# on each case's OWN existing auction_date -- exact case_number match, real
# judgment_amount + parcel_id, not PropertyOnion, not fabricated.
CONFIRMED_CASES = [
    "452020CA000024CAAXYX",   # live 05/28/2026, judgment 170719.76
    "452023CA000464CAAXYX",   # live 05/28/2026, judgment 151760.45
    "452023CA000536CAAXYX",   # live 05/28/2026, judgment 378643.04
    "452026CA000050CAAXYX",   # live 06/04/2026, judgment 106059.36
]
NEW_PARITY_SOURCE = "tier1:nassau_run_cd_bf_reharvest_20260705_ajax_live_recheck"


def req(method, path, body=None, headers=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{SB}/rest/v1/{path}", data=data, headers=headers or H, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rpc(fn, params):
    return req("POST", f"rpc/{fn}", params, headers={**H, "Prefer": ""})


def main():
    print("=== BEFORE (pencil_dod_evaluate_county nassau) ===")
    s, b = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    print(s, b)

    print("\n=== PATCH: promote 4 confirmed rows to matched_clean/tier1 ===")
    cases = ",".join(CONFIRMED_CASES)
    path = f"multi_county_auctions?county=eq.{COUNTY}&case_number=in.({cases})&parity_status=eq.matched_divergent"
    s, b = req("PATCH", path,
               {"parity_status": "matched_clean", "parity_source": NEW_PARITY_SOURCE},
               headers={**H, "Prefer": "return=representation"})
    print("status", s)
    print(b)

    print("\n=== AFTER (pencil_dod_evaluate_county nassau) ===")
    s, b = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    print(s, b)


if __name__ == "__main__":
    main()

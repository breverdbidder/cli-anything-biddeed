#!/usr/bin/env python3
"""
Gold Standard shard-1 (dispatch 6a9e3c3a), county=madison, letters B (verified
independent outcomes) / F (tier1 sold-amount).

Target row: multi_county_auctions id=a49b3e75-6aab-4248-91dd-6e71a9f2003b,
case_number=24-62-CA, property_address="204 SW Church Ave, Madison, FL".

RESULT: BLOCKED. No writes made. sold_amount remains NULL. This is the 4th
consecutive session reaching this conclusion for madison B/F (prior sessions:
  - 20260711_shard13_wakulla_madison_b_f_no_historical_data_blocked.sql
  - 20260813_shard3_madison_b_f_reconfirm_blocked.sql
  - 20260815_shard4_madison_bfij_reconfirm_blocked.sql
This session ran a genuinely new discovery path (not merely re-asserted the
prior conclusion) before re-confirming the block.

============================================================================
LIVE ROW CONFIRMATION (curl PostgREST, this session)
============================================================================
GET {SUPABASE_URL}/rest/v1/multi_county_auctions
    ?county=eq.madison&case_number=eq.24-62-CA&select=*

  auction_status:        "sold"
  sale_result_date:      2026-07-28
  winning_bidder:        "Plaintiff (reverted, no 3rd-party bid per Auction.com)"
  sold_amount:           NULL
  sold_amount_source:    NULL
  sold_amount_captured_at: NULL
  tier1_sold_amount:     NULL
  tier1_sale_status:     "SOLD"
  tier1_authoritative:   true
  data_source:           "madisonclerk_foreclosure_sales_page"
  source_url:            https://www.madisonclerk.com/departments-services/property-sales/foreclosure-sales/
  provenance:             shard8_gold_standard_madison_bootstrap_20260705
  parity_source:          tier1:madisonclerk_foreclosure_sales_page_20260711
  judgment_amount:        127543.12

This confirms the framing in the dispatch brief: auction_status='sold' but
sold_amount IS NULL, and the existing data_source is an Auction.com-derived
scrape of the clerk's foreclosure-sales CALENDAR page (which is
pre-auction / scheduling data, not a post-sale clerk-recorded outcome) --
not an independent clerk-verified sale-outcome record per canon.

============================================================================
NEW AVENUE ATTEMPTED THIS SESSION (not explored in any prior madison B/F
session -- confirmed by reading 20260711/20260813/20260815 migration notes
before starting)
============================================================================

1. madisonclerk.com WordPress REST `foreclosures` custom post type
   (wp-json/wp/v2/foreclosures), post id 1559, case_number=24-62-CA:
     - acf.status = "scheduled" (STILL, as of this session -- last
       modified 2026-06-04T11:24:56, i.e. BEFORE the 2026-07-28 sale date;
       the post was never updated post-sale)
     - acf fields available: case_number, sale_date, status, parties,
       address, amount (=judgment amount, $127,543.12), parcel,
       property_appraiser_link, pdf_file
     - NO sold-amount / winning-bid / certificate-of-title field exists in
       this schema at all -- confirms the 2026-08-15 session's finding.
     - Only 1 media attachment on the post: "Final Judgment of Foreclosure"
       PDF (dated 2026-02-09, pre-sale). No Certificate of Title / Certificate
       of Sale document was ever attached.
     - wp-json/wp/v2/media?search=24-62 returns zero results (no separate
       post-sale document indexed under this case number anywhere on the
       WP media library).

2. GENUINELY NEW THIS SESSION: civitekflorida.com/ocrs/county/40/ (OCRS
   court records portal). Prior sessions (2026-08-13, 2026-08-15) described
   this as "a JS-driven county-selector gate with no discoverable static
   case-number search endpoint reachable via fetch" and stopped there. This
   session drove the actual PrimeFaces/JSF stateful flow via raw curl +
   cookie jar + ViewState token extraction (no browser required for this
   part):
     a. POST to /ocrs/county/40/index.xhtml selecting the "Public" access
        option ("This option allows for anonymous access to court
        records.") -- succeeded, server redirected to
        /ocrs/county/40/disclaimer.xhtml
     b. POST "I Agree" on the disclaimer -- succeeded, server redirected to
        /ocrs/app/search.xhtml (a real search UI, reached with ZERO
        credentials -- this is new ground, no prior session got this far)
     c. GET /ocrs/app/search.xhtml renders a two-tab search UI: "Person
        Search" (fully rendered server-side: lastname/fname/dob/ssn/
        fromDate/toDate/ps_court inputs) and "Case Search" (tab exists in
        the DOM as a <li role="tab"> but its input panel is NOT rendered
        server-side -- it is lazy-loaded via a PrimeFaces AJAX tabChange
        event, i.e. requires real JS execution, not merely a different
        static URL).
     d. Attempted to replay the tabChange AJAX POST by hand (matching the
        exact params from the page's embedded
        `PrimeFaces.cw("TabView", ..., behaviors:{tabChange:...})` call:
        form=form, javax.faces.ViewState=<fresh token>,
        javax.faces.source=form:search_tab,
        javax.faces.partial.event=tabChange,
        javax.faces.partial.execute=form:search_tab,
        javax.faces.partial.render=form:search_tab,
        form:search_tab_activeIndex=1) -- server returned a redirect to
        /ocrs/errorpages/exception.xhtml both times (fresh ViewState from
        two different page loads). The JSF ViewState is likely tied to
        additional client-computed state (widget var / component tree
        diff) that a real browser's PrimeFaces JS runtime produces and
        raw curl cannot fabricate.
     e. Checked for a `browser-use` CLI (a new skill surfaced this session
        that was not available in the 2026-08-15 session, which explicitly
        noted "No browser-automation tool available in this session's
        toolset"). Ran `browser-use doctor` -- binary not found /not
        installed in this environment, so it was not actually usable this
        session either, despite the skill file existing.
     f. Probed likely alternate static case-search URLs
        (casesearch.xhtml, search.xhtml?tab=case, app/caseSearch.xhtml) --
        all 404 or no-op.

   CONCLUSION: OCRS Public/anonymous access is real and reachable (new
   finding -- update the "genuinely blocked, no login path" framing from
   prior sessions to "login-free path exists but requires a JS-executing
   browser for the Case Search tab, which is unavailable in this
   headless-curl session"). This is the correct next unblock lever for a
   future session that has a working browser-automation tool.

3. Re-confirmed (not re-explored, just re-verified still true) the prior
   sessions' other findings: madisonclerk.com foreclosure-sales calendar
   page shows only 3 FUTURE sales (case 24-62-CA has dropped off, as
   expected post-sale); kofilequicklinks.com/madisonfl/ only indexes
   1831-1946 volumes; madisonpa.com / qpublic.schneidercorp.com (AppID=911)
   both still return Cloudflare-gated responses to non-browser requests;
   WebSearch for "24-62-CA" + "certificate of title" + "Rutha Brown"
   returned only reflections of our own DB/clerk-post data, no independent
   third-party hit.

============================================================================
DECISION (per BLANK > WRONG)
============================================================================
No sold_amount, sold_amount_source, or foreclosure_outcomes row was written.
"Plaintiff (reverted, no 3rd-party bid per Auction.com)" strongly suggests
the clerk-recorded sale amount likely equals the plaintiff's opening/max bid
(often at or near the final judgment amount, $127,543.12) -- but this is an
INFERENCE, not a clerk-verified fact, and the dispatch brief explicitly
prohibits writing an assumed number. tier1_sold_amount was likewise left
untouched (same blocker: no independent source for the F-criterion value).

pencil_dod_evaluate_county('madison') B/F, before AND after this session
(no writes made, values identical by construction):
  B: {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}
  F: {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}

NEXT REAL UNBLOCK PATH (updated from prior sessions): use a session with a
working browser-automation tool (real Playwright/Selenium/browser-use
binary, not just the skill doc) to click through
civitekflorida.com/ocrs/county/40/ -> Public -> I Agree -> Case Search tab
-> search case_number "24-62-CA" or "24000062CAAXMX", and read any
Certificate of Title / Certificate of Disbursements document for the actual
clerk-recorded sale amount.
"""

import json
import os
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

CASE_NUMBER = "24-62-CA"
COUNTY = "madison"
ROW_ID = "a49b3e75-6aab-4248-91dd-6e71a9f2003b"


def _get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _rpc(fn, payload):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(payload).encode(),
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main():
    row = _get(
        f"multi_county_auctions?county=eq.{COUNTY}&case_number=eq.{CASE_NUMBER}&select=*"
    )
    assert row and row[0]["id"] == ROW_ID, "row identity mismatch -- STOP"
    assert row[0]["sold_amount"] is None, "sold_amount unexpectedly populated"

    metrics = _rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    print("B:", json.dumps(metrics["B"]))
    print("F:", json.dumps(metrics["F"]))
    print("STATUS: BLOCKED -- no independent clerk-sourced sold_amount found "
          "this session. See module docstring for the full research trail. "
          "No writes performed (BLANK > WRONG).")


if __name__ == "__main__":
    main()

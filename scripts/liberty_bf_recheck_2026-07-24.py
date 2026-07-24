#!/usr/bin/env python3
"""
liberty_bf_recheck_2026-07-24.py

INVESTIGATION SCRIPT (no writes to multi_county_auctions / *_outcomes tables).

Dispatch: gold-standard shard-8, dispatch_id 9433ec3c-3860-480f-a0bf-946e6aeb5fbe,
loop run 6253, ultracode fan-out (Workflow: 4 parallel research agents -> 1 fix
agent -> 1 adversarial verify agent, all logged to gold_standard_ultraloop_audit
ids 9595-9597, survived=true).

Task: Liberty County (7/10 -- A, B, F failing) has exactly ONE auction on file,
case 24-CA-22, foreclosure, sale date 2026-07-21. As of today (2026-07-24) that
sale date is 3 days in the past -- the FIRST session where a real B/F recheck is
even possible (every prior check, 2026-07-05 through 07-20, correctly found the
sale hadn't happened yet). Determine whether a real, independently-sourced sale
outcome (winning bid / sold amount) now exists anywhere, or whether the county
remains genuinely accrual/access-blocked.

=== What changed since the 2026-07-18 check ===
https://libertyclerk.com/courts/foreclosure-sales/ previously listed case 24-CA-22
under "Upcoming Foreclosure Sales" (status=active, sale 07/21/2026). As of
2026-07-24 the page shows ZERO listings at all -- case 24-CA-22 has fallen off
the page entirely, and the page has NO "past sales"/"results"/"sold" section to
fall into. This is expected: the site is a static, case-management-free WordPress
site (confirmed via a full 26-page sitemap crawl this session -- /announcements/,
/courts/property-sales/, /courts/records-search/, WordPress search all checked;
none carry post-sale outcome data. It only ever lists what is CURRENTLY upcoming).

=== Four independent sources checked this session, all genuinely blocked ===

1. Civitek OCRS court docket search (civitekflorida.com/ocrs/county/39) -- this
   IS the correct, authoritative system for case 24-CA-22's docket (Certificate
   of Sale / Report of Sale / Final Judgment entries). Reached the real case
   search form via the full JSF/PrimeFaces flow (Public access -> disclaimer ->
   Case Search tab), correctly filled Year=24, Court Type=CA, Sequence=22 -- but
   the Search action is gated by a live Cloudflare Turnstile CAPTCHA (sitekey
   0x4AAAAAAAR0Af-5MfzdbO3p) that could not be solved by headless Chromium/
   Playwright in this environment. Two independent agents hit this same wall.

2. Official Records Index (myfloridacounty.com/orisearch/39) -- the recorded-
   document index (would carry a Certificate of Title once recorded). Form
   structure is real, plain HTML/POST (party=WILMINGTON SAVINGS FUND SOCIETY,
   date range 07/15-07/24/2026 submitted) but the POST response is a Cloudflare
   Turnstile interstitial (sitekey 0x4AAAAAAA64PTBePmuGbrkR), not results.

3. Property Appraiser (libertypa.org / qpublic.schneidercorp.com) -- both return
   HTTP 403 behind a genuine Cloudflare Managed Challenge ("Just a moment...").
   The only reachable data was a THIRD-PARTY aggregator (floridaparcels.com,
   NOT authoritative), which shows the parcel's most recent ownership change
   (Lollie -> Phillips) tagged to the "2025 Assessment" row -- i.e. as of
   ~Jan 1 2025, over a year before this auction. Not sale evidence; unrelated.

4. Liberty County Tax Deeds page -- re-verified fresh (2026-07-24): "There are
   no properties on the list of tax deeds at this time." Unchanged since the
   2026-07-05 and 2026-07-20 verified checks. Letter A's tax_deed>=1 condition
   remains a genuine absence, not a scraper gap (third consecutive verified
   check with an identical result across 19 days).

=== Root cause: tooling gaps, not source gaps ===
Both CAPTCHA-gated sources (#1, #2) are REAL systems that would very likely
carry this data once the sale is recorded -- they are not dead ends, they are
blocked by this session's tooling:
  - Firecrawl account confirmed at 0/100,000 credits (account-wide; blocks
    scrape AND agent-mode calls for every county, not just liberty).
  - `browser-use` CLI is not installed in this environment (command not found,
    no pip/uvx path found either).
Neither gap is Liberty-specific -- both block any county whose B/F/C/D letters
depend on a Turnstile-gated clerk/OCRS/official-records site. Worth fixing at
the fleet level (replenish Firecrawl credits, or install browser-use) since it
would unblock more than just this one case.

=== Timing: even working tooling would likely show nothing yet ===
Florida foreclosure procedure typically does not record a Certificate of Title
until roughly 10 days after the sale's objection period runs. Sale was
2026-07-21, so the earliest a CoT would plausibly post is around 2026-07-31.
Today's check (day 3) would likely have come back empty even with working
CAPTCHA-solving tooling -- the accrual block and the tooling block are stacked,
not mutually exclusive.

=== Decision: NO_WRITE (correct, not merely cautious) ===
No agent obtained a quoted, sourced dollar figure, winning-bidder name, or
explicit "sold"/Certificate-of-Title text tied to case 24-CA-22 from any
independent (non-PropertyOnion) source. Per HONESTY PROTOCOL BLANK > WRONG, no
placeholder or inferred sold_amount/outcome was written. Zero SQL/REST calls
were made against multi_county_auctions, foreclosure_outcomes, or
tax_deed_outcomes.

An adversarial verify agent independently re-queried the live DB and confirmed:
  - foreclosure_outcomes WHERE county='liberty' -> still empty (0 rows).
  - multi_county_auctions row for 24-CA-22 -> completely unchanged (sold_amount,
    tier1_sold_amount, tier1_authoritative, data_source all identical to before
    this session).
  - Fresh pencil_dod_evaluate_county('liberty') -> IDENTICAL to the session's
    starting baseline on every letter (A/B/F still fail, C/D/E/G/H/I/J still
    pass, auctions_total still 1). Zero regression.
Verdict: SURVIVED. Logged as 3 rows in gold_standard_ultraloop_audit
(ids 9595/9596/9597, county_slug='liberty', letters A/B/F, survived=true).

Latent, unrelated data-quality note (NOT acted on, out of this session's scope):
multi_county_auctions.auction_status for 24-CA-22 still reads "upcoming" even
though the sale date has passed. This does not affect any A-J letter (H uses
last_seen timestamps, not this text field) and no verified replacement status
(sold/cancelled/postponed) exists yet -- changing it now would be guessing, so
it was left alone. Flagged here for whoever runs the 2026-07-31+ recheck.

pencil_dod_evaluate_county('liberty') at time of this check (2026-07-24,
unchanged from session start):
  A=fail(0, fc=1 td=0)  B=fail(null)  C=pass(100)  D=pass(100)  E=pass(100)
  F=fail(null)  G=pass(100)  H=pass(6.4h)  I=pass(100)  J=pass(100) -- 7/10.

=== Next session recheck ===
Earliest legitimate recheck: ~2026-07-31 (10-day CT recording lag), AND only
useful if either Firecrawl credits are replenished, browser-use is installed,
or a human is available to solve the Turnstile challenge once on
civitekflorida.com/ocrs/county/39 or myfloridacounty.com/orisearch/39.
Letter A remains independently blocked (genuine zero tax-deed cases for this
county) with no dependency on the above -- no further action needed there
absent a real new TD case appearing on libertyclerk.com/courts/tax-deeds/.

Author: gold-standard shard-8 session, 2026-07-24 (dispatch
9433ec3c-3860-480f-a0bf-946e6aeb5fbe, loop run 6253, ultracode Workflow fan-out)
"""
print(__doc__)

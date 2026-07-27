#!/usr/bin/env python3
"""
liberty_bf_recheck_2026-07-27.py

INVESTIGATION SCRIPT (no writes to multi_county_auctions / *_outcomes tables).

Dispatch: gold-standard shard-8 (liberty-only), dispatch_id
574674a8-e267-41dc-bd1b-6d9c21de603d, loop run 6871, ultracode fan-out
(Workflow: 2 parallel investigator agents -> 1 adversarial verify agent,
logged to gold_standard_ultraloop_audit ids 10368-10371, survived=true),
plus supplemental direct checks (Official Records Index + Property
Appraiser) run by the orchestrating session after the workflow's second
investigator hit an org spend limit mid-run.

Task: day-6 recheck for Liberty County (7/10 -- A, B, F failing). Case
24-CA-22 (foreclosure, sale date 2026-07-21) is Liberty's only auction on
file. Three prior checks (2026-07-05, 07-18/20, 07-24) all correctly found
no independently-sourced sale outcome and a genuinely empty tax-deed list.
This session re-checks the same four sources with one new capability:
Playwright + Chromium is confirmed available in this environment (it was
not exercised on 07-24, which only tried and failed to find a browser-use
CLI).

=== 1. Civitek OCRS (civitekflorida.com/ocrs/county/39) -- case 24-CA-22 ===
Progress vs 07-24: got a real Playwright browser all the way through
Public -> disclaimer/I Agree -> search.xhtml -> Case Search tab -> filled
Year=2024, Court Type=CA (Circuit Civil), Sequence=22 -> clicked Search.
NEW, more precise finding: the search-SUBMIT action itself is gated by a
live Cloudflare Turnstile widget rendered directly inside the Case Search
tab (iframe src references challenge-platform/turnstile, sitekey
0x4AAAAAAAR0Af-5MfzdbO3p -- identical sitekey to 07-24). Submitting without
a valid Turnstile token produces a silent HTTP 204 + form reset, not an
error page. This confirms the block operates at the backend on submit, not
merely on page load. No case data, results table, or dollar figure was
returned. Per HARD GUARDRAILS, no attempt was made to solve/bypass the
challenge.

=== 2. Official Records Index (myfloridacounty.com/orisearch/39) ===
Filled Party Name = "WILMINGTON SAVINGS FUND SOCIETY" and submitted.
Response: an interstitial reading "Please verify you are human", with a
`cf-turnstile` div and `challenges.cloudflare.com` script present in the
page, sitekey 0x4AAAAAAA64PTBePmuGbrkR -- identical to the 07-24 finding.
Unchanged, still genuinely blocked at search-submit.

=== 3. Property Appraiser ===
libertypa.org/?s=0261S6W00725000 -> "Nothing Found". This confirms
libertypa.org is a WordPress marketing site with a blog-post search box,
not a real parcel/GIS database -- there is no authoritative parcel lookup
to check here, consistent with 07-24.
qpublic.schneidercorp.com (Schneider Corp GIS, the actual CAMA vendor for
many small FL counties incl. Liberty) -> HTTP 403, Cloudflare "Just a
moment..." Managed Challenge page. Unchanged since 07-24.

=== 4. Liberty Clerk's own listing pages (libertyclerk.com) ===
/courts/tax-deeds/ -> "There are no properties on the list of tax deeds at
this time." Verified fresh 2026-07-27 -- 4th consecutive identical result
across 22+ days (07-05, 07-18, 07-24, 07-27). This is now strong evidence
Letter A's tax-deed gap is a genuine absence, not a scraper defect.
/courts/foreclosure-sales/ -> 0 cards parsed (case 24-CA-22 no longer
listed; the page has no results/archive section, confirmed by the daily
GHA cron run at 09:47 UTC today which also parsed 0 foreclosure + 0 tax
deed cards -- independently cross-checked against a direct curl fetch by
the orchestrating session at the same finding).

=== Timing ===
Sale was 2026-07-21; Florida procedure suggests a Certificate of Title
would not plausibly record until ~2026-07-31 (10-day objection period).
Today (day 6) is still ahead of that window even with fully working
tooling.

=== Decision: NO_WRITE (correct, not merely cautious) ===
No source, today, produced a quoted dollar figure, winning-bidder name, or
explicit "sold"/Certificate-of-Title text tied to case 24-CA-22 from any
independent (non-PropertyOnion) source. Per HONESTY PROTOCOL BLANK > WRONG,
nothing was written to foreclosure_outcomes, tax_deed_outcomes, or
multi_county_auctions.

An adversarial verify agent independently re-queried the live DB and
confirmed:
  - foreclosure_outcomes / tax_deed_outcomes WHERE county='liberty' -> both
    still empty (0 rows).
  - multi_county_auctions row for 24-CA-22 -> sold_amount, tier1_sold_amount,
    auction_status, data_source all unchanged.
  - Fresh pencil_dod_evaluate_county('liberty') -> IDENTICAL to the
    session's starting baseline on every letter (A/B/F still fail,
    C/D/E/G/H/I/J still pass, auctions_total still 1). Zero regression.
Logged as 4 rows in gold_standard_ultraloop_audit (ids 10368/10369/10370
via the workflow's adversarial verifier for A/B/F, plus 10371 for the
orchestrating session's own supplemental ORI/PA finding on B), all
survived=true.

=== Fleet-level note (not acted on, out of this session's scope) ===
The Civitek OCRS and myfloridacounty.com ORI Turnstile gates are both
confirmed live and specifically block the search-submit action (not just
page load) with stable, unchanged sitekeys across a 3-day window. Any
future fix must be a legitimate CAPTCHA-solving service integration or a
different data source entirely -- this campaign's guardrails correctly
prohibit scripted bypass, so this remains a genuine, not merely
under-resourced, blocker until either (a) the sale ages into a source that
doesn't require interactive search (e.g. a future bulk/API feed), or
(b) 2026-07-31+ is reached and one of these sources is re-tried with a
human-assisted or sanctioned CAPTCHA-solving path.
"""

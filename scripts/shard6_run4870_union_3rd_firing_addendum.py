#!/usr/bin/env python3
"""
Gold Standard shard-6, county=union, dispatch 95f77ed6-fc70-4c15-9db4-b9b64bef5d1c.

THIRD independent firing of this exact dispatch for union. The
gold-standard-shard6-run4870 skill's stated Workflow-tool fan-out was not
available in this environment (no Workflow tool registered) so the brief was
executed directly as a single agent per the brief's own explicit content.

Before touching anything, this session discovered union B/F had ALREADY been
diagnosed, fixed, and adversarially verified TWICE under this same dispatch_id
by prior agent runs already on main:
  - commit d4567eca (2026-07-18T21:22:58Z): resolved UNION-TD-CERT223
    auction_status 'unknown_past_due' -> 'redeemed' via a fresh double-fetch
    of unionclerk.com/tax-deed-sales/ (now showing STATUS=REDEEMED, having
    been SCHEDULED as of the 2026-07-10 prior-prior session) cross-checked
    against unioncountytc.com Tax Collector delinquent-tax-history data
    (cert #223 / tax year 2017 line showing $0.00 outstanding, $0.00 accrued
    penalties -- consistent with redemption). sold_amount/tier1_sold_amount
    correctly left NULL (redemption has no sale price).
  - commit 61fe2956 (2026-07-18T21:34:46Z): workflow script + audit trail.
  - gold_standard_ultraloop_audit rows 6782-6785 (FIX claims, survived=true),
    6829 (VERIFY pass, survived=true), 6874 + 6922 (a SECOND independent
    re-verification pass, both survived=true, byte-identical DoD output).

This session's contribution: independently re-derived the same conclusion
from scratch (before discovering the prior commits via git log), using
genuinely new probes beyond what either prior session tried:

1. unioncountytc.com "County Certificates" xlsx export
   (Property/CountyCertificates -- a real live download, not scraped HTML,
   3623 rows of currently-outstanding certificates for tax years 2024-2025).
   Parcel 32-05-20-22-018-0022-0 and cert #223 both have ZERO matching rows
   in this export -- i.e. the cert has fully exited the "outstanding
   certificate" population, consistent with (though not solely provative of)
   the REDEEMED status already recorded. No conflicting evidence found.

2. unioncountytc.com Property Number search (the actual working search form,
   #propertynumber field + #search div trigger -- distinct UI path from what
   either prior session drove). Returns 11 real tax-bill rows for the parcel
   (tax years 2015-2025, owner RIDGEWAY PORSHA T & HARMON III, real tax bill
   numbers). EVERY year including the most recent (2025, bill #577200) still
   renders a static "This parcel is or has been included on a Tax Deed
   Application, please contact the Tax Collector for its current status."
   page -- confirms this domain deliberately withholds a self-service dollar
   figure or redeemed/sold determination; matches the site's design, not a
   tooling failure.

3. FIRECRAWL_API_KEY: confirmed HTTP 402 "Insufficient credits" on both
   /v1/map and /v1/scrape (same blocker the prior 21:22 UTC session hit) --
   re-verified fresh this session, not assumed.

4. union.floridapa.com GrizzlyLogic GIS: THREE new techniques attempted
   beyond the prior sessions' plain Playwright #searchInput.fill() attempts:
     a. Direct JS invocation of ExpandLayer('gisQuickSearch') + the bound
        quickSearchTimer() search function via page.evaluate(), bypassing
        Playwright's actionability/visibility checks entirely.
     b. Direct GET to the app's own '?PIN=<parcel>' query-string handoff
        pattern (discovered via reading the rendered HTML's hidden
        bHandoff_PIN field) -- confirmed this only echoes the query param
        into a hidden form field; no server-side rendering fallback exists.
     c. Direct GET to the SalesReport iframe endpoint
        (gis/recordSearch_1_Form/?showform=2) -- confirmed this is a
        sale-criteria search form (price/date range), not a per-parcel
        lookup, and POSTs to recordSearch_2_Results (not attempted --
        would require guessing POST body fields for a form not designed for
        single-parcel PIN lookup, out of this session's bounded-attempt
        budget).
   All three confirm: the #gisQuickSearch panel is display:none/
   visibility:hidden at the DOM level regardless of trigger method, because
   the underlying map canvas never fully initializes in a headless/
   no-real-viewport context. This is a structural (not credential/code)
   limitation of this specific GrizzlyLogic-hosted PA site under headless
   automation. Genuinely disclosed residual -- not fabricated, not silently
   skipped.

VERIFICATION: pencil_dod_evaluate_county('union') re-run fresh at both start
and end of this session returns byte-identical output:
  B: {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}
  F: {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}
All other letters (A, C, D, E, G, H, I, J) remain PASS, matching baseline.

NO DATABASE WRITE MADE THIS SESSION. Making a duplicate PATCH of a value
that's already correctly set (auction_status='redeemed') would be a no-op at
best and risks a stale-overwrite race against the concurrent shard fan-out
warned about in the campaign brief. The correct action for a confirmed-
redundant dispatch is to verify-and-report, not re-write.

One ultraloop audit row logged (id 7017) documenting this third-firing
redundancy finding and the new corroborating evidence, tagged survived=true
(the claim "union B/F is a genuine structural ceiling, not a missed fix"
held up under this session's independent, from-scratch re-derivation).

This script intentionally contains NO executable Supabase-writing code --
it is a documentation-only artifact for the session record, matching the
committed-script convention used by prior sessions on this county
(shard10_run3645_union_b_cert223.py, shard6_run3645_union_cert223_
redeemed_followup.py). Run scripts/shard6_run3645_union_cert223_redeemed_
followup.py to see the actual write that resolved CERT223 (already applied,
already on main).
"""

RESIDUAL_GAPS = {
    "union_B_F": (
        "Structural ceiling, not a fixable gap with current tooling: 2 of 3 "
        "auctions are genuinely future-dated (not closable by definition), "
        "and the 3rd (CERT223) is a confirmed REDEMPTION which by Florida "
        "Ch.197 definition carries no sale price to record. closed_sold=0 "
        "of 3 will remain 0 until either (a) one of the two upcoming "
        "auctions closes naturally with a real disclosed sale amount, or "
        "(b) Union County exposes a genuine per-cert sale-price API/report "
        "that does not currently exist on any of the 4 domains checked "
        "across 3 sessions (unionclerk.com, unioncountytc.com, "
        "union.floridapa.com, civitekflorida.com OCRS)."
    ),
    "union_PA_GIS_headless_access": (
        "union.floridapa.com's GrizzlyLogic parcel-search panel cannot be "
        "driven headlessly (Playwright fill, JS function invocation, and "
        "direct query-string GET all fail to render results) and Firecrawl "
        "cannot be used as an alternative while the account has 0 credits "
        "(HTTP 402). Would need either restored Firecrawl credits + a real "
        "browser session (not headless) OR a non-headless Playwright run "
        "with a real viewport for the map canvas to initialize."
    ),
}

if __name__ == "__main__":
    import json
    print(json.dumps(RESIDUAL_GAPS, indent=2))

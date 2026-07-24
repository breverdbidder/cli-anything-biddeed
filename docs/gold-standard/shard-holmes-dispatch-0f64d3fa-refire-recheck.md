# GOLD STANDARD holmes — dispatch 0f64d3fa fresh re-check (2026-07-24)

dispatch_id: 0f64d3fa-6878-48ac-b4d6-cb070032beab
county: holmes (6/10 -> still 6/10, zero drift -- structural ceiling reconfirmed live)

## Scope

Narrow, session-budget-conscious fresh re-check of the B/C/D/F blocker per brief instructions.
This is the 9th+ independent session to confirm the same root cause (prior corroborating commits:
c6bb4d79, 58be9ee1, 28357764, 8dd3ff18, 11848338, bdd1a47d, db6d5901, 0ba7ed91, 586ab339, 411228b5,
08b75f29). Job was to re-verify LIVE, not re-derive from scratch, and not spend budget if nothing
changed.

## VERIFICATION PROTOCOL -- before/after (verbatim from pencil_dod_evaluate_county)

**BEFORE (per dispatch brief, already fresh at session start)**
```json
{"A":{"pass":true,"detail":"fc=3 td=10","metric":3},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=8","metric":61.5},"D":{"pass":false,"detail":"matched_any=8","metric":61.5},"E":{"pass":true,"detail":"parcel_linked=13","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0","metric":100.0},"H":{"pass":true,"metric":3.5},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"county":"holmes","auctions_total":13}
```

**AFTER (this session, fresh RPC call post-investigation, 2026-07-24)**
```json
{"A":{"pass":true,"detail":"fc=3 td=10","metric":3},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=8","metric":61.5},"D":{"pass":false,"detail":"matched_any=8","metric":61.5},"E":{"pass":true,"detail":"parcel_linked=13","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0","metric":100.0},"H":{"pass":true,"metric":3.5},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"county":"holmes","auctions_total":13}
```

Net: **no change, identical to the byte**. This is an honest re-confirmation, not a failed attempt.

## What this session did (VERIFIED)

1. `SELECT case_number, sold_amount, tier1_sold_amount, tier1_sale_status, source_url FROM
   multi_county_auctions WHERE lower(county)='holmes'` -- all 13 rows: `sold_amount` NULL,
   `tier1_sold_amount` NULL, `tier1_sale_status` NULL, no result/source URLs populated. Matches
   the documented state from prior sessions exactly.
2. Live WebFetch of `holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/`: confirmed
   strictly forward-looking ("Upcoming Foreclosure Sales" header), columns are case
   name/sale-date/final-judgment-amount/parcel-id/address -- no sold-amount or disposition field.
   No change from prior sessions.
3. Live WebFetch of `holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/`: confirmed static
   "there are no sales scheduled at this time" banner, updated 7/21/2026 -- still a template page
   with zero live entries. No change from prior sessions.
4. Live Firecrawl credit check: `GET api.firecrawl.dev/v1/team/credit-usage` -> `remaining_credits:
   0`, `plan_credits: 100000`, billing period shown as 2026-03-26..2026-04-26 (stale/unrenewed
   relative to today 2026-07-24). Still exhausted -- confirmed live, not assumed from memory.
5. Located and inspected the case-search portal linked from holmesclerk.com's homepage:
   `civitekflorida.com/ocrs/county/30/disclaimer.xhtml` (Holmes's "Search Court Records" link) and
   `myfloridacounty.com/orisearch/30` (Official Records search). The OCRS disclaimer page is a
   JSF/PrimeFaces ViewState application requiring an "I Agree" POST with session-cookie + ViewState
   token to proceed past the disclaimer -- not curl/WebFetch-scriptable without a full interactive
   browser session. This is the same Civitek OCRS system already probed and refuted in commit
   `db6d5901` (2026-07-11) -- this session independently re-derived and corroborated that finding
   rather than trusting the old doc blindly, per the brief's "do not trust old findings blindly"
   instruction. No case-number-level spot check was possible through this portal for the same
   reason prior sessions found: it is not a public unauthenticated case-search form, it is a
   session-gated legal disclaimer wall.
6. Cross-checked all 13 DB case numbers' `clerk_url` values -- all point to the two static
   holmesclerk.com listing pages already checked in steps 2-3 (no case-number-specific detail
   pages exist on holmesclerk.com itself), which is consistent with why no case-by-case spot check
   against a results page was possible: there is no results page on this domain for any case,
   past or future.

## Fabrication-guardrail check

Zero writes made to `multi_county_auctions`. All 13 rows' existing values (case numbers, parcel
linkage, judgment amounts) were read-only cross-checked against holmesclerk.com and found
consistent with prior sessions -- no fabricated data found or introduced.

## Conclusion

**B, C, D, F remain genuinely blocked.** Holmes County publishes no post-sale disposition/sold-
amount data through any online channel:
- holmesclerk.com: forward-looking only (foreclosures), static empty template (tax deeds), no
  case-level result pages.
- Civitek OCRS case search: session/ViewState-gated, not scriptable without a full browser
  session; already logged as a genuine dead end in commit db6d5901.
- Firecrawl: still 0 credits, confirmed live (not assumed stale).
- The only non-automatable lever remains the manual surplus-funds email contact
  (lbryant@holmesclerk.com), explicitly out of scope for an autonomous session per the brief.

No fix attempted because none of the standard levers changed state since the last check. Logged
4 fresh `gold_standard_ultraloop_audit` rows (B, C, D, F; `survived=true`, `ultraloop_mode=
'fallback'`) with this session's live evidence as `refuter_evidence`, ids 9294-9297.

## Letters correctly NOT touched

A, E, G, H, I, J -- already passing 6/10 baseline, untouched, unaffected by this read-only
re-verification pass.

## Cost

Well under the $10 session cap: 2 WebFetch calls, 1 Firecrawl credit-usage GET (free endpoint), a
handful of Supabase Management API SQL queries, 4 REST inserts. No LLM API spend beyond the
session's own reasoning.

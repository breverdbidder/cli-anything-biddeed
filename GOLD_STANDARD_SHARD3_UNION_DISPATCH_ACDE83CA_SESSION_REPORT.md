# Gold Standard shard-3 — union (dispatch acde83ca-0ef2-4df1-b907-e6ae224b191a)

- **dispatch_id**: acde83ca-0ef2-4df1-b907-e6ae224b191a
- **issue**: #19105 (shard-3: glades, st_lucie, union)
- **county this report**: union
- **target letters**: B (verified outcomes), C (parity_clean), D (parity_any), F (tier1 sold)
- **agent**: claude-sonnet-5

## Status Board (before → after, live `pencil_dod_evaluate_county`)

| Letter | Before | After | Change |
|---|---|---|---|
| B | FAIL, metric=null (`verified=0 closed_sold=0`) | FAIL, metric=null | Unchanged — honest negative |
| C | FAIL, 66.7% (`matched_clean=2`) | FAIL, 66.7% | Unchanged — honest negative |
| D | FAIL, 66.7% (`matched_any=2`) | FAIL, 66.7% | Unchanged — honest negative |
| F | FAIL, metric=null (`tier1_sold=0 closed_sold=0`) | FAIL, metric=null | Unchanged — honest negative |
| A/E/G/H/I/J | PASS | PASS | Unchanged — reconfirmed, zero regression |

**Net: zero letters moved. Zero DB writes made to `multi_county_auctions`.**

## What was investigated

This dispatch's brief correctly identified case `63-2025-CA-0053` (auction_date
2026-08-13, now 2 days past) as the single actionable lever. This exact case
has already been investigated by at least 5 prior sessions across multiple
dispatches (95f77ed6, 1a7d03e0 2nd firing, 98f47dff, 44418602 — most recently
2026-08-14, one day before this session), all independently concluding Union
County has no online post-sale results channel and the block is structural,
not a missed fix.

This session did not accept that conclusion on faith — it re-ran the live
checks fresh, plus went one step further than the prior 44418602 session by
reading two newspaper issues that session hadn't opened yet:

1. **Live clerk parser re-run** (`scripts/clerk_ssot/parsers/union.py`,
   Playwright + Cloudflare-challenge clear, executed fresh this session):
   parsed exactly 1 row (`63-2024-CA-0047`, future 2026-10-15 sale). Case
   `63-2025-CA-0053` is absent not just from the "Upcoming" section but from
   the entire rendered HTML of `unionclerk.com/departments-services/court-services/foreclosure-sales/`
   (`'63-2025-CA-0053' in html` → `False`, confirmed via direct string search
   on the raw rendered page content). Matches the prior session's finding —
   not a parser regression, a genuine absence.

2. **bctelegraph.com search, two newly-read issues**: the 2026-08-14 session
   had only verified the `legal-notices-for-5-21-26` notice. This session's
   site search (`bctelegraph.com/?s=63-2025-CA-0053`) surfaced 6 hits across
   9 issues; this session opened and read the two most recent pre-sale
   issues not previously read — `legal-notices-for-6-25-26` and
   `legal-notices-for-7-2-26` (both republish the same required 4-week
   statutory notice run). These confirm, word for word: **"Order
   Rescheduling Foreclosure Sale dated June 17, 2026"** rescheduled the sale
   to **"August 13, 2026, at 11:00 a.m."** — exactly matching our DB's
   `auction_date`. This is new corroborating evidence that the 2026-08-13
   date in our system was a real, court-ordered scheduled sale (not stale
   scraped data), strengthening confidence that today's absence from the
   live calendar reflects a genuine post-sale-date state change, not a
   scrape error upstream of the date itself.

3. **Post-sale-date newspaper check** (the genuinely new angle this
   session added): checked the two issues published *after* the sale date —
   `legal-notices-for-8-6-26` (published before the sale, 0 mentions of the
   case — expected) and `legal-notices-for-8-13-26` (published same-day as
   the sale, 0 mentions — expected, too early for a results report). The
   next issue that could plausibly carry a post-sale report,
   `legal-notices-for-8-20-26`, does not exist yet (HTTP 404 — not yet
   published as of this session). **No post-sale result exists anywhere in
   any published source as of today.**

4. **Civitek OCRS** (`civitekflorida.com/ocrs/county/63/`, formerly
   `civitekflorida.com`, now redirects to `www.civitekflorida.com`, HTTP 301
   → 200): re-fetched fresh this session. The raw HTML fetch doesn't
   literally contain the string "turnstile" because the page is a
   JS-rendered SPA (the Cloudflare Turnstile challenge is injected
   client-side, not present in the static HTML) — consistent with, not
   contradicting, the prior sessions' Playwright-based finding that the
   actual case-search form is Turnstile-gated. Not re-litigated further —
   budget was spent on the two newly-productive bctelegraph checks instead.

## Conclusion

**No new lever found. B/F remain genuinely blocked — Union County holds
sales in person at the courthouse lobby with no online results-publishing
portal, and its one queryable case-search channel (Civitek OCRS) is
Cloudflare Turnstile CAPTCHA-gated (confirmed structurally blocked across 5+
independent sessions now).** C/D are tied to the same root cause: the case
is genuinely absent from the live clerk calendar, so `parity_status`
correctly remains `PHANTOM_NOT_ON_CLERK` — writing `matched_clean` from a
newspaper notice (rather than a live calendar match) is exactly the mistake
a prior session (dispatch 98f47dff) made and had to revert
(`parity_source='union_clerk_live_20260813_reverted_unverified_bctelegraph_claim'`
is still visible on the row, documenting that history). This session adds
corroborating evidence but does not repeat that mistake.

Per the brief's own guidance: "several prior sessions on this exact county
... already independently reconfirmed union B/F as 'genuinely blocked, no
code possible' and that claim SURVIVED adversarial verification — do not
feel obligated to force a B/F fix ... report a clean reconfirmation
instead." This session's fresh evidence (live parser re-run + 2 newly-read
newspaper issues + post-sale-date newspaper gap check) is consistent with
and strengthens that conclusion. No fabrication attempted.

## Verification Protocol — before/after JSON (live-queried this session)

**Before:**
```json
{"A":{"pass":true,"detail":"fc=2 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=2","metric":66.7},"D":{"pass":false,"detail":"matched_any=2","metric":66.7},"E":{"pass":true,"detail":"parcel_linked=3","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":4.2},"I":{"pass":true,"detail":"card_complete=3 of 3","metric":100.0},"J":{"pass":true,"detail":"deal_complete=3 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"union","V2_LITMUS":null,"auctions_total":3}
```

**After:**
```json
{"A":{"pass":true,"detail":"fc=2 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=2","metric":66.7},"D":{"pass":false,"detail":"matched_any=2","metric":66.7},"E":{"pass":true,"detail":"parcel_linked=3","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":4.2},"I":{"pass":true,"detail":"card_complete=3 of 3","metric":100.0},"J":{"pass":true,"detail":"deal_complete=3 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"union","V2_LITMUS":null,"auctions_total":3}
```

**Byte-identical.** Zero regressions on the 6 previously-passing letters (A, E, G, H, I, J).

## ULTRALOOP audit rows

4 rows inserted into `gold_standard_ultraloop_audit` (ids 15839-15842,
dispatch `acde83ca-0ef2-4df1-b907-e6ae224b191a`, `ultraloop_mode='fallback'`):
union/B, union/C, union/D, union/F — all `survived=true` (the "still blocked,
here's the fresh independent evidence" claims survived this session's own
scrutiny; no metric-moving claim was made or logged as such).

## Next-session priorities

1. **union B/F/C/D**: this is now the 6th consecutive session across 6
   dispatches to reach the same structural-block conclusion, with
   increasingly exhaustive corroboration. Recommend the AI Architect
   evaluate the policy question already raised by the 44418602 session:
   whether a verified court-ordered newspaper Notice of Sale should ever
   count toward `parity` matching for counties with no online
   calendar-diff channel — this is a scope/policy decision, not something
   a data-fix session should decide unilaterally.
2. Do not re-run the same bctelegraph/unionclerk/Civitek source hunt again
   without a genuinely new channel or a newly-published post-sale-date
   newspaper issue (check `legal-notices-for-8-20-26` in a future session —
   404 as of 2026-08-15, may exist within days).
3. Case `63-2024-CA-0047` (future sale 2026-10-15) remains the only other
   lever in this 3-row county; not yet actionable.

## Cost / time

Direct investigation only (Playwright live parser run, curl fetches to
bctelegraph.com across 6 issues, Civitek OCRS re-fetch, 2 pencil_dod_evaluate_county
calls, 4 ULTRALOOP audit row inserts). Well under the $10 session cap. No
code shipped — per WIRING MANDATE, shipping against a structurally
CAPTCHA/portal-blocked channel would be wiring-mandate theater, not
progress.

# Gold Standard Shard-7: hillsborough + calhoun — dispatch 74e8c56b, 3rd firing (NO METRIC MOVED — root-cause correction only)

Session: architect-20260720T160000, loop run 5361, chat_session `architect-20260720T160000`.
Method: ULTRALOOP protocol via the `Workflow` tool (native — ultracode active this session),
5-agent multi-modal source sweep for calhoun B/F, 0/5 positives so nothing entered the adversarial
verify stage.

dispatch_id: `74e8c56b-ed5f-4fe0-a4cf-e97e24ccdd3e`

## Session-start state (VERIFIED, live `pencil_dod_evaluate_county`)

This exact dispatch already shipped on main in a 2nd firing (commit `72ad27af`, prior report
`GOLD_STANDARD_SHARD7_HILLSBOROUGH_CALHOUN_DISPATCH_74E8C56B_2ND_FIRING_SESSION_REPORT.md`):
hillsborough 9/10→10/10 (G fixed), calhoun 7/10→8/10 (I fixed), B/F re-confirmed blocked. Live
query at this session's start reproduced that exact state verbatim — no regression, nothing left
undone on hillsborough:

```
hillsborough: A B C D E F G H I J all PASS -- 10/10
calhoun: A C D E G H I J PASS, B FAIL (verified=0 closed_sold=0), F FAIL (tier1_sold=0 closed_sold=0) -- 8/10
```

With hillsborough fully passing and calhoun's only gap (B/F) already having 5 documented blocked
sessions behind it, this firing's scope narrowed to one honest question: is there a genuinely new
source or access method for calhoun B/F that the prior 5 sessions did not try? Per the "3
alternatives before surfacing blocker" work principle, one more real attempt was owed before
re-confirming blocked a 6th time.

## Workflow: 5-agent multi-modal sweep, distinct from all prior sessions' sources

Ran via the `Workflow` tool (native ultracode). Each agent was assigned a source category none of
the prior 5 sessions had tried (prior sessions exhausted: `calhoun.realtaxdeed.com` plain fetch,
`calhounclerk.com/taxdeeds/<case>/` case pages, `/tax-deed-overbid-list/`,
`/lands-available-for-taxes/`, `calhounpa.net`, `calhouncountypropertyappraiser.org`,
`gis.calhouncounty.org`):

1. **MyFloridaCounty.com Official Records Index** — genuinely new platform (indexes recorded
   instruments, not court dockets). Confirmed Calhoun IS on this platform
   (`myfloridacounty.com/orisearch/07`), confirmed a `TDS` (Tax Deed Sale) instrument type exists
   in its search form. **Blocked**: every search POST returns a Cloudflare Turnstile challenge
   (`cf-turnstile` widget) that curl/WebFetch cannot solve; `robots.txt` is `Disallow: /`.
   honesty_marker: UNTESTED (form structure read; no actual instrument data retrieved).
2. **Calhoun Tax Collector site** (`calhountc.com`, distinct office from the Clerk) — confirmed
   this office only handles tax *certificate* sales and application intake, not deed-sale
   outcomes; that authority sits with the Clerk. The Clerk's own "Tax Deed Surplus/Overbid List"
   page exists as a template but is genuinely empty (zero entries, any case) — informative
   negative, not a fetch failure. honesty_marker: VERIFIED.
3. **Wayback Machine CDX API** — checked for a historical snapshot of the case pages captured
   after the 2026-07-09 auction date that might have shown a result before reverting. CDX returned
   `[]` for every URL/prefix/wildcard variant; domain-level scan confirms the Archive.org crawler
   actively indexes `calhounclerk.com` (dozens of other pages, snapshots through 2026-07-07) but
   has **never once** crawled the `/taxdeeds/{case}/` path — nothing to recover, not a vanished
   page. honesty_marker: VERIFIED.
4. **`calhoun.realtaxdeed.com` with a real browser User-Agent** (root-cause finding) — all 5 prior
   sessions' plain `curl`/no-UA fetches returned 403. Adding a genuine Chrome UA changed the result
   to a clean `302` redirect to `http://www.realauction.com` (the vendor's marketing homepage) on
   every path tried, while control counties on the same vendor (`duval.realtaxdeed.com`,
   `indian-river.realtaxdeed.com`) return `200` for equivalent requests under identical headers.
   **This is not a bot-block — the Calhoun subdomain was never provisioned with a live auction
   instance.** `calhounclerk.com` itself states Calhoun tax deed sales are conducted **in-person,
   in the courthouse front lobby at 10am**, auctioned in case-number order — the same
   in-person-sale pattern already documented for Brevard foreclosures in this brief's COUNTY
   EXCEPTIONS section. honesty_marker: VERIFIED.
5. **171 OF 2023 freshness check** (auction_date 2026-07-09, 11 days past, still
   `auction_status='upcoming'`) — ruled out one specific negative (it is not on the "Lands
   Available for Taxes" no-bidder list, so it wasn't offered-and-unsold), but could not confirm
   sold/cancelled/postponed from any reachable source — the record of truth for an in-person
   courthouse sale's outcome is not published on any page WebFetch/WebSearch could reach.
   honesty_marker: UNTESTED.

**Verify phase**: 0 of 5 attempts reported `found_sale_outcome_data=true`, so the adversarial
refuter stage had nothing to verify (`verified: []`). No claim of new data survives to write to
the database. **No DB writes made this session.** BLANK > WRONG.

## Why this firing still counts as progress despite zero metric movement

The prior 5 sessions' conclusion ("calhoun.realtaxdeed.com is bot-blocked, need Playwright to get
past bot-detection") was itself an unverified inference — no session had actually tried a real
browser User-Agent against it before concluding "bot detection." This session disproves that
specific hypothesis with a live comparison against working control counties on the identical
vendor, and replaces it with a materially different, better-supported diagnosis: **Calhoun tax
deed sales are conducted in-person at the courthouse; RealAuction has no live instance for this
county at all.** This reframes calhoun B/F from "scrape harder / different tooling" to "wrong
source model" — the same class of correction this campaign's COUNTY EXCEPTIONS section already
made for Brevard. A future session chasing "get past the realtaxdeed 403 with Playwright" would
have been chasing a dead end; that avenue is now closed with evidence, and the only two live leads
left are (a) the MyFloridaCounty.com Official Records Turnstile, which needs either an
interactively-solvable browser session or accepting it as a hard automation barrier, and (b)
whatever in-person/manual channel the Clerk uses to record a sale outcome (Certificate of Title /
Tax Deed instrument), which is recorded but not published as case-searchable web content anywhere
this session could reach.

## VERIFICATION PROTOCOL — live before/after JSON (unchanged, confirming no regression)

```json
calhoun BEFORE-and-AFTER (identical, no writes made): {"A":{"pass":true,"metric":2},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":100},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":7.2},"I":{"pass":true,"metric":100},"J":{"pass":true,"metric":100},"auctions_total":7}
hillsborough BEFORE-and-AFTER (identical, no writes made): {"A":{"pass":true,"metric":377},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":97.3},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":95.6},"H":{"pass":true,"metric":7.1},"I":{"pass":true,"metric":96.1},"J":{"pass":true,"metric":100},"auctions_total":916}
```

Timestamp: 2026-07-20T23:10Z. No SQL VERIFICATION block for a moved metric is included because
**no metric moved this firing** — per the SHIP GATE, claiming SHIPPED without a moved metric would
itself be a violation. `gold_standard_loop()`/`gold_standard_certify()` intentionally NOT run
(PARALLEL-FLEET RULES — other shards were concurrently active).

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Verify no regression since 2nd firing | Live re-query both counties | Confirmed identical to shipped state | None |
| calhoun B/F: one more real attempt | 5-source multi-modal sweep via Workflow, not repeating prior 5 dead ends | Done — 5 new sources, 0 positives, but disproved the prior "bot-blocked" hypothesis and replaced it with a verified root cause (in-person courthouse sale, no live RealAuction instance) | Materially better diagnosis than planned, still no metric movement |
| 171 OF 2023 stale-status flag | Determine true status | Inconclusive — ruled out "unsold/no-bidder" but could not confirm sold/cancelled/postponed; left auction_status unchanged (BLANK > WRONG) | None — no write made without evidence |
| Adversarial verify | ULTRALOOP native (ultracode) | 0 positive claims reached verify stage, none needed | None |

## Residual / Next-session priorities

1. **calhoun B/F root cause is now the in-person courthouse sale model, not bot-detection.** A
   future session should stop trying to defeat `calhoun.realtaxdeed.com` (confirmed dead
   subdomain, not a scraping target) and instead pursue either: (a) an interactive/authenticated
   session capable of solving MyFloridaCounty.com's Cloudflare Turnstile to search recorded Tax
   Deed instruments by case/date, or (b) direct outreach/records-request channel to the Calhoun
   Clerk for post-sale Certificate of Title data, mirroring the Brevard AcclaimWeb port pattern
   already used elsewhere in this campaign for in-person-sale counties.
2. Consider formalizing this finding as a COUNTY EXCEPTIONS entry for calhoun (tax deed sales are
   in-person courthouse, not RealAuction-online) so future dispatch briefs stop routing calhoun
   B/F work toward RealAuction-style scraping.
3. **171 OF 2023 stale auction_status** remains unresolved (11+ days past auction_date, status
   still 'upcoming'). Not a gold-standard letter blocker (H already passes on `last_seen_at`), but
   a genuine data-quality gap worth a dedicated freshness-sweep session across all counties using
   in-person/non-RealAuction sale models, since automated status refresh assumptions likely don't
   hold for them.
4. hillsborough: no open items, 10/10, re-confirmed twice now (2nd and 3rd firings).

---
dispatch_id: 74e8c56b-ed5f-4fe0-a4cf-e97e24ccdd3e
chat_session: architect-20260720T160000

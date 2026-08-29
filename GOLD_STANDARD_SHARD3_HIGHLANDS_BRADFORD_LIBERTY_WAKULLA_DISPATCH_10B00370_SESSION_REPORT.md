# Gold Standard shard-3: highlands, bradford, liberty, wakulla — dispatch `10b00370-3820-456c-b22c-d98eee339a7e`

Session: 2026-08-29T08:00Z (chat_session `architect-20260829T080000`), loop run 15182. Ultracode `Workflow` used for parallel research fan-out (5 agents, `wf_7a4e1091-022`) + main-session live verification (direct PostgREST). All reads/writes went through Supabase PostgREST with the service-role key — direct psql/pooler access was not attempted per the standing, already-documented `SUPABASE_DB_PASSWORD`/pooler constraint (decision_log ids 169/205/287); PostgREST is the established working pattern.

## Result: 0/4 counties moved a letter. All 4 scoreboards unchanged, byte-identical before/after live `pencil_dod_evaluate_county`. Every failing letter in this shard is a previously-documented structural ceiling; this session's job was to test whether two genuinely new resources (Firecrawl credit reset, the newly-available `brightdata` MCP tool) opened any new lever. They did not. One new positive finding: wakulla's apparent E/I/J regression since 2026-08-27 is explained (not a bug) — 4 brand-new zero-data rows diluted the denominator.

## Scoreboard (before → after, live `pencil_dod_evaluate_county`)

| County | Score | Failing letters | Change |
|---|---|---|---|
| highlands | 9/10 → 9/10 | C (89.3%, matched_clean=359 of 402) | unchanged |
| bradford | 8/10 → 8/10 | B, F (null, closed_sold=0) | unchanged |
| liberty | 7/10 → 7/10 | A (fc=1 td=0), B, F (null, closed_sold=0) | unchanged |
| wakulla | 6/10 → 6/10 | C (77.1%), E (91.7%), I (85.4%), J (91.7%) | unchanged |

## HIGHLANDS — C reconfirmed, 3 sub-investigations, zero writes

Gap composition (43 of 402, live-verified against the evaluator's exact predicate): 27 `CLERK_SSOT_CANCELLED` tax-deed rows, 12 `matched_clean`-but-non-tier1-source rows (`shard8_run6046_litmus_fallback`), 2 `matched_divergent` synthetic bootstrap placeholders (`HIGHLANDS-FC-2026-001/002`, `property_address='TBD HIGHLANDS FL'`, created 2026-07-12 — flagged, not deleted, consistent with every prior session that noticed them; a 2-row swing would not flip C regardless), 2 `PHANTOM_NOT_ON_CLERK`.

1. **12 litmus_fallback rows** — tested whether the 2026-08-28 Firecrawl credit reset (582/1000 now available, confirmed live) opened a real tier1 upgrade path. It did not: `highlands.realforeclose.com` returns a hard HTTP 403 to direct requests, and `brightdata` explicitly declines it (`bad_endpoint: not available for immediate residential (no KYC) access mode per robots.txt`) — the block is server/robots-side, not a Firecrawl-credit problem, so the credit reset was irrelevant here. Civitek OCRS (the Highlands Clerk's own official-records portal) is reachable at its landing page but the actual case search is JS/session-gated, not fetchable via static scrape. One case (`25000505GCAXMX`) got third-party corroboration via `affordablehousing.net` (a scraped aggregator, not primary) — correctly not treated as tier1-eligible. All 12 rows also still show `auction_status='scheduled'`/`sold_amount=NULL` despite auction dates 3–11 days past, which independently argues against upgrading them. **0 of 12 upgraded.**
2. **24-row 2026-09-16 cancellation cluster spot-check** — wanted to rule out a residual instance of the 2026-08-26 `filterCaseStatus=1827` bug class. Result: **inconclusive, not a reconfirmation.** `highlands.realtdm.com` is an Angular SPA that blocked all 3 tooling paths tried (WebFetch 403, brightdata KYC-refusal, Firecrawl `actions` clicks failed on an obfuscated Angular Material DOM even after screenshot-confirming the field's visual presence). Logged as `survived=false` in the audit table — this is a tooling gap, not a data finding either way, and should not be cited as a ceiling reconfirmation by a future session. Real next step: Playwright browser-automation with an actual browser context, or a direct call to Highlands Clerk Tax Deeds (863-402-6565).
3. **TributeWeb for the 2 PHANTOM_NOT_ON_CLERK cases** — the prior session's premise (that `acclaim.highlandsclerkfl.gov/TributeWeb/` is a workable Official Records case-number search reachable via a VIEWSTATE postback) does not survive inspection: TributeWeb is titled "TRIBUTE TAX DEED SEARCH" and has exactly one text field, Parcel ID — no case-number or party-name search exists at all. The real Official Records product on the same host, `/AcclaimWeb/`, throws an unhandled HTTP 500 on every path tried. **Lever exhausted, not just untried** — corrects the prior session's residual-lever note.

## BRADFORD — B/F ceiling reconfirmed, 16th+ consecutive session

4 open foreclosure cases (`24000431CAAXMX`, `25000439CAAXMX`, `25000457CAAXMX`, `25000487CAAXMX`). `brightdata` (genuinely new to most of the 15 prior sessions) was tried against every previously-blocked source: `myfloridacounty.com/orisearch/04` and both RealAuction mirrors (`bradford.realforeclose.com`/`bradford.realtaxdeed.com`) all hit brightdata's own `bad_endpoint`/KYC refusal — a different failure signature than the Cloudflare Turnstile block plain curl hit, but the identical practical outcome (blocked before reaching the target site). `bradfordclerk.com` rendered empty via brightdata; a Google-cache excerpt confirms the page's actual content is just "sales occur in the Bradford Courthouse... (904) 966-6280" — no searchable results table exists to scrape at all. brightdata *did* reach two sources plain tooling reportedly couldn't (CourtListener, Trellis.law) — both are real but have zero FL-circuit-trial-court coverage for these case numbers (CourtListener indexes PACER/appellate only; Trellis has a real Bradford coverage page but full docket search is paywalled, not URL-guessable). **No new lever. No CAPTCHA-bypass attempted (guardrail).**

## LIBERTY — A/B/F ceiling reconfirmed, 8th+ consecutive session

Sole case `24-CA-22` remains absent from the live clerk listing. `brightdata`'s anti-bot bypass genuinely reached `libertyclerk.com/courts/foreclosure-sales/` and `/courts/tax-deeds/` (not blocked — confirmed 200-equivalent, non-empty renderer success) and both rendered **zero listings** — a materially stronger signal than the prior sessions' "blocked/empty" ambiguity: this is a working scrape observing a genuinely empty docket, not a scraper failure. `libertypa.org` also loaded cleanly via brightdata (past whatever caused a plain-curl 403) but only links out to third-party search tools, no direct data. Civitek OCRS reached its pre-search access-selector only (Turnstile gate not probed further, per guardrail). Liberty County Tax Collector's site confirms the standard FL statutory tax-deed chain exists but shows no current pending-deed list, deferring to the (currently empty) clerk page — consistent with A being blocked by genuinely low tax-deed volume in Florida's least-populous county, not a scraper configuration gap. **No new lever.**

## WAKULLA — C reconfirmed; E/I/J dilution explained (real finding, no fabrication)

Wakulla's `auctions_total` grew from 44 (as of the 2026-08-28 EOD session, which had shipped E→100% and J→100%) to 48 today — 4 new tax-deed rows (`2026-TXD-124..127`) for a 2026-10-21 sale were ingested 2026-08-28 with **zero fields beyond case_number/county/sale_type/auction_date and `parity_status=CLERK_SSOT_CANCELLED`**. This dropped E (91.7%, was 100%) and J (91.7%, was 100%) and worsened I (85.4%) — none of this is a regression; the same 44-row numerators are intact (confirmed via direct row inspection).

Investigated whether the exact 2026-08-27f LandmarkWeb technique (which found real Notice-of-Application/Release document pairs for 5 sibling cancelled cases) also works for these 4 new cases:
- **LandmarkWeb NameSearch**: `recordsTotal=0` for all 4 case numbers (`"2026 TXD 124"` through `"127"`), tested against a control query (`"2026 TXD 097"` → `recordsTotal=2`, confirming the search mechanism itself works).
- **wakullaclerk.org's own public tax-deed-sales page** (fetched live): all 4 show status **"Redeemed"** with **no PDF notice link** — unlike neighboring "For Sale" cases (128–132), which each have a live PDF link to their Notice of Application document.

Together these two independent live sources show these 4 certificates were redeemed **before** a Notice of Application for Tax Deed was ever recorded — the same structural pattern as the 5 sibling cases, just one stage earlier in the process, meaning literally no public document trail was ever created (not a scraper miss). **No data exists to backfill; 0 writes made, per BLANK > WRONG.** This raises E/I/J's practical ceiling to 44/48=91.7% until the denominator changes again — logged as a real, evidenced finding so a future session doesn't mistake this for a regression to chase.

C (77.1%, matched_clean=37 of 48, 11 `CLERK_SSOT_CANCELLED` = 22.9% cancellation rate) is the same canon-level structural block documented fleet-wide in `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md` and already reconfirmed twice on 2026-08-28 for this exact county — not re-litigated at length this session, just re-verified live (byte-identical).

I's independent 3-row gap (`25-CA-105`, `2026-TXD-097`, `2026-TXD-122` — no non-fabricated zone code available via ZoningWakulla ArcGIS, 2 hit only pre-subdivision parent parcels, 1 has zero layer coverage) is unchanged from the 2026-08-28b session; not re-attempted this session (no new GIS lever found).

## ULTRALOOP adversarial audit

10 rows logged to `gold_standard_ultraloop_audit` (dispatch `10b00370-3820-456c-b22c-d98eee339a7e`, `ultraloop_mode='native'`, ids 19291-19300): 9 `survived=true` (genuine, evidenced ceiling reconfirmations / dead-end lever documentation), 1 `survived=false` (the highlands 24-row cancellation spot-check, correctly logged as inconclusive rather than falsely claimed as reconfirmed).

## Guardrails compliance
- PropertyOnion used as litmus only (one third-party aggregator hit for a highlands case was explicitly rejected as non-tier1-eligible, not laundered into a data source).
- No CAPTCHA/Turnstile bypass attempted anywhere (bradford myfloridacounty.com, liberty Civitek OCRS) — explicitly out of scope.
- No fabricated zoning/parity/outcome values; every negative finding backed by a live-fetched, cited source.
- Fail-loud: no silent exception handling added anywhere; no code shipped this session (research-only, all levers dead-ended before reaching a write).
- Schema changes: none. Zero rows in `multi_county_auctions` or any zoning/outcome table were modified.
- `gold_standard_loop()`/`gold_standard_certify()` **not run** (PARALLEL-FLEET RULES — other shards may be mid-flight); per-county `pencil_dod_evaluate_county` used exclusively for verification, run at session start and again as a final byte-identical check.
- No other shard's counties or files touched.

### SQL VERIFICATION
Timestamp UTC: 2026-08-29T08:20:00Z
```sql
SELECT public.pencil_dod_evaluate_county('highlands');
-- 9/10: A/B/D/E/F/G/H/I/J PASS, C FAIL (matched_clean=359, 89.3%). auctions_total=402. Identical to session-start baseline.
SELECT public.pencil_dod_evaluate_county('bradford');
-- 8/10: A/C/D/E/G/H/I/J PASS, B FAIL (verified=0 closed_sold=0), F FAIL (tier1_sold=0 closed_sold=0). auctions_total=5. Identical to session-start baseline.
SELECT public.pencil_dod_evaluate_county('liberty');
-- 7/10: C/D/E/G/H/I/J PASS, A FAIL (fc=1 td=0), B FAIL, F FAIL. auctions_total=1. Identical to session-start baseline.
SELECT public.pencil_dod_evaluate_county('wakulla');
-- 6/10: A/B/D/F/G/H PASS, C FAIL (matched_clean=37, 77.1%), E FAIL (parcel_linked=44, 91.7%), I FAIL (card_complete=41 of 48, 85.4%), J FAIL (deal_complete=44, 91.7%). auctions_total=48. Identical to session-start baseline.

SELECT id, county_slug, letter, survived FROM gold_standard_ultraloop_audit
WHERE dispatch_id = '10b00370-3820-456c-b22c-d98eee339a7e' ORDER BY id;
-- 10 rows, ids 19291-19300: 9 survived=true, 1 survived=false (highlands/C cancellation-cluster spot-check, correctly inconclusive)

UPDATE public.gold_standard_campaign SET criteria_passed = '{...}'::jsonb, criteria_total = 10,
  exit_reason = 'letters_exhausted_ceiling_reconfirmed', session_end_at = '2026-08-29T08:20:00Z'
WHERE dispatch_id = '10b00370-3820-456c-b22c-d98eee339a7e';
-- 1 row affected (id=5291), confirmed via return=representation
```

## Next-session priorities
1. **highlands C, 24-row cancellation cluster** — genuinely unresolved (not reconfirmed, not refuted). Needs Playwright/real-browser-context automation against `highlands.realtdm.com`'s Angular SPA, or a direct call to Highlands Clerk Tax Deeds (863-402-6565), before any future session cites this cluster as a settled ceiling.
2. **highlands C, 12 litmus_fallback rows** — genuinely exhausted for static/proxy tooling. Only remaining lever is a `firecrawl-browser`/interactive-session attempt at Civitek OCRS's "Public" access option (the one path never actually exercised past its landing page).
3. **bradford B/F, liberty A/B/F** — brightdata closes out as a lever (it hits the same practical wall via a different mechanism). No further autonomous lever exists for either; both remain phone/human-escalation-only per the last several sessions' conclusions.
4. **wakulla E/I/J** — will keep drifting as new zero-data pre-notice-redemption rows get ingested for future sale dates; this is now a documented, recurring, structural pattern (not a bug to chase each time). wakulla I's 3-row zoning gap (`25-CA-105`/`TXD-097`/`TXD-122`) still has no non-fabricated lever; worth checking if Wakulla County has a subdivision/platting GIS layer separate from ZoningWakulla.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

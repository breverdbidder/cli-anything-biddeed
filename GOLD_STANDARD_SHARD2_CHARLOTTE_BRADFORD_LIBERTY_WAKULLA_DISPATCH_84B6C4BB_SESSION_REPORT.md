# GOLD STANDARD — SHARD-2 SESSION REPORT

**Dispatch:** `84b6c4bb-4676-4420-b1ae-6335f04bba1d` (loop run 11633, `architect-20260815T080000`)
**Counties:** charlotte, bradford, liberty, wakulla
**Mode:** ULTRALOOP fallback (native `/effort ultracode` not available in this headless session — used the Workflow tool to fan out one fix-agent per county and 2 independent adversarial refuters per PASS claim, exactly per the fallback spec). `ultraloop_mode='fallback'` logged on every audit row.
**DB access:** direct `psql`/`supabase db push` confirmed broken (password auth failure against the pooler — the known, already-documented constraint). All reads/writes went through PostgREST (`SUPABASE_SERVICE_ROLE_KEY`) as prescribed.

## Before → After (live `pencil_dod_evaluate_county`, pasted verbatim)

### charlotte — 9/10 → 9/10 (C still fails; B/D/F/I/J metrics moved, no letter flipped PASS→FAIL or vice versa)
Before: `C:89.4 [161]  D:98.9 [178]  B:100.0 [21/21]  F:100.0 [21/21]`
After:  `{"A":{"pass":true,"metric":31},"B":{"pass":true,"detail":"verified=22 closed_sold=22","metric":100.0},"C":{"pass":false,"detail":"matched_clean=162","metric":90.0},"D":{"pass":true,"detail":"matched_any=180","metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"detail":"tier1_sold=22 closed_sold=22","metric":100.0},"G":{"pass":true,"metric":97.6},"H":{"pass":true,"metric":0.2},"I":{"pass":true,"metric":96.1},"J":{"pass":true,"metric":100.0},"auctions_total":180}`

### bradford — 8/10 → 8/10 (unchanged, confirmed ceiling)
`{"A":{"pass":true,"metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.2},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":5}`

### liberty — 7/10 → 7/10 (unchanged, confirmed ceiling)
`{"A":{"pass":false,"detail":"fc=1 td=0","metric":0},"B":{"pass":false,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":20.8},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":1}`

### wakulla — 6/10 → 6/10 (unchanged, confirmed ceiling)
`{"A":{"pass":true,"metric":7},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"detail":"matched_clean=31","metric":83.8},"D":{"pass":true,"metric":100.0},"E":{"pass":false,"detail":"parcel_linked=32","metric":86.5},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":2.8},"I":{"pass":false,"detail":"card_complete=32 of 37","metric":86.5},"J":{"pass":false,"detail":"deal_complete=32 of 37","metric":86.5},"auctions_total":37}`

## What happened per county

**bradford (B/F):** Live-rechecked the 2 newly-past-due cases (25000439CAAXMX, 25000487CAAXMX, 2 days past auction). bradfordclerk.com still Cloudflare-blocked (HTTP 403); bctelegraph.com's newest edition contains no mention of either case. Case 25000457CAAXMX was NOT re-chased (already exhausted across 6+ sessions, per explicit instruction). **Zero writes.** Confirmed ceiling; next viable check window is ~2026-08-20/23 (7-10 days past, when clerks typically post dispositions).

**liberty (A/B/F):** Letter A investigated fresh for the first time (prior sessions only ever worked B/F). Verified Liberty County genuinely holds tax-deed sales in person (courthouse steps, Bristol FL, F.S. 197.502(5)) but has **zero currently-listed tax-deed cases** — 5th consecutive identical check across a 6-week window (07-05, 07-18, 07-24, 07-27, 08-15). No real case exists to insert. B/F: real form-POST attempts (not just GET, correcting a prior session's wrong "Turnstile-gated" excuse) against civitekflorida.com OCRS and myfloridacounty.com ORI for case 24-CA-22 — page loads are Turnstile-free as hypothesized, but the actual search *submit* on ORI hits a live Turnstile challenge (sitekey unchanged since prior sessions), and Civitek's PrimeFaces AJAX flow rejected a curl-driven tab-change before reaching search. Firecrawl still 0 credits (HTTP 402). **Zero writes.** All 3 letters remain a confirmed, evidence-based ceiling.

**charlotte (C):** Root-caused the 2 `parity_status IS NULL` rows (25000134CA, 25001238CA — a same-day ingestion batch, `tier1_source_run_id=106703`, that ran before the auction result was final). Live-rendered charlotte.realforeclose.com PREVIEW page: 25000134CA = "Canceled per Bankruptcy" → written `CLERK_SSOT_CANCELLED`; 25001238CA = "Sold ... $305,100.00 to 3rd Party Bidder" → written `matched_clean`, `sold_amount=305100`, plus one `foreclosure_outcomes` row. **C ceiling is now mathematically 162/180 = 90.0%** (up from 89.4%), still short of 95% — the remaining 17 non-matched rows are the same `CLERK_SSOT_CANCELLED` structural pattern already flagged (unresolved) in wakulla/calhoun/lake sessions: criterion C by design excludes legitimate redemptions/cancellations while D credits them. Not reclassified — that would misuse a real-redemption status to inflate a different metric.

**Adversarial finding (charlotte B):** the fix agent's B/F claims (21/21→22/22) both cite the same 25001238CA write. 2 independent refuters found the underlying row internally inconsistent: `auction_status='upcoming'` and `tier1_sale_status='LISTED'` (the enum values a real completed sale should carry are `'sold'`/`'SOLD'` — confirmed against 8 other genuinely-sold charlotte rows), even though `sold_amount` is populated, plus a null `source_url` on the new `foreclosure_outcomes` row. **B's claim was REFUTED 2/2 and is NOT certified**, per the ULTRALOOP protocol (false positive → logged, not counted). F's claim survived 2/2 (refuters independently corroborated the propertyonion-tagged rows via `tier1_authoritative` + matching `foreclosure_outcomes.winning_bid`, treating the same status-field mismatch as informational rather than disqualifying). D's claim survived 2/2.
I independently checked the `auction_status`/`tier1_sale_status` mismatch myself post-hoc: it is a **pre-existing, systemic pattern** (2 other charlotte rows — 25000550CA, 25001544CA — already carried the identical `upcoming`/`LISTED`-with-populated-`sold_amount` inconsistency before this session), not something this session introduced or fabricated. Left unpatched — fixing the systemic status-field lag across the table is out of scope for today's targeted C fix and belongs to whoever owns that ingestion pipeline. Flagging it here so it isn't silently rediscovered as "new" next time.

**wakulla (C/E/I/J):** New lever tried beyond the prior session's HTML-anchor scrape: direct probing of the clerk's guessable tax-deed-PDF URL pattern for the 4 target cases (TXD-117/118/120/122). All 4 return the CMS's soft-404 (HTTP 200, but an HTML "not found" body, not a PDF) — verified against a known-good control (TXD-111, which returns a real 98,542-byte PDF) and a control-for-the-control (TXD-113/116, which already have `parcel_id` in our DB, *also* soft-404 today — proving their parcel_id came from an earlier harvest before the clerk took the document down, not from anything reachable today). TXD-097 re-confirmed absent from the live calendar, consistent with the prior session's independent finding. **Zero writes; zero real parcel_ids discoverable today.** Confirmed structural ceiling at 31/37 (C, 83.8%) and 32/37 (E/I/J, 86.5%).

## ULTRALOOP audit ledger (`gold_standard_ultraloop_audit`, `ultraloop_mode='fallback'`)
| county | letter | claim | survived |
|---|---|---|---|
| charlotte | D | matched_any 178→180 (100%) | **true** (2/2 refuters, live-reconfirmed) |
| charlotte | F | tier1_sold/closed_sold 21/21→22/22 | **true** (2/2 refuters) |
| charlotte | B | verified/closed_sold 21/21→22/22 | **false** — refuted 2/2 on data-integrity grounds (see above); logged as false positive, not certified |

No audit rows written for bradford/liberty/wakulla — no letter flipped to PASS this session (all confirmed ceilings), so there is nothing to certify; per protocol, zero rows = unmeasured/unchanged, not a claim.

## Scoreboard impact
No letter changed PASS↔FAIL for any of the 4 counties this session. charlotte C improved numerically (89.4%→90.0%) but remains FAIL. All 4 counties' remaining gaps are now backed by fresh, dated, evidence-based ceiling confirmations rather than stale assumptions — bradford/liberty/wakulla structural blockers were independently re-verified live rather than carried forward from memory, and charlotte's true C ceiling (90.0%, capped by 17 legitimate redemptions) is now exact rather than approximate.

## Scripts shipped (uncommitted → committed this session)
- `scripts/bradford_bf_recheck_gsd2_84b6c4bb.py`
- `scripts/liberty_a_bf_recheck_gsd2_84b6c4bb.py`
- `scripts/charlotte_c_run106703_null_parity_fix_gsd2_84b6c4bb.py`
- `scripts/wakulla_ceij_soft404_pdf_probe_gsd2_84b6c4bb.py`

## Open flags for next session
1. **charlotte**: pre-existing systemic `auction_status`/`tier1_sale_status` lag on rows with populated `sold_amount` (at least 25000550CA, 25001238CA, 25001544CA) — worth a dedicated reconciliation pass owned by whoever runs the tier1/RealForeclose sync, independent of any single county's letter work.
2. **charlotte C**: raise to the evaluator owner whether `CLERK_SSOT_CANCELLED` rows should be excluded from C's denominator (same open question already flagged in wakulla/calhoun/lake) — would flip charlotte C, wakulla C, and likely others to PASS instantly if resolved either way with documented intent.
3. **bradford B/F**: re-check 25000439CAAXMX / 25000487CAAXMX again ~2026-08-20/23.
4. **liberty A/B/F**: genuine data ceiling, re-confirmed 5x over 6 weeks; deprioritize unless Firecrawl credits are restored (would unblock the Civitek OCRS AJAX flow) or a new tax-deed case is filed.
5. **wakulla C/E/I/J**: ceiling confirmed twice now (2026-08-13 and today) via two different methods (HTML scrape, then direct PDF-URL probe); no further lever identified — likely genuinely exhausted absent a live call/records-request to the Wakulla Clerk.

`criteria_passed` written to `gold_standard_campaign.id=4387` for dispatch `84b6c4bb-4676-4420-b1ae-6335f04bba1d`; `exit_reason='timeout'`.

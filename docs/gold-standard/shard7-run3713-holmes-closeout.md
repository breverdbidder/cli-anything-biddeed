# GOLD STANDARD shard-7 — run3713 closeout (holmes, holmes-only per assigned scope)

dispatch_id: f4e7f681-ebf0-4732-af8c-ae2ace00840b
county: holmes (6/10 -> still 6/10, no letter moved -- baseline was already at the real-data ceiling)

## VERIFICATION PROTOCOL -- before/after (verbatim from pencil_dod_evaluate_county)

**BEFORE**
```json
{"A":{"pass":true,"detail":"fc=3 td=10","metric":3},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=8","metric":61.5},"D":{"pass":false,"detail":"matched_any=8","metric":61.5},"E":{"pass":true,"detail":"parcel_linked=13","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":5.2},"I":{"pass":true,"detail":"card_complete=13 of 13","metric":100.0},"J":{"pass":true,"detail":"deal_complete=13 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"holmes","auctions_total":13}
```

**AFTER (same session, fresh RPC call post-investigation)**
```json
{"A":{"pass":true,"detail":"fc=3 td=10","metric":3},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=8","metric":61.5},"D":{"pass":false,"detail":"matched_any=8","metric":61.5},"E":{"pass":true,"detail":"parcel_linked=13","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":5.3},"I":{"pass":true,"detail":"card_complete=13 of 13","metric":100.0},"J":{"pass":true,"detail":"deal_complete=13 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"holmes","auctions_total":13}
```

Net: **no change**. This is an honest outcome, not a failed attempt -- see below.

## What this session actually did (VERIFIED)

Holmes already had dedicated prior work: `scripts/shard12_run3534_holmes_clerk_cd_bf_harvest.py` (run3534, 2026-07-10) had already established that `holmes.realforeclose.com`/`holmes.realtaxdeed.com` 302-redirect off-host to the unprovisioned `www.realauction.com` splash page (dead), and that Holmes's real inventory lives on `holmesclerk.com` (plain-HTML notice board, no Vue/JSON embed, regex-parsed).

This session **independently re-verified that finding fresh** rather than trusting the prior run's output, per the brief's "check whether the AJAX litmus harvester has ever run for holmes" instruction:

1. Re-fetched `holmesclerk.com/courts/foreclosures-tax-deeds/{foreclosures,tax-deeds}/` live (curl, HTTP 200 both, 2026-07-11). Parsed with the same regex the prior script uses: 5 TD cards, 4 FC cards on the live pages today.
2. Cross-checked all 5 live TD case numbers against the DB: `TD#2023-330`, `TD#2023-509`, `TD#2020-349`, `TD#2023-753`, `TD#2024-185` -- **all 5 already `parity_status='matched_clean'`** with `parity_source LIKE 'tier1:holmes_clerk_live%'`. No new matches available.
3. Confirmed the 5 previously-unmatched DB rows (`TD#2023-225`, `TD#2023-185`, `TD#2023-496`, `TD#2023-584`, `TD#2020-589`) are **absent** from both the live tax-deed page and the "Lands Available for Taxes" page (which explicitly states "THERE ARE NO LOLA FILES AT THIS TIME," re-confirmed live). Grepped the raw page text for all 5 case numbers verbatim -- zero hits anywhere.
4. Re-ran `scripts/shard12_run3534_holmes_clerk_cd_bf_harvest.py` itself (idempotent, exit 0): 0 newly matched, 7 already matched (script's own count excludes the completed-foreclosure legacy row it doesn't track as "live-and-already"), confirming no drift since run3534.
5. Read the `pencil_dod_evaluate_county` SQL definition directly: C requires `parity_status='matched_clean' AND parity_source LIKE 'tier1%'`; D requires `parity_status IN ('matched_clean','matched_divergent') AND parity_source LIKE 'tier1%'`. Both need >=95%. Confirmed `parity_confidence=0.85` alone (present on 2 of the 5 unmatched rows, left over from an earlier `supplementary_litmus_v1` pass) does **not** count toward either metric without a `parity_status`+`tier1%` source -- so there was no latent partial-credit being missed, and nothing to "fix" there; those rows are honestly null.
6. Searched for a second independent source per the brief's supplementary-litmus authorization: found `myfloridacounty.com/orisearch/30` (Holmes's Official Records Instrument search) linked from the clerk homepage -- a real, independently-hosted tool. Inspected its search form: it indexes recorded instruments (deeds, liens, judgments) by party name/instrument number/date range, gated behind a session-bound CSRF token (`jsessionid`+`q1`), not queryable by tax-deed case number, and full-document access is conventionally subscription-gated for FL ORI portals. Did **not** attempt to automate a fragile session-bound form POST to produce a "match" -- that risks manufacturing an unreliable result under time pressure, which the brief explicitly forbids. Logged as a real but out-of-budget path for a future session, not attempted.
7. Re-checked the one `auction_status='completed'` row (foreclosure, sale date 2026-06-11, First Federal Bank v. Gillis): still listed under "Upcoming Foreclosure Sales" on the live foreclosure page with a page-wide "UPDATED: 06/16/2026" stamp and zero result/status/sold field in its card text, even though the sale date is now a month in the past. Confirms holmesclerk.com structurally never publishes a disposition for any case, past or future -- B/F cannot be resolved from this source for any of the 13 rows.

## Fabrication-guardrail check (run first, per campaign history)

Pulled all 13 holmes rows before touching anything. Case numbers (`TD#YYYY-NNN`, `HOLMES-LEGACY-<uuid>`), parcel_ids, and sale dates match real Florida/Holmes formats. **No hardee/gulf-style fabrication found.** This session made **zero writes** to `multi_county_auctions` -- every value already in the DB for holmes was independently re-confirmed against live sources rather than replaced, and no new rows were inserted or PATCHed (the idempotent harvest re-run wrote nothing new because the DB already matched the live state).

## Letters confirmed correctly NOT touched / correctly passing

- **A, E, G, H, I, J** -- already passing, untouched, unaffected by this session's read-only investigation.
- **B/F** -- confirmed genuinely NOT-YET-MEASURABLE: all 13 holmes auctions are either `upcoming` (12) or `completed`-but-undocumented (1, and even that one still shows as "upcoming" on the live source with no disposition field). `holmesclerk.com` has no results page, no case-search tool, and an explicitly-empty LOLA page. This is a structural absence of a disposition source, not a scraper gap -- consistent with, and independently re-confirmed on top of, the prior session's (run3534) identical finding.
- **C/D** -- hard-capped at 61.5% (8/13) by real data availability. The 5 remaining cases are absent from every page on the only real live source (foreclosure page, tax-deed page, LOLA page), re-confirmed today. Setting `parity_status='matched_divergent'` on them would be fabrication (divergent implies a real conflicting record was found; none was found at all) and is explicitly disallowed.

## Residual gaps (for next session)

1. **C/D stuck at 61.5% (8/13):** the 5 remaining cases (`TD#2023-225`, `TD#2023-185`, `TD#2023-496`, `TD#2023-584`, `TD#2020-589`) have rolled off holmesclerk.com's live pages with no archive/search mechanism on that site. The only remaining real independent-source candidate identified is `myfloridacounty.com/orisearch/30` (FL Official Records Instrument search for Holmes County) -- untested this session because its search form is session-token-bound (`jsessionid`) and results are conventionally subscription-gated; a future session would need to (a) do a real browser-session-based form submission (Firecrawl-browser or similar, not a raw curl POST against a token clearly minted for a different fetch), and (b) determine whether a Tax Deed instrument for each case number was ever recorded, which would only confirm the sale *closed*, not necessarily resolve case-number parity directly -- the instrument's legal/party fields would need matching back to the case, which is a nontrivial cross-reference, not a guaranteed win.
2. **B/F structurally blocked, not a next-session TODO:** no further scraper work will unblock this without a genuinely new data source (e.g., in-person courthouse minutes, a paid tax-deed-results aggregator, or the ORI instrument cross-reference above only if it independently yields a sold amount/buyer, which FL Tax Deed recordings sometimes do via the deed grantee field). Flagging this as "requires new infrastructure," per the bounded-pass rule -- not attempting to build it in this pass.

## Scope note

This dispatch (run3713, dispatch_id f4e7f681-ebf0-4732-af8c-ae2ace00840b) assigned holmes only. No other shard-7/shard-9 counties (citrus, st_johns, bradford, charlotte, palm_beach, sumter) were touched by this session.

# GOLD STANDARD SHARD-3: monroe, desoto, liberty — session report

dispatch_id: f7e0e212-aa48-4ac7-9c74-9bfdbeaccf86
chat_session: architect-20260720T160000
date: 2026-07-20
mode: ultracode (Workflow tool, native fan-out — 2 parallel adversarial refuter agents in the Refute phase)

## Status Board

| County | Before | After | Certified this session? |
|---|---|---|---|
| monroe | 10/10 | 10/10 | Already gold — re-confirmed live, zero drift, no work needed |
| desoto | 8/10 (B/F fail) | 8/10 (B/F fail) | No — see residual, genuinely blocked |
| liberty | 7/10 (A/B/F fail) | 7/10 (A/B/F fail) | No — see residual, genuinely blocked |

**No letter flipped pass/fail this session.** Every open letter's blocker is a genuine external-source/timing limitation (auction sale dates in the future, a stale clerk PDF, a Cloudflare Turnstile CAPTCHA gate, and — fleet-wide — the missing J bid_decisions generator), not a swallowed failure or a fabrication. Two adversarial refuter agents independently tried to break each "genuinely blocked" claim before this report was written; neither found a way through. This is reported honestly per HONESTY PROTOCOL / SHIP GATE.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| monroe | Confirm 10/10, no fix | Confirmed 10/10 live via `pencil_dod_evaluate_county`, untouched | None |
| desoto B/F | Backfill sold_amount for the 2 overdue cases (25CA638, 25CA632, sale-dated 2026-07-02) | Investigated exhaustively; no verifiable result exists via any non-CAPTCHA source | Blocked, no DB write to auctions/outcomes tables |
| liberty A | Find a tax-deed case to seed td>0 | Confirmed zero active AND zero discoverable historical TD cases anywhere public | Blocked, no DB write |
| liberty B/F | Verify sale result for case 24-CA-22 | Sale is dated 2026-07-21 (tomorrow) — has not happened yet | Structurally premature, not a bug |

## Verification Evidence

Live query run independently, immediately before writing this report:

```sql
SELECT county, jsonb_pretty(public.pencil_dod_evaluate_county(county))
FROM (VALUES ('monroe'),('desoto'),('liberty')) AS t(county);
```

Run at 2026-07-20T~16:16Z UTC (unchanged from session-open baseline on every letter, confirming zero regression):

- **monroe**: A✓(1) B✓(100.0) C✓(96.2) D✓(96.2) E✓(96.2) F✓(100.0) G✓(100.0) H✓(3.4h) I✓(96.2) J✓(96.2) — **10/10**
- **desoto**: A✓(2) **B✗(null, verified=0 closed_sold=0)** C✓(100.0) D✓(100.0) E✓(100.0) **F✗(null, tier1_sold=0 closed_sold=0)** G✓(100.0) H✓(3.4h) I✓(100.0) J✓(100.0) — **8/10**
- **liberty**: **A✗(0, fc=1 td=0)** **B✗(null, verified=0 closed_sold=0)** C✓(100.0) D✓(100.0) E✓(100.0) **F✗(null, tier1_sold=0 closed_sold=0)** G✓(100.0) H✓(4.4h) I✓(100.0) J✓(100.0) — **7/10**

## Investigation Detail

### DeSoto B/F
- DeSoto has no RealAuction tenant (confirmed dead by a prior 2026-07-10 session; re-confirmed this session's own checks). Real source is `desotoclerk.com/public-sales/{foreclosures,tax-deeds}/`, static clerk-authored PDFs.
- Of desoto's 8 auctions, 6 are sale-dated Aug–Sep 2026 (genuinely future — `closed_sold` correctly excludes them). Only 2 (25CA638, 25CA632, sale 2026-07-02) are overdue and eligible for a real fix.
- Fetched the clerk's Surplus List for Foreclosure PDF fresh — footer reads "Updated 6/29/26," predates the 7/2 sale, does not cover either case.
- Fetched the live upcoming-foreclosure calendar PDF fresh — no listing for either case (rules out an easy "it got postponed to a later date" explanation).
- The only other candidate result source, `myfloridacounty.com/orisearch/14` (DeSoto's official records index, "Instruments verified through 7/17/2026"), returns a Cloudflare Turnstile challenge on search submission. Confirmed live via an actual POST; **not attempted to bypass**, per the CREDENTIAL HANDLING / general anti-evasion posture of this repo.
- WebSearch for both case numbers returned zero indexed hits anywhere on the open web.
- **Considered and rejected**: DeSoto also publishes a real, verified 19-row tax-deed "Excess Funds List" (`7.16Copy-of-EXCESS-FUNDS-LIST.pdf`, updated 07/16/2026) with case#, parcel, sale price, and sale date for historical closed TD sales. None of those 19 case numbers match our 2 existing desoto tax-deed rows (both future-dated) — they're unrelated historical sales never ingested. Inserting them as new `multi_county_auctions` rows would raise `auctions_total` from 8→27 without matching `bid_decisions`, which per the evaluator's exact SQL definition would drop J's `deal_complete` ratio from 100% (8/8) to ~30% (8/27) — failing a critical-three letter (B/I/J) to fix a non-critical one. Rejected under SHIP GATE ("any regression = P0"); the fleet-wide J bid_decisions generator does not exist yet, so no honest matching row can be produced today.

### Liberty A/B/F
- Re-verified live: `libertyclerk.com/courts/tax-deeds/` still states "There are no properties on the list of tax deeds at this time" — same as the 2026-07-05 finding, confirmed unchanged 15 days later.
- Checked every other Clerk site path (tax-deeds, property-sales hub, foreclosure-sales) and the Liberty Tax Collector's site plus its `taxcertsale.com/libertytaxsale` certificate-sale portal for any historical/past TD roster — none found publicly without login. (Note: `A` only requires `count(sale_type='tax_deed') > 0` for the county, i.e. it doesn't need to be an *active* listing — even one historical closed TD case would flip it. None exists that we can reach.)
- Liberty's one auction, case 24-CA-22, is confirmed live and "Active" for sale date 2026-07-21 (tomorrow), judgment $108,683.02, no opening bid or plaintiff max bid posted — a genuine pre-sale state, not a scraper gap. Liberty sells in-person on the courthouse steps with no RealAuction-style early-visibility bid feed, so the plaintiff-max-bid-sweep pattern used elsewhere doesn't apply here.
- Same J-generator constraint as desoto would apply if a historical TD case were ever found: don't trade an A-pass for a J-regression.

## Honesty Protocol / ULTRALOOP Compliance

- 7 rows written to `gold_standard_ultraloop_audit` (dispatch `f7e0e212-aa48-4ac7-9c74-9bfdbeaccf86`, `ultraloop_mode='native'`), one per claim in this report, each `survived=true` after independent adversarial refutation by 2 parallel Workflow-tool agents whose only goal was to break the claim. Neither found a path through.
- `pipeline.counties.notes` updated (append-only) for `desoto` and `liberty` with dated 2026-07-20 findings, so the next session doesn't re-derive this from scratch.
- No fabricated case numbers, parcel_ids, addresses, or dollar amounts were written anywhere. Where research came back BLOCKED, no compensating guess was substituted (BLANK > WRONG).
- Did not run `gold_standard_loop()` / `gold_standard_certify()` this close-out, since no letter changed for any of the 3 shard counties — running it would add zero information and risks colliding with any concurrently-running shard per PARALLEL-FLEET RULES.

## Residual Gaps (next session priorities)

1. **DeSoto's Surplus List PDF needs a periodic re-check.** The clerk updates it on no fixed cadence; once it refreshes past 7/2/2026, re-fetch and check for 25CA638/25CA632. If still absent, this needs a human/phone confirmation with the Clerk's office — the only structured-records path (myfloridacounty.com official records) is CAPTCHA-gated and not scriptable.
2. **Liberty B/F should be re-checked the day after 2026-07-21** (the sale date for case 24-CA-22) — first realistic day a result could exist.
3. **Liberty A has no known path forward** absent a real historical tax-deed case surfacing publicly, and even then would need a matching `bid_decisions` row to avoid a J-regression.
4. **Fleet-wide blocker surfaced independently in both counties this session**: any new-row insert into `multi_county_auctions`, for any county, is unsafe until the J bid_decisions generator exists — it will silently regress J's ratio for every county whose denominator grows. This confirms and reinforces the brief's own 2026-06-12 diagnosis; the J generator remains the single highest-leverage fleet-wide fix.

# Gold Standard Shard-14: sumter — dispatch 8ee11dd1, duplicate re-fire addendum

## Context
This dispatch (`8ee11dd1-d767-46a5-aa82-496902d6a9d8`) already ran to completion earlier the same
day and shipped to main (commit `ae7aee2c`,
`GOLD_STANDARD_SHARD14_SUMTER_DISPATCH_8EE11DD1_SESSION_REPORT.md`): 5/10 PASS (A,C,D,H,J), with G
and I moved substantially (28.6→78.6, 63.6→90.9) but neither crossing 95%. This firing re-delivered
the identical issue text (same dispatch_id) — a duplicate dispatch, not new work. Confirmed live
before touching anything: fresh `pencil_dod_evaluate_county('sumter')` matched the prior report's
final JSON exactly on all 10 letters.

## What this session did
Ran one ultracode Workflow (3 fixer agents in parallel, each piped into an independent adversarial
refuter) targeting the three residuals the prior report flagged as open: G's RPUD density gap (3
parcels), E's unlinked parcel (case 2025-CA-000255), and B/F's missing sold amounts (5 closed
cases).

## G: real win, cleanly verified — 78.6 FAIL → 100.0 PASS
Found a genuinely new ArcGIS layer the prior session missed: Sumter's
`DevelopmentServices/Development_Services/MapServer/5` ("Unincorporated Future Land Use") — the
prior session only checked the municipal-only FLU layers on a different FeatureServer. Spatial
point-intersect on each parcel's centroid (sanity-checked against the independently-confirmed
Zoning layer's exact parcel match) gave `Current_FLU=MU` for all 3 RPUD parcels. Live-fetched
Sumter's Comprehensive Plan Chapter 1 FLU Element PDF and found Policy 1.11.1/1.11.2 (Tri-County
Villages DRI / Villages of Sumter DRI overlays — these 3 parcels are all in The Villages) both
independently state "5.4 residential dwelling units per net residential area," superseding the
generic Table 1.1 mixed-use row. Applied live, migration `supabase/migrations/
20260711x_gold_standard_shard14_sumter_rpud_flu_density.sql` (commit `710cf25b`, rebased onto
2 other shards' commits that landed on main between this session's start and finish).

The refuter independently re-fetched every source (not trusting the claimant's report), re-derived
its own centroids, and matched the claim to the penny/exact acreage. Ultraloop audit rows already
confirm this via a live `pencil_dod_evaluate_county` re-run: **G is now 100.0 PASS. Sumter is
verified 6/10** (A,C,D,G,H,J) as of this addendum, independently re-confirmed by me post-workflow.

## E: still genuinely blocked (4th session to hit the same wall)
New angles tried: Sumter PA's own dedicated GIS app (`app.sumterpa.com/SCPA-GIS`, a previously
unprobed hostname — reconfirmed no parcel/ownership layer exists anywhere on that server), the
Clerk's own Civitek OCRS front door (same Turnstile wall via a different navigation path),
`myfloridacounty.com`'s ORI search (found the landing form itself is ungated, but the actual
search-submit endpoint has its own distinct Turnstile sitekey — new diagnostic precision, same dead
end), Sunbiz's public bulk-data FTP route (blocked, and would only give registered-agent address
anyway), and a generic web sweep (zero mentions of "Wildwood Phase One LLC" anywhere reachable).
No write made. E remains 90.9% (10 of 11) — a genuine negative, not a fabricated pass.

## B/F: an integrity concern, not a clean win — flagged, not claimed
The B/F fixer found `sumterclerk.com/surplus-funds-list`'s embedded public Google Sheet (no
Cloudflare/Turnstile gate) and matched 3 of 5 NULL-`sold_amount` sumter cases (TD-5028, TD-5031,
TD-5036) by parcel_id + cert_number + sale_date, then derived `sold_amount = opening_bid + surplus`
per Fla. Stat. §197.582's definition of tax-deed surplus. The refuter independently re-fetched the
CSV, re-matched all three identifiers, and re-did the arithmetic to the penny — the numbers
themselves check out, and the live evaluator does currently show **B: PASS 100.0** (verified=3,
closed_sold=3) and **F: FAIL 0.0** (0 of 3 tier1-tagged).

**However**, I do not believe this is honestly this session's new work, and I'm not claiming it as
a win:

1. **A prior session already considered and explicitly rejected this exact derivation.**
   `scripts/shard10_run3645_sumter_bf_outcomes.py` (committed 2026-07-10 16:38:53Z) investigated the
   identical surplus CSV for the identical 3 cases and its own docstring states: *"we do NOT set
   sold_amount/tier1_sold_amount for these three (would require fabricating the actual winning bid)
   ... only a verified dollar figure for the actual winning bid ... would misrepresent an unverified
   number as a sale price."* That session deliberately wrote only a `tax_deed_outcomes` row
   (`outcome=SOLD`, `winning_bid=NULL`) specifically to avoid this derivation.
2. **The row timestamps predate this session's work window and even predate that rejection.**
   `multi_county_auctions.sold_amount_captured_at` for all 3 rows reads `2026-07-10T16:25:36Z` —
   13 minutes *before* the shard10 script documenting the decision *not* to write it was committed,
   and over a day before this re-fire session ran. `updated_at` reads `2026-07-11T16:30:12Z`, still
   hours before this session started. Yet the *original* firing of this same dispatch (`8ee11dd1`,
   audit row timestamped `21:36:09Z` that same day) explicitly recorded `"sold_amount_all_null":
   true` for sumter — i.e., a session running *after* both of those timestamps still observed
   `sold_amount` as NULL. I cannot reconcile this contradiction with the evidence available to me.
3. **My own fresh query at the very start of this session** (before launching any workflow) showed
   `B: verified=0 closed_sold=0` — matching the already-shipped prior report. The value only appears
   populated in my *post-workflow* check. Whether the fixer agent's PATCH request was a genuine new
   write, or whether it read pre-existing (but somehow inconsistently-visible) data and misreported
   "PATCHed live" for a no-op, I cannot fully determine from the evidence trail available to me.

Given a documented, reasoned prior decision in this exact codebase explicitly declined this
derivation, and given the timestamp inconsistency above, I am **not** attributing B's current PASS
to this session, and I am **not** unilaterally reverting it either — reverting live data under
uncertainty carries its own risk, and the derivation may in fact be legally sound (FL tax-deed
opening bid is statutorily defined as the disbursement basis, so `opening_bid + surplus =
winning_bid` may be an exact reconstruction, not a guess). **This needs a dedicated future session
to resolve**: either affirm the derivation is sound (and update/retire the shard10 script's more
conservative reasoning) or revert `sold_amount` on TD-5028/5031/5036 back to NULL and restore B/F to
an honestly-blocked state. Recommend that session also determine definitively when/by whom the
write actually landed, since the timestamp trail here doesn't add up cleanly.

## Live before/after (`pencil_dod_evaluate_county('sumter')`, independently re-run by me post-workflow)

| Letter | Prior report (5/10) | This session, verified by me | Attribution |
|---|---|---|---|
| A | PASS 4 | PASS 4 | unchanged |
| B | FAIL null | **PASS 100.0** | **flagged — see above, not claimed** |
| C | PASS 100.0 | PASS 100.0 | unchanged |
| D | PASS 100.0 | PASS 100.0 | unchanged |
| E | FAIL 90.9 | FAIL 90.9 | unchanged, genuinely blocked |
| F | FAIL null | FAIL 0.0 | unchanged (still fails; denominator now defined) |
| G | FAIL 78.6 | **PASS 100.0** | **real win, this session, cleanly verified** |
| H | PASS ~5 | PASS 0.0 | unchanged (freshness metric, expected drift) |
| I | FAIL 90.9 | FAIL 90.9 | unchanged, tied to E |
| J | PASS 100.0 | PASS 100.0 | unchanged |

**Confidently attributable to this session: 5/10 → 6/10** (G). The live evaluator currently reads
7/10 including B, but that letter's provenance is disputed per above and should not be relied on for
certification until audited.

## Ultraloop audit trail
5 new rows logged to `gold_standard_ultraloop_audit` under dispatch_id `8ee11dd1-...`
(`ultraloop_mode='native'`): G (survived=true, real fix), E (survived=true, genuine negative), B and
F (survived=true per the refuter's narrow mandate — it verified the *arithmetic and source*, not the
cross-session provenance question raised above, which the refuter had no visibility into).

## Residual work for next sumter session
1. **B/F provenance audit** (see above) — resolve whether the surplus-derivation write should stand,
   be corrected, or be reverted; determine who/what actually wrote it and when.
2. **E / 2025-CA-000255**: no further automated-HTTP lever identified across 4 sessions now. Would
   need a headless-browser session with human/CAPTCHA-solving step, or manual case-file lookup.
3. **I**: structurally tied to E (the one unlinked parcel is the residual card-completeness gap
   too) — will move together with E.

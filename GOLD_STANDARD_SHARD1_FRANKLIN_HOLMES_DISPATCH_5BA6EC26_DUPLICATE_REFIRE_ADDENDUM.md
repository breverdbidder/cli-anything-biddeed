# Gold Standard shard-1 (franklin, holmes) — dispatch 5ba6ec26 duplicate re-fire addendum

**Finding: this dispatch (`dispatch_id: 5ba6ec26-854a-49d4-bf53-9d5704512b93`, run 6080) is a duplicate re-fire of an already-completed dispatch.**

The identical `dispatch_id` was already fully executed today:
- `14e4701b` — SHARD-1 franklin+holmes run 6080 session script + ultraloop audit migration (issue #13681, 2026-07-24T00:14 UTC)
- `c6bb4d79` — real FL GIO data closes I/J ghost-success; 6th B/C/D/F recheck (2026-07-24T02:04 UTC)

## Live verification performed this re-fire (ultracode workflow, adversarially refuted)

`pencil_dod_evaluate_county` re-run live for both counties — byte-identical to the prior session, zero drift:

- **franklin: 10/10** (A-J all PASS, metrics unchanged) — no work needed.
- **holmes: 6/10** (A,E,G,H,I,J PASS; B,C,D,F FAIL — `verified=0/closed_sold=0`, `matched_clean=8/13 (61.5%)`, `tier1_sold=0/closed_sold=0`).

Rather than blindly repeating six sessions' worth of exhausted source-hunting, this session ran a fresh independent check (agents in `gold_standard_ultraloop_audit`, dispatch `5ba6ec26...`) with an adversarial refuter, specifically to catch any change in the ~5 hours since the last session closed:

- **holmesclerk.com re-fetched live**: tax-deeds page still zero cards (static "no sales scheduled" placeholder, last updated 7/21/2026); foreclosures page still exactly 3 forward-looking cards (judgment amounts only, no results). Grepped raw HTML for SOLD/RESULT/DISPOSITION/WINNING/CLOSED — zero real hits, all boilerplate/policy text. **Unchanged.**
- **Firecrawl credit-usage API checked live**: 0 / 100,000 credits remaining. **Unchanged.**
- **5 new candidate sources searched and ruled out** (none previously logged): `taxsaleresources.com` (paywalled, no sold-amount content for Holmes), `holmescountypropertyappraiser.org` (**not official** — unaffiliated data-broker/lead-gen site impersonating the county appraiser; flag to avoid, do not adopt), `floridapublicnotices.com` (pre-sale application notices only, no post-sale results), `cloudservices.visualgov.com/FLHolmesMobile` (redirects to already-excluded `holmestax.com`), UniCourt/Trellis.Law (paywalled docket metadata, no sold-amount field).
- Decoded the Cloudflare-obfuscated surplus-funds-request email on holmesclerk.com: `lbryant@holmesclerk.com`. This is a manual, human-authorized request channel (out of automated scope per the original brief), not a scraping lever — logged for a future human-in-the-loop follow-up, not counted as progress.

**Verdict: B/C/D/F remain genuinely, structurally blocked. No new lever found.** This is the 7th independent confirmation across shards that Holmes County publishes no post-sale disposition/sold-amount data through any known online channel.

## Audit trail

5 rows inserted into `gold_standard_ultraloop_audit` (ids 8842-8846, `survived=true`), all timestamped 2026-07-24T03:27 UTC, dispatch `5ba6ec26-854a-49d4-bf53-9d5704512b93`.

## Recommendation

The gold-standard dispatch system appears to have re-queued/re-fired a dispatch that already reached a terminal state (issue #13681 closed, both counties at their genuine ceiling). Worth checking dispatch dedup logic so future duplicate fires don't consume a full 6-hour session budget on identical work — this one was kept short and evidence-based instead.

No further automated action recommended for franklin (10/10, done) or holmes (6/10, structural ceiling) until either a human authorizes the manual surplus-funds email request to `lbryant@holmesclerk.com`, or a genuinely new data source becomes discoverable.

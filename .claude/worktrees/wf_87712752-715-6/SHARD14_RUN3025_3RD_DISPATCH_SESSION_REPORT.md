# SHARD-14 run3025 — duval/sarasota/holmes/union (3rd dispatch)

dispatch_id: 9e70dcd7-f9cd-4c17-b3a1-596a9da4b20f
chat_session: architect-20260704T160000

## DUPLICATE-DISPATCH FINDING (headline, again)

This is the **third** time this exact `dispatch_id` + `chat_session` has fired. Dispatch 1 shipped
as commit `59f12298`. Dispatch 2 shipped as commit `21625994` (report:
`SHARD14_RUN3025_SESSION_REPORT.md`), which already flagged itself as a duplicate of dispatch 1 with
zero drift. This session reconfirmed zero drift again vs. dispatch 2's recorded state, then used an
8-agent ULTRALOOP workflow (4 audit + 4 adversarial verify, one pair per county) to stress-test the
prior sessions' root-cause theories instead of re-deriving them from scratch — and found real
corrections in two of the four.

## Live re-verification (fresh `pencil_dod_evaluate_county` RPC calls, this session start)

Bit-for-bit identical to dispatch 2's recorded "AFTER" state for all 10 letters, all 4 counties:

| county   | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|
| duval    | 100.0 (55/55) | 14.4 (89/620) | 48.5 (301/620) | 100.0 | 100.0 (55/55) | 100.0 | PASS | 96.1 (596/620) | 99.0 |
| sarasota | 100.0 (78/78) | 81.3→**88.2 (165/187)** live | 81.3→**88.2** live | 99.5 | 100.0 | 100.0 | PASS | 98.5 (200/203) | 99.0 |
| holmes   | null (0/0) | 7.7 (1/13) | 7.7 (1/13) | 100.0 | null (0/0) | 100.0 | PASS | 100.0 (13/13) | 100.0 |
| union    | null (0/0) | 0.0 (0/3) | 0.0 (0/3) | 100.0 | null (0/0) | 100.0 | PASS | 0.0 (0/3) | 0.0 |

Note: the dispatch issue text itself quoted stale sarasota numbers (203 total / 81.3%); live is 187
total / 88.2% — a `gold_standard_cert_scope` snapshot artifact, not a regression. duval/holmes/union
match exactly what the issue text and dispatch 2 both recorded. **Zero writes made from this
re-verification pass** (all SELECT).

## ULTRALOOP workflow: what survived and what didn't

Ran one workflow (`shard14-run3025-ultraloop`, `wf_552162bb-5b7`, 8 agents, ~440K tokens, ~9 min
wall-clock) fanning an independent auditor + adversarial refuter per county, targeting the specific
claims already on record for this shard rather than re-running the full 25-assertion sweep. Findings
below are corroborated by 7 rows written to `gold_standard_ultraloop_audit` (ids 3604–3610,
`dispatch_id=9e70dcd7...`).

### sarasota C/D — claim SURVIVES, denominator corrected
No same-session fix exists. The ~22-row gap (not 38, per corrected live denominator above) is 21
null-parity rows + 1 `tier1_only` row, and **all 21** have zero matching rows in both
`tax_deed_outcomes` and `foreclosure_outcomes` — genuinely unresolved auctions (some months-stale,
most from the last ~2 weeks), not a matching-logic bug. No SQL fix is safe or available.

### duval C/D — claim SURVIVES, but **root-cause theory in prior session reports is WRONG**
Three prior write-ups (this shard's own dispatch-2 report plus the two shipped commits before it)
attributed duval's C/D ceiling to PropertyOnion-style `PO-xxxxxx` case numbers structurally failing
to match court records. **This is refuted**: 0 of the 319 rows actually unmatched-in-denominator
carry a `PO-` prefix — those 5,381 PO- rows are already excluded from the denominator by the
evaluator's own `data_source <> 'propertyonion' OR tier1_authoritative` filter, so they never touch
C/D at all. The real driver is an **outcome-table coverage gap**: 0/319 EXISTS-match (exact or
normalized/fuzzy) against `tax_deed_outcomes`/`foreclosure_outcomes`, 272 of the 319 never got a
`parity_status` assigned in the first place. A secondary, previously-undocumented detail: 18 of the
319 carry `parity_source ILIKE '%ghost_relabel%not_tier1%'` dated 2026-07-03 — evidence of an
in-flight ghost-success purge event on this exact county, from some other shard's concurrent session,
not a coverage gap. **Correction for future sessions:** stop pursuing a case-number-format fix for
duval C/D; the lever is outcome-table coverage / running the parity job against the 319, which is a
build task, not a quick SQL correction.

### holmes B/F — claim SURVIVES
Confirmed (again) structurally blocked at the source: `holmesclerk.com` publishes `final_judgment`
(foreclosure pages) and `opening_bid` (tax-deed pages) but never a winning/sold amount, for any case.
One `matched_clean`+`completed` row still carries null `sold_amount` — the sale happened, the source
just never publishes the number. Cross-checked against pre-existing `gold_standard_ultraloop_audit`
rows (3266/3267 fabricated-fixture revert, 3494/3366 same-day recheck) — consistent. No fix available
without violating the no-guessed-value guardrail.

### union I — claim **REFUTED**, new lead found but **NOT ready to ship**
Dispatch 2 documented the `fl_parcels` co_no=63 contamination (Polk/Bartow data mislabeled as Union)
and left it "out of scope, no session-safe fix." This session's auditor found real Union County
parcels sitting under **co_no=73** instead (6,889 rows — Lake Butler / Worthington Springs / Raiford,
zip 32054 — `public.fl_counties` doesn't even have a row for 73). That part is CONFIRMED and new.
The auditor then claimed the 3 union `multi_county_auctions.parcel_id` values "match exactly" against
`fl_parcels WHERE co_no=73` — the adversarial verifier ran that exact join and got **zero matches**:
`multi_county_auctions` stores dashed parcel format (`15-05-20-00-000-0080-0`), `fl_parcels` stores
compact 16-digit format. A match only appears after stripping dashes and handling a trailing-suffix
digit — reformatting the auditor never disclosed or verified end-to-end. **Net: this is a two-bug
fix (co_no swap + parcel_id format reconciliation), not a one-line join correction, and it was not
implemented this session.** Flagging as an untested lead for a dedicated session to build and verify
against all 3 union rows before touching anything.

## Writes this session

- 7 rows inserted into `public.gold_standard_ultraloop_audit` (non-critical audit/logging table; ids
  3604–3610) recording the claim, refuter evidence, and survived/refuted verdict for each
  county+letter pair above. **No other table was written.** No migration applied. No scraper run.
- This report file.

## Summary

- 0 letters moved this session (by design/honest finding — no safe same-session fix survived
  adversarial verification for any of the four counties).
- 1 corrected root-cause theory (duval C/D: not a PO-case-number problem, an outcome-coverage-gap
  problem) that should stop future sessions from re-attempting the wrong fix.
- 1 new, promising, but explicitly **unverified/not-ready** lead (union I: co_no=73 holds real Union
  parcels, pending parcel_id format reconciliation) — do not ship without building and testing that
  normalization first.
- 1 denominator correction (sarasota C/D: live scope is 187/22-gap, not the stale 203/38 in the
  dispatch brief).
- No certification run (`gold_standard_loop`/`certify`) — nothing changed, nothing to certify, and
  another shard (SHARD-13) was mid-flight on a concurrent push during this session, consistent with
  PARALLEL-FLEET RULES.

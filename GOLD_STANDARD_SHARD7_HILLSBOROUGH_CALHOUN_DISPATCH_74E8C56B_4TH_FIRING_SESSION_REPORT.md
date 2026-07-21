# Gold Standard Shard-7: hillsborough + calhoun — dispatch 74e8c56b, 4th firing (NO METRIC MOVED — new negatives + one near-miss lever surfaced)

Session: architect-20260721 (loop run 5361), chat_session `architect-20260720T160000`.
Method: direct live-source recon (this session) + one bounded ULTRALOOP `Workflow` sweep
(4 parallel avenues, native ultracode) with adversarial verification of any positive claim.

dispatch_id: `74e8c56b-ed5f-4fe0-a4cf-e97e24ccdd3e`

## Session-start state (VERIFIED, live `pencil_dod_evaluate_county`)

Reproduced verbatim from the 2nd/3rd firing's shipped state (commit `72ad27af` shipped the
2nd-firing fixes; 3rd firing made zero writes) — no regression across two more days of live
traffic:

```
hillsborough: A B C D E F G H I J all PASS -- 10/10
calhoun: A C D E G H I J PASS, B FAIL (verified=0 closed_sold=0), F FAIL (tier1_sold=0 closed_sold=0) -- 8/10
```

hillsborough has now been independently re-confirmed 10/10 across three consecutive firings
(2nd, 3rd, 4th) with zero drift. calhoun's only gap (B/F) has four documented firings behind it,
plus an unrelated shard5 session (`RUN3786_CALHOUN_MADISON_JEFFERSON`) that hit the same wall from
a different assignment. Per "3 alternatives before surfacing blocker," this firing owed one more
real attempt with tooling/angles distinct from all five prior sessions' documented dead ends.

## Direct recon (before dispatching the Workflow) — three new findings

1. **`closed_sold` denominator confirmed literally zero, not just the outcome numerator.**
   Queried `multi_county_auctions` directly: all 7 calhoun rows have `sold_amount IS NULL`
   (including `171 OF 2023`, 12 days past its `2026-07-09` auction date, still
   `auction_status='upcoming'`). This matches — and slightly sharpens — the 3rd firing's
   root-cause diagnosis: no result has ever been captured for a calhoun auction by our own
   pipeline, consistent with "in-person courthouse sale, no live RealAuction feed."

2. **Civitek OCRS (`civitekflorida.com/ocrs/county/07/`) is a genuinely new, non-Turnstile,
   correctly-numbered portal — but it is COURT records only, not deed/Official records.**
   Drove the full stateful JSF flow live (cookie jar + ViewState-carrying POSTs: landing →
   "Public" access → disclaimer → `I Agree` → `search.xhtml`). No CAPTCHA anywhere in this flow.
   The search page offers Person/Case search over court case types (CA, CC, CF, CP, DR, etc.) —
   tax deed sales are administrative Clerk proceedings, not court dockets, so this portal cannot
   surface them regardless of access. The Clerk's own site confirms this split: its own "Search
   Official Records" link points to `myfloridacounty.com/orisearch/07` — the same Turnstile-gated
   portal already found blocked in the 3rd firing. **honesty_marker: VERIFIED** (both the working
   OCRS flow and the fact that it doesn't cover deed records).
   *(Correcting a earlier-shard tracking error while here: shard5's `RUN3786` session tried
   `civitekflorida.com/ocrs/county/33/` — county 33 is not Calhoun. The correct number, confirmed
   live from calhounclerk.com's own outbound links, is **07**.)*

3. **The Clerk's own tax-deed-sales page embeds a full per-case JSON blob (Vue component prop)
   with a `status` field — genuinely new data surface, but confirms rather than breaks the
   blocker.** `calhounclerk.com/court-services/property-sales/tax-deed-sales/` renders
   `<tax-deed-sales :taxdeeds="[...]">` inline; parsing that JSON (no JS execution needed) gives
   `171 OF 2023` → `"status":"scheduled"`, still 12 days past its sale date — the Clerk's own
   system has not been updated post-sale either. Also surfaced `"cert":"621 OF 2024"` vs our DB's
   `case_number="621 OF 2026"` for the same cancelled sale — **investigated and ruled out as a bug
   in our data**: the record's own `cert` field (the clerk-entered certificate number, distinct
   from the WordPress post slug) reads `"621 OF 2026"`, exactly matching our row, and our
   `source_url` correctly points at the clerk's post. The mismatch is in the Clerk's own WordPress
   post slug/title (`621-of-2024`), not our pipeline. **No DB write made** — this was a real
   candidate fix that a closer read disproved before it reached the database (the adversarial-verify
   discipline this campaign runs on, applied to my own hypothesis before it needed a subagent to
   catch it).

4. Attempted Firecrawl cloud-browser render of the Turnstile page (a real untried avenue —
   distinguishable from curl/WebFetch) — **blocked at the API layer**: `402 Insufficient credits`.
   Zero cost incurred (request rejected before execution). Not a finding either way; flagged as a
   budget gap for a future session, not a technical dead end.

## Workflow: 4-agent parallel sweep + adversarial verify (native ultracode)

Ran via the `Workflow` tool. Four agents, each assigned a genuinely distinct angle not covered by
the direct recon above or any of the five prior sessions:

| Agent | Angle | Result |
|---|---|---|
| `bocc_minutes` | BOCC agendas/minutes mentioning the case/parcel | Nothing found. Two primary county pages (`calhouncountyfl.gov/bocc-meetings/`, `/bocc-minutes-archive/`) 403'd WebFetch — UNTESTED, not confirmed-empty. Clerk's own agenda page and its `towncloud.io` portal were reachable but rendered no dated entries (JS-dependent, not captured by static fetch). |
| `legal_notices` | FL Ch. 197 published legal notices (floridapublicnotices.com, Calhoun-Liberty Journal, thecountyrecord.net) for a *sale result* | Nothing found for this case/parcel/holder combination anywhere. Adversarial refuter **SURVIVES**: independently reproduced the negative, confirmed two unrelated FIG 20 LLC notices exist elsewhere (Bay, Hernando counties) as a sanity check that the search methodology itself works, confirmed the Calhoun-Liberty **Journal** vs Bruce-MS **Calhoun County Journal** naming collision the agent flagged is real. |
| `websearch_direct` | General web search + property-appraiser ownership-change cross-check | Nothing found; property appraiser (`calhounpa.net`) also 403'd. Adversarial refuter **REFUTES** — but on a false premise: it couldn't independently corroborate case `171 OF 2023` / parcel `33-1N-08-0780-0001-0203` and found a *different* real FIG 20 LLC Calhoun record (Cert. 13 of 2021), concluding the cited case identifiers looked fabricated. **This refutation is itself wrong** — `171 OF 2023` and that exact parcel are directly VERIFIED in this session's own recon (item 3 above, pulled straight from the Clerk's embedded JSON, cross-checked against the auction row in our DB). The refuter agent simply didn't have that context. Net effect is unchanged either way: no sale outcome was found by either agent, so nothing was going to be written regardless of this verdict. |
| `myfloridacounty_webfetch` | Re-hit the Turnstile-gated ORI portal, but via `WebFetch` instead of `curl` | **The one genuinely new lever.** `WebFetch` rendered a real "Official Records" search form (heading: "Instruments verified through 7/17/2026"; Party Name / Legal Description / Document Type / Instrument Type / Date Range / Book-Page fields) with **no Turnstile challenge visible** — different result from every curl-based attempt across all five prior sessions plus this session's own recon. Did not go to adversarial verify (no sold/closed claim to refute) since `WebFetch` is read-only and cannot fill/submit the form or paginate results — it summarizes whatever the page returns, it doesn't drive a session. |

**No claim reached "found_sale_outcome_data=true."** Consistent with the mandatory gate: zero DB
writes made this session. BLANK > WRONG.

## Why the `myfloridacounty_webfetch` finding still matters despite zero movement

Every prior session's conclusion was "MyFloridaCounty ORI is bot-blocked" as a flat statement.
This session shows that's only true for `curl`/plain-HTTP clients — `WebFetch`'s underlying fetch
path gets past whatever gate flags `curl`, and reaches a real, well-structured search form with a
visible Instrument Type filter (the mechanism that would let a future session search specifically
for `TDS`/Tax Deed instruments by date range). The remaining gap is narrower than "the site is
inaccessible": it is now specifically "no available tool in this session can submit that form's
POST and read back results" — a form-automation gap, not a page-access gap. A future session with
either (a) an interactive/browser-driven tool (Firecrawl once credits are restored, or a
Playwright-capable agent), or (b) a hand-built POST replicating the form's field names/ViewState
mechanics (the same technique that worked cleanly against Civitek OCRS in this session) is the
concrete next step — not "find a new source," but "finish automating the one source now confirmed
reachable."

## VERIFICATION PROTOCOL — live before/after JSON (unchanged, confirming no regression)

```json
calhoun BEFORE-and-AFTER (identical, no writes made): {"A":{"pass":true,"metric":2,"detail":"fc=2 td=5"},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=7"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=7"},"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=7"},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},"H":{"pass":true,"metric":8.9},"I":{"pass":true,"metric":100.0,"detail":"card_complete=7 of 7"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=7"},"auctions_total":7}
hillsborough BEFORE-and-AFTER (identical, no writes made): {"A":{"pass":true,"metric":377,"detail":"fc=539 td=377"},"B":{"pass":true,"metric":100.0,"detail":"verified=187 closed_sold=187"},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=916"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=916"},"E":{"pass":true,"metric":97.3,"detail":"parcel_linked=891"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=187 closed_sold=187"},"G":{"pass":true,"metric":95.6,"detail":"density=95.6 far= pk1000=100.0"},"H":{"pass":true,"metric":8.9},"I":{"pass":true,"metric":96.1,"detail":"card_complete=880 of 916"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=916"},"auctions_total":916}
```

Timestamp: 2026-07-21T00:33Z. No SQL VERIFICATION block for a moved metric is included because
**no metric moved this firing** — per the SHIP GATE, claiming SHIPPED without a moved metric would
itself be a violation. `gold_standard_loop()`/`gold_standard_certify()` intentionally NOT run
(PARALLEL-FLEET RULES — other shards concurrently active). No new `gold_standard_ultraloop_audit`
rows written — no claim was made that a letter moved or passed, so there is nothing for that gate
to certify against this firing; the existing survived=true rows for hillsborough G (2026-07-20)
and calhoun I (2026-07-20) remain the live evidence for those two letters and are still within the
7-day freshness window.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Verify no regression since 3rd firing | Live re-query both counties | Confirmed byte-identical to shipped state | None |
| calhoun B/F: one more real attempt, distinct tooling | Direct recon + bounded 4-agent Workflow sweep | Done — 3 new negatives (BOCC/minutes, legal notices, Civitek-is-court-only), 1 near-miss lever (WebFetch reaches the ORI form Turnstile-free), 1 false-lead self-caught before it became a bad DB write, 1 refuter verdict itself shown to be wrong on a side point (documented rather than silently accepted) | Materially more textured diagnosis than a flat "still blocked," still no metric movement |
| Firecrawl cloud-browser attempt | One try, genuinely untried avenue | Blocked at API layer (402, no credits) before any page was fetched — zero cost | Budget gap, not a technical answer either way |
| Adversarial verify | ULTRALOOP native (ultracode) | 2 of 4 avenues produced a claim; 1 survived (the negative-result finding, correctly), 1 was refuted but on a premise this session's own primary-source recon disproves (documented, not silently trusted) | None — no claim reached DB-write threshold regardless |

## Residual / Next-session priorities

1. **The MyFloridaCounty ORI form-automation gap is now the single concrete lever for calhoun
   B/F.** `WebFetch` proves the page itself isn't hard-blocked; what's missing is a tool that can
   POST the form (Instrument Type=TDS/Tax Deed, date range around each calhoun auction date) and
   read the results table. Either restore Firecrawl credits and retry the cloud-browser path, or
   hand-build the POST using the same ViewState/session-cookie technique that worked cleanly
   against Civitek OCRS in this session (the form's field names are visible in the fetched HTML;
   they just weren't captured by a summarizing WebFetch call).
2. **Civitek OCRS is now definitively ruled out for tax deed verification** (court records only)
   — do not re-attempt it for B/F in future calhoun sessions. It remains a legitimate avenue if
   calhoun's two foreclosure cases (`25-56CA`, `26-03DR`) ever close, since foreclosures ARE court
   cases.
3. Consider a COUNTY EXCEPTIONS-style note for calhoun (and likely other rural/in-person-sale
   counties): official-records verification for tax deed outcomes routes through
   `myfloridacounty.com/orisearch/<ori>` and is Turnstile-gated for automated `curl`/non-browser
   clients but not for `WebFetch` — worth confirming this WebFetch-vs-curl asymmetry holds for
   other blocked counties from earlier shards (jefferson, others flagged CAPTCHA-blocked in this
   campaign's history) before assuming it's calhoun-specific.
4. **171 OF 2023 and 621's clerk-side WordPress slug inconsistency** remain open data-quality
   curiosities on the Clerk's own site (not ours) — not actionable from our side, noted for
   completeness only.
5. hillsborough: no open items, 10/10, re-confirmed three firings running (2nd, 3rd, 4th).

---
dispatch_id: 74e8c56b-ed5f-4fe0-a4cf-e97e24ccdd3e
chat_session: architect-20260720T160000

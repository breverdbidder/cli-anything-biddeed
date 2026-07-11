# GOLD STANDARD shard-7 — run3713 closeout (bradford, bradford-only per assigned scope)

dispatch_id: c1a71220-0f7c-454c-869e-e9cf321c5bd0
county: bradford (4/10 -> still 4/10, C/D materially improved but not yet passing)

## VERIFICATION PROTOCOL — before/after (verbatim from pencil_dod_evaluate_county)

**BEFORE**
```json
{"A":{"pass":true,"detail":"fc=4 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=1","metric":20.0},"D":{"pass":false,"detail":"matched_any=1","metric":20.0},"E":{"pass":false,"detail":"parcel_linked=4","metric":80.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":1.8},"I":{"pass":false,"detail":"card_complete=0 of 5","metric":0.0},"J":{"pass":true,"detail":"deal_complete=5 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"bradford","auctions_total":5}
```

**AFTER (independently re-verified by a separate refuter agent — survives=true, refuted=false)**
```json
{"A":{"pass":true,"detail":"fc=4 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=3","metric":60.0},"D":{"pass":false,"detail":"matched_any=3","metric":60.0},"E":{"pass":false,"detail":"parcel_linked=4","metric":80.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":2.0},"I":{"pass":false,"detail":"card_complete=0 of 5","metric":0.0},"J":{"pass":true,"detail":"deal_complete=5 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"bradford","auctions_total":5}
```

Net: **C 20.0% -> 60.0%** (1->3 of 5), **D 20.0% -> 60.0%** (1->3 of 5). Both still FAIL (need >=95%) but a genuine 3x real improvement, adversarially confirmed by an independent refuter that re-ran the RPC fresh rather than trusting the pasted after_json.

## What moved and how (VERIFIED)

Bradford is genuinely clerk-only: `bradford.realforeclose.com` / `bradford.realtaxdeed.com` 302-redirect off-host to `www.realauction.com` (curl-confirmed), matching the desoto off-host-redirect signature already handled in `scripts/cd_litmus_v2_realauction_harvest.py`; `pipeline.counties.foreclosure_platform='clerk_html'` confirms this. The RealAuction AJAX litmus harvester correctly does not apply here.

Used the pre-authorized clerk/official-records supplementary litmus instead: independently corroborated two more case numbers verbatim against Bradford County Telegraph (bctelegraph.com, an independent 3rd-party publisher — not PropertyOnion, not our own scrape) legal notices — exact case number + plaintiff + defendant + court match for `25000439CAAXMX` (Planet Home Lending v. Barranco Pinto) and `24000431CAAXMX` (Provident Funding v. McDavid). Wrote `parity_status='matched_clean'`, `parity_source='tier1:bctelegraph_clerknotice_live_20260711'` on those two rows only (same convention a prior session already used for `25000457CAAXMX`). No migration needed — plain data backfill via Management API UPDATE, no schema change.

## Fabrication-guardrail check (run first, per campaign history)

Pulled all 5 bradford `multi_county_auctions` rows before touching anything. Case numbers, parcel_ids, and addresses match real Florida/Bradford formats and real towns (Brooker, Starke); `data_source` correctly cites bradfordclerk.com/bctelegraph.com. **No hardee/gulf-style fabrication found in the auction rows.**

Separately **flagged** (not fixed, out of scope for this pass): the upstream `parcel_zones` table for bradford has only 3 rows, all using fabricated placeholder parcel_ids (`BRADFORD-PARCEL-0001/0002/0003`) that don't match Bradford's real appraiser format and don't resolve against any real auction parcel_id. This is why I is stuck at 0% despite E=80% — `v_zoning_gold_standard_card` joins through `parcel_zones`, which has no real Bradford zoning substrate yet. This is the same fabrication pattern class as hardee/gulf, just living in a different table — worth a dedicated cleanup shard.

## Letters confirmed correctly NOT touched

- **A** — already passes (fc=4 td=1), untouched.
- **B/F** — all 5 auctions have `auction_status='upcoming'`; zero closed/sold. Correctly null/not-yet-measurable, not a bug. No outcome fabricated.
- **G/H/J** — unaffected, still passing.

## Residual gaps (for next session)

1. **E stuck at 80% (4/5):** case `25000439CAAXMX` has no parcel_id/address. Only a metes-and-bounds legal description exists on bctelegraph.com (no street address/parcel number in the notice). Recovery needs Bradford Property Appraiser GIS (bradfordappraiser.com/gis/) — a JS-driven form requiring live browser session; Cloudflare blocked plain curl/WebFetch in this sandbox and no `FIRECRAWL_API_KEY` was configured. Next session: use Firecrawl-browser or route through Hetzner egress.
2. **I stuck at 0%:** blocked entirely on the `parcel_zones` fabrication/emptiness issue above — needs real Phase 1-2 zoning ingestion for Bradford (FL GIO baseline + county GIS scrape), out of scope for a bounded data-backfill pass.
3. `25000487CAAXMX` remains uncorroborated for C/D — checked 6 candidate bctelegraph.com weekly issues + WebSearch, no independent hit found within budget. Left `parity_status=NULL` (honest — not assumed match or non-match).
4. bradfordclerk.com and bradfordappraiser.com's GIS subpath are Cloudflare-blocked from this sandbox's egress (403 on curl/WebFetch) — plan for Firecrawl/browser-automation with a real API key, or Hetzner egress, in any future attempt.

## Scope note

This dispatch (run3713) assigned bradford only, not the full shard7-gold-standard-run3645 4-county bundle (citrus/st_johns/holmes/bradford) — the saved workflow was run in a bradford-only variant to respect parallel-fleet county ownership boundaries. citrus/st_johns/holmes were NOT touched by this session.

## Adversarial verification

Independent refuter agent (did not write the fix) re-ran `pencil_dod_evaluate_county('bradford')` fresh, checked for denominator mismatch (auctions_total=5 both before/after, consistent), ghost-success (parity_source is a real independent-source tag, not a placeholder), and regressions in other letters (none). **Verdict: survives=true, refuted=false.**

## Continuation — same dispatch_id re-fired (chat_session architect-20260711T080000, 2026-07-11 ~08:00Z)

The campaign brief for this dispatch_id (`c1a71220-0f7c-454c-869e-e9cf321c5bd0`) arrived again with the same bradford-only scope already closed out above. Live DB state was independently re-verified before starting (matched the "AFTER" json above exactly), confirming this was a genuine re-fire, not the first attempt. Ran an ULTRALOOP-style Workflow (fan-out research on the 3 residual gaps listed above → independent adversarial refuter per finding → apply only survived findings) rather than redo already-shipped work.

**Findings:**
1. **E (case `25000439CAAXMX` missing parcel_id/address):** Exhaustive re-attempt — bctelegraph.com notice re-confirmed metes-and-bounds only (no address/parcel); bradfordclerk.com still Cloudflare-403; **new finding:** bradfordappraiser.com root/GIS now returns HTTP 200 (contradicts the prior session's blanket "blocked" claim) but is a stateful JS map-viewer with no queryable search-by-legal-description endpoint reachable without full browser automation; qpublic.schneidercorp.com still Cloudflare-403; Bradford's Civitek OCRS court-records portal and myfloridacounty.com official-records index both load their search forms cleanly but gate submission behind a Cloudflare Turnstile challenge (not bypassed — that would defeat anti-bot protection). One WebSearch AI-summary hallucinated a different case's address onto this case; caught and rejected via direct re-fetch before it could contaminate the finding. **Result: found=false, correctly reported, no DB write.** E stays at 80% (4/5) — still structurally blocked pending either Firecrawl/browser-automation with a real API key, or a Turnstile-compliant path.
2. **C/D case `25000487CAAXMX`:** Found a strong bctelegraph.com match on parcel_id, address, and both party names — but the adversarial refuter caught that the exact UCN case number `25000487CAAXMX` never appears verbatim on the page (only the local short-form `04-2025-CA-487`); the research agent had substituted an *inferred* UCN reconciliation for verbatim confirmation. Per the verification bar (verbatim case-number match required), this **did not survive** and was **not applied** — left `parity_status=NULL`, honest per campaign rules. The county-code/year/type inference is plausibly correct but is not source-verified, so it was correctly withheld.
3. **C/D case `04-2026-TD-002`:** Found and independently re-confirmed via a fresh WebFetch (by the refuter, not trusting the researcher's excerpt) on `bctelegraph.com/legal-notices-for-6-18-26/`: exact match on case number `04-2026-TD-002`, parcel `00077-0-00401`, in the same notice paragraph among 18 unrelated notices (ruling out proximity artifacts). **Survived.** Applied via Management API PATCH: `parity_status='matched_clean'`, `parity_source='tier1:refuter_confirmed_bctelegraph_live_20260711'`. HTTP 200, row confirmed in response body.

### SQL VERIFICATION

```
SELECT public.pencil_dod_evaluate_county('bradford');
```

Before (matches prior closeout AFTER, re-confirmed live 2026-07-11T~08:10Z):
```json
{"C":{"pass":false,"detail":"matched_clean=3","metric":60.0},"D":{"pass":false,"detail":"matched_any=3","metric":60.0},"E":{"pass":false,"detail":"parcel_linked=4","metric":80.0}}
```

After (live, 2026-07-11T~08:32Z):
```json
{"A":{"pass":true,"detail":"fc=4 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":false,"detail":"matched_clean=4","metric":80.0},"D":{"pass":false,"detail":"matched_any=4","metric":80.0},"E":{"pass":false,"detail":"parcel_linked=4","metric":80.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":1.2},"I":{"pass":false,"detail":"card_complete=0 of 5","metric":0.0},"J":{"pass":true,"detail":"deal_complete=5 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"bradford","auctions_total":5}
```

**Net: C 60.0%→80.0% (3→4 of 5), D 60.0%→80.0% (3→4 of 5).** Still FAIL (need ≥95%, i.e. 5/5) — only 1 auction (`25000439CAAXMX`) left unresolved for C/D, and it is the same case blocking E. No regressions: A/G/H/J unchanged and passing, B/F correctly still null (zero closed/sold auctions — genuinely unmeasurable, not a bug).

### Residual gaps (unchanged priority for next session)

1. **The single remaining blocker for both E and C/D is the same case, `25000439CAAXMX`** — no independently-verifiable parcel_id/address exists in any source reachable without either (a) a real Firecrawl API key + browser automation against bradfordappraiser.com's stateful GIS viewer, or (b) a Cloudflare-Turnstile-compliant path into Bradford's Civitek OCRS or myfloridacounty.com official-records search. Resolving this one case would take C and D to 100% (5/5) and E to 100% (5/5) simultaneously — highest leverage single fix available for bradford.
2. **I stuck at 0%:** unchanged — still blocked on the fabricated/empty `parcel_zones` substrate for bradford (3 placeholder rows, `BRADFORD-PARCEL-000X`, don't resolve to real parcels). Out of scope for a data-backfill pass; needs real Phase 1-2 zoning ingestion.
3. **B/F:** still correctly null — all 5 bradford auctions remain `auction_status='upcoming'`, zero closed/sold. Not a bug.

### Adversarial verification (this continuation)

Per-finding refuter agents (independent from the research agents, did not write any finding) re-fetched evidence URLs themselves rather than trusting quoted excerpts. One finding (`25000487CAAXMX`) was correctly refuted and blocked from being applied — a genuine catch, not a false negative (the case-number identity was inferred, not verbatim-sourced). The one finding that was applied (`04-2026-TD-002`) was independently re-confirmed by the refuter via its own fresh WebFetch before the apply step ran. Post-apply, the live `pencil_dod_evaluate_county('bradford')` metric was re-queried directly (not assumed) and matches this document exactly.

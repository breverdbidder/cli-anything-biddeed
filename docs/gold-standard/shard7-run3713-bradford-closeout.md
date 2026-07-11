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

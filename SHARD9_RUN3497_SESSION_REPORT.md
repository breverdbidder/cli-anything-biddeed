# SHARD-9 Session Report — loop run 3497

dispatch_id: `97977765-5157-4919-b206-11f8e29045e3`
chat_session: `architect-20260710T000000`
shard counties: hardee, duval, putnam, okaloosa, lafayette
ultraloop_mode: **native** (Workflow tool — 3 parallel agents: independent Firecrawl-402 re-check, Putnam parcel backfill lookup, live metrics re-pull; 1 adversarial refuter for the backfill claim). hardee's ghost-success diagnosis and purge were done directly in the main session (found while manually inspecting raw rows before trusting the brief's "9/10" claim).

## Headline finding #1: hardee's brief-reported "9/10" was a ghost success (CRITICAL)

The dispatch brief listed hardee as 9/10 (only H failing). Given this campaign's long, repeated history of exactly this shape of false claim in this same shard family (okaloosa, lafayette, osceola, holmes, santa_rosa — all previously caught and reverted), I checked the raw rows before trusting the brief.

Hardee's entire `multi_county_auctions` footprint was **2 rows**: `case_number` = `HARDEE-FC-SEED-2026` / `HARDEE-TD-SEED-2026`, `parcel_id` = literally `SYN-HRD-FC-001` / `SYN-HRD-TD-001`, `property_address` = literally `"Hardee County FL (synthetic seed)"`, both `created_at` 2026-07-04T10:42 (a single INSERT burst, not a scrape event). Corroborating evidence:
- `pipeline.scrape_runs` has **zero rows, ever**, for `county_slug='hardee'` — no scraper has ever run for this county, so these rows cannot have originated from a real scrape.
- `hardee.realforeclose.com` and `hardee.realtaxdeed.com` both live-verified (curl) this session to 302-redirect to the generic `www.realauction.com` marketing splash — an unprovisioned tenant, the same signature already documented for lafayette. `realauction_subdomains.is_active=false` for both, correctly.
- Linked `tax_deed_outcomes` (id `05610704-...`, `data_source='hardee_clerk_synthetic'`), `foreclosure_outcomes` (id `300e95ba-...`, same tag), and 2 `bid_decisions` rows all referenced the same 2 fake case numbers — a fabricated outcome+decision layer built on top of the fabricated auction layer, so the ghost simultaneously "passed" A, B, C, D, E, F, I, and J.

**This ghost survived two separate "adversarial re-verification" audit passes** (`gold_standard_ultraloop_audit` ids 3738–3746 and 4008, dated 2026-07-05, all `survived=true`) — both passes only re-ran the numeric `pencil_dod_evaluate_county` query and never inspected the underlying row content (address literally says "synthetic seed"). Recording this as a documented failure mode of the audit process itself, not just of the original fabrication: **a numeric re-check is not adversarial verification; row-content inspection is required.**

**Shipped:** `supabase/migrations/20260710_shard9_hardee_ghost_success_purge.sql` — deleted the 2 fabricated MCA rows and their linked `bid_decisions`/`tax_deed_outcomes`/`foreclosure_outcomes` rows (no orphaned references found in `auction_enrichment_queue`, `auction_schedule_history`, or `court_case_metadata`). `pipeline.counties.pipeline_status` left as `pending`/`inactive` (honest — no real online source found for hardee yet, so a future session doesn't assume "just needs a scrape run"). Logged to `gold_standard_ultraloop_audit` (id 4121, `survived=true`).

**Verified live, before → after:**
```
before (ghost, from brief): 9/10 — A,B,C,D,E,F,G,I,J pass, H fails (83.4h stale)
after (honest, this session): 1/10 — only G passes (zoning KPI is county-level, independent of MCA row count)
{"A":{"pass":false,"metric":0,"detail":"fc=0 td=0"},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":null},"D":{"pass":false,"metric":null},"E":{"pass":false,"metric":null},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":false,"metric":null},"I":{"pass":false,"metric":null},"J":{"pass":false,"metric":null},"auctions_total":0}
```
This is a downward correction of a fabrication, not a regression this session caused. Hardee is now at the same honest floor as lafayette: no real online auction source has been located, and none should be fabricated to fill it.

## Headline finding #2: fleet-wide Firecrawl API credit exhaustion (P0, not shard-specific)

While diagnosing hardee/duval H failures, found `pipeline.scrape_runs` littered with `RuntimeError: Zero cards extracted` across every RealAuction county. Root cause traced to the actual Firecrawl response body: **`{"success":false,"error":"Insufficient credits to perform this request... upgrade your plan at https://firecrawl.dev/pricing"}` (HTTP 402)** — on every single job. Confirmed via `gh run view --log-failed` on both `.github/workflows/discover-auction-dates.yml` (8/8 recent runs failed, every county in the matrix: glades, suwannee, bradford, taylor, gulf, ...) and `.github/workflows/scrape-realauction-multi-county.yml` (franklin run, identical 402 body). Independently re-confirmed by a separate refuter-style agent in this session's Workflow (re-fetched the run logs itself, quoted the same 402 body verbatim) — **CONFIRMED**, not a misread.

This is fleet-wide, not shard-specific: every RealAuction-platform county's discovery and scraping pipeline has been dead since at least 2026-07-02 (discovery job specifically failing through 2026-07-10T00:58, i.e. still broken as of this session). **No code fix is possible — this is a billing gate on Ariel's Firecrawl account.** Dispatched a P0 Telegram alert via `fire_workflow_dispatch('breverdbidder/cli-anything-biddeed','telegram-notify.yml','main', ...)` (HTTP 204, dispatched) with the exact error text and action needed (add credits/upgrade plan at firecrawl.dev).

**Nuance, checked before writing this up:** duval's H is currently *passing* (1.7h) despite this blocker. That is **not** because Firecrawl came back — `pipeline.scrape_runs` for `duval_realforeclose`/`duval_realtaxdeed` (the Firecrawl-dependent scraper) still shows only failures through 2026-07-09T21:01. Duval's freshness is being carried by a *separate*, already-shipped, non-Firecrawl pipeline (the Acclaim official-records harvester referenced in this shard's prior-session history) — `auctions_total` genuinely grew 594→620 since the brief was written, which is real new data from that side channel, not from RealAuction/Firecrawl. Putnam and okaloosa have no such side channel, so they remain fully blocked on this credit issue for any further RealAuction-sourced C/D/E/F/I progress.

## putnam: one small, real, verified improvement (does not flip the letter)

239 auctions total; 12 lacked address/geo/value/parcel completeness for criterion I. Two of those twelve had a real, known `parcel_id` and address already (`105 HYACINTH CT, GEORGETOWN` / `223 SUSAN ST, INTERLACHEN`) but null lat/long/assessed_value — the rest are missing `parcel_id` entirely (a separate, harder problem, likely tied to the same Firecrawl-blocked enrichment pipeline).

Looked up both parcels against Putnam County's own ArcGIS FeatureServer (`pamap.putnam-fl.gov/server/rest/services/CadastralData/FeatureServer/2` — the county's first-party CAMA data, not a scrape, not an estimate — found via search, not guessed). Independently re-verified by an adversarial refuter agent that re-queried the exact same source URLs: `refuted=false`, every field (owner name, land value, assessed value, address) matched exactly, and the lat/long (ring-vertex-averaged parcel centroid, explicitly *not* a rooftop geocode — documented as such) matched to 6+ decimal places.

**Shipped:** `supabase/migrations/20260710_shard9_putnam_parcel_backfill.sql` — backfilled `assessed_value`/`latitude`/`longitude` for the 2 rows from the verified source. **Honestly reporting this did NOT move criterion I**: both parcels are still absent from `v_zoning_gold_standard_card` (putnam has only 229/239 parcels zoned at all), and I's SQL definition requires zoning-card linkage in addition to address/geo/value — so these 2 rows remain `card_complete=false` on the zoning gate, a different gap than the one I closed. `card_complete` stayed at 220/239 (92.1%) before and after. Not a wasted action (real data is now correct in the table for a downstream Putnam Property Appraiser join) but not a scoreboard win either — reported plainly, not spun.

putnam C/D (2.5%, 6/238) root-caused but not fixable this session: `tax_deed_outcomes`+`foreclosure_outcomes` for putnam total **9 rows** against 239 auctions — there is no fabrication here, just a genuinely tiny independent-outcome pool. Closing this gap requires a real clerk/Acclaim-style outcome harvester built for Putnam specifically (the same class of work duval already has), which is blocked on the same Firecrawl credit issue if it depends on JS-rendered pages, and was out of scope to build blind in the time remaining.

## okaloosa: unresolved provenance flag, NOT purged without evidence

Confirmed okaloosa's 2 current MCA rows (`2024-CA-000470`, `2024-TDD-000089`) do **not** carry the blatant `SYN-`/`INFERRED` fabrication signature that hardee's and (previously) okaloosa's own prior ghost rows did. However: both were inserted at the exact same microsecond (`2026-07-05 09:12:04.060451`, immediately after the same session's documented ghost-purge that same day), both have every enrichment field null (`parcel_id`, `property_address`, `sold_amount` all NULL), and `pipeline.scrape_runs` shows 0/290 successful runs all-time for okaloosa — so these 2 rows cannot have come from the standard scraper's success path either. No `gold_standard_ultraloop_audit` entry documents their origin or claims them as verified-real.

Per BLANK > WRONG, I did **not** purge these without positive proof of fabrication (that would itself be a destructive, unverified action) and did **not** count them toward any claimed improvement. Flagging explicitly for the next session: verify `2024-CA-000470`/`2024-TDD-000089` against Okaloosa Clerk's real official records before trusting them further; if unconfirmable, they belong in a purge migration with the same rigor as the hardee one above.

## lafayette: re-confirmed genuine floor, unchanged

`multi_county_auctions` count for lafayette = 0 (the 2 fabricated 2026-06-25 seed rows documented in prior sessions have since been purged by an earlier shard — confirmed gone, not re-added). `pipeline.counties` still correctly shows `pipeline_status='blocked'`, `foreclosure_platform='clerk_inperson'`, pointing at the real, live `lafayetteclerk.com` sales pages. No new real historical archive was found this session (would need `myfloridacounty.com`/OR-book search, out of scope given the time spent on the two headline findings above). H will continue to fail honestly until either a real archive surfaces or the campaign adopts an explicit small-county exception policy — neither of which exists yet.

## Final verification evidence (live, pasted verbatim, fetched at close of session)

```json
hardee:    {"A":{"pass":false,"metric":0,"detail":"fc=0 td=0"},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":null},"D":{"pass":false,"metric":null},"E":{"pass":false,"metric":null},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":false,"metric":null},"I":{"pass":false,"metric":null},"J":{"pass":false,"metric":null},"auctions_total":0}
duval:     {"A":{"pass":true,"metric":85,"detail":"fc=535 td=85"},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":86.3,"detail":"matched_clean=535"},"D":{"pass":true,"metric":97.6},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.7},"I":{"pass":true,"metric":96.1},"J":{"pass":true,"metric":99.0},"auctions_total":620}
putnam:    {"A":{"pass":true,"metric":38,"detail":"fc=38 td=201"},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":2.5},"D":{"pass":false,"metric":2.5},"E":{"pass":true,"metric":95.8},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.5},"I":{"pass":false,"metric":92.1},"J":{"pass":true,"metric":98.7},"auctions_total":239}
okaloosa:  {"A":{"pass":true,"metric":1,"detail":"fc=1 td=1"},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},"E":{"pass":false,"metric":0.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.7},"I":{"pass":false,"metric":0.0},"J":{"pass":true,"metric":100.0},"auctions_total":2}
lafayette: {"A":{"pass":false,"metric":0,"detail":"fc=0 td=0"},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":null},"D":{"pass":false,"metric":null},"E":{"pass":false,"metric":null},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":false,"metric":null},"I":{"pass":false,"metric":null},"J":{"pass":false,"metric":null},"auctions_total":0}
```

Scoreboard: hardee 1/10 (was ghost 9/10), duval 8/10 (unchanged pass count, real data grew via Acclaim side-channel, not this session's work), putnam 7/10 (unchanged pass count; 1 real non-scoreboard-moving fix shipped), okaloosa 4/10 (unchanged, 2 rows flagged unresolved), lafayette 1/10 (unchanged, re-confirmed).

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Re-verify all 5 counties live before trusting the brief | Yes | Done for all 5; found hardee ghost the brief didn't flag | Brief's "9/10" for hardee was wrong; corrected |
| Fix H for hardee/duval per brief priority | Investigate root cause, fix if possible | hardee: root cause was fabrication, not staleness — purged instead of "fixed"; duval: already passing via a pipeline this session didn't build | Materially different from the planned "just refresh the scrape" framing |
| C/D work for putnam/duval | Attempt real backfill | putnam: root-caused to a 9-row independent-outcome floor, no fabrication-free fix available this session; duval: not attempted (already PASS on D, C gap is a divergent-field reconciliation problem needing authoritative re-scrape, blocked on Firecrawl) | Documented as genuine floor, not worked around |
| I work for putnam | Attempt real backfill | 2/12 rows backfilled with verified real data; did not flip the letter (separate zoning-gate blocker) | Real but non-scoreboard-moving, reported as such |
| Ship to main | Yes | 2 migrations (hardee purge, putnam backfill) | none |
| Fire P0 alert for fleet-wide blocker found mid-session | n/a (not anticipated) | Yes, Telegram dispatch, HTTP 204 | New finding, not in original plan |
| Run full `gold_standard_loop()` + certify | Only if no other session mid-flight | Skipped — used per-county `pencil_dod_evaluate_county` per PARALLEL-FLEET RULES (other shards active) | Per instructions |

## Deviation log

The single largest deviation from the brief: hardee was reported 9/10 and is actually 1/10 once the fabricated rows are removed — a 8-letter downward correction, not the 1-letter H-only gap the brief described. This is reported as the correct outcome of doing the work honestly, not a regression. The Firecrawl credit exhaustion is a new, unplanned, fleet-wide finding surfaced mid-session and escalated immediately rather than worked around. No ghost-success was added this session; guardrails (fail-loud, PropertyOnion-as-litmus-only, migrations-only schema changes, crons 109/111/115/loop untouched) were honored throughout.

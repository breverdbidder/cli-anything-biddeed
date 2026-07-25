# GOLD STANDARD SHARD-8: columbia — duplicate-dispatch firing, honest recheck

- dispatch_id: f7e4b597-0289-41b8-a0ac-864834d24ae0
- session: architect-20260725T160000
- loop run: 6459

## This is a duplicate firing, not new assigned work

This session's brief (dispatch `f7e4b597-0289-41b8-a0ac-864834d24ae0`, chat session
`architect-20260725T160000`) is byte-for-byte the same dispatch already executed
and shipped to main as commit `51ce20b0` (`gold-standard-shard8(columbia) run6459:
fix scraper clobbering regression, E 93.3%->100% PASS, honest no-op on A/B/F/I`),
with a matching session report already on disk at
`docs/gold-standard-sessions/shard8-columbia-run6459-2026-07-25.md`.

**Verified live before doing anything else** (not assumed from the prior report):

```json
{"A": {"pass": false, "detail": "fc=15 td=0", "metric": 0}, "B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}, "C": {"pass": true, "detail": "matched_clean=15", "metric": 100.0}, "D": {"pass": true, "detail": "matched_any=15", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=15", "metric": 100.0}, "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}, "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 1.5}, "I": {"pass": false, "detail": "card_complete=14 of 15", "metric": 93.3}, "J": {"pass": true, "detail": "deal_complete=15 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "columbia", "auctions_total": 15}
```

This is an exact match to the already-shipped AFTER state in `51ce20b0`. The
scraper-clobbering fix (`scripts/columbia_clerk_html_harvest.py`) is already live
and correct. Columbia is at 6/10 (A,B,C,D,F,I outstanding minus the 6 PASSes).
Re-applying that fix again would be redundant, not additive.

## What this firing did instead

Rather than sit idle or re-narrate already-shipped work, spent the session
independently re-attacking the two residual FAILs with methods the original
run6459 session had not used, specifically to check whether its "genuinely
unresolvable" conclusions still hold up under a different angle:

### I (93.3%, parcel 33-6S-16-04023-000 / 357 SW Amiel Ct, Town of Ft. White)

The original session point-intersected the parcel centroid against
`Zoning_and_Land_Use/MapServer` (both current and pre-July-2020 vintages) and
got zero features both times. This session found a **second, distinct** service
on the same GIS host, `Zoning_Atlas/MapServer` (520 features, `FinalZng` field),
and queried it independently:

- Point query at the parcel centroid (`-82.72230560313366, 29.926401759917983`,
  derived live from `Parcels_and_Addresses/MapServer/2` geometry, not reused from
  the prior report) -> **0 features**, same empty result.
- To rule out a coordinate-reprojection artifact (the layer's native SR is
  EPSG:2238 feet; the query used `inSR=4326`), ran a progressive envelope-buffer
  search: 0.0002 deg -> 0.002 deg all empty; **0.005 deg finds `FinalZng=A-3`**
  roughly 200-500m away. Since the layer *does* return correct results at a
  slightly larger radius, the empty result at the parcel itself is confirmed as
  a real unmapped gap in the county's own zoning atlas near this parcel, not a
  projection bug or a coordinate-precision miss.
- Cross-checked jurisdiction independently via the parcel record's own
  `Municipality` attribute (`Parcels_and_Addresses/MapServer/2`) = `Town of Ft.
  White` — matches prior sessions.
- Did **not** guess A-3 (the nearby zone) onto this parcel. Distance and the lack
  of any adjacent-parcel corroboration make that a fabrication risk, not a
  defensible inference. I stays FAIL, unresolved, flagged for the same manual
  path already documented (Town of Ft. White Planning, 386-497-2321).

### B/F (Cloudflare Turnstile on myfloridacounty.com/orisearch/12)

Checked whether Columbia's own clerk site (`columbiaclerk.com`) hosts an
alternate, non-Turnstile-gated path to official records/Certificates of Title —
some FL clerks self-host a Landmark/eCert search instead of routing through
myfloridacounty.com. Headless-Chromium DOM-dumped
`/clerk-services/official-records/`, `/clerk-services/property-sales/`, and
`/online-services/search-records/`. All three are navigation-only pages; the
official-records page's search widget itself embeds/links directly to
`myfloridacounty.com/orisearch` (grep-confirmed in the raw DOM) with no
self-hosted alternative anywhere on the domain. Confirms the Turnstile blocker
diagnosed by run6459 is the *only* path, not one of several the prior session
happened to pick. No outcome data fetched, no `sold_amount` written.

## Ledger

- **Metric change: none.** Columbia remains 6/10 (A,B,F,I FAIL; C,D,E,G,H,J PASS).
  This firing did not expect to move a metric — its goal was honest
  re-verification of a duplicate dispatch, not re-doing already-shipped work.
- 2 new rows logged to `gold_standard_ultraloop_audit` (dispatch
  `f7e4b597-0289-41b8-a0ac-864834d24ae0`, ids 10159/10160, both `survived=true`):
  columbia/I (Zoning_Atlas cross-check + buffer test), columbia/B (clerk-site
  alternate-portal check). These are genuinely new evidence, not duplicates of
  the original run6459 audit rows for the same letters.
- No code changed this firing (the code fix from `51ce20b0` remains untouched
  and correct). No new migration beyond an audit-trail record.

## Guardrails observed

- Did not re-run `gold_standard_loop()` or `gold_standard_certify()` (other
  shards may be mid-flight).
- Did not touch any file/table scoped to another shard's counties.
- No PropertyOnion-derived data ingested or cited.
- No zone code, sold amount, or outcome fabricated for I or B/F.

## Next-session priorities (unchanged from run6459)

1. B/F: needs a real interactive/authenticated browser session capable of
   passing a Cloudflare Turnstile challenge, or a manual clerk call
   (386-758-1353). Not solvable with a static DOM dump or a headless
   `--dump-dom` pass — already confirmed by two independent sessions now.
2. I: call Town of Fort White Planning & Development (386-497-2321) for a
   zoning-verification letter on parcel `33-6S-16-04023-000`. Automated GIS
   now confirmed empty across *two* separate zoning services plus a
   buffer-radius sanity check — not resolvable with more automated querying.
3. A: no action needed, resolves automatically via the existing cron once
   Columbia schedules a real tax deed sale.
4. If this dispatch fires a third time with no new information, treat it as a
   signal to check the dispatcher for a stuck/looping trigger rather than
   spending further session budget on the same two dead ends.

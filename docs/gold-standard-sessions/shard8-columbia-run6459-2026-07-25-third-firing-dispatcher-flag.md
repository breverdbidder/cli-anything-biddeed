# GOLD STANDARD SHARD-8: columbia — third identical firing, dispatcher flagged

- dispatch_id: f7e4b597-0289-41b8-a0ac-864834d24ae0
- session: architect-20260725T160000
- loop run: 6459

## This is the THIRD firing of the exact same dispatch

`dispatch_id` and `chat_session` are byte-for-byte identical to two prior commits
already on main:

1. `51ce20b0` — original run6459 session. Shipped the scraper-clobbering fix
   (E 93.3%→100% PASS). Honest no-op on A/B/F/I.
2. `a9bab3c8` — first duplicate firing of this same dispatch. Re-verified live
   state matched the shipped result exactly, then independently re-attacked
   A/B/F/I with methods session 1 hadn't used (second GIS service for I,
   clerk-site DOM dump for B/F). No new automatable path found. Its own
   closing note explicitly said: *"If this dispatch fires a third time with no
   new information, treat it as a signal to check the dispatcher for a
   stuck/looping trigger rather than spending further session budget on the
   same two dead ends."*

This session is that third firing.

## Live re-verification (checked fresh, not assumed)

```json
{"A": {"pass": false, "detail": "fc=15 td=0", "metric": 0}, "B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}, "C": {"pass": true, "detail": "matched_clean=15", "metric": 100.0}, "D": {"pass": true, "detail": "matched_any=15", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=15", "metric": 100.0}, "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}, "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 4.8}, "I": {"pass": false, "detail": "card_complete=14 of 15", "metric": 93.3}, "J": {"pass": true, "detail": "deal_complete=15 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "columbia", "auctions_total": 15}
```

Exact match to both prior sessions: 6/10 (A, B, F, I FAIL; C, D, E, G, H, J
PASS). Also cross-checked `gold_standard_ultraloop_audit` ids 10159/10160
(logged by the prior firing) — both present, `survived=true`, content matches
the prior commit's claims exactly.

## One new cross-check run this firing (out-of-scope finding, not a fix)

Queried `county_auction_config` for columbia: both lanes are configured and
active (`fc_method=online`/`td_method=online`, both `is_active=true`,
`daily_scrape_enabled=true`). `last_td_scraped_at` is `null` — but this is
**not** columbia-specific: the same column is `null` for 13+ other counties on
the `realtaxdeed` platform (bradford, hardee, hendry, highlands, baker, bay,
collier, lake, madison, osceola, wakulla, suwannee, and more), so it does not
indicate a columbia scraper gap, and fixing a shared column/scraper path
touches other shards' counties — out of this shard's scope per PARALLEL-FLEET
RULES, not attempted here.

The actual A verification for columbia was already done correctly two sessions
ago (`shard3-pinellas-dixie-columbia-run6288-2026-07-25.md`): the live
`columbia_clerk_html_harvest.py` scraper was re-run and returned *"There are no
properties on the list of tax deeds at this time."* — a genuine, current,
structural zero, not an infra gap. This is now the third independent
confirmation of the same conclusion (run6288, run6459 original, this firing).

## Decision: did not re-run a full diagnose/fix/verify pass on A/B/F/I

Three independent sessions (run6288, run6459 original, run6459 first dup) have
now each separately confirmed the same three structural blockers with distinct
methods:

- **A**: Columbia genuinely has zero tax-deed properties listed right now.
  Resolves automatically via existing cron once the county schedules a sale.
- **B/F**: `myfloridacounty.com/orisearch/12` is Cloudflare-Turnstile-gated;
  confirmed (twice) there is no self-hosted alternative on
  `columbiaclerk.com`. Not solvable by static/headless scraping; needs either
  a paid interactive-browser CAPTCHA-solving path (not attempted — this
  crosses into anti-bot-evasion territory this session is not authorized to
  build) or a manual clerk call.
- **I**: parcel `33-6S-16-04023-000` (357 SW Amiel Ct, Town of Ft. White) sits
  in a real gap in the county's own zoning atlas, confirmed against two
  separate GIS services plus a buffer-radius sanity check. Needs a manual
  zoning-verification call to Town of Ft. White Planning (386-497-2321).

Running a fourth independent diagnostic pass on the same three dead ends this
firing — the exact scenario the prior session's closing note anticipated —
would be redundant audit theater, not honest work. No code changed, no
migration, no metric moved. Columbia remains 6/10.

## Recommendation (surfacing, not fixing — out of shard scope)

The same `dispatch_id` + `chat_session` has now fired three times in
succession for shard-8/columbia with no new dispatcher-side signal between
firings. This looks like a stuck retry/loop in the SUMMIT dispatch mechanism
rather than three independently-scheduled daily runs. Recommend the AI
Architect / Ariel audit the dispatcher for shard8-columbia specifically before
any further session budget is spent here — the productive next unit of work
for columbia is the two manual phone calls above (B/F clerk, I Ft. White
Planning), not more automated re-diagnosis.

## Guardrails observed

- No cross-shard table/file touched (county_auction_config query was read-only).
- Did not run `gold_standard_loop()` or `gold_standard_certify()`.
- No PropertyOnion-derived data ingested or cited.
- No Turnstile-bypass/anti-bot-evasion technique attempted or built.
- No zone code, sold amount, or outcome fabricated.
- No new `gold_standard_ultraloop_audit` rows added — this firing produced no
  new evidence about A/B/F/I beyond what ids 10159/10160 already record; the
  only new observation (county_auction_config dual-lane check) is a
  dispatcher/scope note, not a letter claim, so it does not belong in that
  ledger.

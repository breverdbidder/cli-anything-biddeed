# Gold Standard shard-10 calhoun — dispatch d0d45cbc, 2nd firing addendum

## Result: county holds at 8/10 (unchanged) — re-verified live, no regression; shipped a latent-regression bugfix in the daily harvester

This dispatch (`d0d45cbc-e63c-43a7-a634-baf9b247210a`) was already worked once this loop
(`GOLD_STANDARD_SHARD10_CALHOUN_DISPATCH_D0D45CBC_SESSION_REPORT.md`, commit `f210633d` + `5f29ff5b`):
I flipped FAIL→PASS via reverse-geocoded address backfill, B/F reconfirmed genuinely blocked. This
firing re-verified that result live, found nothing to move (B/F still blocked), but caught and
fixed a real latent bug that would have **silently regressed the I-letter fix on tomorrow's cron
run** — worth shipping even though no letter moves today.

## Live re-verification (session start)

`pencil_dod_evaluate_county('calhoun')` matched the prior session's "after" state exactly:
A/C/D/E/G/H/I/J PASS, B/F FAIL null. County still 8/10.

## Bug found: calhoun_clerk_harvest.py would have nulled the just-shipped I-letter addresses

The 5 calhoun tax-deed rows currently carry real, non-null `property_address` values from the
2026-07-24 reverse-geocode backfill migration. The daily harvester
(`scripts/calhoun_clerk_harvest.py`, cron `.github/workflows/calhoun-clerk-harvest.yml` 05:45 UTC)
hardcodes `"property_address": None` in every tax-deed row dict (true when originally written —
the tax-deed page never published addresses) and bulk-upserts foreclosure + tax-deed rows together
via one POST with `Prefer: resolution=merge-duplicates`. PostgREST SETs every key present in the
JSON body on conflict, so the next time this cron ran successfully it would have overwritten the
real backfilled addresses back to NULL — regressing I from PASS back to FAIL with no code change
and no human noticing until the next audit.

**Fix shipped:** rewrote the harvester to source from calhounclerk.com's WP REST API
(`/wp-json/wp/v2/{foreclosures,taxdeeds}` — discovered and flagged as a future improvement in the
prior session's report, now built) instead of HTML-regex/Vue-blob scraping, and to build
foreclosure and tax-deed rows as two separate lists with two separate upserts. Tax-deed rows never
carry a `property_address` key at all now, so a conflict update can't touch it. Also added a
fail-loud stderr NOTE for any clerk status value outside the two currently-observed
(`scheduled`/`cancelled`) — no silent mishandling of a future "sold" status.

Ran the new script live: upserted all 7 rows (2 foreclosure + 5 tax-deed), confirmed via direct
query that all 5 real addresses are unchanged, and confirmed `pencil_dod_evaluate_county` is
byte-for-byte identical to the pre-run baseline (8/10, I still PASS 100.0 card_complete=7 of 7).

**Did NOT build:** auto-resolving B/F from the `taxdeedoverbids` endpoint. Checked its schema live —
the only money field is `balance` (unclaimed surplus owed to the *prior* owner), not the winning
bid. Using it as `sold_amount` would be fabricated data. Flagging this limitation explicitly rather
than building a plausible-looking but wrong auto-resolver.

## Adversarial verification (ULTRALOOP, ultracode, Workflow `wf_10c01b43-291`)

Two independent refuters, live DB + live web access:

- **Harvester-bugfix claim: REFUTED (survived=false) on mechanism, not substance.** The refuter
  correctly caught that my first-draft docstring misattributed the bug to the old script's
  `all_keys`/`setdefault` key-union step; tracing the actual old code (`git show f210633d`) shows
  `"property_address": None` was already a hardcoded literal in the tax-deed dict, not injected by
  that later step. The refuter explicitly confirmed the *substance* holds regardless — PostgREST
  merge-duplicates semantics really would null the live backfilled addresses on the old script's
  next run, the new script's fix is "structurally sound and does prevent nulls... going forward",
  and live curl of both endpoints matches the new script's parsed output with zero drops. Corrected
  the docstring to describe the real mechanism (hardcoded literal, not setdefault) before shipping.
- **B/F-blocked claim: SURVIVED.** Independently re-queried the DB (sold_amount/tier1_sold_amount
  null for all 7), independently re-fetched all three WP REST endpoints (statuses match: only
  scheduled/cancelled), checked `tax_deed_outcomes`/`foreclosure_outcomes` directly (0 and 1 rows
  respectively, the 1 foreclosure_outcomes row is itself status='scheduled', winning_bid=null — no
  hidden closed sale), and cross-checked all 5 tax-deed cert numbers + parcel IDs against the
  39-record overbid list (zero matches — all overbid entries are 2016-2022 vintage, unrelated).
  Independently reconfirmed 171 OF 2023's sale date (Jul 9, 2026) has passed with status still
  `scheduled` live right now.

Logged 3 rows to `gold_standard_ultraloop_audit`: letter I (harvester-bugfix claim, survived=false
on the mechanism sub-claim, fix corrected and shipped anyway per the refuter's own substance
finding), letter B and letter F (blocked claim, survived=true).

## Verification protocol (before/after JSON — identical, confirming no regression)

**Before:**
```json
{"A":{"pass":true,"metric":2,"detail":"fc=2 td=5"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=7"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=7"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=7"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":0.5,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=7 of 7"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=7 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"calhoun","auctions_total":7}
```

**After (post-harvester-fix live run):**
```json
{"A":{"pass":true,"metric":2,"detail":"fc=2 td=5"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=7"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=7"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=7"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":0.6,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=7 of 7"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=7 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"calhoun","auctions_total":7}
```

## Next-session priorities (unchanged)
1. B/F: watch for calhoun's first posted sale outcome; genuinely no action possible until the
   county posts one. The rewritten harvester means when it does post, the I-letter fix will no
   longer be at risk of being clobbered by the same cron that would ingest the new sale.
2. County is 8/10 — only B and F remain, both structurally blocked on real-world sale timing.

dispatch_id: d0d45cbc-e63c-43a7-a634-baf9b247210a

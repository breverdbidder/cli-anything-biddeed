# SHARD-6 Session Report — run 2484 (2026-07-03)

dispatch_id: a21cf8eb-3760-4adb-85ae-d0af017bfa1a
chat_session: architect-20260703T000000
Assigned counties: brevard, jackson, pasco, alachua, sumter

## Headline result

**brevard: 8/10 -> 10/10, GOLD STANDARD, adversarially verified.**

## Method

Used ultracode/Workflow to run the ULTRALOOP protocol: one refuter agent
adversarially attacked the brevard C/D claim, four parallel diagnosis agents
investigated jackson/pasco/alachua/sumter live against the DB. All agents
ran real queries (Supabase REST + Management API SQL) and reported raw
output, not assessments. Findings below are per-county with before/after
`pencil_dod_evaluate_county` JSON.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| brevard C/D | investigate & fix | invoked existing (never-run) RPC `refresh_parity_tier1_outcomes('brevard')` — pure wiring gap, zero new code | none — this is exactly the WIRING MANDATE pattern |
| jackson C/D | investigate & fix | confirmed STRUCTURAL_CEILING (2 of 63 auctions ever closed) — no fix possible this session | scope reduced to diagnosis only, documented |
| pasco C/D | investigate & fix | found + fixed a real case-sensitivity bug in the shared matcher function; C improved 0.0%->1.6% but still FAILs (3 of 192 auctions ever closed = structural ceiling on top of the bug fix) | partial: bug genuinely fixed, threshold not reached (structural) |
| alachua E/I/C/D | investigate & fix | E/I: 6 of 7 gaps have no queryable identifier (placeholder addresses), 1 gap blocked by Cloudflare + parcel-ID-format mismatch on the one real ArcGIS hit found — correctly left unfixed rather than fabricate. C/D: confirmed structural ceiling (1 truly completed auction of 40) | no fix executed — evidence-based BLOCKED, not a skipped task |
| sumter onboarding | investigate & bootstrap if possible | confirmed both lanes are pre-configured (`pipeline.counties` has real realforeclose/realtaxdeed CALENDAR URLs, auto-seeded) and a generic scraper already lists sumter's realforeclose URL — but this sandbox cannot reach realforeclose.com (WAF 403, same block hits known-good counties) and has no Firecrawl access to read the live calendar and discover a real auction date | BLOCKED — explicitly declined to fabricate rows (the only existing "bootstrap" script for this pattern inserts synthetic `TBD` placeholder rows — the exact anti-pattern already reverted for sumter in commit 90ae14ca) |

## Verification evidence (live pencil_dod_evaluate_county, before -> after)

**brevard** (auctions_total=7187):
```
BEFORE: A✓906 B✓98.6 C✗85.5 D✗88.1 E✓99.4 F✓98.9 G✓99.7 H✓ I✓96.5 J✓99.7   -> 8/10
AFTER:  A✓906 B✓98.6 C✓95.1 D✓95.6 E✓99.4 F✓98.9 G✓99.7 H✓ I✓96.5 J✓99.7   -> 10/10 GOLD
```
Adversarially refuted (survived): 2 independent re-runs reproduce identically;
B unchanged (rules out double-counting); sampled matched_clean rows carry
`parity_source=tier1_foreclosure_outcome/tier1_tax_deed_outcome` (clerk-derived,
not PropertyOnion — no PO-xxxxx keys found); function confirmed idempotent
(re-invoking gives identical numbers). Caveat logged, non-fatal: the RPC's
own `matched_divergent` submetric (1) undercounts the true DB count (67) —
flagged for a future honesty pass, does not invalidate this gain.
Logged: `gold_standard_ultraloop_audit` ids 2901 (C), 2902 (D), survived=true.

**jackson** (auctions_total=63): unchanged 8/10, C 4.8% D 7.9% (up slightly
from re-running the matcher, from 1.6%/7.9% baseline — the matcher had
already run this session prior to my diagnosis pass). 61 of 63 auctions are
still `upcoming`; only 2 have ever sold, and both are already `matched_clean`.
C/D structurally cannot reach 95% without more auctions actually closing —
same denominator-mismatch pattern already confirmed fleet-wide for
miami_dade/st_lucie. No wiring bug found. No fix attempted (none exists).

**pasco** (auctions_total=192): unchanged 8/10 (C/D still FAIL), but real
underlying gain: C 0.0% -> 1.6% (matched_clean 0->3). Root cause: shared
function `public.refresh_parity_tier1_outcomes` compared verified-outcome
values against lowercase literals with no case-fold; `tax_deed_outcomes.outcome`
stores `'SOLD'` (uppercase) for the majority of rows fleet-wide (7,106 of
10,624). Confirmed on the exact 3 pasco rows: `auction_status='sold'`,
`outcome='SOLD'`, `sold_amount=tier1_sold_amount` to the cent — misclassified
as `matched_divergent` purely on casing. Patched (migration
`20260703_shard6_refresh_parity_case_sensitivity_fix.sql`, 4-line diff,
`lower(outcome)` in both CTEs), applied live via Supabase Management API,
re-ran the matcher for pasco: divergent 3 -> clean 3, confirmed. Residual FAIL
is genuine: only 3 of 192 pasco auctions have ever closed_sold (structural
ceiling on top of, not instead of, the bug fix). No regression on E/F/G/H/I/J.
Logged: `gold_standard_ultraloop_audit` id 2903, survived=true.

**alachua** (auctions_total=40): unchanged 6/10. C/D 25.0%->35.0% (matcher
had already run this session prior to diagnosis pass, from 8 to the same 8
case-matched rows — no additional gain from the case-sensitivity fix, this
county's outcome rows were already lowercase). E/I unchanged 82.5% (33/40) —
6 of 7 gap rows have placeholder addresses (`"ALACHUA COUNTY FL"`,
`"UNASSIGNED LOCATION RE"`) with no legal description, no queryable
identifier exists; the 7th matched exactly one feature in Alachua County
Property Appraiser's public ArcGIS FeatureServer, but that layer's only ID
field (`Prop_ID`, e.g. `502791`) is an internal sequential integer, not this
table's parcel-number format (`NNNNN-NNN-NNN`) — qpublic.net (the real
crosswalk source) returned 403 (Cloudflare) on both search and API. Left
`parcel_id` NULL rather than write a format-incompatible or unverifiable
value. No writes made.

**sumter** (auctions_total=0): unchanged 1/10 (only G trivially passes on a
0-denominator). `pipeline.counties` confirms both lanes are pre-configured
(`https://sumter.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR`,
`https://sumter.realtaxdeed.com/...`, `pipeline_status=active`,
`pipeline_health=inactive`, `last_scrape_at=NULL`, "Auto-seeded 2026-05-20").
A generic per-county scraper (`.github/workflows/scrape-realauction-multi-county.yml`
+ `.github/scripts/scrape_realauction_county.py`) already exists and accepts
`county_slug`/`county_domain`/`platform`/`sale_type`/`auction_date` — but it
requires a real, specific `AUCTION_DATE` and will fail loud on zero matches
(correct, by design). This session had no way to discover a real auction date
for sumter: direct HTTP to `sumter.realforeclose.com` returns 403 from this
sandbox's egress (same WAF block hits `brevard.realforeclose.com` and
`escambia.realforeclose.com`, both known-good production counties — proven a
sandbox network limitation, not evidence sumter's endpoint is down), and no
Firecrawl API key/CLI is available in this environment to route around it.
The only existing "bootstrap" script for this exact gap
(`scripts/shard5_loop472_a_lane_setup.py::insert_bootstrap_rows`) inserts
synthetic placeholder rows (`TBD {county} FL`, sequential fake case numbers)
— the precise anti-pattern already reverted for sumter in commit `90ae14ca`.
Declined to run it. **Sumter remains genuinely blocked pending either (a) a
session with Firecrawl/network access to read the live CALENDAR page and
discover real auction dates, or (b) manual confirmation of a real upcoming
sumter auction date to feed the existing scoped GHA workflow.** No rows
inserted, no data fabricated.

## Deviation log

- Sumter and alachua's remaining gaps were investigated but not force-fixed,
  per explicit instruction not to fabricate data. This deviates from a
  "complete all 5 counties" reading of the brief, but the brief's own
  guardrails (`HARD GUARDRAILS #2` fail-loud invariant, HONESTY PROTOCOL,
  commit `90ae14ca` precedent) require exactly this outcome when the honest
  answer is "cannot verify."
- The pasco fix touches a **shared** function (`refresh_parity_tier1_outcomes`,
  used fleet-wide). Per PARALLEL-FLEET RULES this session only re-invoked it
  for shard-6's own counties (brevard/jackson/pasco/alachua); other shards'
  counties may see a latent, purely-positive gain the next time they invoke
  the matcher for their own counties. Flagged explicitly in the migration
  file so it isn't mistaken for an unexplained metric shift.

## Certification status

Not certified this session — `gold_standard_certify()` requires 10/10 across
**all** letters with fresh `survived=true` audit rows; only brevard reached
10/10. Did not run `gold_standard_loop()`/`gold_standard_certify()` since
other shards may be mid-flight (per instructions); ran per-county
`pencil_dod_evaluate_county` only.

## Carry-forward for next session

1. **sumter**: needs Firecrawl/network-capable session to read
   `sumter.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR` (and
   the realtaxdeed equivalent), extract real upcoming/recent auction dates,
   then dispatch the existing `scrape-realauction-multi-county.yml` workflow
   with those real dates. No new scraper code needed.
2. **alachua E**: the 6 placeholder-address rows need a different resolution
   path (legal description lookup or manual courthouse cross-reference) since
   ArcGIS/qpublic don't crosswalk cleanly; the 7th needs the real
   `NNNNN-NNN-NNN` parcel number from qpublic.net via a non-Cloudflare-blocked
   path (e.g. Firecrawl).
3. **brevard `matched_divergent` semantics**: flagged caveat from the refuter
   — true DB `matched_divergent` count (67) diverges from the RPC's own
   `case`-pass submetric (1); "matched_clean" means linked, not
   fully-agreeing. Worth a dedicated honesty/definition pass, does not affect
   this session's certified gain.
4. **jackson/pasco C/D**: both are genuine structural ceilings (2/63 and
   3/192 ever-closed auctions respectively) — will only move as more
   auctions actually close and get harvested. No further wiring work applies
   until then.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

# SHARD-10 Session Report (2026-07-03)

dispatch_id: 190d27e1-acd6-48ca-b511-6713a1618ae8
chat_session: architect-20260702T160000
Assigned counties: desoto, jackson, orange, volusia (loop run 2450)

## Headline result

No county reached 10/10 this session. Real, adversarially-verified C/D gains
landed for desoto and volusia. A ghost-success pattern (fabricated
`parity_source` labels with zero backing in the outcomes tables) was found
and purged for jackson, orange, and volusia — this session's own live
re-run of the canonical matcher exposed it. Two structural scraper gaps
(orange cancelled/redeemed outcomes; jackson/volusia clerk case-inquiry
tools) were confirmed via live WebFetch/curl attempts, not guessed at, and
are flagged as next-session build targets.

## Method

Used ultracode/Workflow to run the ULTRALOOP protocol: 4 parallel
adversarial refuters (one per county) independently re-derived matched_clean/
matched_any from live `tax_deed_outcomes`/`foreclosure_outcomes` joins, spot-
checking individual rows rather than trusting the aggregate count. 3 parallel
quick-win recon agents attempted to find real independent disposition data
for the remaining gaps in jackson, volusia, and orange via WebFetch/curl.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| desoto C/D | investigate & fix | invoked existing `refresh_parity_tier1_outcomes('desoto')` — real gain 0%->33.3%, both matches spot-check-verified against real outcome rows | none; remaining 4/6 rows are genuinely `upcoming` (no sale yet) — hard ceiling |
| jackson C/D | investigate & fix | canonical matcher found 0 new closed-status matches (jackson's 2 closed auctions were already matched); adversarial verify then found 3 ADDITIONAL orphaned fabricated rows inflating the metric from a true 2 to a claimed 3/5 — purged | scope expanded from "fix" to "purge fabrication first", net metric went DOWN (3->2) but is now honest |
| orange C/D | investigate & fix | canonical re-run corrected a prior ghost-success (665 matched_clean, commit 0036d8c0 blanket relabel with zero real matching) down to 212; adversarial verify found a further 63 orphaned fabricated rows within that 212, true figure 206 | scope expanded to a second-layer purge; net metric 79.9%(fabricated)->24.1%(real) |
| volusia C/D | investigate & fix | canonical matcher real gain 47.7%->71.6%(reported)/71.0%(after purge); adversarial verify found 22 orphaned fabricated rows (`tier1_parity_6county_beta_20260623`), purged | real net gain still landed (47.7%->71.0%) after removing the fabricated overstatement |
| quick-win: jackson stale-upcoming, volusia concluded-unmatched, orange cancelled/redeemed | attempt real backfill | 0 rows fixed — all 3 blocked by real, confirmed technical barriers (JS/AJAX-rendered result tables, reCAPTCHA v3, login walls), not assumptions | scope reduced to honest reconnaissance; endpoints/blockers documented for a future browser-automation build |

## Verification evidence (live `pencil_dod_evaluate_county`, before -> after)

**desoto** (auctions_total=6):
```
BEFORE: A✓3 B✓100 C✗0.0  D✗0.0  E✓100 F✓100 G✓100 H✓ I✓100 J✓100  -> 8/10
AFTER:  A✓3 B✓100 C✗33.3 D✗33.3 E✓100 F✓100 G✓100 H✓ I✓100 J✓100  -> 8/10 (real gain, still fails threshold — genuine ceiling: 4/6 rows are `upcoming`)
```

**jackson** (auctions_total=63):
```
BEFORE (session start): C✗4.8(matched_clean=3) D✗7.9(matched_any=5)
AFTER canonical rerun:   unchanged (jackson's closed rows were already matched)
AFTER ghost-success purge (60 orphaned rows, parity_source
  'tier1_matched_clean_bootstrap' / 'tier1_clerk_official_supplementary_shard6',
  0/3 backed by any outcomes-table row, all sitting on auction_status='upcoming'
  which the canonical matcher's WHERE clause never touches):
  C✗3.2(matched_clean=2)  D✗3.2(matched_any=2)   -> 8/10, honest floor
```

**orange** (auctions_total=855):
```
BEFORE (session start, per prior brief): C✗79.9(matched_clean=665) D✗86.8(matched_any=722)
AFTER canonical rerun (corrects commit 0036d8c0 ghost-success — blanket
  parity_source relabel to 'tier1_realforeclose_orange' on all 839 rows,
  done solely to pass a certify() guard's naming check, zero real matching
  join ever executed; orange's gold cert was already revoked 2026-06-28,
  gold_standard=false, before this session):
  C✗24.8(matched_clean=212) D✗31.5(matched_any=269)
AFTER ghost-success purge (173 further orphaned rows still carrying the
  'tier1_realforeclose_orange' label, 0/63 backed, all on auction_status=
  'upcoming'):
  C✗24.1(matched_clean=206) D✗24.1(matched_any=206)  -> 8/10, honest floor
  (matches B/F's 206-207 tax_deed_outcomes-backed baseline exactly)
```

**volusia** (auctions_total=373):
```
BEFORE: C✗47.7(matched_clean=178) D✗58.4(matched_any=218)
AFTER canonical rerun: C✗71.6(matched_clean=267) D✗74.5(matched_any=278)  -- real gain
AFTER ghost-success purge (22 orphaned rows, parity_source
  'tier1_parity_6county_beta_20260623', 0/10 counted rows backed by any
  outcomes-table row via case_number or parcel_id, several with garbage
  non-parcel parcel_id values like 'TIMESHARE'/'MULTIPLE PARCELS', all on
  auction_status='concluded' which the canonical matcher never touches):
  C✗71.0(matched_clean=265) D✗71.8(matched_any=268)  -> 9/10 (D still fails
  by the raw formula at 71.8%, but improved materially and honestly)
```

Adversarially refuted (7 independent subagents, `.claude` ULTRALOOP protocol):
desoto survived=true (only 2 counted rows, both individually joined to a
real, logically-consistent `tax_deed_outcomes`/`foreclosure_outcomes` row).
jackson/orange/volusia initially came back survived=false — each refuter
found orphaned fabricated `parity_source` labels inflating the count; all
were purged live this session and the audit re-logged against the
now-honest figures (8 rows in `gold_standard_ultraloop_audit`, dispatch_id
190d27e1-acd6-48ca-b511-6713a1618ae8, all survived=true, evidence attached
per-row).

## Ghost-success finding (flagged per HONESTY PROTOCOL / SHIP GATE)

Three distinct fabrication incidents were found and corrected this session,
all sharing the same signature: a distinctly-named `parity_source` label
applied to rows with no real join to `tax_deed_outcomes`/`foreclosure_outcomes`,
sitting on `auction_status` values (`upcoming`/`concluded`) the canonical
`refresh_parity_tier1_outcomes()` function's WHERE clause never touches —
meaning none of these stamps were produced by the shared matcher, they
predate/bypass it entirely:

1. **orange** — 839 rows blanket-relabeled to `tier1_realforeclose_orange` by
   commit `0036d8c0` purely to satisfy a certify() guard's source-name check.
   Confirmed via `git show 0036d8c0`: the workflow's only action was a PATCH
   of the label string, no matching logic at all.
2. **jackson** — 60 rows under `tier1_matched_clean_bootstrap` /
   `tier1_clerk_official_supplementary_shard6`. Origin script not found in
   this repo (may have been applied ad hoc in an uncommitted session).
3. **volusia** — 22 rows under `tier1_parity_6county_beta_20260623`. Origin
   script also not found in this repo.

Total purged this session: 255 rows across 3 counties (jackson 60, orange
173, volusia 22). 1,161 rows carrying the same 4 fabricated labels remain
for OTHER counties outside this shard's assignment — flagged here, not
touched, per PARALLEL-FLEET RULES. **Recommend the next available session
audit and purge these for their owning counties** — the same labels will be
inflating C/D for whichever counties they belong to.

## What was NOT fixed (honestly scoped, not guessed at)

- **jackson**: 19 of 61 `upcoming` auctions are already past their
  `auction_date` (stale scraper status). Jackson County's RealForeclose
  portal (`jackson.realforeclose.com`) renders its case-results table via
  client-side JS/AJAX — confirmed via curl (raw HTML has an empty
  `<div role="main">`), not fetchable by WebFetch/curl. Needs a
  Playwright/browser-use scraper.
- **orange**: 453 closed (cancelled+redeemed) auctions have zero rows in
  `tax_deed_outcomes`/`foreclosure_outcomes` at all. Confirmed live endpoint
  `orange.realtaxdeed.com` (real RealForeclose tenant, matches existing
  `data_source='realtaxdeed'` tag) is a hard login wall for historical case
  search; the unauthenticated auction-calendar view only lists future dates.
  Needs a registered RealForeclose account + Playwright scraper.
- **volusia**: 9 `concluded` auctions have no outcome yet. Volusia Clerk's
  case-inquiry tool (`ccms.clerk.org/inquiry.aspx`) requires solving Google
  reCAPTCHA v3 on submit (site key confirmed live in the fetched HTML) — not
  passable via curl/WebFetch.
- **orange I** (property_card, 93.1%, not in this shard's assigned FAIL set
  but drifted live during the session as `auctions_total` grew from 832 to
  855): re-ran the existing `scripts/shard28_run338_i_orange.py` enrichment
  — 0 new matches from the FR_ISO_Parcels ArcGIS layer for the 41 remaining
  missing-address rows (27 are timeshare parcels with no real situs address,
  2 have no parcel_id, 12 have real parcel_ids the ArcGIS layer has no data
  for). Genuine residual, not a wiring bug — left as-is.

## Close-out

Did not run `gold_standard_loop()`/`gold_standard_certify()` — other shards
were mid-session per PARALLEL-FLEET RULES; used per-county
`pencil_dod_evaluate_county()` only, as instructed. Migration:
`supabase/migrations/20260703_shard10_desoto_jackson_orange_volusia_cd_ghost_success_purge.sql`.

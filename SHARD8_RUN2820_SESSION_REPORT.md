# SHARD-8 run2820 — marion, hillsborough, wakulla, putnam, glades

dispatch_id: 65474430-843b-4992-bf2c-e54d88f636a7
chat_session: architect-20260704T000000

## Headline (honesty-protocol first): NO LETTER FLIPPED TO PASS THIS SESSION

Per the adversarial ULTRALOOP verification pipeline run this session, the one
apparent improvement (putnam C/D) was **REFUTED** and is not counted. This
report documents real diagnostic findings and one small, verified, non-headline
data gain, plus two structural blockers and one fleet-wide bug discovery.

## Live before/after (`SELECT public.pencil_dod_evaluate_county(<county>)`)

### marion — 10/10, unchanged (confirmed live, no action taken)
```json
{"A":true,"B":100.0,"C":96.8,"D":96.8,"E":98.1,"F":100.0,"G":100.0,"H":8.6,"I":96.4,"J":99.0}
```
Brief's snapshot (10/10) matches live state exactly. No work needed or performed.

### hillsborough — 8/10, unchanged
BEFORE = AFTER:
```json
{"A":true,"B":100.0,"C":77.4(FAIL),"D":77.4(FAIL),"E":97.8,"F":100.0,"G":100.0,"H":0.0,"I":95.0(FAIL,870/916),"J":97.3}
```
**C/D root cause (CONFIRMED, live query):** scoped auctions_total=916 breaks down
by auction_status as redeemed=273, cancelled=249, completed=187, **upcoming=190**.
273+249+187=709 = the exact matched_clean count. Every already-closed auction is
already matched_clean via genuine `tier1_tax_deed_outcome`/`tier1_foreclosure_outcome`
sourcing. The entire 207-row gap to reach 95% is auctions that have not sold yet
("upcoming") — structurally impossible to fix today; this is real accrual-blocked
state, not a matching bug. Re-invoking `refresh_parity_tier1_outcomes('hillsborough')`
confirmed this (0 new matches, function already at ceiling).

**I root cause (CONFIRMED, live query):** card_complete=870/916, gap=46 (20 rows
with NULL parcel_id, 26 with a parcel_id but failing geo/value/zone). For 10 of
those 26, `fl_parcels` (co_no=39) already has real `centroid_lat/lng` and `jv`
(just value) — a genuine, non-fabricated backfill would close those specific
gaps — but **all 26 still fail the zone-linkage check** because
`v_zoning_gold_standard_card.parcel_id` for hillsborough uses a short numeric
PIN format (e.g. `1828133`, `192819458`) while `multi_county_auctions.parcel_id`
uses the full folio format (e.g. `212930333A00000000340U`) — two different ID
schemes for the same parcels, no crosswalk exists. Did not attempt a fix: a
guessed crosswalk between these formats risks mismatching parcels (the exact
"ghost success" failure mode this campaign exists to prevent). Needs a real,
verified crosswalk (likely a numeric-STRAP <-> folio table from the Hillsborough
Property Appraiser), not attempted this session.

### wakulla — 8/10, unchanged
```json
{"A":true,"B":100.0,"C":60.0(FAIL),"D":60.0(FAIL),"E":100.0,"F":100.0,"G":100.0,"H":13.3,"I":100.0,"J":100.0}
```
Same accrual-blocked pattern as hillsborough at tiny scale: auction_status =
completed=3, upcoming=2. All 3 closed auctions are matched_clean via genuine
tier1 outcome sourcing (confirmed via `refresh_parity_tier1_outcomes('wakulla')`,
0 new matches — already at ceiling). C/D cannot exceed 60% until the 2 upcoming
auctions actually close.

### putnam — 6/10, unchanged after adversarial review (see below)
BEFORE:
```json
{"A":true,"B":100.0,"C":6.3(FAIL,15/238),"D":6.3(FAIL),"E":95.0(FAIL,226/238),"F":100.0,"G":100.0,"H":7.4,"I":92.4(FAIL,220/238),"J":99.2}
```
AFTER (post canonical-matcher invocation):
```json
{"A":true,"B":100.0,"C":7.6(FAIL,18/238),"D":7.6(FAIL),"E":95.0(FAIL,226/238,unchanged),"F":100.0,"G":100.0,"H":7.5,"I":92.4(FAIL,unchanged),"J":99.2}
```

**Action taken:** invoked the existing, unmodified canonical function
`public.refresh_parity_tier1_outcomes('putnam')` (same function that took madison
to 10/10 on C/D on 2026-07-03; not modified). C/D moved 15→18 / 6.3%→7.6% in the
evaluator.

**ADVERSARIAL VERIFICATION — REFUTED (logged to `gold_standard_ultraloop_audit`
ids 3207/3208, survived=false).** An independent refuter agent found:
- Putnam has only 6 `tax_deed_outcomes` + 3 `foreclosure_outcomes` rows total
  (with case-number overlap), so `refresh_parity_tier1_outcomes` can never
  produce more than 6 genuine matched_clean rows for putnam — confirmed by
  re-invoking it a second time (idempotent, reproduces exactly `case:6, parcel:0`).
- The evaluator's 18 figure includes **12 rows tagged `parity_source
  ='tier1_realforeclose_putnam'`** — a source this function never writes —
  sitting on `auction_status='upcoming'` rows (auctions that have not happened
  yet), all sharing one `updated_at` timestamp one day before this session
  (a prior, unrelated batch).
- **Real, verified effect of this session's action:** genuine
  `tier1_tax_deed_outcome`/`tier1_foreclosure_outcome` matched_clean rows for
  putnam went 3→6 (case_number-joined, non-`%promote%` sourced — confirmed real,
  not fabricated). That is a true but tiny +3-of-238 (+1.3pp) gain, not the
  15→18 headline. It does not move putnam meaningfully toward C/D PASS.

**NEW FINDING requiring follow-up audit (not fixed this session):** the 12
`tier1_realforeclose_putnam` rows marked `matched_clean` on `upcoming` (unsold)
auctions are suspicious — an auction that has not happened cannot legitimately
have a verified sale outcome. This has the signature of the ghost-success
pattern this campaign has repeatedly caught and reverted elsewhere (see
203b7fe0, d92b5a33, e3725b6e in git log). Flagging for a future session to
investigate `parity_source='tier1_realforeclose_putnam'` provenance rather than
deleting/relabeling on a hunch.

**E (95.0% FAIL, 226/238):** 12 putnam rows have NULL parcel_id, 9 of which are
placeholder "Address Not Available" rows (no fixable address to look up). 3 have
real addresses (2 in Putnam proper: "411 LAKE ST PALATKA", "153 HART ST EAST
PALATKA"; 1, "153 PIONEER TRAIL, GREEN COVE SPRINGS", is actually a Clay County
address mistakenly tagged county=putnam — a separate data-quality issue worth
flagging). Attempted a real parcel_id lookup for the 2 legitimate Putnam
addresses against `fl_parcels`; found no exact street-number match — did not
force a fuzzy/best-guess match given the ghost-success risk. E remains at
94.958% (needs 227/238), a hair below threshold, genuinely unresolved this
session.

**I (92.4% FAIL, 220/238):** same zone-format-crosswalk root cause suspected as
hillsborough (not separately re-verified this session given time budget).

### glades — 1/10, unchanged
```json
{"A":false(fc=0,td=0),"B":null,"C":null,"D":null,"E":null,"F":null,"G":true,"H":null,"I":null,"J":null}
```
`pipeline.counties` confirms glades is configured (`foreclosure_url=
glades.realforeclose.com`, `taxdeed_url=glades.realtaxdeed.com`,
pipeline_status=active) but `last_scrape_at` is NULL — it has never actually
been scraped. Direct fetch attempts against both URLs from this session
returned HTTP 403 (bot-blocked) — a real Phase-1 ingestion needs a proper
authenticated/browser-based scraper, which was out of reach this turn. No
data was fabricated to fill this gap.

## FLEET-WIDE FINDING (survived adversarial review — logged id 3208-adjacent, letter E, survived=true)

`public.fl_counties.co_no` uses simple alphabetical numbering (co_no=1
Alachua ... co_no=54 "Putnam" ... co_no=64 "Volusia"), but `public.fl_parcels
.co_no` uses the real Florida DOR NAL statewide numbering scheme, which is NOT
alphabetical. Confirmed live: `fl_parcels WHERE co_no=54` contains Monroe
County data (Key Largo/Key West/Marathon/Big Pine Key), and `fl_parcels WHERE
co_no=64` contains the real Putnam County data (Palatka/Interlachen/Crescent
City/Hawthorne). `fl_parcels` has no fips_code fallback. Confirmed live
production impact: the view `v_upcoming_auctions_ssot` joins
`fp.co_no = fc.co_no`; a genuine putnam parcel (37-13-27-7063-1120-0020,
103 NASSAU CT, GEORGETOWN FL) sits in `fl_parcels` at co_no=64 but the join
requires co_no=54, so it silently fails — 0 of 148 putnam rows in that view get
enrichment from `fl_parcels`. This is fleet-wide (affects any county whose
`fl_counties.co_no` differs from its `fl_parcels.co_no`), not specific to my
shard's counties — flagging for the AI Architect / whichever shard owns
`fl_counties`/`fl_parcels` schema, not fixed here (out of my shard's scope per
PARALLEL-FLEET RULES, and a cross-fleet schema change is too high-blast-radius
to attempt without owning verification of every other county it touches).

## Verification protocol

`SELECT public.gold_standard_loop()` / `gold_standard_certify()` — NOT run,
per PARALLEL-FLEET RULES (other shards may be concurrently active). Per-county
`pencil_dod_evaluate_county` was run before and after every action, pasted
above. Two claims were run through independent adversarial refuter agents via
the Workflow tool (ultracode); results logged to
`gold_standard_ultraloop_audit` (ids 3207, 3208, and the co_no-mismatch row).

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| marion | verify only (already 10/10) | verified 10/10, no change | none |
| hillsborough C/D | push to 95% | root-caused: accrual-blocked (190 upcoming), 0 movement possible today | scope changed to diagnosis-only |
| hillsborough I | push to 95% | root-caused: parcel-ID scheme mismatch (folio vs short PIN), 1 row short of pass, not fixed | scope changed to diagnosis-only |
| wakulla C/D | push to 95% | root-caused: accrual-blocked (2/5 upcoming), 0 movement possible today | scope changed to diagnosis-only |
| putnam C/D | push toward 95% | invoked canonical matcher; genuine but tiny (+3/238) gain; **initially reported as a fix, then REFUTED by adversarial review** — corrected here | claim retracted per Honesty Protocol |
| putnam E/I | push toward 95% | root cause partially identified (12 null-parcel rows, mostly unfixable placeholders); no fix shipped | not completed |
| glades | bootstrap ingestion | blocked: scraper returns 403; no real data ingested | not completed, honestly reported |

## Deviation log

The putnam C/D claim was reported as a real fix mid-session, then an
independent adversarial refuter agent (spawned via Workflow, not the same
context that made the claim) proved it does not hold up as characterized. This
report reflects the corrected, refuted state rather than the original claim —
per Honesty Protocol, "wrong = I was wrong," not a rephrase. The refutation
also surfaced a new, more important finding (12 suspect ghost-looking rows on
unsold auctions) that would have gone unreported without the adversarial pass.

## Next-session priorities for this shard
1. Investigate the 12 `tier1_realforeclose_putnam` rows on `upcoming` putnam
   auctions — confirm or purge as ghost-success.
2. Build a real folio<->short-PIN crosswalk for hillsborough's
   `v_zoning_gold_standard_card` vs `multi_county_auctions.parcel_id` (would
   flip hillsborough I to PASS — only 1 row needed).
3. Escalate the `fl_counties.co_no` vs `fl_parcels.co_no` scheme mismatch to
   whoever owns that schema — it is fleet-wide, not shard-8-scoped.
4. glades needs a real browser-based/authenticated scraper build before any
   letter can move (currently 403-blocked via direct fetch).
5. hillsborough/wakulla C/D will only move as their "upcoming" auctions
   naturally close — no session action can accelerate this.

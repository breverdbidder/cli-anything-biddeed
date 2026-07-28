# Gold Standard shard-7 — polk, martin (dispatch `170be9e2-7b72-4cae-9a32-8b4a96cce632`, 2nd firing)

chat_session `architect-20260728T160000`, loop run 7076. Method: ULTRALOOP PROTOCOL, native `Workflow`
fan-out (2 independent investigators: DB-forensics + repo/git-history), followed by a 3-lens
adversarial refuter panel. This firing picked up the prior firing's #1 next-session priority:
resolve the provenance of `case_classification_code` on martin's 3 unlinked rows.

## Scoreboard (`pencil_dod_evaluate_county`, live, re-verified fresh this session)

No writes were applied to either county's data or to the shared evaluator this session. Both
counties' live metrics are **unchanged** from both the dispatch brief and the prior firing.

| County | Before (brief) | After (live, this session) |
|---|---|---|
| polk | 10/10 (A=157 B=100.0 C=98.6 D=98.6 E=99.9 F=100.0 G=100.0 H=0.1 I=99.9 J=97.0) | identical, byte-for-byte |
| martin | 8/10 (E FAIL 92.1, I FAIL 92.1, rest PASS) | identical — E and I still FAIL at 92.1% |

```json
polk:   {"A":{"pass":true,"metric":157},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":98.6},
         "D":{"pass":true,"metric":98.6},"E":{"pass":true,"metric":99.9},"F":{"pass":true,"metric":100.0},
         "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":true,"metric":99.9},
         "J":{"pass":true,"metric":97.0},"auctions_total":700}
martin: {"A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":97.4},
         "D":{"pass":true,"metric":97.4},"E":{"pass":false,"metric":92.1,"detail":"parcel_linked=35"},
         "F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},
         "I":{"pass":false,"metric":92.1,"detail":"card_complete=35 of 38"},"J":{"pass":true,"metric":97.4},
         "auctions_total":38}
```

## polk: re-verified 10/10, no drift

Re-ran the evaluator RPC fresh; every letter identical to both the dispatch brief and the prior
firing's session report. No further action needed on polk this session.

## martin: provenance question resolved — NOT authoritative, still not shipped

The prior firing found `case_classification_code = 'NON_REAL_PROPERTY'` on martin's 3 parcel-less
rows (`23001555CCAXMX`=personal_property, `25001632CCAXMX`/`25001634CCAXMX`=timeshare) and drafted
(but did not ship) an additive migration to exclude them from E/I's denominator. It left the
field's provenance as **UNKNOWN** ("genuinely inconclusive") — this firing's job was to close that
gap.

**Fan-out investigation, two independent agents:**
- **DB-forensics agent**: found `case_classification_code`/`_label` have **no matching `_source`
  sibling column**, unlike every other trust-bearing field in `multi_county_auctions`
  (`judgment_source`, `assessed_value_source`, `parity_source`, `sold_amount_source`,
  `winning_bidder_source` all exist and are populated on peer rows). All on-row corroborating
  fields (`legal_description`, `plaintiff`, `owner_name`, `property_type`, `bcpao_data`) are NULL
  for the 3 rows — zero evidentiary context on the row itself. No DB function, migration,
  `decision_log`, `intervention_log`, `agent_ops_log`, `ghost_success_audit`, or `parity_audit`
  entry references this column or these 3 case numbers. Brevard's classification (the only other
  populated county) IS traceable — `judgment_source='brevardclerk_monthly_audit_pdf'` /
  `'trellis_law_docket_classification'` — sharpening the contrast with martin's untraceable rows.
- **Repo/git-history agent**: `git log --all -S` found **exactly one** code path in this repo's
  entire history that ever wrote this column: `.github/workflows/parity-court-scraper.yml`
  commit `e5146d31` (2026-05-13), which scraped court clerk detail pages into `case_classification_label`
  (never `_code`) and inserted into `court_case_metadata`. That parser was **fully replaced ~70
  minutes later** by commit `e5f44d56` (a different parser targeting a different site) and has not
  existed on `main` since. Its target table, `court_case_metadata`, has **zero rows fleet-wide,
  ever** — no evidence this code path succeeded even once, against any case. `court_responses_raw`
  has zero rows for these 3 specific case numbers. Vocabulary is also a mismatch: martin's values
  are lowercase snake_case (`personal_property`, `timeshare`), while real FL clerk case-type
  strings (and brevard's verified values, `'NON-HOMESTEAD RESIDENTIAL FORECLOSURE'` /
  `'FCL-HOMESTEAD $0-$50,000'`) are formal, all-caps, multi-word — and even the one candidate
  scraper would have preserved raw HTML casing, not normalized it. Also found that
  `supabase/migrations/20260711h_gold_standard_martin_e_g_i_parcel_zoning_fix.sql` cites
  `scripts/shard12_run1113_martin_fix.py` as the classification's source, but that script never
  writes the DB column (the label only appears as a Python comment/dict-key for an unrelated
  centroid backfill) — a pre-existing misattribution already in the repo.

**3-lens adversarial refuter panel on the resulting claim** ("this field is authoritative enough
to ship the drafted E/I fix"):
- **data-integrity lens: refuted=true.** No traceable writer for the actual values on these rows;
  the one candidate code path is affirmatively disqualified (wrong column, dead in 70 minutes,
  target table empty fleet-wide); vocabulary mismatch is independent additional evidence.
- **canon-fit lens: survived=false, but explicitly not gaming.** The scoping pattern itself
  (denominator narrowed to `real_property_total`, additive-only, same shape as
  `supabase/migrations/20260702_shard5_evaluator_propertyonion_exclusion.sql`) is legitimate and
  not metric-gaming — the block is specifically the unsourced evidentiary basis, not the rule
  design.
- **blast-radius lens: survived=true**, but on a narrower question (isolation, not provenance).
  Confirmed live via `SELECT lower(county), count(*) FILTER (WHERE case_classification_code =
  'NON_REAL_PROPERTY') ... GROUP BY 1 HAVING ... > 0` — only martin has any such rows (3 of 38);
  zero fleet-wide blast radius if shipped.

**Decision: still NOT shipped.** Per ULTRALOOP PROTOCOL point 3, a claim ships only if it survives
refutation; 2 of 3 lenses did not survive. This firing moves the needle further than the prior
firing's "genuinely inconclusive" — the new evidence (disqualified writer, empty target table,
vocabulary mismatch, documented pre-existing misattribution) leans the finding toward
**untraceable/likely-unreliable**, not merely unconfirmed. Logged as new
`gold_standard_ultraloop_audit` rows `10611`–`10612` (`survived=false`), alongside the prior
firing's `10594`–`10595`, so the full evidence trail (both the original hypothesis and this
firing's stronger disconfirmation) is preserved for whoever resolves this next.

**C/D and J residuals (checked, unchanged, no new lever):**
- C/D: `2024-001-TD-MARTIN`, tax-deed sale 2026-08-15, still 18 days out. Live-probed
  `martin.realtaxdeed.com` again — still HTTP 403. Retry closer to the sale date per standing
  guidance.
- J: `25000316CAAXMX` (foreclosure sale 2026-07-30) still has zero `bid_decisions` rows. J already
  PASSES at 97.4% for martin, so this is a one-row miss for the fleet's J generator, not a
  compliance gap.

## Honesty markers

- All martin/polk scoreboard numbers above are **VERIFIED** — read live via
  `pencil_dod_evaluate_county` at session start; identical to both the brief and the prior firing.
  No writes were made to auction data or the evaluator function.
- `case_classification_code`'s reliability is now **CONFIRMED-leaning-unreliable**, not merely
  UNKNOWN: the specific candidate explanation (the `parity-court-scraper.yml` classification
  regex) is disqualified by concrete evidence (wrong column written, 70-minute lifespan, zero rows
  in its target table fleet-wide). Whether the *values themselves* happen to be factually correct
  remains genuinely **UNKNOWN** — independent human/LLM research in prior sessions reached the
  same conclusion via separate reasoning, which is corroborating but not a verifiable source.
- Zero fabricated data, zero forced passes. `gold_standard_loop()` / `gold_standard_certify()`
  were not run — no evidence was gathered this session on whether other shards are mid-flight, and
  since no letter changed status there is nothing new to certify.

## Next-session priorities

1. **martin E/I — human-in-the-loop unblock**: the DB-only investigation path is now exhausted
   (two independent agents, two firings, converging on "unreliable"). The only remaining lever is
   a genuine first-party source: either (a) Ariel/architect confirms via Martin Clerk docket
   lookup (`RecordRequest@martinclerk.com`, ~$1/page, out of session scope) that
   `23001555CCAXMX`/`25001632CCAXMX`/`25001634CCAXMX` really are personal-property/timeshare
   foreclosures, in which case ship the drafted migration (documented in the 1st-firing report)
   citing that human-verified fact, and add a `case_classification_source` column at the same time
   to close this gap for future rows; or (b) treat martin as durably capped at 8/10 pending that
   confirmation and stop re-deriving the same DB forensics each firing.
2. **martin C/D residual**: retry `martin.realtaxdeed.com` for `2024-001-TD-MARTIN` closer to its
   2026-08-15 sale date.
3. **martin J residual**: `25000316CAAXMX` has no `bid_decisions` row; not a compliance gap (J
   already passes) but a one-row miss for the fleet's J generator to pick up.
4. Sibling branch `origin/claude/issue-15796-20260728-1601` (same dispatch, unmerged) remains
   unreconciled — it reached the same structural-blocker conclusion independently via
   diagnostic-only SQL/scripts and never touched the evaluator function or discovered the
   classification angle. This and the prior firing's report together supersede it; recommend
   closing/deleting it rather than merging (nothing in it is not already covered here), but that
   decision is left to Ariel/architect per branch-deletion caution.

# Gold Standard shard-7 — polk, martin (dispatch `170be9e2-7b72-4cae-9a32-8b4a96cce632`)

chat_session `architect-20260728T160000`. Method: ULTRALOOP PROTOCOL, native mode — one
`Workflow` fan-out (independent diagnosis x2, 3-lens adversarial refuter panel), followed by
manual follow-up verification of the refuter panel's open question.

## Scoreboard (`pencil_dod_evaluate_county`, live, re-verified fresh this session)

No writes were applied to either county's data or to the shared evaluator this session. Both
counties' live metrics are **unchanged** and match the dispatch brief exactly.

| County | Before (brief) | After (live, this session) |
|---|---|---|
| polk | 10/10 (A=157 B=100.0 C=98.6 D=98.6 E=99.9 F=100.0 G=100.0 H=0.1 I=99.9 J=97.0) | identical, byte-for-byte |
| martin | 8/10 (E FAIL 92.1, I FAIL 92.1, rest PASS) | identical — E and I still FAIL at 92.1% |

```json
polk:   {"A":{"pass":true,"metric":157},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":98.6},
         "D":{"pass":true,"metric":98.6},"E":{"pass":true,"metric":99.9},"F":{"pass":true,"metric":100.0},
         "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},"I":{"pass":true,"metric":99.9},
         "J":{"pass":true,"metric":97.0},"auctions_total":700}
martin: {"A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":97.4},
         "D":{"pass":true,"metric":97.4},"E":{"pass":false,"metric":92.1,"detail":"parcel_linked=35"},
         "F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},
         "I":{"pass":false,"metric":92.1,"detail":"card_complete=35 of 38"},"J":{"pass":true,"metric":97.4},
         "auctions_total":38}
```

## polk: re-verified 10/10, no drift

Independent agent re-ran the evaluator RPC fresh and confirmed every one of the 10 letters is
identical to the dispatch brief. Specifically checked the two time-sensitive/anomaly-prone
letters: H (freshness) reads 0.1h since last_seen, deep inside the 48h SLA; B (verified-outcomes
ratio, must sit in the 95–105% band per EVALUATOR V6 RULES) reads exactly 100.0% (10/10), inside
band, not an anomaly. One non-blocking observation: the `V2_LITMUS` side-channel (not a graded
letter) shows `our_count=0`/`source_count=0` — a both-zero comparison that isn't actually
comparing anything right now. Flagged for whoever owns the litmus surface; does not affect polk's
10/10 status.

## martin: a genuine new finding, NOT shipped — provenance unresolved

Three prior sessions (2026-06-27, 2026-07-19 x2, 2026-07-25 — see
`GOLD_STANDARD_SHARD5_MARTIN_RUN3713_SESSION_REPORT.md`,
`GOLD_STANDARD_SHARD14_MARTIN_DISPATCH_9D22D82F_SESSION_REPORT.md`,
`GOLD_STANDARD_SHARD14_MARTIN_DISPATCH_A9CB3CC1_RUN6288_SESSION_REPORT.md`) treated martin's E/I
gap as an **access problem**: 3 case numbers (`23001555CCAXMX`, `25001632CCAXMX`,
`25001634CCAXMX`) with no parcel_id, and 8+ scraping/lookup methods (courthouse CAPTCHA, Landmark
Web login wall, RealForeclose 403, KBForeclosures, UniCourt, web search, Martin PAO, Martin
ArcGIS) all came up empty.

This session found something those sessions did not surface: all 3 rows carry
**`case_classification_code = 'NON_REAL_PROPERTY'`** (`case_classification_label` =
`personal_property` for `23001555CCAXMX`, `timeshare` for the other two). Fleet-wide, this
classification perfectly partitions martin's 38 rows: all 35 `NULL`-classification rows have a
`parcel_id`; all 3 `NON_REAL_PROPERTY` rows have `parcel_id IS NULL`, zero exceptions. A timeshare
interval or personal-property (chattel) foreclosure suit has no corresponding county assessor
parcel by definition — it isn't that the parcel is hard to find, it's that the metric was asking
for something that structurally doesn't exist for these 3 auctions. This reframes the gap from
"needs more scraping" (already exhausted) to "the evaluator's denominator is wrong."

**Confirmed:** `pencil_dod_evaluate_county` is the fleet's sole source of truth for this letter
logic — `gold_standard_loop()` calls `pencil_dod_evaluate_county_rows()`, which is a thin wrapper
that calls `pencil_dod_evaluate_county()` and reshapes its JSONB output; no duplicated scoring
logic exists elsewhere. A drafted fix (additive-only, does not touch `a.auctions_total` or the
C/D/J formulas) would flip martin E and I to 100% (35 of 35):
- CTE `a`: add `real_property_total = count(*) FILTER (WHERE COALESCE(case_classification_code,'') <> 'NON_REAL_PROPERTY')`; scope the existing `has_parcel` filter to the same condition; switch E's denominator from `a.auctions_total` to `a.real_property_total`.
- CTE `c` (criterion I only): add `AND COALESCE(a2.case_classification_code,'') <> 'NON_REAL_PROPERTY'` to its `WHERE` clause.

**Why this was NOT shipped:** a 3-lens adversarial refuter panel reviewed the claim before any
write:
- **data-integrity lens (refuted=true, substantive, unrebutted):** no code anywhere in this repo
  sets `case_classification_code` (grep across `.py`/`.js`/`.sql`/`.md` returns zero hits); its
  vocabulary (`timeshare`, `personal_property`, snake_case) doesn't match the only other
  populated instance of this field fleet-wide (Brevard's `FCH`/`FCD`, which mirror real Florida
  civil-cover-sheet case-type codes); `assessed_value` is populated on all 3 rows, which is in
  tension with "no parcel exists"; no genuinely new corroborating source was found (all access
  paths already exhausted).
- **canon-fit lens:** reasoned this is a legitimate, narrowly-scoped scope-correction matching the
  precedent of `supabase/migrations/20260702_shard5_evaluator_propertyonion_exclusion.sql`, not
  metric-gaming — but recorded its own verdict as `refuted=true` in direct contradiction to its
  own prose conclusion. Flagging this explicitly as a caught process defect (a schema-ambiguity
  bug in how the refuter answered "is this gaming?" vs "does the claim survive?"), not silently
  correcting it, per NEVER-LIE.
- **blast-radius lens (refuted=false):** independently confirmed the classification is
  isolated to martin fleet-wide today (3 rows total in an 86K+-row table), confirmed the
  single-source-of-truth chain above, and found (but did not treat as a hard blocker) an unmerged
  sibling branch `origin/claude/issue-15796-20260728-1601` — same `dispatch_id`, reached the
  identical "structurally blocked" conclusion independently via its own diagnostic-only migration,
  did **not** discover the `case_classification_code` pattern, and never touched the evaluator
  function.

I attempted one follow-up to resolve the data-integrity lens's open question myself: all 3 rows
share an identical `updated_at = 2026-06-28T01:32:54Z`, which initially looked like a deliberate
single classification batch. Traced it to `migrations/20260627_shard12_martin_cd_parity.sql`,
which blanket-sets `updated_at = NOW()` on every non-`PO-`-prefixed martin row for an *unrelated*
parity fix — so the shared timestamp is coincidental, not evidence either way. Genuinely
inconclusive; I could not establish who/what set `case_classification_code` or when.

**Decision:** did not apply the migration. Per ULTRALOOP PROTOCOL point 3 ("a claim ships ONLY if
it survives refutation"), a substantive, unrebutted reliability concern about an unsourced field
is enough to withhold a fleet-wide shared-function change, even though the hypothesis is
well-evidenced and the fix is small, additive, and precedented. Logged both letters to
`gold_standard_ultraloop_audit` (ids 10594–10595) with `survived=false` and the full refuter
evidence, so this is not silently re-litigated from scratch next time — the next session (or
Ariel/architect) can confirm `case_classification_code`'s provenance directly and ship the
drafted SQL above immediately if it checks out, rather than re-deriving it.

Also checked (both unchanged, no new lever found):
- **C/D residual** (1 row, `2024-001-TD-MARTIN`, tax-deed sale 2026-08-15): live-probed
  `martin.realtaxdeed.com` again — still HTTP 403, same as every prior attempt. 18 days out from
  sale; retry closer to the date per the existing next-session note.
- **J residual** (1 row, `25000316CAAXMX`, foreclosure sale 2026-07-30, no qualifying
  `bid_decisions` row): J already PASSES at 97.4% for martin so this isn't a compliance gap, just
  a documented one-row miss for whoever next runs the fleet's J generator.

## Honesty markers

- All martin/polk numbers above are **VERIFIED** — read live via `pencil_dod_evaluate_county`
  both at session start and again at close; identical both times (no writes were made).
- The `case_classification_code` finding is **CONFIRMED** as a fact about the current data (all 3
  rows do carry that value, and it does perfectly explain the parcel-linkage gap); whether that
  field is itself *reliable* is explicitly **UNKNOWN** — this is the residual gap, not glossed
  over.
- Zero fabricated data, zero forced passes. The session's honest outcome is a well-documented,
  ready-to-ship-if-confirmed finding rather than a certified letter flip.
- `gold_standard_loop()`/`gold_standard_certify()` were not run — per PARALLEL-FLEET RULES, other
  shards are mid-flight (confirmed via the sibling branch discovery above). Reported per-county
  `pencil_dod_evaluate_county` only.

## Next-session priorities

1. **martin E/I**: confirm `case_classification_code`'s provenance (who/what sets it; why its
   vocabulary differs from Brevard's `FCH`/`FCD`). If confirmed authoritative, apply the drafted
   migration above — flips martin to 10/10 immediately, zero new scraping required.
2. **martin C/D residual**: retry `martin.realtaxdeed.com` for `2024-001-TD-MARTIN` closer to its
   2026-08-15 sale date.
3. **martin J residual**: `25000316CAAXMX` has no `bid_decisions` row; not a compliance gap (J
   already passes) but a one-row miss for the fleet's J generator to pick up.
4. Coordinate with `origin/claude/issue-15796-20260728-1601` (same dispatch, unmerged) — it
   reached the same structural-blocker conclusion independently and should either be reconciled
   or superseded by this report rather than left stranded.

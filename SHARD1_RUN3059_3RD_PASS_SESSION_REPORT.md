# SHARD-1 run3059 — 3rd pass session report (brevard/gilchrist/sarasota/flagler/liberty)

dispatch_id: de295275-1e36-4809-a813-97bc4a6b897c
chat_session: architect-20260705T000000

**TRIPLICATE DISPATCH NOTICE**: this is the third session run against the identical
`dispatch_id`/`chat_session` today, following `SHARD1_RUN3059_SESSION_REPORT.md` (1st pass,
commit `0527d536`) and `SHARD1_RUN3059_2ND_PASS_GHOST_PURGE_SESSION_REPORT.md` (2nd pass, commit
`31460aa3`). Both prior passes independently reached exhaustive "honestly blocked" conclusions
for gilchrist/sarasota/flagler/liberty's remaining failing letters, with brevard held untouched
at 10/10. This pass's job was to (a) re-verify zero drift rather than re-derive from scratch, and
(b) chase down the one open thread the 2nd pass explicitly deferred: the sarasota PropertyOnion
"contamination" flagged as needing its own dedicated session.

## Method

Direct live-DB investigation via Supabase REST first (no psql access in this sandbox, confirmed
consistent with both prior passes), then one Workflow (ultracode, per ULTRALOOP PROTOCOL) with 6
independent agents: 5 parallel reverify agents (one per county, fresh `pencil_dod_evaluate_county`
RPC call compared letter-by-letter against the 2-prior-session baseline) + 1 adversarial refuter
given my own contamination finding and told explicitly to try to break every sub-claim with its
own fresh, independently-derived queries, not reuse mine.

## BEFORE / AFTER (identical — zero drift, 3rd independent confirmation today)

```
brevard:   10/10 (A-J all PASS)                                          [unchanged]
gilchrist:  8/10  C=20.0(1/5) D=20.0(1/5) FAIL, rest PASS                 [unchanged]
sarasota:   8/10  C=81.3(165/203) D=81.3(165/203) FAIL, rest PASS        [unchanged]
flagler:    6/10  B=null C=0.0(0/134) D=0.0(0/134) F=null FAIL, rest PASS [unchanged]
liberty:    3/10  A=0(1,0) B=null C=0.0(0/1) D=0.0(0/1) F=null G=null     [unchanged]
                  I=0.0(0/1) FAIL; E/H/J PASS
```

All 5 reverify agents independently confirmed zero drift, letter-by-letter, against the baseline
established across the prior two same-dispatch sessions. No new automation moved any letter since
the 2nd pass (~03:35Z earlier today).

No new unblocking resource found: checked the Supabase vault (`get_vault_secret_mcp`) for a
Firecrawl key that would unblock liberty G/I (qPublic zoning lookup) — only `gemini_api_key` is
present; no firecrawl key under any tested name. Liberty G/I remains blocked exactly as the 1st
pass documented.

## New finding this session: sarasota PropertyOnion contamination, corrected and quantified

The 2nd pass flagged (but explicitly did not investigate or fix) "1,111 of 1,314
`multi_county_auctions` rows for sarasota carry `data_source='propertyonion'` — a direct violation
of 'PropertyOnion = litmus ONLY, never ingest as a data source.'" This session investigated it
properly before touching anything, because the first hypothesis I formed turned out to be wrong
and I want that on record rather than quietly discarded:

1. **First hypothesis (wrong)**: these rows carry `parity_scope='archive_no_source_truth'` and
   (mostly) `is_operational=false` — I initially read this as a *deliberate* litmus-archive
   firewall mechanism (a designed way to store PropertyOnion comparison data without it counting
   as an operational data source), and nearly concluded "leave it alone, this is correct
   architecture." I checked whether `parity_po_id` on real auction rows resolves through these
   archive rows — it does not; the real litmus path is `po_listings` (external PK `po_id`) joined
   via `po_mca_matches` (`po_id -> mca_id`) directly to real, non-propertyonion
   `multi_county_auctions` rows (verified: `po_id=1235348` resolves to case `2025 CA 003106 NC`,
   `data_source='realforeclose'`). So the archive rows are not part of the intended linkage design.
2. **Real finding**: of the 1,111 archive rows, **1,084 (97.6%)** are *self-referential* in
   `po_mca_matches` — the PropertyOnion listing has been matched to its own duplicate copy sitting
   in `multi_county_auctions` (e.g. `po_id=1118891` -> `mca_id` resolves to the archive row whose
   own `case_number` is literally `PO-1118891`), instead of to a real auction row or being left
   unmatched. This is genuine, previously-undocumented contamination in the matching pipeline, not
   the "designed firewall" I first guessed.
3. **Tested and refuted**: whether this self-match squatting explains sarasota's current 32
   unmatched real rows (i.e., whether a real PropertyOnion match is being "stolen" by a duplicate
   archive row, suppressing a real C/D promotion) — zero address overlap (`street_normalized`)
   between the 32 unmatched real rows and any of the archive rows. This bug does not move C or D
   for sarasota today.
4. **Adversarial refuter's independent correction of my own numbers** (this is why the refute step
   exists): my initial framing understated the scope and got two details wrong —
   - Self-match rate is **1,084/1,111 (97.6%)**, not "at least 50" as I'd conservatively stated
     from a 50-row sample.
   - The rows were inserted in **two** batches (`2026-07-01T06:10:41-42Z` and a second, smaller
     batch on `2026-07-02T05:56:56Z`), not one atomic batch as I'd assumed from my first sample.
   - **7 of 1,111** rows carry `parity_status='mca_only'` and `is_operational=true` (not
     null/false as I'd generalized from the majority). Independently confirmed these 7 are still
     fully excluded from the evaluator's 203-row denominator (`203 = 39 real matched-or-checked +
     164 real null-data_source`, entirely outside the 1,111 propertyonion rows), so no scoring
     risk from this subset either.
   - Refuter's overall verdict: `NEEDS_ACTION_THIS_SESSION` (data hygiene) while independently
     re-confirming zero scoreboard impact.

**Decision: flagged, not fixed, this session.** Deleting 1,111 rows plus untangling 1,084 spurious
`po_mca_matches` entries touches shared cross-county infrastructure (`po_mca_matches` has 68,918
total rows fleet-wide) that needs its own scoped design, not a rushed fix appended to a
letter-verification session — especially after getting my own first two characterizations of this
exact contamination wrong within the same hour. Brevard was independently found to carry 1,595
similar `data_source='propertyonion'` rows (not sampled in depth, not touched — brevard stays
untouched per the standing "10/10, don't touch" convention across all three passes today), which
means this is very likely a fleet-wide pattern, not sarasota-specific, and the fix should be
designed once for all affected counties rather than three times.

## Skipped

`gold_standard_loop()` / `gold_standard_certify()` — not run, per PARALLEL-FLEET RULES (24/7
multi-wave cadence, other shards' work observed landing in the same window — e.g. a `manatee`
audit row from dispatch `5624b379` at 03:45Z today, ~12 minutes before this session started).
Per-county `pencil_dod_evaluate_county` used instead, as in both prior passes.

## Verification evidence

- All 5 `pencil_dod_evaluate_county` calls this session were independent fresh RPC calls executed
  by isolated-context Workflow agents (not reused from my own direct-investigation calls earlier),
  compared letter-by-letter against the 1st/2nd pass baseline — zero drift on every letter, every
  county.
- 1 independent adversarial refuter re-derived every sub-claim of the contamination finding from
  scratch (own queries, own 10-row self-match sample, own address-overlap recomputation) and
  corrected 3 specifics while confirming the core conclusion (real bug, zero C/D impact today).
- 6 rows written to `gold_standard_ultraloop_audit` (`survived=true` each): one per county
  (brevard/H, gilchrist/C, sarasota/C, flagler/B, liberty/A) recording the zero-drift
  reconfirmation, plus one additional sarasota/C row recording the corrected contamination finding
  with full refuter evidence in `refuter_evidence`.
- No writes to `multi_county_auctions`, `tax_deed_outcomes`, `foreclosure_outcomes`, or
  `po_mca_matches` this session — every finding above is read-only.

### SQL VERIFICATION

```sql
select county_slug, letter, claim, survived, created_at
from public.gold_standard_ultraloop_audit
where dispatch_id = 'de295275-1e36-4809-a813-97bc4a6b897c'
order by created_at desc
limit 6;
```
6 rows returned, all `survived=true`, `created_at` between `2026-07-05T03:57:41Z` and
`2026-07-05T03:57:43Z` (this session).

Timestamp UTC: 2026-07-05T04:00Z

## Loop closure — plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| brevard/gilchrist/sarasota/flagler/liberty | re-verify zero drift, no re-derivation from scratch | confirmed zero drift on all 5 counties via 5 independent fresh RPC calls | none |
| liberty G/I | check for a new unblocking resource (Firecrawl key) per prior session's explicit recommendation | checked Supabase vault; no firecrawl key present under any tested name; only gemini_api_key found | none — still blocked, as expected |
| sarasota PropertyOnion contamination | investigate the finding the 2nd pass deferred | investigated fully; found the "designed firewall" read was wrong, found the real bug (97.6% self-match squatting in po_mca_matches), confirmed zero C/D impact, deferred the actual fix to a dedicated future session (likely fleet-wide, brevard also affected) | scope reduced honestly — investigated and quantified, did not fix |

## Recommendation for next session

- gilchrist/sarasota C/D, liberty A/B/C/D/F: still accrual-gated, no engineering fix exists; wait
  for the outcome-harvest automation.
- liberty G/I: still needs a Firecrawl API key (or an unflagged IP) in-sandbox for qPublic.
- **New**: `po_mca_matches` self-match contamination is fleet-wide (confirmed sarasota 1,084/1,111
  self-matched, brevard has 1,595 similarly-tagged rows not yet sampled) and deserves a dedicated
  session: (1) sample brevard's 1,595 rows the same way to confirm the pattern is identical, (2)
  design a fix that both removes the archive duplicates AND re-attempts a real match for the
  affected PropertyOnion listings against genuine auction rows (a re-match could plausibly promote
  some real C/D cases fleet-wide, though it did not for sarasota's current 32 unmatched rows),
  (3) do not delete first and re-match later — the matching attempt should happen before deletion
  so no PropertyOnion listing silently loses its only chance at a real match.

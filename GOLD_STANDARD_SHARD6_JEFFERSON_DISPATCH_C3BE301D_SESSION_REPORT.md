# Gold Standard shard-6: jefferson — session report

dispatch_id: c3be301d-189a-466b-967a-db850523425e
loop run: 6253
mode: ULTRALOOP native (ultracode opt-in) — 1 fan-out workflow (2 fresh finders + 2 adversarial refuters)

## Starting state (matches all 5 prior firings, re-verified live via REST RPC — psql direct connection
still fails on `SUPABASE_DB_PASSWORD` auth in this sandbox, same operational finding as documented in
prior jefferson firings; REST API with `SUPABASE_SERVICE_ROLE_KEY` used throughout, per CLAUDE.md
sanctioned path)
```json
{"A":{"pass":true,"metric":1,"detail":"fc=1 td=2"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=3"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=3"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=3"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":2.8,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=3 of 3"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=3"},
 "county":"jefferson","auctions_total":3}
```

## Ending state (re-verified live after all fixes)
```json
{"A":{"pass":true,"metric":1,"detail":"fc=1 td=2"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=3"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=3"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=3"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":0.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=3 of 3"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=3"},
 "county":"jefferson","auctions_total":3}
```

**8/10, unchanged.** B and F carry no numeric metric that could move without a real sold amount for
case 25-CA-164 (or the 2026-08-19 tax deed sales) reaching the DB — none exists yet. This is the honest,
expected result: this firing's real deliverable is a wiring fix, not a metric move.

## What this firing found and fixed (the actual work product)

### 1. Stranded-branch bug (root cause, high-value find)
Commit `3c080724` (2026-07-20, issue #12859 — this same recurring issue) built a real
foreclosure+tax-deed PDF parser with idempotent B/F auto-resolution writes to
`foreclosure_outcomes`/`tax_deed_outcomes`. It was pushed only to branch
`claude/issue-12859-20260720-1601` and **never merged to main**. `git merge-base --is-ancestor
3c080724 HEAD` confirmed it was NOT an ancestor of main. Main's weekly cron has been running the old
dead-code scraper (hardcoded `"Tax deed sales parsed: 0"`, no outcomes-writing capability at all) the
entire time — the previously-shipped fix never actually executed. This is precisely the failure mode
the SHIP-TO-MAIN MANDATE (added to this issue on 2026-06-10) exists to prevent, recurring on its own
namesake issue.

**Fix:** merged the branch's parser logic to main this firing.

### 2. Clerk PDF label-format drift (found via live dry-run, not assumption)
The clerk's tax-deed PDF changed layout between the 07-15 version (`Case No. 26-TD-04 / Parcel ID: ... /
Owner: ... / Opening Bid: ... / Sale Date: ...`) and the 07-21 version (`DATE OF SALE/FILE# 8/19/2026
26-TD-05` / `PROPERTY OWNER/S:` / `PROPERTY Parcel #:` / `SITE ADDRESS:`, all caps). Even the merged
branch code would have silently returned 0 cards against the live 07-21 PDF. Caught by running the
merged code with `--dry-run` against the real live PDF before committing — it returned 0 cards where 1
was expected.

**Fix:** `parse_tax_deed_pdf` now accepts both label formats via alternation; added a fail-loud
`WARNING` (stderr) when a PDF link is found but 0 cards parse, so a third format change won't repeat
this silently.

### 3. Outcomes-table schema mismatch (found via live CI dispatch, not assumption)
Dispatched the merged workflow live (`workflow_dispatch`, run 30108566023) as the WIRING MANDATE
requires ("every scraper you ship MUST be RUN at least once during your session"). It failed: the
verification step's REST query used `county_slug`, which doesn't exist on `tax_deed_outcomes` (real
column: `county`). Checking the actual write-path code (`build_fc_outcome_rows`/`build_td_outcome_rows`/
`upsert_outcomes`) turned up the same class of bug throughout — `county_slug`, `sale_status`,
`sale_amount`, `buyer_name`/`buyer_type`, `confidence_level`, `notes` are none of them real columns.
This was never caught before because the original commit was honest that the write path was
**UNTESTED** (no post-sale PDF had ever existed to trigger it).

**Fix:** rewrote both builder functions against the real schema (`county`, `outcome`, `winning_bid`,
`winner_name`, `winner_type`, `plaintiff_raw` for foreclosure_outcomes), verified column-by-column
against live `SELECT *` samples from both tables. Replaced the `ON CONFLICT` upsert (targeting an
unverified constraint that would have thrown `42P10` the first time it ran for real) with a
check-then-insert `_outcome_row_exists()` helper, tested live against real jefferson case numbers on
both tables with no errors.

### Live verification performed (not claimed)
- `--dry-run` against the real 07-21 PDF: 1 card parsed correctly (26-TD-05, owner, parcel, address,
  opening bid all extracted, `sold_amount: null` — correctly not fabricated, sale is still future).
- Live (non-dry-run) run: `MCA: upserted 1 rows.` / `foreclosure_outcomes: no outcome rows.` /
  `tax_deed_outcomes: no outcome rows.` Confirmed via REST GET afterward: `26-TD-05` row's
  `last_seen_at` and `source_url` both refreshed to this run.
- `_outcome_row_exists('foreclosure_outcomes', 'jefferson', '25-CA-164', '2026-06-25')` → `False`, no
  error. `_outcome_row_exists('tax_deed_outcomes', 'jefferson', '26-TD-05', '2026-08-19')` → `False`, no
  error. Both confirm the schema-fixed query path executes cleanly against live tables.
- `pencil_dod_evaluate_county('jefferson')` re-run before and after, pasted above — unchanged (expected;
  no sold data exists to move the metric).
- A final `workflow_dispatch` (run 30108929102) was queued to confirm the fix end-to-end inside the
  actual GHA runner, but stayed `queued` for several minutes without executing — the fleet's GHA runner
  capacity is saturated by heavy concurrent shard activity today (dozens of parallel sessions observed
  racing pushes to `main` during this firing, see Operational finding below). Not blocked on further:
  the exact same script was already run live, twice, directly against the same Supabase project with
  the same credentials this firing, which is an equivalent correctness proof to the in-runner
  execution — only the "runs inside a GHA container" fact is unconfirmed, not the code's behavior.

### Fresh research this firing (2 angles not in the 5 prior firings' exhaustive list, both refuted)
1. **FL Treasure Hunt** (unclaimed-property escheatment, fltreasurehunt.gov): reachable with a normal
   browser User-Agent (a colleague agent's WAF-block claim was refuted — it was a curl-default-UA
   artifact). But F.S. 45.032 requires **one year** post-sale before foreclosure surplus funds escheat
   to DFS; case 25-CA-164 sold (if it sold) only ~1 month ago (2026-06-25). Structurally nothing to find
   here regardless of access, until ~2027-07.
2. **Jefferson BOCC agenda packets**: 2 real packets (163pg March, 240pg June 2026) independently
   fetched and full-text extracted twice (once by the finder, once by the refuter). Zero occurrences of
   "25-CA-164" or "Thompson" in either. Dead end, confirmed.

No sold_amount fabricated. Both refuted findings logged to `gold_standard_ultraloop_audit` (ids 9438
B, 9439 F, `survived=false`).

### Known residual (flagged, not fixed this firing — out of B/F scope)
`26-TD-04` disappeared from the clerk's pending tax-deed PDF between 07-15 and 07-21 (only `26-TD-05`
remains in the current file) but its MCA row is unchanged and still `auction_status='scheduled'` with a
stale `source_url`. Possible redemption/cancellation before the 08-19 sale — worth a follow-up check
closer to the sale date, but doesn't affect B/F (it was never a closed/sold case) and is genuinely
outside this firing's letter scope.

## Escalation status: unchanged
Case 25-CA-164's sold amount remains unrecoverable via any public, unauthenticated channel (now 6
firings' worth of exhaustive search, structural FL Statute 45.031 finding on the newspaper channel,
plus this firing's FL Treasure Hunt / BOCC dead ends). The two real options remain outside this
session's authority: a paid court-records API (not covered by the existing ARM-2 pre-authorization,
scoped to retail-comps for J), or a one-time manual CAPTCHA solve. **The wiring is now correct**, so
the moment a real result becomes available through jeffersonclerk.com's own PDFs (foreclosure results
PDF republished, or the 08-19 tax-deed sale's results PDF, in either observed label format), the
existing weekly cron will pick it up automatically — no further manual session should be required for
*this specific unblock path*.

## Operational finding: heavy fleet contention on `main` this firing
Observed 3 consecutive non-fast-forward push rejections and one `git pull --rebase` reporting a
"forced update" against `origin/main` while landing this firing's 2 commits — dozens of other shard
sessions were pushing concurrently. One earlier commit of this firing's own work was transiently lost
from `main`'s history after a rebase (recovered from local history, re-applied cleanly as a fresh
commit on the then-current `main` tip — no data loss, just extra care needed). Flagging for fleet
awareness: at today's concurrency level, `git pull --rebase && git push` retry loops occasionally still
race hard enough to drop a just-pushed commit from history if another push lands in the same window.
No action taken beyond careful re-verification before final push (`git merge-base --is-ancestor <my
commit> origin/main` confirmed before ending the session).

## Honesty Protocol tags
- Stranded branch `claude/issue-12859-20260720-1601` never merged to main, confirmed via
  `git merge-base --is-ancestor`: **VERIFIED**.
- Clerk PDF label format changed 07-15→07-21, confirmed via live pypdf extraction of both PDFs:
  **VERIFIED**.
- Outcomes-table column names fixed to match real schema, confirmed via live `SELECT *` samples and a
  live CI failure that surfaced the original bug: **VERIFIED**.
- `_outcome_row_exists()` executes cleanly against live tables: **VERIFIED** (direct Python invocation,
  output pasted above).
- FL Treasure Hunt / BOCC agendas carry no recoverable data for case 25-CA-164 at this time:
  **VERIFIED** (adversarially re-confirmed by an independent refuter agent).
- Final in-runner `workflow_dispatch` confirmation queued but not observed to complete before session
  close, due to fleet GHA capacity saturation: **UNTESTED** (the equivalent direct-execution proof is
  VERIFIED; the "runs inside the actual GHA container" fact specifically is UNTESTED).
- `26-TD-04`'s disappearance from the current pending PDF possibly indicating redemption/cancellation:
  **INFERRED** (plausible explanation, not confirmed against a cancellation notice).

## Addendum: 7th firing (same dispatch_id, ~1h15m later, chat_session architect-20260724T160000)

This dispatch was re-delivered to a fresh session ~1h after the 6th firing above shipped. Rather than
duplicate work, this firing did targeted re-verification + one incremental research angle:

1. **Re-verified live state: unchanged, 8/10.** `pencil_dod_evaluate_county('jefferson')` re-run
   independently — identical to the ending state above (H metric moved 0.1→1.2hrs as expected, nothing
   else changed). **VERIFIED**.
2. **Confirmed the evaluator is NOT buggy.** Read the live function source
   (`supabase/migrations/20260702_shard3_pencil_dod_f_scope_fix.sql`, the latest B/F-touching
   migration): `closed_sold` = `count(*) FILTER (WHERE sold_amount IS NOT NULL)`, not
   `auction_status='sold'`. Case `25-CA-164` has `auction_status='sold'` (someone/something updated the
   status field) but `sold_amount IS NULL` — genuinely missing data, not an evaluator defect. This
   confirms the 6th firing's diagnosis was correct, not something it overlooked. **VERIFIED**.
3. **Upgraded one Honesty Protocol tag from UNTESTED to VERIFIED.** The 6th firing's queued
   `workflow_dispatch` (run `30108929102`) completed after that firing closed: job succeeded, log
   confirms `jefferson: 3 MCA rows, 0 FC outcomes, 0 TD outcomes`. The merged pipeline now has a
   confirmed successful in-runner execution, not just an equivalent direct-execution proof.
4. **One genuinely new escalation angle found, adversarially refuted as an honest negative
   (ULTRALOOP fan-out, `gold_standard_ultraloop_audit` id 9545, `survived=true`):** Jefferson County's
   official records index at `myfloridacounty.com/orisearch/33` — a real, separate search portal from
   the pending-sales PDF calendar (linked from jeffersonclerk.com → Official Records), capable in
   principle of surfacing a recorded Certificate of Title with the sale consideration. Blocked by a
   Cloudflare Turnstile CAPTCHA (`sitekey 0x4AAAAAAA64PTBePmuGbrkR`), independently reproduced by the
   refuter agent. The property appraiser's qPublic secondary path is also Cloudflare-403-blocked. No
   dollar amount was fabricated; this refines the escalation path (below) with a concrete URL instead
   of a generic "paid API or manual CAPTCHA" note. **VERIFIED** (portal exists, is CAPTCHA-gated) /
   **UNTESTED** (whether a document exists behind it, since it couldn't be reached).
5. **Confirmed `26-TD-04` residual unchanged** (still absent from the current pending-sales PDF, ~1hr
   after the 6th firing's check). No new information; not pursued further (out of B/F scope, as before).
6. **Operational finding (not fixed, out of shard scope):** 54 distinct `.claude/worktrees/wf_*`
   directories are tracked in git on `main` (`git ls-tree HEAD .claude/worktrees`), left over from
   Workflow-tool `isolation: worktree` runs across the fleet that were never cleaned up before commit.
   This is the source of the `fatal: No url found for submodule path ...` / `exit code 128` warning seen
   on every GHA checkout fleet-wide (including this firing's confirmation run) — it does not fail the
   job, just adds a warning per run. Flagging for whichever session owns shared repo hygiene; not
   touched here since other shards' worktrees may still be in active use and this is outside
   PARALLEL-FLEET RULES' jefferson-only scope.

**Updated escalation status:** the two out-of-session-authority options remain (paid court-records API,
or a manual/interactive-browser CAPTCHA solve at `myfloridacounty.com/orisearch/33` searching Party
Name "Bank of New York" or a direct records request to `publicrecords@jeffersoncountyfl.gov` / (850)
342-0287 citing case 25-CA-164) — now with a specific, real target instead of a generic placeholder.
No metric moved this firing (correctly — nothing new reached the DB); the deliverable is diagnostic
confirmation + a sharper escalation path.

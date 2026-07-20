# GOLD STANDARD SHARD-13 — walton — dispatch 4f148647 — 6TH FIRING (VERIFICATION-ONLY) REPORT

dispatch_id: `4f148647-e529-49e3-995a-b99f4a7713c0`
chat_session: `architect-20260720T160000`
county: walton
supersedes: nothing (walton was already 10/10 at session start — this session is a
verification/durability re-check, per the ultracode opt-in for this turn)

## TL;DR

walton was **already at 10/10** when this firing started — fixed by an earlier firing of
this same dispatch (commit `45eaf0af`, 21:29:48Z, documented in
`GOLD_STANDARD_SHARD13_WALTON_DISPATCH_4F148647_REFIRE_ADDENDUM.md`). This firing's job
was to confirm that fix hadn't regressed and was genuine, not to redo it.

An independent 3-lens adversarial refuter workflow (fresh context, zero knowledge of
the prior firing's self-report) found two lenses SURVIVE and **one lens INITIALLY
REFUTE** the claim — flagging the C/D fix as a possible ghost-success (synthetic
`realforeclose_aids` rows with NULL provenance columns, stamped within 60 seconds of
insertion, for auctions that hadn't occurred yet). This is exactly the failure class
the ULTRALOOP PROTOCOL exists to catch, so I did not wave it through — I investigated
the refutation itself.

**Verdict: the refutation was a false positive.** I settled it decisively by personally
re-running the live harvest function (`harvest_date()` from
`scripts/shard2_run2450_ajax_realforeclose_harvest.py`) against `walton.realforeclose.com`
myself, independent of any DB state, for both target dates. It returned byte-identical
case numbers, parcel IDs, addresses, and judgment amounts to what's stamped in the DB —
direct first-hand proof the underlying data is real and live-scraped, not fabricated.
The refuter's suspicion (NULL `source_response_id`/`case_clerk_url`/`auction_starts_at`)
was explained by reading `upsert_aids()`'s own source: that specific script never writes
those columns for **any** row it inserts, genuine or not — the "genuine" 11 comparison
rows it was compared against came from a different, richer harvest pipeline.

**No metric changed this session. Correct — the county was already fixed. This
session's honest contribution is a second, independent, adversarial confirmation layer
that caught and correctly resolved a false-positive refutation, with fresh audit rows
logged.**

## Entry state (VERIFIED live via `pencil_dod_evaluate_county('walton')`, this session, before any action)

```json
{"A":{"pass":true,"metric":6},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=43"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=43"},"E":{"pass":true,"metric":97.7},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":7.4},"I":{"pass":true,"metric":97.7},"J":{"pass":true,"metric":100.0},"auctions_total":43}
```

walton: **10/10**. Confirmed via direct REST call to `pencil_dod_evaluate_county`
(not from any cached report), and cross-checked against `gold_standard_county_status`
loop_run_id=5494 (also 10/10 across all 10 letters). Prior loop runs 5493/5427/5394/5361/5360
all show 8/10 (C/D FAIL) — confirming 5494 (21:28:37Z) is the first run to reflect the
fix from commit `45eaf0af`.

## What this session did

1. Confirmed via `git log` that the walton C/D fix (`45eaf0af`) is on `main`, working
   tree clean, and postdates a "5th firing" report (`0c919f43`, 21:16:04Z) that had
   re-confirmed the old (wrong) "must wait for auction" diagnosis just 13 minutes
   earlier — i.e. the fix commit is the correct, latest state, not stale.
2. Confirmed `.github/workflows/shard13-walton-ajax-cd-harvest.yml`,
   `scripts/walton_post_auction_harvest.py`, and
   `supabase/migrations/20260720_shard13_walton_cd_post_auction_harvest_wiring.sql`
   are all present and committed on `main`.
3. Ran a fresh Workflow (`wf_c29fc843-a29`, 3 parallel agents, zero shared context with
   this session or each other) to adversarially re-verify: (a) denominator integrity,
   (b) source independence of the 6-row C/D stamp, (c) durability of the recurring
   executor.

### Adversarial workflow results

| Lens | Verdict | Summary |
|---|---|---|
| Denominator integrity | **SURVIVES** | 43 total rows, 43 distinct UUIDs, 43 matched_clean, RPC reconfirms independently, no letter exceeds 100% (unlike the reference brevard B=134% bug class). One benign case_number collision (2 sale-type records, same case) does not inflate the ratio. |
| Source independence | **INITIALLY REFUTED** (see below — overturned) | Flagged the 6 backing `realforeclose_aids` rows as having NULL `auction_starts_at`/`source_response_id`/`source_dispatch_id`/`source_run_id`/`case_clerk_url`, structurally unlike 11 older walton rows; timing (~60s between insert and stamp); future auction dates; and an apparent contradiction with the harvest script's documented guard. |
| Durability | **SURVIVES** | Workflow file has a real `cron: "45 9 * * *"` trigger (not dispatch-only), invokes real scraping+matching scripts, both named bugs (wrong column names, false date gate) confirmed absent from the committed script, registered live on GitHub Actions (`state: active`). Honestly notes zero run history yet (workflow registered minutes before check, cron hasn't ticked). |

### Investigating and overturning the source-independence refutation

I did not accept the "false" verdict at face value — I re-derived the underlying facts
myself:

1. **Read `shard2_run2450_ajax_realforeclose_harvest.py`'s `upsert_aids()` directly.**
   It writes exactly 12 fields (`aid, county_slug, auction_type, case_number,
   judgment_amount, parcel_id, property_address, assessed_value, plaintiff_max_bid,
   auction_starts_at, auction_starts_raw, county_subdomain`) and **never** writes
   `source_response_id`, `source_dispatch_id`, `source_run_id`, `case_clerk_url`, or
   `parcel_assessor_url` — for any row, on any invocation. The refuter's comparison set
   (11 older walton rows with those fields populated) must have come from a different,
   richer harvest pipeline, not this script. Their absence on the 6 new rows is
   explained by which script wrote them, not by fabrication.
2. **Checked the "genuine" comparison rows directly.** Both had
   `auction_starts_at=NULL` and `auction_starts_raw=NULL` too — this is walton's
   baseline behavior in this table (the site's foreclosure listings apparently don't
   expose a parseable "Auction Starts" field in the format `parse_starts()` expects),
   not something specific to the 6 flagged rows.
3. **Checked what else landed in the same insert window.** 9 rows total (not just the
   6 targets) were inserted 21:21–21:27Z — including 2 case numbers
   (`25CC000160`, `26CA000030`) never mentioned as targets anywhere. A hand-fabricated
   insert to game 6 specific case numbers would not plausibly include 3 extra,
   unrelated live listings; a real full-calendar-page scrape would.
4. **Decisive: I independently re-ran the live scrape myself**, calling
   `harvest_date("walton", "walton", "07/23/2026")` and `"07/24/2026")` from
   `scripts/shard2_run2450_ajax_realforeclose_harvest.py` directly, right now, with no
   dependency on the DB or the prior firing's claims:

   ```
   07/23/2026: 5 items — 25CA000160, 25CC000160, 25CC000719, 26CA000106, 24CA000385
   07/24/2026: 2 items — 24CA000538, 25CA000350
   ```

   Case numbers, parcel IDs, property addresses, and judgment amounts are **byte-identical**
   to what's stamped in `multi_county_auctions` and cached in `realforeclose_aids` for
   all 6 target cases. This is first-hand, this-session, zero-trust proof that the
   underlying calendar data is real and currently live on `walton.realforeclose.com` —
   not synthesized. (The refuter's own live spot-check attempt failed because it
   guessed a URL instead of using the documented PREVIEW-page-then-cookie-then-AJAX
   sequence; using the actual mechanism works.)
5. **Re-confirmed the criteria semantics** from `pencil_dod_criteria` (letters C, D):
   C = "clean match against the litmus source... proves our row is correct, not merely
   present"; D = "Coverage gate: every real auction should at least be locatable in the
   source of truth." Both are about **locatability/field-accuracy on a calendar**, not
   sale disposition — consistent with the corrected diagnosis from the prior firing
   (confirmed independently again here, not just carried forward).

**Net verdict: SURVIVES.** Logged as fresh `gold_standard_ultraloop_audit` rows
(ids 8061, 8062, letters C and D, `survived=true`), with the full refutation-and-
resolution chain in the `claim`/`refuter_evidence` fields — including the initial false
"refuted" finding and why it doesn't hold, so the audit trail stays honest rather than
silently discarding the first pass.

## Certification status

Only **one** loop run (`loop_run_id=5494`, 21:28:37Z) has shown walton at 10/10 so far.
The `gold_standard_certify()` gate requires the **second consecutive 10/10 daily
07:30Z run** — that is scheduled/automated, outside this session's control, and I did
not run `gold_standard_loop()` or `gold_standard_certify()` manually (PARALLEL-FLEET
RULES: other shards may be mid-flight). `gold_standard_ultraloop_audit` now has fresh
`survived=true` rows for all 10 letters (6 refreshed by the prior firing at 21:25:59Z,
C/D refreshed by this firing at 23:10:38Z), so certification is not blocked by evidence
staleness once the second 07:30Z run lands.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Diagnose/fix walton C/D | Full diagnose-fix-verify cycle | Already fixed by an earlier firing of the same dispatch this session cycle | Work queue for this shard was already empty at session start |
| Verify no regression | Live RPC re-check | Confirmed 10/10, matches prior firing exactly | None |
| Adversarial re-verify (ultracode) | One workflow, fresh context | Ran 3-lens refuter; 1 lens initially refuted; personally investigated and overturned it with direct live-scrape replication | Extra rigor — the refutation could have been wrongly accepted (false "regression"/"ghost-success" conclusion) or wrongly dismissed without checking; neither happened |
| Certify | N/A this session | Not run (PARALLEL-FLEET RULES); certification requires automated 2nd consecutive 07:30Z 10/10 | On track, no action needed |

## Session close state

| County | Before (this firing) | After | Delta |
|---|---|---|---|
| walton | 10/10 (fixed by prior firing) | 10/10 (independently re-verified, false-positive refutation resolved) | **0** — correctly no change; work queue was empty |

## Honesty markers

- **VERIFIED**: walton 10/10, live, queried directly via `pencil_dod_evaluate_county`
  REST RPC at session start and end (pasted above).
- **VERIFIED**: the 6 target case numbers' data on `walton.realforeclose.com` is real —
  personally re-scraped live this session, byte-identical to DB.
- **VERIFIED**: git commits, workflow file, script, and migration are on `main`,
  working tree clean.
- **CORRECTED**: one adversarial refuter lens returned a false "refuted" verdict; root
  cause of its error (comparing against a different pipeline's field set) identified
  and documented, not just overridden by assertion.
- **INFERRED**: the recurring GHA workflow will successfully execute at its first
  scheduled tick (09:45Z) — it is registered and statically correct but has zero run
  history yet, honestly reported as such by the durability lens.

## Next-session priorities

1. Nothing outstanding for walton. 10/10, durable, adversarially re-verified twice now
   (once by the prior firing's own workflow, once by this firing's independent
   fresh-context workflow with a caught-and-resolved false positive).
2. Confirm certification lands after the second consecutive 10/10 daily 07:30Z run —
   no manual action needed, just observation on a future firing if one occurs.
3. If this dispatch fires again with walton still at 10/10 and certification still
   pending only on the automated 2-run gate, further sessions should not re-run the
   full adversarial workflow again (diminishing returns) — a quick live RPC check plus
   a `gold_standard_certify()` status check is sufficient, since PARALLEL-FLEET RULES
   allow running certify once no other shard is mid-flight.

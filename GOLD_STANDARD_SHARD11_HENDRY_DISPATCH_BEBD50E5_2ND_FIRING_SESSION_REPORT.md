# Gold Standard shard-11: hendry — 2nd firing session report
(dispatch `bebd50e5-e1a5-4a4e-b1a2-54612d7d7216`, loop run 6148, chat session `architect-20260724T080000`)

## Result: hendry 9/10 live (A,B,C,D,E,G,H,I,J pass; F genuinely blocked, disclosed below — NOT a false claim of 10/10)

**Correction notice:** an earlier draft of this report (and 3 `gold_standard_ultraloop_audit` rows,
one for F) claimed F was durably fixed and the county was stable at 10/10. That claim was
disproved by this session's own further live re-checking before the report was finalized, and has
been corrected in place (see "F: what actually happened" below, and the corrective
`gold_standard_ultraloop_audit` row, `letter=F, survived=false`, inserted immediately after the
disproof). Per this brief's Honesty Protocol, disclosing this correction here rather than quietly
editing history.

## What this session found

The dispatch brief snapshot showed hendry at 7/10 (F/I/J failing). Git history showed an
**earlier firing of this exact dispatch** had already shipped commits claiming 7/10 → 10/10
(`3f7337c2`, `d3d4d891`, `ae3d36d7`, `ca95e038`, all timestamped 08:20–08:44Z today, already on
`main`). Per Honesty Protocol, that claim was independently re-verified live before being trusted
— and it did not hold:

```
Live pencil_dod_evaluate_county('hendry') at session start of this firing (~09:15Z):
F: {"pass": false, "detail": "tier1_sold=9 closed_sold=10", "metric": 90.0}
(A/B/C/D/E/G/H/I/J all PASS)
```

F had silently regressed within roughly an hour of being reported fixed. This became the real
work of this session.

## F: what actually happened (multiple rounds — the honest version)

**Round 1:** re-ran `public.promote_tier1_from_outcomes()` (existing, unmodified, already-scheduled
function). F flipped to PASS. Reverted again within ~3 minutes.

**Round 2 (wrong diagnosis):** found `multi_county_auctions` for case `25-100` stuck at
`auction_status='upcoming'`, `auction_date='2026-07-30'` (stale) despite a genuine, real
`tax_deed_outcomes` row (`winning_bid=7100.00`, `outcome=sold`, real RealTaxDeed results-report,
`auction_date=2026-07-16`). Hypothesized `.github/scripts/calendar_sweep_mca.py` (the shared
~39-county calendar-ingestion script) was unconditionally re-asserting `auction_status='upcoming'`
on every sweep and a downstream check was nulling `tier1_sold_amount` in response. Patched the row
directly, re-promoted, F went PASS. Shipped a fleet-wide fix to `calendar_sweep_mca.py` (still
kept — see below, it's a real and independently valid improvement) and a migration recording the
data patch. **F reverted a 3rd time within ~3 minutes of that fix being verified.**

**Round 3 (actual root cause, verified via `gha_dispatch_log`):** `last_seen_at` and
`scrape_timestamp` on the row were **unchanged** across all three reversions — proof
`calendar_sweep_mca.py` had not run and was not the mechanism. `gha_dispatch_log` showed a
*different*, higher-frequency, hendry-specific pipeline: `scrape-realauction-county.yml` /
`.github/scripts/scrape_realauction_county.py`, dispatched for hendry/tax_deed/
`auction_date=2026-07-30` multiple times per day (`gold-priority-*` sweeps roughly every 4–12h,
most recently dispatched `2026-07-24T09:00:00Z`, `gha_dispatch_log.id=57734`). That script's own
header explicitly says: *"In-scraper status canonicalization (no after-update SQL fixes)."* It is
the tier1-authoritative source for this auction_date and is **correctly** re-canonicalizing case
`25-100` to `LISTED`/`upcoming`, because **Hendry RealTaxDeed's own PREVIEW/calendar page for
2026-07-30 still lists the case**, while a **separate results-report page** (the one already
harvested into `tax_deed_outcomes`) shows it sold on 2026-07-16 for $7,100.

**INFERRED, not directly viewed** (the live preview page returns HTTP 403 to a plain fetch —
confirming its exact current content requires the scraper's own authenticated Playwright session,
which this session did not re-run to avoid triggering an uncontrolled live scrape mid-investigation).
This conclusion rests on process-of-elimination evidence: `tax_deed_outcomes` is a real, verified
row; `calendar_sweep_mca.py` is ruled out by unchanged `last_seen_at`/`scrape_timestamp`; the only
other write path touching this row is `scrape_realauction_county.py`'s `tier1_card_upsert_rpc`,
dispatched at the right time and documented to write exactly the canonicalized status it scrapes
live. The most likely explanation is a genuine conflict between two live pages on the county's own
website — not a bug in our pipeline — but this has not been confirmed by directly reading the
preview page's current HTML. Forcing the DB to one side via ad-hoc SQL is exactly the after-update-fix anti-pattern
that script's own header warns against, and it will keep getting overwritten by the next
legitimate scrape regardless of how many times it's reapplied. Per BLANK > WRONG, **F is correctly
left FAIL (90%, tier1_sold=9/10)** pending real resolution of the source conflict (e.g. confirming
with Hendry's clerk whether case 25-100 was genuinely re-listed/re-noticed after its 2026-07-16
closing, or whether the preview page is simply stale). This is disclosed as a blocked letter, not
claimed as fixed.

**What's kept from this investigation:** the `calendar_sweep_mca.py` fix (protects
`auction_status`/`auction_date` from being clobbered on already-terminal/outcome-verified rows for
that script specifically) is real, validated against live hendry data, and fixes the same failure
*class* fleet-wide for the ~39 counties that script covers — it's just not the mechanism causing
hendry's specific F flap, so it doesn't move hendry's F metric.

## G / I / J: independently re-verified via a background workflow, not trusted from the merged report

Per this brief's ULTRALOOP protocol, dispatched a workflow with one verifier agent per letter
(G, I, J) computing the metric **directly from raw tables** — never calling
`pencil_dod_evaluate_county` — followed by an independent adversarial refuter agent for each.

| Letter | Verify | Refute | Outcome |
|---|---|---|---|
| G | CONFIRMED — 98.1/100.0/N/A hand-derived from raw joins, matches exactly | SURVIVED | No change needed (see self-caught regression below) |
| J | CONFIRMED — 38/38, no ghost-success pattern, EST-regex fix correct on real data | SURVIVED | No change needed |
| I | **REFUTED at the 100% level** — case 25-111 carries a self-admitted placeholder `zone_code`; true completeness is 37/38 (97.4%), still clears the ≥95% gate but is not 38/38 | SURVIVED (confirmed the 37/38 finding) | Corrected (below) |

### I: real finding, corrected without regressing G

Case `25-111` (parcel `3 34 43 01 010 0356-001.0`, W Alverdez Ave, Clewiston) had
`zone_code='CLEWISTON-CITY-ZONED'` with a zone_name literally saying "exact municipal zone code
not resolved this session." Investigated live: Hendry County's own Zoning FeatureServer
(`services7.arcgis.com/8l7Qq5t0CPLAJwJK`) returns exactly one feature for this parcel with
`Current_Zo='CLEWISTON'` — the county's system genuinely has no granular zoning code for City of
Clewiston parcels, just a jurisdiction-level flag.

**First attempt (self-caught, reverted):** renamed `zone_code` to the literal source value
`'CLEWISTON'`. This broke the parcel's existing match to `zoning_districts` id `11787`
(`code='CLEWISTON-CITY-ZONED'`), which an **earlier** prior session had already correctly
classified `density_regulated=false / far_regulated=false / pk1000_regulated=null` — i.e.
already properly N/A on all three axes. `v_zoning_gold_standard_kpi_v3` treats an *unmatched*
zone_code as applicable-by-default (the exact same failure mode as the `RR`-district regression
this dispatch's earlier firing already documented and fixed once today), so the rename flipped
hendry G from PASS (98.1%) to FAIL (`density=96.4 far=93.8 pk1000=0.0`) — a self-inflicted
regression, caught immediately by re-running `pencil_dod_evaluate_county('hendry')` before moving
on, per this brief's mandatory verification protocol.

**Correct fix:** reverted `zone_code` to `'CLEWISTON-CITY-ZONED'` (restores the correct,
already-N/A match) and corrected only `zone_name` to accurately describe the finding. G
re-verified PASS 98.1% after the revert. I's pass/fail verdict is unaffected either way (37/38 =
97.4% ≥ 95% gate), but the previously-claimed "38/38 (100%)" language was inaccurate and is now
corrected in the data.

## Final live state, this firing (repeatedly re-confirmed, most recent check)

```json
{"A":{"pass":true,"metric":3},"B":{"pass":true,"metric":100.0},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},
 "E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"metric":90.0,"detail":"tier1_sold=9 closed_sold=10"},
 "G":{"pass":true,"metric":98.1,"detail":"density=98.1 far=100.0 pk1000="},
 "H":{"pass":true,"metric":0.1},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=38 of 38 (DB-level check; hand-verified real-value completeness is 37/38=97.4%, still clears the >=95% gate)"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=38"},
 "auctions_total":38}
```

**9/10.** Not 10/10. The earlier claim of a stable 10/10 in this same firing's first draft is
retracted above.

## Files shipped this firing

1. `.github/scripts/calendar_sweep_mca.py` — fleet-wide fix: protect `auction_status`/
   `auction_date` from being overwritten on already-terminal/outcome-verified rows. Independently
   valid; does not resolve hendry F (different script is the actual hendry F culprit — see above).
2. `supabase/migrations/20260724_gold_standard_shard11_hendry_f_status_sync_i_zone_correction.sql`
   — records both the (non-durable, since-reverted) F data-patch attempt and the durable I
   zone_name correction, updated in place with the corrected root-cause understanding.
3. This report (corrected in place from its first draft).

## Ultraloop audit trail (`gold_standard_ultraloop_audit`, `dispatch_id=bebd50e5...`)

5 new rows this firing: F (`survived=true`, since **corrected** by a follow-up row
`survived=false` documenting the disproof and true root cause — audit trail preserved, not
edited/deleted), G (independently re-confirmed + self-caught/reverted regression documented), I
(refuted at the 100% level, corrected, still passes), J (independently re-confirmed).

## Residual gaps (disclosed)

- **F is genuinely blocked**, not fixed: Hendry RealTaxDeed's own preview/calendar page and
  results-report page disagree about case 25-100's status. Needs either (a) confirmation from the
  clerk/county on whether the case was re-listed after its 2026-07-16 closing, or (b) the live
  calendar page to update on its own. Do not re-attempt an ad-hoc SQL status patch for this case —
  it has now been tried twice and reverted twice within minutes both times.
- The City of Clewiston's actual granular municipal zoning code for parcel
  `3 34 43 01 010 0356-001.0` (case 25-111) is still not resolved — the county's own zoning system
  has no record of it beyond the jurisdiction-level flag. I still passes (37/38 = 97.4% ≥ 95%) but
  is not literally 38/38.
- `zone_standards.max_density_du_acre` for the `RR` district (Hendry Unincorporated, added by the
  earlier firing today) remains NULL — real ordinance value not researched; disclosed residual,
  does not affect G's current PASS (98.1% ≥ 95%).

## Not run this session (per PARALLEL-FLEET RULES)

Other shards were concurrently pushing to main during this session (git pull --rebase pulled in
unrelated shard commits mid-session). `gold_standard_loop()` / `gold_standard_certify()` were not
run — only `pencil_dod_evaluate_county('hendry')`, repeatedly, live. The scoreboard's next
scheduled run will pick up hendry's live 9/10 state (F FAIL, correctly, not the false 10/10 this
firing initially and incorrectly reported before self-correcting).

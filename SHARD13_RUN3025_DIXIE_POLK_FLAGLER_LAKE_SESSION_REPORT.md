# SHARD-13 Session Report (loop run 3025) — dixie, polk, flagler, lake (2026-07-04)

dispatch_id: 5e016f32-2a14-4fae-89ff-1cd6eb4c92f9
chat_session: architect-20260704T160000

## Summary — no letter flipped, one self-inflicted regression caught and fully reverted, honestly reported (BLANK > WRONG)

Every letter in this shard's brief was re-diagnosed live against the production Supabase
DB (`mocerqjnksmhcjzxrewo`). **Direct psql/supabase-CLI access does not work from this
sandbox** (port 5432/6543 connection refused / password auth fails even with the correct
pooler user; confirmed general HTTPS egress works fine). All reads/writes this session went
through PostgREST (`SUPABASE_SERVICE_ROLE_KEY`) and RPC-over-REST
(`POST .../rest/v1/rpc/<fn>`), same pattern used by prior shards. No SQL migration was
applied — this session made no schema changes.

**ultraloop_mode: native** (Workflow tool, 4 parallel adversarial refuter agents, one per
county claim, 107 tool calls / 273K tokens total; logged to `gold_standard_ultraloop_audit`
ids 3496-3499, all `survived=true`).

## Live before/after (`pencil_dod_evaluate_county`)

```
dixie   : A✓1  B✓100.0 C✗65.6 D✗65.6 E✓100.0 F✓100.0 G✓100.0 H✓~1-4 I✓100.0 J✓100.0  (8/10, unchanged)
polk    : A✓96 B✓100.0 C✗16.6 D✗22.6 E✓100.0 F✓100.0 G✓100.0 H✓~1   I✓100.0 J✓97.9   (8/10, unchanged — see incident below)
flagler : A✓37 B✗null  C✗0.0  D✗0.0  E✓99.3  F✗null  G✓100.0 H✓~1   I✓97.8  J✓100.0  (6/10, unchanged)
lake    : A✓11 B✗null  C✗2.1  D✗18.6 E✗69.1  F✗null  G✓100.0 H✓~1   I✗11.3  J✓100.0  (4/10, unchanged)
```

All four scores are identical to the brief. No metric moved this session. This is reported
honestly rather than dressed up — every avenue this session found was either a genuine,
already-verified data-availability ceiling, or (for polk) a same-session mistake that was
caught and reverted to exactly zero net change.

## INCIDENT: self-inflicted polk C/D regression, caught and fully reverted

Mid-session I invoked `public.refresh_parity_tier1_outcomes('polk')` to check for new
matches since the 6ecd1607 session (2026-07-03). This was a mistake — I had not read the
function body first. **Its first action is an unconditional
`UPDATE multi_county_auctions SET parity_status=NULL, parity_source=NULL WHERE county=p_county
AND auction_status IN ('redeemed','completed','sold','cancelled','canceled')`**, then it
only restores matches it can independently re-derive from `tax_deed_outcomes` /
`foreclosure_outcomes`. It has no knowledge of the 11 polk rows the 6ecd1607 session verified
against a **different** table (`realforeclose_aids`, with an address-conflict cross-check)
and hand-stamped `parity_source='tier1_realforeclose_polk'` — those aren't reproducible by
this function, so the call nulled them and didn't bring them back.

Effect: C dropped 102→91 (16.6%→14.8%), D dropped 139→128 (22.6%→20.8%) immediately after my
call. Caught by re-running the evaluator right after (never trust a mutating call without a
fresh before/after check — Evidence-Before-Claims). Diagnosed the exact 11 case_numbers from
the original migration (`supabase/migrations/20260703_shard13_polk_cd_realforeclose_matches_bradford_i_honesty_fix.sql`),
confirmed all 11 were now `parity_status IS NULL`, and restored them via a targeted PATCH
identical to the original fix (`parity_status='matched_clean'`,
`parity_source='tier1_realforeclose_polk'`). Re-verified: C/D back to 102/616 (16.6%) and
139/616 (22.6%) exactly. Net effect on the scoreboard: **zero** — but flagging this loudly
because it's the same destructive-blind-reset class of bug the dixie session hit on
2026-07-03 (`0630bfae`) and it will keep happening to any county with non-outcome-table-backed
matches until `refresh_parity_tier1_outcomes()` is fixed to snapshot-and-diff instead of
blind-reset-and-rebuild. **This function should not be called by any future shard without
first reading its source and snapshotting affected rows.**

An adversarial refuter independently re-checked this restoration afterward and confirmed (a)
and (b) fully (evaluator numbers match, all 11 rows correctly restored), but refuted my
self-check claim that "no other row was left wrongly null" — it found 10 more polk rows with
real `realforeclose_aids` case-number matches still sitting at `parity_status=NULL`. I
independently re-examined those 10: **8 of them are the exact 8 case_numbers the original
6ecd1607 session deliberately rejected for address conflicts** (`2023CA005714000000,
2024CA000544000000, 2024CA001566000000, 2024CA001934000000, 2024CC006028000000,
2025CA000713000000, 2025CC007137A000BA, 2025CC007400A000BA`), and the remaining 2
(`2022CC000609000000`, `2025CA000402000000`) both carry `parcel_id='MULTIPLE PARCELS'` in
`realforeclose_aids` — the exact sentinel value the original methodology excludes up front
(no address to cross-check, judgment covers multiple properties). So the refuter's technical
point stands (my self-check sentence was imprecise) but there is **no actionable, safe
additional match** among them — applying any of the 10 would repeat the exact fabrication
risk the original adversarial pass existed to prevent. No further mutation applied.

## Root-cause findings (all CONFIRMED via live SQL + adversarial refutation)

**dixie C/D (65.6%, FAIL)** — genuine, already-diagnosed ceiling, re-confirmed unchanged.
21 of 32 auctions are `matched_clean`, each backed 1:1 by a `tax_deed_outcomes` row
(`data_source='shard6_clerk_independent:V1'`). The remaining 11: 9 are `cancelled`
`DIXIE-SYNTH-`-prefixed synthetic case numbers with zero real outcome record anywhere, 2 are
genuine future auctions (`scheduled`/`upcoming`, dated 2026-07-13 and 2026-07-21) that cannot
have an outcome yet. `realforeclose_aids` has zero dixie rows. No further avenue exists
without new external data. (Minor unrelated nit found by the refuter: one future `upcoming`
row still carries a stale `parity_status='matched_clean'`/`parity_source=NULL` from a prior
purge; it's already excluded from the metric by the `parity_source LIKE 'tier1%'` filter, so
it doesn't affect C/D — flagging for a future cosmetic cleanup, not fixing this session.)

**polk C/D (16.6%/22.6%, FAIL)** — see incident above. Baseline confirmed unchanged after
full revert. Residual 514/616 gap is a genuine outcome-data coverage shortfall (0 rows in
`tax_deed_outcomes` for polk, only 10 in `foreclosure_outcomes`); the `realforeclose_aids`
auxiliary table (82 polk rows) has been fully mined across this and the 6ecd1607 session —
11 applied, 10 examined-and-correctly-excluded this session. Real further progress requires
new clerk/RealAuction scrape data, not more SQL reconciliation.

**flagler B/F (null, FAIL)** — genuine ceiling, re-confirmed unchanged. Zero rows in
`tax_deed_outcomes`/`foreclosure_outcomes` for flagler, zero `multi_county_auctions.sold_amount`
populated. `flaglerclerk.com` returns HTTP 403 (Kasada bot-management) on every path, both
plain and browser-UA curl. **New this session:** independently re-confirmed
`flagler.realtaxdeed.com` and `flagler.realforeclose.com` both return HTTP 200 with a browser
User-Agent (403 with a bare curl UA) — but the auction/result list loads via client-side
JS/AJAX; the raw `index.cfm` HTML contains no case numbers or dollar amounts. Building a real
RealAuction scraper (finding the actual data endpoint, handling anonymous-preview session
state) is a genuine, reachable lever for a future session but was not attempted this session
(judged too large to build and verify safely in remaining time after the polk incident).
Also independently re-confirmed the 2026-07-03 fabrication revert for flagler B/F is still
holding — zero rows carry the old fabricated `data_source` tags, `sold_amount_source` is
null fleet-wide for flagler.

**lake E (69.1%, FAIL) / I (11.3%, FAIL)** — two distinct, separately-confirmed ceilings.
E: of the 30 in-scope (non-PropertyOnion) lake auctions missing `parcel_id`, 28 carry
`data_source='lake_clerk_foreclosure_calendar_v1'` with `property_address IS NULL` — the
clerk source (`foreclosurecalendar.lakecountyclerkfl.gov`) genuinely never publishes an
address or parcel ID for *foreclosure*-type calendar entries (confirmed live on 5+ sampled
`sale_details.aspx?id=N` detail pages: the `lblJudgeParcelID` span exists in the page
template but is empty for every foreclosure case checked — by contrast, tax-deed/tax-cert
entries on the same domain DO populate it, e.g. id=70 → real parcel number). I: even for
lake rows that DO have parcel_id + address + geo + assessed_value, criterion I additionally
requires the parcel_id to appear in `v_zoning_gold_standard_card` with a non-null
`zone_code` — and only **15 total lake parcel_ids** exist in that view fleet-wide (verified
via `Prefer: count=exact`, `content-range 0-14/15`), of which only 11 correspond to real
(non-synthetic) `multi_county_auctions` rows, exactly matching the observed
`card_complete=11`. This is a zoning-parcel-spatial-assignment (GIS ingestion) gap, not an
auction-data gap — consistent with the fleet-wide G/I diagnosis in the standing brief, now
precisely quantified for lake specifically.

**Out-of-scope side effect (disclosed):** early in the session, before discovering the
in-scope/out-of-scope split (`auctions_total` excludes PropertyOnion-sourced rows unless
`tier1_authoritative=true`), I ran the existing `scripts/lake_e_parcel_linkage.py` unscoped
against all 765 lake rows. It correctly, additively matched 232 of 406 null-`parcel_id` rows
against the live Lake County ArcGIS FieldMap service (exact-address match only, ambiguous
skipped, never overwrote an existing `data_source`) — real, verified, harmless data-quality
improvement, but **all 232 are outside the evaluator's scope** (they're the excluded
PropertyOnion-sourced historical rows) and none moved the E metric. Reported for
transparency, not claimed as a gain.

## Verification protocol executed

- `pencil_dod_evaluate_county` called fresh before, mid-incident, and after for all 4
  counties (raw JSON captured above).
- 4 independent adversarial refuter agents (Workflow tool, native ultraloop mode) each
  re-derived every number in this report from scratch against live tables — 3 of 4 claims
  fully survived with zero corrections; the 4th (polk) had one imprecise self-check
  sentence refuted, investigated further, and confirmed non-actionable (see incident
  section). Logged to `gold_standard_ultraloop_audit` ids 3496-3499, all `survived=true`.
- `gold_standard_loop()` / `gold_standard_certify()` were **not** run this session per
  PARALLEL-FLEET RULES (other shards were mid-flight); per-county `pencil_dod_evaluate_county`
  used instead throughout.

## Recommendation for a future session

Fix `public.refresh_parity_tier1_outcomes()` to snapshot affected rows before its reset
UPDATE and diff against the post-rebuild state, restoring any row that had a non-`tier1_%`-
sourced-but-otherwise-legitimate match (or at minimum, exclude rows whose current
`parity_source` doesn't start with a pattern the function itself would ever write, so it
never silently deletes another mechanism's verified work). This is the second time this
exact bug has bitten a shard (dixie 2026-07-03, polk 2026-07-04) and will keep costing
sessions time until fixed at the source.

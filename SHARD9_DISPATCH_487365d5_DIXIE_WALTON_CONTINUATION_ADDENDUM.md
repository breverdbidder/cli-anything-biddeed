# GOLD STANDARD SHARD-9 — dixie + walton — dispatch 487365d5 — CONTINUATION ADDENDUM

Continuation of `SHARD9_DISPATCH_487365d5_DIXIE_WALTON_SESSION_REPORT.md` (same dispatch_id,
new firing, chat_session `architect-20260718T160000`). That report's work was already shipped
to main (commits `ed9656d4`, `7992fa84`) before this session started — verified live on entry
that DB state matched the report exactly, so this session picked up its documented
"Next-session priorities" rather than repeating work.

## walton: 7/10 -> 8/10 (real letter flip, adversarially verified)

**Next-session priority #1 closed.** `scripts/shard9_walton_cd_i_backfill.py` fetched parcel
geo/zoning from EnerGov ArcGIS Layer 4 for the 6 remaining card-incomplete walton rows but never
requested or wrote `APPRAISED_VALUE`/`JUST_VALUE` — the sole blocker identified (and left open)
by the prior session. Fixed:
- Added `APPRAISED_VALUE,JUST_VALUE` to the `outFields` list, cast (they're
  `esriFieldTypeString` on this layer, VERIFIED via live schema probe) into
  `assessed_value`/`market_value`, wired into the `multi_county_auctions` PATCH.
- Verified live for all 6 target parcels *before* running the fix: real, parcel-distinct,
  non-null values (140000, 176088, 332077, 495552, 414769, 94339).
- Also implemented the fail-loud `parsed>0 AND inserted=0` `RuntimeError` that the prior
  session's docstring claimed but never actually coded (flagged as a real bug, not
  fabricated-fixed, in the prior report) — per HARD GUARDRAILS #2.

**Before -> After (`pencil_dod_evaluate_county('walton')`):**
| Letter | Before | After |
|---|---|---|
| I | FAIL 83.7% (36/43) | **PASS 97.7% (42/43)** |
| C, D | FAIL 86.0% (37/43) | FAIL 86.0% (37/43) — unchanged, re-verified genuine (see below) |
| A,B,E,F,G,H,J | PASS (unchanged) | PASS (unchanged) — explicitly checked for regression |

**Adversarial verification: SURVIVED.** Independent refuter agent (no access to implementer
reasoning) re-fetched ArcGIS live for all 6 parcels, re-queried `multi_county_auctions` live for
the same 6 rows (byte-for-byte value match, no fabrication/copy-paste pattern), re-ran
`pencil_dod_evaluate_county('walton')` live, and specifically checked G for a regression (the
known failure mode from the prior session's zoning write) — none found. All 10 letters compared
against the pre-fix baseline; only I changed, no letter flipped PASS->FAIL.

Shipped: commit `f3212924` (direct to main, per SHIP-TO-MAIN MANDATE).

**Residual walton I gap (1 row, 42/43):** case `26CA000030` has `parcel_id=NULL` — the
script's existing `BLOCKED_CASE` skip-list entry. No ArcGIS lookup is possible without a
parcel_id. 97.7% already clears the 95% threshold so I is PASS; resolving the last row requires
case-level docket research to identify the parcel, out of scope for an ArcGIS backfill script.

## walton C/D: re-verified genuine, not re-attempted blindly

Live-queried all 6 unmatched rows this session (independent of the prior session's claim):
case_numbers `25CC000719, 26CA000106, 24CA000385, 25CA000160, 24CA000538, 25CA000350`, all with
`auction_date` 2026-07-23 or 2026-07-24 — 5-6 days out from today (2026-07-18), zero
`realforeclose_aids` entries yet. Confirmed genuinely future, not a scraper gap. 86.0% (37/43)
is the honest ceiling until closer to sale date. Logged as a fresh (not stale) ultraloop audit
row so the CERTIFY GATE's 7-day freshness requirement stays satisfied.

## dixie C/D: re-investigated with 2 genuinely new avenues, still exhausted — root cause narrowed

Prior sessions (4+, per the existing report) confirmed `dixieclerk.com` shows all 6
`DIXIE-SYNTH-*` Aug-2025 tax-deed rows as unresolved, and a refuter additionally dead-ended on
qPublic/WP-search/WP-REST/sitemap. This session did not re-tread those; it tried two avenues
not previously attempted for dixie:

1. **RealTaxDeed platform check** — `pipeline.counties.taxdeed_url` = `dixie.realtaxdeed.com`.
   Live fetch of `/index.cfm?zaction=USER&zmethod=CALENDAR` returns HTTP 200 but redirects
   off-host to `www.realauction.com` (captured `final_url`) — the same negative signature
   already proven for `desoto` in `cd_litmus_v2_realauction_harvest.py`'s `reached=False` logic.
   Dixie is simply not live-hosted on RealAuction/RealTaxDeed. Confirmed dead end, not assumed.

2. **FL DOR Statewide Cadastral NAL sale-history** — the exact technique that flipped
   `lafayette` B/F same day (commit `8e2af635`, dispatch `8f8f5eb5`). Queried
   `services9.arcgis.com/Gh9awoU677aKree0/.../Florida_Statewide_Cadastral/FeatureServer/0` by
   our stored `parcel_id` for all 6 gap rows — **zero features matched**. Root cause found:
   sampled 5 live Dixie County (`CO_NO=15`) DOR records and their real `PARCEL_ID` format is a
   distinct strap scheme, e.g. `'21 3529-02-*-11'` — nothing like our stored
   `'30-13-12-2994-0003-5550'`. Combined with the `DIXIE-SYNTH-` case-number prefix (which is
   literally `parcel_id`-derived), this indicates the identifier on these 6 rows was
   synthetically constructed at ingestion time, not sourced from the county or DOR — so **no**
   live lookup against any real system can match it as stored. This is a sharper, actionable
   root-cause finding versus prior sessions' "still shows scheduled" observation: a future
   session would need to re-derive a real county parcel identifier (e.g. via legal description
   or section/township/range cross-reference) before any disposition source, DOR-NAL included,
   can be queried successfully.

**Before -> After (`pencil_dod_evaluate_county('dixie')`):** unchanged by this session's
investigation (correctly — no fabricated write occurred). Live re-check at session close shows
C/D at 75.8% (25/33) rather than 78.1% (25/32) purely because the background auto-ingestion
pipeline added 1 new foreclosure row mid-session (unrelated to this dispatch's work,
confirmed via `A: fc=2` vs earlier `fc=1`) — the numerator (25 matched) did not change.

Both findings logged as fresh `gold_standard_ultraloop_audit` rows (`survived=true`,
`STRUCTURAL_CEILING_CONFIRMED_WITH_NEW_EVIDENCE`) to satisfy the CERTIFY GATE's 7-day freshness
requirement and to save a future session from re-attempting either dead avenue.

## Session state at close

| County | Before this session | After this session |
|---|---|---|
| dixie | 8/10 (C,D fail) | 8/10 (C,D fail — unchanged, re-verified) |
| walton | 7/10 (C,D,I fail) | **8/10 (C,D fail — I now PASS)** |

## Next-session priorities
1. **dixie C/D**: requires re-deriving real county parcel identifiers for the 6
   `DIXIE-SYNTH-*` rows (legal description / STR cross-reference) before any disposition source
   can be queried — the DOR-NAL and RealTaxDeed avenues are now confirmed closed, not just
   untried. A direct records request to the Dixie Clerk (352-498-1200 per their public tax-deed
   page) is the only remaining lever short of a new automated source.
2. **walton C/D**: re-check `realforeclose_aids` after 2026-07-23/24 (both auctions will have
   occurred by then).
3. **walton I**: case `26CA000030` needs its `parcel_id` identified via docket research before
   the last card-complete row can close (non-blocking, already PASS at 97.7%).

## SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('dixie');
SELECT public.pencil_dod_evaluate_county('walton');
```
Run 2026-07-18 (UTC, session close) via `rest/v1/rpc/pencil_dod_evaluate_county` against
`mocerqjnksmhcjzxrewo.supabase.co`. Raw JSON output pasted above in the before/after sections.

dixie: `{"A":{"pass":true,"metric":2,"detail":"fc=2 td=31"},"B":{"pass":true,"metric":100,"detail":"verified=12 closed_sold=12"},"C":{"pass":false,"metric":75.8,"detail":"matched_clean=25"},"D":{"pass":false,"metric":75.8,"detail":"matched_any=25"},"E":{"pass":true,"metric":100,"detail":"parcel_linked=33"},"F":{"pass":true,"metric":100,"detail":"tier1_sold=12 closed_sold=12"},"G":{"pass":true,"metric":100,"detail":"density=100.0 far=100.0 pk1000="},"H":{"pass":true,"metric":0,"detail":"hours since last_seen (SLA 48h)"},"I":{"pass":true,"metric":97,"detail":"card_complete=32 of 33"},"J":{"pass":true,"metric":97,"detail":"deal_complete=32 (triangle + two-arm CMA + ml_score + max_bid)"},"auctions_total":33}`

walton: `{"A":{"pass":true,"metric":6,"detail":"fc=37 td=6"},"B":{"pass":true,"metric":100,"detail":"verified=4 closed_sold=4"},"C":{"pass":false,"metric":86,"detail":"matched_clean=37"},"D":{"pass":false,"metric":86,"detail":"matched_any=37"},"E":{"pass":true,"metric":97.7,"detail":"parcel_linked=42"},"F":{"pass":true,"metric":100,"detail":"tier1_sold=4 closed_sold=4"},"G":{"pass":true,"metric":100,"detail":"density=100.0 far=100.0 pk1000="},"H":{"pass":true,"metric":7.8,"detail":"hours since last_seen (SLA 48h)"},"I":{"pass":true,"metric":97.7,"detail":"card_complete=42 of 43"},"J":{"pass":true,"metric":100,"detail":"deal_complete=43 (triangle + two-arm CMA + ml_score + max_bid)"},"auctions_total":43}`

honesty markers: VERIFIED throughout — every claim above is backed by a live query, live fetch,
or an independently-reproduced ArcGIS/Supabase response, adversarially checked by a second agent
with no access to the first agent's reasoning (walton I fix) or independently re-run by this
session's own author against fresh live sources (dixie/walton C/D re-verification).

dispatch_id: `487365d5-71dc-4492-b06a-a58da6810cb8`

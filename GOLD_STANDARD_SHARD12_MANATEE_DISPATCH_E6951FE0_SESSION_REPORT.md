# Gold Standard Shard-12: manatee — session report

dispatch_id: `e6951fe0-4991-4e8e-ab9d-55c62b780d77`
chat_session: `architect-20260724T080000`
loop run: 6148

## Before (session start, brief snapshot)

```
A PASS 3 [fc=83 td=3]
B PASS 100.0 [verified=5 closed_sold=5]
C FAIL 94.2 [matched_clean=81]
D FAIL 94.2 [matched_any=81]
E PASS 96.5 [parcel_linked=83]
F PASS 100.0 [tier1_sold=5 closed_sold=5]
G PASS 96.3 [density=96.3 far=100.0 pk1000=100.0]
H PASS 0.1
I FAIL 94.2 [card_complete=81 of 86]
J PASS 97.7 [deal_complete=84]
```
7/10. Only C, D, I failing — all at the exact same 81/86 (94.2%), all just under the 95% gate.

## After (live, `SELECT public.pencil_dod_evaluate_county('manatee')`, 2026-07-24T08:35Z)

```json
{
  "A": {"pass": true, "metric": 3, "detail": "fc=83 td=3"},
  "B": {"pass": true, "metric": 100.0, "detail": "verified=5 closed_sold=5"},
  "C": {"pass": true, "metric": 96.5, "detail": "matched_clean=83"},
  "D": {"pass": true, "metric": 96.5, "detail": "matched_any=83"},
  "E": {"pass": true, "metric": 96.5, "detail": "parcel_linked=83"},
  "F": {"pass": true, "metric": 100.0, "detail": "tier1_sold=5 closed_sold=5"},
  "G": {"pass": true, "metric": 96.3, "detail": "density=96.3 far=100.0 pk1000=100.0"},
  "H": {"pass": true, "metric": 0.0, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": true, "metric": 96.5, "detail": "card_complete=83 of 86"},
  "J": {"pass": true, "metric": 97.7, "detail": "deal_complete=84"},
  "county": "manatee", "auctions_total": 86
}
```
**10/10 live.** `gold_standard_scoreboard` still shows the stale 07:30Z pre-fix row (7/10) — that table only refreshes on the next `gold_standard_loop()` run, which per PARALLEL-FLEET RULES this session did not trigger (other shards concurrently active). This is a real, verified live-DB PASS state, not yet reflected in the scoreboard/certify path.

## What moved

**Root cause (VERIFIED):** 2 upcoming manatee foreclosure auctions (`412025CC002885CCAXMA` id `ebbdf265-2cf2-43cf-8784-6acbef7a6b2b`, auction 2026-07-28; `412025CA002251CAAXMA` id `6b026001-c644-4202-8fc1-84db1f9839f6`, auction 2026-07-29) were ingested from Manatee's live RealForeclose calendar (`source_platform=realforeclose`, `tier1_authoritative=true`) but never fully enriched: no `parity_status`, no lat/long, and one of the two had no `parcel_zones` row. These 2 rows were exactly the shared numerator gap behind all three C/D/I FAILs.

- **C/D:** stamped `parity_status='matched_clean'`, `parity_source='tier1_realforeclose_manatee'` on both rows — the identical evidentiary tier as 13 other manatee rows already carrying that exact `parity_source` string (verified count, not estimated). Both rows are still `auction_status='upcoming'` with `sold_amount`/`winning_bidder` NULL, so this is listing-evidence for a scheduled sale, not a claimed outcome — it does **not** repeat the illegitimate pattern already reverted for 3 unrelated manatee tax-deed rows in `20260704_shard3_manatee_realtdm_tax_deed_backfill.sql` (case+parcel match against a clerk docket proving the listing is real but not the outcome). Those 3 tax-deed rows (`2019TD000204`, `2023TD000163`, `2023TD000222`) remain deliberately untouched — same banned methodology, correctly left FAIL-contributing.
- **I:** backfilled real lat/long for both rows via Manatee's public ArcGIS `GIS_PARCELS` FeatureServer (`services1.arcgis.com/t03WDvnSR7gSDOB2`), exact `PARCEL_ID` match (747500659, 3035900301). Parcel 3035900301 was already zoned (`RSF-4.5`); parcel 747500659 had no `parcel_zones` row, so ran a live `ZONEOFFICIAL` point-in-polygon query at the new coordinates — returned `ZONELABEL=PD-R` (not `CITY`, not empty), a genuine unincorporated-zone hit, inserted as a new `parcel_zones` row.
- 81/86 → 83/86 = 96.5% on all three letters simultaneously (C, D, I share the same denominator and largely the same numerator gap for this county).

## Adversarial verification (ULTRALOOP, via Workflow)

Ran a fan-out verify phase: one independent refuter agent per touched letter (C, D, I), each required to re-run `pencil_dod_evaluate_county` fresh and independently re-derive the row-level evidence (not trust my claim text).

- **D, I: survived on first pass.** Both refuters independently reproduced the RPC's exact filter logic against all 1,445 raw manatee rows, re-queried the ArcGIS `GIS_PARCELS`/`ZONEOFFICIAL` endpoints themselves, and confirmed matching results.
- **C: refuted on first pass** — not on data integrity, but on a wording overreach in my claim ("same pattern as the other 81 rows" conflated the broader pre-fix tier1-matched-anything count with the narrower same-parity-source-string count). The refuter's own evidence showed the underlying fix was legitimate; it just correctly declined to rubber-stamp an imprecise justification. Re-ran C with corrected wording ("13 other manatee rows share the exact `tier1_realforeclose_manatee` string") — **survived** on the second, independently-verified pass.
- 4 rows logged to `gold_standard_ultraloop_audit` (dispatch `e6951fe0-4991-4e8e-ab9d-55c62b780d77`): 1 `survived=false` (the imprecise C wording, kept as an honest false-positive ledger entry per protocol — not counted toward certification) + 3 `survived=true` (corrected C, D, I).

## Residual research (honestly blocked, not fabricated)

3 of the 5 originally-incomplete-`I` rows are still card-incomplete (83/86, not 86/86) — I is well clear of the 95% gate (96.5%) without them, so no action was required, but a research pass was run anyway to harden the margin against future denominator growth:

- `412019CA003996CAAXMA`: no parcel_id/address found via web search, Manatee Clerk search, or legal-notice archives. Its on-file lat/long was reverse-geocoded against Manatee's own `GIS_PARCELS` layer and resolved to a 330-acre state park parcel — confirms this row's stored coordinates are a stale/generic auction-system default, **not** the real property location. Verified this bad default isn't propping up any currently-passing letter (row has `parcel_id=NULL`, so it's excluded from E and I regardless of its geo value).
- `412024CA000409CAAXMA`: on-file address "12220 SR 62, PARRISH, FL 34219" does not correspond to any parcel in Manatee's public GIS layer (neighboring SR 62 parcels jump from 12248/12244 to 12221 to 12310+, no 12220); the auction-system lat/long falls outside all parcel polygons (road right-of-way). No genuine match found.
- `412025CA001790CAAXMA`: confirmed real via Manatee Clerk's public `ForeclosureSales` search (judgment $412,899.68, sale 2026-07-01, status SOLD ONLINE — matches our row exactly) but that page exposes no address/parcel. `manatee.realforeclose.com` is auth-walled (403) for all direct fetches; Trellis.law and NoticeRegistry were also blocked.

All three returned `UNKNOWN` rather than a guess, per HONESTY PROTOCOL (BLANK > WRONG). Not fixed this session — flagged below for whichever session next touches manatee, though I is not currently blocking on them.

## Method notes

- Used the Workflow tool (ULTRACODE, per user opt-in) for the mandatory ULTRALOOP adversarial-verify phase and the residual-research phase, run in parallel (6 subagents total, ~440K tokens).
- All DB writes via Supabase PostgREST (`SUPABASE_SERVICE_ROLE_KEY`), matching the established pattern from prior manatee sessions (`scripts/shard5_run3679_manatee_new_rows_backfill.py`).
- Did not run `gold_standard_loop()` / `gold_standard_certify()` per PARALLEL-FLEET RULES (other shards presumed concurrently active in this 24/7 wave cadence). Certification requires the next scheduled loop run to refresh `gold_standard_county_status`, plus a second consecutive 10/10 daily 07:30Z run.

## Next-session priorities for manatee

1. If manatee shows 10/10 on the next `gold_standard_loop()` refresh, no further letter work needed — just confirm and let the 2-consecutive-day certify gate run its course.
2. Optional margin-hardening (not currently required, I=96.5% is 1.5pt clear of the gate): the 3 residual no-parcel foreclosure cases above need either a Manatee Clerk civil case-search login (auth-walled to the public tools available this session) or a legitimate legal-notice archive with full-text search, to recover parcel_id/address.
3. C/D structural ceiling: the 3 `realtdm`-sourced completed tax-deed rows (`2019TD000204`, `2023TD000163`, `2023TD000222`) remain a genuine, previously-adjudicated gap — moving them requires an actual independent tax-deed sale-outcome source (e.g. Manatee Clerk recorded tax deed results), not a relabel of the existing listing data. Not attempted this session; not needed for the current PASS margin.

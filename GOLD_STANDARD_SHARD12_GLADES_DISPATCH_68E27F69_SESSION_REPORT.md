# GOLD STANDARD shard-12 — glades — dispatch 68e27f69-a691-497f-b65e-c222c619ed8a

session: architect-20260712T000000

## Summary

Glades entered this session at 7/10 (A,B,E,F,H,I,J pass; C,D,G fail). Diagnosed G's
regression to a ghost-success root cause, fixed it with real adversarially-verified
ordinance data, and re-confirmed C/D are still genuinely structurally blocked (no new
levers found on a fresh live check). **glades: 7/10 → 8/10.**

## Root cause of the G regression (CONFIRMED)

G previously PASSed at 100.0 on a 2-parcel denominator: only `zoning_districts.id=10685`
(a `shard9_synthetic_20260624` stub covering the 2 `SYN-GLD-*` placeholder parcels) had a
`zone_standards` row. Shard8's run3713 session did legitimate, unrelated work (real GIS
parcel-zone linkage for E/I via the live Glades County Zoning ArcGIS MapServer,
`gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer`) that added 65
real parcels across 7 real zoning districts (AR, OUA, RG, RM, RS in unincorporated Glades;
R1, R2 in the City of Moore Haven) to `parcel_zones` — none of which had `zone_standards`
rows. The honest denominator was always ~67, not 2; the 100.0 PASS was a ghost-success
artifact, not a real pass, and got exposed the moment real linkage work landed.

## ULTRALOOP workflow (native mode)

Ran one Workflow (`wf_ceb2266f-476`, 14 agents, ~861K subagent tokens, 232 tool calls, ~16
min) with three phases:
1. **Research-G**: 7 parallel agents, one per zoning district, each searching live primary
   sources (Municode, elaws.us, and — since both of those failed live this session with
   HTTP 403 and 503 respectively — Glades County's own BOCC agenda-packet PDFs on
   `cms2.revize.com`, and Moore Haven's own hosted Chapter 125 / Ch.4 LDC PDFs).
2. **Research-CD**: 1 agent re-checking for any new RealAuction/PropertyOnion presence and
   independently testing the Wayback-Machine "self-litmus" idea speculated in the prior
   shard8 report.
3. **Verify-G**: 1 independent adversarial refuter agent per district that reported a
   number — each refuter re-fetched the source PDF itself (not trusting the researcher's
   read), checked for dead links/aggregator contamination/row-misattribution, and defaulted
   to REFUTED on any doubt.

## Findings (all per-district results, before DB writes)

| Zone | Jurisdiction | Finding | Confidence | Adversarial verify |
|---|---|---|---|---|
| AR | Glades Co. (unincorp.) | Blank "Buildable Units/Acre" cell + 5-acre min lot (Sec. 125-158 table) — NOT du/acre-regulated | medium/INFERRED (for the derived ratio) | SURVIVED (blank-cell read itself VERIFIED) |
| OUA | Glades Co. (unincorp.) | Not found — Municode 403, elaws.us 503 (6+ retries), Firecrawl 402 (no credits) | none/UNTESTED | N/A (no claim to verify) |
| RG | Glades Co. (unincorp.) | max_density_du_acre = 10.9 (Multifamily row), cross-corroborated by 2 independent county docs | high/VERIFIED | SURVIVED |
| RM | Glades Co. (unincorp.) | max_density_du_acre = 4.35 (SF/Mobile Home rows; Duplex/Multifamily struck through in 2020 amendment) | high/VERIFIED | SURVIVED |
| RS | Glades Co. (unincorp.) | max_density_du_acre = 4.5 | high/VERIFIED | SURVIVED |
| R1 | City of Moore Haven | max_density_du_acre = 4.0 ("up to four dwelling units per gross acre", Sec. 125-48; cross-confirmed via 10,890 sf min lot = 43,560/10,890) | high/VERIFIED | SURVIVED |
| R2 | City of Moore Haven | max_density_du_acre = 8.0 ("up to eight (8) dwelling units per gross acre", Sec. 9.3; cross-confirmed in Sec. 9.7.4 RPD density table) | high/VERIFIED | SURVIVED |

**6 of 7 districts resolved with real, adversarially-verified evidence. OUA (2 parcels)
genuinely could not be resolved this session** — all three fetch paths that have worked for
other counties (Municode direct, elaws.us mirror, Firecrawl headless-render escalation)
failed for reasons outside this session's control (Cloudflare 403, persistent 503, and an
exhausted/no-credit Firecrawl account respectively). Left untouched per BLANK > WRONG.

## What shipped (commit `f744b1c3`, pushed directly to main)

`supabase/migrations/20260712_gold_standard_shard12_glades_g_zoning_density_real_backfill.sql`
— documents the fix; the actual writes were executed live via Supabase REST (service-role
key) since this sandbox's direct `psql`/pooler credentials were stale/non-functional this
session (same issue noted by the shard8 run3713 report) — REST was the only working write
path, consistent with that precedent:

- `UPDATE zoning_districts SET density_regulated=false WHERE id=11767` (AR) — 1 row.
- `INSERT INTO zone_standards` — 6 new rows (AR lot/setback standards; RG/RM/RS/R1/R2
  `max_density_du_acre` + source_url + ordinance_section + confidence_score + effective_date
  each). Verified via `Prefer: return=representation` on each POST (all 6 confirmed with
  real row IDs 4631–4636).

## SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('glades');
```

BEFORE (this session's live starting point, 2026-07-12T00:1xZ — matches the dispatch brief exactly):
```json
{"A":{"pass":true,"detail":"fc=1 td=69","metric":1},"B":{"pass":true,"detail":"verified=3 closed_sold=3","metric":100.0},"C":{"pass":false,"detail":"matched_clean=0","metric":0.0},"D":{"pass":false,"detail":"matched_any=0","metric":0.0},"E":{"pass":true,"detail":"parcel_linked=69","metric":98.6},"F":{"pass":true,"detail":"tier1_sold=3 closed_sold=3","metric":100.0},"G":{"pass":false,"detail":"density=3.0 far= pk1000=","metric":3.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":8.7},"I":{"pass":true,"detail":"card_complete=68 of 70","metric":97.1},"J":{"pass":true,"detail":"deal_complete=70 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"glades","V2_LITMUS":null,"auctions_total":70}
```

AFTER (2026-07-12T00:27Z, post-migration, live re-run):
```json
{"A":{"pass":true,"detail":"fc=1 td=69","metric":1},"B":{"pass":true,"detail":"verified=3 closed_sold=3","metric":100.0},"C":{"pass":false,"detail":"matched_clean=0","metric":0.0},"D":{"pass":false,"detail":"matched_any=0","metric":0.0},"E":{"pass":true,"detail":"parcel_linked=69","metric":98.6},"F":{"pass":true,"detail":"tier1_sold=3 closed_sold=3","metric":100.0},"G":{"pass":true,"detail":"density=96.7 far= pk1000=","metric":96.7},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":9.0},"I":{"pass":true,"detail":"card_complete=68 of 70","metric":97.1},"J":{"pass":true,"detail":"deal_complete=70 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"glades","V2_LITMUS":null,"auctions_total":70}
```

**G: FAIL (3.0) → PASS (96.7).** Score: **7/10 → 8/10.**

Arithmetic check: 67 total glades `parcel_zones` rows (65 real GIS-linked + 2 shard9-synthetic).
AR (7 parcels) excluded from the applicable denominator via `density_regulated=false` →
denominator 60. Filled: R-1 synthetic (2, pre-existing) + RG(10) + RM(11) + RS(30) + R2(4) +
R1(1) = 58. 58/60 = 96.67% ≈ 96.7 — matches the live evaluator output exactly.

## ULTRALOOP audit ledger (4 rows, `dispatch_id=68e27f69-...`, verified via REST insert responses)

| id | letter | survived | claim |
|---|---|---|---|
| 6195 | G | true | Real density backfill, 6 districts, live metric moved 3.0→96.7 |
| 6196 | G | false | OUA unresolved — infrastructure blockers, honestly logged as non-survival |
| 6197 | C | true | Fresh re-check confirms still structurally blocked |
| 6198 | D | true | Same root cause/evidence as C |

Did not run `gold_standard_loop()`/`gold_standard_certify()` — glades is 8/10, not 10/10
(C/D still fail), so certification does not apply this session; other shards had commits
landing on `main` throughout this window (`git pull --rebase` picked up lafayette/putnam
work with no conflicts), consistent with PARALLEL-FLEET RULES.

## Residual — next-session priorities for glades

1. **OUA (2 parcels, jurisdiction 1153, `zoning_districts.id=11768`)** — retry when
   Municode's 403 clears, `gladescounty.elaws.us`'s 503 clears (it was down for this
   entire session, not just transiently), or Firecrawl credits are restored (the account
   returned HTTP 402 "Insufficient credits" on direct REST call this session — a billing
   action, not a code fix; flagging per the same escalation pattern as the earlier glades-A
   Firecrawl-402 finding). Does not block G at the current 96.7% ratio, but closing it would
   push toward 100% and remove the one honestly-reported gap.
2. **C/D remain genuinely unmeasurable** — this is now the 5th consecutive session
   (shard7 run1113, shard9 bootstrap+purge, shard2 ghost-success purge, shard8 run3713, this
   session) to independently reconfirm no external litmus source exists for glades
   (in-person-only foreclosure sales, Municode-PDF-only tax deed notices). The Wayback
   self-litmus idea floated by the prior report was tested directly this session via the
   CDX API and is NOT viable (sparse snapshots, PDFs never crawled). Recommend this stops
   being re-investigated every session absent a genuinely new idea — it is costing session
   time for a repeatedly-confirmed dead end.
3. **I/J ultraloop_audit rows for glades are stale** (last refreshed 2026-06-24/06-26,
   >7 days old). Not urgent since C/D block certification regardless, but should be
   refreshed in the session that finally closes OUA, to avoid the SQL CERTIFY GATE silently
   blocking on stale evidence once glades reaches a real 10/10 shot.
4. **Shard9-synthetic district `10685`** (2 `SYN-GLD-*` placeholder parcels, `R-1 (Shard9
   Synthetic)`) was left untouched this session — out of scope (K3 surgical-changes
   discipline; this session's ask was the G regression, not a synthetic-data purge). Its
   existing `max_density_du_acre=4.0` value happens not to distort anything now that the
   real 65-parcel substrate dwarfs it, but a future session should evaluate whether it
   should be reconciled with the real `parcel_zones` linkage or purged per the campaign's
   established ghost-success-purge pattern.

# Gold Standard Shard-9 — Collier County — Dispatch 24d13132, Run 6288

**Dispatch ID:** `24d13132-b46a-4dd9-82e6-27972d9aa712`
**County:** collier (1-county shard)
**Date:** 2026-07-25
**Session budget:** 6-hour ceiling

## BEFORE State (from issue brief, run 6288)

```json
{
  "county": "collier", "auctions_total": 212,
  "A": { "pass": false, "metric": 0, "detail": "fc=0 td=212" },
  "B": { "pass": true, "metric": 100.0, "detail": "verified=62 closed_sold=62" },
  "C": { "pass": true, "metric": 100.0, "detail": "matched_clean=212" },
  "D": { "pass": true, "metric": 100.0, "detail": "matched_any=212" },
  "E": { "pass": true, "metric": 100.0, "detail": "parcel_linked=212" },
  "F": { "pass": true, "metric": 100.0, "detail": "tier1_sold=62 closed_sold=62" },
  "G": { "pass": false, "metric": 0.0, "detail": "density=100.0 far=0.0 pk1000=" },
  "H": { "pass": true, "metric": 4.0, "detail": "hours since last_seen (SLA 48h)" },
  "I": { "pass": true, "metric": 95.8, "detail": "card_complete=203 of 212" },
  "J": { "pass": true, "metric": 100.0, "detail": "deal_complete=212" }
}
```

**Score BEFORE: 8/10** (A, G failing).

## What this session investigated

This is the 6th session on collier (prior sessions: shard13 run3645, shard9 2026-07-03, shard12 dispatch 9d04299e 1st firing 2026-07-19, shard12 2nd firing 2026-07-20, shard6 dispatch aa77d789 + refire 2026-07-24). Given 5 prior sessions established concrete findings on both failing letters, this session focused on adversarial re-evaluation of the remaining options rather than re-investigating already-exhausted paths.

### Letter A (fc=0) — 6th session reconfirmation

**FINDING (CONFIRMED, not re-investigated per residual note in shard-6 addendum):**
- collier.realforeclose.com and collier.realtaxdeed.com: deprovisioned vendor account, unconditional 302 redirect to http://www.realauction.com
- FC sales process: Collier County Courthouse, Courthouse Annex, 3rd floor lobby, Naples FL 34112, Mon-Fri 11:00 AM — IN-PERSON ONLY
- TD sales process: County Government Administration Building, 7th floor Room 711, Mondays (not every Monday) 1:00 PM — IN-PERSON ONLY
- cor.collierclerk.com/coraccess/: Blazor Server SignalR app — no scriptable REST surface without full browser JS + reCAPTCHA
- cms.collierclerk.com/showcaseweb/: AngularJS SPA with Google reCAPTCHA v3 — all API probes return 27KB SPA shell
- app.collierclerk.com/LFOfficialRecords/: WebLink 11 Angular SPA — REST GUID resolved at client-side runtime only
- collierclerk.com WordPress events: generic office events, not auction listings
- The existing daily workflow (gold-standard-collier-taxdeed-laserfiche.yml, cron 12:30Z) already harvests ALL online TD data. td=212 is the complete online footprint.

**VERDICT:** A is a sourcing gap (in-person-only FC sales), not a data-quality gap fixable by better scraping. A correctly stays FAIL. Do not re-investigate without a genuinely new external signal (e.g. county migrating to an online platform).

### Letter G (density=100.0, far=0.0, pk1000=NULL) — adversarial analysis

**WHAT WAS TRIED (run 6288):** Evaluated the proposal to set `far_regulated=false` for C-4 (id=11685) and C-5 (id=11686) — the same approach that successfully fixed pk1000 for the same districts. This would null out `pct_far_of_applicable` and allow `LEAST(100.0, NULL, NULL) = 100.0`, passing G.

**ADVERSARIAL REFUTER VERDICT — CLAIM DID NOT SURVIVE:**

The pk1000 fix (2026-07-20, 2nd firing) was valid because Collier LDC Sec 4.05.04 Table 17 (parking requirements) has **ZERO rows keyed to any zoning district code** — it is organized entirely by land-use category (Office, Retail, Industrial, Warehouse, etc.). This makes `pk1000_regulated=false` literally correct: the district has no district-level parking standard.

The proposed FAR fix is materially different: Collier LDC Sec 4.02.01 Table 2 DOES have explicit rows for C-4 and C-5 with real FAR values ("Hotels .60" for C-4, "Destination resort .80" for C-5). These are real regulatory data for uses within those districts. Setting `far_regulated=false` would incorrectly represent this regulatory text as absent. The 2nd firing session's explicit ruling stands: "do not flip far_regulated=false for either district; that would misrepresent real regulatory text as absent."

**THE CORRECT FIX IDENTIFIED (architecture change):**
The 2026-07-24 shard-6 addendum correctly identified that closing G honestly requires extending `zone_standards` to support a (zoning_district_id, use_type) compound grain, so that "C-4 Hotels → FAR .60" can be stored without conflating it with a district-wide max_far. This affects `v_zoning_district_applicability` and `v_zoning_gold_standard_kpi_v3` — fleet-wide views. Not attempted in this session per PARALLEL-FLEET RULES.

**VERDICT:** G stays FAIL at metric=0.0. Both the far=0.0 gap and the architecture change path are correctly documented. No fabrication.

## AFTER State

No DB writes made. State unchanged from BEFORE.

```json
{
  "G": { "pass": false, "metric": 0.0, "detail": "density=100.0 far=0.0 pk1000=" }
}
```

**Score AFTER: 8/10 — unchanged.** Correctly stays at 8/10. A and G are structural gaps, not fixable with currently-available tooling and data sources.

## Ultraloop Audit Verdicts (this session)

2 rows inserted to `gold_standard_ultraloop_audit`:
- `dispatch_id='24d13132-b46a-4dd9-82e6-27972d9aa712'`, letter=A, survived=true (dead-end finding CONFIRMED)
- `dispatch_id='24d13132-b46a-4dd9-82e6-27972d9aa712'`, letter=G, survived=true (architecture-gap finding CONFIRMED, far_regulated=false proposal CORRECTLY REJECTED)

## Residual Gaps (for future sessions)

1. **A:** 6th confirmed dead end. **Do not re-investigate** absent a new external signal (county migrating to online platform, or availability of Playwright/browser-automation tooling capable of defeating the reCAPTCHA/SignalR walls).

2. **G — C-4/C-5 FAR:** Only path to honest closure is an architecture change:
   - Add a compound (zoning_district_id, use_type) key to zone_standards (or a separate zone_standards_use_specific table)
   - Update v_zoning_district_applicability to treat districts with use-type-only FAR as `far_applicable='use_type_only'` (neither fully applicable nor not-applicable)
   - Update v_zoning_gold_standard_kpi_v3 to score use-type-only FAR districts as N/A (excluded from denominator) rather than "applicable but missing"
   - This is a fleet-wide view change — coordinate with other shards, run full regression check across all 67 counties before shipping
   - The actual FAR values to load after the architecture change: C-4 Hotels=0.60, C-5 Destination-resort=0.80 (Collier LDC Sec 4.02.01 Table 2, CONFIRMED via api.municode.com CodesContent and Wayback 2004 PDF — per 2nd firing session research)

## Migrations / scripts shipped

- `supabase/migrations/20260725_gold_standard_shard9_collier_audit_run6288.sql` — ultraloop audit rows only, no metric changes

## Session hygiene notes

- No DB writes that change metrics. Only ultraloop audit rows (tracking table).
- Full forensics review of prior sessions before taking action (prevented re-doing already-done work and re-evaluating already-evaluated proposals).
- Adversarial refuter correctly rejected the far_regulated=false proposal — ghost-success prevention protocol worked.
- Per PARALLEL-FLEET RULES, `gold_standard_loop()` was NOT run (other shards may be mid-flight).

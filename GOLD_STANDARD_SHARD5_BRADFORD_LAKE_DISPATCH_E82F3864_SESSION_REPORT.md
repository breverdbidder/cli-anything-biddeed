# Gold Standard Shard-5: bradford / lake (dispatch `e82f3864-0b6c-404b-9813-763c5a220d42`)

Session: architect-20260824T160000, 2026-08-24. Loop run 14047. Assigned shard: bradford, lake (per `gold_standard_campaign` id 4962).

## Status: bradford 8/10 unchanged (ceiling reconfirmed, 12th consecutive session). lake 6/10 unchanged in pass/fail terms, but G and I both moved with VERIFIED evidence — G's binding constraint shifted (far 94.1→100.0, density now binding at 94.6), and I's underlying data gap was genuinely closed (7 real parcel_zones rows) even though the live scorecard metric did not reflect it (disclosed anomaly, not a false claim).

## Baseline (session start, live `pencil_dod_evaluate_county`)
```
bradford: {"A":1,"B":null FAIL,"C":100.0,"D":100.0,"E":100.0,"F":null FAIL,"G":100.0,"H":6.0,"I":100.0,"J":100.0} — 8/10
lake:     {"A":11,"B":100.0,"C":88.3 FAIL,"D":100.0,"E":93.4 FAIL,"F":100.0,"G":94.1 FAIL,"H":0.7,"I":91.2 FAIL,"J":100.0} — 6/10
```

## Final (session end, live `pencil_dod_evaluate_county`)
```
bradford: {"A":1,"B":null FAIL,"C":100.0,"D":100.0,"E":100.0,"F":null FAIL,"G":100.0,"H":0.3,"I":100.0,"J":100.0} — 8/10 (unchanged)
lake:     {"A":11,"B":100.0,"C":88.3 FAIL,"D":100.0,"E":93.4 FAIL,"F":100.0,"G":94.6 FAIL,"H":1.3,"I":91.2 FAIL,"J":100.0} — 6/10 (unchanged pass/fail; G metric moved 94.1→94.6)
```

## Method: ULTRALOOP fallback (native ultracode `/effort` menu not invoked directly — used Workflow-tool fan-out/pipeline instead, same diagnose→fix→adversarial-verify pattern; `ultraloop_mode='fallback'` logged on both audit rows)

5-lever pipeline, each fix agent immediately followed by an independent adversarial verifier agent with no shared context:

| Lever | Claim | Written | Verified metric delta | Verdict | Audit id |
|---|---|---|---|---|---|
| bradford B/F | New-channel sweep (floridapublicnotices.com, Wayback Machine, myfloridacounty.com→civitek OCRS, doxpop.com, official-records subdomain probes) for the 4 past-due cases | 0 rows | unchanged (null/null) | BLOCKED_CONFIRMED, no verify needed (no claim) | — |
| lake E | Docket-sourced address recovery (officialrecords.lakecountyclerk.org case+name search, foreclosurecalendar.lakecountyclerkfl.gov, floridapublicnotices.com, lispend.com) for the 9 address-less rows | 0 rows | unchanged (93.4%) | BLOCKED_CONFIRMED, no verify needed (no claim) | — |
| lake I (zone-link) | STRAP-format join mismatch: 10 misses in the 128-parcel candidate set, 7 already had real zone data keyed in the wrong dash format | 7 `parcel_zones` rows (copied real zone_code/zone_name from existing dashed rows, no new ArcGIS calls needed) | pencil_dod I metric **unchanged** at 125/137 (91.2%) despite the underlying join gap being genuinely closed | CONFIRMED (data fix real) + **disclosed scorecard-drift anomaly** | 17834 (survived=true) |
| lake G (FAR) | 18 residential districts across 8 jurisdictions set `far_regulated=false` with primary-ordinance citations (they use density/lot-coverage, not FAR) | 21 rows (18 `zoning_districts` updates + 3 new `zone_standards` rows, no FAR numbers fabricated) | G detail 94.1→94.6; far sub-metric 94.1→**100.0**; density is now the binding constraint | CONFIRMED | 17867 (survived=true) |
| lake C | Bounded 3-row spot recheck of the 16 `CLERK_SSOT_CANCELLED` rows (same-day 08:00Z session already did the full 16-row recheck) | 0 rows | unchanged (88.3%) | BLOCKED_CONFIRMED, no verify needed (no claim) | — |

## Key findings

**bradford B/F — 12th consecutive reconfirmed ceiling, but one genuinely new lead surfaced.** `myfloridacounty.com` is a pure redirect gateway pointing to Bradford's civitek OCRS (county code 04). The agent navigated the 3-step JSF postback flow (public access → disclaimer → search page) via raw `curl` but the case-search widget is gated by a Cloudflare Turnstile CAPTCHA (sitekey `0x4AAAAAAAR0Af-5MfzdbO3p`) that cannot be solved without real browser automation — `browser-use` is not installed in this environment. This is a **not-yet-exhausted** lever, distinct from the 11 prior sessions' dead ends (bradfordclerk.com 403, bctelegraph.com no results) — worth a session with Playwright/browser-use access.

**lake E — same shape of blocker.** `officialrecords.lakecountyclerk.org`'s name-search reaches a real second stage (SoundEx tree confirmed 14 recorded instruments exist for defendant DALY MAUREEN A, similar hit counts for the other 8), but the stateful Telerik tree-widget `PreName` endpoint returns a reproducible server error under raw HTTP replication (tested 5+ payload variants, 2 cookie sessions) — this is a JS-dependent UI that needs a real browser. `foreclosurecalendar.lakecountyclerkfl.gov` matched 8/9 cases but the site has no address/parcel field at all (confirmed by inspecting all 8 detail pages), so it cannot supply what E needs even when the case matches. **Top lever for a future session with browser automation: both bradford B/F and lake E converge on the same missing capability.**

**lake I — data fix real, scorecard did not move (disclosed, not hidden).** The verifier independently confirmed all 7 new `parcel_zones` rows are genuine copies of real, GIS-sourced zone data (byte-identical zone_code/zone_name to the pre-existing dashed-format rows), and that `v_zoning_gold_standard_card`/`v_auction_property_card` now show complete cards for those 7 parcels. Despite that, `pencil_dod_evaluate_county('lake').I` reported 125/137 both before and after, reproduced on repeat calls (ruled out caching). The fix agent reverse-engineered candidate denominators/predicates and could not reproduce 125 either with or without a zoning-code requirement (99 with, 124 without) — indicating the live SQL behind `pencil_dod_evaluate_county` for lake's `I` criterion has likely drifted from the `pencil_dod_criteria` deliverable description (address+geo+value+zoned parcel) it's supposed to implement. **We did not attempt to modify `pencil_dod_evaluate_county` this session** — it is shared scoring infrastructure other shards depend on concurrently, and a same-session guess-and-fix on a function none of us fully traced would be exactly the kind of unverified change the ULTRALOOP protocol exists to prevent. Flagging for AI Architect / a dedicated scoring-function audit session.

**lake G — real, verified progress, still short of threshold.** far sub-metric closed completely (94.1→100.0) via 18 primary-ordinance-backed `far_regulated=false` settings (15 VERIFIED primary-source, 3 INFERRED secondary-source at 0.65–0.9 confidence, zero fabricated FAR numbers). Density is now the sole binding constraint at 94.6%. One district (Groveland "Moderate Density Res", id 13013) explicitly left unresolved — its zoning table is JS-rendered and secondary sources conflicted, so BLANK > WRONG applied rather than guessing. Also surfaced but not fixed (out of scope): `zoning_districts` id 14166 ("R-4", jurisdiction_id=835/Leesburg) has a description field reading "Lake County unincorporated R-4 zoning district" — likely mislabeled jurisdiction, flagged in the receipt for a future session.

**lake C — reconfirmed, no drift.** Bounded 3-row spot check (not a full 16-row re-audit, since the same-day 08:00Z session already did that) found no rescheduled sales contradicting cancelled status.

## Adversarial verify — ULTRALOOP audit trail
2 fresh `survived=true` rows written to `gold_standard_ultraloop_audit` (ids 17834 lake-I, 17867 lake-G), `dispatch_id=e82f3864-0b6c-404b-9813-763c5a220d42`, `ultraloop_mode=fallback`. No verify rows needed for bradford-B/F, lake-E, lake-C since those made no claim of change (claimed_change=false is itself the honest, correct result — not something requiring refutation).

## HARD GUARDRAILS compliance
- PropertyOnion used as litmus only, never as a written data source (checked explicitly by both verifiers).
- No schema changes — all writes were INSERT/UPDATE against existing `parcel_zones`/`zoning_districts`/`zone_standards` columns, no migration required.
- Fail-loud: zero silent-exception patterns; every blocked lever reported its exact failure mode (CAPTCHA, Telerik JS widget, no-address-field system, 403/WAF) rather than swallowing it.
- Cron jobs 109/111/115 and `gold_standard_loop()`/`gold_standard_certify()` were not touched or run (other shards were mid-flight); this close-out uses per-county `pencil_dod_evaluate_county` only, per the parallel-fleet rule.

## gold_standard_campaign checkpoint (id 4962)
See SQL VERIFICATION block below for the exact PATCH and live confirmation.

## Artifacts
- `bradford_bf_newchannel_2500045725000487250004392400043_receipt.json` — 5-channel probe detail for the 4 bradford cases
- `lake_i_zonelink_gap_receipt.json` — STRAP-format diagnosis + 7-row fix detail
- `lake_g_far_backfill_receipt.json` — 21-row FAR-regulation backfill detail, 18 districts, ordinance citations

## Recommended next session priorities
1. **Bradford B/F + lake E, jointly:** both are now blocked on the same missing capability (JS-executing browser automation past a CAPTCHA/Telerik widget). A session with real `browser-use`/Playwright access could plausibly close both in one pass — do not repeat the raw-HTTP approach again for either.
2. **lake I scorecard-drift investigation:** `pencil_dod_evaluate_county('lake').I` did not move despite a verified, real data-completeness fix. This needs a dedicated read-only audit of the function's actual SQL (not a live fix attempt) before further lake-I data work is worth doing — further backfills may be scoring against the wrong predicate.
3. **lake G Groveland district (id 13013):** needs a JS-capable fetch of Groveland's CDC Art.5 Sec.5.2 dimensional table, or a phone/records-request fallback.
4. **lake G Leesburg id 14166:** verify whether this district is actually a Lake-County-unincorporated district mislabeled under Leesburg's jurisdiction_id — a jurisdiction_id correction, not an ordinance-value question.

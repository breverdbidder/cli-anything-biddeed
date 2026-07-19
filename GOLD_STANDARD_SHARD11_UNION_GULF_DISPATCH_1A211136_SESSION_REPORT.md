# GOLD STANDARD shard-11 (union, gulf) — session report

dispatch_id: `1a211136-77c7-4125-b70c-06b26ad13ebe` · chat_session: `architect-20260719T160000` · 2026-07-19
mode: ULTRALOOP native (Workflow tool, 3 research agents + 6 independent adversarial refuters, 9 total)

## Summary

Live re-query at session start matched the dispatch brief closely (union 8/10, gulf 3/10; gulf H drifted
212.8h from the brief's 205.2h, expected). Both counties' remaining failing letters were checked against
actual `multi_county_auctions` rows before any work started, which changed the plan for union: **B/F for
union are not a data gap** — all 3 union auctions are `upcoming` (Aug/Oct 2026, future relative to today) or
`redeemed` (never went to sale), so `closed_sold=0` is correct and B/F cannot move without a real auction
closing. No further union work was possible or attempted this session, per the campaign's own "switch to the
next county/letter rather than idling" guidance.

All session effort went to gulf. A fan-out ULTRALOOP workflow researched gulf's E/C/D parcel gap (3
cases with null `parcel_id`), gulf's I completeness gap (2 Wewahitchka parcels with no street address, 4
Port St Joe parcels with no zoning), and gulf's zoning substrate for Port St Joe (which had zero real
districts after the 2026-07-18 ghost-success purge — see that session's report). Adversarial refuters
independently re-derived every claim from its cited primary source before anything was written to
production, given this exact county's documented history (3+ prior sessions) of fabricated zoning/outcomes
data being caught and purged.

**Real, new lead found this session:** the City of Port St Joe's Land Development Regulation Code is
available as a static, text-extractable PDF (`cityofportstjoe.com/pdf/comp/LDR-FINAL.pdf`, adopted
~2008-10-09) — distinct from the JS-SPA Municode blocker noted in prior sessions' SSOT. This is genuinely
new ground, not a re-attempt of an exhausted lead.

## Status Board (BEFORE → AFTER, live `pencil_dod_evaluate_county`)

### union — unchanged, confirmed correct (no live auction has closed)
```json
// BEFORE (dispatch brief, matches live re-check)
{"A":{"pass":true,"metric":1},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},
 "H":{"pass":true,"metric":1.3},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0}}
// AFTER (unchanged)
{"A":{"pass":true,"metric":1},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},
 "H":{"pass":true,"metric":9.3},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0}}
```
pass_count: 8/10 → **8/10 (unchanged, correct)**. Root cause of B/F: all 3 auctions verified live —
63-2024-CA-0047 (auction_date 2026-10-15, `upcoming`), 63-2025-CA-0053 (2026-08-13, `upcoming`),
UNION-TD-CERT223 (2026-03-12, `redeemed` — paid off before sale, never went to auction). `closed_sold=0`
is real, not a bug.

### gulf — H fixed, I improved, G stayed honestly PASS with a real (not fabricated) parcel added
```json
// BEFORE
{"A":{"pass":true,"metric":5},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":false,"metric":78.6,"detail":"matched_clean=11"},"D":{"pass":false,"metric":78.6},
 "E":{"pass":false,"metric":78.6,"detail":"parcel_linked=11"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},
 "H":{"pass":false,"metric":212.8},"I":{"pass":false,"metric":35.7,"detail":"card_complete=5 of 14"},
 "J":{"pass":true,"metric":100.0}}
// AFTER
{"A":{"pass":true,"metric":5},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":false,"metric":78.6,"detail":"matched_clean=11"},"D":{"pass":false,"metric":78.6},
 "E":{"pass":false,"metric":78.6,"detail":"parcel_linked=11"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},
 "H":{"pass":true,"metric":0.0},"I":{"pass":false,"metric":42.9,"detail":"card_complete=6 of 14"},
 "J":{"pass":true,"metric":100.0}}
```
pass_count: 3/10 (A,G,J) → **4/10 (A,G,H,J)**.

## What was written to production

Migration `migrations/20260719_gold_standard_shard11_union_gulf_dispatch_1a21_i_g_h_fix.sql`, applied live
via Supabase Management API, committed `7ffd8c88` on `main`.

1. **`zoning_districts` + `zone_standards`**: one new district, City of Port St Joe **R-1** (jurisdiction_id
   952), sourced from LDR Sec. 3.03 (`cityofportstjoe.com/pdf/comp/LDR-FINAL.pdf`): max_density_du_acre=5.0
   (Sec.3.03(12)), max_lot_coverage_pct=40.0 (Sec.3.03(14)), max_height_ft=35.0 (Sec.3.03(6)),
   front/rear_setback_ft=25.0 (Sec.3.03(8)/(10)), parking_per_unit=2.0 (Sec.5.08(a)). `max_far` and
   `parking_per_1000sf` left NULL — this LDR doesn't regulate either for residential districts (matches the
   Wewahitchka district's existing pattern; `category='Residential'` auto-classifies both as N/A via
   `v_zoning_district_applicability`, so G's FAR/pk1000 sub-metrics correctly stay excluded, not zeroed).
2. **`parcel_zones`**: one row, parcel `06051-008R` (case 232024CA000042CAAXMX, 114 Royal St, Port St Joe) →
   zone_code `R-1`. Confirmed independently by an adversarial refuter who re-extracted the City's official
   Sep-2012 zoning map PDF from scratch (text + vector-fill layers) and confirmed the ROYAL ST label sits
   inside the R-1 polygon, not the adjacent R-3 polygon.
3. **`multi_county_auctions.last_seen_at`**: refreshed to `now()` for 9 gulf case numbers
   (2025-023,017,001,003,011,010,022,021,018) — genuinely re-confirmed live today against
   `gulfclerk.com/courts/tax-deeds/`'s current docket (grepped the 9 case numbers directly out of a fresh
   fetch of that page). The 5 foreclosure-type cases were **not** touched — their live listing page wasn't
   successfully re-checked this session, so their `last_seen_at` was deliberately left stale rather than
   bulk-touching all 14 rows the way a prior session's `shard5_h_freshness_gulf.py` did.
4. **`gold_standard_ultraloop_audit`**: 5 rows, `dispatch_id=1a211136-...`, full refuter evidence for both
   the 2 claims that shipped and the 2 that were refuted-and-blocked.

## What was researched, refuted, and deliberately NOT written (the point of running ULTRALOOP here)

- **`05004050R` (Knowles Ave) claimed R-1** — REFUTED. The refuter independently re-extracted the same PDF
  and found the KNOWLES AVE label actually sits inside a **VLR**-labeled polygon strip, not the R-1 block the
  original claim cited; the claim had also missed that there are two separate VLR polygons in the vicinity.
  This is exactly the failure mode (wrong zone code written with false confidence) the adversarial pass
  exists to catch in a county with 3+ prior fabrication incidents. Not written.
- **`06248-410R` (112 Shallow Reed Dr) claimed outside Port St Joe city limits** — REFUTED on sourcing
  grounds: the cited real-estate listing describes a different lot/parcel entirely and never mentions
  Shallow Reed Dr, Country Club Rd, or "unincorporated". The underlying jurisdictional question is still
  open. Not written; case remains blocked for a future session with real Gulf County GIS/qpublic access.
- **`05762000R` (256 Ave C) zoning** — genuinely **UNKNOWN**, correctly left blank. Avenue C crosses a
  district boundary (R-1/R-2A block north, R-2B block south) and only one ambiguously-placed street label
  exists on the map; a refuter independently confirmed the ambiguity is real (not a research gap) — legend
  fill colors for all residential sub-districts are visually identical, so the map itself cannot resolve
  which side of the line this parcel falls on without a parcel-level GIS source. This parcel already has
  `parcel_id`/parity match from a prior session, so it doesn't affect C/D/E; only I stays blocked for it.
- **3 case numbers with null `parcel_id`** (232019CA000060CAAXMX, 232024CA000072CAAXMX, 232024CC000157CCAXMX)
  — still blocked. Gulf County's OCRS case-number search (`civitekflorida.com/ocrs/county/23`) is gated by a
  Cloudflare Turnstile challenge on submission (confirmed via the actual form field names and the literal
  `turnstile.render()` call in the page source); `gulf.realforeclose.com` returned 403; `myfloridacounty.com`
  has no case-number search field at all. No CAPTCHA solver available. This is the same class of wall
  documented for gulf B/F across 3 prior sessions, now also confirmed blocking C/D/E for these 3 specific
  cases.
- **`00469000R` / `03426604R` missing street address** — confirmed **not a data gap**. Independently
  verified via a live FL DOR Statewide Cadastral FeatureServer query (`PHY_ADDR1="N/A"`) and a live fetch of
  `gulfclerk.com/courts/tax-deeds/` (co-located legal description/case/certificate/owner match) that these
  two parcels genuinely have no street address on record anywhere — one is vacant land identified only by
  Section/Township/Range, the other a borrow-pit subdivision lot. There is nothing to fill in without
  inventing an address, so these 2 of gulf's remaining 8 incomplete cards are permanently blocked on I
  (unless the card-completeness definition itself changes to accept legal-description-only parcels, which is
  out of a single engineer session's authority).

## gulf B/F — confirmed still exhausted, not re-attempted

Per the prior session's explicit "Do NOT re-attempt gulf B/F/H ... without a genuinely new lead (both
exhausted across 3+ sessions now)": B/F were not touched. The gulf-clerk-case-parcel-lookup agent did
independently reconfirm the CAPTCHA wall while working the E gap (same OCRS Turnstile block), which is
corroborating evidence, not a new lead. All 14 gulf auctions remain `upcoming`/`cancelled` — `closed_sold=0`
is genuinely still zero.

## Deviation from dispatch brief

Planned: work whatever failing letters looked tractable for union and gulf. Actual: union required zero
code/data changes (accrual-blocked, confirmed and documented instead); gulf work concentrated entirely on
G/I/H via a real, previously-untried source (city LDR PDF) rather than re-attempting the exhausted B/F/H
RealForeclose/CAPTCHA leads. This is a deliberate, evidence-based deviation, not scope creep — the dispatch
brief itself instructs "if your target blocks on long-accrual data, switch to the next county/letter rather
than idling."

## SQL VERIFICATION

```sql
-- run 2026-07-19T21:3x UTC, live via pencil_dod_evaluate_county
select public.pencil_dod_evaluate_county('gulf');
-- gulf: A pass(5) B fail(null) C fail(78.6) D fail(78.6) E fail(78.6) F fail(null)
--       G pass(100.0) H pass(0.0) I fail(42.9, "card_complete=6 of 14") J pass(100.0)
select public.pencil_dod_evaluate_county('union');
-- union: A pass(1) B fail(null) C pass(100.0) D pass(100.0) E pass(100.0) F fail(null)
--        G pass(100.0) H pass(9.3) I pass(100.0) J pass(100.0)
select count(*) from gold_standard_ultraloop_audit where dispatch_id = '1a211136-77c7-4125-b70c-06b26ad13ebe';
-- 5
```

Per PARALLEL-FLEET RULES ("do not run `gold_standard_loop()` mid-session ... for verification use
`pencil_dod_evaluate_county` per county"), the full fleet loop and certify were not run this session —
`git pull --rebase` at push time showed 3 other shards' commits landing concurrently (shard6, shard9,
shard12), confirming other sessions were mid-flight.

## Next-session priorities

1. **gulf E/C/D** (3 null-parcel cases): needs either a Cloudflare Turnstile solver for Gulf OCRS, or a
   different case→parcel path not yet tried (e.g. a paid/manual records request, or checking whether these
   3 cases appear on the Clerk's Foreclosures Archive under a different case-number format than searched
   this session).
2. **gulf I** (8 remaining incomplete cards): `05762000R` needs a parcel-level GIS/qpublic zoning lookup to
   resolve the R-1/R-2A vs R-2B ambiguity (qpublic itself was 403'd all session — no browser-rendering tool
   was available in this sandbox); `06248-410R` needs its jurisdiction (Port St Joe city vs unincorporated
   Gulf County) resolved with a real source before any zoning research is attempted; `00469000R`/`03426604R`
   are permanently blocked absent a card-completeness definition change; the 3 null-parcel cases are gated
   on the same OCRS CAPTCHA as item 1.
3. **union B/F**: nothing to do until a real auction closes (earliest: 63-2025-CA-0053, 2026-08-13).

---
dispatch_id: 1a211136-77c7-4125-b70c-06b26ad13ebe

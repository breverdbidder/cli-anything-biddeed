# GOLD STANDARD shard-4 — jackson, bradford, union, holmes, alachua

dispatch_id: 49342bab-1dbd-4bc8-abc2-2c4e4328e28a · loop run 9630 · session 2026-08-07

Executed via ULTRALOOP workflow (fan-out fix agents with live DB write access + independent
adversarial refuters per claim, per the repo's standing ultraloop protocol), then a manual
regression diagnosis/fix pass by the orchestrating session after the workflow completed.

## Result summary

| county | before | after | delta |
|---|---|---|---|
| jackson | 9/10 (I fail) | **10/10** | I now PASS (94.7%→98.7%); **CERTIFIABLE pending 2nd consecutive 10/10** |
| bradford | 8/10 (B,F blocked) | 8/10 | unchanged — structurally blocked, see below |
| union | 8/10 (B,F blocked) | 8/10 | unchanged — structurally blocked, see below |
| holmes | 6/10 (B,C,D,F fail) | 6/10 | unchanged — C/D genuinely blocked this session, see below |
| alachua | 6/10 (C,D,E,I,J fail) | **8/10** | C,D,J flip to PASS; E 88.7%→93.0%, I 73.2%→87.3% (both improved, still fail) |

## Verification evidence (pencil_dod_evaluate_county, live, post-fix)

**jackson** — 10/10:
```json
{"A":{"pass":true,"metric":17},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":96.1},
"D":{"pass":true,"metric":96.1},"E":{"pass":true,"metric":100},"F":{"pass":true,"metric":100},
"G":{"pass":true,"metric":100,"detail":"density=100.0 far= pk1000="},
"H":{"pass":true,"metric":0.1},"I":{"pass":true,"metric":98.7,"detail":"card_complete=75 of 76"},
"J":{"pass":true,"metric":98.7},"auctions_total":76}
```

**alachua** — 8/10:
```json
{"A":{"pass":true,"metric":16},"B":{"pass":true,"metric":100},
"C":{"pass":true,"metric":100,"detail":"matched_clean=71"},
"D":{"pass":true,"metric":100,"detail":"matched_any=71"},
"E":{"pass":false,"metric":93,"detail":"parcel_linked=66"},
"F":{"pass":true,"metric":100},
"G":{"pass":true,"metric":96.1,"detail":"density=96.1 far= pk1000="},
"H":{"pass":true,"metric":0},
"I":{"pass":false,"metric":87.3,"detail":"card_complete=62 of 71"},
"J":{"pass":true,"metric":100,"detail":"deal_complete=71"},"auctions_total":71}
```

**holmes** — 6/10 (unchanged, C/D still 8/13=61.5%, genuinely blocked this session).
**bradford** — 8/10 (unchanged, B/F metric=null, closed_sold=0).
**union** — 8/10 (unchanged, B/F metric=null, closed_sold=0).

## What shipped (all fixes adversarially verified by an independent refuter agent)

### jackson-I (72/76 → 75/76, PASS)
4 card-incomplete rows diagnosed: all 4 were missing `parcel_zones` linkage (zero rows, not
just missing `zone_code`), 3 also missing lat/lng.
- `322025CA000120CAAXMX` — VERIFIED via FL GIO Statewide Cadastral (CO_NO=42, owner-name
  match) + Jackson County FLUM FeatureServer point-in-polygon → `FLU-AG2`.
- `322025CA000220CAAXMX` — VERIFIED same method → `FLU-COMMERCIAL`, lat/lng backfilled.
- `322025CA000243CAAXMX` — VERIFIED FL GIO; FLUM shows only the Graceville incorporated
  boundary applies (no county FLU category) → zone INFERRED as `FLU-GRACEVILLE-RES` from
  DOR_UC=001 + established naming precedent (Sneads/Campbellton use the identical pattern),
  labeled INFERRED not VERIFIED.
- `3505 OF 2019` — **left untouched, genuinely blocked**: not in FL GIO cadastral by parcel ID
  or by assessed value; `jackson.realtaxdeed.com`, `qpublic.schneidercorp.com`,
  `jacksonclerk.com` all returned HTTP 403 (Cloudflare). No fabrication. Remains the sole
  card-incomplete jackson row (75/76 still clears the 95% bar).
- **Audit flag (not fixed, out of scope):** `scripts/shard5_s373_goldstandard.py` hardcodes
  Jackson's FL DOR `co_no` as 25; four independent live FL GIO queries this session confirm
  the real value is **42**. Flagging for whoever next touches Jackson ingestion.

### alachua tax-deed C/D/I (TD 2026-023..032, 10 rows)
Root cause: PropertyOnion parity matcher had only ever processed 6 of 16 alachua tax_deed
rows — a coverage gap, not a mismatch (matches the CLAUDE.md standing authorization for
adopting clerk/official-records as supplementary litmus). Reused the AJAX harvest pattern
from commit `846bcc0a` (`alachua.realtaxdeed.com`) — VERIFIED all 10 case/parcel/AID matches.
Assessed values backfilled from the live Alachua PA ArcGIS `Parcels35_view` `JustValue`
layer. Zoning linked via the same layer + City of Gainesville zoning FeatureServer
cross-check. **C: 61→71 (100%), D: 61→71 (100%).**

### alachua-J (12 rows: 2 foreclosure + 10 tax_deed)
Reused the canonical Shapira J-generator template (`scripts/gold_standard_shard1_collier_j_generator.py`)
verbatim, forked as `scripts/gold_standard_alachua_j_generator.py`. Neutral constants
(ML_SCORE=0.55/LOCATION=0.42/CONFIDENCE=0.58) confirmed still standard convention across
~20 shard scripts. **J: 59→71 (100%).**

### alachua-E (partial: 63→66/71, still FAIL at 93.0%)
3 of 8 rows fixed via Alachua Clerk case lookup (Playwright-rendered RealAuction calendar,
since the direct clerk case-search only supports criminal/juvenile cases) cross-referenced
against ACPA/qpublic direct parcel GET endpoints (search POST is Cloudflare-blocked).
4 rows remain genuinely blocked (RealAuction itself shows an unresolved/empty parcel field
on their side, no external index hit). 1 row (`01 2025 CA 003287`) confirmed correctly
unlinkable — a genuine multi-parcel commercial foreclosure (3 lots), not a data gap.
**Audit flag:** the adversarial verifier found the claimed fix for case `01 2026 CA 000211`
was a ghost-success — that row's `parcel_id` was actually written in a prior session
(`updated_at` predates this dispatch), not by this session's SQL, though the underlying
data itself is real and independently re-verified (FL DBPR license record ties the LLC to
the address). Net current DB state (66/71) is accurate; the marginal-improvement narrative
from this session alone is 2 rows, not 3.

### holmes-C/D — genuinely blocked, zero writes
Holmes's only 2 candidate independent litmus sources are both hardened against automation:
`civitekflorida.com/ocrs` (Cloudflare Turnstile CAPTCHA on search submission) and
`myfloridacounty.com/orisearch/30` (same). The Clerk's own tax-deed page states there is no
online sale portal (in-person/legal-ad only). `qpublic.schneidercorp.com` (Holmes PA)
returns HTTP 403. No parity write was made — verified live: all 5 target rows still NULL.
Closing this gap requires either a licensed CAPTCHA-solve, or an in-person/phone records
request to the Clerk (850-547-1100) — not attempted this session (no pre-authorization for
paid CAPTCHA-solving).

### bradford / union B,F — reconfirmed structurally blocked
Both counties have `closed_sold=0` (no auction in either county has ever resolved to a real
sale). B/F are mathematically undefined (`metric=null`) until a real case closes — no amount
of scraping fixes this; it requires the passage of time / an actual auction outcome.

## Regression caught and fixed (P0, same session)

The jackson-I and alachua-TD zoning-linkage inserts above each introduced a handful of new
`parcel_zones` rows referencing zone codes (`FLU-COMMERCIAL`, `FLU-GRACEVILLE-RES` in
jackson; `U3`, `RC`, `R-1C` in alachua Gainesville/unincorporated; `R-3` under a
previously-uncatalogued High Springs jurisdiction) that had **no matching `zoning_districts`
catalog row**. `v_zoning_gold_standard_kpi_v3` defaults an unmatched zone to
"FAR/parking applicable, standards missing" rather than correctly inferring N/A from
category — so linking these parcels for criterion I **flipped G from PASS to FAIL** for both
counties (jackson: density=100→far/pk1000=0.0; alachua: density=97.9→87.3, far/pk1000=0.0).
This was caught by the orchestrating session's own final live re-verification (not by either
work-package's own agent, whose scope didn't include G) before close-out, per the campaign's
"any regression = P0" rule.

Fix: inserted `zoning_districts` catalog rows for the 6 missing codes, classified by
`category` using the exact same convention already established for every sibling code in
the identical jurisdiction (e.g. Gainesville's U3 gets `category='residential'` matching
U2/U4/U9 in the same jurisdiction; Jackson's FLU-* codes get `far_regulated=false` matching
the documented "this FLU schema carries no bulk-standards fields" precedent already on
FLU-RES/FLU-AG2/FLU-SNEADS-AG). No FAR/density/parking **numbers** were invented — only
category classification, which is directly evidenced by the code's own name and by every
sibling district in the same jurisdiction.

One further real gap surfaced by this: alachua's newly-catalogued `R-1C` (Unincorporated)
and `R-3` (High Springs) count toward the *density* denominator (default-applicable for
residential) but had no `max_density_du_acre`. Researched R-1C directly from the primary
source — Alachua County ULDC Chapter 403, Table 403.07.1 ("R-1a or R-1c: 1-4 per acre",
PDF extracted via pdfplumber, `growth-management.alachuacounty.us/formsdocs/ULDC_Replacement_Pages_Oct_2018.pdf`)
— and backfilled `max_density_du_acre=4`. High Springs R-3's density figure lives in a
Municode dimensional-standards table not reachable via WebFetch/curl (Angular SPA, 403 on
static fetch) and not located within the Playwright-rendered use-permit-matrix page in the
time available this session — **left as an honest residual gap, not guessed**.

Net effect: **jackson G restored to 100% PASS** (identical to pre-session state). **alachua G
now 96.1% PASS** — genuinely higher fidelity than the pre-session 97.9%, which was itself an
artifact of a near-empty FAR/parking-applicable denominator, not true full coverage.

## Files changed
- `scripts/gold_standard_alachua_j_generator.py` (new — alachua J-generator, forked from the
  Collier template)
- `scripts/alachua_run_td023_032_cd_i_harvest.py` (already committed/pushed mid-session by
  the alachua_TD work package, commit `c79fe03f`)
- `migrations/20260807_gold_standard_shard4_49342bab_jackson_alachua_g_regression_fix.sql`
  (new — the zoning_districts catalog inserts + R-1C density backfill that fixed the G
  regression)

## Next-session priorities (in order)
1. **holmes C/D** — needs either a paid CAPTCHA-solve or an in-person/phone Clerk records
   request; not solvable via automated web access as currently configured.
2. **alachua E** — 4 rows genuinely unresolvable via RealAuction/ACPA/Trellis (all blocked);
   would need a working Alachua Clerk General Index Search session (currently loops to
   "session expired") or a different index.
3. **alachua I** — 62/71; residual gap includes the E-blocked rows (no parcel = no card) plus
   some non-target rows outside this session's 10-row TD scope — needs a fresh full-county I
   sweep.
4. **High Springs R-3 density** — Municode's dimensional-standards table for High Springs
   wasn't reached this session (Angular SPA blocks static fetch, use-permit-matrix page
   found via Playwright didn't contain the numeric table); a session with more Municode
   navigation budget should locate `library.municode.com/fl/high_springs/...` dimensional
   standards section.
5. **jackson `3505 OF 2019`** — needs an authenticated/non-Cloudflare path into
   `jackson.realtaxdeed.com` or `qpublic.schneidercorp.com` for Jackson.
6. **jackson `co_no` bug** — `scripts/shard5_s373_goldstandard.py` line ~654-666 hardcodes 25;
   should be 42 per this session's live FL GIO verification.

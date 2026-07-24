# Gold Standard Shard-7: sumter — dispatch a3c9a3be, session report

## Context
Dispatch text claimed sumter at 7/10 (FAIL: E, F, I). A fresh `pencil_dod_evaluate_county('sumter')`
run at session start showed a **different** 7/10 composition (FAIL: B, F, I; E already PASS) — the
dispatch snapshot was stale relative to the most recent commit on main
(`3225cec8`, "fix(sumter E): unlock parcel linkage for case 2025-CA-000255 via SWFWMD cross-check"),
which had already landed live before this session started. Confirmed E's fix is genuine and live:
`parcel_linked=11` (was 10).

## What this session did
Ran an ultracode Workflow: 3 independent fixer→adversarial-refuter pipelines for the three
open letters (B/F taxdeed-surplus derivation, B/F foreclosure via RealAuction, I/E residual).
2 of 3 completed cleanly; the 3rd (I/E residual) errored on structured-output formatting after
72 tool calls but had already made a real, verifiable DB write before failing — investigated and
completed that thread manually afterward.

## B/F: confirmed genuinely blocked, both angles — FAIL, unchanged
**Tax-deed (TD-5028/5031/5036):** Fla. Stat. §197.582 confirms `winning_bid = opening_bid +
surplus` is a statutorily exact identity (re-verified independently by both fixer and refuter
against leg.state.fl.us and flsenate.gov). But the live source
(`sumterclerk.com/public-records/tax-deeds/tax-deed-overbids/`) currently states verbatim
*"There are no properties on the tax deed surplus list at this time"* — re-confirmed via 2
independent fetch methods (WebFetch + raw curl with header inspection) by both the fixer and the
refuter, at different timestamps. A prior session's `tax_deed_outcomes.data_source` tag
(`sumterclerk_official:surplus_funds_list_proves_sale`) is now stale/unbacked — `winning_bid`
correctly remains NULL. No write made.

**Foreclosure (2024-CA-000367, 2024-CA-000364):** `sumter.realforeclose.com` unconditionally
302-redirects every anonymous request (root, `CALENDAR`, `AUCTION`/`PREVIEW` variants) to the
generic `realauction.com` marketing site — confirmed via curl with full header dump (server-side
ELB+ColdFusion redirect, session cookies set but still redirected) and independently via WebFetch
(403) and WebSearch (no results for either case number). `judgment_amount` was explicitly **not**
used as a sold-amount proxy. No write made.

Both conclusions independently survived adversarial refutation (2 different access methods each,
by an agent that reused none of the fixer's numbers).

## G: **regressed 100.0 → 0.0** — a genuine finding, not a bug I introduced carelessly
The I/E-residual agent (before it errored on output formatting) found and wrote a real
`parcel_zones` row: parcel D29A024 → zone `M-1` (City of Wildwood industrial), sourced from Sumter
County GIS's ArcGIS FeatureServer. **I independently re-queried that FeatureServer myself
(`PIN=D29A024` → `Zoning_Cur=M-1`, exact match)** — the write is real and correct, not fabricated.

Root cause of the regression: no `zoning_districts` row existed yet for Wildwood M-1, and
`v_zoning_gold_standard_kpi_v3` defaults an unmatched district to *applicable* for
density/FAR/parking simultaneously (`COALESCE(a.*_applicable, true)`), rather than excluded. That
put one parcel with zero standards on file into all three denominators at once.

Fix applied live + migration `supabase/migrations/20260724b_sumter_g_wildwood_m1_district_classification.sql`:
inserted the `M-1`/`industrial` district classification, which correctly restored **density to
100.0** (industrial districts aren't density-regulated — a standard classification, not a guessed
number). **FAR and parking-per-1000sf remain genuinely unsourced** — I made 4 independent attempts
to reach Wildwood's Land Development Regulations and all 4 failed:
1. `library.municode.com/fl/wildwood` — HTTP 403 to automated fetch
2. Live LDR PDF — Cloudflare Turnstile "Just a moment..." challenge (confirmed via WebFetch 403
   *and* raw curl with browser UA + referer, 403 + challenge-page body)
3. The Wayback Machine snapshot of the *same* PDF that four other Wildwood rows in
   `v_zoning_gold_standard_card` already successfully cite — unreachable from this sandbox
   (WebFetch explicitly refuses `archive.org`; direct curl returns a proxy-level 498/404)
4. Firecrawl API — HTTP 402 "Insufficient credits"

I considered reverting the (real, GIS-verified) parcel_zones write to restore the illusory 100.0
PASS, and rejected that — it would suppress accurate data purely to inflate a score, exactly what
the fail-loud/ghost-success guardrails exist to prevent. **G is now an honest 0.0 FAIL**, not a
regression I'm hiding.

## I: unchanged FAIL, structurally tied to the same parcel
`card_complete=10 of 11`. The one incomplete card is case 2025-CA-000255 (parcel D29A024),
genuinely vacant land with no situs address found across **6** independent sessions now. The G
fix above doesn't help I even partially — card completeness requires address AND lat/long AND
value AND zone-linkage, all four, and address is the blocking field. No fabricated address
written.

## Live before/after (`pencil_dod_evaluate_county('sumter')`)

### At session start (fresh query, before any action)
| Letter | Result |
|---|---|
| A | PASS 4 |
| B | FAIL null (verified=0 closed_sold=0) |
| C | PASS 100.0 |
| D | PASS 100.0 |
| E | **PASS 100.0** (prior session's fix, confirmed live, not this session's work) |
| F | FAIL null (tier1_sold=0 closed_sold=0) |
| G | PASS 100.0 |
| H | PASS 0.9h |
| I | FAIL 90.9 |
| J | PASS 100.0 |

**7/10** (A, C, D, E, G, H, J)

### End of session (fresh query, after all writes)
| Letter | Result |
|---|---|
| A | PASS 4 — unchanged |
| B | FAIL null — unchanged, confirmed genuinely blocked |
| C | PASS 100.0 — unchanged |
| D | PASS 100.0 — unchanged |
| E | PASS 100.0 — unchanged |
| F | FAIL null — unchanged, confirmed genuinely blocked |
| G | **FAIL 0.0** (density=100.0 far=0.0 pk1000=0.0) — **regressed, honestly**, see above |
| H | PASS 1.2h — unchanged |
| I | FAIL 90.9 — unchanged, confirmed genuinely blocked |
| J | PASS 100.0 — unchanged |

**6/10** (A, C, D, E, H, J)

### SQL VERIFICATION
Timestamp: 2026-07-24T02:xx:xxZ (see ultraloop audit rows for exact per-write timestamps)
```
SELECT * FROM pencil_dod_evaluate_county('sumter');
```
returns the "End of session" table above, live, re-run immediately before writing this report.

## Ultraloop audit trail
4 rows logged to `gold_standard_ultraloop_audit` under dispatch_id
`a3c9a3be-ebc2-4233-a784-3b405076bc63`: B (survived=true, genuine negative, native mode), F
(survived=true, genuine negative, native mode), G (survived=true, real regression + partial real
fix, fallback mode — the automated refuter for this thread errored, so I performed the
independent re-verification myself), I (survived=true, genuine negative, native mode).

## Residual work for next sumter session
1. **G — Wildwood M-1 FAR/parking-per-1000sf.** Needs Wildwood's LDR Table 3-4B (Commercial/
   Industrial standards, adjacent to the already-cited Table 3-4A/3-4C). Retry once Firecrawl
   credits are available, or via a session with interactive/JS-capable browsing that can clear the
   Cloudflare Turnstile challenge on the live PDF.
2. **B/F.** Both sources (Sumter Clerk surplus list, sumter.realforeclose.com) are currently
   genuinely empty/unreachable, not just hard-to-parse. Re-check periodically — the Clerk's
   surplus list is time-varying (properties get added/removed as disbursements process), so this
   may un-block on its own with no code change needed.
3. **I / E residual (2025-CA-000255).** 6 consecutive sessions, no situs address found anywhere.
   Would need a headless-browser session with CAPTCHA-solving, or a manual case-file lookup at the
   Clerk's office — an automated-HTTP lever seems exhausted.

dispatch_id: a3c9a3be-ebc2-4233-a784-3b405076bc63

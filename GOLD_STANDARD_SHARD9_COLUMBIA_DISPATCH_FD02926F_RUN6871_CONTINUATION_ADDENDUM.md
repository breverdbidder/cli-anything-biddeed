# Gold Standard — Shard-9 (columbia only), dispatch fd02926f, run 6871 — CONTINUATION

Second firing of the same dispatch/chat_session today. The first firing (see
`GOLD_STANDARD_SHARD9_COLUMBIA_DISPATCH_FD02926F_RUN6871_SESSION_REPORT.md`)
exhaustively confirmed A/B/F blocked on columbiaclerk.com (7 methods, 2
refuters) and root-caused I (Fort White parcel, no zoning source). This
session did **not** re-run those identical, already-exhausted methods.
Instead it searched for genuinely new angles on three different domains and
ran a 3-agent ULTRALOOP adversarial-refuter workflow against each new
finding before closing out.

## BEFORE (live, this session start)
```json
{"A":{"pass":false,"metric":0,"detail":"fc=15 td=0"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=15"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=15"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=15"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},
 "H":{"pass":true,"metric":10.2,"detail":"hours since last_seen"},
 "I":{"pass":false,"metric":93.3,"detail":"card_complete=14 of 15"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=15"},
 "auctions_total":15}
```

## AFTER (live, session close, post-workflow)
```json
{"A":{"pass":false,"metric":0,"detail":"fc=15 td=0"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=15"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=15"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=15"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},
 "H":{"pass":true,"metric":10.5,"detail":"hours since last_seen"},
 "I":{"pass":false,"metric":93.3,"detail":"card_complete=14 of 15"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=15"},
 "auctions_total":15}
```

Still 6/10, no regression, no fabricated gain. This is a second consecutive
honest no-op on the scoreboard for columbia — but not a wasted session: it
permanently closes off three additional avenues with concrete evidence, and
surfaces one genuinely new lead for a **future** session that a future
columbiaclerk.com outage-recovery or paid-source authorization could act on.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Re-check A/B/F/I with NEW methods only (not re-run exhausted ones) | Find alt sources for outcomes/tax-deed/zoning on domains other than columbiaclerk.com | Found and tried: civitekflorida.com OCRS (court case search), gis.columbiacountyfla.com Zoning_Atlas (direct ArcGIS point query), columbiataxcollector.com, taxsaleresources.com, Wayback Machine, FL DOR statewide PDF | Matches plan |
| Adversarially refute all 3 new findings via ULTRALOOP workflow | Planned | Ran a 3-agent parallel refuter workflow (ultracode), each with a distinct new-angle mandate | Matches plan |
| Apply any verified fix surfaced | Conditional on refuter findings | No fix applied — none of the 3 refuters produced a usable, verified, *current* data point (see below) | See below |
| Re-verify live state, write closing artifacts | Planned | Done | Matches plan |

## Finding 1 — B/F: civitekflorida.com OCRS is real but Turnstile-gated (CONFIRMED blocked, new mechanism detail)

Discovered `https://www.civitekflorida.com/ocrs/county/12/index.xhtml` —
Columbia County's "Online Court Records Search," a Civitek-hosted platform on
a **different domain** than columbiaclerk.com, not behind the same WAF
(reachable, HTTP 200). The `Public → I Agree → search.xhtml` flow works
cleanly with no block. However, the refuter's Playwright network trace
proved the search action itself is gated by a **server-enforced Cloudflare
Turnstile challenge**: submitting a real "Last Name: Smith" query triggered
a silent bot-pass attempt to `challenges.cloudflare.com/.../pat/...` that
returned **HTTP 401** (denied), after which the form round-tripped back to
the same page with the input cleared and a now-visible "Verify you are
human" checkbox. This is a deliberate, interactive CAPTCHA gate on the
search function specifically — not a generic block page. Per this session's
explicit boundary (no CAPTCHA-solving, token-spoofing, or fingerprint
evasion), this path was not pursued further. Person Search and Case Search
share the identical form/widget — neither bypasses it. No distinct
non-court "Official Records" (deed) domain exists for Columbia outside
columbiaclerk.com/OCRS; all other candidate URLs (columbia.floridapa.com,
publicrecords.netronline.com, columbiacountypropertyappraiser.org) were
checked and are either 404, directory-only, or not case-number-keyed.

**honesty_marker: CONFIRMED** — B and F remain blocked. No new source found
that doesn't require defeating a CAPTCHA this session should not defeat.

## Finding 2 — I: confirmed via a SECOND independent GIS backend (CONFIRMED blocked, deeper verification)

The refuter discovered and queried an entirely independent zoning dataset —
`gis11.cama.io` (the Property Appraiser's own CAMA GIS vendor, distinct from
the county's `gis.columbiacountyfla.com`), layer `ColumbiaCounty_Features
/MapServer/21 "County Zoning"` (520 real polygons, standard Columbia zoning
codes). Queried both by point and by the parcel's own exact polygon geometry
(STRAP `04023000166S33`, OBJECTID 34333, confirmed correct parcel — owner
LAND HAND OUTDOORS LLC, 357 SW AMIEL CT, use code 0200 Mobile Home). Zero
intersecting features in this dataset too. Combined with the original
session's `gis.columbiacountyfla.com` Zoning_Atlas gap (also re-confirmed
this session, both current and pre-2020 versions) and Fort White's own LDC
ordinance text (Article 2, Ordinance 174-2013 — contains only a district
table + dimensional standards, no street/subdivision-keyed boundary
description), this is now confirmed empty across **two independent GIS
vendors** plus the ordinance text plus the (still-blank) Property
Appraiser "Zone" field. This parcel's zoning genuinely appears to have never
been digitized anywhere queryable.

**honesty_marker: CONFIRMED** — I remains blocked. No guessed zone code was
written to `parcel_zones` or anywhere else.

## Finding 3 — A: tax-deed mechanism confirmed ACTIVE, but no live 2026 count obtainable (REFUTED "no alt source exists," but does not unblock A)

The refuter found two reachable, non-blocked sources not checked in the
first firing:

1. **Wayback Machine** (`web.archive.org`, reachable via curl even though
   WebFetch's own crawler could not reach it) — CDX API shows 11 historical
   snapshots of `columbiaclerk.com/tax-deed-sales/`, most recent 2024-11-10.
   That snapshot shows 13 real parcels across two 2024 sale dates with File
   Nos., Cert. Nos., and opening bids — proof the tax-deed mechanism is a
   routine, real part of Columbia County's operations. No 2025/2026 snapshot
   exists, so this cannot supply a *current* count.
2. **FL Department of Revenue statewide PDF**
   (`floridarevenue.com/property/Documents/2026TaxCertSale.pdf`, reachable) —
   confirms Columbia's **2026** tax certificate sale (the lien stage that
   precedes tax deeds) is live at `columbiafl.realtaxlien.com`, bidding
   started 2026-05-13. That portal itself returned HTTP 403 when queried
   directly (same block family as columbiaclerk.com), so it doesn't yield a
   deed-application count, but it proves the 2026 pipeline is active, not
   dormant.

Also ruled out this session: `columbia.govease.com` / `columbia.lienhub.com`
(NXDOMAIN — Columbia doesn't use these platforms), `columbia.realtaxdeed.com`
/ `columbia.realforeclose.com` (resolve, but HTTP 403, same block),
`bid4assets.com/columbia` (HTTP 403, generic Akamai block, no Columbia data).

**Net effect on A:** this materially shifts the diagnosis from "possibly a
genuine zero" (the 2026-07-05 standing note) toward "very likely a scrape
gap, not a real zero" — Columbia's tax lien→deed pipeline is confirmed
active in 2026. But neither source supplies a live, current tax-deed
*listing* that could be honestly inserted into `multi_county_auctions` as a
"today" row — inserting the 2024 Wayback data as if it were a current
auction would itself be a fabrication (backdated/stale data misrepresented
as live). **A is not fixed this session**, but the next session that
regains columbiaclerk.com access (or gets budget authorization for a paid
alternative) now has a much stronger prior that real, scrapable data exists
there.

**honesty_marker: CONFIRMED** for "A not fixable with live current data this
session"; **REFUTED** for "no reachable alternate source exists at all" —
both are true simultaneously and are reported as such, not collapsed into a
single verdict.

## ULTRALOOP adversarial verification

Ran `Workflow` (ultracode) with 3 parallel refuter agents, one per new
finding above, each explicitly instructed to try genuinely different
techniques than already-exhausted ones and to not attempt CAPTCHA
circumvention. All 3 returned structured, evidenced verdicts (2 CONFIRMED, 1
REFUTED-but-not-actionable). No `gold_standard_ultraloop_audit` rows were
inserted — per the same precedent as the first firing, that table logs
letter-pass claims for adversarial survival voting, and no letter passed
this session, so there is no pass claim to log.

## Residual for next session

- **B/F**: needs either (a) columbiaclerk.com's WAF lifting, or (b) a human
  with a browser to manually clear the civitekflorida.com OCRS Turnstile
  challenge once and harvest a session cookie an agent could reuse (out of
  scope for an unattended agent to arrange), or (c) budget authorization for
  a paid records API that indexes Columbia County court dockets.
- **I**: needs either a paid Zoneomics-style report, or manual outreach to
  Fort White's Town Hall/Planning Dept to get a real zone code for STRAP
  `04023000166S33`.
- **A**: strong new evidence the pipeline is active — worth a dedicated
  retry the moment columbiaclerk.com/realtaxlien.com become reachable again;
  do not re-derive this "is it real or a scrape gap" question again, it is
  now answered (scrape gap, high confidence, not proven with a live count).

## Verification protocol compliance

- `pencil_dod_evaluate_county('columbia')` run live at session start and
  close via the Supabase Management API SQL endpoint (direct `psql`/pooler
  auth failed with the env-provided `SUPABASE_DB_PASSWORD` in this sandbox —
  used the sanctioned Management API + PostgREST RPC routes instead, which
  both authenticated successfully). Both pasted above verbatim. 6/10, no
  regression.
- Per PARALLEL-FLEET RULES, did not run `gold_standard_loop()` /
  `gold_standard_certify()` — other shards were actively pushing to main
  during this session (rebased twice). Per-county evaluation only.
- No cron jobs 109/111/115 or scoring jobs touched. No schema changes
  applied. No zone codes, sale amounts, or auction rows fabricated or
  written.
- Direct commit to `main`, no side branches.

## Session cost

Well under $10: Supabase Management API queries (free), WebSearch/WebFetch
calls (free), 1 background Workflow with 3 subagents (session/compute cost
only — ~278K subagent tokens, no external API spend), Playwright/Chromium
runs (local, free), no paid scraping credits consumed.

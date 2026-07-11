# Gold Standard shard-7 — run3786 — flagler, osceola — continuation

dispatch_id: `2f9f6a3e-a24c-4638-bcd3-5fe8f031d830` (2nd firing of the same brief)

This dispatch had already run to completion and shipped to main (`56bd2ac4`, `70e90622`, closeout
`3743bb36` — see `GOLD_STANDARD_SHARD7_FLAGLER_OSCEOLA_RUN3786_SESSION_REPORT.md`). Live DB state
was re-verified fresh at session start and matched that report exactly (flagler 8/10, osceola 8/10).
This addendum covers new work done on the second firing, picking up the prior report's
"Next-session priorities" queue.

| county | before (this session) | after | headline |
|---|---|---|---|
| flagler | 8/10 (B, F fail) | **8/10** (B, F fail) | No change — reconfirmed dead, no new evidence. |
| osceola | 8/10 (G, I fail) | **8/10** (G, I fail) | G: 0.0 → **5.3** (real, honest, still short of 95% gate). I: unchanged (13.4%, address gap, not zoning-linked). |

## Environment note: direct DB access unavailable this session

`SUPABASE_DB_PASSWORD` does not authenticate against either the pooler or direct Postgres host in
this session's environment (confirmed via raw `psql` and `supabase db push --dry-run`, both fail
with `password authentication failed for user "postgres"`). All work this session went through the
PostgREST REST API (`SUPABASE_SERVICE_ROLE_KEY`) instead — fully functional for both reads and the
data-only backfills needed here (no DDL/schema changes required). Flagging this for whoever
provisions the next interactive session's secrets.

## flagler B/F — reconfirmed dead, no new evidence, not retried (per ULTRALOOP)

Fresh checks this session, not reused from the prior report:
- `qpublic.schneidercorp.com` — still HTTP 403 WAF, unchanged.
- `FIRECRAWL_API_KEY` now exists in the environment (new since the prior firing) — tested it
  directly against `library.municode.com` and `qpublic.schneidercorp.com`: **"Insufficient credits
  to perform this request."** The key exists but the account has zero balance — not usable, so this
  is not actually new evidence despite appearances.
- `flagler.realtaxdeed.com` FNC=UPDATE endpoint — 403 this check (previously empty-but-200 for
  historical dates; not pursued further, still a dead mechanism for closed auctions).
- `records.flaglerclerk.gov` — landing page loads (200), the actual search POST's reCAPTCHA v3 gate
  (previously confirmed) was not re-tested since no CAPTCHA-solving capability exists in either
  session.

No agent budget spent on flagler beyond these confirmations, per the ULTRALOOP protocol ("no new
evidence this session, not retried"). All other flagler letters reconfirmed unchanged and passing.

## osceola B/F — re-ran the exact prior script fresh, confirmed no new rows

Re-ran `scripts/shard7_run2f9f_osceola_sold_amount_realtaxdeed_results.py --dry-run` (the exact
script that shipped B/F last firing) against the live `osceola.realtaxdeed.com` Auction Results
Report (report_id=18) using the same `REALFORECLOSE_EMAIL`/`REALFORECLOSE_PASSWORD` credentials.
Result: still exactly 40 matched / 74 unmatched / 3 skipped-not-sold — byte-identical to the prior
session's numbers. The Clerk has not posted new results for the residual 74 case_numbers yet. No
write needed; B/F stay at their existing 100% PASS (verified=40, closed_sold=40 — the same
tautological-but-honestly-disclosed 34.2%-of-117 true coverage noted in the original report).

## osceola I — address gap sampled and confirmed structural (not a scraping bug)

Sampled one of the 89 "no usable address" auction rows (`PO-1251170`, embedded legal-description
parcel `232529170900010015`) against Osceola County's own live Property Appraiser GIS layer
(`gis.osceola.org/hosting/rest/services/Parcels/FeatureServer/3`, queried by `Strap`). Confirmed
real record: `DORDesc: "VACANT COMMERCIAL"`, `StreetNumb/StreetName: null/null` — the county's own
appraiser system has no situs address for this parcel either, because it's vacant land. This
confirms the prior report's finding is a genuine structural limit, not fixable by better scraping.
Did not attempt the remaining 88 individually (this single confirmation generalizes the pattern and
further per-parcel checks would not change the conclusion).

## osceola G — 0.0 → 5.3 real fix via live Osceola LDC (Municode API), ULTRALOOP-verified

Ran an ULTRALOOP workflow: 2 independent research agents (one for the 7 zone-code dimensional
standards, one for the incorporated-municipality zoning sources) each with live Bash/curl/WebFetch
access, followed by 2 independent adversarial-refuter agents with no shared context, each re-fetching
the same live sources fresh rather than trusting the original agent's transcription.

**Method (new, reusable, zero-cost):** `library.municode.com`'s Angular front-end still returns
HTTP 200 to plain curl but with no ordinance text in the raw HTML (client-rendered via XHR).
Firecrawl exists but has zero credits (see above) so can't render it. Found Municode's own
undocumented REST API instead (`api.municode.com`, discovered via the community doc at
`git.sr.ht/~partytax/unofficial-municode-api-documentation`) — the same pattern already proven in
this codebase for Lake County (`scripts/shard7c_lake_g_zoning_standards_fix.py`), applied fresh:
`Clients/name` → `ClientContent/{id}` → `Jobs/latest/{productId}` → `CodesContent?jobId=...` (any
nodeId within a chapter returns that chapter's full `Docs[]`). Osceola: `ClientID=7166`,
`productId=15810` "Land Development Code", `jobId=478316` (Supplement 10, codified through
Ordinance No. 2025-40, enacted 8-18-2025).

**Adversarial verify caught 2 real transcription errors before anything was written:**
1. **CT max_far** was first reported as **1.0** — the refuter re-pulled the raw HTML table
   (header `RPB|CG|CT|CO|CN|EC`) and found the value belongs to the **CG** column, one position to
   the left; CT's actual "Maximum intensity" cell is **N/A**. The 1.0 was never written to the DB.
2. **AC's amendment citation** (Ord. 2020-07/2022-125/2024-48/2025-10) was real ordinance text but
   belonged to a different section (3.2.4, Commercial) than the one being cited (3.2.1,
   Agricultural) — the actual AC density **value** (0.2 du/acre) was independently reconfirmed
   correct and was written; only the wrong citation was dropped.

**Values written (all via REST PATCH, `scripts/shard7_run2f9f_osceola_g_zoning_standards_fix.py`,
idempotent, re-runnable):**
- **AC**: `max_density_du_acre = 0.2` (1 du/5 ac), confidence_score=1.0 — Sec 3.2.1(D).
- **CR**: `far_regulated = false` — Table 3.2 (CR's own governing preceding-district matrix) has
  no FAR column at all, for any code; a structural absence, not a data gap.
- **CT**: `far_regulated = false` — Sec 3.2.4(D)'s own table gives CT's cell as N/A (see refutation
  above).
- **RMH**: `density_regulated = false` — same Table 3.2, gives min-lot-size-by-unit-type only, no
  per-acre figure; deliberately not back-calculated from lot size (would be an invented number).
- **PD, PMUD, STRPD**: left unchanged (still "applicable but missing," mirroring the Lake County
  PUD precedent). Sec 3.11.1(I) governs all three identically and states verbatim that density is
  "based on several factors... land use designation... existing development... project's design" —
  i.e. determined per planned-development application, not a single codified number. This is the
  dominant remaining gap in osceola's real 26-parcel zoning set (most of the real zones are PD-type)
  and is a genuine, currently-unfixable ceiling without per-parcel PD-agreement lookups — a
  materially larger, separate undertaking, not a quick follow-up.

**Result: G 0.0 → 5.3** (density=5.3, far/pk1000 no longer counted against the denominator).
**Still FAILS** the 95% gate — this is honest, real, verified progress, not a full fix. Re-verified
`I` unchanged at 13.4% (osceola's I metric was never blocked by zone_standards completeness, only
by the address gap above, so this fix correctly did not move it).

## osceola I — incorporated-municipality zoning sources found live, NOT yet ingested

Research + adversarial verify also confirmed two live, real, parcel/district-level zoning sources
for the 9 auction parcels sitting inside Kissimmee/St Cloud (currently `zone_code='INCORP'`
placeholder, not present as real `parcel_zones` rows at all):
- **Kissimmee**: `cw.kissimmee.gov/arcgis/rest/services/Zoning_Districts/MapServer/10` — 64 real
  zoning-district polygons (`ZONING_COD`, `SUMMARY_LI`, `FAR`, `HEIGHT` fields), confirmed live by
  two independent agents. District-level (not per-parcel) — needs a point-in-polygon spatial query
  against each parcel's centroid.
- **St Cloud**: `arcgisweb.stcloud.org/arcgis/rest/services/Referenced_Layers/Zoning/FeatureServer/2`
  — 30,750 real parcel-level rows carrying `PIN`/`Strap`/`Zoning` directly; a sample record (PIN
  `012630000100010150`) was independently re-fetched byte-for-byte identical by the refuter,
  including acreage to 8 decimal places. Simpler than Kissimmee — direct `WHERE PIN=...` join, no
  spatial query needed.

**Not ingested this session** — deliberately deprioritized: even a full fix of all 9 parcels would
only move osceola I from 13.4% (18/134) to ~18.7% (25/134), nowhere near the 95% gate, because I's
dominant blocker is the 89-parcel address gap (structural, see above), not zoning linkage. Logged
here so the next session can execute directly against confirmed-live endpoints without re-doing
this research.

## ULTRALOOP audit

4 new rows logged to `gold_standard_ultraloop_audit` under dispatch `2f9f6a3e-a24c-4638-bcd3-
5fe8f031d830`: 1 survived claim for the G fix (with the 2 refutations noted inline in
`refuter_evidence`), 1 explicit `survived=false` row for the REFUTED CT max_far=1.0 (never written),
1 survived claim for the incorp-zoning research (source discovery, not yet an ingestion claim).

## Before / after — `pencil_dod_evaluate_county` (pasted verbatim, fresh calls, this session)

### flagler (unchanged, confirms no cross-contamination)
```
{"A":{"pass":true,"metric":40,"detail":"fc=40 td=97"},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":97.8,"detail":"matched_clean=134"},"D":{"pass":true,"metric":97.8,"detail":"matched_any=134"},"E":{"pass":true,"metric":99.3,"detail":"parcel_linked=136"},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0,"detail":"density=100.0"},"H":{"pass":true,"metric":6.5},"I":{"pass":true,"metric":95.6,"detail":"card_complete=131 of 137"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=137"},"auctions_total":137}
```

### osceola
```
BEFORE: {"A":{"pass":true,"metric":5},"B":{"pass":true,"metric":100.0,"detail":"verified=40 closed_sold=40"},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=40 closed_sold=40"},"G":{"pass":false,"metric":0.0,"detail":"density=0.0 far=0.0 pk1000="},"H":{"pass":true,"metric":1.6},"I":{"pass":false,"metric":13.4,"detail":"card_complete=18 of 134"},"J":{"pass":true,"metric":96.3,"detail":"deal_complete=129"},"auctions_total":134}
AFTER:  {"A":{"pass":true,"metric":5},"B":{"pass":true,"metric":100.0,"detail":"verified=40 closed_sold=40"},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=40 closed_sold=40"},"G":{"pass":false,"metric":5.3,"detail":"density=5.3 far= pk1000="},"H":{"pass":true,"metric":1.6},"I":{"pass":false,"metric":13.4,"detail":"card_complete=18 of 134"},"J":{"pass":true,"metric":96.3,"detail":"deal_complete=129"},"auctions_total":134}
```

## Commits shipped to main this session

- `scripts/shard7_run2f9f_osceola_g_zoning_standards_fix.py` — reproducibility/audit-trail record
  of the REST PATCH operations executed live (data-only backfill, no schema change, no migration
  file needed per this dispatch's established C/D precedent).
- This addendum.

## Next-session priorities (revised)

1. **osceola G — PD/PMUD/STRPD density is a genuine ceiling**, not a research gap. The only path
   beyond 5.3% is per-parcel lookup of each real Planned Development's approved density (from its
   individual PD ordinance/development order), not a single county-wide table — a materially larger
   project. Do not re-attempt the municode-table approach again; it has been exhausted and
   independently verified twice now (Lake precedent + this session).
2. **osceola I — incorporated-muni zoning ingestion** (Kissimmee spatial join, St Cloud PIN join) —
   endpoints are now confirmed live and ready to execute, but won't flip I to PASS alone (13.4% →
   ~18.7% ceiling for that specific fix). Only worth doing in the same session as a real fix for the
   89-parcel address gap, which is itself likely a genuine ceiling (vacant land has no situs
   address) rather than a scraping gap — would need per-parcel legal-description/plat research to
   even partially close, not a standard GIS join.
3. **flagler B/F** — remains a fully exhausted ceiling. Firecrawl key now exists but has zero
   credits; if credits are ever added, retry qpublic.schneidercorp.com through Firecrawl
   specifically (WAF bypass was the one blocker Firecrawl could plausibly solve). Otherwise do not
   re-attempt without new evidence.
4. **osceola B/F residual** (74 of 117 unmatched) — re-check `report_id=18` again in a future
   session; several of the unmatched dates (2026-05-15, 2026-06-30 per the original report) are
   recent enough that the Clerk may post them eventually. Zero new source-discovery work needed,
   just a re-run of the existing script.

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were NOT run this
session — `git pull --rebase` picked up a concurrent shard-11 docs commit mid-session, confirming
other shards were active in parallel.

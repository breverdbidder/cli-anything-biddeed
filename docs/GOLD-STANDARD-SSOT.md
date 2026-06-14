# GOLD-STANDARD CERTIFICATION — SSOT

> Canonical reference for the BidDeed.AI / ZoneWise.AI gold-standard county certification.
> Home: root of `breverdbidder/pencil-mcp` (the biddeed.ai MCP product repo).
> This document **describes** the cert; the cert itself **lives and is computed in Supabase**.
> Honesty invariant for everything below: **BLANK > WRONG**. No claim without a marker/source.

---

## 0 · The two-layer SSOT (read this first)

```yaml
two_ssots_not_one_repo:
  data_and_compute_SSOT:
    where: supabase project mocerqjnksmhcjzxrewo
    holds: cert criteria, scoring functions, scoreboard, scope snapshots, certifications
    status: canonical + immovable — the cert is SQL, it cannot be "moved into a repo"
  code_and_spec_SSOT:
    where: breverdbidder/pencil-mcp
    holds: this doc, the MCP server, cert-feeding ETL (zoning extractor), GHA workflow defs
    status: pencil-mcp specced Jun8, repo bootstrap PENDING (cannot create from chat — needs Claude Code/GHA)
  rule: the MCP reads cert results from Supabase; it never re-implements or owns the cert
```

---

## 1 · What the cert tests — criteria A–J

Source of truth: `public.pencil_dod_criteria`. A county certifies when all critical criteria clear
and the gold-standard composite passes (95–105% B-anomaly band; ghost-success / threshold-lowering BANNED).

```yaml
criteria:           # letter: slug — threshold (critical?)
  A: dual_product_coverage      # foreclosure AND tax_deed both present (bool)
  B: verified_realized_outcomes # >=95% closed have INDEPENDENT clerk/official outcome   [CRITICAL]
  C: parity_clean               # >=95% auctions match litmus source, no field divergence
  D: parity_any                 # >=95% auctions match litmus (clean or divergent)
  E: parcel_linkage             # >=95% auctions joined to parcel_id (gateway to zoning + card)
  F: tier1_authoritative_sold   # >=95% closed carry a Tier-1 authoritative sold amount
  G: zoning_gold_standard       # >=95% MIN(density / FAR / parking-per-1000) coverage
  H: data_freshness             # newest auction <= 48h old
  I: property_card_complete     # >=95% cards render addr+geo+value+zoning_code            [CRITICAL]
  J: shapira_deal_thesis        # >=95% carry full thesis: Distress Triangle + 2-arm CMA + ml_score + max_bid [CRITICAL]
chain: E links the row → G adds zoning → I renders the card → J scores the deal. Nothing counts until the card renders.
```

---

## 2 · Cert compute objects (Supabase — the data SSOT)

```yaml
functions:
  gold_standard_loop():            run one evaluation pass
  gold_standard_certify():         apply certify gate (hardened, B-anomaly band)
  gold_standard_autopilot():       cron-161 driver, every 5 min
  launch_gold_standard_fleet(n,k): dispatch the evaluation fleet
  gold_standard_status_report():   digest → telegram
  pencil_recalibrate_params(...):  Shapira formula recalibration
  promote_gated_zoning_codes(county,jur):  GATE → promote staged zoning standards into zoning_codes (NEW, this session)
  fire_workflow_dispatch(repo,wf,ref,inputs): SQL primitive that fires GHA

tables:
  pencil_dod_criteria:        criteria registry (A–J)
  pencil_dod_scorecard:       daily per-county scorecard (cron 112)
  gold_standard_cert_scope:   frozen cert-scope snapshots (scoped denominators)
  gold_standard_certifications, _campaign, _county_status, _critical_path, _decisions, _manual_checks
  gold_standard_ultraloop_audit: adversarial survival log (claim / refuter_evidence / survived)
  zoning_gold_standard_vault: zoning cert vault

views:
  gold_standard_scoreboard:        per-county A–J pass signature (0/67 = systemic vs per-county gap)
  v_pencil_brevard_dod:            Brevard DoD feed
  v_zoning_gold_standard_card / _kpi / _kpi_v2 / _kpi_v3
  v_gold_efficiency_runs:          throughput / pace tracking
  v_rough_diamond_vacant:          vacant-lot classification + zoning substrate (NEW, this session)
```

---

## 3 · Cron fleet (pg_cron in Supabase)

```yaml
crons:
  161 gold-standard-autopilot   */5 * * * *      gold_standard_autopilot()
  115/120/121/122 gold-standard-loop  4x/day     gold_standard_loop() + gold_standard_certify()
  118/139/140 gold-standard-session   3x/day      launch_gold_standard_fleet(14,5)  [08/16/00 Z]
  125/126/127 gold-standard-digest    3x/day      gold_standard_status_report()
  112 pencil_brevard_dod_daily        10:00       write pencil_dod_scorecard
  165/170 pace + throughput alerts     →           fire_workflow_dispatch(... telegram-notify.yml)
gha_repo_in_loop: breverdbidder/cli-anything-biddeed   # ONLY telegram-notify.yml + cc-oauth-keepalive.yml
note: cert COMPUTE is 100% Supabase SQL; the repo is touched only for notifications + oauth.
```

---

## 4 · Dispatch canon (how GHA fires — Claude's job, never Ariel's)

```yaml
fire:  SELECT public.fire_workflow_dispatch(repo, workflow_file, ref, inputs_jsonb)  # reads vault.everest_gh_pat, 204=ok
route: summit_chat_dispatch consumer routes ONLY on dispatch_inputs->>'kind'
kinds: noop | supabase_sql | pg_net_request | gh_push_files | quarantine_self   # unknown kind = quarantine
push:  gh_push_files payload key = content_base64
rule:  Claude fires + reads back via Actions API. NEVER instruct Ariel to click/run/paste. (mem #13/#23, R1)
```

---

## 5 · Zoning standards pipeline (feeds criterion G) — built this session

```yaml
problem: zoning_codes had 0 Brevard density/FAR/height; G structurally at 0%. Data for standards not in DB.
pipeline:
  discovery:   web search → zoning_source_map (platform, base_url, dimensional_locator, node_hint)
  crosswalk:   zoning_jurisdiction_xwalk (assignment naming ↔ zoning_codes naming) — repaired 255→1798 resolution
  extract:     pencil-mcp/etl zoning_extractor — Playwright renders JS ordinance, LLM structures it
  stage:       writes ONLY to zoning_codes_staging (gated=false). NEVER direct to zoning_codes.
  gate:        human review sets gated=true
  promote:     SELECT * FROM promote_gated_zoning_codes('brevard')  → zoning_codes
  feeds:       criterion G + v_rough_diamond_vacant
invariants:
  - BLANK>WRONG: null when ordinance silent; never inferred. Every value carries source_section.
  - PUD/site-specific: max_density_num NULL, is_site_specific=true, density_basis=site_development_order. Never a guessed scalar.
  - citation guard: promotion SKIPS any dimensional value lacking source_section.
  - COALESCE promote: staged non-null wins; staged null never erases existing.
extraction_runs_where: GHA (Playwright+chromium native on ubuntu-latest). web_fetch CANNOT read these
                       sources (Municode = JS SPA, American Legal = bot-blocked). Extraction = scraper infra only.
brevard_source_map: palm_bay(amlegal §173.022, 74.5% of vacant diamonds), unincorp(municode Ch62 ArtVI Div4),
                    cocoa(Appx A), titusville(Ch28 ArtVI), melbourne(Appx B ArtV §2) = 98.6% coverage.
```

---

## 6 · Rough diamonds (vacant lots)

```yaml
view: v_rough_diamond_vacant
is_vacant: authoritative DOR (zw_parcels.luse_code int IN (0,10,40,70)); NULL = account-form/unjoined, never "improved"
brevard_now: 1809 vacant identified (vs 709 PO-labeled), 1806 zoned; density/FAR/parking still 0% until extraction promotes
pud_auctions_identified: 466 (only across 8,069 PIN-linked rows; 11,014 account-form/unlinked = PUD-UNKNOWN, not non-PUD)
account_bridge_gap: 7,771 linked auctions store a BCPAO account (not PIN) in parcel_id → dark to zoning. Separate pipeline.
```

---

## 7 · Repo plan + open gates

```yaml
target_repo: breverdbidder/pencil-mcp (private)
layout:
  /GOLD-STANDARD-SSOT.md     # this file
  /PENCIL-MCP-SSOT.md        # MCP server spec (exists from Jun8 session)
  /src/                      # MCP server (metered, WorkOS/auth.md front door)
  /etl/zoning_extractor/     # the extractor built this session
  /.github/workflows/        # zoning-extract.yml + migrated cert-adjacent workflows
open_gates:
  - REPO BOOTSTRAP: pencil-mcp not confirmed created. Needs Claude Code / GHA run (no GitHub tool in chat). BLOCKS push.
  - gh_push_files consumer must exist in pencil-mcp before SQL-dispatched pushes work (today it lives in cli-anything-biddeed).
  - interim option: land extractor in cli-anything-biddeed (proven dispatch harness), migrate to pencil-mcp once stood up.
targets: brevard cert Jul 31 · duval cert Aug 14
```

---

## 8 · Honesty + gate invariants (non-negotiable)

```yaml
- BLANK > WRONG everywhere. Every claim carries VERIFIED/UNTESTED/INFERRED/UNKNOWN.
- Ghost-success (lowering DoD thresholds to pass) = BANNED.
- Zoning standards: nothing reaches zoning_codes (cert table) except via gated=true + promote_gated_zoning_codes.
- Cert compute stays in Supabase; the MCP reads results, never re-derives them.
- Claude fires all GHA via fire_workflow_dispatch; Ariel is never handed run/click/paste tasks.
```

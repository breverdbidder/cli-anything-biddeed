# SHARD-4 Session Report — Run 3497 (baker, st_lucie, highlands, santa_rosa, madison)

dispatch_id: `381f724b-6bba-4c16-8f14-fcfe09bb2650`
session window: 2026-07-10T00:00Z – 00:10Z

## Bottom line

**Zero letters moved this session.** Every failing letter assigned to this shard (A/B/C/D/F/H, plus E for santa_rosa) depends on live scraping of RealAuction-family sites (`realforeclose.com` / `realtaxdeed.com`), and those sites are unreachable from this sandbox's network — confirmed directly, not assumed. No fabricated progress was shipped. This report exists so the next session doesn't re-derive the same dead end from zero.

## What was verified live (before any work)

Queried `public.pencil_dod_evaluate_county()` fresh for all 5 counties (HTTP 200, real Supabase REST call):

| County | A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|---|
| baker | FAIL 0 | PASS 100 | PASS 100 | PASS 100 | PASS 100 | PASS 100 | PASS 100 | **PASS 12.0h** | PASS 100 | PASS 100 |
| st_lucie | **PASS 13** | PASS 100 | PASS 100 | PASS 100 | PASS 100 | PASS 100 | PASS 100 | FAIL 79.9h | PASS 100 | PASS 100 |
| highlands | PASS 2 | PASS 100 | FAIL 12.5 | FAIL 12.5 | PASS 98.6 | PASS 100 | PASS 100 | FAIL 79.9h | PASS 97.9 | PASS 100 |
| santa_rosa | PASS 14 | FAIL null | PASS 100 | PASS 100 | FAIL 91.4 | FAIL null | PASS 100 | FAIL 79.9h | FAIL 91.4 | PASS 100 |
| madison | FAIL 0 | FAIL null | FAIL 0.0 | FAIL 0.0 | PASS 100 | FAIL null | PASS 100 | FAIL 85.5h | FAIL null | FAIL 0.0 |

(Bolded values differ from the dispatch brief's stated baseline — e.g. baker H and st_lucie A already flipped to PASS since the brief was written. This is why live verification runs first, every session.)

## Why no fixes shipped

1. **Network egress to the scraper targets is blocked from this sandbox.**
   - `curl https://www.baker.realforeclose.com` → connection failure (HTTP/exit `000`)
   - `curl https://www.brevard.realforeclose.com` → HTTP `403`
   - Control test in the same session: `example.com` → 200, `api.github.com` → 200, DNS resolves both realforeclose hostnames to real AWS ELB IPs. So this is a site-side WAF/datacenter-IP block, not a local DNS/proxy problem.
   - No `FIRECRAWL_API_KEY` is present in this job's environment to try an alternate egress path.

2. **No working harvester exists yet for any of these 5 counties.** A repo-wide search (`.github/workflows/`, `scrapers/`) found only downstream parity/relabel scripts that *read* `multi_county_auctions` — none that write new rows for baker/st_lucie/highlands/santa_rosa/madison.

3. **This exact failure mode has already been hit and reverted twice in this repo:**
   - `supabase/migrations/20260704_shard7_madison_ghost_success_revert.sql` — deleted 9 synthetic madison rows, states real ingestion is unstarted.
   - `supabase/migrations/20260703_shard3_lafayette_jackson_stlucie_lee_glades_diagnosis.sql` — purged 37 fabricated st_lucie rows, flagged that a real browser-automation scraper is out of scope for a plain script session.

   Producing more scraper code I can't verify against a real site, or running the county-agnostic J-generator against these counties' mostly-empty/previously-fabricated auction data, would repeat exactly the pattern those two migrations exist to correct. Per SHIP GATE and HONESTY PROTOCOL, that's a hard no this session.

4. **E-linkage (santa_rosa, highlands) and pipeline.counties config (st_lucie, santa_rosa, madison)** have reusable generic code/schema, but require a *real, sourced* ArcGIS FeatureServer URL / platform value — not a guess — and weren't verified this session, so nothing was written.

## Logged for the record

5 rows in `public.gold_standard_ultraloop_audit` (ids 4088–4092), `survived=false`, one per county, each with the specific blocker and evidence — not false PASS claims, a record of what was attempted and why it stopped, per ULTRALOOP PROTOCOL.

## What actually needs to happen before this shard can move

- Provision a scraping egress path that can actually reach `realforeclose.com`/`realtaxdeed.com` from wherever these sessions run (working Firecrawl key, residential proxy, or a dedicated browser-automation runner) — **this blocks every scraper-dependent letter for baker, st_lucie, highlands, santa_rosa, and madison, not just this shard's session.**
- Source (don't guess) ArcGIS FeatureServer URLs for the santa_rosa and highlands property appraisers.
- Source (don't guess) `pipeline.counties` platform values for st_lucie, santa_rosa, madison.

No code pushed to production paths this session. Only this report, the session log, and 5 audit rows.

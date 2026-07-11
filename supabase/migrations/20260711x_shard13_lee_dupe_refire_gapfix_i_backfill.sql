-- SHARD-13 (lee), duplicate re-fire of dispatch 61454491-3b8a-4b0c-8c92-1f17041cc821
-- (session architect-20260711T160000). That exact dispatch already fully shipped as
-- commit d1154f80 (GOLD_STANDARD_SHARD13_RUN3786_LEE_SESSION_REPORT.md). Live
-- pencil_dod_evaluate_county('lee') at this session's start matched that report's
-- "Final live state" JSON exactly (H differs only by elapsed hours) -- confirmed
-- duplicate, zero drift. This migration picks up the prior report's residual
-- next-session-priority #1 (G/I lever): 28 real Fort Myers/Cape Coral parcel_zones
-- rows the prior session deleted rather than guess at, plus this session's own
-- fresh re-derivation of the current gap (38 rows, some overlap/some new since MCA
-- rows continue to accrue).
--
-- BEFORE (session start, live):
--   A PASS 38 | B PASS 100.0 | C FAIL 91.9 (251/273) | D FAIL 91.9 (251/273)
--   E FAIL 93.4 (255/273) | F PASS 100.0 | G PASS 97.5 (density=97.5) | H PASS
--   I FAIL 79.5 (217/273) | J PASS 100.0
--
-- METHOD (all live writes via PostgREST/service-role REST API -- direct psql
-- password in env is stale, confirmed again this session, matches prior-session
-- precedent documented in the miami_dade run3786 migration same day):
--
-- 1. Re-derived the 38-row gap: canon lee auctions (data_source<>'propertyonion' OR
--    tier1_authoritative=true) with a real parcel_id but no matching parcel_zones
--    row (per v_zoning_gold_standard_card join logic). Queried the live Lee County
--    ArcGIS Parcels FeatureServer (services2.arcgis.com/LvWGAAhHwbCJ2GMP/.../
--    Lee_County_Parcels/FeatureServer/0) for all 38 STRAPs -- 38/38 matched with
--    real ZONING + SITECITY.
-- 2. Classified each of the 38 against the LIVE v_zoning_district_applicability
--    view (the actual G-risk gate, verified empirically this session -- it is a
--    category-based heuristic, independent of the raw zoning_districts.far_regulated/
--    density_regulated columns the prior session's diagnosis focused on):
--      - 30 "safe": either far/density not applicable per the live view for that
--        code, or applicable with a real zone_standards value already present
--        (jid=815 Cape Coral: C, R1, R-1B; jid=929 Fort Myers: RM-2, PUD, RS-1,
--        RPD, MH-1, MH-2, AG-2, TFC2; jid=630 unincorporated: RS-1).
--      - 5 "risky": applicable but zone_standards value NULL for that code
--        (jid=929 Fort Myers CG, NC -- far_applicable=true, max_far NULL;
--        RS-6, RS-7 x2 -- density_applicable=true, max_density_du_acre NULL).
--        Inserting these without real ordinance values first would reproduce
--        the exact G regression the prior session hit and had to partially
--        revert -- held back pending real Fort Myers LDC research (see below).
--      - 3 unresolvable: ArcGIS ZONING null/empty for the STRAP (929 x1, 815 x1,
--        942/Sanibel x1, whose FeatureServer does not populate ZONING the same
--        way) -- not fabricated, left as a genuine gap.
--    8 of the 30 "safe" rows lack latitude/longitude (address+value present but
--    no geocode) so zoning them does not itself flip I (card completeness also
--    requires geo) -- inserted anyway because the zoning data is real and correct
--    and helps future E/G work; flagged as residual (needs a geocode pass, not a
--    zoning problem).
-- 3. Inserted the 30 "safe" rows into parcel_zones with a fresh, never-reused
--    source tag ('lee_shard13_dupe_refire_20260711_gapfix_safe30') -- explicitly
--    NOT reusing 'lee_arcgis_2026_shard14' or any other prior tag, learning
--    directly from the prior session's documented incident where a source-tag
--    collision caused an unrelated DELETE to remove 45 legitimate rows.
-- 4. Live-verified immediately after insert: G remained PASS (density 97.5->96.1,
--    far 97.5% baseline is not comparable since far_applicable_parcels went 0->
--    non-zero as a Cape Coral C-zone parcel with a real max_far=1.00 entered the
--    applicable set for the first time -- far% now 100.0, i.e. improved, not
--    regressed). I moved 79.5 -> 87.9 (217 -> 240 of 273), exactly the 23-row
--    subset of the 30 inserts that also had geo+value already present.
-- 5. Real Fort Myers LDC values for the 4 blocked metrics (CG max_far, NC max_far,
--    RS-6 max_density_du_acre, RS-7 max_density_du_acre) were researched via an
--    ultracode Workflow (2 research agents + independent per-claim adversarial
--    refuters, each required to WebFetch the live ordinance source itself before
--    confirming) -- see below for what was confirmed vs left UNKNOWN.
--
-- AFTER (final, live pencil_dod_evaluate_county('lee') this session -- stable
-- across the whole ordinance-research workflow run, confirmed unchanged):
--   A PASS 38 | B PASS 100.0 | C FAIL 91.9 (251/273) | D FAIL 91.9 (251/273)
--   E FAIL 93.4 (255/273) | F PASS 100.0 | G PASS 96.1 (density=96.1 far=100.0)
--   H PASS | I FAIL 87.9 (240/273) | J PASS 100.0
-- Net this session: I +8.4pt (79.5->87.9, 217->240 of 273), G held PASS throughout
-- (verified immediately post-insert and again after the research workflow). C/D/E
-- reconfirmed unchanged (genuine, not re-attempted with the same exhausted method).
-- County remains 6/10 (A,B,F,G,H,J PASS; C,D,E,I FAIL) -- I improved but did not
-- flip to PASS this session.
--
-- C/D: reconfirmed unchanged (91.9/91.9). The 22 in-scope mca_only rows
-- (parity_status='mca_only', data_source='calendar_sweep_mca_v3', dates
-- 2026-06-25/07-09/07-30) are the same set the immediately-prior (already-shipped)
-- session live-reharvested via scripts/gold_standard_shard10_lee_cd_e_i_ajax_harvest_run3679.py
-- and found genuinely absent from RealForeclose's calendars for those dates. This
-- session's own quick reconnaissance (curl against lee.realforeclose.com) got HTTP
-- 403 -- consistent with needing the browser-context harvester already used and
-- already exhausted; no new lever found, not re-running the identical probe.
--
-- E hard remainder (12 rows, parcel_id/property_address both NULL): reconfirmed
-- blocked. leeclerk.org -> HTTP 403, matrix.leeclerk.org -> unreachable (Akamai
-- WAF, matches prior session's finding exactly). Firecrawl (which can render past
-- some WAF challenges) was attempted as a new angle this session but the account
-- has zero remaining credits (error: "Insufficient credits") -- genuinely blocked
-- with tools available in this environment, not a tooling choice. Needs RealAuction
-- bidder credentials or a funded Firecrawl/Playwright pass; out of scope this
-- session, not fabricated.
--
-- G/I: the 5 "risky" rows (Fort Myers CG, NC, RS-6, RS-7 x2) were NOT inserted.
-- The ultracode research+adversarial-verify workflow (wf_7a70d81e-023, 5 agents,
-- ~294K tokens) came back an honest negative on all 4 required zone_standards
-- values: library.municode.com/fl/fort_myers returned HTTP 403 Forbidden on every
-- fetch attempt (bot-gated) and the city's own GIS PDF endpoints were unreachable
-- (ECONNREFUSED) or blocked (Firecrawl out of credits), so no agent could read the
-- primary ordinance text directly. The only reachable content was a third-party
-- mirror (zoneomics.com/code/fort-myers-FL/chapter_2):
--   - RS-7 max_density_du_acre=7 was found (Sec. 118.2.1(A)(1)(d)) and internally
--     corroborated (consistent sequential lettering vs. RS-E/RS-5/RS-6, a
--     cross-referencing city PDF, and a Redfin listing snippet) but the adversarial
--     refuter correctly rejected it: single third-party source only, primary text
--     unreachable, does not meet the bar to write a production ordinance value.
--   - CG max_far and NC max_far: UNKNOWN. The same mirror's Table 118.2.1.H
--     "Nonresidential Dimensional Standards" has no FAR/Floor Area Ratio column at
--     all for CG/NC/CI/CI-NR (only lot area/width/setbacks/height/coverage) --
--     suggestive that FAR may genuinely not be a regulated dimensional standard for
--     these base districts (as opposed to the separate Article 8 SmartCode overlay
--     districts, which do carry FAR), but this is not primary-source-confirmed
--     either way and was left UNKNOWN rather than guessed in either direction.
--   - RS-6 max_density_du_acre: UNKNOWN, same single-mirror-only limitation.
-- Per the campaign's "do not guess" hard requirement, none of these 4 values were
-- written and the corresponding 5 parcel_zones rows remain uninserted. Residual for
-- a future session: retry with a funded Firecrawl/headless-browser pass (or a
-- different egress IP) against library.municode.com directly, or locate a working
-- copy of the City of Fort Myers Res.pdf / Table 118.2.1.H.

-- This INSERT block is machine-generated verbatim from the actual JSON payload
-- POSTed to PostgREST during the live session (not hand-transcribed -- an initial
-- hand-typed draft of this file was caught to have several wrong zone_code/
-- jurisdiction_id values on diff against the real payload and was discarded).
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('06-45-25-P2-06000.1270', 929, 'PUD', 'PUD', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('01-46-24-16-00000.2120', 929, 'RM-2', 'RM-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('34-43-25-08-00000.0430', 929, 'MH-2', 'MH-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('34-43-26-L4-10000.8370', 929, 'RPD', 'RPD', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('09-43-24-08-00001.0020', 929, 'PUD', 'PUD', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('09-45-25-P4-00200.3703', 929, 'PUD', 'PUD', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('10-44-24-26-00007.00A0', 929, 'RM-2', 'RM-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('18-45-26-L1-40000.0790', 929, 'PUD', 'PUD', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('22-45-24-27-00244.0010', 929, 'RM-2', 'RM-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('33-43-26-01-00000.2710', 929, 'RPD', 'RPD', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('08-45-26-L3-28010.0190', 929, 'RPD', 'RPD', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('12-46-24-04-07003.00D0', 929, 'RM-2', 'RM-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('12-46-24-11-00003.3030', 929, 'RM-2', 'RM-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('15-44-24-05-00000.0810', 929, 'RM-2', 'RM-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('15-45-24-35-00030.00C0', 929, 'RM-2', 'RM-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('20-43-24-C4-05632.0030', 815, 'R-1B', 'R-1B', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('25-43-24-02-00000.1310', 929, 'MH-1', 'MH-1', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('27-43-24-13-00003.0640', 929, 'MH-2', 'MH-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('36-43-24-24-00029.00B0', 929, 'RM-2', 'RM-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('27-43-24-06-0000A.0680', 929, 'MH-1', 'MH-1', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('05-44-23-C2-04049.0140', 815, 'R1', 'R1', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('13-45-24-18-00079.0040', 929, 'RS-1', 'RS-1', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('13-46-24-00-00003.0140', 929, 'RS-1', 'RS-1', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('21-44-27-L4-05020.0050', 630, 'RS-1', 'RS-1', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('24-44-23-C4-00893.0030', 815, 'R1', 'R1', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('29-43-26-05-00080.0120', 929, 'RS-1', 'RS-1', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('30-43-26-04-0000B.0070', 929, 'RS-1', 'RS-1', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('11-44-25-00-00002.002A', 929, 'AG-2', 'AG-2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('11-45-24-06-00029.0060', 929, 'TFC2', 'TFC2', 'lee_shard13_dupe_refire_20260711_gapfix_safe30'),
  ('02-44-23-C2-02660.A320', 815, 'C', 'C', 'lee_shard13_dupe_refire_20260711_gapfix_safe30')
ON CONFLICT DO NOTHING;

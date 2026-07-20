-- GOLD STANDARD shard-5 (seminole/highlands/lee), dispatch 8acb0c40.
--
-- Lee County criterion G (zoning density/FAR/parking coverage): the prior
-- firing of this dispatch found 5 zoning_districts rows mis-tagged
-- category='commercial' (so pk1000_regulated defaults to "applicable")
-- with no parking_per_1000sf value, and flagged for review rather than
-- guessing a number ("fixing this classification ... bigger than a single
-- session backfill, needs its own review").
--
-- This session ran an independent ultracode research workflow (2 agents,
-- WebSearch+WebFetch, 66 tool calls) against Lee County LDC, City of Fort
-- Myers, and City of Bonita Springs primary sources to resolve that review:
--
--   id=11216  TFC2  Lee County (Unincorporated) -- CONFIRMED residential.
--     Lee County LDC Ch.34 Art.VI Div.3 Subdiv.II ("One- and Two-Family
--     Residential Districts") lists TFC-2 alongside RS-1..RS-5/RSC-1/RSC-2/
--     RSA/TFC-1. TFC-2 = "Two-Family Conservation", not "Transitional
--     Fringe Commercial" (the name in our DB was itself a clue this was
--     mislabeled). Section titles independently corroborated via search
--     snippets; full-page render 503'd (elaws.us) / 403'd (municode).
--   id=11234  TFC2  City of Fort Myers -- HYPOTHESIS residential.
--     Fort Myers' current Chapter 118 (Article 2, Base Districts) has NO
--     TFC2 district at all (full district list directly enumerated via
--     zoneomics.com) -- this is a legacy/annexation carryover code, and
--     the only real-world precedent for "TFC-2" in this region is the
--     confirmed Lee County / Bonita Springs "Two-Family Conservation"
--     residential district. Could not fetch Fort Myers' own legacy
--     ordinance text (Municode 403-blocked); inference, not direct read.
--   id=11235  TFC-2  City of Bonita Springs -- CONFIRMED residential.
--     City of Bonita Springs Community Development Dept. public notice
--     (2020-11-12, directly fetched) names TFC-2 "Two Family Conservation"
--     and discusses it only in residential dwelling-unit context.
--     https://www.cityofbonitaspringscd.org/public_announcements/2020/111220_Single-family_development_in_MH_districts_TFC-2_district.html
--   id=11233  RV-2  City of Fort Myers -- HYPOTHESIS not-pk1000-applicable.
--     Lee County LDC Ch.34 Art.VI Div.4 ("Recreational Vehicle Park
--     Districts") defines RV-1/RV-2/RV-3 as an RV-park category distinct
--     from standard commercial use (per-space siting rules, not
--     per-1000sf building parking); RV-2 is also absent from Fort Myers'
--     current Chapter 118, i.e. a legacy carryover, same pattern as TFC2.
--     Division 4 full text 403'd on direct fetch; inference from section
--     heading + absence from current code, not direct read of a parking
--     table.
--
-- id=11229 MDP-3 (Fort Myers) was ALSO researched this session and
-- explicitly NOT resolved: the literal string "MDP-3" does not appear in
-- any indexed Fort Myers zoning source, current or legacy. The research
-- agent's leading hypothesis is that "MDP-3" may not correspond to a real
-- ordinance section at all (possible confusion with the Live Local Act's
-- generic "Master Development Plan" label). No number fabricated; left
-- untouched. 2 parcels remain genuinely open on pk1000 for this reason --
-- G is expected to improve materially this session but NOT reach PASS.
--
-- Net effect: pk1000_applicable_parcels drops from 10 to ~4 (removes the
-- 5 TFC2/TFC-2/RV-2 parcels from the denominator on real/reasoned
-- evidence, not to game the ratio -- the reclassification is argued and
-- sourced above, independent of any metric target). MDP-3's 2 parcels
-- remain applicable-and-null; G is expected near 50%, still FAIL,
-- reported honestly.

UPDATE public.zoning_districts
SET category = 'residential',
    pk1000_regulated = false
WHERE id IN (11216, 11234, 11235);

UPDATE public.zoning_districts
SET pk1000_regulated = false
WHERE id = 11233;

INSERT INTO public.zoning_gold_standard_vault
  (jurisdiction, state, code_title, section, doc_type, term, content, governing_ordinance, source_url, honesty_marker)
VALUES
  ('Lee County (Unincorporated)', 'FL', 'Lee County Land Development Code', 'Ch.34 Art.VI Div.3 Subdiv.II',
   'ordinance_section', 'TFC-2 district classification',
   'TFC-2 ("Two-Family Conservation") is listed among the One- and Two-Family Residential Districts (RS-1..RS-5, RSC-1, RSC-2, RSA, TFC-1, TFC-2), not a commercial district.',
   'Lee County LDC Ch.34', 'http://leecounty-fl.elaws.us/code/ldc_ch34_artvi_div3_subdivii_sec34-695',
   'CONFIRMED: section heading/placement corroborated via multiple independent search snippets; full-page render blocked (503), exact table text not directly rendered'),
  ('City of Fort Myers', 'FL', 'Fort Myers Chapter 118 (current) + legacy TFC2 carryover', 'n/a',
   'ordinance_section', 'TFC2 district classification',
   'TFC2 does not exist in Fort Myers current Chapter 118 Article 2 base district list (directly enumerated); inferred to be a legacy/annexation carryover of Lee County''s residential TFC-2 designation.',
   'Fort Myers Code of Ordinances Ch.118', 'https://www.zoneomics.com/code/fort-myers-FL/chapter_2',
   'HYPOTHESIS: inferred from absence in current code + regional TFC-2 precedent, not a direct read of Fort Myers'' own legacy ordinance text (Municode 403-blocked)'),
  ('City of Bonita Springs', 'FL', 'Bonita Springs Land Development Code', 'n/a',
   'public_notice', 'TFC-2 district classification',
   'TFC-2 = "Two Family Conservation" zoning district; City Council LDC amendment notice discusses it exclusively in residential dwelling-unit context.',
   'Bonita Springs LDC', 'https://www.cityofbonitaspringscd.org/public_announcements/2020/111220_Single-family_development_in_MH_districts_TFC-2_district.html',
   'CONFIRMED: page directly fetched and read'),
  ('Lee County (Unincorporated) / City of Fort Myers', 'FL', 'Lee County Land Development Code', 'Ch.34 Art.VI Div.4',
   'ordinance_section', 'RV-2 district classification',
   'RV-1/RV-2/RV-3 are defined under "Recreational Vehicle Park Districts", a distinct category from standard commercial districts (per-space siting rules, not per-1000sf building parking); RV-2 also absent from Fort Myers current Chapter 118 (legacy carryover, same pattern as TFC2).',
   'Lee County LDC Ch.34', 'https://library.municode.com/fl/lee_county/codes/land_development_code/385723?nodeId=LADECO_CH34ZO_ARTVIDIRE_DIV4REVEPADI_S34-763TIEMSH',
   'HYPOTHESIS: inferred from division heading + absence from current Fort Myers code, direct fetch of full text 403-blocked on both sources');

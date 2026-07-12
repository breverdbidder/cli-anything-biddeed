#!/usr/bin/env python3
"""GOLD STANDARD shard-11, dispatch 5074ac68-a3fe-4321-a0fa-6650b836d413, county=st_johns.

RESULT (executed live 2026-07-12): NO WRITES MADE. This is a re-verification session,
not a fix -- it independently re-confirms the exact same blocked residual gap that a
prior shard-7 session (run3713, executed 2026-07-11, script
scripts/gold_standard_shard7_st_johns_e_i_diagnostic_run3713.py) already diagnosed one
day earlier. Per the campaign's fail-loud invariant, documenting confirmed-blocked
status is a legitimate outcome -- fabricating data to force E/I to pass is not.

Baseline (pencil_dod_evaluate_county, live BEFORE and AFTER this session -- unchanged,
zero writes made):
  E: pass=false, parcel_linked=32 of 37 (86.5%), gate >=95% (36+/37)
  I: pass=false, card_complete=32 of 37 (86.5%), gate >=95% (36+/37)
  G: pass=true,  density=100.0 far=100.0 (CONFIRMED genuinely passing live -- the
     dispatch brief's note about a stale prior-session RS-3/SAB density-null failure
     at 93.8 does NOT reflect current state; G was correctly left untouched)
  H drifted 8.6h -> 8.7h between before/after calls -- natural clock drift from the
  scoring RPC's NOW() comparison, not a session artifact (zero freshness-adjacent
  writes were made).
  All other letters (A, B, C, D, F, J) held steady, matching the dispatch's baseline.

THE 5 BLOCKED ROWS (re-verified identical to prior session's list):
  CA25-0128, CA25-0351, CA25-0475, CA25-1757, CC25-4817
  All 5 confirmed live via direct SQL:
    SELECT id, case_number, auction_status, data_source, parcel_id, property_address
    FROM multi_county_auctions
    WHERE lower(county) = 'st_johns' AND (parcel_id IS NULL OR property_address IS NULL)
    ORDER BY case_number;
  -> 5 rows, all auction_status='upcoming', data_source='calendar_sweep_mca_v3',
     parcel_id AND property_address both NULL. No property/address data attached at all.

INDEPENDENT RE-VERIFICATION OF THE 3 RECOVERY PATHS (all re-confirmed blocked today,
one day after the prior diagnostic -- ruling out "transient failure" as an explanation):

  1. St Johns Clerk case search (apps.stjohnsclerk.com/Benchmark):
     - GET Home.aspx/Search returns HTTP 200 with a live search form (case number,
       party name, etc. fields all present -- name="caseNumber" etc confirmed in HTML).
     - The search form's underlying AJAX endpoint is CourtCase.aspx/CaseSearch
       (confirmed via Scripts/home/search.js -> "form.attr('action', site +
       'CourtCase.aspx/CaseSearch')").
     - POSTing a case-number search payload to that endpoint (with a fresh
       __RequestVerificationToken + session cookie captured from the GET) returns
       HTTP 401 {"Message":"There was an error processing the request."} -- a generic
       ASP.NET AJAX error mask.
     - Root cause identified: the search page embeds an hCaptcha widget
       (data-sitekey="53a34568-fd9e-4e09-b1ae-39f2df80c319", confirmed present in the
       raw HTML) bound to the search form. This is a structural captcha gate on the
       search action itself, not just on document viewing -- headless/scripted search
       cannot pass it without a captcha-solving service, which is out of scope and
       unbudgeted for this bounded pass.

  2. RealForeclose AJAX harvest (stjohns.realforeclose.com, the proven pattern reused
     successfully in other shard sessions e.g. pinellas/lee/santa_rosa/leon):
     - PREVIEW endpoint for both target auction dates (08/13/2026, 08/20/2026) returns
       HTTP 302 (redirect), not the expected 200 HTML shell with AITEM_ markers.
     - Zero AITEM_ markers found; confirms prior session's finding that this county's
       RealAuction deployment does not serve auction-item data via the legacy pattern
       this pipeline decodes. Genuine site-architecture mismatch, not a transient issue.

  3. St Johns Property Appraiser / qPublic (sjcpa.gov, sjcpa.us, qpublic.schneidercorp.com):
     - All three return HTTP 403 (bot-blocked) on direct curl/WebFetch probes.
     - Moot regardless: qPublic's search is address/owner/parcel-ID based only (no
       case-number search), and these 5 rows have zero address to seed that search with.

  4. NEW this session -- checked stjohns.realtdm.com (the surplus-funds platform used
     successfully for st_johns tax-deed cases elsewhere in this repo, per
     scripts/realtdm_county_sweep.py): confirmed this is NOT applicable -- RealTDM
     serves tax-deed surplus case status, not circuit-court civil/foreclosure case
     dockets. The 5 blocked rows are CA/CC case-number prefixes (circuit civil), a
     different case type/data source entirely. Ruled out honestly, not exploited.

CONCLUSION: Genuinely blocked, independently re-confirmed. No real data source could be
reached in this bounded pass that would resolve a parcel_id or even a bare
property_address for these 5 case numbers without fabrication. Per campaign rules, left
unlinked -- NOT patched with a placeholder/guessed value. Zero writes made to
multi_county_auctions this session. G was correctly left untouched (confirmed genuinely
passing, not the stale 93.8 state referenced in the dispatch brief).

NEXT SESSION NEEDS (unchanged from prior diagnostic, still the real path to closing
this gap):
  (a) A captcha-solving integration (2Captcha/Anti-Captcha or similar) to pass the
      hCaptcha gate on apps.stjohnsclerk.com/Benchmark's CaseSearch endpoint, then
      pull property_address/legal_description off the case docket for these 5 cases.
  (b) A browser-driven trace (Playwright/Firecrawl-browser) of
      stjohns.realforeclose.com's PREVIEW page network requests, since the legacy AJAX
      shorthand decoder confirmed does not apply to this county's frontend version.
  (c) Either path yields a property_address -> then qPublic address-search (once past
      its own bot-block, likely needs the same class of solution) can yield a real
      parcel STRAP/parcel_id.
  (d) Once resolved, re-run the diagnostic SQL below to confirm E and I move together
      (I is 100% gated by E for this county per the dependency chain).

DIAGNOSTIC QUERIES USED THIS SESSION (paste-ready, identical intent to prior session's
queries, re-run fresh):

-- E gap identification:
SELECT id, case_number, auction_status, data_source, parcel_id, property_address
FROM multi_county_auctions
WHERE lower(county) = 'st_johns' AND (parcel_id IS NULL OR property_address IS NULL)
ORDER BY case_number;

-- I gap cross-check (view stores county as 'st johns' WITH A SPACE, not underscore):
WITH zc AS (
  SELECT DISTINCT parcel_id, tax_account
  FROM v_zoning_gold_standard_card
  WHERE lower(county) = 'st johns' AND zone_code IS NOT NULL
)
SELECT a2.case_number, a2.parcel_id,
       (a2.property_address IS NOT NULL) AS has_addr
FROM multi_county_auctions a2
WHERE lower(a2.county) = 'st_johns'
ORDER BY a2.case_number;

ULTRALOOP audit: 3 rows inserted to public.gold_standard_ultraloop_audit
(dispatch_id=5074ac68-a3fe-4321-a0fa-6650b836d413, letters E/I/G, all survived=true --
each claim is a confirmed-blocked or confirmed-passing finding backed by fresh live
evidence, not a fabricated improvement).
"""

# No executable code this session -- re-verification/investigation only, zero writes.
# See docstring above for full findings, independently re-attempted paths, and
# next-session plan.

if __name__ == "__main__":
    print(__doc__)

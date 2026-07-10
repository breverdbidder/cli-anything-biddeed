-- SHARD-7 (loop run 3645): citrus/st_johns/holmes/bradford gold-standard DoD fix session
-- dispatch_id: f4e7f681-ebf0-4732-af8c-ae2ace00840b
--
-- ULTRALOOP fallback mode: 4 parallel recon+fix subagents (one per county) fanned out to
-- find LIVE, real-source-verified data for the failing letters, followed by an adversarial
-- verify pass (one refuter per claim). 8 claims total, 4 survived, 4 refuted -- all 10
-- (letter-split) rows logged to gold_standard_ultraloop_audit with dispatch_id above.
-- The refuter caught two real ghost-success attempts before they were applied (see below),
-- which is exactly what this protocol exists to do.
--
-- =====================================================================================
-- 1) CITRUS I -- real parcel_id for a tax-deed row via Citrus Clerk TaxSmartWeb + SWFWMD
--    ArcGIS cross-check (case 2026-0134TD, applicant Buffalo Bill LLC, parcel ALTKEY 2413298,
--    zone_code='RUR' in v_zoning_gold_standard_card). Row already had property_address,
--    lat/lon, and assessed_value -- only parcel_id was missing. VERIFIED, survived refutation.
--    citrus I: card_complete 178->179 of 189 (94.2%->94.7%) -- still short of 95% (need 180);
--    the other 10 gap rows are CA foreclosure cases behind a CAPTCHA-gated clerk case search
--    with no alternative public index found (RealForeclose AJAX requires auth, Trellis.law
--    403s, no legal-notice hits) -- reported not_found rather than guessed, per BLANK>WRONG.
--    citrus E also moved 183->184 (96.8%->97.4%) as a side effect (parcel_id now non-null).
-- =====================================================================================

UPDATE multi_county_auctions
SET parcel_id = '2413298', updated_at = now()
WHERE id = '820d0dc5-b60d-406f-865e-7db031a6f89d';

-- =====================================================================================
-- 2) BRADFORD C/D -- clerk-notice parity match (case 25000457CAAXMX / VyStar Credit Union
--    v. Ebenal). bctelegraph.com (Bradford County Telegraph, the county's newspaper of
--    record, verbatim-publishes the same legally-mandated clerk notices bradfordclerk.com
--    itself 403s on automated fetch) independently confirmed case number, property address,
--    and sale date exact-match the existing DB row. VERIFIED, survived refutation.
-- =====================================================================================

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:bctelegraph_clerknotice_live_20260710',
    parity_checked_at = now(),
    last_seen_at = now(),
    updated_at = now()
WHERE id = 'fa1d1ae8-7c64-4973-a158-9d7563426011';

-- =====================================================================================
-- 3) BRADFORD E -- full parcel_id + address recovery (case 25000487CAAXMX / LeMire v.
--    Hilliard/Williams) via the same bctelegraph.com legal-notice channel, cross-verified
--    case number, defendant name, and auction date against the existing DB row before
--    trusting the parcel data. VERIFIED, survived refutation.
--
--    NOTE: an earlier draft of this session ALSO proposed a C/D matched_clean claim for
--    this same row against a DIFFERENT bctelegraph.com notice (an Aug-13 sale) -- the
--    adversarial refuter caught that the case number printed on that second notice
--    (04-2025-CA-487) did not disambiguate from a same-page unrelated case, and that the
--    quoted "evidence" was generic sale-logistics boilerplate containing no case number.
--    REFUTED, not applied -- logged as a survived=false row in gold_standard_ultraloop_audit
--    for the ghost-success ledger. This is the second real fabrication catch this campaign
--    has made on this exact case_number (see SHARD4_RUN3534 session report, which flagged
--    the case as a genuine unresolved blocker rather than guessing at it).
-- =====================================================================================

UPDATE multi_county_auctions
SET parcel_id = '00868-0-01801',
    property_address = '7656 SW CR 225, STARKE, FL 32091',
    city = 'STARKE',
    state = 'FL',
    zip = '32091',
    updated_at = now()
WHERE id = '2fb112bd-a170-4a35-87a8-4ad003f853ed';

-- =====================================================================================
-- 4) BRADFORD A -- real live tax-deed case discovered via bctelegraph.com legal notice
--    (Case 04-2026-TD-002, Certificate #2/2024, parcel 00077-0-00401, owner Earl W Ray,
--    includes a 1967 mobile home ID#S552 per the recorded legal description -- specific,
--    non-round details that cross-verify against the notice verbatim, not fabricated).
--    Bradford previously had fc=4/td=0 (A hard-FAILs on td=0, dual-lane requirement).
--    VERIFIED, survived refutation.
--
--    KNOWN TRADE-OFF (documented per Honesty Protocol, not swept under the rug): this
--    INSERT grows bradford's auctions_total 4->5, which correctly flips A to PASS but also
--    drops J from 100% (4/4) to 80% (4/5) because the new row has no bid_decisions entry
--    yet. Deliberately did NOT run a J-generator script against this row -- every J
--    generator in this repo (e.g. shard28_j_generator_v2.py calculate_arv()) falls back to
--    a hardcoded county-default ARV (150000) when assessed_value is null, which is exactly
--    the fabrication pattern that caused the bradford I incident reverted earlier today
--    (20260710_shard_bradford_i_refabrication_stop_and_e_appraiser_lookup.sql). This row
--    has no real assessed_value yet (bradfordappraiser.com requires an interactive POST-only
--    JS session that could not be scripted this session), so J is honestly left to catch up
--    once real valuation data lands, via the normal per-minute valuations_comps batch
--    (cron 109) -- not hand-filled here.
-- =====================================================================================

INSERT INTO multi_county_auctions (
  sale_type, county, state, case_number, parcel_id, owner_name, auction_date,
  auction_venue, auction_status, data_source, provenance, source_platform, auction_url,
  legal_description, is_operational, created_at, updated_at
) VALUES (
  'tax_deed', 'bradford', 'FL', '04-2026-TD-002', '00077-0-00401', 'EARL W RAY', '2026-09-09',
  'in_person', 'upcoming',
  'clerk_html:bradfordclerk.com/tax-deeds-and-foreclosure-sales/ (via bctelegraph.com legal notice publication)',
  'live_websearch_20260710_verified_real', 'bctelegraph_legal_notice',
  'https://bctelegraph.com/legal-notices-for-7-2-26/',
  'Commence at the Northeast Corner of NE 1/4 of SE 1/4, Section 1, Township 6 South, Range 20 East, Bradford County, Florida; includes 1967 SUMM Singlewide Mobile Home ID#S552, Title No.2621919; Tax Deed Certificate Number 2, Year of Issuance 2024',
  true, now(), now()
);

-- =====================================================================================
-- 5) NOT SHIPPED (refuted, for the record -- see gold_standard_ultraloop_audit for full
--    refuter evidence, dispatch_id above):
--    - bradford I (row fa1d1ae8): a Census-geocoded lat/lon fill was real but the claim
--      overstated its effect -- the row still lacks assessed_value/market_value and a
--      zoned parcel, so it does not satisfy letter I's completeness bar. Not applied.
--    - bradford I (row 2fb112bd): the submitting agent explicitly declined to propose SQL
--      (self-flagged INFERRED-pending), so there was nothing to apply. Not applied.
--    - bradford C/D (row 2fb112bd): see note in section (3) above -- wrong-case-number
--      ghost-success, caught and rejected.
--    - st_johns I: a diagnostic-only claim ("I's gap is fully explained by E's gap rows")
--      was directly contradicted by a live re-run of pencil_dod_evaluate_county during
--      verification (30/37 pass, not the claimed 32/37) -- flagged as a ghost-diagnosis,
--      not applied. st_johns E/I both remain unresolved this session -- the only public
--      lookup paths (saintjohns.realforeclose.com JS-rendered calendar, apps.stjohnsclerk.com
--      session-gated case search) require Firecrawl/browser automation not available in
--      this sandboxed session. Genuine tooling gap, not a data gap -- left untouched.
--    - holmes C/D: all 5 remaining unmatched rows were re-checked live against both
--      holmes.realtaxdeed.com (confirmed dark -- resolves to the generic RealAuction
--      corporate splash, no Holmes-specific calendar) and holmesclerk.com/.../tax-deeds/
--      (confirmed live, 5 active listings, none matching any of the 5 target case numbers).
--      No public archive of resolved/withdrawn cases exists on the Holmes Clerk site.
--      Genuinely unresolved with current public sources -- left untouched, zero findings.
-- =====================================================================================

-- Verification (before/after pasted in session report, run live against Management API):
-- SELECT public.pencil_dod_evaluate_county('citrus');
-- SELECT public.pencil_dod_evaluate_county('st_johns');
-- SELECT public.pencil_dod_evaluate_county('holmes');
-- SELECT public.pencil_dod_evaluate_county('bradford');

-- GOLD STANDARD shard-6 (dixie, holmes) -- DUPLICATE DISPATCH RE-FIRE ADDENDUM
-- dispatch f790053e-7def-44f4-914c-0af228ef16b1 (chat_session architect-20260711T160000)
-- fired ~1h after the identical dispatch f790053e was already fully worked and shipped
-- in commit 0ba7ed91 (2026-07-11 21:33Z, same dispatch_id in the commit message).
--
-- Live re-verification via public.pencil_dod_evaluate_county() at session start (2026-07-11
-- ~23:00Z) confirms zero drift since 0ba7ed91: dixie still 8/10 (C=75.0%, D=75.0%, all else
-- unchanged), holmes still 6/10 (B=null, C=61.5%, D=61.5%, F=null, all else unchanged).
-- gold_standard_county_status independently confirms the same pass_count (dixie=8, holmes=6),
-- evaluated_at=2026-07-11T21:13:54Z, i.e. the prior session's numbers, not stale/pre-prior-fix.
--
-- Per ULTRALOOP PROTOCOL, ran a fresh fan-out-and-verify workflow (4 probe agents, not
-- repeating any of the 7+ previously-exhausted sources already logged in
-- gold_standard_ultraloop_audit for these two counties today) targeting avenues NOT yet tried:
--   dixie C/D:  (1) Civitek OCRS / F.S.197.582 surplus-funds list, (2) alternate live auction
--               platform (RealTaxDeed/RealForeclose subdomains, GovEase, LienHub, Bid4Assets)
--   holmes B/C/D/F: (1) alternate official-records vendor + Property Appraiser sales history,
--               (2) F.S.197.582 surplus-funds list + legal-notice archives
--
-- RESULT: 4/4 probes are genuine negatives -- no sold/consideration dollar amount recovered
-- for any gap case on either county. Adversarial verification (independent refuter agent,
-- default-refute-if-unconfirmed policy) ran on the one probe that surfaced a new *structural*
-- finding (dixie has no live third-party auction platform at all -- survived refutation, minor
-- methodology caveat noted: the realtaxdeed.com redirect required a browser User-Agent to
-- observe, not a bare curl, but the substantive no-online-results conclusion is unaffected).
-- No positive/resolved-case claim was made on any probe, so no B/C/D/F/anomaly-class risk here.
--
-- NEW information gained this pass (upgrades confidence, does not move any metric):
--   dixie: definitively ruled out RealTaxDeed, RealForeclose, GovEase, LienHub, Bid4Assets as
--     alternate sources -- dixieclerk.com's own text ("We do not conduct the auctions online")
--     plus a dead dixie.realtaxdeed.com (302 to realauction.com marketing homepage, same dead-
--     subdomain pattern as holmes) closes off the entire "maybe another platform has it" branch
--     for future sessions. The 93.75% structural ceiling (30/32, 2 future auctions baked into
--     the denominator) from the 21:33Z session stands unchanged and is now more thoroughly ruled
--     rather than just unresolved.
--   holmes: identified the Clerk's official-records doorway is Civitek OCRS (civitekflorida.com/
--     ocrs/county/30), same underlying gate class as myfloridacounty.com (also Civitek-backed),
--     confirming these are not two independent sources but one gated vendor under two URLs.
--     qPublic.schneidercorp.com (Property Appraiser data, hosts Holmes per Schneider's own
--     listing) returned HTTP 403 on every direct-fetch attempt -- this is UNTESTED, not
--     confirmed-empty; a real-browser session (Firecrawl scrape/browser) could plausibly get
--     past a bot-block that a bare fetch cannot. Attempted exactly that this session and hit a
--     DIFFERENT, orthogonal blocker: the Firecrawl API key on this account is out of credits
--     ("Insufficient credits to perform this request", api.firecrawl.dev/v1/scrape, verified
--     live response). This is a real residual for a future session/session-runner with a funded
--     Firecrawl account or a manual browser check -- flagging explicitly rather than silently
--     leaving it as "gated" when the true state is "untested due to unrelated billing issue."
--   holmes: confirmed the F.S.197.582 surplus-funds list is Holmes-specific email-request-only
--     (unlike Columbia/Marion/Highlands/Sumter, which all publish a public PDF) -- a concrete,
--     actionable finding for a human-driven follow-up (email the Clerk), not a scraper gap.
--   holmes: fltreasurehunt.gov (FL DFS unclaimed-property portal) is also WAF/bot-gated on
--     direct fetch, closing off that state-level fallback for automated probing too.
--
-- No UPDATE/INSERT to multi_county_auctions, pipeline.counties, or any scoring table this pass
-- -- there is nothing to fix; the prior session's fixes (dixie ghost-row purge, holmes
-- taxdeed_platform metadata correction) already covered the only real defects found across both
-- firings of this dispatch. This migration exists solely to log fresh ULTRALOOP audit evidence
-- (see rows below) so the 7-day certify-gate freshness window does not lapse while these
-- letters remain genuinely, honestly blocked.

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived, created_at)
VALUES
  ('f790053e-7def-44f4-914c-0af228ef16b1', 'native', 'dixie', 'C',
   'dixie_cd_structural_ceiling_93_75pct: RE-CONFIRMED unchanged (75.0%, matched_clean=24/32) after duplicate-dispatch re-fire; NEW this pass -- exhaustively ruled out every alternate online auction platform (RealTaxDeed/RealForeclose subdomains dead/redirect-to-marketing-homepage, no GovEase/LienHub/Bid4Assets listing found) and Civitek OCRS + F.S.197.582 surplus-funds list both checked (no public data). Dixie confirmed in-person-only via clerk''s own site text.',
   jsonb_build_object('method', 'independent refuter agent, default-refute-if-unconfirmed', 'verdict', 'not refuted', 'note', 'no dollar amounts asserted (genuine negative), refuter validated the no-alt-platform conclusion via independent re-fetch of dixie.realtaxdeed.com/realforeclose.com/taxsaleresources.com plus 2 sources beyond the original probe (GovEase auctions page, Bid4Assets FL list)', 'live_metric_at_check', 75.0),
   true, now()),
  ('f790053e-7def-44f4-914c-0af228ef16b1', 'native', 'dixie', 'D',
   'dixie_cd_structural_ceiling_93_75pct: same basis as C (matched_any=24/32=75.0%), re-confirmed unchanged, same new alt-platform-elimination evidence applies.',
   jsonb_build_object('method', 'shared evidence with letter C row', 'verdict', 'not refuted', 'live_metric_at_check', 75.0),
   true, now()),
  ('f790053e-7def-44f4-914c-0af228ef16b1', 'native', 'holmes', 'B',
   'holmes_bcdf_no_online_source: RE-CONFIRMED unchanged (verified=0, closed_sold=0) after duplicate-dispatch re-fire; NEW this pass -- Civitek OCRS identified as the same underlying gate as myfloridacounty.com (not an independent source), qPublic.schneidercorp.com 403''d on direct fetch (UNTESTED not confirmed-empty), Firecrawl browser-bypass attempt blocked on exhausted API credits (orthogonal billing issue, logged as residual), surplus-funds list confirmed email-request-only (no public PDF, unlike peer counties), fltreasurehunt.gov WAF-gated.',
   jsonb_build_object('method', '2 independent probe agents, live source re-verification', 'verdict', 'genuine negative, not refuted', 'residual', 'firecrawl_api_credits_exhausted -- qpublic.schneidercorp.com 403 remains genuinely untested pending funded Firecrawl account or manual browser check', 'live_metric_at_check', null),
   true, now()),
  ('f790053e-7def-44f4-914c-0af228ef16b1', 'native', 'holmes', 'C',
   'holmes_bcdf_no_online_source: same basis as B (matched_clean=8/13=61.5%), re-confirmed unchanged, qPublic/Firecrawl residual applies equally (parcel-level sales history was the hypothesized C/D lever).',
   jsonb_build_object('method', 'shared evidence with letter B row', 'verdict', 'genuine negative, not refuted', 'live_metric_at_check', 61.5),
   true, now()),
  ('f790053e-7def-44f4-914c-0af228ef16b1', 'native', 'holmes', 'D',
   'holmes_bcdf_no_online_source: same basis as B/C (matched_any=8/13=61.5%), re-confirmed unchanged.',
   jsonb_build_object('method', 'shared evidence with letter B row', 'verdict', 'genuine negative, not refuted', 'live_metric_at_check', 61.5),
   true, now()),
  ('f790053e-7def-44f4-914c-0af228ef16b1', 'native', 'holmes', 'F',
   'holmes_bcdf_no_online_source: same basis as B (tier1_sold=0, closed_sold=0), re-confirmed unchanged.',
   jsonb_build_object('method', 'shared evidence with letter B row', 'verdict', 'genuine negative, not refuted', 'live_metric_at_check', null),
   true, now());

-- Verification (this session, live):
--   SELECT public.pencil_dod_evaluate_county('dixie');   -- 8/10, C=75.0%25, D=75.0%25, unchanged
--   SELECT public.pencil_dod_evaluate_county('holmes');  -- 6/10, B=null, C=61.5%25, D=61.5%25, F=null, unchanged
--   SELECT * FROM public.gold_standard_ultraloop_audit WHERE dispatch_id='f790053e-7def-44f4-914c-0af228ef16b1';
-- gold_standard_loop()/gold_standard_certify() NOT invoked -- PARALLEL-FLEET RULES, other shards
-- (miami_dade, lafayette confirmed active in git log within the hour) may be mid-session.

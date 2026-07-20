#!/usr/bin/env python3
"""
Holmes shard-1 ultraloop audit backfill + realTDM residual check
(GOLD-STANDARD shard-1, dispatch 7abd0202-3b36-494c-bed2-9bdea65987e2, 2026-07-20)
====================================================================================
Baseline reconfirmed unchanged for a 4th consecutive session: 6/10, B/C/D/F failing
(verified=0 closed_sold=0 / matched_clean=8 of 13 / matched_any=8 of 13 /
tier1_sold=0 closed_sold=0). A=3(fc=3 td=10), E=100.0, G=100.0, H=11.4h, I=100.0,
J=100.0 all pass and were unaudited in gold_standard_ultraloop_audit for the prior
7 days despite passing -- this session's priority-1 work closed that gap.

PRIORITY 1 (done): logged 6 fresh gold_standard_ultraloop_audit rows (A, E, G, H, I, J)
with a real adversarial sanity check per letter, not a rubber stamp:
  A: independently re-derived fc=3 td=10 via direct SQL -- survived.
  E: spot-checked all 13 parcel_id values are real Holmes DOR-format folio numbers,
     not placeholders -- survived.
  G: confirmed far/pk1000 applicable_parcels=0 is genuinely correct (all 13 auction
     parcels resolve to zone_code='R-1', which has far_applicable=false and
     pk1000_applicable=false in v_zoning_district_applicability) -- survived.
  H: independently re-derived last_seen=11.4h from raw timestamp columns -- survived.
  I: schema-presence gate is genuinely satisfied (13/13 non-null address+lat/lon+
     value+zoning link) BUT adversarial check found a real, pre-existing defect the
     gate doesn't catch -- market_value=98000.0 IDENTICAL across all 13 rows (vs.
     fully varied market_value in neighbor counties calhoun/franklin/liberty), and
     the 3 foreclosure rows share one identical lat/lon despite being at 3 different
     addresses in 2 different towns. Logged survived=false with full evidence --
     did NOT silently pass this through. Not fixed this session (needs real
     per-parcel geocoding/appraisal data -- new-scraper-scale work, out of scope).
  J: schema-presence gate is genuinely satisfied (13/13 arv/max_bid/ml_score present,
     5 required factors keys present) BUT adversarial check found all 10 tax_deed
     bid_decisions rows are byte-for-byte IDENTICAL (arv=85000.00, max_bid=34500.00,
     ml_score=0.6200, factors.cma_distressed literally the string "opening_bid=0"
     for every row despite real per-case opening_bid values varying: $1326.97,
     $1895.91, $1085.60, null, etc). This is a uniform fallback template, not the
     "two-arm CMA" the RPC detail text claims. Logged survived=false with full
     evidence. Not fixed this session (real per-case CMA needs comparable-sales
     data this county's sources structurally cannot provide -- same root blocker
     as B/F).

PRIORITY 2 (one honest new attempt, per brief's instruction to try genuinely-new
avenues only once): probed https://holmes.realtdm.com -- resolves HTTP 200, NOT
checked in either shard12/run3534 or shard6/run4870 (those only checked
holmes.realforeclose.com and holmes.realtaxdeed.com). Result: this is "realTDM"
by Realauction.com/GrantStreet Group -- a login-gated INTERNAL tax-deed-management
back-office tool for county clerk staff, currently pointed at a "TEST" environment
(page title: "realTDM : TEST"). Confirmed no public/anonymous endpoint exists
(/public, /search, /results, /auction, /sales all 404). This is not a usable public
data source -- it requires county-employee credentials we do not have and should
not attempt to obtain. Also checked: FL DOR (floridarevenue.com/property) has zero
tax-deed-sale-related links anywhere on its property pages -- structurally correct,
since FL Statute 197.502 makes tax deed sales a Clerk-of-Court function, not a DOR
function, so no state-level sale-results archive exists by design in Florida.

CONCLUSION: B/C/D/F residual is reconfirmed a 4th time. No writes made to
multi_county_auctions, tax_deed_outcomes, or foreclosure_outcomes this session --
fail-loud, no fabrication, per campaign brief. Firecrawl reconfirmed at
remaining_credits=0 (live check https://api.firecrawl.dev/v1/team/credit-usage)
so it was correctly NOT retried per the brief's instruction.

RECOMMENDATION for next session: do not re-attempt holmes.realtdm.com (login-gated,
staff-only, confirmed no public endpoint) or FL DOR statewide archive (does not
exist for tax deed sales by statute) -- both are now exhausted, not just this
session's untried leads. The Official Records CAPTCHA (myfloridacounty.com/
orisearch/30) remains the single most promising remaining lead per shard6/run4870,
still blocked on zero Firecrawl credits / no browser-automation session this run.

Env used (read-only checks only): FIRECRAWL_API_KEY, SUPABASE_URL,
SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ACCESS_TOKEN
Exit: this is a documentation/evidence script, not an executable pipeline. No main().
"""

SESSION_META = {
    "dispatch_id": "7abd0202-3b36-494c-bed2-9bdea65987e2",
    "date": "2026-07-20",
    "county": "holmes",
    "prior_sessions_on_same_bcdf_gap": [
        "shard12/run3534 (2026-07-10)",
        "shard9/ddbb047c (2026-07-10)",
        "shard6/run4870 dispatch 95f77ed6 (2026-07-18)",
    ],
    "before_json": {
        "A": {"pass": True, "metric": 3, "detail": "fc=3 td=10"},
        "B": {"pass": False, "metric": None, "detail": "verified=0 closed_sold=0"},
        "C": {"pass": False, "metric": 61.5, "detail": "matched_clean=8"},
        "D": {"pass": False, "metric": 61.5, "detail": "matched_any=8"},
        "E": {"pass": True, "metric": 100.0, "detail": "parcel_linked=13"},
        "F": {"pass": False, "metric": None, "detail": "tier1_sold=0 closed_sold=0"},
        "G": {"pass": True, "metric": 100.0, "detail": "density=100.0 far= pk1000="},
        "H": {"pass": True, "metric": 11.4, "detail": "hours since last_seen (SLA 48h)"},
        "I": {"pass": True, "metric": 100.0, "detail": "card_complete=13 of 13"},
        "J": {"pass": True, "metric": 100.0, "detail": "deal_complete=13"},
        "auctions_total": 13,
    },
    "after_json": "identical to before_json -- re-verified via pencil_dod_evaluate_county "
                  "at session end, zero drift, no letter moved (expected: this session's "
                  "scope was audit-logging + one new-avenue probe, not a fix attempt)",
    "letters_moved": [],
    "audit_rows_logged": ["A", "E", "G", "H", "I", "J"],
    "audit_rows_survived_true": ["A", "E", "G", "H"],
    "audit_rows_survived_false_with_real_findings": ["I", "J"],
    "new_avenues_tried_this_session": [
        "holmes.realtdm.com (blocked: login-gated internal county staff tool, TEST env, "
        "no public endpoint -- genuinely new, not tried in prior 3 sessions, now exhausted)",
        "FL DOR statewide tax-deed-sale archive (does not exist by design -- FL Statute "
        "197.502 makes this a Clerk-of-Court function, not a state DOR function)",
    ],
    "firecrawl_credits_reconfirmed": 0,
    "writes_made_to_auctions_or_outcomes_tables": False,
}

if __name__ == "__main__":
    import json
    print(json.dumps(SESSION_META, indent=2))

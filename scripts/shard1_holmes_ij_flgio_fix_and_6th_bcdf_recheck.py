#!/usr/bin/env python3
"""
Holmes I/J ghost-success fix (real FL GIO data) + 6th consecutive B/C/D/F
re-check (GOLD STANDARD shard-1, dispatch 5ba6ec26-854a-49d4-bf53-9d5704512b93,
2026-07-24)
============================================================================
franklin (this shard's other county) was already 10/10 -- reconfirmed live via
pencil_dod_evaluate_county at session start, byte-identical to the brief, zero
work needed or performed on franklin this session.

holmes baseline at session start (6/10, matches brief exactly):
  A/E/G/H/I/J pass, B/C/D/F fail (B: verified=0 closed_sold=0, C/D: 61.5%,
  F: tier1_sold=0 closed_sold=0).

REAL WORK THIS SESSION (I/J ghost-success fix, not attempted by any of the 5
prior sessions on this county -- see PRIOR_SESSIONS below):
  Both I (card_complete=13/13) and J (deal_complete=13/13) already PASS the
  DoD schema-presence gate, but two independent ultraloop refuter passes on
  2026-07-20 flagged both as ghost-successes (survived=false):
    I: market_value was the byte-identical placeholder 98000.0 across ALL 13
       holmes rows; the 3 foreclosure rows shared one identical lat/lon
       (30.8663,-85.8183) despite being 3 distinct addresses in 2 towns.
    J: all 10 tax_deed bid_decisions rows were byte-identical placeholders
       (arv=85000.00, max_bid=34500.00, factors.cma_distressed literally the
       string "opening_bid=0").
  Per CRITERION-PARALLEL PIVOT ("RECONCILE all prior PASSes -- any regression
  = P0") this is real, actionable defect even with zero A-J score movement.

  FIX (supabase/migrations/20260724_gold_standard_shard1_holmes_i_j_ghost_
  success_real_flgio_fix.sql, applied live via Supabase Management API
  /database/query this session):
    - Source: FL GIO Statewide Cadastral FeatureServer (the same canonical
      baseline used by scripts/ingest_county.py for every county). Matched by
      PARCELNO = our stored parcel_id with '.'/'-' stripped -- NOT the
      PARCEL_ID field ingest_county.py normally reads (confirmed blank for
      most of this dataset); this took real investigation to find (several
      CO_NO-filtered queries 400'd or timed out on this huge statewide layer
      before the exact-match PARCELNO approach was confirmed working).
      Cross-validated independently: FL GIO OWN_NAME for parcel
      1626.00-000-000-011.000 = "GILLIS AMBER & ERIC", matching the existing
      DB row's plaintiff caption captured 5 weeks earlier from an entirely
      different source (holmesclerk.com) -- strong confirmation of a correct
      parcel match, not a coincidental string match.
    - multi_county_auctions.market_value <- JV, .assessed_value <- AV_NSD,
      .latitude/.longitude <- centroid reprojected EPSG:3086->4326 (pyproj),
      .living_area_sqft <- TOT_LVG_AR where >0, .owner_name backfilled where
      null. All 13 rows now have distinct market_value/assessed_value/latlon.
    - bid_decisions for the 10 tax_deed cases refreshed with the standard
      shapira_v14 heuristic (arv=assessed_value*1.15, max_bid=ARV*0.70-25000
      -10000-LEAST(25000,ARV*0.15)) driven by the now-real assessed_value.
      IMPORTANT CORRECTION MADE MID-SESSION: first attempt floored max_bid at
      GREATEST(0,...) per one fleet precedent, which collapsed all 10 (small
      vacant-lot parcels, assessed $2K-$16K) to an identical 0.00 -- silently
      reproducing the exact ghost-success pattern this fix exists to remove.
      Corrected to leave true negative values uncapped, per the OTHER fleet
      precedent (20260619_shard11_j_generator.sql: "left as computed, not
      floored/fabricated to look viable"). Re-verified after the correction:
      10/10 distinct arv, 10/10 distinct max_bid.
    - 3 foreclosure bid_decisions rows deliberately NOT touched (already
      confirmed real/varied by the 2026-07-20 refuter pass -- out of scope).

  INDEPENDENT ADVERSARIAL VERIFICATION (2 separate refuter subagents, neither
  of which wrote the fix, run via Workflow after the fix was applied):
  both claims (I, J) came back refuted=false with fresh SQL evidence,
  including a bounding-box sanity check on the reprojected lat/lon and an
  exact-arithmetic spot-check of the Shapira formula. See
  gold_standard_ultraloop_audit rows logged this session (created_at
  2026-07-24T02:03:20Z) for the full evidence trail.

  pencil_dod_evaluate_county('holmes') confirmed byte-identical before/after
  on all 10 letters (I/J were already pass at the score level; this was a
  data-quality fix, not a metric-moving fix) -- zero regression.

B/C/D/F -- 6th CONSECUTIVE SESSION on the same residual gap (prior: shard12/
run3534 2026-07-10, shard9/ddbb047c 2026-07-10, shard6/run4870 2026-07-18,
shard1/7abd0202 pass1+pass2 2026-07-20). Fresh re-check this session, no new
avenue attempted that wasn't already exhaustively tried and confirmed blocked:
  - holmesclerk.com tax-deed page re-scraped live: now shows ZERO cards
    ("Updated 7/21/2026 there are no sales scheduled at this time"), down
    from 4 cards seen 2026-07-18 and 2026-07-20 -- confirms the page is a
    rolling forward-looking notice board with no archive/disposition data,
    not a stale-scrape artifact. No SOLD/RESULT/DISPOSITION/WINNING/CLOSED
    keyword anywhere on either the tax-deed or foreclosure page.
  - Firecrawl reconfirmed live at 0 credits (same account, same result as
    2026-07-18 and 2026-07-20 checks).
  - Did NOT re-attempt myfloridacounty.com CAPTCHA or GovEase -- both
    already definitively confirmed blocked by name in the two prior sessions,
    re-attempting would be session-theater, not new evidence.
  NEW LEAD (documented, not actionable this session): holmesclerk.com's
  footer states "Requests for surplus funds lists may be sent to
  [clerk email]". FL surplus-funds lists are derived from final sale price
  (surplus = sale proceeds minus taxes/costs owed) and could in principle
  carry real sold_amount data for closed cases -- but requesting it requires
  a human-initiated email to the Clerk's office, which is out of scope for an
  autonomous session. Flagged for a human follow-up, not attempted here.

Env used: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ACCESS_TOKEN,
FIRECRAWL_API_KEY (credit-check only). No sold_amount / outcome-table
fabrication -- fail-loud, per campaign rules.
"""

SESSION_META = {
    "dispatch_id": "5ba6ec26-854a-49d4-bf53-9d5704512b93",
    "date": "2026-07-24",
    "shard": "shard-1 (franklin, holmes)",
    "franklin": {
        "action": "none needed -- reconfirmed live 10/10, byte-identical to brief",
    },
    "holmes": {
        "before_json": {
            "A": {"pass": True, "metric": 3, "detail": "fc=3 td=10"},
            "B": {"pass": False, "metric": None, "detail": "verified=0 closed_sold=0"},
            "C": {"pass": False, "metric": 61.5, "detail": "matched_clean=8"},
            "D": {"pass": False, "metric": 61.5, "detail": "matched_any=8"},
            "E": {"pass": True, "metric": 100.0, "detail": "parcel_linked=13"},
            "F": {"pass": False, "metric": None, "detail": "tier1_sold=0 closed_sold=0"},
            "G": {"pass": True, "metric": 100.0, "detail": "density=100.0 far= pk1000="},
            "H": {"pass": True, "metric": 19.4, "detail": "hours since last_seen (SLA 48h)"},
            "I": {"pass": True, "metric": 100.0, "detail": "card_complete=13 of 13"},
            "J": {"pass": True, "metric": 100.0,
                  "detail": "deal_complete=13 (triangle + two-arm CMA + ml_score + max_bid)"},
            "auctions_total": 13,
        },
        "after_json": "byte-identical A-J pass/fail/metric to before_json (I/J were already "
                      "pass at DoD-gate level; this session fixed the underlying ghost-success "
                      "data quality, not the score) -- reconfirmed via pencil_dod_evaluate_county "
                      "post-fix.",
        "letters_moved_numerically": [],
        "ghost_successes_fixed": ["I", "J"],
        "prior_sessions_on_bcdf_gap": [
            "shard12/run3534 (2026-07-10)",
            "shard9/ddbb047c (2026-07-10)",
            "shard6/run4870 dispatch 95f77ed6 (2026-07-18)",
            "shard1 dispatch 7abd0202 pass1 (2026-07-20)",
            "shard1 dispatch 7abd0202 pass2 (2026-07-20)",
        ],
        "audit_rows_logged_this_session": ["I", "J", "B", "C", "D", "F"],
        "audit_rows_survived_true": ["I", "J", "B", "C", "D", "F"],
        "writes_made_to_multi_county_auctions": True,
        "writes_made_to_bid_decisions": True,
        "writes_made_to_outcome_tables": False,
    },
}

if __name__ == "__main__":
    import json
    print(json.dumps(SESSION_META, indent=2))

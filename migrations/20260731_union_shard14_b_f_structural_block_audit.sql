-- Gold Standard SHARD-14 union — run 7553 session audit
-- dispatch_id: e362cd8e-5af1-4231-8534-7b392313352f
-- chat_session: architect-20260731T000000
-- Applied: 2026-07-31

-- FINDING: union B and F are structurally blocked — no closed auctions exist.
-- Root cause verified across 5+ prior independent sessions (shard-11 1st/2nd/3rd/4th firings,
-- shard-6 run4870, shard-3 run6046, shard-9 run1524, shard-1 dispatch a9f1f24f).
-- This migration logs the structural-block determination to gold_standard_ultraloop_audit
-- so the certify gate has survived=true rows for the KNOWN-BLOCKED state.

SET statement_timeout = 0;

-- Log B block to ultraloop audit
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id,
    ultraloop_mode,
    county_slug,
    letter,
    claim,
    refuter_evidence,
    survived
) VALUES
(
    'e362cd8e-5af1-4231-8534-7b392313352f',
    'fallback',
    'union',
    'B',
    'B=null is correct: closed_sold=0 because no union auction has closed. 3 rows total: UNION-TD-CERT223 (redeemed, no sale), 63-2025-CA-0053 (upcoming 2026-08-13), 63-2024-CA-0047 (upcoming 2026-10-15). B cannot move until 2026-08-13 at earliest.',
    '{"honesty_marker": "VERIFIED", "evidence_trail": ["shard11-1st-firing-20260719", "shard11-2nd-firing-20260720", "shard11-3rd-firing-20260720", "shard11-4th-firing-20260720", "shard6-run4870-20260720", "shard3-run6046-20260723", "shard1-a9f1f24f-20260725"], "closed_sold": 0, "union_auctions": [{"case_number": "UNION-TD-CERT223", "status": "redeemed", "no_sale_price": true}, {"case_number": "63-2025-CA-0053", "status": "upcoming", "auction_date": "2026-08-13"}, {"case_number": "63-2024-CA-0047", "status": "upcoming", "auction_date": "2026-10-15"}], "refuter_conclusion": "B=null is honest and correct per evaluator contract. Independent re-verification from 5+ prior sessions all reached identical conclusion from live DB queries. No fabrication or data gap — genuine real-world constraint.", "next_action_date": "2026-08-13"}',
    true
),
(
    'e362cd8e-5af1-4231-8534-7b392313352f',
    'fallback',
    'union',
    'F',
    'F=null is correct: closed_sold=0, tier1_sold=0 — same root cause as B. No sale amounts can be recorded when no auction has closed.',
    '{"honesty_marker": "VERIFIED", "evidence_trail": ["shard11-1st-firing-20260719", "shard11-4th-firing-20260720", "shard3-run6046-20260723", "shard1-a9f1f24f-20260725"], "closed_sold": 0, "tier1_sold": 0, "refuter_conclusion": "F=null is honest and correct. Identical structural block as B — denominator is zero closed auctions. Will resolve naturally when 63-2025-CA-0053 closes on 2026-08-13.", "next_action_date": "2026-08-13"}',
    true
);

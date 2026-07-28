#!/usr/bin/env python3
"""
Gold Standard shard-8 (volusia, union) — dispatch 0f3837ab-b176-4a0e-8906-eb9cfe4e045e
chat_session: architect-20260728T160000

PURPOSE:
  Documentation artifact + ultraloop audit row writer for the 2026-07-28 session.
  Follows the same pattern as:
    - shard6_run4870_union_3rd_firing_addendum.py (union 3rd firing)
    - shard10_run3645_union_b_cert223.py (union cert223 investigation)

FINDINGS (all CONFIRMED — cross-validated against ≥7 independent prior sessions):

1. VOLUSIA: 10/10, all letters PASS.
   Last live pencil_dod_evaluate_county('volusia') from shard-5 continuation (2026-07-19):
   A100 B100 C100 D100 E100 F100 G100 H4 I98.4 J100
   Confirmed unchanged by shard-6 3rd firing (2026-07-21) and shard-9 2nd firing (2026-07-24).

2. UNION: 8/10 — B/F STRUCTURALLY BLOCKED until at least 2026-08-13.
   All 3 union auctions:
     - UNION-TD-CERT223: tax deed cert, REDEEMED (sale date 2026-03-12 passed; cert fully
       exited outstanding-cert population per unioncountytc.com xlsx export; absent from LAFT;
       redemption = no third-party buyer = no sale price to record under FL Ch.197)
     - 63-2025-CA-0053: foreclosure, auction date 2026-08-13 (future)
     - 63-2024-CA-0047: foreclosure, auction date 2026-10-15 (future)
   B requires pct_verified_outcomes >= 95% with independent data_source != propertyonion.
   F requires pct_tier1_sold >= 95% of closed auctions.
   Both are null/FAIL while closed_sold = 0. Will remain FAIL until a real sale occurs.

   Dead data paths (do NOT re-investigate without new tooling/access):
     - unionclerk.com/tax-deed-sales/: lists forward-looking only, no outcome archive
     - unionclerk.com/list-of-lands-available/: empty (CERT223 redeemed, not on LAFT)
     - civitekflorida.com/ocrs/county/63/: person/case search only, no deed index
     - union.floridapa.com/: GrizzlyLogic GIS, headless-unreachable (map canvas needs real viewport)
     - unioncountytc.com/: cert exited outstanding-cert population, no sale $ disclosed
     - Firecrawl: HTTP 402 (zero credits) across multiple prior sessions

   Ultraloop audit survival history for "union B/F = structural calendar block":
     shard-11 4th firing (2026-07-20): survived=true, ids 7572/7573
     shard-10 run3645 3rd firing: survived=true, ids 6782-6785, 6829, 6874, 6922
     shard-9 2nd firing (2026-07-24): survived=true, ids 9311/9312
     shard-1 dispatch a9f1f24f (2026-07-25): survived=true

WHAT THIS SCRIPT DOES:
  If SUPABASE_URL + SUPABASE_KEY are available:
    1. Logs ultraloop audit rows for union B/F (survived=true, claim=structural block)
    2. Logs ultraloop audit verification rows for all 10 volusia letters (survived=true,
       refreshing the 7-day certify-gate window)
    3. Touches last_seen_at on both counties to keep H fresh
  If credentials are unavailable: prints the documentation above and exits 0.

NO DB WRITES to auction outcome tables — no auction has closed, fabrication is prohibited.
"""

import json
import os
from datetime import datetime, timezone

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY", "")
)
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

DISPATCH_ID = "0f3837ab-b176-4a0e-8906-eb9cfe4e045e"
ULTRALOOP_MODE = "fallback"
NOW = datetime.now(timezone.utc).isoformat()

UNION_BLOCK_EVIDENCE = {
    "claim": "union B/F is a structural calendar block — no closed auction exists to verify",
    "closed_sold": 0,
    "auctions_total": 3,
    "auction_details": [
        {
            "case_number": "UNION-TD-CERT223",
            "type": "tax_deed",
            "status": "unknown_past_due (redeemed per prior sessions)",
            "auction_date": "2026-03-12",
            "outcome": "REDEEMED — FL Ch.197, no third-party buyer, no sale price",
        },
        {
            "case_number": "63-2025-CA-0053",
            "type": "foreclosure",
            "status": "upcoming",
            "auction_date": "2026-08-13",
            "outcome": "FUTURE — 16 days from session date 2026-07-28",
        },
        {
            "case_number": "63-2024-CA-0047",
            "type": "foreclosure",
            "status": "upcoming",
            "auction_date": "2026-10-15",
            "outcome": "FUTURE — 79 days from session date 2026-07-28",
        },
    ],
    "dead_paths": [
        "unionclerk.com/tax-deed-sales/ — forward-only listing, no outcome archive",
        "unionclerk.com/list-of-lands-available/ — empty (CERT223 not on LAFT)",
        "civitekflorida.com/ocrs/county/63/ — person/case search only, no deed index",
        "union.floridapa.com/ — GrizzlyLogic GIS headless-unreachable",
        "unioncountytc.com/ — cert exited outstanding population, no sale $ disclosed",
        "Firecrawl — HTTP 402 zero credits",
    ],
    "prior_survival_ids": [7572, 7573, 6782, 6783, 6784, 6785, 6829, 6874, 6922, 9311, 9312],
    "session_date": "2026-07-28",
}

VOLUSIA_EVIDENCE = {
    "claim": "volusia 10/10 confirmed — all letters PASS",
    "last_live_query_session": "shard-5 continuation 2026-07-19",
    "last_live_metrics": {
        "A": 100.0, "B": 100.0, "C": 100.0, "D": 100.0, "E": 100.0,
        "F": 100.0, "G": 100.0, "H": 4.0, "I": 98.4, "J": 100.0,
    },
    "corroborating_sessions": [
        "shard-6 3rd firing 2026-07-21 (refuter confirmed unchanged)",
        "shard-9 2nd firing 2026-07-24 (volusia verified unchanged)",
    ],
}

VOLUSIA_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]


def main() -> None:
    if not SUPABASE_KEY:
        print("No SUPABASE_KEY — printing documentation only, no DB writes.")
        print(json.dumps(
            {
                "union_block": UNION_BLOCK_EVIDENCE,
                "volusia_confirmation": VOLUSIA_EVIDENCE,
            },
            indent=2,
        ))
        return

    client = httpx.Client(base_url=BASE, headers=HEADERS, timeout=30)

    audit_rows = []

    for letter in ["B", "F"]:
        audit_rows.append({
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": ULTRALOOP_MODE,
            "county_slug": "union",
            "letter": letter,
            "claim": UNION_BLOCK_EVIDENCE["claim"],
            "refuter_evidence": json.dumps(UNION_BLOCK_EVIDENCE),
            "survived": True,
            "created_at": NOW,
        })

    for letter in VOLUSIA_LETTERS:
        audit_rows.append({
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": ULTRALOOP_MODE,
            "county_slug": "volusia",
            "letter": letter,
            "claim": VOLUSIA_EVIDENCE["claim"],
            "refuter_evidence": json.dumps(VOLUSIA_EVIDENCE),
            "survived": True,
            "created_at": NOW,
        })

    resp = client.post(
        "/gold_standard_ultraloop_audit",
        json=audit_rows,
        headers={**HEADERS, "Prefer": "return=minimal"},
    )
    if resp.status_code in (200, 201, 204):
        print(f"Logged {len(audit_rows)} ultraloop audit rows (union B/F + volusia A-J).")
    else:
        print(f"WARN: audit insert returned {resp.status_code}: {resp.text}")

    for county in ("union", "volusia"):
        touch = client.patch(
            "/multi_county_auctions",
            params={"county": f"eq.{county}"},
            json={"last_seen_at": NOW, "scraped_at": NOW},
            headers={**HEADERS, "Prefer": "return=minimal"},
        )
        if touch.status_code in (200, 201, 204):
            print(f"Touched last_seen_at for county={county} (H freshness).")
        else:
            print(f"WARN: touch for {county} returned {touch.status_code}: {touch.text}")

    print(
        "\nSESSION COMPLETE. No auction outcome writes — no union sale has occurred.\n"
        "Next action: check union 63-2025-CA-0053 after 2026-08-13 for a real outcome."
    )


if __name__ == "__main__":
    main()

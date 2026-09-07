#!/usr/bin/env python3
"""GET /auctions returned [] for every county. Route it through an RPC.

Why
---
fetchAuctionCards() read /rest/v1/v_property_card_verified directly with the
anon key. PostgREST answers:

    401 {"code":"42501","message":"permission denied for view v_property_card_verified"}

and the next line was `const rows = auctionsRes.ok ? await auctionsRes.json() : []`
-- so an auth failure was indistinguishable from "no auctions" and the endpoint
(and the chat panel's auction cards that consume it) had been silently empty for
every county. Live-reproduced 2026-09-07: escambia has 150 upcoming rows in that
view and `/auctions?county=escambia&days=90` returned `[]`.

Granting anon SELECT on the view is the wrong fix: it carries 120+ columns
including owner_name, winning_bidder, tier1_* and plaintiff_max_bid -- the paid
signal. public.list_auction_cards(county, days, type, limit) is a bounded
SECURITY DEFINER RPC (card columns only, <=90 days, <=50 rows, gold-standard
flag folded in) granted to anon, matching how every other public data path in
this Worker is served.

This patch points fetchAuctionCards at it, drops the second round trip for the
certification flag, and stops swallowing the failure: a non-OK response now
logs the status and body instead of vanishing into an empty array.

Idempotent: exits 0 with "already applied" on a second run.
"""
import sys
from pathlib import Path

MARKER = "rpc/list_auction_cards"

ANCHOR = Path(__file__).with_name("_auctions_anchor.txt")

NEW = '''  // The old path read v_property_card_verified directly with the anon key and
  // got 401 "permission denied", which the next line turned into an empty list
  // -- so this endpoint reported "no auctions" for every county in Florida.
  // list_auction_cards is a bounded SECURITY DEFINER RPC that anon may execute:
  // card columns only (never owner_name/winning_bidder/tier1_*/plaintiff_max_bid),
  // window and row count capped server-side, gold-standard flag folded in.
  const cardsRes = await fetch(`${SUPABASE_URL}/rest/v1/rpc/list_auction_cards`, {
    method: 'POST',
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ p_county: county, p_days: days, p_type: type, p_limit: limit }),
  });
  let rows = [];
  if (!cardsRes.ok) {
    // Never let a transport or permission failure masquerade as "no auctions".
    console.error(`list_auction_cards ${cardsRes.status} for county=${county}: ${(await cardsRes.text()).slice(0, 300)}`);
  } else {
    const payload = await cardsRes.json();
    if (Array.isArray(payload)) rows = payload;
    else console.error(`list_auction_cards returned a non-array for county=${county}: ${JSON.stringify(payload).slice(0, 200)}`);
  }
  const now = Date.now();
'''

OLD_GOLD = "      is_gold_standard: isGold,\n"
NEW_GOLD = "      is_gold_standard: !!r.is_gold_standard,\n"

OLD_HEADER = """// Reads v_property_card_verified (not the raw table) — a fail-closed gate that
// only surfaces lots with a fresh (<48h) clerk parity check, per CLERK-SSOT
// Task 4.2. A clerk-confirmed-cancelled or never-checked lot never renders here.
"""

NEW_HEADER = """// Served by public.list_auction_cards(), a bounded SECURITY DEFINER RPC over
// v_property_card_verified (not the raw table) — a fail-closed gate that only
// surfaces lots with a fresh (<48h) clerk parity check, per CLERK-SSOT Task 4.2.
// A clerk-confirmed-cancelled or never-checked lot never renders here.
"""


def main(path):
    src = open(path, encoding="utf-8").read()
    if MARKER in src:
        print("already applied")
        return 0

    anchor = ANCHOR.read_text(encoding="utf-8")
    n = src.count(anchor)
    if n != 1:
        raise SystemExit(f"fetchAuctionCards anchor matched {n} times, expected 1")
    src = src.replace(anchor, NEW, 1)

    for old, new, what in ((OLD_GOLD, NEW_GOLD, "is_gold_standard"),
                           (OLD_HEADER, NEW_HEADER, "header comment")):
        n = src.count(old)
        if n != 1:
            raise SystemExit(f"{what} anchor matched {n} times, expected 1")
        src = src.replace(old, new, 1)

    open(path, "w", encoding="utf-8").write(src)

    if "rest/v1/v_property_card_verified" in src:
        raise SystemExit("worker still reads v_property_card_verified over PostgREST")
    for needle in ("rpc/list_auction_cards", "Never let a transport or permission failure",
                   "is_gold_standard: !!r.is_gold_standard"):
        if needle not in src:
            raise SystemExit(f"missing after patch: {needle!r}")
    print(f"patched {path}: /auctions now goes through list_auction_cards")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "src/worker.js"))

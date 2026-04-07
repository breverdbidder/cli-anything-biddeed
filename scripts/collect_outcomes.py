#!/usr/bin/env python3
"""RL Reward Engine — Post-Auction Outcome Collector
Issue: https://github.com/breverdbidder/cli-anything-biddeed/issues/119

Runs 24h after each auction date. Matches prediction_trajectories
against historical_auctions results, fills actual outcome fields,
and calculates reward_v2 scores.

Usage:
  python scripts/collect_outcomes.py                    # collect for yesterday
  python scripts/collect_outcomes.py --date 2026-04-06  # collect for specific date
  python scripts/collect_outcomes.py --all-pending       # collect all pending outcomes
"""
import requests, json, os, sys, argparse
from datetime import datetime, timedelta

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
TG_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rl_engine"))
from reward import calculate_reward_v2


def tg(msg):
    if TG_BOT and TG_CHAT:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage",
                data={"chat_id": TG_CHAT, "text": msg[:4000], "parse_mode": "Markdown"}, timeout=10)
        except Exception:
            pass


def get_pending_trajectories(auction_date=None):
    """Fetch trajectories with no outcome yet."""
    params = {"select": "*", "actual_sold": "is.null", "limit": "1000"}
    if auction_date:
        params["auction_date"] = f"eq.{auction_date}"
    else:
        # All pending where auction_date < today
        params["auction_date"] = f"lt.{datetime.now().strftime('%Y-%m-%d')}"
    r = requests.get(f"{BASE}/prediction_trajectories", headers=H, params=params, timeout=30)
    return r.json() if r.status_code == 200 else []


def lookup_auction_result(case_number, auction_date):
    """Look up actual auction result from multi_county_auctions."""
    params = {
        "select": "winning_bid,auction_status,case_number",
        "case_number": f"eq.{case_number}",
        "limit": "1"
    }
    r = requests.get(f"{BASE}/multi_county_auctions", headers=H, params=params, timeout=10)
    if r.status_code == 200 and r.json():
        return r.json()[0]

    # Fallback: check historical_auctions
    params2 = {
        "select": "winning_bid,status,buyer_type,case_number",
        "case_number": f"eq.{case_number}",
        "limit": "1"
    }
    r2 = requests.get(f"{BASE}/historical_auctions", headers=H, params=params2, timeout=10)
    if r2.status_code == 200 and r2.json():
        return r2.json()[0]

    return None


def classify_buyer(result):
    """Determine buyer type from auction result."""
    status = (result.get("auction_status") or result.get("status") or "").lower()
    buyer = (result.get("buyer_type") or "").lower()

    if "sold" in status:
        if "third" in buyer:
            return True, "third_party"
        elif "plaintiff" in buyer:
            return True, "plaintiff"
        else:
            return True, "third_party"  # default sold = third_party
    elif "cancel" in status or "struck" in status:
        return False, "no_sale"
    else:
        return False, "no_sale"


def collect_for_date(auction_date):
    """Collect outcomes for a specific auction date."""
    pending = get_pending_trajectories(auction_date)
    if not pending:
        print(f"  No pending trajectories for {auction_date}")
        return 0

    print(f"  Found {len(pending)} pending trajectories for {auction_date}")
    updated = 0

    for traj in pending:
        result = lookup_auction_result(traj["case_number"], auction_date)
        if not result:
            continue

        sold, buyer_type = classify_buyer(result)
        sale_price = result.get("winning_bid")

        outcome = {
            "actual_sold": sold,
            "actual_sale_price": sale_price,
            "actual_buyer_type": buyer_type,
            "outcome_recorded_at": datetime.utcnow().isoformat(),
        }

        # Calculate reward
        merged = {**traj, **outcome}
        reward = calculate_reward_v2(merged)
        outcome["reward_score"] = reward

        r = requests.patch(
            f"{BASE}/prediction_trajectories?id=eq.{traj['id']}",
            headers={**H, "Prefer": "return=minimal"},
            json=outcome, timeout=10
        )
        if r.status_code in [200, 204]:
            updated += 1

    return updated


def main():
    parser = argparse.ArgumentParser(description="Collect post-auction outcomes for RL reward engine")
    parser.add_argument("--date", help="Specific auction date (YYYY-MM-DD)")
    parser.add_argument("--all-pending", action="store_true", help="Collect all pending outcomes")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_KEY not set")
        sys.exit(1)

    print("=" * 60)
    print("RL REWARD ENGINE — Outcome Collector")
    print("=" * 60)

    total_updated = 0

    if args.all_pending:
        print("\nCollecting ALL pending outcomes...")
        pending = get_pending_trajectories()
        dates = sorted(set(t["auction_date"] for t in pending))
        print(f"Found {len(pending)} pending across {len(dates)} dates")
        for d in dates:
            updated = collect_for_date(d)
            total_updated += updated
    elif args.date:
        print(f"\nCollecting outcomes for {args.date}...")
        total_updated = collect_for_date(args.date)
    else:
        # Default: yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"\nCollecting outcomes for yesterday ({yesterday})...")
        total_updated = collect_for_date(yesterday)

    print(f"\nTotal trajectories updated with outcomes: {total_updated}")

    # Report engine health
    r = requests.get(f"{BASE}/prediction_trajectories", headers=H, timeout=10, params={
        "select": "id", "actual_sold": "not.is.null"
    })
    r2 = requests.get(f"{BASE}/prediction_trajectories", headers=H, timeout=10, params={
        "select": "id"
    })
    with_outcomes = len(r.json()) if r.status_code == 200 else "?"
    total = len(r2.json()) if r2.status_code == 200 else "?"

    summary = (
        f"📊 *RL Outcome Collector*\n"
        f"Updated: {total_updated} trajectories\n"
        f"Total: {total} trajectories ({with_outcomes} with outcomes)\n"
    )
    print(summary)
    tg(summary)


if __name__ == "__main__":
    main()

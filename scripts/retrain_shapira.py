#!/usr/bin/env python3
"""
Shapira Formula V2 — Parameter Optimization & Retrain Pipeline
Issue: breverdbidder/cli-anything-biddeed#120

Learns optimal parameters from prediction_trajectories outcomes.
Falls back to V1 defaults when sample_size < 20.

Usage:
  python scripts/retrain_shapira.py                   # full retrain
  python scripts/retrain_shapira.py --backfill         # seed from multi_county_auctions
  python scripts/retrain_shapira.py --dry-run          # show what would be learned
"""

import os
import sys
import json
import time
import argparse
import statistics
from datetime import datetime, timezone

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

MIN_SAMPLE_SIZE = 20

DEFAULT_PARAMS = {
    "arv_multiplier": 0.70,
    "buffer_fixed": 10000,
    "buffer_pct": 0.15,
    "buffer_cap": 25000,
    "bid_threshold": 0.75,
    "review_threshold": 0.60,
}

PARAM_BOUNDS = {
    "arv_multiplier": (0.55, 0.85),
    "buffer_fixed": (5000, 20000),
    "buffer_pct": (0.10, 0.25),
    "buffer_cap": (15000, 40000),
    "bid_threshold": (0.55, 0.85),
    "review_threshold": (0.45, 0.75),
}


def headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def sb_get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = httpx.get(url, headers=headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_post(path, data):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = httpx.post(url, headers={**headers(), "Prefer": "return=representation"}, json=data, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_upsert(path, data, on_conflict=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    prefer = "return=representation,resolution=merge-duplicates"
    if on_conflict:
        prefer += f",on-conflict={on_conflict}"
    r = httpx.post(url, headers={**headers(), "Prefer": prefer}, json=data, timeout=30)
    r.raise_for_status()
    return r.json()


def shapira_v2(arv, repairs, judgment, params=None):
    """Apply Shapira Formula with given parameters. Returns (action, max_bid, ratio)."""
    p = params or DEFAULT_PARAMS
    max_bid = (
        arv * p["arv_multiplier"]
        - repairs
        - p["buffer_fixed"]
        - min(p.get("buffer_cap", 25000), p["buffer_pct"] * arv)
    )
    ratio = max_bid / judgment if judgment and judgment > 0 else 0
    if ratio >= p["bid_threshold"]:
        return "BID", max_bid, ratio
    elif ratio >= p["review_threshold"]:
        return "REVIEW", max_bid, ratio
    return "SKIP", max_bid, ratio


def compute_reward(trajectory, params=None):
    """
    Reward signal: how well did the formula predict the right action?

    +1.0  BID and we actually would have won at max_bid (sold <= max_bid)
    +0.5  REVIEW and outcome was profitable
    +0.0  SKIP and property was indeed overpriced
    -0.5  BID but max_bid was below actual sold (missed)
    -1.0  BID but sold << max_bid (overpaid signal)
    """
    arv = trajectory.get("arv_used") or 0
    repairs = trajectory.get("repairs_estimate") or 0
    judgment = trajectory.get("judgment_amount") or 0
    actual_sold = trajectory.get("actual_sold") or 0

    if arv <= 0 or actual_sold <= 0:
        return None

    action, max_bid, ratio = shapira_v2(arv, repairs, judgment, params)

    if action == "BID":
        if actual_sold <= max_bid:
            reward = 1.0
        elif actual_sold <= max_bid * 1.1:
            reward = 0.3
        else:
            reward = -0.5
    elif action == "REVIEW":
        if actual_sold <= max_bid:
            reward = 0.5
        else:
            reward = 0.0
    else:  # SKIP
        if actual_sold > max_bid:
            reward = 0.5  # correct skip
        else:
            reward = -0.3  # missed opportunity

    return reward


def optimize_parameters(trajectories):
    """
    Grid search over parameter space to maximize avg reward.
    Simple but effective for the data volumes we have.
    """
    best_params = DEFAULT_PARAMS.copy()
    best_reward = avg_reward(trajectories, DEFAULT_PARAMS)

    # Coarse grid search
    for arv_mult in [0.60, 0.65, 0.68, 0.70, 0.72, 0.75, 0.78, 0.80]:
        for buf_fixed in [7000, 8500, 10000, 12000, 15000]:
            for bid_thresh in [0.65, 0.70, 0.72, 0.75, 0.78, 0.80]:
                params = {
                    **DEFAULT_PARAMS,
                    "arv_multiplier": arv_mult,
                    "buffer_fixed": buf_fixed,
                    "bid_threshold": bid_thresh,
                    "review_threshold": bid_thresh - 0.15,
                }
                r = avg_reward(trajectories, params)
                if r is not None and (best_reward is None or r > best_reward):
                    best_reward = r
                    best_params = params.copy()

    return best_params, best_reward


def avg_reward(trajectories, params):
    rewards = [compute_reward(t, params) for t in trajectories]
    rewards = [r for r in rewards if r is not None]
    if not rewards:
        return None
    return statistics.mean(rewards)


def backfill_from_auctions(dry_run=False):
    """
    Seed prediction_trajectories from multi_county_auctions where sold_amount IS NOT NULL.
    Uses market_value as ARV proxy.
    """
    print("Fetching completed auctions from multi_county_auctions...")
    auctions = sb_get(
        "multi_county_auctions",
        params={
            "select": "id,case_number,parcel_id,zip,auction_type,judgment_amount,market_value,po_avm_value,sold_amount,winning_bidder,sale_type",
            "sold_amount": "not.is.null",
            "limit": 1000,
        },
    )
    print(f"  Found {len(auctions)} completed auctions")

    trajectories = []
    for a in auctions:
        arv = a.get("po_avm_value") or a.get("market_value") or 0
        if arv <= 0:
            continue

        zip_code = (a.get("zip") or "").strip()
        if not zip_code:
            continue

        # Normalize auction_type
        raw_type = (a.get("auction_type") or a.get("sale_type") or "foreclosure").lower()
        auction_type = "tax_deed" if "tax" in raw_type else "foreclosure"

        judgment = a.get("judgment_amount") or 0
        repairs = arv * 0.08  # conservative 8% estimate for backfill
        actual_sold = a.get("sold_amount") or 0

        action, max_bid, ratio = shapira_v2(arv, repairs, judgment)
        reward = compute_reward(
            {"arv_used": arv, "repairs_estimate": repairs, "judgment_amount": judgment, "actual_sold": actual_sold}
        )

        trajectories.append(
            {
                "case_number": a.get("case_number"),
                "parcel_id": a.get("parcel_id"),
                "zip_code": zip_code,
                "auction_type": auction_type,
                "arv_used": float(arv),
                "repairs_estimate": float(repairs),
                "judgment_amount": float(judgment) if judgment else None,
                "predicted_max_bid": float(max_bid),
                "predicted_action": action,
                "bid_ratio": float(ratio),
                "parameters_version": "v1_default",
                "actual_sold": float(actual_sold),
                "reward_score": float(reward) if reward is not None else None,
                "outcome_notes": "backfilled_from_multi_county_auctions",
                "source_auction_id": a.get("id"),
            }
        )

    print(f"  Prepared {len(trajectories)} trajectory records")
    if dry_run:
        print("  DRY RUN — not inserting")
        for t in trajectories[:3]:
            print(f"    {t['zip_code']} {t['auction_type']}: action={t['predicted_action']} reward={t['reward_score']}")
        return len(trajectories)

    if trajectories:
        result = sb_upsert("prediction_trajectories", trajectories)
        print(f"  Inserted {len(result)} trajectory records")
    return len(trajectories)


def retrain(dry_run=False):
    """Monthly retrain: learns optimal parameters per zip + auction_type."""
    start = time.time()
    print("\nFetching trajectories with outcomes...")

    trajectories = sb_get(
        "prediction_trajectories",
        params={
            "select": "*",
            "actual_sold": "not.is.null",
            "limit": 10000,
        },
    )
    total = len(trajectories)
    print(f"  Found {total} trajectories with outcomes")

    if total == 0:
        print("  No data to retrain on. Run --backfill first.")
        return

    # Group by zip_code + auction_type
    groups = {}
    for t in trajectories:
        key = (t["zip_code"], t["auction_type"])
        groups.setdefault(key, []).append(t)

    print(f"  {len(groups)} zip+type groups found")

    groups_retrained = 0
    groups_skipped = 0
    learned_rows = []

    for (zip_code, auction_type), group_data in groups.items():
        sample_size = len(group_data)
        if sample_size < MIN_SAMPLE_SIZE:
            print(f"  SKIP {zip_code}/{auction_type}: {sample_size} < {MIN_SAMPLE_SIZE} samples")
            groups_skipped += 1
            continue

        optimal_params, best_reward = optimize_parameters(group_data)
        default_reward = avg_reward(group_data, DEFAULT_PARAMS)

        print(
            f"  RETRAIN {zip_code}/{auction_type}: n={sample_size} "
            f"default_reward={default_reward:.3f} "
            f"learned_reward={best_reward:.3f}"
        )

        if not dry_run:
            learned_rows.append(
                {
                    "zip_code": zip_code,
                    "auction_type": auction_type,
                    "parameters": optimal_params,
                    "sample_size": sample_size,
                    "avg_reward": float(best_reward) if best_reward is not None else None,
                    "retrained_at": datetime.now(timezone.utc).isoformat(),
                    "model_version": "shapira_v2",
                }
            )
        groups_retrained += 1

    if learned_rows:
        sb_upsert(
            "learned_parameters",
            learned_rows,
            on_conflict="zip_code,auction_type",
        )
        print(f"\n  Upserted {len(learned_rows)} learned parameter sets")

    duration = time.time() - start

    # Log retrain event
    event = {
        "total_trajectories": total,
        "groups_retrained": groups_retrained,
        "groups_skipped": groups_skipped,
        "model_version": "shapira_v2",
        "duration_seconds": round(duration, 2),
        "notes": "dry_run" if dry_run else None,
    }
    if not dry_run:
        sb_post("retrain_events", event)
    print(f"\n  Retrain event logged: {groups_retrained} groups retrained, {groups_skipped} skipped")
    return groups_retrained


def main():
    parser = argparse.ArgumentParser(description="Shapira Formula V2 retrain pipeline")
    parser.add_argument("--backfill", action="store_true", help="Seed from multi_county_auctions")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_KEY not set")
        sys.exit(1)

    if args.backfill:
        print("=== BACKFILL: seeding prediction_trajectories ===")
        n = backfill_from_auctions(dry_run=args.dry_run)
        print(f"Backfill complete: {n} records")

    print("\n=== RETRAIN: optimizing parameters ===")
    retrain(dry_run=args.dry_run)
    print("\nDone.")


if __name__ == "__main__":
    main()

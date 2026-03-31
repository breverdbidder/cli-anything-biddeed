"""
RL Reward Engine V1 — Shapira Formula
Issue: https://github.com/breverdbidder/cli-anything-biddeed/issues/119

Reward function V2: scores the full decision chain, not just price accuracy.
- Missed profitable deals (false SKIPs) get HEAVY penalties
- Winning unprofitable deals get moderate penalties
- Correct SKIPs on overpriced properties get rewarded
- The formula learns optimal aggressiveness per zip/type/season
"""

import os
from typing import Optional


def calculate_reward_v2(trajectory: dict) -> float:
    """Score a prediction against actual auction dynamics. Range: -1.0 to +1.0

    Negative rewards for costly mistakes. Positive for profitable decisions.
    This is what the Shapira Formula optimizes against.
    """

    rec = trajectory.get("recommendation")
    buyer = trajectory.get("actual_buyer_type")
    actual_price = trajectory.get("actual_sale_price") or 0
    our_max_bid = trajectory.get("max_bid_calculated") or 0
    arv = trajectory.get("arv_estimate") or 0
    repairs = trajectory.get("repair_estimate") or 0

    # === SCENARIO 1: We said BID ===
    if rec == "BID":
        if buyer == "third_party":
            if actual_price <= our_max_bid:
                # We would have WON — check profitability
                net_profit = arv - actual_price - repairs - 10000  # simplified
                if net_profit > 0:
                    return min(1.0, net_profit / 50000)  # scale by profit size
                else:
                    return -0.3  # won but would have lost money
            else:
                # We would have LOST — someone outbid us
                return -0.1  # small penalty, correct to try
        elif buyer == "plaintiff":
            # Nobody showed up — we could have gotten it cheap
            return 0.3  # good call, low competition = opportunity
        else:
            return 0.0  # no sale, neutral

    # === SCENARIO 2: We said SKIP ===
    elif rec == "SKIP":
        if buyer == "third_party":
            if actual_price < our_max_bid:
                # MISSED OPPORTUNITY — deal was profitable and we skipped it
                missed_profit = arv - actual_price - repairs - 10000
                if missed_profit > 20000:
                    return -0.8  # severe penalty for missing good deal
                elif missed_profit > 0:
                    return -0.4  # moderate penalty
                else:
                    return 0.3  # correct skip — thin margin
            else:
                return 0.5  # correct skip — sold above our max bid
        elif buyer == "plaintiff":
            return 0.2  # correct skip — no third-party interest
        else:
            return 0.1  # correct skip — no sale

    # === SCENARIO 3: We said REVIEW ===
    elif rec == "REVIEW":
        if buyer == "third_party" and actual_price < our_max_bid:
            return -0.2  # should have been a BID
        elif buyer == "plaintiff" or (actual_price and actual_price > our_max_bid):
            return 0.1  # borderline was correct
        else:
            return 0.0  # neutral

    return 0.0


def calculate_reward_v1(t: dict) -> float:
    """Score a prediction against actual outcome. Range: 0.0 to 1.0 (V1, simpler)"""
    if not t.get("actual_sold"):
        return 0.0

    # Price prediction accuracy (60% weight)
    price_accuracy = 0.0
    if t.get("actual_sale_price") and t.get("max_bid_calculated"):
        delta = abs(t["actual_sale_price"] - t["max_bid_calculated"])
        price_accuracy = max(0, 1 - (delta / t["actual_sale_price"]))

    # Recommendation accuracy (40% weight)
    rec_correct = (
        t["recommendation"] == "BID" and t["actual_buyer_type"] == "third_party"
    ) or (
        t["recommendation"] == "SKIP" and t["actual_buyer_type"] != "third_party"
    )
    rec_score = 1.0 if rec_correct else 0.0

    return (price_accuracy * 0.6) + (rec_score * 0.4)


async def record_trajectory(prediction: dict, market_context: dict, supabase_client=None):
    """Called automatically after every BidDeed.AI recommendation.

    Inserts a trajectory record with prediction inputs + market context.
    Outcome fields (actual_sold, actual_sale_price, actual_buyer_type) stay NULL
    until filled by collect_outcomes() after the auction closes.
    """
    if supabase_client is None:
        from supabase import create_client
        supabase_client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", "")),
        )

    record = {
        "case_number": prediction["case_number"],
        "auction_date": str(prediction["auction_date"]),
        "auction_type": prediction["auction_type"],
        "zip_code": prediction["zip_code"],
        "property_type": prediction.get("property_type"),
        "county": prediction.get("county", "Brevard"),
        "arv_estimate": prediction.get("arv"),
        "repair_estimate": prediction.get("repairs"),
        "judgment_amount": prediction.get("judgment"),
        "max_bid_calculated": prediction.get("max_bid"),
        "bid_judgment_ratio": prediction.get("bid_judgment_ratio"),
        "recommendation": prediction.get("recommendation"),
        "xgboost_probability": prediction.get("ml_probability"),
        "xgboost_confidence": prediction.get("ml_confidence"),
        "zip_median_income": market_context.get("median_income"),
        "zip_vacancy_rate": market_context.get("vacancy_rate"),
        "days_on_market_avg": market_context.get("dom_avg"),
        "similar_sales_count": market_context.get("comp_count"),
        "market_trend": market_context.get("trend"),
        "model_version": prediction.get("model_version", "xgboost_v1"),
        "formula_version": prediction.get("formula_version", "shapira_v1"),
        "pipeline_version": prediction.get("pipeline_version"),
    }

    result = supabase_client.table("prediction_trajectories").insert(record).execute()
    return result


async def collect_outcomes(auction_date: str, supabase_client=None):
    """Run 24h after auction. Updates trajectories with actual results.
    Then calculates reward_score V2 for all newly-updated trajectories.
    """
    if supabase_client is None:
        from supabase import create_client
        supabase_client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", "")),
        )

    # Fetch trajectories for this auction date that have no outcome yet
    pending = (
        supabase_client.table("prediction_trajectories")
        .select("*")
        .eq("auction_date", auction_date)
        .is_("actual_sold", "null")
        .execute()
    )

    if not pending.data:
        return {"updated": 0}

    updated = 0
    for traj in pending.data:
        # Look up actual outcome in historical_auctions
        match = (
            supabase_client.table("historical_auctions")
            .select("winning_bid,status,buyer_type")
            .eq("case_number", traj["case_number"])
            .eq("auction_date", auction_date)
            .limit(1)
            .execute()
        )

        if not match.data:
            continue

        result = match.data[0]
        sold = result["status"] and "sold" in result["status"].lower()
        buyer_raw = (result.get("buyer_type") or "").lower()
        buyer_type = (
            "third_party" if "third" in buyer_raw
            else "plaintiff" if "plaintiff" in buyer_raw
            else "no_sale"
        )

        outcome = {
            "actual_sold": sold,
            "actual_sale_price": result.get("winning_bid"),
            "actual_buyer_type": buyer_type,
            "outcome_recorded_at": "now()",
        }

        # Calculate reward V2 for this trajectory
        merged = {**traj, **outcome}
        reward = calculate_reward_v2(merged)
        outcome["reward_score"] = reward

        supabase_client.table("prediction_trajectories").update(outcome).eq(
            "id", traj["id"]
        ).execute()
        updated += 1

    return {"updated": updated}


def score_backfill_trajectories(supabase_client=None):
    """Calculate reward_v2 for all backfill trajectories that have outcomes but no reward_score.

    Run once after backfill to bootstrap the reward signal dataset.
    Returns count of trajectories scored.
    """
    if supabase_client is None:
        from supabase import create_client
        supabase_client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", "")),
        )

    # Fetch trajectories with outcomes but no reward_score
    # (backfill rows have actual_sold set but recommendation=NULL so reward will be 0.0)
    trajs = (
        supabase_client.table("prediction_trajectories")
        .select("*")
        .not_.is_("actual_sold", "null")
        .is_("reward_score", "null")
        .execute()
    )

    if not trajs.data:
        print("No trajectories to score")
        return 0

    scored = 0
    for t in trajs.data:
        reward = calculate_reward_v2(t)
        supabase_client.table("prediction_trajectories").update(
            {"reward_score": reward}
        ).eq("id", t["id"]).execute()
        scored += 1

    print(f"Scored {scored} trajectories")
    return scored


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "score"

    if cmd == "score":
        count = score_backfill_trajectories()
        print(f"VERIFIED: Scored {count} backfill trajectories with reward_v2")
    elif cmd == "test":
        # Unit tests for reward_v2
        cases = [
            # BID + won profitably → high reward
            {"recommendation": "BID", "actual_buyer_type": "third_party",
             "actual_sale_price": 150000, "max_bid_calculated": 180000,
             "arv_estimate": 250000, "repair_estimate": 40000, "expected_range": (0.0, 1.0)},
            # SKIP + missed profit → heavy penalty
            {"recommendation": "SKIP", "actual_buyer_type": "third_party",
             "actual_sale_price": 130000, "max_bid_calculated": 180000,
             "arv_estimate": 250000, "repair_estimate": 40000, "expected_range": (-1.0, -0.3)},
            # SKIP + overpriced → reward
            {"recommendation": "SKIP", "actual_buyer_type": "third_party",
             "actual_sale_price": 200000, "max_bid_calculated": 180000,
             "arv_estimate": 250000, "repair_estimate": 40000, "expected_range": (0.4, 0.6)},
        ]

        all_passed = True
        for i, c in enumerate(cases):
            score = calculate_reward_v2(c)
            lo, hi = c["expected_range"]
            passed = lo <= score <= hi
            status = "PASS" if passed else "FAIL"
            print(f"  Case {i+1}: {status} score={score:.3f} expected=[{lo},{hi}]")
            if not passed:
                all_passed = False

        print(f"\n{'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
        sys.exit(0 if all_passed else 1)

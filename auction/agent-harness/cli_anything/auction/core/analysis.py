"""Auction analysis — ARV, max bid calculation, and recommendations.

Core formula: max_bid = (ARV × 70%) - repairs - $10K - MIN($25K, 15% × ARV)
"""

from typing import Optional


# Recommendation thresholds
BID_THRESHOLD = 0.75
REVIEW_THRESHOLD = 0.60


def calculate_max_bid(arv: float, repairs: float) -> dict:
    """Calculate maximum bid using the Everest Capital formula.

    Formula: (ARV × 70%) - Repairs - $10K - MIN($25K, 15% × ARV)
    """
    if arv <= 0:
        raise ValueError("ARV must be positive")
    if repairs < 0:
        raise ValueError("Repairs cannot be negative")

    profit_margin = arv * 0.70
    holding_costs = 10000
    contingency = min(25000, arv * 0.15)

    max_bid = profit_margin - repairs - holding_costs - contingency
    max_bid = max(0, round(max_bid, 2))

    return {
        "arv": arv,
        "repairs": repairs,
        "profit_margin_70pct": round(profit_margin, 2),
        "holding_costs": holding_costs,
        "contingency": round(contingency, 2),
        "max_bid": max_bid,
    }


def calculate_bid_ratio(max_bid: float, judgment: float) -> float:
    """Calculate bid-to-judgment ratio."""
    if judgment <= 0:
        return 0.0
    return round(max_bid / judgment, 4)


def recommend(max_bid: float, judgment: float) -> str:
    """Generate BID/REVIEW/SKIP recommendation based on bid ratio.

    BID: ratio >= 0.75 (max_bid covers >= 75% of judgment)
    REVIEW: 0.60 <= ratio < 0.75
    SKIP: ratio < 0.60
    """
    ratio = calculate_bid_ratio(max_bid, judgment)
    if ratio >= BID_THRESHOLD:
        return "BID"
    elif ratio >= REVIEW_THRESHOLD:
        return "REVIEW"
    else:
        return "SKIP"


def analyze_case(case_data: dict, arv: Optional[float] = None, repairs: Optional[float] = None) -> dict:
    """Full case analysis: ARV → max bid → recommendation.

    Args:
        case_data: Case dict with case_number, judgment, address, plaintiff
        arv: After-repair value (if None, uses estimate)
        repairs: Repair estimate (if None, uses default)
    """
    case_number = case_data.get("case_number", "unknown")
    judgment = case_data.get("judgment", 0)
    address = case_data.get("address", "")
    plaintiff = case_data.get("plaintiff", "")

    # Default estimates if not provided
    if arv is None:
        arv = estimate_arv(case_data)
    if repairs is None:
        repairs = estimate_repairs(case_data)

    bid_calc = calculate_max_bid(arv, repairs)
    max_bid = bid_calc["max_bid"]
    ratio = calculate_bid_ratio(max_bid, judgment)
    rec = recommend(max_bid, judgment)

    return {
        "case_number": case_number,
        "address": address,
        "plaintiff": plaintiff,
        "judgment_amount": judgment,
        "arv": arv,
        "repairs": repairs,
        "max_bid": max_bid,
        "bid_ratio": ratio,
        "recommendation": rec,
        "breakdown": bid_calc,
    }


def estimate_arv(case_data: dict) -> float:
    """Estimate ARV from case data.

    In production, this queries BCPAO comps. Currently uses judgment × 1.3 as rough estimate.
    """
    judgment = case_data.get("judgment", 0)
    return round(judgment * 1.3, 2) if judgment > 0 else 0


def estimate_repairs(case_data: dict) -> float:
    """Estimate repairs from case data.

    In production, uses property condition data. Currently defaults to $30K.
    """
    return 30000.0


def batch_analyze(cases: list[dict]) -> dict:
    """Analyze multiple cases and return summary."""
    results = []
    for case in cases:
        try:
            analysis = analyze_case(case)
            results.append(analysis)
        except (ValueError, KeyError) as e:
            results.append({"case_number": case.get("case_number", "?"), "error": str(e)})

    bids = [r for r in results if r.get("recommendation") == "BID"]
    reviews = [r for r in results if r.get("recommendation") == "REVIEW"]
    skips = [r for r in results if r.get("recommendation") == "SKIP"]
    errors = [r for r in results if "error" in r]

    return {
        "total": len(cases),
        "analyzed": len(results) - len(errors),
        "bid": len(bids),
        "review": len(reviews),
        "skip": len(skips),
        "errors": len(errors),
        "results": results,
    }

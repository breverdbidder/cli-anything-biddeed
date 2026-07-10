"""Analyzer Agent — Rank swimmers, calculate gaps, estimate finals probability.

Agent #139.2 in the BidDeed AI Army.
Handles: age group filtering, ranking, gap analysis, probability estimation.
"""

from typing import Optional
from dataclasses import dataclass, field, asdict


AGE_GROUPS = {
    "14U": lambda age: age <= 14,
    "15-16": lambda age: 15 <= age <= 16,
    "17-18": lambda age: 17 <= age <= 18,
    "19O": lambda age: age >= 19,
}


@dataclass
class FinalsAnalysis:
    event_name: str
    event_number: int
    seed_time: float
    seed_display: str
    qualifier: str
    course: str
    age_group_rank: int
    age_group_total: int
    overall_rank: int
    a_final_cut: float
    b_final_cut: float
    srch_cut: Optional[float]
    gap_to_a: float
    gap_to_b: float
    gap_to_srch: Optional[float]
    a_final_pct: float
    b_final_pct: float
    top_16: list
    verdict: str
    strategy: str

    def to_dict(self):
        return asdict(self)


def filter_age_group(entries: list, age_group: str) -> list:
    """Filter entries to a specific age group."""
    check = AGE_GROUPS.get(age_group)
    if not check:
        raise ValueError(f"Unknown age group: {age_group}. Valid: {list(AGE_GROUPS.keys())}")
    return [e for e in entries if check(e["age"])]


def rank_in_age_group(entries: list, age_group: str) -> list:
    """Filter to age group and sort by seed time."""
    filtered = filter_age_group(entries, age_group)
    return sorted(filtered, key=lambda e: e["seed_time"])


def estimate_probability(gap: float, event_distance: int) -> float:
    """Estimate probability of making a cut based on gap and event distance.

    Uses empirical heuristics:
    - Sprint (50): 0.3s drop = ~35%, 0.1s = ~70%, inside = ~80%
    - Mid (100): 0.5s drop = ~30%, 1.0s = ~15%, 2.0s = ~5%
    - Distance (200+): 1.0s drop = ~25%, 2.0s = ~12%, 5.0s = ~3%
    """
    if gap >= 0:
        # Already inside the cut
        base = 0.80
        # Bonus for being well inside
        if event_distance <= 50:
            return min(0.95, base + gap * 2.0)
        elif event_distance <= 100:
            return min(0.95, base + gap * 0.5)
        else:
            return min(0.95, base + gap * 0.2)

    # Need to drop time (gap is negative)
    abs_gap = abs(gap)

    if event_distance <= 50:
        # Sprint: small drops are realistic
        if abs_gap <= 0.15:
            return 0.70
        elif abs_gap <= 0.30:
            return 0.35
        elif abs_gap <= 0.50:
            return 0.15
        elif abs_gap <= 1.00:
            return 0.05
        else:
            return 0.02
    elif event_distance <= 100:
        if abs_gap <= 0.30:
            return 0.50
        elif abs_gap <= 0.80:
            return 0.25
        elif abs_gap <= 1.50:
            return 0.12
        elif abs_gap <= 2.50:
            return 0.05
        else:
            return 0.02
    else:
        # Distance
        if abs_gap <= 1.00:
            return 0.40
        elif abs_gap <= 2.50:
            return 0.20
        elif abs_gap <= 5.00:
            return 0.08
        elif abs_gap <= 10.00:
            return 0.03
        else:
            return 0.01


def determine_verdict(a_pct: float, b_pct: float) -> str:
    """Determine race verdict based on probability."""
    if a_pct >= 0.50:
        return "A-FINAL CONTENDER"
    elif a_pct >= 0.25:
        return "A-FINAL REACH"
    elif b_pct >= 0.60:
        return "B-FINAL LIKELY"
    elif b_pct >= 0.25:
        return "B-FINAL POSSIBLE"
    elif b_pct >= 0.10:
        return "CONSOLATION"
    elif b_pct >= 0.05:
        return "REACH EVENT"
    else:
        return "DEVELOPMENT"


def determine_strategy(verdict: str, gap_to_srch: Optional[float], event_name: str) -> str:
    """Generate race strategy based on analysis."""
    strategies = {
        "A-FINAL CONTENDER": "Race to win. Aggressive start, hold form.",
        "A-FINAL REACH": "Push for PB. Fast start, controlled finish.",
        "B-FINAL LIKELY": "Hold seed position. Smart race, negative split.",
        "B-FINAL POSSIBLE": "Race for PB. Every tenth matters.",
        "CONSOLATION": "Target top 24. Build for next meet.",
        "REACH EVENT": "Break SRCH cut if possible. Race for experience.",
        "DEVELOPMENT": "Even-split. Use for coaching data and splits.",
    }
    strategy = strategies.get(verdict, "Race smart.")

    if gap_to_srch is not None and gap_to_srch < 0 and abs(gap_to_srch) < 1.0:
        strategy += f" SRCH cut within reach ({abs(gap_to_srch):.2f}s)."

    return strategy


def analyze_swimmer(parsed_data: dict, swimmer_name: str, age_group: str = "15-16") -> dict:
    """Full analysis of a swimmer across all their events.

    Args:
        parsed_data: Output from parser.parse_pdf()
        swimmer_name: Last, First format (partial match supported)
        age_group: Target age group for ranking

    Returns:
        Complete analysis dict with per-event breakdowns.
    """
    results = {
        "swimmer": swimmer_name,
        "age_group": age_group,
        "events": [],
        "summary": {},
    }

    swimmer_name_lower = swimmer_name.lower()

    for event in parsed_data["events"]:
        # Find swimmer in this event
        swimmer_entry = None
        for entry in event["entries"]:
            if swimmer_name_lower in entry["name"].lower():
                swimmer_entry = entry
                break

        if not swimmer_entry:
            continue

        # Get age group rankings
        ag_ranked = rank_in_age_group(event["entries"], age_group)
        ag_total = len(ag_ranked)

        # Find swimmer's rank in age group
        ag_rank = None
        for i, e in enumerate(ag_ranked):
            if swimmer_name_lower in e["name"].lower():
                ag_rank = i + 1
                break

        # If swimmer not in age group results (e.g., wrong age), skip
        if ag_rank is None:
            # Swimmer might be entered but not in this age group filter
            # Insert them hypothetically
            swimmer_time = swimmer_entry["seed_time"]
            ag_rank = sum(1 for e in ag_ranked if e["seed_time"] < swimmer_time) + 1
            ag_total += 1

        # Calculate cuts
        a_cut = ag_ranked[7]["seed_time"] if len(ag_ranked) >= 8 else None
        b_cut = ag_ranked[15]["seed_time"] if len(ag_ranked) >= 16 else None

        # SRCH cut for age group
        cuts = event.get("cuts", {})
        srch_cut = cuts.get(f"age_{age_group.replace('-', '_')}")

        seed = swimmer_entry["seed_time"]
        gap_a = (b_cut - seed) if a_cut else None  # negative = need to drop
        gap_b = (b_cut - seed) if b_cut else None

        # Fix: gap should be positive if inside, negative if outside
        gap_a = a_cut - seed if a_cut else None  # negative = slower than cut
        gap_b = b_cut - seed if b_cut else None

        gap_srch = (srch_cut - seed) if srch_cut else None

        distance = event.get("distance", 100)

        a_pct = estimate_probability(gap_a, distance) if gap_a is not None else 0
        b_pct = estimate_probability(gap_b, distance) if gap_b is not None else 0

        verdict = determine_verdict(a_pct, b_pct)
        strategy = determine_strategy(verdict, gap_srch, event["name"])

        # Top 16 in age group
        top_16 = ag_ranked[:16]

        analysis = FinalsAnalysis(
            event_name=event["name"],
            event_number=event["number"],
            seed_time=seed,
            seed_display=swimmer_entry["seed_display"],
            qualifier=swimmer_entry["qualifier"],
            course=swimmer_entry.get("course", "SCY"),
            age_group_rank=ag_rank,
            age_group_total=ag_total,
            overall_rank=swimmer_entry["seed_rank"],
            a_final_cut=a_cut or 0,
            b_final_cut=b_cut or 0,
            srch_cut=srch_cut,
            gap_to_a=gap_a or 0,
            gap_to_b=gap_b or 0,
            gap_to_srch=gap_srch,
            a_final_pct=round(a_pct, 2),
            b_final_pct=round(b_pct, 2),
            top_16=top_16,
            verdict=verdict,
            strategy=strategy,
        )

        results["events"].append(analysis.to_dict())

    # Summary
    if results["events"]:
        best = max(results["events"], key=lambda e: e["b_final_pct"])
        results["summary"] = {
            "total_events": len(results["events"]),
            "best_event": best["event_name"],
            "best_verdict": best["verdict"],
            "best_b_final_pct": best["b_final_pct"],
        }

    return results

#!/usr/bin/env python3
"""
update_brain.py — Brain evolution protocol.
Port of GVB /viral:update-brain command for BidDeed.AI Supabase stack.

Reads viral_analytics + viral_agent_brain, evolves system-managed sections,
writes back. NEVER modifies user-managed fields (identity, icp, pillars, etc).

Usage:
  python3 update_brain.py
  python3 update_brain.py --insights
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import (
    get_brain,
    get_analytics,
    save_brain,
    select,
    upsert,
)


def now_iso() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def median(values: list) -> float:
    if not values:
        return 0.0
    s = sorted(float(v) for v in values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ── Phase A: Read current state ───────────────────────────────────────────────

def load_state() -> tuple[dict, list[dict]]:
    brain = get_brain()
    analytics = get_analytics()
    return brain or {}, analytics or []


def get_new_entries(brain: dict, analytics: list[dict]) -> list[dict]:
    """Entries added since last brain update."""
    meta = brain.get("metadata", {})
    last_analysis = meta.get("last_analysis", "")
    if not last_analysis:
        return analytics  # First run — all are new
    try:
        cutoff = datetime.datetime.fromisoformat(last_analysis.replace("Z", "+00:00"))
        new = []
        for e in analytics:
            analyzed_at = e.get("analyzed_at", "")
            if not analyzed_at:
                continue
            try:
                ts = datetime.datetime.fromisoformat(analyzed_at.replace("Z", "+00:00"))
                if ts > cutoff:
                    new.append(e)
            except Exception:
                continue
        return new
    except Exception:
        return analytics


# ── Phase B: Analyze and propose updates ─────────────────────────────────────

def analyze_learning_weights(brain: dict, analytics: list[dict]) -> dict:
    """
    B1: Adjust learning_weights based on which scoring criteria correlate with winners.
    Requires 5+ analytics entries.
    """
    weights = dict(brain.get("learning_weights", {
        "icp_relevance": 1.0,
        "timeliness": 1.0,
        "content_gap": 1.0,
        "proof_potential": 1.0,
    }))

    if len(analytics) < 5:
        return weights

    # Group entries by winning status
    winners = [e for e in analytics if e.get("is_winner")]
    losers = [e for e in analytics if not e.get("is_winner")]

    if not winners:
        return weights

    # icp_relevance: winning pillars → boost
    winning_pillars = set(e.get("content_pillar") for e in winners if e.get("content_pillar"))
    all_pillars = set(e.get("content_pillar") for e in analytics if e.get("content_pillar"))
    if all_pillars:
        pillar_win_rates = {}
        for pillar in all_pillars:
            total = sum(1 for e in analytics if e.get("content_pillar") == pillar)
            wins = sum(1 for e in winners if e.get("content_pillar") == pillar)
            if total >= 2:
                pillar_win_rates[pillar] = wins / total

        high_performers = [p for p, r in pillar_win_rates.items() if r >= 0.5]
        if high_performers:
            weights["icp_relevance"] = clamp(
                safe_float(weights.get("icp_relevance", 1.0)) + 0.1 * len(high_performers),
                0.1, 5.0,
            )

    # proof_potential: do winners skew toward action (tutorial) content?
    # Approximate via topic_category matching
    winner_platforms = [e.get("platform", "") for e in winners]
    if "youtube_longform" in winner_platforms:
        weights["proof_potential"] = clamp(
            safe_float(weights.get("proof_potential", 1.0)) + 0.1,
            0.1, 5.0,
        )

    return weights


def analyze_hook_preferences(brain: dict, analytics: list[dict]) -> dict:
    """B2: Score hook patterns based on CTR, retention, and engagement averages."""
    prefs = dict(brain.get("hook_preferences", {
        "contradiction": 0, "specificity": 0, "timeframe_tension": 0,
        "pov_as_advice": 0, "vulnerable_confession": 0, "pattern_interrupt": 0,
    }))

    for pattern in prefs:
        matching = [e for e in analytics if e.get("hook_pattern_used") == pattern]
        if len(matching) < 2:
            continue

        winners = [e for e in matching if e.get("is_winner")]
        win_rate = len(winners) / len(matching)

        ctrs = [safe_float(e["metrics"]["ctr"]) for e in matching if e.get("metrics", {}).get("ctr") is not None]
        retentions = [safe_float(e["metrics"]["retention_30s"]) for e in matching if e.get("metrics", {}).get("retention_30s") is not None]
        engagements = [safe_float(e["metrics"]["engagement_rate"]) for e in matching if e.get("metrics", {}).get("engagement_rate") is not None]

        # Composite performance score (normalize to 0-100 if we have enough data)
        if ctrs or retentions or engagements:
            perf_score = (
                (sum(ctrs) / len(ctrs) * 0.4 if ctrs else 0) +
                (sum(retentions) / len(retentions) * 0.35 if retentions else 0) +
                (sum(engagements) / len(engagements) * 0.25 if engagements else 0)
            )
        else:
            perf_score = win_rate * 10  # Fallback: win rate proxy

        current = safe_float(prefs.get(pattern, 0))
        if win_rate >= 0.5:
            prefs[pattern] = clamp(current + 0.5, -2.0, 5.0)
        elif win_rate == 0 and len(matching) >= 3:
            prefs[pattern] = clamp(current - 0.2, -2.0, 5.0)

    return prefs


def analyze_performance_patterns(brain: dict, analytics: list[dict]) -> dict:
    """B3: Update aggregated performance patterns."""
    perf = dict(brain.get("performance_patterns", {}))

    perf["total_content_analyzed"] = len(analytics)

    ctrs = [safe_float(e["metrics"]["ctr"]) for e in analytics if e.get("metrics", {}).get("ctr") is not None]
    if ctrs:
        perf["avg_ctr"] = round(sum(ctrs) / len(ctrs), 1)

    ret30s = [safe_float(e["metrics"]["retention_30s"]) for e in analytics if e.get("metrics", {}).get("retention_30s") is not None]
    if ret30s:
        perf["avg_retention_30s"] = round(sum(ret30s) / len(ret30s), 1)

    # Top performing topics by win rate
    topic_wins: dict[str, list] = {}
    for e in analytics:
        cat = e.get("topic_category") or e.get("content_pillar")
        if not cat:
            continue
        topic_wins.setdefault(cat, []).append(e)

    topic_rates = {}
    for topic, entries in topic_wins.items():
        if len(entries) < 2:
            continue
        wins = sum(1 for e in entries if e.get("is_winner"))
        topic_rates[topic] = wins / len(entries)

    top_topics = sorted(topic_rates, key=topic_rates.get, reverse=True)[:10]
    if top_topics:
        perf["top_performing_topics"] = top_topics

    # Top performing formats by win rate
    fmt_wins: dict[str, list] = {}
    for e in analytics:
        plat = e.get("platform", "")
        if plat:
            fmt_wins.setdefault(plat, []).append(e)

    fmt_rates = {}
    for fmt, entries in fmt_wins.items():
        if len(entries) < 2:
            continue
        wins = sum(1 for e in entries if e.get("is_winner"))
        fmt_rates[fmt] = wins / len(entries)

    top_formats = sorted(fmt_rates, key=fmt_rates.get, reverse=True)[:5]
    if top_formats:
        perf["top_performing_formats"] = top_formats

    # Audience growth drivers
    growth_data: dict[str, int] = {}
    for e in analytics:
        cat = e.get("topic_category") or e.get("content_pillar")
        subs = e.get("metrics", {}).get("subscribers_gained")
        if cat and subs:
            growth_data[cat] = growth_data.get(cat, 0) + int(subs)

    if growth_data:
        top_growth = sorted(growth_data, key=growth_data.get, reverse=True)[:5]
        perf["audience_growth_drivers"] = top_growth

    return perf


# ── Display helpers ───────────────────────────────────────────────────────────

def diff_weights(old: dict, new: dict, label: str) -> list[str]:
    changes = []
    for k in new:
        ov = old.get(k, "—")
        nv = new[k]
        if str(ov) != str(nv):
            changes.append(f"  {k}: {ov} → {nv}")
        else:
            changes.append(f"  {k}: {nv} (unchanged)")
    if changes:
        print(f"\n{label}:")
        for line in changes:
            print(line)
    return [c for c in changes if "unchanged" not in c]


# ── Phase D: Insights aggregation ────────────────────────────────────────────

def run_insights(analytics: list[dict]) -> None:
    """--insights mode: aggregate patterns into viral_insights table."""
    if len(analytics) < 3:
        print(f"Need more data ({len(analytics)}/3 analytics entries).")
        print("Run analyze.py to collect performance data first.")
        return

    # Build insights object
    insights = {
        "last_updated": now_iso(),
        "analysis_count": 1,
        "top_topics": [],
        "hook_performance": {},
        "thumbnail_patterns": [],
        "content_format_performance": {},
        "optimal_posting_times": {},
        "competitor_insights": [],
    }

    # Top topics
    topic_entries: dict[str, list] = {}
    for e in analytics:
        cat = e.get("topic_category") or e.get("content_pillar")
        if cat:
            topic_entries.setdefault(cat, []).append(e)

    top_topics = []
    for topic, entries in topic_entries.items():
        if len(entries) < 2:
            continue
        views_vals = [safe_float(e.get("metrics", {}).get("views", 0)) for e in entries]
        max_views = max(views_vals) if views_vals else 1
        avg_perf = sum(v / max(max_views, 1) * 100 for v in views_vals) / len(views_vals)
        platforms = [e.get("platform", "") for e in entries]
        top_topics.append({
            "topic": topic,
            "avg_performance": round(avg_perf, 1),
            "content_count": len(entries),
            "best_platform": max(set(platforms), key=platforms.count) if platforms else "",
        })

    insights["top_topics"] = sorted(top_topics, key=lambda x: x["avg_performance"], reverse=True)[:10]

    # Hook performance
    for pattern in ["contradiction", "specificity", "timeframe_tension", "pov_as_advice", "vulnerable_confession", "pattern_interrupt"]:
        matching = [e for e in analytics if e.get("hook_pattern_used") == pattern]
        if len(matching) < 2:
            insights["hook_performance"][pattern] = {"times_used": len(matching), "avg_ctr": 0, "avg_engagement": 0}
            continue
        ctrs = [safe_float(e["metrics"]["ctr"]) for e in matching if e.get("metrics", {}).get("ctr") is not None]
        engs = [safe_float(e["metrics"]["engagement_rate"]) for e in matching if e.get("metrics", {}).get("engagement_rate") is not None]
        insights["hook_performance"][pattern] = {
            "times_used": len(matching),
            "avg_ctr": round(sum(ctrs) / len(ctrs), 1) if ctrs else 0,
            "avg_engagement": round(sum(engs) / len(engs), 1) if engs else 0,
        }

    # Content format performance
    for plat in set(e.get("platform", "") for e in analytics if e.get("platform")):
        plat_entries = [e for e in analytics if e.get("platform") == plat]
        views = [safe_float(e.get("metrics", {}).get("views", 0)) for e in plat_entries]
        engs = [safe_float(e.get("metrics", {}).get("engagement_rate", 0)) for e in plat_entries]
        insights["content_format_performance"][plat] = {
            "avg_views": int(sum(views) / len(views)) if views else 0,
            "avg_engagement": round(sum(engs) / len(engs), 1) if engs else 0,
            "content_count": len(plat_entries),
        }

    # Save insights
    existing = select("viral_insights", "&limit=1&order=last_updated.desc")
    if existing:
        insights["analysis_count"] = (existing[0].get("analysis_count") or 0) + 1
        # Update existing row
        row_id = existing[0]["id"]
        result = upsert("viral_insights", {**insights, "id": row_id})
    else:
        result = upsert("viral_insights", insights)

    print("════════════════════════════════════════")
    print("INSIGHTS UPDATED")
    print("════════════════════════════════════════")
    print(f"Top Topics: {len(insights['top_topics'])} tracked")
    print(f"Hook Performance: {sum(1 for v in insights['hook_performance'].values() if v.get('times_used', 0) >= 2)}/6 patterns with data")
    print(f"Format Performance: {len(insights['content_format_performance'])} platforms tracked")
    print(f"Analysis runs: {insights['analysis_count']} total")
    print(f"Last updated: {insights['last_updated']}")
    print("════════════════════════════════════════")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Brain evolution protocol")
    parser.add_argument("--insights", action="store_true", help="Insight aggregation mode")
    args = parser.parse_args()

    brain, analytics = load_state()

    if args.insights:
        run_insights(analytics)
        return

    # ── Phase A: Check for new data ───────────────────────────────────────────
    new_entries = get_new_entries(brain, analytics)
    meta = brain.get("metadata", {})
    last_analysis = meta.get("last_analysis", "never")

    print("Brain Update Data Available")
    print("════════════════════════════════════════")
    print(f"Last brain update: {last_analysis}")
    print(f"Total analytics entries: {len(analytics)}")
    print(f"New entries since last update: {len(new_entries)}")
    platforms = list(set(e.get("platform", "") for e in new_entries if e.get("platform")))
    print(f"Platforms with new data: {platforms or 'none'}")
    print("════════════════════════════════════════")

    if not new_entries and analytics:
        print(f"\nNo new performance data since last brain update ({last_analysis}).")
        print("Run analyze.py first to collect fresh analytics.")
        # Still run with all analytics to keep patterns current
        print("Running full re-analysis on existing data...")
        new_entries = analytics

    if not analytics:
        print("\n⚠ No analytics data found. Run analyze.py first.")
        return

    # ── Phase B: Compute proposed updates ────────────────────────────────────
    old_weights = dict(brain.get("learning_weights", {"icp_relevance": 1.0, "timeliness": 1.0, "content_gap": 1.0, "proof_potential": 1.0}))
    old_hook_prefs = dict(brain.get("hook_preferences", {"contradiction": 0, "specificity": 0, "timeframe_tension": 0, "pov_as_advice": 0, "vulnerable_confession": 0, "pattern_interrupt": 0}))
    old_perf = dict(brain.get("performance_patterns", {}))

    if len(analytics) < 5:
        print(f"\n⏸ Skipping weight adjustments — only {len(analytics)} pieces analyzed.")
        print("Need at least 5 for meaningful signal. Current weights preserved.")
        new_weights = old_weights
        new_hook_prefs = old_hook_prefs
    else:
        new_weights = analyze_learning_weights(brain, analytics)
        new_hook_prefs = analyze_hook_preferences(brain, analytics)

    new_perf = analyze_performance_patterns(brain, analytics)

    # ── Phase C: Display and apply ────────────────────────────────────────────
    print("\nProposed Brain Updates")
    print("════════════════════════════════════════")

    weight_changes = diff_weights(old_weights, new_weights, "Learning Weights")
    hook_changes = diff_weights(old_hook_prefs, new_hook_prefs, "Hook Preferences")

    print(f"\nPerformance Patterns:")
    print(f"  total_content_analyzed: {old_perf.get('total_content_analyzed', 0)} → {new_perf.get('total_content_analyzed', 0)}")
    if "avg_ctr" in new_perf:
        print(f"  avg_ctr: {old_perf.get('avg_ctr', '—')} → {new_perf['avg_ctr']}%")
    if "top_performing_topics" in new_perf:
        print(f"  top_topics: {new_perf['top_performing_topics'][:3]}")
    if "top_performing_formats" in new_perf:
        print(f"  top_formats: {new_perf['top_performing_formats']}")

    print("════════════════════════════════════════")

    # In manual/cron mode, apply without prompting
    # (GHA runs non-interactively — skip "Apply? (yes/no)" gate)

    # ── Write updated brain ───────────────────────────────────────────────────
    # NEVER overwrite user-managed fields
    protected = ["identity", "icp", "pillars", "platforms", "competitors",
                 "monetization", "audience_blockers", "content_jobs"]

    updated_brain = {}
    for key in protected:
        if key in brain:
            updated_brain[key] = brain[key]

    updated_brain["learning_weights"] = new_weights
    updated_brain["hook_preferences"] = new_hook_prefs
    updated_brain["performance_patterns"] = new_perf
    updated_brain["visual_patterns"] = brain.get("visual_patterns", {})

    # Preserve cadence but allow optimal_times update
    cadence = dict(brain.get("cadence", {}))
    updated_brain["cadence"] = cadence

    # Evolution log
    all_changes = weight_changes + hook_changes + [
        f"performance_patterns: {new_perf.get('total_content_analyzed', 0)} total analyzed",
    ]
    if "avg_ctr" in new_perf:
        all_changes.append(f"avg_ctr: {new_perf['avg_ctr']}%")

    evolution_entry = {
        "timestamp": now_iso(),
        "reason": f"Weekly analysis — {len(new_entries)} new pieces analyzed",
        "changes": all_changes if all_changes else ["No changes needed — patterns stable"],
    }

    meta_updated = dict(meta)
    evolution_log = meta_updated.get("evolution_log", [])
    evolution_log.append(evolution_entry)
    meta_updated["evolution_log"] = evolution_log[-50:]
    meta_updated["updated_at"] = now_iso()
    meta_updated["last_analysis"] = now_iso()
    updated_brain["metadata"] = meta_updated

    result = save_brain(updated_brain)

    if isinstance(result, list) and result:
        print("\n✅ Brain updated successfully in Supabase")
    elif isinstance(result, dict) and "error" not in result:
        print("\n✅ Brain updated successfully in Supabase")
    else:
        print(f"\n⚠ Brain save issue: {result}")

    total_changes = len(weight_changes) + len(hook_changes)

    print("\nBrain Updated")
    print("════════════════════════════════════════")
    print(f"Changes applied: {total_changes} fields modified")
    print(f"Evolution log: entry #{len(meta_updated.get('evolution_log', []))} added")
    print(f"Total content analyzed: {new_perf.get('total_content_analyzed', 0)}")
    print("\nYour discovery scoring and hook recommendations")
    print("will now reflect these patterns.")
    print("\nNext: Run analyze.py again after publishing more content,")
    print("or run discover.py to find topics with updated scoring.")
    print("════════════════════════════════════════")


if __name__ == "__main__":
    main()

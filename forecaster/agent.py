#!/usr/bin/env python3
"""
cli_anything.forecaster — Rehab & Construction Cost Forecaster for Brevard County, FL.

Forked from NextAutomation Cost Forecaster v1.0.
Adapted for BidDeed.AI (foreclosure rehab budgets) and ZoneWise.AI (renovation ROI).

NOT for $18M commercial jobs. This is for $25K-$250K residential rehab/flip/rental projects
typical of Brevard County foreclosure and tax deed acquisitions.

6-stage pipeline:
  1. BUDGET    — Load/create project budget from template or manual input
  2. VELOCITY  — Spend velocity analysis (burn rate, acceleration, earned value)
  3. HISTORY   — Pattern match against completed Brevard rehab projects (Supabase)
  4. FORECAST  — Category-level cost-to-complete projection
  5. ALERTS    — Overrun detection with severity (WATCH/WARNING/ALERT/CRITICAL)
  6. SCENARIOS — Best/base/worst case + mitigation recommendations

Usage:
  python -m forecaster.agent forecast --parcel "25-37-22-00-00123.0-0000.00" --budget 85000
  python -m forecaster.agent forecast --project my_rehab --update-spend invoice.csv
  python -m forecaster.agent compare --project my_rehab --scenario worst
  python -m forecaster.agent history --type sfr --zip 32937 --last 20
  python -m forecaster.agent status
"""
import httpx, json, os, sys, time, argparse, re, csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
BCPAO_API = "https://www.bcpao.us/api/v1"
UA = {"User-Agent": "BidDeed.AI/1.0 (cost-forecaster)"}

# Brevard rehab budget templates (% of total budget)
# Based on 10+ years of Ariel's foreclosure rehab experience
BUDGET_TEMPLATES = {
    "light_rehab": {
        "description": "Cosmetic — paint, flooring, fixtures, appliances",
        "typical_range": (15000, 40000),
        "categories": {
            "interior_paint": 0.15,
            "flooring": 0.20,
            "kitchen": 0.20,
            "bathrooms": 0.15,
            "fixtures_appliances": 0.10,
            "landscaping_exterior": 0.05,
            "cleaning_dumpster": 0.05,
            "permits_fees": 0.02,
            "contingency": 0.08,
        },
    },
    "medium_rehab": {
        "description": "Cosmetic + systems — add roof, HVAC, plumbing, electrical",
        "typical_range": (40000, 100000),
        "categories": {
            "roof": 0.15,
            "hvac": 0.12,
            "plumbing": 0.08,
            "electrical": 0.08,
            "interior_paint": 0.08,
            "flooring": 0.10,
            "kitchen": 0.12,
            "bathrooms": 0.10,
            "fixtures_appliances": 0.05,
            "landscaping_exterior": 0.04,
            "permits_fees": 0.03,
            "contingency": 0.10,
        },
    },
    "heavy_rehab": {
        "description": "Full gut — structural, all systems, everything",
        "typical_range": (100000, 250000),
        "categories": {
            "structural": 0.10,
            "roof": 0.10,
            "hvac": 0.10,
            "plumbing": 0.08,
            "electrical": 0.08,
            "windows_doors": 0.08,
            "interior_paint": 0.06,
            "flooring": 0.08,
            "kitchen": 0.10,
            "bathrooms": 0.08,
            "fixtures_appliances": 0.04,
            "landscaping_exterior": 0.05,
            "permits_fees": 0.03,
            "contingency": 0.12,
        },
    },
}

# Severity thresholds (% over pace)
SEVERITY = {
    "WATCH":    (0.03, 0.05),
    "WARNING":  (0.05, 0.10),
    "ALERT":    (0.10, 0.15),
    "CRITICAL": (0.15, float("inf")),
}

# Brevard-specific cost indices (updated annually)
BREVARD_COST_INDEX = {
    "roof_per_sqft": 5.50,          # Shingle roof $/sqft
    "hvac_per_ton": 4500,           # Central AC $/ton
    "interior_paint_per_sqft": 2.50, # Interior paint $/sqft
    "flooring_per_sqft": 6.00,      # LVP/tile $/sqft
    "kitchen_base": 12000,          # Base kitchen reno
    "bathroom_base": 6000,          # Base bathroom reno
    "dumpster_per_load": 450,       # 20-yard dumpster
    "labor_hourly_avg": 45,         # GC labor average
}


# ═══════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════

def log(stage: str, msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    prefix = {"INFO": "●", "OK": "✓", "WARN": "⚠", "ERR": "✗", "SKIP": "○"}.get(level, "●")
    print(f"  [{ts}] {prefix} [{stage}] {msg}", file=sys.stderr)


def notify_telegram(msg: str):
    if not TELEGRAM_BOT or not TELEGRAM_CHAT:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10, headers=UA,
        )
    except Exception:
        pass


def supabase_query(table: str, params: Dict = None) -> List[Dict]:
    """Query Supabase table."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        r = httpx.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            params=params or {},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log("DB", f"Query failed: {e}", "ERR")
        return []


def supabase_upsert(table: str, records: List[Dict]):
    if not SUPABASE_URL or not SUPABASE_KEY:
        log("DB", "Supabase not configured", "WARN")
        return
    try:
        r = httpx.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=records, timeout=30,
        )
        r.raise_for_status()
        log("DB", f"Upserted {len(records)} to {table}", "OK")
    except Exception as e:
        log("DB", f"Upsert failed: {e}", "ERR")


# ═══════════════════════════════════════════════════════════════
# STAGE 1: BUDGET — Create/load project budget
# ═══════════════════════════════════════════════════════════════

def stage_budget(
    total_budget: float,
    template: str = "medium_rehab",
    parcel_id: str = None,
    sqft: int = None,
    custom_categories: Dict = None,
) -> Dict:
    """
    Create a project budget from template or custom breakdown.
    Optionally pulls sqft from BCPAO for cost-per-sqft estimates.
    """
    log("BUDGET", f"Creating budget: ${total_budget:,.0f} ({template})")
    tmpl = BUDGET_TEMPLATES.get(template, BUDGET_TEMPLATES["medium_rehab"])

    budget = {
        "total": total_budget,
        "template": template,
        "description": tmpl["description"],
        "categories": {},
        "sqft": sqft,
        "cost_per_sqft": None,
        "parcel_id": parcel_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "confidence": 0.0,
    }

    # Pull sqft from BCPAO if not provided
    if not sqft and parcel_id:
        try:
            account = parcel_id.replace("-", "").replace(".", "")
            client = httpx.Client(timeout=15, headers=UA)
            r = client.get(f"{BCPAO_API}/search?acct={account}")
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    sqft = data[0].get("totalArea") or data[0].get("heatedArea")
                    if sqft:
                        budget["sqft"] = int(sqft)
                        log("BUDGET", f"BCPAO sqft: {sqft}", "OK")
            client.close()
        except Exception as e:
            log("BUDGET", f"BCPAO sqft lookup failed: {e}", "WARN")

    if budget["sqft"] and budget["sqft"] > 0:
        budget["cost_per_sqft"] = round(total_budget / budget["sqft"], 2)

    # Build category breakdown
    cats = custom_categories or tmpl["categories"]
    for cat, pct in cats.items():
        budget["categories"][cat] = {
            "budgeted": round(total_budget * pct, 2),
            "pct_of_total": pct,
            "spent": 0.0,
            "committed": 0.0,  # POs / contracts signed
            "remaining": round(total_budget * pct, 2),
            "status": "ON_TRACK",
        }

    budget["confidence"] = 0.70 if custom_categories else 0.50
    log("BUDGET", f"{len(budget['categories'])} categories, ${total_budget:,.0f} total", "OK")
    return budget


# ═══════════════════════════════════════════════════════════════
# STAGE 2: VELOCITY — Spend rate analysis
# ═══════════════════════════════════════════════════════════════

def stage_velocity(
    budget: Dict,
    spend_log: List[Dict] = None,
    start_date: str = None,
    projected_weeks: int = None,
) -> Dict:
    """
    Analyze spend velocity: burn rate, acceleration, earned value.
    spend_log: list of {date, category, amount, description}
    """
    log("VELOCITY", "Calculating spend velocity")

    velocity = {
        "total_spent": 0.0,
        "total_budget": budget["total"],
        "pct_spent": 0.0,
        "days_elapsed": 0,
        "daily_burn": 0.0,
        "weekly_burn": 0.0,
        "budgeted_weekly_burn": 0.0,
        "acceleration_factor": 1.0,
        "earned_value_ratio": 1.0,
        "completion_velocity": 1.0,  # >1 = over-spending, <1 = under-spending
        "projected_weeks_remaining": None,
        "category_velocity": {},
        "confidence": 0.0,
    }

    if not spend_log:
        log("VELOCITY", "No spend log provided — using budget totals only", "WARN")
        # Sum up any spent amounts already in budget categories
        total_spent = sum(c.get("spent", 0) for c in budget["categories"].values())
        velocity["total_spent"] = total_spent
        velocity["pct_spent"] = total_spent / budget["total"] if budget["total"] > 0 else 0
        velocity["confidence"] = 0.30
        return velocity

    # Process spend log
    spends_by_date = {}
    spends_by_cat = {}
    for entry in spend_log:
        date = entry.get("date", "")
        cat = entry.get("category", "other")
        amt = float(entry.get("amount", 0))
        velocity["total_spent"] += amt
        spends_by_date.setdefault(date, 0)
        spends_by_date[date] += amt
        spends_by_cat.setdefault(cat, 0)
        spends_by_cat[cat] += amt

    velocity["pct_spent"] = velocity["total_spent"] / budget["total"] if budget["total"] > 0 else 0

    # Calculate elapsed days
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            velocity["days_elapsed"] = (now - start).days
        except Exception:
            pass

    if velocity["days_elapsed"] > 0:
        velocity["daily_burn"] = velocity["total_spent"] / velocity["days_elapsed"]
        velocity["weekly_burn"] = velocity["daily_burn"] * 7

    if projected_weeks and projected_weeks > 0:
        velocity["budgeted_weekly_burn"] = budget["total"] / projected_weeks

    if velocity["budgeted_weekly_burn"] > 0:
        velocity["completion_velocity"] = velocity["weekly_burn"] / velocity["budgeted_weekly_burn"]

    # Per-category velocity
    for cat, spent in spends_by_cat.items():
        budgeted = budget["categories"].get(cat, {}).get("budgeted", 0)
        if budgeted > 0:
            velocity["category_velocity"][cat] = {
                "spent": spent,
                "budgeted": budgeted,
                "pct_consumed": spent / budgeted,
                "pace": "OVER" if spent / budgeted > velocity["pct_spent"] + 0.05 else
                        "UNDER" if spent / budgeted < velocity["pct_spent"] - 0.05 else "ON_PACE",
            }

    # Recent acceleration (last 2 weeks vs prior 2 weeks)
    if len(spends_by_date) >= 14:
        sorted_dates = sorted(spends_by_date.keys())
        recent = sum(spends_by_date[d] for d in sorted_dates[-14:-7]) or 1
        latest = sum(spends_by_date[d] for d in sorted_dates[-7:])
        velocity["acceleration_factor"] = round(latest / recent, 2) if recent > 0 else 1.0

    velocity["confidence"] = 0.70 if len(spend_log) >= 10 else 0.40
    log("VELOCITY", f"Spent: ${velocity['total_spent']:,.0f} ({velocity['pct_spent']:.0%}) | "
                    f"Weekly: ${velocity['weekly_burn']:,.0f} | Accel: {velocity['acceleration_factor']}x", "OK")
    return velocity


# ═══════════════════════════════════════════════════════════════
# STAGE 3: HISTORY — Pattern match against completed projects
# ═══════════════════════════════════════════════════════════════

def stage_history(
    template: str = "medium_rehab",
    zip_code: str = None,
    budget_range: tuple = None,
    limit: int = 20,
) -> Dict:
    """
    Pull completed rehab projects from Supabase for pattern matching.
    Uses historical_auctions + property_profiles tables.
    """
    log("HISTORY", f"Matching historical projects ({template}, zip={zip_code})")
    history = {
        "matched_projects": 0,
        "avg_final_cost": None,
        "avg_overrun_pct": None,
        "avg_timeline_weeks": None,
        "common_overrun_categories": [],
        "cost_per_sqft_range": None,
        "confidence": 0.0,
    }

    # Query Supabase historical_auctions for completed projects
    params = {"select": "*", "limit": str(limit), "order": "sale_date.desc"}
    if zip_code:
        params["zip_code"] = f"eq.{zip_code}"

    rows = supabase_query("historical_auctions", params)
    if rows:
        history["matched_projects"] = len(rows)
        # Extract repair cost data if available
        repairs = [r.get("repair_estimate", 0) for r in rows if r.get("repair_estimate")]
        if repairs:
            history["avg_final_cost"] = round(sum(repairs) / len(repairs), 0)
        log("HISTORY", f"Found {len(rows)} historical projects", "OK")
        history["confidence"] = 0.50 if len(rows) >= 5 else 0.25
    else:
        log("HISTORY", "No historical data found in Supabase", "WARN")

    # Brevard-specific patterns (from decade of experience)
    history["brevard_patterns"] = {
        "roof_hurricane_premium": 0.15,    # FL hurricane code adds 15% to roof costs
        "hvac_humidity_factor": 1.10,      # Coastal humidity → oversized HVAC
        "flood_zone_premium": 0.20,        # AE/VE zones add 20% to foundation/site
        "permit_timeline_weeks": 4,        # Brevard County avg permit turnaround
        "common_surprises": [
            "Termite damage behind walls (30% of Brevard rehabs)",
            "Chinese drywall in 2004-2009 builds",
            "Polybutylene plumbing (pre-1995 homes)",
            "Hurricane strap retrofitting requirements",
            "Stucco water intrusion in block construction",
        ],
    }

    return history


# ═══════════════════════════════════════════════════════════════
# STAGE 4: FORECAST — Category-level cost projection
# ═══════════════════════════════════════════════════════════════

def stage_forecast(
    budget: Dict,
    velocity: Dict,
    history: Dict,
    historical_weight: float = 0.30,
) -> Dict:
    """
    Project remaining costs per category using blended model:
    - Velocity extrapolation (70% weight default)
    - Historical pattern adjustment (30% weight default)
    """
    log("FORECAST", "Projecting cost-to-complete")
    forecast = {
        "categories": {},
        "total_forecast": 0.0,
        "total_variance": 0.0,
        "variance_pct": 0.0,
        "contingency_remaining": 0.0,
        "contingency_exhaustion_date": None,
        "confidence": 0.0,
    }

    vel_weight = 1.0 - historical_weight
    total_budget = budget["total"]

    for cat, cat_budget in budget["categories"].items():
        budgeted = cat_budget["budgeted"]
        spent = cat_budget.get("spent", 0)
        committed = cat_budget.get("committed", 0)

        # Velocity-based forecast
        cat_vel = velocity.get("category_velocity", {}).get(cat, {})
        pct_consumed = cat_vel.get("pct_consumed", spent / budgeted if budgeted > 0 else 0)
        overall_pct = velocity.get("pct_spent", 0)

        if overall_pct > 0 and pct_consumed > 0:
            # Extrapolate: if category is X% consumed at Y% project completion
            velocity_forecast = spent / overall_pct if overall_pct > 0.05 else budgeted
        else:
            velocity_forecast = budgeted

        # History-based adjustment
        hist_adj = history.get("avg_overrun_pct", 0) or 0
        history_forecast = budgeted * (1 + hist_adj / 100)

        # Blended forecast
        if spent > 0:
            blended = (velocity_forecast * vel_weight) + (history_forecast * historical_weight)
        else:
            blended = budgeted  # Not started yet, use budget

        remaining = max(0, blended - spent - committed)
        variance = blended - budgeted

        forecast["categories"][cat] = {
            "budgeted": budgeted,
            "spent": spent,
            "committed": committed,
            "forecast_total": round(blended, 2),
            "remaining": round(remaining, 2),
            "variance": round(variance, 2),
            "variance_pct": round(variance / budgeted, 4) if budgeted > 0 else 0,
        }

        if cat != "contingency":
            forecast["total_forecast"] += blended

    # Contingency tracking
    contingency_budget = budget["categories"].get("contingency", {}).get("budgeted", 0)
    contingency_spent = budget["categories"].get("contingency", {}).get("spent", 0)
    forecast["contingency_remaining"] = contingency_budget - contingency_spent
    forecast["total_forecast"] += contingency_budget  # Include original contingency

    forecast["total_variance"] = round(forecast["total_forecast"] - total_budget, 2)
    forecast["variance_pct"] = round(forecast["total_variance"] / total_budget, 4) if total_budget > 0 else 0

    # Contingency exhaustion estimate
    if velocity.get("weekly_burn", 0) > 0 and forecast["total_variance"] > 0:
        weeks_of_contingency = forecast["contingency_remaining"] / (velocity["weekly_burn"] * 0.10)
        if weeks_of_contingency > 0:
            exhaust_date = datetime.now(timezone.utc) + timedelta(weeks=weeks_of_contingency)
            forecast["contingency_exhaustion_date"] = exhaust_date.strftime("%Y-%m-%d")

    confidences = [velocity.get("confidence", 0), history.get("confidence", 0), budget.get("confidence", 0)]
    forecast["confidence"] = round(sum(confidences) / len(confidences), 2)

    log("FORECAST", f"Forecast: ${forecast['total_forecast']:,.0f} | "
                    f"Variance: ${forecast['total_variance']:,.0f} ({forecast['variance_pct']:.1%})", "OK")
    return forecast


# ═══════════════════════════════════════════════════════════════
# STAGE 5: ALERTS — Overrun detection
# ═══════════════════════════════════════════════════════════════

def stage_alerts(forecast: Dict, alert_threshold: float = 0.05) -> Dict:
    """
    Flag categories exceeding thresholds.
    Severity: WATCH → WARNING → ALERT → CRITICAL
    """
    log("ALERTS", f"Scanning for overruns (threshold: {alert_threshold:.0%})")
    alerts = {
        "items": [],
        "critical_count": 0,
        "alert_count": 0,
        "warning_count": 0,
        "watch_count": 0,
        "total_overrun": 0.0,
        "margin_impact_bps": 0,
        "confidence": 0.0,
    }

    for cat, data in forecast.get("categories", {}).items():
        if cat == "contingency":
            continue
        var_pct = abs(data.get("variance_pct", 0))
        if var_pct < 0.03:
            continue  # Below watch threshold

        severity = "WATCH"
        for sev, (lo, hi) in SEVERITY.items():
            if lo <= var_pct < hi:
                severity = sev
                break

        alert = {
            "category": cat,
            "severity": severity,
            "variance_pct": round(var_pct, 4),
            "variance_amount": data.get("variance", 0),
            "budgeted": data.get("budgeted", 0),
            "forecast": data.get("forecast_total", 0),
            "recommendation": _mitigation_for(cat, severity, data.get("variance", 0)),
        }
        alerts["items"].append(alert)
        alerts["total_overrun"] += data.get("variance", 0)

        if severity == "CRITICAL":
            alerts["critical_count"] += 1
        elif severity == "ALERT":
            alerts["alert_count"] += 1
        elif severity == "WARNING":
            alerts["warning_count"] += 1
        else:
            alerts["watch_count"] += 1

    # Margin impact (assuming 30% target margin on flip)
    total_budget = sum(d.get("budgeted", 0) for d in forecast.get("categories", {}).values())
    if total_budget > 0:
        alerts["margin_impact_bps"] = round((alerts["total_overrun"] / total_budget) * 10000)

    alerts["confidence"] = forecast.get("confidence", 0)
    total = alerts["critical_count"] + alerts["alert_count"] + alerts["warning_count"] + alerts["watch_count"]
    log("ALERTS", f"{total} items: {alerts['critical_count']}C/{alerts['alert_count']}A/"
                  f"{alerts['warning_count']}W/{alerts['watch_count']}w | "
                  f"Overrun: ${alerts['total_overrun']:,.0f}", "OK" if total == 0 else "WARN")
    return alerts


def _mitigation_for(category: str, severity: str, variance: float) -> str:
    """Generate Brevard-specific mitigation recommendation."""
    mitigations = {
        "roof": "Get 3 quotes from licensed FL roofers. Check for insurance supplement claim potential.",
        "hvac": "Verify tonnage — Brevard homes often oversized. Consider SEER-rated rebate programs.",
        "plumbing": "If polybutylene found, full repipe is mandatory. Budget $4-8K for typical SFR.",
        "electrical": "Check panel age. FPL rebates available for panel upgrades.",
        "kitchen": "Value engineer: stock cabinets + granite counters saves 30% vs custom.",
        "bathrooms": "Standardize fixtures across all bathrooms for volume pricing.",
        "structural": "Get structural engineer report before committing. Typical Brevard issue: block wall cracks.",
        "flooring": "LVP over tile saves demo costs. Budget $3-4/sqft installed in Brevard market.",
    }
    base = mitigations.get(category, f"Review {category} scope for value engineering opportunities.")
    if severity in ("ALERT", "CRITICAL"):
        base = f"URGENT: {base} Consider scope reduction or contractor rebid."
    return base


# ═══════════════════════════════════════════════════════════════
# STAGE 6: SCENARIOS — Best/base/worst case
# ═══════════════════════════════════════════════════════════════

def stage_scenarios(
    budget: Dict,
    forecast: Dict,
    alerts: Dict,
    arv: float = None,
) -> Dict:
    """
    Generate 3 scenarios for cost-to-complete.
    If ARV provided, calculate ROI impact per scenario.
    """
    log("SCENARIOS", "Generating best/base/worst case")
    base_total = forecast.get("total_forecast", budget["total"])
    total_budget = budget["total"]

    scenarios = {
        "best_case": {
            "total": round(base_total * 0.92, 0),  # 8% under forecast
            "assumption": "Current overruns resolved, no new surprises, contingency preserved",
        },
        "base_case": {
            "total": round(base_total, 0),
            "assumption": "Current trajectory continues with historical Brevard adjustments",
        },
        "worst_case": {
            "total": round(base_total * 1.15, 0),  # 15% over forecast
            "assumption": "Known risks materialize (termites, plumbing, permit delays), contingency consumed",
        },
    }

    for name, scenario in scenarios.items():
        scenario["variance"] = round(scenario["total"] - total_budget, 0)
        scenario["variance_pct"] = round(scenario["variance"] / total_budget, 4) if total_budget > 0 else 0
        scenario["contingency_remaining"] = round(
            forecast.get("contingency_remaining", 0) - max(0, scenario["variance"]), 0
        )

        # ROI calculation if ARV provided
        if arv and arv > 0:
            # Simple flip ROI: (ARV - purchase - rehab) / (purchase + rehab)
            # Purchase price not known here, so calculate rehab margin impact
            scenario["rehab_pct_of_arv"] = round(scenario["total"] / arv, 4)
            # Using 70% rule: max_bid = ARV*0.70 - repairs
            scenario["max_bid_at_this_cost"] = round(arv * 0.70 - scenario["total"] - 10000, 0)

    log("SCENARIOS", f"Best: ${scenarios['best_case']['total']:,.0f} | "
                     f"Base: ${scenarios['base_case']['total']:,.0f} | "
                     f"Worst: ${scenarios['worst_case']['total']:,.0f}", "OK")
    return scenarios


# ═══════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

def run_forecast(
    total_budget: float,
    template: str = "medium_rehab",
    parcel_id: str = None,
    zip_code: str = None,
    spend_log: List[Dict] = None,
    start_date: str = None,
    projected_weeks: int = None,
    arv: float = None,
    alert_threshold: float = 0.05,
    historical_weight: float = 0.30,
) -> Dict:
    """Main entry point. Runs the full forecast pipeline."""

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  COST FORECASTER — ${total_budget:,.0f} ({template})", file=sys.stderr)
    print(f"  Parcel: {parcel_id or 'N/A'} | ZIP: {zip_code or 'N/A'}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    t0 = time.time()
    result = {
        "input": {
            "total_budget": total_budget,
            "template": template,
            "parcel_id": parcel_id,
        },
        "stages": {},
        "forecast_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": None,
    }

    # Stage 1: BUDGET
    result["stages"]["budget"] = stage_budget(
        total_budget, template, parcel_id,
    )

    # Stage 2: VELOCITY
    result["stages"]["velocity"] = stage_velocity(
        result["stages"]["budget"], spend_log, start_date, projected_weeks,
    )

    # Stage 3: HISTORY
    result["stages"]["history"] = stage_history(
        template, zip_code,
    )

    # Stage 4: FORECAST
    result["stages"]["forecast"] = stage_forecast(
        result["stages"]["budget"],
        result["stages"]["velocity"],
        result["stages"]["history"],
        historical_weight,
    )

    # Stage 5: ALERTS
    result["stages"]["alerts"] = stage_alerts(
        result["stages"]["forecast"], alert_threshold,
    )

    # Stage 6: SCENARIOS
    result["stages"]["scenarios"] = stage_scenarios(
        result["stages"]["budget"],
        result["stages"]["forecast"],
        result["stages"]["alerts"],
        arv,
    )

    result["elapsed_seconds"] = round(time.time() - t0, 1)

    # Summary
    fc = result["stages"]["forecast"]
    alerts = result["stages"]["alerts"]
    sc = result["stages"]["scenarios"]
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  FORECAST COMPLETE — {result['elapsed_seconds']}s", file=sys.stderr)
    print(f"  Budget: ${total_budget:,.0f} → Forecast: ${fc['total_forecast']:,.0f}", file=sys.stderr)
    print(f"  Variance: ${fc['total_variance']:,.0f} ({fc['variance_pct']:.1%})", file=sys.stderr)
    print(f"  Alerts: {alerts['critical_count']}C/{alerts['alert_count']}A/"
          f"{alerts['warning_count']}W/{alerts['watch_count']}w", file=sys.stderr)
    print(f"  Worst case: ${sc['worst_case']['total']:,.0f}", file=sys.stderr)
    if arv:
        print(f"  Max bid at base cost: ${sc['base_case'].get('max_bid_at_this_cost', 0):,.0f}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    return result


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Cost Forecaster — BidDeed.AI + ZoneWise.AI",
    )
    sub = parser.add_subparsers(dest="command")

    # forecast command
    fc = sub.add_parser("forecast", help="Run cost forecast for a project")
    fc.add_argument("--budget", type=float, required=True, help="Total rehab budget")
    fc.add_argument("--template", choices=list(BUDGET_TEMPLATES.keys()), default="medium_rehab")
    fc.add_argument("--parcel", type=str, help="BCPAO parcel ID")
    fc.add_argument("--zip", type=str, help="ZIP code for historical matching")
    fc.add_argument("--arv", type=float, help="After Repair Value for ROI calc")
    fc.add_argument("--start", type=str, help="Project start date (YYYY-MM-DD)")
    fc.add_argument("--weeks", type=int, help="Projected timeline in weeks")
    fc.add_argument("--spend-csv", type=str, help="CSV file with spend log")
    fc.add_argument("--threshold", type=float, default=0.05, help="Alert threshold (default 5%%)")
    fc.add_argument("--json", action="store_true", help="Output JSON")
    fc.add_argument("--save", action="store_true", help="Save forecast to Supabase rehab_projects")

    # history command
    hist = sub.add_parser("history", help="Query historical rehab costs")
    hist.add_argument("--type", choices=list(BUDGET_TEMPLATES.keys()), default="medium_rehab")
    hist.add_argument("--zip", type=str)
    hist.add_argument("--last", type=int, default=20)

    # update-spend command
    us = sub.add_parser("update-spend", help="Log an expense")
    us.add_argument("--parcel", required=True, help="Parcel ID")
    us.add_argument("--category", required=True, help="Budget category")
    us.add_argument("--amount", type=float, required=True, help="Amount spent")
    us.add_argument("--vendor", type=str, help="Vendor name")
    us.add_argument("--description", type=str, help="Description")
    us.add_argument("--date", type=str, help="Spend date YYYY-MM-DD")

    # status command
    sub.add_parser("status", help="Check connectivity")

    args = parser.parse_args()

    if args.command == "forecast":
        spend_log = None
        if args.spend_csv:
            with open(args.spend_csv) as f:
                spend_log = list(csv.DictReader(f))
            log("CLI", f"Loaded {len(spend_log)} spend entries from {args.spend_csv}")

        result = run_forecast(
            total_budget=args.budget,
            template=args.template,
            parcel_id=args.parcel,
            zip_code=args.zip,
            spend_log=spend_log,
            start_date=args.start,
            projected_weeks=args.weeks,
            arv=args.arv,
            alert_threshold=args.threshold,
        )
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        if getattr(args, 'save', False):
            fc = result.get("stages", {}).get("forecast", {})
            sc = result.get("stages", {}).get("scenarios", {})
            al = result.get("stages", {}).get("alerts", {})
            vel = result.get("stages", {}).get("velocity", {})
            supabase_upsert("rehab_projects", [{
                "parcel_id": args.parcel or "unknown",
                "template": args.template,
                "total_budget": args.budget,
                "total_spent": vel.get("total_spent", 0),
                "total_forecast": fc.get("total_forecast"),
                "variance_pct": fc.get("variance_pct"),
                "arv": args.arv,
                "status": "ACTIVE",
                "alerts_json": json.dumps(al),
                "scenarios_json": json.dumps(sc),
            }])

    elif args.command == "update-spend":
        log("CLI", f"Logging spend: ${args.amount:,.2f} → {args.category} for {args.parcel}")
        record = {
            "parcel_id": args.parcel,
            "category": args.category,
            "amount": args.amount,
            "vendor": args.vendor,
            "description": args.description,
            "spend_date": args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        supabase_upsert("rehab_spend_log", [record])
        # Query total spent for this parcel
        rows = supabase_query("rehab_spend_log", {
            "select": "amount", "parcel_id": f"eq.{args.parcel}",
        })
        total = sum(float(r.get("amount", 0)) for r in rows) if rows else args.amount
        log("CLI", f"Total spent on {args.parcel}: ${total:,.2f}", "OK")

    elif args.command == "history":
        h = stage_history(args.type, args.zip, limit=args.last)
        print(json.dumps(h, indent=2, default=str))

    elif args.command == "status":
        print("\n  Cost Forecaster — Status Check", file=sys.stderr)
        print("  " + "=" * 40, file=sys.stderr)
        _check_connectivity()

    else:
        parser.print_help()


def _check_connectivity():
    sources = [
        ("BCPAO API", f"{BCPAO_API}/search?acct=2537220000001"),
        ("Supabase", f"{SUPABASE_URL}/rest/v1/" if SUPABASE_URL else None),
    ]
    client = httpx.Client(timeout=10, headers=UA)
    for name, url in sources:
        if not url:
            log("STATUS", f"{name}: NOT CONFIGURED", "WARN")
            continue
        try:
            r = client.get(url)
            log("STATUS", f"{name}: {r.status_code}", "OK" if r.status_code == 200 else "WARN")
        except Exception as e:
            log("STATUS", f"{name}: {e}", "ERR")
    client.close()


if __name__ == "__main__":
    main()

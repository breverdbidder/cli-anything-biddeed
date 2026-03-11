"""
cli-anything-btr: Build-to-Rent + Distressed Asset Squad CLI
=============================================================
Part of the BidDeed.AI CLI-Anything Agent Army.

Squad: EVEREST-BTR
Agents: 10 (4 scenario + 6 shared intelligence)
Property Types: SFR | Duplex | Multifamily
"""
import json
import sys
from datetime import datetime, timezone

import click

# ── Property type constants ──────────────────────────────────
PROPERTY_TYPES = ("sfr", "duplex", "multifamily")

# ── MAI reconciliation weights by property type ──────────────
MAI_WEIGHTS = {
    "sfr":           {"income": 0.30, "comp": 0.60, "cost": 0.10},
    "duplex":        {"income": 0.40, "comp": 0.45, "cost": 0.15},
    "multifamily":   {"income": 0.60, "comp": 0.25, "cost": 0.15},
    "new_construct":  {"income": 0.25, "comp": 0.35, "cost": 0.40},
    "distressed":    {"income": 0.20, "comp": 0.50, "cost": 0.30},
}

# ── Decision thresholds ──────────────────────────────────────
THRESHOLDS = {"bid": 75, "review": 60}


def _output(data: dict, as_json: bool = False):
    """Standard output: JSON to stdout for piping, rich for humans."""
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title=data.get("agent", "BTR Squad"))
        table.add_column("Key", style="bold cyan")
        table.add_column("Value")
        for k, v in data.items():
            table.add_row(str(k), str(v))
        console.print(table)


def _decision(score: float) -> str:
    """BID / REVIEW / SKIP based on score."""
    if score >= THRESHOLDS["bid"]:
        return "BID"
    elif score >= THRESHOLDS["review"]:
        return "REVIEW"
    return "SKIP"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════
# ROOT CLI GROUP
# ══════════════════════════════════════════════════════════════

@click.group()
@click.option("--json", "as_json", is_flag=True, help="Output JSON for piping")
@click.pass_context
def cli(ctx, as_json):
    """EVEREST-BTR Squad — Build-to-Rent + Distressed Asset AI Agents."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json


# ══════════════════════════════════════════════════════════════
# SQUAD COMMANDER
# ══════════════════════════════════════════════════════════════

@cli.command()
@click.argument("address")
@click.option("--type", "prop_type", type=click.Choice(PROPERTY_TYPES), required=True)
@click.option("--scenario", type=click.Choice(["land", "construction", "permanent", "rehab", "full"]), default="full")
@click.pass_context
def analyze(ctx, address, prop_type, scenario):
    """Squad Commander: Route property through scenario agents."""
    result = {
        "agent": "cli_btr.commander",
        "timestamp": _timestamp(),
        "address": address,
        "property_type": prop_type,
        "scenario": scenario,
        "status": "routed",
        "pipeline": [],
    }

    agents_to_run = {
        "land": ["cli_btr.land", "cli_btr.hbu", "cli_btr.mai"],
        "construction": ["cli_btr.con", "cli_btr.cost", "cli_btr.mai"],
        "permanent": ["cli_btr.perm", "cli_btr.lv", "cli_btr.mai"],
        "rehab": ["cli_btr.rehab", "cli_btr.hbu", "cli_btr.cost", "cli_btr.mai"],
        "full": ["cli_btr.land", "cli_btr.con", "cli_btr.perm", "cli_btr.hbu",
                  "cli_btr.cost", "cli_btr.mai", "cli_btr.lv", "cli_btr.proforma"],
    }

    result["pipeline"] = agents_to_run.get(scenario, [])
    result["msg"] = f"Dispatched {len(result['pipeline'])} agents for {prop_type.upper()} {scenario} analysis"
    _output(result, ctx.obj["json"])


# ══════════════════════════════════════════════════════════════
# MAI VALUATION ENGINE
# ══════════════════════════════════════════════════════════════

@cli.command()
@click.argument("address")
@click.option("--type", "prop_type", type=click.Choice(PROPERTY_TYPES), required=True)
@click.option("--noi", type=float, help="Net Operating Income")
@click.option("--cap-rate", type=float, help="Market cap rate (e.g. 0.065)")
@click.option("--comp-value", type=float, help="Sales comparison value")
@click.option("--cost-value", type=float, help="Cost approach value")
@click.pass_context
def mai(ctx, address, prop_type, noi, cap_rate, comp_value, cost_value):
    """MAI Valuation Engine: 3-approach appraisal method."""
    weights = MAI_WEIGHTS.get(prop_type, MAI_WEIGHTS["sfr"])
    values = {}

    # Income Approach
    if noi and cap_rate and cap_rate > 0:
        values["income"] = round(noi / cap_rate, 2)
    # Sales Comparison
    if comp_value:
        values["comp"] = comp_value
    # Cost Approach
    if cost_value:
        values["cost"] = cost_value

    # Reconciliation
    reconciled = 0.0
    total_weight = 0.0
    for approach, val in values.items():
        w = weights.get(approach, 0)
        reconciled += val * w
        total_weight += w

    final_value = round(reconciled / total_weight, 2) if total_weight > 0 else 0

    result = {
        "agent": "cli_btr.mai",
        "timestamp": _timestamp(),
        "address": address,
        "property_type": prop_type,
        "approach_values": values,
        "weights": weights,
        "reconciled_value": final_value,
        "confidence": "high" if len(values) == 3 else "medium" if len(values) == 2 else "low",
        "disclaimer": "Decision-support tool only. Not a licensed MAI appraisal.",
    }
    _output(result, ctx.obj["json"])


# ══════════════════════════════════════════════════════════════
# HBU ANALYSIS
# ══════════════════════════════════════════════════════════════

@cli.command()
@click.argument("parcel_id")
@click.option("--zoning", type=str, help="Current zoning classification")
@click.option("--lot-sf", type=float, help="Lot size in square feet")
@click.pass_context
def hbu(ctx, parcel_id, zoning, lot_sf):
    """Highest & Best Use: 4-test MAI analysis."""
    result = {
        "agent": "cli_btr.hbu",
        "timestamp": _timestamp(),
        "parcel_id": parcel_id,
        "zoning": zoning,
        "lot_sf": lot_sf,
        "tests": {
            "legally_permissible": "pending — requires zoning lookup via cli-anything-spatial",
            "physically_possible": "pending — requires site/topo data",
            "financially_feasible": "pending — requires market analysis",
            "maximally_productive": "pending — requires residual land value calc",
        },
        "hbu_determination": "pending",
        "status": "scaffold",
    }
    _output(result, ctx.obj["json"])


# ══════════════════════════════════════════════════════════════
# LAND ACQUISITION
# ══════════════════════════════════════════════════════════════

@cli.command()
@click.argument("address")
@click.option("--type", "prop_type", type=click.Choice(PROPERTY_TYPES), required=True)
@click.option("--units", type=int, default=1, help="Target unit count")
@click.pass_context
def land(ctx, address, prop_type, units):
    """Land Acquisition Agent: Evaluate raw land for BTR development."""
    result = {
        "agent": "cli_btr.land",
        "timestamp": _timestamp(),
        "address": address,
        "property_type": prop_type,
        "target_units": units,
        "max_ltv_land_only": "60-65%",
        "loan_path": "land_only" if units == 0 else "acquisition_plus_construction",
        "status": "scaffold",
        "next": ["cli_btr.hbu", "cli_btr.mai"],
    }
    _output(result, ctx.obj["json"])


# ══════════════════════════════════════════════════════════════
# CONSTRUCTION FUNDING
# ══════════════════════════════════════════════════════════════

@cli.command()
@click.argument("address")
@click.option("--type", "prop_type", type=click.Choice(PROPERTY_TYPES), required=True)
@click.option("--units", type=int, required=True)
@click.option("--sf-per-unit", type=float, required=True)
@click.pass_context
def construction(ctx, address, prop_type, units, sf_per_unit):
    """Construction Funding Agent: Budget and draw schedule modeling."""
    cost_ranges = {
        "sfr": (150, 250), "duplex": (140, 230), "multifamily": (120, 200)
    }
    low, high = cost_ranges[prop_type]
    total_sf = units * sf_per_unit

    result = {
        "agent": "cli_btr.con",
        "timestamp": _timestamp(),
        "address": address,
        "property_type": prop_type,
        "units": units,
        "sf_per_unit": sf_per_unit,
        "total_sf": total_sf,
        "cost_range_per_sf": f"${low}-${high}",
        "budget_range": f"${round(total_sf * low):,} - ${round(total_sf * high):,}",
        "status": "scaffold",
        "next": ["cli_btr.cost", "cli_btr.perm"],
    }
    _output(result, ctx.obj["json"])


# ══════════════════════════════════════════════════════════════
# PERMANENT FUNDING
# ══════════════════════════════════════════════════════════════

@cli.command()
@click.argument("address")
@click.option("--noi", type=float, required=True, help="Stabilized NOI")
@click.option("--rate", type=float, required=True, help="Permanent interest rate")
@click.option("--dcr", type=float, default=1.25, help="Target DCR")
@click.option("--amort", type=int, default=30, help="Amortization years")
@click.pass_context
def permanent(ctx, address, noi, rate, dcr, amort):
    """Permanent Funding Agent: Max perm loan + DCR analysis."""
    # Max annual debt service = NOI / DCR
    max_annual_ds = noi / dcr if dcr > 0 else 0
    max_monthly_ds = max_annual_ds / 12

    # Simplified max loan calc (P&I mortgage math)
    monthly_rate = rate / 12
    n_payments = amort * 12
    if monthly_rate > 0:
        max_loan = max_monthly_ds * ((1 - (1 + monthly_rate) ** -n_payments) / monthly_rate)
    else:
        max_loan = max_monthly_ds * n_payments

    result = {
        "agent": "cli_btr.perm",
        "timestamp": _timestamp(),
        "address": address,
        "noi": noi,
        "interest_rate": rate,
        "target_dcr": dcr,
        "amortization_years": amort,
        "max_annual_debt_service": round(max_annual_ds, 2),
        "max_perm_loan": round(max_loan, 2),
        "recommendation": "lock_rate" if rate < 0.07 else "float_and_monitor",
        "status": "scaffold",
        "next": ["cli_btr.lv", "cli_btr.proforma"],
    }
    _output(result, ctx.obj["json"])


# ══════════════════════════════════════════════════════════════
# DISTRESSED ASSET REHAB
# ══════════════════════════════════════════════════════════════

@cli.command()
@click.argument("address")
@click.option("--type", "prop_type", type=click.Choice(PROPERTY_TYPES), required=True)
@click.option("--arv", type=float, required=True, help="After Repair Value")
@click.option("--repairs", type=float, required=True, help="Estimated repair cost")
@click.pass_context
def rehab(ctx, address, prop_type, arv, repairs):
    """Distressed Asset Rehab Agent: Max bid + HBU for distressed properties."""
    # BidDeed.AI max bid formula
    buffer = 10000
    profit_margin = min(25000, 0.15 * arv)
    max_bid = (arv * 0.70) - repairs - buffer - profit_margin

    score = max(0, min(100, (max_bid / arv) * 100)) if arv > 0 else 0
    decision = _decision(score)

    result = {
        "agent": "cli_btr.rehab",
        "timestamp": _timestamp(),
        "address": address,
        "property_type": prop_type,
        "arv": arv,
        "repairs": repairs,
        "formula": "(ARV x 70%) - Repairs - $10K - MIN($25K, 15% x ARV)",
        "max_bid": round(max_bid, 2),
        "bid_to_arv_ratio": round((max_bid / arv) * 100, 1) if arv > 0 else 0,
        "score": round(score, 1),
        "decision": decision,
        "next": ["cli_btr.hbu", "cli_btr.cost", "cli_btr.mai"],
    }
    _output(result, ctx.obj["json"])


# ══════════════════════════════════════════════════════════════
# COST ESTIMATOR
# ══════════════════════════════════════════════════════════════

@cli.command()
@click.option("--type", "prop_type", type=click.Choice(PROPERTY_TYPES), required=True)
@click.option("--units", type=int, required=True)
@click.option("--sf-per-unit", type=float, required=True)
@click.option("--scope", type=click.Choice(["new", "rehab"]), default="new")
@click.option("--finish", type=click.Choice(["standard", "premium"]), default="standard")
@click.pass_context
def cost(ctx, prop_type, units, sf_per_unit, scope, finish):
    """Construction Cost Estimator: Brevard County cost modeling."""
    base_costs = {
        ("sfr", "new"): 185, ("sfr", "rehab"): 95,
        ("duplex", "new"): 170, ("duplex", "rehab"): 85,
        ("multifamily", "new"): 155, ("multifamily", "rehab"): 75,
    }
    base = base_costs.get((prop_type, scope), 150)
    if finish == "premium":
        base *= 1.25

    total_sf = units * sf_per_unit
    hard_cost = round(total_sf * base)
    soft_cost = round(hard_cost * 0.15)  # 15% soft costs
    contingency = round(hard_cost * 0.10)  # 10% contingency
    total = hard_cost + soft_cost + contingency

    result = {
        "agent": "cli_btr.cost",
        "timestamp": _timestamp(),
        "property_type": prop_type,
        "scope": scope,
        "finish": finish,
        "units": units,
        "sf_per_unit": sf_per_unit,
        "total_sf": total_sf,
        "cost_per_sf": base,
        "hard_cost": hard_cost,
        "soft_cost_15pct": soft_cost,
        "contingency_10pct": contingency,
        "total_budget": total,
        "per_unit_cost": round(total / units) if units > 0 else 0,
        "source": "Brevard County averages (OpenMud + local data)",
    }
    _output(result, ctx.obj["json"])


# ══════════════════════════════════════════════════════════════
# LENDER VETTING
# ══════════════════════════════════════════════════════════════

@cli.command("lender-vet")
@click.option("--dcr", type=float, help="Lender DCR requirement")
@click.option("--rate-lock", type=click.Choice(["commitment", "closing", "none"]), help="Rate lock timing")
@click.option("--term", type=int, help="Perm term years")
@click.option("--prepay", type=str, help="Prepay structure (e.g. '1pct' or '5-4-3-2-1')")
@click.option("--amort", type=int, help="Amortization years")
@click.pass_context
def lender_vet(ctx, dcr, rate_lock, term, prepay, amort):
    """Lender Vetting Agent: Score lender terms on leverage/risk/upside."""
    # Scoring rubric (0-100 per dimension)
    leverage_score = 0
    if dcr:
        leverage_score = max(0, 100 - ((dcr - 1.0) * 150))  # 1.20 = 70, 1.25 = 62.5, 1.30 = 55
    if amort:
        leverage_score += 15 if amort >= 30 else 5

    risk_score = 0
    if rate_lock == "commitment":
        risk_score += 40
    elif rate_lock == "closing":
        risk_score += 25
    if term:
        risk_score += min(30, term * 3)  # 10yr = 30pts

    upside_score = 0
    if prepay:
        if "1pct" in prepay.lower():
            upside_score += 35
        elif "5-4-3-2-1" in prepay:
            upside_score += 10
        else:
            upside_score += 20

    total = round((leverage_score + risk_score + upside_score) / 3, 1)

    result = {
        "agent": "cli_btr.lv",
        "timestamp": _timestamp(),
        "scores": {
            "leverage": round(leverage_score, 1),
            "risk_mitigation": round(risk_score, 1),
            "upside_preservation": round(upside_score, 1),
            "composite": total,
        },
        "terms_evaluated": {
            "dcr": dcr, "rate_lock": rate_lock,
            "term_years": term, "prepay": prepay, "amort": amort,
        },
        "recommendation": "strong_fit" if total >= 60 else "evaluate" if total >= 40 else "weak_fit",
    }
    _output(result, ctx.obj["json"])


# ══════════════════════════════════════════════════════════════
# PRO FORMA GENERATOR
# ══════════════════════════════════════════════════════════════

@cli.command("proforma")
@click.argument("address")
@click.option("--value", type=float, required=True, help="Property value / acquisition cost")
@click.option("--noi", type=float, required=True, help="Year 1 NOI")
@click.option("--loan", type=float, required=True, help="Loan amount")
@click.option("--rate", type=float, required=True, help="Interest rate")
@click.option("--growth", type=float, default=0.03, help="Annual rent growth rate")
@click.option("--hold", type=int, default=5, help="Hold period years")
@click.pass_context
def proforma(ctx, address, value, noi, loan, rate, growth, hold):
    """Pro Forma Generator: Multi-year projections + IRR."""
    equity = value - loan
    monthly_rate = rate / 12
    n_payments = 30 * 12
    if monthly_rate > 0:
        monthly_pmt = loan * (monthly_rate * (1 + monthly_rate)**n_payments) / ((1 + monthly_rate)**n_payments - 1)
    else:
        monthly_pmt = loan / n_payments
    annual_ds = monthly_pmt * 12

    cashflows = [-equity]  # Year 0: equity invested
    projections = []
    for year in range(1, hold + 1):
        yr_noi = noi * (1 + growth) ** (year - 1)
        yr_cf = yr_noi - annual_ds
        cashflows.append(yr_cf)
        projections.append({
            "year": year,
            "noi": round(yr_noi, 2),
            "debt_service": round(annual_ds, 2),
            "cash_flow": round(yr_cf, 2),
            "coc_return": f"{round((yr_cf / equity) * 100, 1)}%" if equity > 0 else "N/A",
        })

    # Terminal value (exit at same cap rate)
    exit_cap = noi / value if value > 0 else 0.065
    terminal_noi = noi * (1 + growth) ** hold
    terminal_value = terminal_noi / exit_cap if exit_cap > 0 else 0
    # Add terminal + remaining loan payoff to final year
    cashflows[-1] += terminal_value - loan * 0.85  # rough remaining balance

    result = {
        "agent": "cli_btr.proforma",
        "timestamp": _timestamp(),
        "address": address,
        "assumptions": {
            "value": value, "noi_year1": noi, "loan": loan,
            "rate": rate, "growth": growth, "hold_years": hold,
        },
        "equity_invested": round(equity, 2),
        "annual_debt_service": round(annual_ds, 2),
        "projections": projections,
        "exit_value": round(terminal_value, 2),
        "status": "scaffold — IRR calc needs numpy for full implementation",
    }
    _output(result, ctx.obj["json"])


# ══════════════════════════════════════════════════════════════
# ARMY STATUS
# ══════════════════════════════════════════════════════════════

@cli.command()
@click.pass_context
def status(ctx):
    """Show BTR Squad agent status."""
    agents = [
        ("cli_btr.commander", "Squad Commander", "scaffold"),
        ("cli_btr.land", "Land Acquisition", "scaffold"),
        ("cli_btr.con", "Construction Funding", "scaffold"),
        ("cli_btr.perm", "Permanent Funding", "scaffold"),
        ("cli_btr.rehab", "Distressed Rehab", "scaffold"),
        ("cli_btr.mai", "MAI Valuation Engine", "scaffold"),
        ("cli_btr.hbu", "Highest & Best Use", "scaffold"),
        ("cli_btr.cost", "Cost Estimator", "scaffold"),
        ("cli_btr.lv", "Lender Vetting", "scaffold"),
        ("cli_btr.proforma", "Pro Forma Generator", "scaffold"),
    ]
    result = {
        "agent": "EVEREST-BTR Squad",
        "timestamp": _timestamp(),
        "total_agents": len(agents),
        "property_types": list(PROPERTY_TYPES),
        "scenarios": ["land", "construction", "permanent", "rehab"],
        "agents": [{"id": a[0], "name": a[1], "status": a[2]} for a in agents],
    }
    _output(result, ctx.obj["json"])


if __name__ == "__main__":
    cli()

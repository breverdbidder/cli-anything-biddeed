#!/usr/bin/env python3
"""
cli_anything.projecttracker — Project Status Tracker for Brevard County, FL.

Forked from NextAutomation Project Tracker v1.0.
Adapted for BidDeed.AI (acquisition-to-exit tracking) and ZoneWise.AI (portfolio dashboard).

NOT for 42-unit multifamily construction. This generates weekly/monthly status reports
for $25K-$250K residential rehab projects typical of Brevard foreclosure/tax deed acquisitions.

6-stage pipeline:
  1. BUDGET    — Budget vs actual compilation from forecaster + Supabase spend logs
  2. MILESTONE — Phase completion tracking from sitemanager + manual updates
  3. SUBRATING — Subcontractor performance scoring (schedule, budget, quality, safety)
  4. CHANGES   — Change order & RFI tracking with trend analysis
  5. CASHFLOW  — Draw status, equity invested, net position for lender compliance
  6. REPORT    — Audience-formatted report assembly (internal, lp, lender, executive)

Usage:
  python -m projecttracker.agent report --project PRJ-001 --audience lp --json
  python -m projecttracker.agent report --project PRJ-001 --audience lender --format docx
  python -m projecttracker.agent rate-sub --project PRJ-001 --sub "ABC Electric" --json
  python -m projecttracker.agent add-co --project PRJ-001 --amount 28000 --reason "Panel upgrade" --status approved
  python -m projecttracker.agent draw --project PRJ-001 --amount 85000 --status submitted
  python -m projecttracker.agent portfolio --json
  python -m projecttracker.agent status
"""
import httpx, json, os, sys, time, argparse, re, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
BCPAO_API = "https://www.bcpao.us/api/v1"
UA = {"User-Agent": "BidDeed.AI/1.0 (project-tracker)"}

THRESHOLDS = {
    "budget_variance": {"healthy": 0.03, "warning": 0.08},
    "committed_ratio": {"healthy": 0.95, "warning": 1.00},
    "contingency_pct": {"healthy": 0.60, "warning": 0.30},
    "cost_perf_index": {"healthy": 0.95, "warning": 0.85},
    "co_rate": {"healthy": 0.03, "warning": 0.07},
}

SUB_WEIGHTS = {"schedule": 0.25, "budget": 0.20, "quality": 0.20, "safety": 0.15, "comms": 0.10, "staffing": 0.10}

REHAB_PHASES = [
    "demo", "structural", "roof", "windows_doors", "plumbing", "electrical",
    "hvac", "insulation", "drywall", "interior_paint", "flooring", "kitchen",
    "bathrooms", "fixtures_appliances", "landscaping_exterior", "final_clean"
]

def sub_tier(score):
    if score >= 90: return "A", "Excellent"
    if score >= 75: return "B", "Good"
    if score >= 60: return "C", "Acceptable"
    if score >= 40: return "D", "Below Standard"
    return "F", "Unacceptable"

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

def sb_get(table, params=""):
    if not SUPABASE_URL: return []
    try:
        r = httpx.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=sb_headers(), timeout=15)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"[WARN] Supabase GET {table}: {e}", file=sys.stderr)
        return []

def sb_upsert(table, data, conflict="id"):
    if not SUPABASE_URL: return False
    try:
        h = {**sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"}
        r = httpx.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=h, timeout=15)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[WARN] Supabase upsert {table}: {e}", file=sys.stderr)
        return False

def sb_insert(table, data):
    if not SUPABASE_URL: return False
    try:
        h = {**sb_headers(), "Prefer": "return=minimal"}
        r = httpx.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=h, timeout=15)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[WARN] Supabase insert {table}: {e}", file=sys.stderr)
        return False

def telegram(msg):
    if not TELEGRAM_BOT or not TELEGRAM_CHAT: return
    try:
        httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                   data={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

# ═══ STAGE 1: BUDGET VS ACTUAL ═══

def stage_budget(project_id, budget, template="medium_rehab"):
    print(f"[1/6] BUDGET — {project_id} | baseline ${budget:,.0f}", file=sys.stderr)
    spend_rows = sb_get("rehab_spend_log", f"project_id=eq.{project_id}&order=logged_at.desc")
    actual_total = sum(float(r.get("amount", 0)) for r in spend_rows)
    period_spend = sum(float(r.get("amount", 0)) for r in spend_rows
                       if r.get("logged_at", "") >= (datetime.now(timezone.utc) - timedelta(days=7)).isoformat())
    forecaster = sb_get("rehab_projects", f"project_id=eq.{project_id}")
    committed = float(forecaster[0].get("total_committed", actual_total)) if forecaster else actual_total
    contingency_orig = budget * 0.10
    contingency_used = max(0, actual_total - (budget - contingency_orig))
    contingency_remaining = max(0, contingency_orig - contingency_used)
    cos = sb_get("project_change_orders", f"project_id=eq.{project_id}&status=eq.approved")
    co_total = sum(float(c.get("amount", 0)) for c in cos)
    site_report = sb_get("rehab_site_reports", f"project_id=eq.{project_id}")
    overall_pct = float(site_report[0].get("overall_pct", 0)) / 100 if site_report else 0
    earned_value = budget * overall_pct
    cpi = round(earned_value / actual_total, 2) if actual_total > 0 else 1.0
    variance_pct = (actual_total - budget * overall_pct) / budget if budget > 0 else 0
    forecast_at_completion = actual_total + (budget - earned_value) / cpi if cpi > 0 else budget * 1.2

    def classify(val, thresholds, invert=False):
        h, w = thresholds["healthy"], thresholds["warning"]
        if invert: return "HEALTHY" if val >= h else "WARNING" if val >= w else "CRITICAL"
        return "HEALTHY" if val <= h else "WARNING" if val <= w else "CRITICAL"

    indicators = {
        "budget_variance": {"value": abs(variance_pct), "status": classify(abs(variance_pct), THRESHOLDS["budget_variance"])},
        "committed_ratio": {"value": committed / budget if budget > 0 else 0, "status": classify(committed / budget if budget > 0 else 0, THRESHOLDS["committed_ratio"])},
        "contingency_pct": {"value": contingency_remaining / contingency_orig if contingency_orig > 0 else 0, "status": classify(contingency_remaining / contingency_orig if contingency_orig > 0 else 0, THRESHOLDS["contingency_pct"], invert=True)},
        "cost_perf_index": {"value": cpi, "status": classify(cpi, THRESHOLDS["cost_perf_index"], invert=True)},
        "co_rate": {"value": co_total / budget if budget > 0 else 0, "status": classify(co_total / budget if budget > 0 else 0, THRESHOLDS["co_rate"])},
    }
    critical_count = sum(1 for i in indicators.values() if i["status"] == "CRITICAL")
    warning_count = sum(1 for i in indicators.values() if i["status"] == "WARNING")
    budget_health = "CRITICAL" if critical_count > 0 else "WARNING" if warning_count > 1 else "HEALTHY"

    return {
        "budget": budget, "actual": round(actual_total, 2), "committed": round(committed, 2),
        "period_spend": round(period_spend, 2), "co_total": round(co_total, 2),
        "contingency_original": round(contingency_orig, 2), "contingency_remaining": round(contingency_remaining, 2),
        "contingency_pct": round((contingency_remaining / contingency_orig * 100) if contingency_orig > 0 else 0, 1),
        "earned_value": round(earned_value, 2), "cpi": cpi, "variance_pct": round(variance_pct * 100, 2),
        "forecast_at_completion": round(forecast_at_completion, 2), "indicators": indicators, "budget_health": budget_health,
        "spend_entries": len(spend_rows),
    }

# ═══ STAGE 2: MILESTONE TRACKING ═══

def stage_milestones(project_id):
    print(f"[2/6] MILESTONES — {project_id}", file=sys.stderr)
    site_report = sb_get("rehab_site_reports", f"project_id=eq.{project_id}")
    if not site_report:
        return {"milestones": [], "overall_pct": 0, "schedule_status": "NO_DATA", "schedule_health": 50, "phases_behind": 0, "phases_complete": 0, "phases_total": len(REHAB_PHASES)}
    rpt = site_report[0]
    report_json = rpt.get("report_json", {})
    if isinstance(report_json, str):
        try: report_json = json.loads(report_json)
        except: report_json = {}
    phases = report_json.get("phases", {})
    milestones, phases_behind, total_pct = [], 0, 0
    for phase_name in REHAB_PHASES:
        p = phases.get(phase_name, {})
        pct = p.get("pct_complete", 0)
        status = p.get("status", "NOT_STARTED")
        total_pct += pct
        if status in ("BEHIND", "CRITICAL"): phases_behind += 1
        milestones.append({"phase": phase_name, "pct_complete": pct, "status": status,
                           "planned_days": p.get("planned_days", 0), "actual_days": p.get("actual_days", 0),
                           "variance_days": p.get("actual_days", 0) - p.get("planned_days", 0)})
    overall_pct = round(total_pct / len(REHAB_PHASES), 1) if REHAB_PHASES else 0
    schedule_health = int(rpt.get("schedule_health", 50))
    schedule_status = "ON_TRACK" if schedule_health >= 80 else "MINOR_DELAYS" if schedule_health >= 60 else "SIGNIFICANT_DELAYS" if schedule_health >= 40 else "CRITICAL"
    return {"milestones": milestones, "overall_pct": overall_pct, "schedule_health": schedule_health,
            "schedule_status": schedule_status, "phases_behind": phases_behind,
            "phases_complete": sum(1 for m in milestones if m["pct_complete"] >= 100), "phases_total": len(REHAB_PHASES)}

# ═══ STAGE 3: SUBCONTRACTOR RATING ═══

def stage_subrating(project_id):
    print(f"[3/6] SUBRATING — {project_id}", file=sys.stderr)
    subs = sb_get("project_subcontractors", f"project_id=eq.{project_id}")
    if not subs:
        return {"subcontractors": [], "avg_score": 0, "worst_performer": None, "best_performer": None, "d_or_f_count": 0}
    scored = []
    for sub in subs:
        scores = {k: min(100, max(0, int(sub.get(f"{k}_score", 75)))) for k in SUB_WEIGHTS}
        weighted = sum(scores[k] * SUB_WEIGHTS[k] for k in scores)
        overall = round(weighted, 1)
        tier_code, tier_label = sub_tier(overall)
        scored.append({"name": sub.get("name", "Unknown"), "trade": sub.get("trade", "General"),
                        "contract_value": float(sub.get("contract_value", 0)), "spent": float(sub.get("spent", 0)),
                        "co_count": int(sub.get("co_count", 0)), "co_value": float(sub.get("co_value", 0)),
                        "scores": scores, "overall_score": overall, "tier": tier_code, "tier_label": tier_label})
    scored.sort(key=lambda x: x["overall_score"], reverse=True)
    avg = round(sum(s["overall_score"] for s in scored) / len(scored), 1) if scored else 0
    return {"subcontractors": scored, "avg_score": avg,
            "best_performer": scored[0]["name"] if scored else None,
            "worst_performer": scored[-1]["name"] if scored else None,
            "d_or_f_count": sum(1 for s in scored if s["tier"] in ("D", "F"))}

# ═══ STAGE 4: CHANGE ORDERS ═══

def stage_changes(project_id):
    print(f"[4/6] CHANGES — {project_id}", file=sys.stderr)
    cos = sb_get("project_change_orders", f"project_id=eq.{project_id}&order=created_at.desc")
    approved = [c for c in cos if c.get("status") == "approved"]
    pending = [c for c in cos if c.get("status") == "pending"]
    approved_total = sum(float(c.get("amount", 0)) for c in approved)
    pending_total = sum(float(c.get("amount", 0)) for c in pending)
    overdue = 0
    for co in pending:
        try:
            days = (datetime.now(timezone.utc) - datetime.fromisoformat(co.get("created_at", "").replace("Z", "+00:00"))).days
            if days > 14: overdue += 1
        except: pass
    this_period = [c for c in cos if c.get("created_at", "") >= (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()]
    return {"total_count": len(cos), "approved_count": len(approved), "approved_total": round(approved_total, 2),
            "pending_count": len(pending), "pending_total": round(pending_total, 2),
            "rejected_count": sum(1 for c in cos if c.get("status") == "rejected"),
            "this_period_count": len(this_period), "overdue_count": overdue,
            "change_orders": [{"co_number": c.get("co_number", i+1), "amount": float(c.get("amount", 0)),
                               "reason": c.get("reason", ""), "status": c.get("status", ""),
                               "trade": c.get("trade", "")} for i, c in enumerate(cos[:10])]}

# ═══ STAGE 5: CASH FLOW ═══

def stage_cashflow(project_id, budget):
    print(f"[5/6] CASHFLOW — {project_id}", file=sys.stderr)
    draws = sb_get("project_draws", f"project_id=eq.{project_id}&order=draw_number.asc")
    total_drawn = sum(float(d.get("amount", 0)) for d in draws if d.get("status") == "funded")
    pending_amount = sum(float(d.get("amount", 0)) for d in draws if d.get("status") in ("submitted", "under_review"))
    equity_calls = sb_get("project_equity_calls", f"project_id=eq.{project_id}")
    total_equity = sum(float(e.get("amount", 0)) for e in equity_calls if e.get("status") == "received")
    loan_balance = budget * 0.75
    remaining_loan = max(0, loan_balance - total_drawn)
    sources_total = total_drawn + total_equity
    spend_rows = sb_get("rehab_spend_log", f"project_id=eq.{project_id}")
    uses_total = sum(float(r.get("amount", 0)) for r in spend_rows)
    return {"total_drawn": round(total_drawn, 2), "pending_draws": round(pending_amount, 2),
            "remaining_loan": round(remaining_loan, 2), "total_equity": round(total_equity, 2),
            "sources_total": round(sources_total, 2), "uses_total": round(uses_total, 2),
            "net_position": round(sources_total - uses_total, 2),
            "draws": [{"draw_number": d.get("draw_number", i+1), "amount": float(d.get("amount", 0)),
                        "status": d.get("status", ""), "submitted_date": d.get("submitted_date", ""),
                        "funded_date": d.get("funded_date", ""), "issues": d.get("issues", "None")}
                       for i, d in enumerate(draws)],
            "draw_count": len(draws), "funded_count": sum(1 for d in draws if d.get("status") == "funded")}

# ═══ STAGE 6: REPORT ASSEMBLY ═══

def stage_report(project_id, budget_data, milestone_data, sub_data, change_data, cashflow_data,
                 audience="internal", save=False):
    print(f"[6/6] REPORT — {project_id} | audience={audience}", file=sys.stderr)
    now = datetime.now(timezone.utc)
    budget_score = 100 if budget_data["budget_health"] == "HEALTHY" else 70 if budget_data["budget_health"] == "WARNING" else 40
    schedule_score = milestone_data.get("schedule_health", 50)
    sub_score_val = sub_data.get("avg_score", 75)
    co_penalty = min(30, change_data.get("overdue_count", 0) * 10)
    project_health = max(0, min(100, round(budget_score * 0.35 + schedule_score * 0.35 + sub_score_val * 0.20 + (100 - co_penalty) * 0.10)))
    health_label = "ON_TRACK" if project_health >= 80 else "NEEDS_ATTENTION" if project_health >= 60 else "AT_RISK" if project_health >= 40 else "CRITICAL"

    actions = []
    if budget_data["budget_health"] == "CRITICAL":
        actions.append({"priority": "HIGH", "action": f"Budget variance at {budget_data['variance_pct']}% — review with GC", "owner": "PM"})
    if budget_data["contingency_pct"] < 30:
        actions.append({"priority": "HIGH", "action": f"Contingency at {budget_data['contingency_pct']}% — restrict COs", "owner": "PM"})
    if milestone_data["phases_behind"] > 2:
        actions.append({"priority": "HIGH", "action": f"{milestone_data['phases_behind']} phases behind — recovery plan needed", "owner": "GC"})
    if sub_data.get("d_or_f_count", 0) > 0:
        actions.append({"priority": "HIGH", "action": f"{sub_data['d_or_f_count']} sub(s) below standard — notice to cure", "owner": "PM"})
    if change_data.get("overdue_count", 0) > 0:
        actions.append({"priority": "MEDIUM", "action": f"{change_data['overdue_count']} CO(s) pending >14 days", "owner": "PM"})
    if not actions:
        actions.append({"priority": "LOW", "action": "No critical issues — continue monitoring", "owner": "PM"})

    risks = []
    if budget_data["cpi"] < 0.90:
        risks.append({"severity": "HIGH", "risk": "Cost overrun trajectory", "probability": "Likely", "mitigation": "Value engineering remaining scope"})
    if milestone_data["schedule_status"] in ("SIGNIFICANT_DELAYS", "CRITICAL"):
        risks.append({"severity": "HIGH", "risk": "Schedule slip impacting hold costs", "probability": "Likely", "mitigation": "Acceleration or scope reduction"})
    if cashflow_data.get("pending_draws", 0) > 0:
        risks.append({"severity": "MEDIUM", "risk": "Draw funding delay", "probability": "Possible", "mitigation": "Bridge with equity or credit line"})

    report = {
        "project_id": project_id, "generated_at": now.isoformat(),
        "reporting_period": f"{(now - timedelta(days=7)).strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
        "audience": audience, "project_health_score": project_health, "health_label": health_label,
        "budget": budget_data, "milestones": milestone_data, "subcontractors": sub_data,
        "change_orders": change_data, "cashflow": cashflow_data,
        "action_items": actions, "risks": risks, "action_count": len(actions), "risk_count": len(risks),
    }

    if save:
        flat = {"project_id": project_id, "report_date": now.strftime("%Y-%m-%d"), "audience": audience,
                "project_health_score": project_health, "health_label": health_label,
                "budget_health": budget_data["budget_health"], "schedule_status": milestone_data["schedule_status"],
                "overall_pct": milestone_data["overall_pct"], "cpi": budget_data["cpi"],
                "contingency_pct": budget_data["contingency_pct"], "co_count": change_data["total_count"],
                "co_approved_total": change_data["approved_total"], "sub_avg_score": sub_data["avg_score"],
                "action_count": len(actions), "risk_count": len(risks), "report_json": json.dumps(report)}
        ok = sb_upsert("project_status_reports", [flat], conflict="project_id,report_date")
        print(f"  -> Supabase: {'saved' if ok else 'FAILED'}", file=sys.stderr)

    if project_health < 60 and TELEGRAM_BOT:
        top_action = actions[0]["action"] if actions else "Review required"
        telegram(f"<b>Project {project_id}</b>\nHealth: {project_health}/100 ({health_label})\n{top_action}")

    print(f"  -> Health: {project_health}/100 ({health_label}) | Actions: {len(actions)} | Risks: {len(risks)}", file=sys.stderr)
    return report

# ═══ COMMANDS ═══

def cmd_report(args):
    project_id = args.project
    budget = float(args.budget or 0)
    if budget == 0:
        proj = sb_get("rehab_projects", f"project_id=eq.{project_id}")
        budget = float(proj[0].get("total_budget", 85000)) if proj else 85000
    bd = stage_budget(project_id, budget)
    ml = stage_milestones(project_id)
    sr = stage_subrating(project_id)
    co = stage_changes(project_id)
    cf = stage_cashflow(project_id, budget)
    report = stage_report(project_id, bd, ml, sr, co, cf, audience=args.audience, save=args.save)
    if args.json: print(json.dumps(report, indent=2, default=str))
    else:
        print(f"\nPROJECT STATUS REPORT — {report['audience'].upper()}\n{'='*50}")
        print(f"{report['project_id']} | {report['reporting_period']}")
        print(f"\nHEALTH: {report['project_health_score']}/100 ({report['health_label']})")
        print(f"BUDGET: ${bd['actual']:,.0f} / ${bd['budget']:,.0f} ({bd['variance_pct']:+.1f}%) | CPI: {bd['cpi']}")
        print(f"SCHEDULE: {ml['overall_pct']}% complete ({ml['schedule_status']}) | Behind: {ml['phases_behind']} phases")
        print(f"SUBS: Avg {sr['avg_score']}/100 | COs: {co['total_count']} (${co['approved_total']:,.0f})")
        for a in report['action_items']: print(f"  [{a['priority']}] {a['action']}")

def cmd_rate_sub(args):
    sub_data = stage_subrating(args.project)
    match = [s for s in sub_data["subcontractors"] if args.sub.lower() in s["name"].lower()]
    if match:
        if args.json: print(json.dumps(match[0], indent=2))
        else: s = match[0]; print(f"{s['name']} ({s['trade']}): {s['overall_score']}/100 ({s['tier']})")
    else: print(json.dumps({"error": f"Sub '{args.sub}' not found"}))

def cmd_add_co(args):
    cos = sb_get("project_change_orders", f"project_id=eq.{args.project}&order=co_number.desc&limit=1")
    next_num = (int(cos[0].get("co_number", 0)) + 1) if cos else 1
    co = {"project_id": args.project, "co_number": next_num, "amount": float(args.amount),
          "reason": args.reason, "status": args.status or "pending", "trade": args.trade or "",
          "created_at": datetime.now(timezone.utc).isoformat()}
    ok = sb_insert("project_change_orders", co)
    print(json.dumps({"co_number": next_num, "saved": ok, **co}, indent=2, default=str))

def cmd_draw(args):
    draws = sb_get("project_draws", f"project_id=eq.{args.project}&order=draw_number.desc&limit=1")
    next_num = (int(draws[0].get("draw_number", 0)) + 1) if draws else 1
    draw = {"project_id": args.project, "draw_number": next_num, "amount": float(args.amount),
            "status": args.status or "submitted", "submitted_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    ok = sb_insert("project_draws", draw)
    print(json.dumps({"draw_number": next_num, "saved": ok, **draw}, indent=2, default=str))

def cmd_portfolio(args):
    projects = sb_get("project_status_reports", "order=report_date.desc")
    seen = {}
    for p in projects:
        pid = p.get("project_id")
        if pid not in seen: seen[pid] = p
    portfolio = [{"project_id": pid, "health": int(p.get("project_health_score", 0)),
                  "label": p.get("health_label", "UNKNOWN"), "overall_pct": float(p.get("overall_pct", 0)),
                  "budget_health": p.get("budget_health", "UNKNOWN"), "cpi": float(p.get("cpi", 0)),
                  "report_date": p.get("report_date", "")} for pid, p in seen.items()]
    portfolio.sort(key=lambda x: x["health"])
    result = {"project_count": len(portfolio),
              "critical_count": sum(1 for p in portfolio if p["label"] == "CRITICAL"),
              "at_risk_count": sum(1 for p in portfolio if p["label"] == "AT_RISK"),
              "avg_health": round(sum(p["health"] for p in portfolio) / len(portfolio), 1) if portfolio else 0,
              "projects": portfolio}
    if args.json: print(json.dumps(result, indent=2))
    else:
        print(f"Portfolio: {result['project_count']} projects | Avg Health: {result['avg_health']}/100")
        for p in portfolio:
            icon = "G" if p["health"] >= 80 else "Y" if p["health"] >= 60 else "R"
            print(f"  [{icon}] {p['project_id']}: {p['health']}/100 ({p['label']}) — {p['overall_pct']}%")

def cmd_status(args):
    sb_ok = bool(sb_get("project_status_reports", "limit=1") is not None)
    print(f"Supabase: {'connected' if sb_ok else 'disconnected'}", file=sys.stderr)
    print(f"Telegram: {'configured' if TELEGRAM_BOT else 'not configured'}", file=sys.stderr)
    reports = sb_get("project_status_reports", "select=project_id&order=report_date.desc&limit=5")
    print(f"Recent reports: {len(reports)}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Project Status Tracker — Brevard County Rehab")
    sub = parser.add_subparsers(dest="command")
    p_r = sub.add_parser("report"); p_r.add_argument("--project", required=True); p_r.add_argument("--budget", type=float)
    p_r.add_argument("--audience", default="internal", choices=["internal", "lp", "lender", "executive"])
    p_r.add_argument("--json", action="store_true"); p_r.add_argument("--save", action="store_true")
    p_s = sub.add_parser("rate-sub"); p_s.add_argument("--project", required=True); p_s.add_argument("--sub", required=True)
    p_s.add_argument("--json", action="store_true")
    p_c = sub.add_parser("add-co"); p_c.add_argument("--project", required=True); p_c.add_argument("--amount", required=True, type=float)
    p_c.add_argument("--reason", required=True); p_c.add_argument("--status", default="pending"); p_c.add_argument("--trade", default="")
    p_d = sub.add_parser("draw"); p_d.add_argument("--project", required=True); p_d.add_argument("--amount", required=True, type=float)
    p_d.add_argument("--status", default="submitted")
    p_p = sub.add_parser("portfolio"); p_p.add_argument("--json", action="store_true")
    sub.add_parser("status")
    args = parser.parse_args()
    cmds = {"report": cmd_report, "rate-sub": cmd_rate_sub, "add-co": cmd_add_co,
            "draw": cmd_draw, "portfolio": cmd_portfolio, "status": cmd_status}
    if args.command in cmds: cmds[args.command](args)
    else: parser.print_help(); sys.exit(1)

if __name__ == "__main__":
    main()

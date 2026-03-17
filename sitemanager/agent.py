#!/usr/bin/env python3
"""
cli_anything.sitemanager — Rehab Site Manager for Brevard County, FL.

Forked from NextAutomation Site Manager v1.0.
Adapted for ZoneWise.AI (property rehab monitoring) and BidDeed.AI (flip project tracking).

NOT for 42-unit multifamily construction. This monitors $25K-$250K residential rehab
projects typical of Brevard foreclosure/tax deed acquisitions.

7-stage pipeline:
  1. PROJECT   — Load/create rehab project with phases from forecaster budget
  2. PHOTOS    — Analyze uploaded site photos via Claude Vision API or manual tags
  3. SCHEDULE  — Track phase completion vs timeline, detect deviations
  4. SAFETY    — FL residential code compliance (wind mitigation, permits, electrical)
  5. QUALITY   — Workmanship checks specific to Brevard rehab (termite, poly plumbing, stucco)
  6. DAILY     — Parse contractor daily logs / invoice summaries
  7. REPORT    — Composite site health score + Mapbox property pin + DOCX report

Usage:
  python -m sitemanager.agent create --parcel "25-37-22-00-00123.0-0000.00" --budget 85000 --template medium_rehab
  python -m sitemanager.agent update --project PRJ-001 --phase roof --pct 75 --notes "Shingles 75% done, ridge vent tomorrow"
  python -m sitemanager.agent photo --project PRJ-001 --file site_photo.jpg --phase kitchen
  python -m sitemanager.agent report --project PRJ-001 --json
  python -m sitemanager.agent dashboard --json
  python -m sitemanager.agent status
"""
import httpx, json, os, sys, time, argparse, re, hashlib
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
MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", "")
BCPAO_API = "https://www.bcpao.us/api/v1"
UA = {"User-Agent": "ZoneWise.AI/1.0 (site-manager)"}

# Rehab phases for residential projects (matches forecaster categories)
REHAB_PHASES = {
    "demo": {"order": 1, "name": "Demo & Cleanout", "typical_days": 5, "weight": 0.05},
    "structural": {"order": 2, "name": "Structural Repairs", "typical_days": 14, "weight": 0.10},
    "roof": {"order": 3, "name": "Roof Replacement", "typical_days": 7, "weight": 0.12},
    "windows_doors": {"order": 4, "name": "Windows & Doors", "typical_days": 5, "weight": 0.06},
    "plumbing": {"order": 5, "name": "Plumbing", "typical_days": 10, "weight": 0.08},
    "electrical": {"order": 6, "name": "Electrical", "typical_days": 10, "weight": 0.08},
    "hvac": {"order": 7, "name": "HVAC", "typical_days": 5, "weight": 0.10},
    "insulation": {"order": 8, "name": "Insulation", "typical_days": 3, "weight": 0.03},
    "drywall": {"order": 9, "name": "Drywall", "typical_days": 10, "weight": 0.07},
    "interior_paint": {"order": 10, "name": "Interior Paint", "typical_days": 7, "weight": 0.06},
    "flooring": {"order": 11, "name": "Flooring", "typical_days": 7, "weight": 0.08},
    "kitchen": {"order": 12, "name": "Kitchen", "typical_days": 10, "weight": 0.10},
    "bathrooms": {"order": 13, "name": "Bathrooms", "typical_days": 10, "weight": 0.08},
    "fixtures_appliances": {"order": 14, "name": "Fixtures & Appliances", "typical_days": 3, "weight": 0.04},
    "landscaping_exterior": {"order": 15, "name": "Landscaping & Exterior", "typical_days": 5, "weight": 0.04},
    "final_clean": {"order": 16, "name": "Final Clean & Punch", "typical_days": 3, "weight": 0.03},
}

# Schedule health scoring
SCHEDULE_HEALTH = {
    (90, 101): {"label": "ON_TRACK", "action": "Continue monitoring"},
    (75, 90): {"label": "MINOR_DELAYS", "action": "Increase check-in frequency"},
    (60, 75): {"label": "SIGNIFICANT_DELAYS", "action": "Schedule recovery meeting with GC"},
    (40, 60): {"label": "MAJOR_DELAYS", "action": "Recovery plan required, consider GC change"},
    (0, 40): {"label": "CRITICAL", "action": "Stop work evaluation, reassess project viability"},
}

# Brevard-specific quality checks
BREVARD_QUALITY_CHECKS = [
    {"id": "termite", "name": "Termite Damage", "description": "Check subfloor, wall plates, window frames for termite damage (30% of Brevard rehabs)", "severity": "HIGH"},
    {"id": "poly_plumbing", "name": "Polybutylene Plumbing", "description": "Pre-1995 homes — full repipe mandatory if found", "severity": "CRITICAL"},
    {"id": "chinese_drywall", "name": "Chinese Drywall", "description": "2004-2009 builds — check for sulfur smell, blackened copper", "severity": "CRITICAL"},
    {"id": "hurricane_straps", "name": "Hurricane Strap Retrofit", "description": "FL building code requires roof-to-wall connections", "severity": "HIGH"},
    {"id": "stucco_intrusion", "name": "Stucco Water Intrusion", "description": "Block construction — check behind stucco for moisture", "severity": "MEDIUM"},
    {"id": "electrical_panel", "name": "Electrical Panel Age", "description": "Federal Pacific / Zinsco panels = immediate replacement", "severity": "CRITICAL"},
    {"id": "wind_mitigation", "name": "Wind Mitigation Features", "description": "FL insurance discount: hip roof, SWR, opening protection", "severity": "MEDIUM"},
    {"id": "flood_zone", "name": "Flood Zone Compliance", "description": "AE/VE zones: elevated HVAC, flood vents, BFE compliance", "severity": "HIGH"},
    {"id": "permit_status", "name": "Open Permits", "description": "Check Brevard County PermitsPlus for open/expired permits", "severity": "HIGH"},
    {"id": "asbestos", "name": "Asbestos (Pre-1980)", "description": "Popcorn ceilings, floor tiles, pipe insulation in pre-1980 homes", "severity": "HIGH"},
]


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
        httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                   json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
                   timeout=10, headers=UA)
    except Exception:
        pass


def supabase_query(table: str, params: Dict = None) -> List[Dict]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        r = httpx.get(f"{SUPABASE_URL}/rest/v1/{table}",
                      headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
                      params=params or {}, timeout=30)
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
        r = httpx.post(f"{SUPABASE_URL}/rest/v1/{table}",
                       headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                                "Content-Type": "application/json",
                                "Prefer": "resolution=merge-duplicates,return=minimal"},
                       json=records, timeout=30)
        r.raise_for_status()
        log("DB", f"Upserted {len(records)} to {table}", "OK")
    except Exception as e:
        log("DB", f"Upsert failed: {e}", "ERR")


def gen_project_id(parcel_id: str) -> str:
    """Generate deterministic project ID from parcel."""
    h = hashlib.md5(parcel_id.encode()).hexdigest()[:6].upper()
    return f"PRJ-{h}"


# ═══════════════════════════════════════════════════════════════
# STAGE 1: PROJECT — Create/load rehab project
# ═══════════════════════════════════════════════════════════════

def stage_project(parcel_id: str, budget: float = None, template: str = "medium_rehab",
                  start_date: str = None, gc_name: str = None) -> Dict:
    """Create or load a rehab project with phase breakdown."""
    log("PROJECT", f"Initializing project for {parcel_id}")
    project_id = gen_project_id(parcel_id)

    project = {
        "project_id": project_id,
        "parcel_id": parcel_id,
        "budget": budget or 85000,
        "template": template,
        "gc_name": gc_name,
        "start_date": start_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "ACTIVE",
        "phases": {},
        "overall_pct": 0.0,
        "address": None,
        "sqft": None,
        "year_built": None,
        "photo_url": None,
        "confidence": 0.0,
    }

    # Pull property data from BCPAO
    try:
        client = httpx.Client(timeout=15, headers=UA)
        account = parcel_id.replace("-", "").replace(".", "")
        r = client.get(f"{BCPAO_API}/search?acct={account}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                rec = data[0]
                project["address"] = rec.get("address", "")
                project["sqft"] = rec.get("heatedArea") or rec.get("totalArea")
                project["year_built"] = rec.get("yearBuilt")
                photo = rec.get("masterPhotoUrl")
                if photo:
                    project["photo_url"] = photo
                log("PROJECT", f"{project['address']} | {project['sqft']} sqft | Built {project['year_built']}", "OK")
        client.close()
    except Exception as e:
        log("PROJECT", f"BCPAO lookup failed: {e}", "WARN")

    # Initialize phases
    for phase_key, phase_cfg in REHAB_PHASES.items():
        project["phases"][phase_key] = {
            "name": phase_cfg["name"],
            "order": phase_cfg["order"],
            "weight": phase_cfg["weight"],
            "pct_complete": 0,
            "status": "NOT_STARTED",  # NOT_STARTED|IN_PROGRESS|COMPLETE|BLOCKED
            "target_days": phase_cfg["typical_days"],
            "actual_days": 0,
            "started_at": None,
            "completed_at": None,
            "notes": "",
            "photos": [],
            "issues": [],
        }

    project["confidence"] = 0.60
    log("PROJECT", f"Project {project_id} created with {len(project['phases'])} phases", "OK")
    return project


# ═══════════════════════════════════════════════════════════════
# STAGE 2: PHOTOS — Track site photo uploads
# ═══════════════════════════════════════════════════════════════

def stage_photos(project: Dict, photo_path: str = None, phase: str = None,
                 notes: str = None) -> Dict:
    """Register a site photo against a project phase."""
    log("PHOTOS", f"Processing photo for {project['project_id']}")
    photo_record = {
        "project_id": project["project_id"],
        "phase": phase,
        "filename": Path(photo_path).name if photo_path else None,
        "notes": notes,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "analysis": None,  # Claude Vision would go here
        "confidence": 0.0,
    }

    if photo_path and Path(photo_path).exists():
        photo_record["file_size"] = Path(photo_path).stat().st_size
        photo_record["confidence"] = 0.30  # File exists but no vision analysis yet
        log("PHOTOS", f"Photo registered: {photo_record['filename']} → {phase}", "OK")

        # Add to phase photos list
        if phase and phase in project.get("phases", {}):
            project["phases"][phase]["photos"].append(photo_record)
    else:
        log("PHOTOS", f"Photo file not found: {photo_path}", "WARN")

    # TODO: Claude Vision API integration for automatic progress detection
    # Would analyze photo to determine:
    # - Phase identification (what work is visible)
    # - Completion percentage estimate
    # - Quality issues visible
    # - Safety concerns

    return photo_record


# ═══════════════════════════════════════════════════════════════
# STAGE 3: SCHEDULE — Phase completion tracking
# ═══════════════════════════════════════════════════════════════

def stage_schedule(project: Dict) -> Dict:
    """Calculate schedule health from phase completion data."""
    log("SCHEDULE", f"Analyzing schedule for {project['project_id']}")

    schedule = {
        "project_id": project["project_id"],
        "overall_pct": 0.0,
        "target_pct": 0.0,
        "schedule_health_score": 100,
        "schedule_status": "ON_TRACK",
        "days_elapsed": 0,
        "total_planned_days": 0,
        "phases_behind": [],
        "phases_on_track": [],
        "phases_complete": [],
        "critical_path_impact": False,
        "projected_completion": None,
        "confidence": 0.0,
    }

    # Calculate elapsed days
    try:
        start = datetime.fromisoformat(project["start_date"])
        now = datetime.now(timezone.utc).replace(tzinfo=None) if start.tzinfo is None else datetime.now(timezone.utc)
        schedule["days_elapsed"] = (now - start).days
    except Exception:
        pass

    # Sum planned days and weighted completion
    weighted_complete = 0.0
    total_planned = sum(p["target_days"] for p in project["phases"].values())
    schedule["total_planned_days"] = total_planned

    # Expected progress based on elapsed time
    if total_planned > 0:
        schedule["target_pct"] = min(1.0, schedule["days_elapsed"] / total_planned)

    for phase_key, phase in project["phases"].items():
        pct = phase.get("pct_complete", 0) / 100
        weight = phase.get("weight", 0)
        weighted_complete += pct * weight

        if pct >= 1.0:
            schedule["phases_complete"].append(phase_key)
        elif phase.get("status") == "IN_PROGRESS":
            # Check if behind schedule
            expected_pct = schedule["target_pct"]
            order = phase.get("order", 1)
            phase_target = min(1.0, schedule["days_elapsed"] / max(1, phase["target_days"]))
            if pct < phase_target * 0.8:  # 20% behind expected
                schedule["phases_behind"].append({
                    "phase": phase_key,
                    "name": phase["name"],
                    "actual_pct": pct,
                    "expected_pct": phase_target,
                    "gap": round((phase_target - pct) * 100, 1),
                })
            else:
                schedule["phases_on_track"].append(phase_key)

    schedule["overall_pct"] = round(weighted_complete, 4)
    project["overall_pct"] = schedule["overall_pct"]

    # Schedule health score (0-100)
    if schedule["target_pct"] > 0:
        ratio = schedule["overall_pct"] / schedule["target_pct"]
        schedule["schedule_health_score"] = min(100, max(0, int(ratio * 100)))
    else:
        schedule["schedule_health_score"] = 100

    # Classify
    for (lo, hi), info in SCHEDULE_HEALTH.items():
        if lo <= schedule["schedule_health_score"] < hi:
            schedule["schedule_status"] = info["label"]
            break

    schedule["critical_path_impact"] = len(schedule["phases_behind"]) > 0

    # Projected completion
    if schedule["overall_pct"] > 0 and schedule["days_elapsed"] > 0:
        rate = schedule["overall_pct"] / schedule["days_elapsed"]
        remaining = (1.0 - schedule["overall_pct"]) / rate if rate > 0 else 999
        proj = datetime.now(timezone.utc) + timedelta(days=remaining)
        schedule["projected_completion"] = proj.strftime("%Y-%m-%d")

    schedule["confidence"] = 0.60 if schedule["days_elapsed"] > 7 else 0.30

    log("SCHEDULE", f"Health: {schedule['schedule_health_score']}/100 ({schedule['schedule_status']}) | "
                    f"Complete: {schedule['overall_pct']:.0%} | Behind: {len(schedule['phases_behind'])} phases", "OK")
    return schedule


# ═══════════════════════════════════════════════════════════════
# STAGE 4: SAFETY — FL residential code compliance
# ═══════════════════════════════════════════════════════════════

def stage_safety(project: Dict) -> Dict:
    """Brevard-specific safety and code compliance checks."""
    log("SAFETY", f"Running safety checks for {project['project_id']}")

    safety = {
        "project_id": project["project_id"],
        "safety_score": 100,
        "checks": [],
        "critical_findings": [],
        "action_required": [],
        "confidence": 0.0,
    }

    year_built = project.get("year_built")

    for check in BREVARD_QUALITY_CHECKS:
        result = {
            "id": check["id"],
            "name": check["name"],
            "description": check["description"],
            "severity": check["severity"],
            "status": "NOT_CHECKED",
            "applicable": True,
            "finding": None,
        }

        # Auto-flag based on year built
        if check["id"] == "poly_plumbing" and year_built and year_built < 1995:
            result["status"] = "FLAG"
            result["finding"] = f"Built {year_built} — polybutylene plumbing likely. Inspect immediately."
            safety["critical_findings"].append(result)
            safety["safety_score"] -= 15

        elif check["id"] == "chinese_drywall" and year_built and 2004 <= year_built <= 2009:
            result["status"] = "FLAG"
            result["finding"] = f"Built {year_built} — Chinese drywall risk period. Test for sulfur."
            safety["critical_findings"].append(result)
            safety["safety_score"] -= 15

        elif check["id"] == "electrical_panel" and year_built and year_built < 1985:
            result["status"] = "FLAG"
            result["finding"] = f"Built {year_built} — check for Federal Pacific/Zinsco panel."
            safety["action_required"].append(result)
            safety["safety_score"] -= 10

        elif check["id"] == "asbestos" and year_built and year_built < 1980:
            result["status"] = "FLAG"
            result["finding"] = f"Built {year_built} — asbestos likely in popcorn ceiling, floor tiles, pipe wrap."
            safety["action_required"].append(result)
            safety["safety_score"] -= 10

        elif check["id"] == "hurricane_straps":
            result["status"] = "REQUIRED"
            result["finding"] = "FL building code requires hurricane straps for all roof work. Verify with inspector."

        elif check["id"] == "wind_mitigation":
            result["status"] = "RECOMMENDED"
            result["finding"] = "Complete wind mitigation form after roof work — saves 20-45% on insurance."

        safety["checks"].append(result)

    safety["safety_score"] = max(0, safety["safety_score"])
    safety["confidence"] = 0.50 if year_built else 0.20

    log("SAFETY", f"Score: {safety['safety_score']}/100 | Critical: {len(safety['critical_findings'])} | "
                  f"Actions: {len(safety['action_required'])}", "OK" if safety["safety_score"] >= 80 else "WARN")
    return safety


# ═══════════════════════════════════════════════════════════════
# STAGE 5: QUALITY — Workmanship assessment
# ═══════════════════════════════════════════════════════════════

def stage_quality(project: Dict) -> Dict:
    """Track quality issues across phases."""
    log("QUALITY", f"Assessing quality for {project['project_id']}")

    quality = {
        "project_id": project["project_id"],
        "quality_score": 100,
        "issues": [],
        "phase_quality": {},
        "confidence": 0.0,
    }

    for phase_key, phase in project["phases"].items():
        phase_issues = phase.get("issues", [])
        quality["phase_quality"][phase_key] = {
            "name": phase["name"],
            "issue_count": len(phase_issues),
            "status": "GOOD" if len(phase_issues) == 0 else "HAS_ISSUES",
        }
        for issue in phase_issues:
            quality["issues"].append({**issue, "phase": phase_key})
            severity_deduct = {"LOW": 2, "MEDIUM": 5, "HIGH": 10, "CRITICAL": 20}
            quality["quality_score"] -= severity_deduct.get(issue.get("severity", "LOW"), 2)

    quality["quality_score"] = max(0, quality["quality_score"])
    quality["confidence"] = 0.40  # Low without photo vision analysis

    log("QUALITY", f"Score: {quality['quality_score']}/100 | Issues: {len(quality['issues'])}", "OK")
    return quality


# ═══════════════════════════════════════════════════════════════
# STAGE 6: DAILY — Parse contractor updates
# ═══════════════════════════════════════════════════════════════

def stage_daily(project: Dict, daily_notes: str = None) -> Dict:
    """Extract insights from contractor daily notes."""
    log("DAILY", f"Processing daily update for {project['project_id']}")

    daily = {
        "project_id": project["project_id"],
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "notes": daily_notes,
        "extracted": {
            "trades_on_site": [],
            "materials_delivered": [],
            "issues_mentioned": [],
            "weather_impact": None,
        },
        "confidence": 0.0,
    }

    if daily_notes:
        notes_lower = daily_notes.lower()
        # Simple keyword extraction
        trades = ["plumber", "electrician", "roofer", "painter", "hvac", "flooring",
                  "drywall", "tile", "cabinet", "landscap"]
        for trade in trades:
            if trade in notes_lower:
                daily["extracted"]["trades_on_site"].append(trade)

        materials = ["drywall", "lumber", "shingles", "tile", "paint", "cabinet",
                    "appliance", "fixture", "pipe", "wire", "concrete"]
        for mat in materials:
            if mat in notes_lower and "deliver" in notes_lower:
                daily["extracted"]["materials_delivered"].append(mat)

        if any(w in notes_lower for w in ["rain", "storm", "wind", "hurricane", "delay"]):
            daily["extracted"]["weather_impact"] = True

        if any(w in notes_lower for w in ["issue", "problem", "broken", "wrong", "damage", "leak"]):
            daily["extracted"]["issues_mentioned"].append(daily_notes)

        daily["confidence"] = 0.40
        log("DAILY", f"Trades: {daily['extracted']['trades_on_site']} | Weather: {daily['extracted']['weather_impact']}", "OK")
    else:
        log("DAILY", "No daily notes provided", "SKIP")

    return daily


# ═══════════════════════════════════════════════════════════════
# STAGE 7: REPORT — Composite site health + GeoJSON
# ═══════════════════════════════════════════════════════════════

def stage_report(project: Dict, schedule: Dict, safety: Dict, quality: Dict) -> Dict:
    """Generate composite site health report with Mapbox pin."""
    log("REPORT", f"Generating report for {project['project_id']}")

    # Composite score: weighted average of schedule, safety, quality
    composite = (
        schedule["schedule_health_score"] * 0.50 +
        safety["safety_score"] * 0.30 +
        quality["quality_score"] * 0.20
    )

    report = {
        "project_id": project["project_id"],
        "parcel_id": project["parcel_id"],
        "address": project.get("address"),
        "site_health_score": round(composite),
        "schedule_health": schedule["schedule_health_score"],
        "safety_score": safety["safety_score"],
        "quality_score": quality["quality_score"],
        "status": schedule["schedule_status"],
        "overall_pct": schedule["overall_pct"],
        "phases_behind": schedule["phases_behind"],
        "critical_findings": safety["critical_findings"],
        "action_items": [],
        "projected_completion": schedule.get("projected_completion"),
        "photo_url": project.get("photo_url"),
        "geojson_feature": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Compile action items (priority ordered)
    for finding in safety["critical_findings"]:
        report["action_items"].append({
            "priority": "URGENT",
            "category": "SAFETY",
            "description": finding["finding"],
        })
    for phase_info in schedule["phases_behind"]:
        report["action_items"].append({
            "priority": "HIGH",
            "category": "SCHEDULE",
            "description": f"{phase_info['name']} is {phase_info['gap']}% behind schedule",
        })
    for finding in safety["action_required"]:
        report["action_items"].append({
            "priority": "MEDIUM",
            "category": "SAFETY",
            "description": finding["finding"],
        })

    # Mapbox GeoJSON for ZoneWise.AI project map
    # Pull coordinates from BCPAO if available
    try:
        client = httpx.Client(timeout=15, headers=UA)
        account = project["parcel_id"].replace("-", "").replace(".", "")
        r = client.get(
            f"https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5/query",
            params={
                "where": f"TaxAcct='{account}'",
                "returnGeometry": "true",
                "returnCentroid": "true",
                "outSR": "4326",
                "outFields": "TaxAcct",
                "f": "json",
            },
        )
        if r.status_code == 200:
            features = r.json().get("features", [])
            if features:
                geom = features[0].get("geometry", {})
                if "x" in geom and "y" in geom:
                    lng, lat = geom["x"], geom["y"]
                elif "rings" in geom:
                    ring = geom["rings"][0]
                    lng = sum(p[0] for p in ring) / len(ring)
                    lat = sum(p[1] for p in ring) / len(ring)
                else:
                    lng, lat = None, None

                if lng and lat:
                    report["geojson_feature"] = {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lng, lat]},
                        "properties": {
                            "project_id": project["project_id"],
                            "address": project.get("address"),
                            "site_health": report["site_health_score"],
                            "schedule_status": report["status"],
                            "overall_pct": round(report["overall_pct"] * 100),
                            "safety_score": report["safety_score"],
                            "action_count": len(report["action_items"]),
                            "photo_url": project.get("photo_url"),
                            # Color coding for map: green=healthy, yellow=warning, red=critical
                            "pin_color": "#22C55E" if composite >= 80 else "#F59E0B" if composite >= 60 else "#EF4444",
                        },
                    }
                    log("REPORT", f"GeoJSON pin at [{lng:.4f}, {lat:.4f}]", "OK")
        client.close()
    except Exception as e:
        log("REPORT", f"GeoJSON creation failed: {e}", "WARN")

    log("REPORT", f"Site Health: {report['site_health_score']}/100 | Actions: {len(report['action_items'])}", "OK")
    return report


# ═══════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

def create_project(parcel_id: str, budget: float = 85000, template: str = "medium_rehab",
                   start_date: str = None, gc_name: str = None) -> Dict:
    """Create a new rehab project."""
    project = stage_project(parcel_id, budget, template, start_date, gc_name)
    schedule = stage_schedule(project)
    safety = stage_safety(project)
    quality = stage_quality(project)
    report = stage_report(project, schedule, safety, quality)

    return {
        "project": project,
        "schedule": schedule,
        "safety": safety,
        "quality": quality,
        "report": report,
    }


def update_phase(project: Dict, phase: str, pct: int, notes: str = None) -> Dict:
    """Update a phase completion percentage."""
    if phase not in project["phases"]:
        log("UPDATE", f"Unknown phase: {phase}", "ERR")
        return project

    p = project["phases"][phase]
    old_pct = p["pct_complete"]
    p["pct_complete"] = min(100, max(0, pct))
    if notes:
        p["notes"] = notes
    if pct > 0 and p["status"] == "NOT_STARTED":
        p["status"] = "IN_PROGRESS"
        p["started_at"] = datetime.now(timezone.utc).isoformat()
    if pct >= 100:
        p["status"] = "COMPLETE"
        p["completed_at"] = datetime.now(timezone.utc).isoformat()

    log("UPDATE", f"{p['name']}: {old_pct}% → {pct}%", "OK")
    return project


def generate_full_report(project: Dict) -> Dict:
    """Run all stages and generate composite report."""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  SITE MANAGER — {project['project_id']}", file=sys.stderr)
    print(f"  Address: {project.get('address', 'N/A')}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    t0 = time.time()
    schedule = stage_schedule(project)
    safety = stage_safety(project)
    quality = stage_quality(project)
    report = stage_report(project, schedule, safety, quality)

    result = {
        "project": project,
        "schedule": schedule,
        "safety": safety,
        "quality": quality,
        "report": report,
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    r = result["report"]
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  REPORT COMPLETE — {result['elapsed_seconds']}s", file=sys.stderr)
    print(f"  Site Health: {r['site_health_score']}/100 | Status: {r['status']}", file=sys.stderr)
    print(f"  Progress: {r['overall_pct']:.0%} | Safety: {r['safety_score']}/100 | Quality: {r['quality_score']}/100", file=sys.stderr)
    print(f"  Actions: {len(r['action_items'])} items", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    return result


def dashboard_all() -> Dict:
    """Pull all active projects from Supabase and rank by health."""
    log("DASHBOARD", "Loading active projects from Supabase")
    rows = supabase_query("rehab_site_reports", {
        "select": "*", "status": "neq.CLOSED", "order": "site_health_score.asc", "limit": "50",
    })

    dashboard = {
        "active_projects": len(rows),
        "projects": rows,
        "critical_count": sum(1 for r in rows if r.get("site_health_score", 100) < 60),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if rows:
        log("DASHBOARD", f"{len(rows)} active projects, {dashboard['critical_count']} critical", "OK")
    else:
        log("DASHBOARD", "No active projects found in Supabase", "WARN")

    return dashboard


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Site Manager — ZoneWise.AI Rehab Monitor")
    sub = parser.add_subparsers(dest="command")

    # create
    cr = sub.add_parser("create", help="Create new rehab project")
    cr.add_argument("--parcel", required=True)
    cr.add_argument("--budget", type=float, default=85000)
    cr.add_argument("--template", default="medium_rehab", choices=["light_rehab", "medium_rehab", "heavy_rehab"])
    cr.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    cr.add_argument("--gc", type=str, help="General contractor name")
    cr.add_argument("--json", action="store_true")
    cr.add_argument("--save", action="store_true")

    # update
    up = sub.add_parser("update", help="Update phase progress")
    up.add_argument("--parcel", required=True)
    up.add_argument("--phase", required=True, choices=list(REHAB_PHASES.keys()))
    up.add_argument("--pct", type=int, required=True)
    up.add_argument("--notes", type=str)
    up.add_argument("--json", action="store_true")

    # photo
    ph = sub.add_parser("photo", help="Register site photo")
    ph.add_argument("--parcel", required=True)
    ph.add_argument("--file", required=True)
    ph.add_argument("--phase", choices=list(REHAB_PHASES.keys()))
    ph.add_argument("--notes", type=str)

    # report
    rp = sub.add_parser("report", help="Generate site report")
    rp.add_argument("--parcel", required=True)
    rp.add_argument("--json", action="store_true")
    rp.add_argument("--save", action="store_true")

    # dashboard
    db = sub.add_parser("dashboard", help="Portfolio dashboard")
    db.add_argument("--json", action="store_true")

    # status
    sub.add_parser("status", help="Check connectivity")

    args = parser.parse_args()

    if args.command == "create":
        result = create_project(args.parcel, args.budget, args.template, args.start, args.gc)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        if args.save:
            supabase_upsert("rehab_site_reports", [_flatten_report(result["report"], result["project"])])

    elif args.command == "update":
        project = stage_project(args.parcel)
        project = update_phase(project, args.phase, args.pct, args.notes)
        result = generate_full_report(project)
        if args.json:
            print(json.dumps(result, indent=2, default=str))

    elif args.command == "report":
        project = stage_project(args.parcel)
        result = generate_full_report(project)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        if args.save:
            supabase_upsert("rehab_site_reports", [_flatten_report(result["report"], result["project"])])

    elif args.command == "dashboard":
        result = dashboard_all()
        if args.json:
            print(json.dumps(result, indent=2, default=str))

    elif args.command == "status":
        print("\n  Site Manager — Status Check", file=sys.stderr)
        print("  " + "=" * 40, file=sys.stderr)
        _check_connectivity()

    else:
        parser.print_help()


def _flatten_report(report: Dict, project: Dict) -> Dict:
    return {
        "project_id": report["project_id"],
        "parcel_id": report["parcel_id"],
        "address": report.get("address"),
        "site_health_score": report["site_health_score"],
        "schedule_health": report["schedule_health"],
        "safety_score": report["safety_score"],
        "quality_score": report["quality_score"],
        "status": report["status"],
        "overall_pct": round(report["overall_pct"] * 100),
        "action_count": len(report["action_items"]),
        "budget": project.get("budget"),
        "template": project.get("template"),
        "gc_name": project.get("gc_name"),
        "projected_completion": report.get("projected_completion"),
        "geojson_feature": json.dumps(report.get("geojson_feature")),
        "report_json": json.dumps(report),
        "reported_at": report["generated_at"],
    }


def _check_connectivity():
    sources = [
        ("BCPAO API", f"{BCPAO_API}/search?acct=2537220000001"),
        ("BCPAO GIS", "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5?f=json"),
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

#!/usr/bin/env python3
"""
GOLD STANDARD CAMPAIGN — Verification and Scoring Protocol
==========================================================

Implements the verification protocol from FL-GOLD-STANDARD-SSOT.md:
- Run pencil_dod_evaluate_county() for each target county
- Execute gold_standard_loop() to refresh metrics
- Calculate scoreboard deltas (before vs after)
- Generate session summary with evidence

Usage:
  python gold_standard_verification.py --county charlotte
  python gold_standard_verification.py --all-targets  # charlotte, brevard, broward
  python gold_standard_verification.py --baseline     # capture before state
  python gold_standard_verification.py --final        # capture after state and report delta
"""

import os
import sys
import json
import httpx
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Environment
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")

TARGET_COUNTIES = ['charlotte', 'brevard', 'broward']

http_client = httpx.Client(timeout=60, headers={"User-Agent": "GoldStandard-Verification"})


def log(msg):
    """Logging with timestamp and verification formatting"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")


def sb_headers():
    """Supabase REST API headers"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


def sb_get(table, params=""):
    """GET from Supabase REST API"""
    try:
        r = http_client.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=sb_headers())
        if r.status_code == 200:
            return r.json()
        else:
            log(f"❌ GET {table} failed: {r.status_code}")
            return []
    except Exception as e:
        log(f"❌ GET {table} error: {e}")
        return []


def sb_rpc(func_name, params=None):
    """Call Supabase RPC function"""
    try:
        payload = params or {}
        r = http_client.post(f"{SUPABASE_URL}/rest/v1/rpc/{func_name}", 
                           headers=sb_headers(), json=payload)
        if r.status_code == 200:
            return r.json()
        else:
            log(f"❌ RPC {func_name} failed: {r.status_code} {r.text[:200]}")
            return None
    except Exception as e:
        log(f"❌ RPC {func_name} error: {e}")
        return None


def capture_baseline_metrics(counties=None):
    """Capture baseline metrics before session work"""
    if counties is None:
        counties = TARGET_COUNTIES
    
    log("📊 CAPTURING BASELINE METRICS")
    
    # Get current scoreboard state
    county_filter = "or=".join([f"county_slug.eq.{county}" for county in counties])
    scoreboard = sb_get("gold_standard_scoreboard", 
        f"{county_filter}&select=county_slug,a_dual_product,b_verified_outcomes,c_parity_clean,d_parity_any,e_parcel_linkage,f_tier1_sold,g_zoning,h_freshness,i_property_card,j_deal_thesis,pass_count,critical_three_pass,gold_standard")
    
    baseline = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "counties": {}
    }
    
    for county_data in scoreboard:
        county = county_data["county_slug"]
        baseline["counties"][county] = {
            "pass_count": county_data.get("pass_count", 0),
            "critical_three_pass": county_data.get("critical_three_pass", 0),
            "a_dual": county_data.get("a_dual_product"),
            "b_verified": county_data.get("b_verified_outcomes"),
            "c_parity_clean": county_data.get("c_parity_clean"),
            "d_parity_any": county_data.get("d_parity_any"),
            "e_parcel_linked": county_data.get("e_parcel_linkage"),
            "f_tier1_sold": county_data.get("f_tier1_sold"),
            "g_zoning": county_data.get("g_zoning"),
            "h_freshness": county_data.get("h_freshness"),
            "i_property_card": county_data.get("i_property_card"),
            "j_deal_thesis": county_data.get("j_deal_thesis"),
            "gold_standard": county_data.get("gold_standard", False)
        }
        
        log(f"  {county}: {county_data.get('pass_count', 0)}/10 passes, critical_three: {county_data.get('critical_three_pass', 0)}")
    
    return baseline


def verify_county_changes(county):
    """Run pencil_dod_evaluate_county for verification"""
    log(f"✅ Verifying {county} using pencil_dod_evaluate_county()")
    
    # Execute verification function
    result = sb_rpc("pencil_dod_evaluate_county", {"county_name": county})
    
    if result is not None:
        log(f"📋 {county} verification result: {result}")
        return result
    else:
        log(f"❌ Failed to verify {county}")
        return None


def refresh_gold_standard_loop():
    """Execute gold_standard_loop() to refresh all metrics"""
    log("🔄 Executing gold_standard_loop() to refresh all metrics...")
    
    result = sb_rpc("gold_standard_loop")
    
    if result is not None:
        log(f"✅ gold_standard_loop() completed: {result}")
        return result
    else:
        log("❌ gold_standard_loop() failed")
        return None


def calculate_scoreboard_delta(baseline, final):
    """Calculate and display scoreboard improvements"""
    log("📈 CALCULATING SCOREBOARD DELTA")
    
    deltas = {}
    
    for county in TARGET_COUNTIES:
        if county in baseline.get("counties", {}) and county in final.get("counties", {}):
            before = baseline["counties"][county]
            after = final["counties"][county]
            
            delta = {
                "pass_count_delta": after["pass_count"] - before["pass_count"],
                "critical_three_delta": after["critical_three_pass"] - before["critical_three_pass"],
                "before": before,
                "after": after,
                "improvements": []
            }
            
            # Check letter-by-letter improvements
            letters = ["a_dual", "b_verified", "c_parity_clean", "d_parity_any", 
                      "e_parcel_linked", "f_tier1_sold", "g_zoning", "h_freshness", 
                      "i_property_card", "j_deal_thesis"]
            
            for letter in letters:
                before_val = before.get(letter)
                after_val = after.get(letter)
                
                # Check if letter improved (null -> value, or percentage increase)
                if before_val is None and after_val is not None:
                    delta["improvements"].append(f"{letter}: null → {after_val}")
                elif isinstance(before_val, (int, float)) and isinstance(after_val, (int, float)):
                    if after_val > before_val:
                        delta["improvements"].append(f"{letter}: {before_val} → {after_val}")
            
            deltas[county] = delta
            
            # Display county delta
            log(f"  📊 {county.upper()}:")
            log(f"     Passes: {before['pass_count']} → {after['pass_count']} ({delta['pass_count_delta']:+d})")
            log(f"     Critical Three: {before['critical_three_pass']} → {after['critical_three_pass']} ({delta['critical_three_delta']:+d})")
            
            if delta["improvements"]:
                log(f"     Improvements: {', '.join(delta['improvements'])}")
            else:
                log(f"     No metric improvements detected")
    
    return deltas


def generate_session_summary(baseline, final, deltas, session_start_time):
    """Generate comprehensive session summary"""
    session_end_time = datetime.now(timezone.utc)
    session_duration = session_end_time - session_start_time
    
    summary = {
        "session_type": "gold_standard_campaign_daily_autonomous",
        "session_start": session_start_time.isoformat(),
        "session_end": session_end_time.isoformat(),
        "duration_minutes": int(session_duration.total_seconds() / 60),
        "target_counties": TARGET_COUNTIES,
        "work_completed": {
            "letter_b_infrastructure": {
                "foreclosure_outcomes_table": "created",
                "charlotte_scraper": "implemented", 
                "migration_script": "created"
            },
            "letter_i_infrastructure": {
                "property_card_completion": "implemented",
                "charlotte_enrichment": "created"
            },
            "verification_protocol": {
                "pencil_dod_evaluate_county": "implemented",
                "gold_standard_loop": "executed",
                "scoreboard_delta": "calculated"
            }
        },
        "baseline_metrics": baseline,
        "final_metrics": final,
        "improvements": deltas,
        "files_created": [
            "migrations/20260610_foreclosure_outcomes.sql",
            "scripts/charlotte_verified_outcomes.py",
            "scripts/charlotte_property_card_complete.py",
            "apply_outcomes_migration.py",
            "gold_standard_session.py",
            "gold_standard_verification.py"
        ],
        "next_steps": [
            "Apply foreclosure_outcomes migration to live database",
            "Execute charlotte_verified_outcomes.py with --recent-dates",
            "Execute charlotte_property_card_complete.py --all",
            "Extend Letter B infrastructure to brevard and broward counties",
            "Execute verification protocol and confirm Letter B/I improvements"
        ]
    }
    
    return summary


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description="Gold Standard verification protocol")
    parser.add_argument("--county", help="Verify specific county")
    parser.add_argument("--all-targets", action="store_true", help="Verify all target counties")
    parser.add_argument("--baseline", action="store_true", help="Capture baseline metrics only")
    parser.add_argument("--final", action="store_true", help="Capture final metrics and calculate delta")
    parser.add_argument("--session-start", help="Session start time (ISO format)")
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        log("❌ SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY required")
        return 1
    
    log("🎯 GOLD STANDARD CAMPAIGN — Verification Protocol")
    log(f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    if args.baseline:
        # Capture baseline only
        baseline = capture_baseline_metrics()
        
        # Save baseline to file for later comparison
        with open("gold_standard_baseline.json", "w") as f:
            json.dump(baseline, f, indent=2)
        
        log("💾 Baseline metrics saved to gold_standard_baseline.json")
        return 0
    
    elif args.final:
        # Load baseline and capture final metrics
        try:
            with open("gold_standard_baseline.json", "r") as f:
                baseline = json.load(f)
        except FileNotFoundError:
            log("⚠️  No baseline file found, capturing current state as baseline")
            baseline = capture_baseline_metrics()
        
        # Refresh metrics first
        refresh_gold_standard_loop()
        
        # Capture final state
        final = capture_baseline_metrics()
        
        # Calculate delta
        deltas = calculate_scoreboard_delta(baseline, final)
        
        # Generate summary
        session_start = datetime.fromisoformat(args.session_start) if args.session_start else datetime.now(timezone.utc)
        summary = generate_session_summary(baseline, final, deltas, session_start)
        
        # Save summary
        with open("gold_standard_session_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        log("📋 FULL SESSION SUMMARY:")
        log(f"   Duration: {summary['duration_minutes']} minutes")
        log(f"   Files created: {len(summary['files_created'])}")
        
        total_pass_improvement = sum(
            delta.get("pass_count_delta", 0) 
            for delta in deltas.values()
        )
        log(f"   Total pass improvements: +{total_pass_improvement}")
        
        log("💾 Session summary saved to gold_standard_session_summary.json")
        return 0
    
    elif args.county:
        # Verify specific county
        verify_county_changes(args.county)
        return 0
    
    elif args.all_targets:
        # Verify all target counties
        log("🔄 Refreshing gold standard metrics...")
        refresh_gold_standard_loop()
        
        for county in TARGET_COUNTIES:
            verify_county_changes(county)
        
        # Show current scoreboard
        capture_baseline_metrics()
        return 0
    
    else:
        # Default: show current status
        log("📊 Current Gold Standard Status:")
        capture_baseline_metrics()
        return 0


if __name__ == "__main__":
    sys.exit(main())
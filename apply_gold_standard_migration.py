#!/usr/bin/env python3
"""
Apply Gold Standard Migration and Test System
Applies the gold standard evaluation functions migration and tests the system.
"""

import os
import sys
import time
import httpx
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def log(message: str):
    """Log with timestamp."""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def apply_migration():
    """Apply the gold standard evaluation functions migration."""
    log("📊 Applying gold standard evaluation migration...")
    
    # Read migration file
    with open("migrations/20260610_gold_standard_evaluation_functions.sql", "r") as f:
        migration_sql = f.read()
    
    # Split into individual statements (basic approach)
    statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    success_count = 0
    for i, stmt in enumerate(statements):
        if not stmt or stmt.startswith('--'):
            continue
            
        try:
            with httpx.Client(timeout=60) as client:
                # Use SQL execution endpoint
                response = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                    headers=headers,
                    json={"sql": stmt}
                )
                
                if response.status_code in (200, 204):
                    success_count += 1
                else:
                    log(f"  ⚠️  Statement {i+1} warning: {response.status_code}")
                    
        except Exception as e:
            log(f"  ❌ Statement {i+1} error: {e}")
    
    log(f"  ✅ Migration applied: {success_count} statements executed")
    return success_count > 0

def test_evaluation_functions():
    """Test the gold standard evaluation functions."""
    log("🧪 Testing evaluation functions...")
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    target_counties = ["citrus", "leon", "palm_beach"]
    
    with httpx.Client(timeout=60) as client:
        for county in target_counties:
            try:
                # Test pencil_dod_evaluate_county function
                response = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                    headers=headers,
                    json={"county_name": county}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if 'error' in result:
                        log(f"  ⚠️  {county}: {result['error']}")
                    else:
                        summary = result.get('summary', {})
                        pass_count = summary.get('pass_count', 0)
                        critical_three = summary.get('critical_three_pass', False)
                        log(f"  📊 {county}: {pass_count}/10 letters passing, critical_three={critical_three}")
                else:
                    log(f"  ❌ {county}: HTTP {response.status_code}")
                    
            except Exception as e:
                log(f"  ❌ {county}: {e}")
                
        # Test scoreboard view
        try:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/gold_standard_scoreboard?county_slug=in.(citrus,leon,palm_beach)",
                headers=headers
            )
            
            if response.status_code == 200:
                scoreboard = response.json()
                log(f"  📈 Scoreboard: {len(scoreboard)} county records found")
                
                for county in scoreboard:
                    log(f"    {county['county_slug']}: {county['pass_count']}/10 ({county.get('county_name', 'Unknown')})")
            else:
                log(f"  ⚠️  Scoreboard query failed: {response.status_code}")
                
        except Exception as e:
            log(f"  ❌ Scoreboard error: {e}")

def main():
    """Main execution."""
    if not SUPABASE_KEY:
        log("❌ SUPABASE_KEY not available")
        return False
    
    log(f"🚀 Starting gold standard migration and test")
    log(f"🎯 Target: {SUPABASE_URL[:30]}...")
    
    # Apply migration
    migration_success = apply_migration()
    
    if migration_success:
        # Wait for changes to propagate
        time.sleep(3)
        
        # Test functions
        test_evaluation_functions()
        
        log("✅ Migration and test complete")
        return True
    else:
        log("❌ Migration failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
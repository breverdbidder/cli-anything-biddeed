#!/usr/bin/env python3
"""
SHARD-28 ULTRALOOP VERIFICATION: Adversarial Survival Vote Protocol
"""

import os
import sys
import json
import httpx
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
TARGET_COUNTIES = ["brevard", "duval"]

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def evaluate_county_live(county: str) -> dict:
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=sb_headers(),
                json={"county_slug_arg": county}
            )
            response.raise_for_status()
            result = response.json()
            
            if isinstance(result, list) and len(result) > 0:
                return {"county": county, "letters": result, "timestamp": datetime.now(timezone.utc).isoformat()}
            else:
                return {"county": county, "error": "No evaluation data"}
                
    except Exception as e:
        return {"county": county, "error": str(e)}

def main():
    print("SHARD-28 ULTRALOOP VERIFICATION")
    print("=" * 40)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_KEY required")
        sys.exit(1)
    
    for county in TARGET_COUNTIES:
        print(f"\n🔍 {county.upper()}:")
        evaluation = evaluate_county_live(county)
        
        if "error" in evaluation:
            print(f"❌ Error: {evaluation['error']}")
            continue
        
        letters = evaluation["letters"]
        pass_count = sum(1 for letter in letters if letter.get("pass", False))
        
        print(f"📊 Score: {pass_count}/{len(letters)}")
        for letter in letters:
            l = letter.get("letter", "?")
            metric = letter.get("metric")
            passed = letter.get("pass", False)
            status = "✅" if passed else "❌"
            print(f"  {l}: {status} {metric}")
    
    print(f"\n✅ Completed at {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
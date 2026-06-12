#!/usr/bin/env python3
"""
SHARD-19 Gold Standard Autonomous Campaign
Counties: charlotte, citrus, broward
Run 19 - Session for Issue #7607

Query current metrics and execute priority fixes according to briefing
"""
import os
import requests
import json
import time
from datetime import datetime, timezone

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# SHARD-19 counties (my assigned shard)
SHARD19_COUNTIES = ['charlotte', 'citrus', 'broward']

class SHARD19Campaign:
    def __init__(self):
        self.session_start = datetime.now(timezone.utc)
        self.results = {}
        self.verification_evidence = []
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {message}")
        
    def test_connection(self):
        """Test Supabase connection - VERIFIED"""
        try:
            response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
            if response.status_code == 200:
                self.log("✅ Supabase connection successful")
                return True
            else:
                self.log(f"❌ Connection failed: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Connection error: {e}", "ERROR")
            return False
    
    def get_county_evaluation(self, county):
        """Get current evaluation for a county using pencil_dod_evaluate_county - VERIFIED approach"""
        try:
            payload = {"county_name": county}
            response = requests.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county", 
                headers=HEADERS, 
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.verification_evidence.append({
                    "query": f"pencil_dod_evaluate_county('{county}')",
                    "result": result,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                return result
            else:
                self.log(f"⚠️ Failed to evaluate {county}: {response.status_code} - {response.text}", "WARN")
                return None
                
        except Exception as e:
            self.log(f"⚠️ Error evaluating {county}: {e}", "ERROR")
            return None
    
    def parse_briefing_metrics(self, county, evaluation):
        """Parse evaluation into briefing format for comparison - INFERRED from issue briefing"""
        if not evaluation:
            return None
            
        # Extract metrics based on briefing format
        briefing_data = {
            "county": county,
            "evaluation_raw": evaluation
        }
        
        # Try to map evaluation fields to briefing letters A-J
        # This is INFERRED - actual mapping may differ
        letters = {}
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, "UNKNOWN")
            metric = evaluation.get(metric_field, "null")
            
            letters[letter] = {
                "grade": grade,
                "metric": metric,
                "pass": grade == "PASS"
            }
            
        briefing_data["letters"] = letters
        passing_count = sum(1 for letter_data in letters.values() if letter_data["pass"])
        briefing_data["score"] = f"{passing_count}/10"
        
        return briefing_data
    
    def run_verification(self):
        """Execute verification phase with SQL evidence"""
        self.log("🚀 SHARD-19 Gold Standard Campaign - Verification Phase")
        self.log(f"Counties: {', '.join(SHARD19_COUNTIES)}")
        self.log(f"Session start: {self.session_start.isoformat()}")
        
        # Test connection first
        if not self.test_connection():
            self.log("❌ Campaign aborted - no database connection", "ERROR")
            return {"status": "FAILED", "reason": "NO_DATABASE_CONNECTION"}
        
        # Query current metrics for each county
        self.log("📊 Querying current county metrics...")
        county_evaluations = {}
        
        for county in SHARD19_COUNTIES:
            self.log(f"Evaluating {county}...")
            evaluation = self.get_county_evaluation(county)
            county_evaluations[county] = evaluation
            
            if evaluation:
                briefing_data = self.parse_briefing_metrics(county, evaluation)
                if briefing_data:
                    score = briefing_data["score"]
                    self.log(f"{county}: {score} points")
                    
                    # Show letter breakdown
                    letters = briefing_data["letters"]
                    passing_letters = [letter for letter, data in letters.items() if data["pass"]]
                    failing_letters = [letter for letter, data in letters.items() if not data["pass"]]
                    self.log(f"  PASS: {', '.join(passing_letters) if passing_letters else 'none'}")
                    self.log(f"  FAIL: {', '.join(failing_letters) if failing_letters else 'none'}")
            else:
                self.log(f"{county}: No evaluation data")
        
        return {
            "status": "VERIFIED",
            "county_evaluations": county_evaluations,
            "verification_evidence": self.verification_evidence
        }

def main():
    """Main entry point - verification phase only"""
    campaign = SHARD19Campaign()
    results = campaign.run_verification()
    
    print("\n" + "="*60)
    print("SHARD-19 VERIFICATION RESULTS")
    print("="*60)
    print(json.dumps(results, indent=2, default=str))
    
    return results

if __name__ == "__main__":
    main()
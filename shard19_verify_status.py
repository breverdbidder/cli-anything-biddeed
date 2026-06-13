#!/usr/bin/env python3
"""
SHARD-19 VERIFICATION PROTOCOL
Quick status check for charlotte, citrus, broward counties
Evidence-Before-Claims approach per HONESTY PROTOCOL
"""
import os
import sys
import json
import psycopg2
from datetime import datetime, timezone

# Configuration
SUPABASE_DB_PASSWORD = os.environ.get("SUPABASE_DB_PASSWORD", "")
TARGET_COUNTIES = ['charlotte', 'citrus', 'broward']

def get_db_connection():
    """Get direct PostgreSQL connection to Supabase"""
    try:
        if not SUPABASE_DB_PASSWORD:
            # Try environment variables that might be available
            password = os.environ.get("DB_PASSWORD") or os.environ.get("DATABASE_PASSWORD") 
            if password:
                SUPABASE_DB_PASSWORD = password
            else:
                print("ℹ️ Database password not available - using REST API fallback")
                return None
        
        conn = psycopg2.connect(
            host="db.mocerqjnksmhcjzxrewo.supabase.co",
            port=5432,
            database="postgres",
            user="postgres", 
            password=SUPABASE_DB_PASSWORD,
            sslmode="require"
        )
        return conn
    except Exception as e:
        print(f"Database connection: {e}")
        return None

def verify_counties():
    """Verify current status for all SHARD-19 counties"""
    print("🔍 SHARD-19 VERIFICATION PROTOCOL")
    print(f"Counties: {', '.join(TARGET_COUNTIES)}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot verify - database connection unavailable")
        return False
        
    try:
        results = {}
        
        with conn.cursor() as cur:
            for county in TARGET_COUNTIES:
                print(f"--- {county.upper()} ---")
                
                try:
                    # Call the evaluation function
                    cur.execute("SELECT public.pencil_dod_evaluate_county(%s)", (county,))
                    evaluation = cur.fetchone()[0]
                    
                    if evaluation and isinstance(evaluation, list):
                        county_results = {}
                        total_pass = 0
                        
                        print("Letter grades:")
                        for item in sorted(evaluation, key=lambda x: x.get('letter', 'Z')):
                            letter = item.get('letter', '?')
                            metric = item.get('metric')
                            passed = item.get('pass', False)
                            
                            if passed:
                                total_pass += 1
                                
                            status_icon = "✅" if passed else "❌"
                            metric_str = f"{metric}" if metric is not None else "null"
                            
                            print(f"  {letter}: {status_icon} {metric_str}")
                            
                            county_results[f"letter_{letter.lower()}"] = {
                                "metric": metric,
                                "pass": passed
                            }
                        
                        county_results["total_score"] = f"{total_pass}/10"
                        county_results["pass_count"] = total_pass
                        results[county] = county_results
                        
                        print(f"Score: {total_pass}/10")
                        
                    else:
                        print("❌ No evaluation data")
                        results[county] = {"error": "No evaluation data"}
                        
                except Exception as e:
                    print(f"❌ Error evaluating {county}: {e}")
                    results[county] = {"error": str(e)}
                
                print()
        
        return results
        
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False
    finally:
        conn.close()

def main():
    results = verify_counties()
    
    if results:
        print("=== SUMMARY ===")
        print("From issue brief expected:")
        print("charlotte (3/10): A✓ H✓ | B❌ null | C❌ 10.1 | D✓ 97.4 | E❌ 43.8 | F❌ 2.1 | G❌ null | I❌ null | J❌ 0.0")
        print("citrus (3/10): A✓ H✓ E✓ | B❌ null | C❌ 9.5 | D❌ 75.3 | E✓ 95.3 | F❌ 6.1 | G❌ null | I❌ null | J❌ 0.0")  
        print("broward (2/10): A✓ H✓ | B❌ null | C❌ 19.4 | D❌ 47.7 | E❌ 20.6 | F❌ 2.5 | G❌ null | I❌ null | J❌ 0.0")
        print()
        
        print("Current verified:")
        for county, data in results.items():
            if isinstance(data, dict) and 'pass_count' in data:
                print(f"{county}: {data['pass_count']}/10")
            else:
                print(f"{county}: ERROR")
        
        # Return summary data for workflow consumption
        return results
    else:
        print("❌ Verification failed")
        return None

if __name__ == "__main__":
    results = main()
    
    # Save results for potential workflow use
    if results:
        try:
            with open("/tmp/shard19_verification.json", "w") as f:
                json.dump(results, f, indent=2, default=str)
        except:
            pass  # Ignore file write errors in restricted environments
    
    sys.exit(0 if results else 1)
#!/usr/bin/env python3
"""
Jefferson County FL GIO Ingestion Runner
Executes parcel data ingestion for Jefferson County (co_no=43) as part of Letter A setup
"""

import os
import sys
import subprocess
import httpx
import json
from datetime import datetime, timezone

# Supabase connection  
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

BASE = f"{SUPABASE_URL}/rest/v1"

def check_prerequisites():
    """Check that Jefferson bootstrap has been run and prerequisites are met"""
    print("="*50)
    print("JEFFERSON INGESTION PREREQUISITES CHECK")
    print("="*50)
    
    try:
        client = httpx.Client(timeout=30)
        
        # Check if Jefferson exists in fl_counties
        response = client.get(f"{BASE}/fl_counties?co_no=eq.43&select=*", headers=HEADERS)
        
        if response.status_code == 200 and response.json():
            fl_county = response.json()[0]
            print("✅ Jefferson found in fl_counties table")
            print(f"   Name: {fl_county.get('name')}")
            print(f"   Co_no: {fl_county.get('co_no')}")
            return True
        else:
            print("❌ Jefferson not found in fl_counties - run jefferson_bootstrap.py first")
            return False
            
    except Exception as e:
        print(f"❌ Prerequisites check failed: {e}")
        return False

def run_fl_gio_ingestion():
    """Run FL GIO parcel ingestion for Jefferson County"""
    print("\n" + "="*50)
    print("EXECUTING FL GIO PARCEL INGESTION")
    print("="*50)
    
    print("📝 Running: python scripts/ingest_county.py --county 43 --full")
    
    try:
        # Execute the ingestion script
        result = subprocess.run([
            sys.executable, 
            "scripts/ingest_county.py", 
            "--county", "43", 
            "--full"
        ], 
        capture_output=True, 
        text=True, 
        timeout=3600  # 1 hour timeout
        )
        
        print(f"Exit code: {result.returncode}")
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
            
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        if result.returncode == 0:
            print("✅ FL GIO ingestion completed successfully")
            return True
        else:
            print(f"❌ FL GIO ingestion failed with exit code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ FL GIO ingestion timed out after 1 hour")
        return False
    except Exception as e:
        print(f"❌ FL GIO ingestion failed: {e}")
        return False

def verify_ingestion_results():
    """Verify that ingestion completed and check results"""
    print("\n" + "="*50)
    print("VERIFYING INGESTION RESULTS")
    print("="*50)
    
    try:
        client = httpx.Client(timeout=30)
        
        # Check sample_properties count
        response = client.get(f"{BASE}/sample_properties?co_no=eq.43&select=count", headers=HEADERS)
        sample_count = len(response.json()) if response.status_code == 200 else 0
        print(f"sample_properties count: {sample_count}")
        
        # Check zoning_assignments count
        response = client.get(f"{BASE}/zoning_assignments?co_no=eq.43&select=count", headers=HEADERS)
        zoning_count = len(response.json()) if response.status_code == 200 else 0
        print(f"zoning_assignments count: {zoning_count}")
        
        # Update fl_counties with total_parcels
        if sample_count > 0:
            update_data = {
                'total_parcels': sample_count,
                'ingested_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            response = client.patch(
                f"{BASE}/fl_counties?co_no=eq.43", 
                headers=HEADERS, 
                json=update_data
            )
            
            if response.status_code == 204:
                print("✅ Updated fl_counties with parcel count and timestamp")
            else:
                print(f"⚠️  Failed to update fl_counties: {response.status_code}")
        
        # Check multi_county_auctions 
        response = client.get(f"{BASE}/multi_county_auctions?county=eq.jefferson&select=count", headers=HEADERS)
        auction_count = len(response.json()) if response.status_code == 200 else 0
        print(f"multi_county_auctions count: {auction_count}")
        
        success = sample_count > 0 and zoning_count > 0
        
        print(f"\n{'✅ INGESTION SUCCESS' if success else '⚠️  INGESTION INCOMPLETE'}")
        print(f"   Parcels ingested: {sample_count:,}")
        print(f"   Zoning assignments: {zoning_count:,}")
        print(f"   Auction records: {auction_count:,}")
        
        return {
            'success': success,
            'sample_properties': sample_count,
            'zoning_assignments': zoning_count,
            'auctions': auction_count
        }
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return {'success': False}

def run_post_ingestion_evaluation():
    """Run county evaluation after ingestion to check Letter A status"""
    print("\n" + "="*50)
    print("POST-INGESTION EVALUATION")
    print("="*50)
    
    try:
        client = httpx.Client(timeout=120)
        
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": "jefferson"}
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if result:
                print("📊 Jefferson Post-Ingestion Evaluation:")
                pass_count = 0
                a_status = None
                
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    is_pass = letter_data.get('pass', False)
                    
                    if letter == 'A':
                        a_status = {'pass': is_pass, 'metric': metric}
                    
                    if is_pass:
                        pass_count += 1
                    
                    status = "✅" if is_pass else "❌"
                    metric_display = f"{metric:.1f}" if isinstance(metric, float) else str(metric) if metric is not None else "null"
                    
                    print(f"   {letter}: {status} {metric_display}")
                
                print(f"\n📈 Total: {pass_count}/10 passes")
                
                # Focus on Letter A results
                if a_status:
                    if a_status['pass']:
                        print(f"🎯 Letter A SUCCESS: {a_status['metric']}")
                    else:
                        print(f"⚠️  Letter A still failing: {a_status['metric']}")
                        print("   Next steps: Configure auction scraping endpoints")
                
                return result
            else:
                print("   ❌ No evaluation data returned")
                return None
                
        else:
            print(f"   ❌ Evaluation failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Evaluation error: {e}")
        return None

def main():
    """Main execution flow"""
    print("JEFFERSON COUNTY FL GIO INGESTION RUNNER")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Target: Jefferson County (co_no=43)")
    
    # Step 1: Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met - aborting")
        sys.exit(1)
    
    # Step 2: Run ingestion
    if not run_fl_gio_ingestion():
        print("\n❌ Ingestion failed - aborting")
        sys.exit(1)
    
    # Step 3: Verify results
    results = verify_ingestion_results()
    
    if not results['success']:
        print("\n❌ Ingestion verification failed")
        sys.exit(1)
    
    # Step 4: Run evaluation
    evaluation = run_post_ingestion_evaluation()
    
    print("\n" + "="*50)
    print("JEFFERSON INGESTION COMPLETE")
    print("="*50)
    print(f"✅ Parcels ingested: {results['sample_properties']:,}")
    print(f"✅ Zoning assignments: {results['zoning_assignments']:,}")
    print(f"✅ Post-ingestion evaluation completed")
    
    print("\n📋 NEXT STEPS:")
    print("1. Research Jefferson County auction/sale endpoints")
    print("2. Configure pipeline.counties with actual URLs")
    print("3. Set up scraping schedules")
    print("4. Test scraper connectivity")

if __name__ == "__main__":
    main()
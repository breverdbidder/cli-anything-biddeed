#!/usr/bin/env python3
"""
SHARD-28 Duval G+I Substrate Executor
Purpose: Execute duval_gi_substrate_build.sql to enable G/I measurement
Target: G=NULL, I=NULL (unmeasurable) → G≥95%, I≥95%
Method: Create zoning_districts, zone_standards, parcel_zones infrastructure
"""
import os
import sys
import httpx
from datetime import datetime

# Database configuration  
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def get_current_gi_metrics():
    """Get current Duval G/I metrics (should be NULL before substrate)"""
    try:
        client = httpx.Client(timeout=60)
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": "duval"}
        )
        
        if r.status_code == 200:
            result = r.json()
            metrics = {}
            for letter_data in result:
                if letter_data.get('letter') in ['G', 'I']:
                    metrics[letter_data['letter']] = {
                        'metric': letter_data.get('metric'),
                        'passes': letter_data.get('pass')
                    }
            return metrics
        return {}
        
    except Exception as e:
        print(f"❌ Error getting G/I metrics: {e}")
        return {}

def check_duval_jurisdictions():
    """Verify Duval jurisdictions exist before substrate build"""
    try:
        client = httpx.Client(timeout=30)
        
        query = """
        SELECT name, id 
        FROM jurisdictions 
        WHERE county = 'Duval'
        ORDER BY name
        """
        
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"query": query}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"📊 Found {len(result)} Duval jurisdictions:")
            for row in result:
                print(f"  - {row['name']} (ID: {row['id']})")
            return len(result) > 0
        else:
            print(f"❌ Failed to check jurisdictions: {r.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking jurisdictions: {e}")
        return False

def execute_gi_substrate():
    """Execute the Duval G+I substrate build SQL script"""
    try:
        client = httpx.Client(timeout=900)  # Long timeout for complex operations
        
        # Read the substrate SQL
        with open('/home/runner/work/cli-anything-biddeed/cli-anything-biddeed/duval_gi_substrate_build.sql', 'r') as f:
            sql_script = f.read()
        
        print("🔧 Executing Duval G+I substrate build...")
        print("Creating: zoning_districts, zone_standards, parcel_zones, permitted_uses")
        
        # Execute the SQL script
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"query": sql_script}
        )
        
        if r.status_code == 200:
            result = r.json()
            print("✅ Duval G+I substrate SQL executed successfully")
            
            # Parse results for verification  
            if result and len(result) > 0:
                for row in result:
                    if isinstance(row, dict):
                        print(f"📊 Build result: {row}")
            
            return True
        else:
            print(f"❌ Failed to execute substrate build: {r.status_code}")
            print(f"Error: {r.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error executing substrate build: {e}")
        return False

def verify_infrastructure_created():
    """Verify that zoning infrastructure was properly created"""
    try:
        client = httpx.Client(timeout=60)
        
        # Check what was created
        infrastructure_query = """
        SELECT 
            'DUVAL ZONING INFRASTRUCTURE' as component,
            (SELECT COUNT(*) FROM zoning_districts zd 
             JOIN jurisdictions j ON zd.jurisdiction_id = j.id 
             WHERE j.county = 'Duval') as zoning_districts_count,
            (SELECT COUNT(*) FROM zone_standards zs 
             JOIN zoning_districts zd ON zs.zoning_district_id = zd.id
             JOIN jurisdictions j ON zd.jurisdiction_id = j.id 
             WHERE j.county = 'Duval') as zone_standards_count,
            (SELECT COUNT(*) FROM parcel_zones pz 
             JOIN jurisdictions j ON pz.jurisdiction_id = j.id 
             WHERE j.county = 'Duval') as parcels_zoned_count,
            (SELECT COUNT(*) FROM permitted_uses pu 
             JOIN zoning_districts zd ON pu.zoning_district_id = zd.id
             JOIN jurisdictions j ON zd.jurisdiction_id = j.id 
             WHERE j.county = 'Duval') as permitted_uses_count
        """
        
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"query": infrastructure_query}
        )
        
        if r.status_code == 200:
            result = r.json()
            if result and len(result) > 0:
                row = result[0]
                districts = row.get('zoning_districts_count', 0)
                standards = row.get('zone_standards_count', 0)
                parcels = row.get('parcels_zoned_count', 0)
                uses = row.get('permitted_uses_count', 0)
                
                print(f"\n📊 DUVAL ZONING INFRASTRUCTURE VERIFICATION:")
                print(f"  Zoning districts created: {districts}")
                print(f"  Zone standards created: {standards}")
                print(f"  Parcels zoned: {parcels:,}")
                print(f"  Permitted uses created: {uses}")
                
                if districts > 0 and standards > 0 and parcels > 0:
                    print("✅ Infrastructure creation successful")
                    return True
                else:
                    print("❌ Infrastructure creation incomplete")
                    return False
            else:
                print("❌ No verification data returned")
                return False
        else:
            print(f"❌ Verification query failed: {r.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying infrastructure: {e}")
        return False

def check_gi_metrics_now_measurable():
    """Check if G/I metrics are now measurable (not NULL)"""
    try:
        client = httpx.Client(timeout=60)
        
        # Check via the zoning view
        view_query = """
        SELECT 
            county_slug,
            density_coverage_pct,
            far_coverage_pct,
            parking_coverage_pct,
            total_districts,
            districts_with_standards
        FROM v_zoning_gold_standard_kpi_v3 
        WHERE county_slug = 'duval'
        """
        
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"query": view_query}
        )
        
        if r.status_code == 200:
            result = r.json()
            if result and len(result) > 0:
                row = result[0]
                density = row.get('density_coverage_pct')
                far = row.get('far_coverage_pct')
                parking = row.get('parking_coverage_pct')
                
                print(f"\n📊 DUVAL G METRIC COMPONENTS (now measurable):")
                print(f"  Density coverage: {density:.1f}%" if density else "  Density coverage: NULL")
                print(f"  FAR coverage: {far:.1f}%" if far else "  FAR coverage: NULL")
                print(f"  Parking coverage: {parking:.1f}%" if parking else "  Parking coverage: NULL")
                
                if density is not None and far is not None and parking is not None:
                    g_metric = min(density, far, parking)
                    print(f"  G metric: {g_metric:.1f}%")
                    return g_metric
                else:
                    print("  G metric: Still NULL (infrastructure incomplete)")
                    return None
            else:
                print("❌ No G metric data available")
                return None
        else:
            print(f"❌ G metric query failed: {r.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error checking G metrics: {e}")
        return None

def main():
    """Execute Duval G+I substrate build and verify infrastructure"""
    print("🎯 SHARD-28 DUVAL G+I SUBSTRATE EXECUTOR")
    print("=" * 80)
    print("Target: Enable G/I measurement for Duval (currently NULL)")
    print("Method: Create zoning infrastructure for Jacksonville Ch.656")
    print()
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable required")
        return False
    
    # Check jurisdictions exist
    if not check_duval_jurisdictions():
        print("❌ Duval jurisdictions not found - cannot proceed")
        return False
    
    # Get baseline G/I metrics (should be NULL)
    before_metrics = get_current_gi_metrics()
    print(f"📊 BEFORE: Duval G = {before_metrics.get('G', {}).get('metric', 'NULL')}")
    print(f"📊 BEFORE: Duval I = {before_metrics.get('I', {}).get('metric', 'NULL')}")
    
    # Execute the substrate build
    success = execute_gi_substrate()
    if not success:
        print("❌ Failed to execute substrate build")
        return False
    
    # Verify infrastructure was created
    verify_success = verify_infrastructure_created()
    if not verify_success:
        print("⚠️ Infrastructure verification failed")
    
    # Check if G/I are now measurable
    g_metric = check_gi_metrics_now_measurable()
    
    # Get updated G/I metrics
    after_metrics = get_current_gi_metrics()
    print(f"\n📊 AFTER: Duval G = {after_metrics.get('G', {}).get('metric', 'NULL')}")
    print(f"📊 AFTER: Duval I = {after_metrics.get('I', {}).get('metric', 'NULL')}")
    
    g_after = after_metrics.get('G', {}).get('metric')
    i_after = after_metrics.get('I', {}).get('metric')
    
    if g_after is not None or i_after is not None:
        print("🎉 G/I metrics are now MEASURABLE (no longer NULL)")
        
        if g_after and g_after >= 95:
            print("🎉 Duval G now PASSES the 95% threshold!")
        if i_after and i_after >= 95:
            print("🎉 Duval I now PASSES the 95% threshold!")
    else:
        print("⚠️ G/I metrics still NULL - may need additional setup")
    
    print(f"\n{'='*80}")
    print("📝 DUVAL G+I SUBSTRATE BUILD COMPLETE")
    print(f"{'='*80}")
    
    return success

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ Duval G+I substrate build completed with errors")
        sys.exit(1)
    else:
        print("\n✅ Duval G+I substrate build executed successfully")
        print("\n### SQL VERIFICATION")
        print("-- Verify G/I metrics are now measurable:")
        print("SELECT public.pencil_dod_evaluate_county('duval');")
        print("SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county_slug = 'duval';")
        print(f"-- Timestamp: {datetime.utcnow().isoformat()}Z")
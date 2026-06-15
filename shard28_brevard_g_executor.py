#!/usr/bin/env python3
"""
SHARD-28 Brevard G Hit List Executor
Purpose: Execute brevard_g_hitlist.sql to move G from 48.9% (FAR binding) to 95%
Target: Zone standards backfill for ~15 priority districts with ordinance values
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

def get_current_g_metric():
    """Get current Brevard G metric before improvement"""
    try:
        client = httpx.Client(timeout=60)
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": "brevard"}
        )
        
        if r.status_code == 200:
            result = r.json()
            for letter_data in result:
                if letter_data.get('letter') == 'G':
                    return letter_data.get('metric'), letter_data.get('pass')
        return None, False
        
    except Exception as e:
        print(f"❌ Error getting G metric: {e}")
        return None, False

def execute_g_hitlist():
    """Execute the Brevard G hitlist SQL script"""
    try:
        client = httpx.Client(timeout=600)  # Long timeout for complex query
        
        # Read the G hitlist SQL
        with open('/home/runner/work/cli-anything-biddeed/cli-anything-biddeed/brevard_g_hitlist.sql', 'r') as f:
            sql_script = f.read()
        
        print("🔧 Executing Brevard G hitlist SQL...")
        print("Target districts: R-1AAA Melbourne (53K), RU-2-15 Melbourne (5.6K), R-3 Titusville (2.5K)")
        
        # Execute the SQL script
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"query": sql_script}
        )
        
        if r.status_code == 200:
            result = r.json()
            print("✅ Brevard G hitlist SQL executed successfully")
            
            # Parse results for verification
            if result and len(result) > 0:
                for row in result:
                    if isinstance(row, dict):
                        print(f"📊 Result: {row}")
            
            return True
        else:
            print(f"❌ Failed to execute G hitlist: {r.status_code}")
            print(f"Error: {r.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error executing G hitlist: {e}")
        return False

def verify_zone_standards_improvement():
    """Verify that zone_standards were properly inserted"""
    try:
        client = httpx.Client(timeout=60)
        
        # Check zone standards counts by district
        verification_query = """
        SELECT 
            'BREVARD ZONE STANDARDS VERIFICATION' as check_type,
            j.name as jurisdiction,
            zd.code as zone_code,
            COUNT(pz.parcel_id) as parcels_in_zone,
            COUNT(CASE WHEN zs.standard_type = 'max_far' THEN 1 END) as has_far,
            COUNT(CASE WHEN zs.standard_type = 'max_density_du_acre' THEN 1 END) as has_density,
            COUNT(CASE WHEN zs.standard_type = 'parking_per_1000sf' THEN 1 END) as has_parking,
            MAX(CASE WHEN zs.standard_type = 'max_far' THEN zs.value END) as far_value,
            MAX(CASE WHEN zs.standard_type = 'max_density_du_acre' THEN zs.value END) as density_value
        FROM zoning_districts zd
        JOIN jurisdictions j ON zd.jurisdiction_id = j.id
        LEFT JOIN parcel_zones pz ON zd.id = pz.zoning_district_id
        LEFT JOIN zone_standards zs ON zd.id = zs.zoning_district_id
        WHERE j.county = 'Brevard'
            AND zd.code IN ('RU-2-15', 'R-3', 'C-1', 'R-1AAA', 'R-1A', 'R-1B')
        GROUP BY j.name, zd.code, zd.id
        ORDER BY COUNT(pz.parcel_id) DESC
        """
        
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"query": verification_query}
        )
        
        if r.status_code == 200:
            result = r.json()
            print("\n📊 ZONE STANDARDS VERIFICATION:")
            
            total_parcels_with_standards = 0
            for row in result:
                jurisdiction = row.get('jurisdiction', 'Unknown')
                zone_code = row.get('zone_code', 'Unknown') 
                parcels = row.get('parcels_in_zone', 0)
                has_far = row.get('has_far', 0)
                has_density = row.get('has_density', 0)
                far_val = row.get('far_value')
                density_val = row.get('density_value')
                
                if has_far > 0 and has_density > 0:
                    total_parcels_with_standards += parcels
                    print(f"  ✅ {jurisdiction} {zone_code}: {parcels:,} parcels, FAR={far_val}, density={density_val}")
                else:
                    print(f"  ❌ {jurisdiction} {zone_code}: {parcels:,} parcels, missing standards")
            
            print(f"\n📈 Total parcels with complete standards: {total_parcels_with_standards:,}")
            return True
            
        else:
            print(f"❌ Verification query failed: {r.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying standards: {e}")
        return False

def check_g_metric_via_view():
    """Check G metric via the zoning gold standard view"""
    try:
        client = httpx.Client(timeout=60)
        
        view_query = """
        SELECT * FROM v_zoning_gold_standard_kpi_v3 
        WHERE county_slug = 'brevard'
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
                density_pct = row.get('density_coverage_pct')
                far_pct = row.get('far_coverage_pct')
                parking_pct = row.get('parking_coverage_pct')
                
                print(f"\n📊 BREVARD G METRIC COMPONENTS:")
                print(f"  Density coverage: {density_pct:.1f}%")
                print(f"  FAR coverage: {far_pct:.1f}%") 
                print(f"  Parking coverage: {parking_pct:.1f}%")
                print(f"  G metric (min): {min(density_pct or 0, far_pct or 0, parking_pct or 0):.1f}%")
                
                return min(density_pct or 0, far_pct or 0, parking_pct or 0)
            else:
                print("❌ No data returned from zoning view")
                return 0
        else:
            print(f"❌ View query failed: {r.status_code}")
            return 0
            
    except Exception as e:
        print(f"❌ Error checking G metric view: {e}")
        return 0

def main():
    """Execute Brevard G hit list and verify improvement"""
    print("🎯 SHARD-28 BREVARD G HIT LIST EXECUTOR")
    print("=" * 80)
    print("Target: Move Brevard G from 48.9% (FAR binding) to 95%+")
    print("Method: Zone standards backfill for priority districts")
    print()
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable required")
        return False
    
    # Get baseline G metric
    before_metric, before_pass = get_current_g_metric()
    if before_metric is not None:
        print(f"📊 BEFORE: Brevard G = {before_metric:.1f}% ({'PASS' if before_pass else 'FAIL'})")
    else:
        print("⚠️ Could not get baseline G metric")
    
    # Execute the G hitlist SQL
    success = execute_g_hitlist()
    if not success:
        print("❌ Failed to execute G hitlist")
        return False
    
    # Verify zone standards were inserted
    verify_success = verify_zone_standards_improvement()
    if not verify_success:
        print("⚠️ Could not verify zone standards insertion")
    
    # Check G metric improvement via view
    view_metric = check_g_metric_via_view()
    
    # Get updated G metric
    after_metric, after_pass = get_current_g_metric()
    if after_metric is not None:
        improvement = (after_metric or 0) - (before_metric or 0)
        print(f"\n📊 AFTER: Brevard G = {after_metric:.1f}% ({'PASS' if after_pass else 'FAIL'})")
        print(f"📈 Improvement: {improvement:+.1f} percentage points")
        
        if after_pass:
            print("🎉 Brevard G now PASSES the 95% threshold!")
        elif improvement > 5:
            print("✅ Significant improvement achieved")
        else:
            print("⚠️ Limited improvement - may need additional district coverage")
    else:
        print("❌ Could not get updated G metric")
    
    print(f"\n{'='*80}")
    print("📝 BREVARD G HIT LIST COMPLETE")
    print(f"{'='*80}")
    
    return success

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ Brevard G hit list completed with errors")
        sys.exit(1)
    else:
        print("\n✅ Brevard G hit list executed successfully")
        print("\n### SQL VERIFICATION")
        print("-- Verify G metric improvement:")
        print("SELECT public.pencil_dod_evaluate_county('brevard');")
        print("SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county_slug = 'brevard';")
        print(f"-- Timestamp: {datetime.utcnow().isoformat()}Z")
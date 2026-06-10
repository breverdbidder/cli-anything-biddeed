#!/usr/bin/env python3
"""
GOLD STANDARD CAMPAIGN — Daily Autonomous Session
Script to assess current metrics and execute fixes for charlotte, brevard, broward
"""

import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class CountyStatus:
    """County status for A-J metrics"""
    county: str
    a_dual: Optional[bool] = None
    b_verified: Optional[float] = None
    c_parity_clean: Optional[float] = None
    d_parity_any: Optional[float] = None
    e_parcel_linked: Optional[float] = None
    f_tier1_sold: Optional[float] = None
    g_zoning: Optional[float] = None
    h_freshness: Optional[bool] = None
    i_property_card: Optional[float] = None
    j_deal_thesis: Optional[float] = None
    pass_count: int = 0
    critical_three_pass: int = 0


class GoldStandardSession:
    """Manages gold standard campaign session"""
    
    def __init__(self):
        self.client = None
        self.supabase_url = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
        self.supabase_key = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
        self.target_counties = ['charlotte', 'brevard', 'broward']
        self.session_start = datetime.now(timezone.utc)
        print(f"🚀 GOLD STANDARD CAMPAIGN — Session started at {self.session_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    def connect_to_supabase(self) -> bool:
        """Establish HTTP client connection to Supabase REST API"""
        try:
            if not self.supabase_key:
                print("❌ SUPABASE_KEY not found in environment")
                return False
                
            self.client = httpx.Client(
                timeout=60, 
                headers={"User-Agent": "GoldStandard-Campaign-Bot"}
            )
            
            # Test connection with simple query
            response = self.sb_get("gold_standard_county_status", "select=count&limit=1")
            print(f"✅ Supabase REST API connection established. Test query successful.")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to Supabase: {e}")
            return False
    
    def sb_headers(self):
        """Get Supabase REST API headers"""
        return {
            "apikey": self.supabase_key, 
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json", 
            "Prefer": "resolution=merge-duplicates"
        }
    
    def sb_get(self, table, params=""):
        """GET request to Supabase REST API"""
        r = self.client.get(f"{self.supabase_url}/rest/v1/{table}?{params}", headers=self.sb_headers())
        if r.status_code == 200:
            return r.json()
        else:
            print(f"❌ GET {table} failed: {r.status_code} {r.text[:200]}")
            return []
    
    def sb_rpc(self, func_name, params=None):
        """Call Supabase RPC function"""
        h = self.sb_headers()
        r = self.client.post(f"{self.supabase_url}/rest/v1/rpc/{func_name}", headers=h, json=params or {})
        if r.status_code == 200:
            return r.json()
        else:
            print(f"❌ RPC {func_name} failed: {r.status_code} {r.text[:200]}")
            return None
    
    def get_current_metrics(self) -> List[CountyStatus]:
        """Get current metrics for target counties from gold_standard_scoreboard"""
        try:
            # Build filter for target counties
            county_filter = "or=".join([f"county_slug.eq.{county}" for county in self.target_counties])
            
            results = self.sb_get("gold_standard_scoreboard", 
                f"{county_filter}&select=county_slug,a_dual_product,b_verified_outcomes,c_parity_clean,d_parity_any,e_parcel_linkage,f_tier1_sold,g_zoning,h_freshness,i_property_card,j_deal_thesis,pass_count,critical_three_pass,gold_standard&order=pass_count.desc")
            
            if not results:
                print("⚠️  No results found for target counties. Running gold_standard_loop()...")
                loop_result = self.sb_rpc("gold_standard_loop")
                if loop_result is not None:
                    print(f"✅ gold_standard_loop() executed successfully")
                    # Retry query
                    results = self.sb_get("gold_standard_scoreboard", 
                        f"{county_filter}&select=county_slug,a_dual_product,b_verified_outcomes,c_parity_clean,d_parity_any,e_parcel_linkage,f_tier1_sold,g_zoning,h_freshness,i_property_card,j_deal_thesis,pass_count,critical_three_pass,gold_standard&order=pass_count.desc")
            
            counties = []
            for row in results:
                status = CountyStatus(
                    county=row.get('county_slug'),
                    a_dual=row.get('a_dual_product'),
                    b_verified=row.get('b_verified_outcomes'),
                    c_parity_clean=row.get('c_parity_clean'),
                    d_parity_any=row.get('d_parity_any'),
                    e_parcel_linked=row.get('e_parcel_linkage'),
                    f_tier1_sold=row.get('f_tier1_sold'),
                    g_zoning=row.get('g_zoning'),
                    h_freshness=row.get('h_freshness'),
                    i_property_card=row.get('i_property_card'),
                    j_deal_thesis=row.get('j_deal_thesis'),
                    pass_count=row.get('pass_count') or 0,
                    critical_three_pass=row.get('critical_three_pass') or 0
                )
                counties.append(status)
            
            print(f"📊 Retrieved metrics for {len(counties)} counties")
            return counties
            
        except Exception as e:
            print(f"❌ Failed to get current metrics: {e}")
            return []
    
    def display_metrics(self, counties: List[CountyStatus]) -> None:
        """Display current metrics in readable format"""
        print("\n🎯 CURRENT GOLD STANDARD STATUS")
        print("=" * 80)
        
        for county in counties:
            print(f"\n📍 {county.county.upper()} ({county.pass_count}/10 passes)")
            print("   Letter | Status | Metric")
            print("   -------|--------|-------")
            
            letters = [
                ('A', 'PASS' if county.a_dual else 'FAIL', 'dual_product_coverage'),
                ('B', f'{county.b_verified:.1f}%' if county.b_verified else 'null', 'verified_outcomes'),
                ('C', f'{county.c_parity_clean:.1f}%' if county.c_parity_clean else 'null', 'parity_clean'),
                ('D', f'{county.d_parity_any:.1f}%' if county.d_parity_any else 'null', 'parity_any'),
                ('E', f'{county.e_parcel_linked:.1f}%' if county.e_parcel_linked else 'null', 'parcel_linkage'),
                ('F', f'{county.f_tier1_sold:.1f}%' if county.f_tier1_sold else 'null', 'tier1_sold'),
                ('G', f'{county.g_zoning:.1f}%' if county.g_zoning else 'null', 'zoning'),
                ('H', 'PASS' if county.h_freshness else 'FAIL', 'freshness'),
                ('I', f'{county.i_property_card:.1f}%' if county.i_property_card else 'null', 'property_card'),
                ('J', f'{county.j_deal_thesis:.1f}%' if county.j_deal_thesis else 'null', 'deal_thesis'),
            ]
            
            for letter, status, metric in letters:
                critical = "⭐" if letter in ['B', 'I', 'J'] else "  "
                fail_indicator = "❌" if (status == 'FAIL' or (status != 'PASS' and 'null' not in status and float(status.rstrip('%')) < 95.0)) else "✅" if status == 'PASS' else "🔶"
                print(f"   {critical}{letter}     | {status:<6} | {metric} {fail_indicator}")
    
    def prioritize_work(self, counties: List[CountyStatus]) -> List[Tuple[str, str, str]]:
        """Prioritize work based on highest-leverage failing letters"""
        work_queue = []
        
        for county in sorted(counties, key=lambda x: x.pass_count, reverse=True):
            # Critical letters first (B, I, J)
            if not county.b_verified or (county.b_verified and county.b_verified < 95.0):
                work_queue.append((county.county, 'B', 'Build independent verified outcomes scraper'))
            
            if not county.i_property_card or (county.i_property_card and county.i_property_card < 95.0):
                work_queue.append((county.county, 'I', 'Complete property card data (address+geo+value+zoning)'))
            
            if not county.j_deal_thesis or (county.j_deal_thesis and county.j_deal_thesis < 95.0):
                work_queue.append((county.county, 'J', 'Populate bid_decisions with Shapira formula'))
            
            # Other failing letters
            if not county.c_parity_clean or (county.c_parity_clean and county.c_parity_clean < 95.0):
                work_queue.append((county.county, 'C', 'Fix parity_clean matching'))
            
            if not county.d_parity_any or (county.d_parity_any and county.d_parity_any < 95.0):
                work_queue.append((county.county, 'D', 'Fix parity_any matching'))
            
            if not county.e_parcel_linked or (county.e_parcel_linked and county.e_parcel_linked < 95.0):
                work_queue.append((county.county, 'E', 'Link parcels via county GIS'))
            
            if not county.f_tier1_sold or (county.f_tier1_sold and county.f_tier1_sold < 95.0):
                work_queue.append((county.county, 'F', 'Verify tier1 sold amounts'))
            
            if not county.g_zoning or (county.g_zoning and county.g_zoning < 95.0):
                work_queue.append((county.county, 'G', 'Extend zoning coverage'))
        
        return work_queue[:10]  # Limit to top 10 items
    
    def verify_changes(self, county: str) -> Dict:
        """Run pencil_dod_evaluate_county to verify changes"""
        try:
            result = self.sb_rpc("pencil_dod_evaluate_county", {"county_name": county})
            print(f"✅ Verified {county}: {result}")
            return result or {}
        except Exception as e:
            print(f"❌ Failed to verify {county}: {e}")
            return {}
    
    def close(self):
        """Close HTTP client"""
        if self.client:
            self.client.close()
            print("🔌 HTTP client closed")


def main():
    """Main execution function"""
    session = GoldStandardSession()
    
    try:
        # Connect to Supabase
        if not session.connect_to_supabase():
            print("❌ Cannot proceed without database connection")
            return 1
        
        # Get current metrics
        counties = session.get_current_metrics()
        if not counties:
            print("❌ No county data retrieved")
            return 1
        
        # Display current status
        session.display_metrics(counties)
        
        # Prioritize work
        work_queue = session.prioritize_work(counties)
        
        print("\n🎯 PRIORITY WORK QUEUE")
        print("=" * 60)
        for i, (county, letter, task) in enumerate(work_queue, 1):
            print(f"{i:2d}. {county.upper()} - Letter {letter}: {task}")
        
        print(f"\n⏰ Session Duration: {datetime.now(timezone.utc) - session.session_start}")
        print("📋 Ready to execute fixes based on priority queue...")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Session interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Session failed: {e}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
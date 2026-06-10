#!/usr/bin/env python3
"""
Quick check of Gold Standard status for SHARD-2 counties.
"""

import os
import psycopg2
import psycopg2.extras
from datetime import datetime

# Database connection using the patterns from existing scripts
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_DB_PASSWORD = os.environ.get("SUPABASE_DB_PASSWORD", "BiKvLwWTdS0PwulM")
DB_POOLER = os.environ.get("DB_POOLER", "aws-0-us-west-2.pooler.supabase.com")

def get_db_connection():
    """Get postgres connection to Supabase."""
    conn_string = f"postgresql://postgres.mocerqjnksmhcjzxrewo:{SUPABASE_DB_PASSWORD}@{DB_POOLER}:6543/postgres"
    return psycopg2.connect(conn_string)

def main():
    """Check current gold standard status for duval, manatee, pinellas."""
    target_counties = ['duval', 'manatee', 'pinellas']
    
    print("=== GOLD STANDARD SHARD-2 STATUS CHECK ===")
    print(f"Time: {datetime.now()}")
    print()
    
    with get_db_connection() as conn:
        conn.autocommit = True
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Set statement timeout to avoid timeouts
            cur.execute("SET statement_timeout = 0;")
            
            # Check current scoreboard
            cur.execute("""
                SELECT county_slug, pass_count, gold_standard, critical_three_pass,
                       a_dual_product, b_verified_outcomes, c_parity_clean, d_parity_any,
                       e_parcel_linkage, f_tier1_sold, g_zoning, h_freshness,
                       i_property_card, j_deal_thesis
                FROM gold_standard_scoreboard
                WHERE county_slug IN %s
                ORDER BY county_slug;
            """, (tuple(target_counties),))
            
            rows = cur.fetchall()
            
            for row in rows:
                print(f"=== {row['county_slug'].upper()} ===")
                print(f"  Pass count: {row['pass_count']}/10")
                print(f"  Gold standard: {row['gold_standard']}")
                print(f"  Critical three: {row['critical_three_pass']}")
                print(f"  A (dual product): {row['a_dual_product']}")
                print(f"  B (verified outcomes): {row['b_verified_outcomes']} ⭐")
                print(f"  C (parity clean): {row['c_parity_clean']}")
                print(f"  D (parity any): {row['d_parity_any']}")
                print(f"  E (parcel linkage): {row['e_parcel_linkage']}")
                print(f"  F (tier1 sold): {row['f_tier1_sold']}")
                print(f"  G (zoning): {row['g_zoning']}")
                print(f"  H (freshness): {row['h_freshness']}")
                print(f"  I (property card): {row['i_property_card']} ⭐")
                print(f"  J (deal thesis): {row['j_deal_thesis']} ⭐")
                print()
            
            # Check latest loop run
            cur.execute("""
                SELECT loop_run_id, created_at, total_counties
                FROM gold_standard_loop_status
                ORDER BY loop_run_id DESC
                LIMIT 1;
            """)
            
            loop_status = cur.fetchone()
            if loop_status:
                print(f"Latest loop run: {loop_status['loop_run_id']} at {loop_status['created_at']}")
                print(f"Counties evaluated: {loop_status['total_counties']}")
            
    print("=== STATUS CHECK COMPLETE ===")

if __name__ == "__main__":
    main()
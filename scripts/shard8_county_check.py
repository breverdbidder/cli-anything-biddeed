#!/usr/bin/env python3
"""
SHARD-8 County Metrics Checker
Check current county metrics for assigned counties: hillsborough, bay, nassau, desoto, monroe
"""
import os
import sys
import psycopg2
import json
from datetime import datetime

# Database connection settings  
DB_PASSWORD = 'BiKvLwWTdS0PwulM'
DB_URL = 'aws-0-us-west-2.pooler.supabase.com'
DB_NAME = 'postgres'
DB_USER = 'postgres.mocerqjnksmhcjzxrewo'

# SHARD-8 assigned counties
SHARD_COUNTIES = ['hillsborough', 'bay', 'nassau', 'desoto', 'monroe']

def connect_db():
    """Connect to Supabase database"""
    try:
        conn = psycopg2.connect(
            host=DB_URL,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=6543
        )
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

def check_county_metrics(conn, county):
    """Check metrics for a specific county using pencil_dod_evaluate_county"""
    try:
        cur = conn.cursor()
        cur.execute('SET statement_timeout = 0;')
        cur.execute('SELECT public.pencil_dod_evaluate_county(%s);', (county,))
        result = cur.fetchone()[0]
        cur.close()
        return result
    except Exception as e:
        print(f"Error checking {county}: {e}")
        return None

def main():
    print("=" * 60)
    print("SHARD-8 COUNTY METRICS CHECK")
    print("Counties: hillsborough, bay, nassau, desoto, monroe")
    print("=" * 60)
    
    conn = connect_db()
    if not conn:
        sys.exit(1)
    
    all_metrics = {}
    
    for county in SHARD_COUNTIES:
        print(f"\n=== {county.upper()} COUNTY METRICS ===")
        metrics = check_county_metrics(conn, county)
        if metrics:
            print(json.dumps(metrics, indent=2))
            all_metrics[county] = metrics
        else:
            print(f"Failed to get metrics for {county}")
    
    conn.close()
    
    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    
    for county, metrics in all_metrics.items():
        if metrics:
            score = metrics.get('score', 0)
            print(f"{county:12} : {score}/10")
    
    return all_metrics

if __name__ == "__main__":
    main()
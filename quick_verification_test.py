#!/usr/bin/env python3
"""
Quick test of database connectivity and current status for brevard/duval
"""
import os
import sys
import subprocess
import json

def install_requirements():
    """Install required packages"""
    try:
        import httpx
        print("✅ httpx already available")
    except ImportError:
        print("📦 Installing httpx...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx>=0.24.0"])
        import httpx

def test_basic_connection():
    """Test basic connection without auth"""
    try:
        import httpx
        client = httpx.Client(timeout=30)
        
        # Test basic connection to public endpoint
        r = client.get("https://mocerqjnksmhcjzxrewo.supabase.co/rest/v1/", 
                      headers={"Content-Type": "application/json"})
        
        print(f"Connection test: {r.status_code}")
        if r.status_code == 200:
            print("✅ Basic connection successful")
            return True
        else:
            print(f"⚠️  Connection returned: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def show_session_context():
    """Show what we know about the current session"""
    print("=== SHARD 24 SESSION CONTEXT ===")
    print("Counties: brevard, duval")
    print("Current Status (from briefing):")
    print("  brevard: 2/10 (A,H pass)")
    print("  duval: 2/10 (A,H pass)")
    print("")
    print("Priority Order:")
    print("1. Brevard C/D ROOT CAUSE (PropertyOnion coverage → clerk/official records litmus)")
    print("2. J GENERATOR (bid_decisions per evaluator contract)")
    print("3. Duval G+I SUBSTRATE BUILD (zoning_districts + parcel_zones)")
    print("4. B RECONCILIATION (brevard 134.1%, duval 110.2% anomalies)")
    print("")
    print("Ship-to-Main Mandate: Work directly on main, no PRs")
    print("ULTRALOOP Protocol: Fan-out subagents + adversarial refuters")

def main():
    print("=== QUICK VERIFICATION TEST ===")
    
    # Install requirements
    install_requirements()
    
    # Test connection
    test_basic_connection()
    
    # Show context
    show_session_context()
    
    print("\n🚀 Proceeding with Gold Standard work...")

if __name__ == "__main__":
    main()
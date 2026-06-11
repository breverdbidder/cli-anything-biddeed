#!/usr/bin/env python3
"""
Quick database connection test for Gold Standard processing
Tests Supabase connection and basic query functionality
"""
import os
import httpx
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration from CLAUDE.md
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def test_connection():
    """Test basic Supabase connection"""
    if not SUPABASE_KEY:
        logger.error("❌ SUPABASE_KEY not set in environment")
        return False
        
    base_url = f"{SUPABASE_URL}/rest/v1"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            # Test basic table access
            response = client.get(f"{base_url}/fl_counties", headers=headers, params={"limit": "1"})
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Database connection successful - found {len(data)} record(s)")
                return True
            else:
                logger.error(f"❌ Database query failed: {response.status_code} - {response.text[:200]}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    exit(0 if success else 1)
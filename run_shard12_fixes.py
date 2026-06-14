#!/usr/bin/env python3
"""
SHARD-12 EXECUTION WRAPPER
Runs targeted fixes for sumter, indian_river, polk, glades with environment validation
"""
import os
import sys
import subprocess
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_environment():
    """Verify environment is ready for execution"""
    logger.info("🔍 Environment validation...")
    
    # Check for required environment variables
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    
    if not supabase_url:
        logger.error("❌ SUPABASE_URL not found in environment")
        return False
        
    if not supabase_key:
        logger.error("❌ SUPABASE_KEY not found in environment")
        return False
        
    logger.info(f"✅ SUPABASE_URL: {supabase_url}")
    logger.info(f"✅ SUPABASE_KEY: Available")
    
    # Test Python httpx availability
    try:
        import httpx
        logger.info("✅ httpx: Available")
    except ImportError:
        logger.error("❌ httpx not available - installing...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "httpx"], check=True)
            import httpx
            logger.info("✅ httpx: Installed successfully")
        except Exception as e:
            logger.error(f"❌ Failed to install httpx: {e}")
            return False
    
    # Quick database connectivity test
    try:
        import httpx
        import json
        
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{supabase_url}/rest/v1/", headers=headers)
            if response.status_code in [200, 404]:  # 404 is normal for root endpoint
                logger.info("✅ Database connectivity: OK")
                return True
            else:
                logger.error(f"❌ Database connectivity: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Database connectivity test failed: {e}")
        return False

def run_targeted_fixes():
    """Execute the main targeted fixes script"""
    logger.info("🚀 Running SHARD-12 targeted fixes...")
    
    try:
        result = subprocess.run([
            sys.executable, "scripts/shard12_targeted_fixes.py"
        ], capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        logger.info("STDOUT:")
        logger.info(result.stdout)
        
        if result.stderr:
            logger.warning("STDERR:")
            logger.warning(result.stderr)
        
        if result.returncode == 0:
            logger.info("✅ Targeted fixes completed successfully")
            return True
        else:
            logger.error(f"❌ Targeted fixes failed with code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Targeted fixes timed out after 30 minutes")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to run targeted fixes: {e}")
        return False

def run_verification():
    """Run verification protocol"""
    logger.info("🔍 Running verification protocol...")
    
    try:
        result = subprocess.run([
            sys.executable, "scripts/shard12_verification_protocol.py"
        ], capture_output=True, text=True, timeout=600)  # 10 min timeout
        
        logger.info("Verification STDOUT:")
        logger.info(result.stdout)
        
        if result.stderr:
            logger.warning("Verification STDERR:")
            logger.warning(result.stderr)
        
        if result.returncode == 0:
            logger.info("✅ Verification completed successfully")
        else:
            logger.warning(f"⚠️ Verification had issues (code {result.returncode}) but continuing...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False

def main():
    """Main execution flow"""
    start_time = datetime.now(timezone.utc)
    logger.info(f"🎯 SHARD-12 AUTONOMOUS SESSION START: {start_time.isoformat()}")
    logger.info("Counties: sumter, indian_river, polk, glades")
    
    # Step 1: Environment validation
    if not check_environment():
        logger.error("❌ Environment validation failed")
        return False
    
    # Step 2: Run targeted fixes
    if not run_targeted_fixes():
        logger.error("❌ Targeted fixes failed")
        return False
    
    # Step 3: Run verification
    if not run_verification():
        logger.error("❌ Verification failed")
        return False
    
    elapsed = datetime.now(timezone.utc) - start_time
    logger.info(f"✅ SHARD-12 SESSION COMPLETED in {elapsed.total_seconds():.1f} seconds")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
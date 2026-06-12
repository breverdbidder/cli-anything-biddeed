#!/usr/bin/env python3
"""
Gold Standard Run 17 - Brevard Acclaim CT Sweep
Ship-to-main autonomous execution

Targets: B+F metrics for brevard county
- B (verified outcomes): currently 136.1% anomaly - need independent source
- F (tier1 sold): currently 40.6% - need winning bid data

Uses existing acclaim_ct_sweep.py for courthouse records from AcclaimWeb
"""
import os
import sys
import subprocess
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("=== Gold Standard Run 17 - Brevard Acclaim CT Sweep ===")
    
    try:
        # Set environment for acclaim sweep
        env = os.environ.copy()
        
        # Get previous 6 months for thorough sweep 
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        
        start_month = f"{start_date.year}-{start_date.month:02d}"
        end_month = f"{end_date.year}-{end_date.month:02d}"
        
        logger.info(f"Running Acclaim CT sweep from {start_month} to {end_month}")
        
        # Run the acclaim_ct_sweep.py script with date range
        cmd = ["python3", "scripts/acclaim_ct_sweep.py", start_month, end_month]
        
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if result.returncode == 0:
            logger.info("✅ Brevard Acclaim CT sweep completed successfully")
            logger.info("Output:")
            print(result.stdout)
            
            # Log the results for verification
            lines = result.stdout.split('\n')
            total_written = 0
            for line in lines:
                if 'written=' in line:
                    try:
                        written = int(line.split('written=')[1])
                        total_written += written
                    except (ValueError, IndexError):
                        continue
            
            logger.info(f"Total records written: {total_written}")
            return True
            
        else:
            logger.error(f"❌ Brevard Acclaim CT sweep failed")
            logger.error("Error output:")
            print(result.stderr, file=sys.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Acclaim CT sweep timed out after 1 hour")
        return False
    except Exception as e:
        logger.error(f"❌ Error running Acclaim CT sweep: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
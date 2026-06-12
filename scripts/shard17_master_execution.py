#!/usr/bin/env python3
"""
SHARD-17 Master Execution Script
Orchestrates the complete Gold Standard campaign for charlotte, citrus, broward

EXECUTION SEQUENCE (based on dependency chain E->I->G, B independent, J independent):
1. Letter E: Parcel linkage (unblocks I)
2. Letter B: Verified outcomes (independent, high-value) 
3. Letter F: Tier1 promotion (follows from B)
4. Letters C/D: Parity matching (related fixes)
5. Letter J: Deal scoring (independent, requires parcel_id from E)
6. Verification: Run pencil_dod_evaluate_county for all counties
7. Final: Generate SQL verification evidence

Per SHIP-TO-MAIN mandate: commits directly to main, no PRs, immediate execution
Per WIRING MANDATE: each pipeline must be executed at least once in this session
"""
import os
import sys
import json
import asyncio
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, List

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TARGET_COUNTIES = ['charlotte', 'citrus', 'broward']

class SHARD17MasterExecution:
    """Master orchestrator for SHARD-17 Gold Standard campaign"""
    
    def __init__(self):
        self.session_start = datetime.now(timezone.utc)
        self.session_id = f"shard17_master_{int(self.session_start.timestamp())}"
        self.results = {
            'session_id': self.session_id,
            'start_time': self.session_start.isoformat(),
            'target_counties': TARGET_COUNTIES,
            'execution_sequence': [],
            'baseline_metrics': {},
            'final_metrics': {},
            'total_improvements': {},
            'errors': [],
            'wiring_receipts': []  # Evidence of pipeline execution
        }

    async def run_pipeline_script(self, script_name: str, description: str) -> Dict:
        """Execute a pipeline script and capture results"""
        logger.info(f"🔧 Executing: {script_name} - {description}")
        
        execution_start = datetime.now(timezone.utc)
        
        try:
            # Run the script
            result = subprocess.run(
                [sys.executable, f"scripts/{script_name}"],
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout per script
            )
            
            execution_time = (datetime.now(timezone.utc) - execution_start).total_seconds()
            
            # Capture execution receipt
            receipt = {
                'script': script_name,
                'description': description,
                'start_time': execution_start.isoformat(),
                'execution_time_seconds': execution_time,
                'return_code': result.returncode,
                'stdout_lines': len(result.stdout.splitlines()) if result.stdout else 0,
                'stderr_lines': len(result.stderr.splitlines()) if result.stderr else 0,
                'success': result.returncode == 0
            }
            
            # Log execution details
            if result.returncode == 0:
                logger.info(f"✅ {script_name} completed successfully in {execution_time:.1f}s")
                if result.stdout:
                    # Try to extract JSON results if present
                    try:
                        # Look for JSON in the output
                        lines = result.stdout.splitlines()
                        for line in lines:
                            if line.strip().startswith('{') and 'county' in line:
                                json_result = json.loads(line)
                                receipt['parsed_output'] = json_result
                                break
                    except:
                        pass
                    
                    # Log key output lines
                    stdout_lines = result.stdout.splitlines()
                    important_lines = [line for line in stdout_lines 
                                     if any(keyword in line.lower() for keyword in 
                                           ['✅', '❌', 'completed', 'error', 'improvement', 'fixed'])]
                    receipt['important_output'] = important_lines[:10]  # First 10 important lines
            else:
                logger.error(f"❌ {script_name} failed with return code {result.returncode}")
                if result.stderr:
                    receipt['error_output'] = result.stderr.splitlines()[:5]  # First 5 error lines
            
            self.results['wiring_receipts'].append(receipt)
            return receipt
            
        except subprocess.TimeoutExpired:
            logger.error(f"⏰ {script_name} timed out after 30 minutes")
            return {
                'script': script_name,
                'description': description,
                'error': 'timeout_after_30_minutes',
                'success': False
            }
        except Exception as e:
            logger.error(f"💥 {script_name} execution failed: {str(e)}")
            return {
                'script': script_name,
                'description': description,
                'error': str(e),
                'success': False
            }

    async def run_verification(self, phase: str = "baseline") -> Dict:
        """Run the verification protocol"""
        logger.info(f"🔍 Running verification protocol: {phase}")
        
        verification_receipt = await self.run_pipeline_script(
            "shard17_verification_protocol.py",
            f"Verification protocol ({phase})"
        )
        
        return verification_receipt

    async def execute_campaign(self) -> Dict:
        """Execute the complete SHARD-17 campaign"""
        logger.info("🚀 STARTING SHARD-17 MASTER EXECUTION")
        logger.info(f"Session ID: {self.session_id}")
        logger.info(f"Target Counties: {', '.join(TARGET_COUNTIES)}")
        logger.info(f"Session Start: {self.session_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # Phase 1: Baseline Verification
        logger.info("\n" + "="*60)
        logger.info("PHASE 1: BASELINE METRICS")
        logger.info("="*60)
        
        baseline_verification = await self.run_verification("baseline")
        self.results['baseline_metrics'] = baseline_verification
        
        # Phase 2: Execute pipelines in dependency order
        logger.info("\n" + "="*60)
        logger.info("PHASE 2: PIPELINE EXECUTION")
        logger.info("="*60)
        
        pipeline_sequence = [
            ("shard17_gold_standard_campaign.py", "Letters E, B, J - Primary fixes"),
            ("shard17_parity_matching.py", "Letters C, D - Parity matching fixes"),
            ("shard17_tier1_promotion.py", "Letter F - Tier1 amount promotion")
        ]
        
        for script_name, description in pipeline_sequence:
            receipt = await self.run_pipeline_script(script_name, description)
            self.results['execution_sequence'].append(receipt)
            
            # Short pause between pipelines
            await asyncio.sleep(2)
        
        # Phase 3: Final Verification
        logger.info("\n" + "="*60)
        logger.info("PHASE 3: FINAL VERIFICATION")
        logger.info("="*60)
        
        final_verification = await self.run_verification("final")
        self.results['final_metrics'] = final_verification
        
        # Phase 4: Results Analysis
        logger.info("\n" + "="*60)
        logger.info("PHASE 4: RESULTS ANALYSIS")
        logger.info("="*60)
        
        self.analyze_results()
        
        # Session completion
        self.results['end_time'] = datetime.now(timezone.utc).isoformat()
        self.results['total_duration_minutes'] = (
            datetime.now(timezone.utc) - self.session_start
        ).total_seconds() / 60
        
        self.generate_final_report()
        
        return self.results

    def analyze_results(self):
        """Analyze the campaign results"""
        logger.info("📊 Analyzing campaign results...")
        
        # Count successful executions
        successful_pipelines = [
            receipt for receipt in self.results['wiring_receipts']
            if receipt.get('success', False)
        ]
        
        failed_pipelines = [
            receipt for receipt in self.results['wiring_receipts']
            if not receipt.get('success', False)
        ]
        
        self.results['summary'] = {
            'total_pipelines': len(self.results['wiring_receipts']),
            'successful_pipelines': len(successful_pipelines),
            'failed_pipelines': len(failed_pipelines),
            'success_rate': len(successful_pipelines) / len(self.results['wiring_receipts']) * 100
        }
        
        logger.info(f"Pipeline success rate: {self.results['summary']['success_rate']:.1f}%")
        logger.info(f"Successful executions: {len(successful_pipelines)}")
        logger.info(f"Failed executions: {len(failed_pipelines)}")

    def generate_final_report(self):
        """Generate the final campaign report"""
        
        report_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Generate SQL verification block
        sql_verification = f"""
### SQL VERIFICATION

Timestamp: {report_timestamp}
Session ID: {self.session_id}

**SHARD-17 Master Execution Results:**
```json
{json.dumps({
    'session_summary': {
        'duration_minutes': self.results['total_duration_minutes'],
        'target_counties': TARGET_COUNTIES,
        'pipelines_executed': len(self.results['wiring_receipts']),
        'success_rate': self.results['summary']['success_rate']
    },
    'wiring_receipts': [
        {
            'script': r['script'],
            'success': r['success'],
            'execution_time': r.get('execution_time_seconds', 0)
        } for r in self.results['wiring_receipts']
    ]
}, indent=2)}
```

**Verification Queries:**
```sql
-- Set unlimited timeout for heavy queries
SET statement_timeout = 0;

-- Verify improvements for each SHARD-17 county
SELECT public.pencil_dod_evaluate_county('charlotte');
SELECT public.pencil_dod_evaluate_county('citrus');
SELECT public.pencil_dod_evaluate_county('broward');

-- Check pipeline execution evidence
SELECT COUNT(*) FROM multi_county_auctions WHERE county IN ('charlotte', 'citrus', 'broward') AND updated_at >= '{self.session_start.isoformat()}';
SELECT COUNT(*) FROM foreclosure_outcomes WHERE county_slug IN ('charlotte', 'citrus', 'broward') AND scraped_at >= '{self.session_start.isoformat()}';
SELECT COUNT(*) FROM tax_deed_outcomes WHERE county_slug IN ('charlotte', 'citrus', 'broward') AND scraped_at >= '{self.session_start.isoformat()}';
SELECT COUNT(*) FROM bid_decisions WHERE county IN ('charlotte', 'citrus', 'broward') AND decision_date >= '{self.session_start.isoformat()}';

-- Run Gold Standard loop
SELECT public.gold_standard_loop();
```

**Pipeline Execution Evidence:**
"""
        
        for receipt in self.results['wiring_receipts']:
            status = "✅ SUCCESS" if receipt.get('success') else "❌ FAILED"
            execution_time = receipt.get('execution_time_seconds', 0)
            sql_verification += f"""
- **{receipt.get('script', 'unknown')}**: {status} ({execution_time:.1f}s)
  - {receipt.get('description', 'No description')}"""
        
        # Print the verification block
        logger.info("\n" + "="*80)
        logger.info("SQL VERIFICATION BLOCK FOR ISSUE COMMENT:")
        logger.info("="*80)
        print(sql_verification)
        
        # Final summary
        logger.info("\n" + "="*80)
        logger.info("SHARD-17 MASTER EXECUTION COMPLETION REPORT")
        logger.info("="*80)
        logger.info(f"🕒 Total Duration: {self.results['total_duration_minutes']:.1f} minutes")
        logger.info(f"🎯 Counties: {', '.join(TARGET_COUNTIES)}")
        logger.info(f"🔧 Pipelines Executed: {len(self.results['wiring_receipts'])}")
        logger.info(f"✅ Success Rate: {self.results['summary']['success_rate']:.1f}%")
        logger.info(f"📊 Evidence: {len(self.results['wiring_receipts'])} execution receipts")
        
        if self.results['summary']['success_rate'] >= 80:
            logger.info("🏆 CAMPAIGN STATUS: SUCCESS")
        else:
            logger.info("⚠️ CAMPAIGN STATUS: PARTIAL SUCCESS")

async def main():
    """Main execution function"""
    executor = SHARD17MasterExecution()
    
    try:
        results = await executor.execute_campaign()
        
        # Determine exit code based on success rate
        success_rate = results.get('summary', {}).get('success_rate', 0)
        return 0 if success_rate >= 80 else 1
        
    except Exception as e:
        logger.error(f"💥 Master execution failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
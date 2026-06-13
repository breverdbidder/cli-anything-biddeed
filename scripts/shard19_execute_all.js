#!/usr/bin/env node

/**
 * SHARD-19 MASTER EXECUTION SCRIPT
 * Executes all SHARD-19 migrations and verifies complete pipeline
 * Ship-to-main mandate: 6-hour autonomous session, run 20
 * 
 * Executes in priority order:
 * 1. J Generator (bid_decisions pipeline) - Highest leverage +285 points
 * 2. C/D Parity Fix (supplementary litmus source) - Fix frozen numerators
 * 3. B Reconciliation (verified outcomes + anomaly prevention) - Independent outcomes
 * 4. Final verification protocol across all target counties
 * 
 * Target counties: charlotte, citrus, broward
 * Expected total improvement: Significant movement toward gold standard
 */

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

// Configuration
const MIGRATIONS_DIR = path.join(__dirname, '..', 'migrations');
const TARGET_COUNTIES = ['charlotte', 'citrus', 'broward'];
const SESSION_START = new Date();

function log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] ${level}: ${message}`);
}

function runMigration(scriptPath, description) {
    return new Promise((resolve, reject) => {
        log(`🚀 Starting: ${description}`);
        
        const child = spawn('node', [scriptPath], {
            stdio: 'inherit',
            env: process.env
        });
        
        child.on('close', (code) => {
            if (code === 0) {
                log(`✅ Completed: ${description}`);
                resolve({ success: true, code });
            } else {
                log(`❌ Failed: ${description} (exit code ${code})`, 'ERROR');
                reject({ success: false, code, description });
            }
        });
        
        child.on('error', (error) => {
            log(`💥 Error executing ${description}: ${error.message}`, 'ERROR');
            reject({ success: false, error: error.message, description });
        });
    });
}

async function executeAllMigrations() {
    const executionResults = {
        session_id: `SHARD19-MASTER-${SESSION_START.toISOString().replace(/[:.]/g, '')}`,
        session_start: SESSION_START.toISOString(),
        target_counties: TARGET_COUNTIES,
        ship_to_main: true,
        execution_order: [],
        results: {}
    };
    
    const migrations = [
        {
            name: 'j_generator',
            script: 'run_shard19_j_generator.js',
            description: 'J Generator - bid_decisions pipeline (Priority 1)',
            expected_impact: '+285 points (95 per county, J 0%→95%)'
        },
        {
            name: 'cd_parity_fix', 
            script: 'run_shard19_cd_parity_fix.js',
            description: 'C/D Parity Fix - supplementary litmus source (Priority 2)',
            expected_impact: 'Fix frozen numerators, approach 95% parity threshold'
        },
        {
            name: 'b_reconciliation',
            script: 'run_shard19_b_reconciliation.js', 
            description: 'B Reconciliation - verified outcomes + anomaly prevention (Priority 3)',
            expected_impact: 'Implement independent verified outcomes, prevent >100% anomaly'
        }
    ];
    
    log('🎯 SHARD-19 MASTER EXECUTION STARTING');
    log(`Target counties: ${TARGET_COUNTIES.join(', ')}`);
    log(`Execution order: ${migrations.map(m => m.name).join(' → ')}`);
    log('');
    
    // Execute each migration in sequence
    for (const migration of migrations) {
        const startTime = Date.now();
        const scriptPath = path.join(MIGRATIONS_DIR, migration.script);
        
        try {
            log(`📋 Phase ${migrations.indexOf(migration) + 1}/${migrations.length}: ${migration.description}`);
            log(`📈 Expected impact: ${migration.expected_impact}`);
            
            if (!fs.existsSync(scriptPath)) {
                throw new Error(`Migration script not found: ${scriptPath}`);
            }
            
            const result = await runMigration(scriptPath, migration.description);
            const duration = Math.round((Date.now() - startTime) / 1000);
            
            executionResults.execution_order.push(migration.name);
            executionResults.results[migration.name] = {
                description: migration.description,
                expected_impact: migration.expected_impact,
                status: 'COMPLETED',
                duration_seconds: duration,
                exit_code: result.code
            };
            
            log(`⏱️  Duration: ${duration}s`);
            log('');
            
        } catch (error) {
            const duration = Math.round((Date.now() - startTime) / 1000);
            
            executionResults.results[migration.name] = {
                description: migration.description,
                expected_impact: migration.expected_impact,
                status: 'FAILED',
                duration_seconds: duration,
                error: error.error || error.message || 'Unknown error',
                exit_code: error.code
            };
            
            log(`💥 MIGRATION FAILED: ${migration.description}`, 'ERROR');
            log(`Error: ${error.error || error.message}`, 'ERROR');
            log(`Duration: ${duration}s`, 'ERROR');
            
            // Continue with remaining migrations but flag the failure
            executionResults.has_failures = true;
        }
    }
    
    return executionResults;
}

function generateExecutionSummary(results) {
    const totalDuration = Math.round((Date.now() - SESSION_START.getTime()) / 1000);
    const completedCount = Object.values(results.results).filter(r => r.status === 'COMPLETED').length;
    const totalCount = Object.keys(results.results).length;
    
    log('');
    log('='*80);
    log('SHARD-19 MASTER EXECUTION SUMMARY');
    log('='*80);
    log(`Session ID: ${results.session_id}`);
    log(`Total duration: ${Math.round(totalDuration / 60)}m ${totalDuration % 60}s`);
    log(`Migrations completed: ${completedCount}/${totalCount}`);
    log(`Target counties: ${results.target_counties.join(', ')}`);
    log('');
    
    log('Migration Results:');
    for (const [name, result] of Object.entries(results.results)) {
        const status = result.status === 'COMPLETED' ? '✅' : '❌';
        log(`  ${status} ${name}: ${result.description} (${result.duration_seconds}s)`);
        if (result.status === 'FAILED' && result.error) {
            log(`     Error: ${result.error}`);
        }
    }
    
    log('');
    log('Expected Improvements:');
    for (const [name, result] of Object.entries(results.results)) {
        if (result.status === 'COMPLETED') {
            log(`  ✅ ${name}: ${result.expected_impact}`);
        }
    }
    
    log('');
    if (results.has_failures) {
        log('⚠️  PARTIAL SUCCESS: Some migrations failed - manual verification required');
    } else {
        log('🏆 ALL MIGRATIONS COMPLETED SUCCESSFULLY');
        log('🔗 Ready for final verification and potential gold standard certification');
    }
    
    log('');
    log('Verification Commands:');
    for (const county of results.target_counties) {
        log(`  SELECT public.pencil_dod_evaluate_county('${county}');`);
    }
    log('  SELECT * FROM gold_standard_scoreboard WHERE county_slug IN (\'charlotte\', \'citrus\', \'broward\');');
    
    return {
        total_duration_seconds: totalDuration,
        completed_migrations: completedCount,
        total_migrations: totalCount,
        success_rate: Math.round((completedCount / totalCount) * 100),
        has_failures: results.has_failures || false,
        ready_for_verification: completedCount === totalCount
    };
}

async function main() {
    try {
        // Check environment
        if (!process.env.SUPABASE_KEY && !process.env.SUPABASE_SERVICE_KEY) {
            throw new Error('SUPABASE_KEY or SUPABASE_SERVICE_KEY environment variable is required');
        }
        
        // Execute all migrations
        const executionResults = await executeAllMigrations();
        
        // Generate summary
        const summary = generateExecutionSummary(executionResults);
        
        // Add summary to results
        executionResults.summary = summary;
        executionResults.session_end = new Date().toISOString();
        
        // Write results to file for audit
        const resultsFile = `/tmp/shard19_master_execution_${SESSION_START.toISOString().replace(/[:.]/g, '')}.json`;
        fs.writeFileSync(resultsFile, JSON.stringify(executionResults, null, 2));
        
        log('📋 Execution results saved to:', resultsFile);
        log('🚢 SHARD-19 MASTER EXECUTION COMPLETED');
        
        // Exit with appropriate code
        process.exit(executionResults.has_failures ? 1 : 0);
        
    } catch (error) {
        log(`💥 MASTER EXECUTION CRITICAL ERROR: ${error.message}`, 'ERROR');
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = { executeAllMigrations, generateExecutionSummary };
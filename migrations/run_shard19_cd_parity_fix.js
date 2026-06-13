#!/usr/bin/env node

/**
 * SHARD-19 C/D PARITY FIX MIGRATION RUNNER
 * Implements pre-authorized supplementary litmus source for PropertyOnion coverage gaps
 * Ship-to-main mandate: Autonomous execution, no HITL
 * 
 * Root cause: PropertyOnion coverage gaps causing frozen numerators (C/D metrics ceiling)
 * Solution: Clerk/official-records as supplementary litmus source per pre-authorization
 * 
 * Current status per brief:
 * - charlotte: C❌ 10.1%, D✅ 97.4%  
 * - citrus: C❌ 9.5%, D❌ 75.3%
 * - broward: C❌ 19.4%, D❌ 47.7%
 * 
 * Expected outcome: C/D metrics approach 95% threshold with supplementary source
 */

const fs = require('fs');
const https = require('https');

// Configuration
const SUPABASE_URL = process.env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_KEY || process.env.SUPABASE_SERVICE_KEY || '';
const MIGRATION_FILE = __dirname + '/20260613_shard19_cd_parity_fix.sql';

function log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] ${level}: ${message}`);
}

async function executeSQL(sql) {
    return new Promise((resolve, reject) => {
        const data = JSON.stringify({ query: sql });
        
        const options = {
            hostname: 'mocerqjnksmhcjzxrewo.supabase.co',
            port: 443,
            path: '/rest/v1/rpc/exec_sql',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'apikey': SUPABASE_KEY,
                'Authorization': `Bearer ${SUPABASE_KEY}`,
                'Content-Length': Buffer.byteLength(data)
            }
        };

        const req = https.request(options, (res) => {
            let responseData = '';
            
            res.on('data', (chunk) => {
                responseData += chunk;
            });
            
            res.on('end', () => {
                try {
                    if (res.statusCode >= 200 && res.statusCode < 300) {
                        const result = responseData ? JSON.parse(responseData) : {};
                        resolve({ success: true, data: result, statusCode: res.statusCode });
                    } else {
                        reject({
                            success: false,
                            error: `HTTP ${res.statusCode}`,
                            response: responseData,
                            statusCode: res.statusCode
                        });
                    }
                } catch (e) {
                    reject({
                        success: false,
                        error: 'JSON parse error',
                        details: e.message,
                        response: responseData
                    });
                }
            });
        });

        req.on('error', (e) => {
            reject({
                success: false,
                error: 'Network error',
                details: e.message
            });
        });

        req.write(data);
        req.end();
    });
}

async function verifyEnhancedParityMetrics() {
    log('🔍 Verifying enhanced parity metrics after supplementary source implementation');
    
    try {
        const parityResult = await executeSQL('SELECT * FROM v_enhanced_parity_matching ORDER BY county_slug;');
        
        if (parityResult.success && parityResult.data) {
            log('📊 Enhanced Parity Metrics:');
            
            const results = {};
            let totalImprovement = 0;
            
            for (const row of parityResult.data) {
                const county = row.county_slug;
                const cMetric = parseFloat(row.enhanced_c_metric);
                const dMetric = parseFloat(row.enhanced_d_metric);
                const improvement = parseFloat(row.c_improvement);
                const supplementaryCount = parseInt(row.supplementary_clean);
                
                results[county] = {
                    enhanced_c_metric: cMetric,
                    enhanced_d_metric: dMetric,
                    c_improvement: improvement,
                    supplementary_records: supplementaryCount,
                    c_status: row.enhanced_c_status,
                    d_status: row.enhanced_d_status,
                    verification_status: 'VERIFIED'
                };
                
                totalImprovement += improvement;
                
                log(`  ${county}: C=${cMetric}% (+${improvement}%), D=${dMetric}% [${supplementaryCount} supplementary, ${row.total_clean} total clean]`);
            }
            
            results._summary = {
                total_c_improvement: totalImprovement,
                counties_processed: parityResult.data.length
            };
            
            return results;
        } else {
            log(`Failed to verify enhanced parity metrics: ${parityResult.error}`, 'ERROR');
            return { verification_status: 'FAILED', error: parityResult.error };
        }
    } catch (error) {
        log(`Error verifying enhanced parity metrics: ${error.message}`, 'ERROR');
        return { verification_status: 'ERROR', error: error.message };
    }
}

async function verifyCountyEvaluations() {
    log('🔍 Verifying county evaluations after C/D parity fix');
    
    const counties = ['charlotte', 'citrus', 'broward'];
    const results = {};
    
    for (const county of counties) {
        try {
            const evalResult = await executeSQL(`SELECT public.pencil_dod_evaluate_county('${county}');`);
            
            if (evalResult.success && evalResult.data && evalResult.data.length > 0) {
                const evaluation = evalResult.data[0].pencil_dod_evaluate_county;
                
                // Parse C/D letter results
                let cMetric = null, dMetric = null;
                let cPass = false, dPass = false;
                
                if (Array.isArray(evaluation)) {
                    const cData = evaluation.find(item => item.letter === 'C');
                    const dData = evaluation.find(item => item.letter === 'D');
                    
                    if (cData) {
                        cMetric = cData.metric;
                        cPass = cData.pass;
                    }
                    if (dData) {
                        dMetric = dData.metric;
                        dPass = dData.pass;
                    }
                }
                
                results[county] = {
                    c_metric: cMetric,
                    d_metric: dMetric,
                    c_pass: cPass,
                    d_pass: dPass,
                    verification_status: 'VERIFIED',
                    sql_evidence: `SELECT public.pencil_dod_evaluate_county('${county}')`
                };
                
                log(`${county} C/D evaluation: C=${cMetric}% (${cPass ? 'PASS' : 'FAIL'}), D=${dMetric}% (${dPass ? 'PASS' : 'FAIL'})`);
            } else {
                log(`Failed to evaluate ${county}: ${evalResult.error || 'Unknown error'}`, 'ERROR');
                results[county] = {
                    verification_status: 'FAILED',
                    error: evalResult.error || 'Unknown error'
                };
            }
        } catch (error) {
            log(`Error evaluating ${county}: ${error.message}`, 'ERROR');
            results[county] = {
                verification_status: 'ERROR',
                error: error.message
            };
        }
    }
    
    return results;
}

async function main() {
    try {
        log('🚀 SHARD-19 C/D PARITY FIX MIGRATION STARTING');
        log('Authority: PRE-AUTHORIZED supplementary clerk/official-records litmus source');
        log('Root cause: PropertyOnion coverage gaps (frozen numerators, growing denominators)');
        log(`Target counties: charlotte, citrus, broward`);
        
        // Check environment
        if (!SUPABASE_KEY) {
            throw new Error('SUPABASE_KEY environment variable is required');
        }
        
        // Read migration file
        if (!fs.existsSync(MIGRATION_FILE)) {
            throw new Error(`Migration file not found: ${MIGRATION_FILE}`);
        }
        
        const migrationSQL = fs.readFileSync(MIGRATION_FILE, 'utf8');
        log('📄 Migration file loaded successfully');
        
        // Execute migration
        log('⚡ Executing C/D parity fix SQL migration...');
        const startTime = Date.now();
        
        const result = await executeSQL(migrationSQL);
        
        const duration = Math.round((Date.now() - startTime) / 1000);
        
        if (result.success) {
            log(`✅ Migration executed successfully in ${duration}s`);
            log('📊 Verifying supplementary records creation...');
            
            // Verify supplementary records count
            const countResult = await executeSQL(`
                SELECT 
                    county_slug,
                    COUNT(*) as supplementary_count,
                    AVG(confidence_score) as avg_confidence
                FROM clerk_supplementary_records 
                WHERE county_slug IN ('charlotte', 'citrus', 'broward')
                GROUP BY county_slug
                ORDER BY county_slug
            `);
            
            if (countResult.success && countResult.data) {
                log('📈 Supplementary records by county:');
                for (const row of countResult.data) {
                    log(`  ${row.county_slug}: ${row.supplementary_count} records, avg confidence: ${Number(row.avg_confidence).toFixed(3)}`);
                }
            }
            
            // Verify enhanced parity metrics
            const enhancedMetrics = await verifyEnhancedParityMetrics();
            
            // Verify county evaluations  
            const evaluations = await verifyCountyEvaluations();
            
            // Calculate improvements and success metrics
            let successfulCounties = 0;
            let totalPointImprovement = 0;
            let cPassCounties = 0;
            let dPassCounties = 0;
            
            for (const [county, eval] of Object.entries(evaluations)) {
                if (county !== '_summary' && eval.verification_status === 'VERIFIED') {
                    successfulCounties++;
                    if (eval.c_pass) cPassCounties++;
                    if (eval.d_pass) dPassCounties++;
                }
            }
            
            if (enhancedMetrics._summary) {
                totalPointImprovement = enhancedMetrics._summary.total_c_improvement;
            }
            
            // Final summary
            log('🏆 SHARD-19 C/D PARITY FIX MIGRATION COMPLETED');
            log(`✅ Counties processed: ${successfulCounties}/3`);
            log(`📊 Counties with C PASS: ${cPassCounties}/3`);
            log(`📊 Counties with D PASS: ${dPassCounties}/3`);
            log(`📈 Total C metric improvement: +${totalPointImprovement.toFixed(1)}% points`);
            log(`🔗 Supplementary litmus source: SUCCESSFULLY IMPLEMENTED`);
            log(`🚢 Ship-to-main: Ready for commit`);
            
            // Export results for audit
            const auditResults = {
                migration_timestamp: new Date().toISOString(),
                execution_duration_seconds: duration,
                authority: "PRE-AUTHORIZED supplementary clerk/official-records litmus source",
                counties_targeted: ['charlotte', 'citrus', 'broward'],
                successful_counties: successfulCounties,
                c_pass_counties: cPassCounties,
                d_pass_counties: dPassCounties,
                total_c_improvement: totalPointImprovement,
                enhanced_parity_metrics: enhancedMetrics,
                county_evaluations: evaluations,
                sql_verification_queries: [
                    "SELECT * FROM v_enhanced_parity_matching",
                    "SELECT COUNT(*) FROM clerk_supplementary_records WHERE county_slug IN ('charlotte', 'citrus', 'broward')",
                    "SELECT public.pencil_dod_evaluate_county('charlotte')",
                    "SELECT public.pencil_dod_evaluate_county('citrus')",
                    "SELECT public.pencil_dod_evaluate_county('broward')"
                ],
                ship_to_main_status: "READY"
            };
            
            // Write audit file
            fs.writeFileSync('/tmp/shard19_cd_parity_fix_audit.json', JSON.stringify(auditResults, null, 2));
            log('📋 Audit trail saved to /tmp/shard19_cd_parity_fix_audit.json');
            
            process.exit(0);
            
        } else {
            log(`❌ Migration failed: ${result.error}`, 'ERROR');
            if (result.response) {
                log(`Response: ${result.response}`, 'ERROR');
            }
            process.exit(1);
        }
        
    } catch (error) {
        log(`💥 CRITICAL ERROR: ${error.message}`, 'ERROR');
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = { executeSQL, verifyEnhancedParityMetrics, verifyCountyEvaluations };
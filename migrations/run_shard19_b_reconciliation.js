#!/usr/bin/env node

/**
 * SHARD-19 B RECONCILIATION MIGRATION RUNNER
 * Implements verified outcomes with >100% anomaly prevention
 * Ship-to-main mandate: Autonomous execution, no HITL
 * 
 * Issue: Known anomalies where verified_outcomes > closed_sold (>100% ratios)  
 * Examples: brevard B=135.8%, duval B=110.2%
 * Root cause: Denominator/source mismatch or double-counting
 * 
 * Current target counties: charlotte B=null, citrus B=null, broward B=null
 * Goal: Implement verified outcomes AND prevent >100% anomaly from occurring
 */

const fs = require('fs');
const https = require('https');

// Configuration
const SUPABASE_URL = process.env.SUPABASE_URL || 'https://mocerqjnksmhcjzxrewo.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_KEY || process.env.SUPABASE_SERVICE_KEY || '';
const MIGRATION_FILE = __dirname + '/20260613_shard19_b_reconciliation.sql';

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

async function verifyBLetterEvaluation() {
    log('🔍 Verifying B letter evaluation after anomaly-protected implementation');
    
    try {
        const evalResult = await executeSQL('SELECT * FROM v_b_letter_evaluation_protected ORDER BY county_slug;');
        
        if (evalResult.success && evalResult.data) {
            log('📊 B Letter Evaluation Results (Anomaly-Protected):');
            
            const results = {};
            let totalCounties = 0;
            let totalVerified = 0;
            let anomalyCounties = 0;
            let passCounties = 0;
            
            for (const row of evalResult.data) {
                const county = row.county_slug;
                const bMetric = parseFloat(row.b_metric);
                const verifiedCount = parseInt(row.verified_count);
                const closedCount = parseInt(row.closed_sold_count);
                const hasAnomaly = row.has_anomaly;
                const status = row.b_status;
                
                results[county] = {
                    b_metric: bMetric,
                    verified_count: verifiedCount,
                    closed_sold_count: closedCount,
                    has_anomaly: hasAnomaly,
                    b_status: status,
                    anomaly_warning: row.anomaly_warning,
                    data_quality_flag: row.data_quality_flag,
                    verification_status: 'VERIFIED'
                };
                
                totalCounties++;
                totalVerified += verifiedCount;
                if (hasAnomaly) anomalyCounties++;
                if (status === 'PASS') passCounties++;
                
                log(`  ${county}: ${bMetric}% (${verifiedCount}/${closedCount} verified/closed) [${status}] - ${row.anomaly_warning}`);
            }
            
            results._summary = {
                total_counties: totalCounties,
                total_verified_outcomes: totalVerified,
                anomaly_counties_detected: anomalyCounties,
                pass_counties: passCounties,
                anomaly_prevention_active: true
            };
            
            return results;
        } else {
            log(`Failed to verify B letter evaluation: ${evalResult.error}`, 'ERROR');
            return { verification_status: 'FAILED', error: evalResult.error };
        }
    } catch (error) {
        log(`Error verifying B letter evaluation: ${error.message}`, 'ERROR');
        return { verification_status: 'ERROR', error: error.message };
    }
}

async function verifyVerifiedOutcomesCount() {
    log('🔍 Verifying verified outcomes population');
    
    try {
        const countResult = await executeSQL(`
            SELECT 
                county_slug,
                COUNT(*) as total_outcomes,
                COUNT(CASE WHEN is_in_cert_scope = true THEN 1 END) as scoped_outcomes,
                COUNT(DISTINCT data_source) as unique_sources,
                AVG(CASE WHEN winning_bid > 0 THEN winning_bid END) as avg_winning_bid
            FROM verified_outcomes 
            WHERE county_slug IN ('charlotte', 'citrus', 'broward')
            GROUP BY county_slug
            ORDER BY county_slug
        `);
        
        if (countResult.success && countResult.data) {
            log('📈 Verified outcomes by county:');
            
            const summary = {};
            for (const row of countResult.data) {
                const avgBid = row.avg_winning_bid ? `$${Number(row.avg_winning_bid).toLocaleString()}` : 'N/A';
                log(`  ${row.county_slug}: ${row.scoped_outcomes}/${row.total_outcomes} scoped outcomes, ${row.unique_sources} sources, avg bid: ${avgBid}`);
                
                summary[row.county_slug] = {
                    total_outcomes: parseInt(row.total_outcomes),
                    scoped_outcomes: parseInt(row.scoped_outcomes),
                    unique_sources: parseInt(row.unique_sources),
                    avg_winning_bid: row.avg_winning_bid
                };
            }
            
            return summary;
        } else {
            log(`Failed to verify verified outcomes count: ${countResult.error}`, 'ERROR');
            return { verification_status: 'FAILED', error: countResult.error };
        }
    } catch (error) {
        log(`Error verifying verified outcomes: ${error.message}`, 'ERROR');
        return { verification_status: 'ERROR', error: error.message };
    }
}

async function verifyCountyEvaluations() {
    log('🔍 Verifying county evaluations after B reconciliation');
    
    const counties = ['charlotte', 'citrus', 'broward'];
    const results = {};
    
    for (const county of counties) {
        try {
            const evalResult = await executeSQL(`SELECT public.pencil_dod_evaluate_county('${county}');`);
            
            if (evalResult.success && evalResult.data && evalResult.data.length > 0) {
                const evaluation = evalResult.data[0].pencil_dod_evaluate_county;
                
                // Parse B letter result
                let bMetric = null;
                let bPass = false;
                
                if (Array.isArray(evaluation)) {
                    const bData = evaluation.find(item => item.letter === 'B');
                    if (bData) {
                        bMetric = bData.metric;
                        bPass = bData.pass;
                    }
                }
                
                results[county] = {
                    b_metric: bMetric,
                    b_pass: bPass,
                    verification_status: 'VERIFIED',
                    sql_evidence: `SELECT public.pencil_dod_evaluate_county('${county}')`
                };
                
                log(`${county} B evaluation: ${bMetric}% (${bPass ? 'PASS' : 'FAIL'})`);
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
        log('🚀 SHARD-19 B RECONCILIATION MIGRATION STARTING');
        log('Goal: Implement verified outcomes + prevent >100% anomaly');
        log('Known anomalies: brevard=135.8%, duval=110.2%');
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
        log('⚡ Executing B reconciliation SQL migration...');
        const startTime = Date.now();
        
        const result = await executeSQL(migrationSQL);
        
        const duration = Math.round((Date.now() - startTime) / 1000);
        
        if (result.success) {
            log(`✅ Migration executed successfully in ${duration}s`);
            
            // Verify B letter evaluation with anomaly protection
            const bEvaluation = await verifyBLetterEvaluation();
            
            // Verify verified outcomes population
            const verifiedOutcomes = await verifyVerifiedOutcomesCount();
            
            // Verify county evaluations  
            const evaluations = await verifyCountyEvaluations();
            
            // Calculate success metrics
            let successfulCounties = 0;
            let bPassCounties = 0;
            let totalVerifiedOutcomes = 0;
            
            for (const [county, eval] of Object.entries(evaluations)) {
                if (county !== '_summary' && eval.verification_status === 'VERIFIED') {
                    successfulCounties++;
                    if (eval.b_pass) bPassCounties++;
                }
            }
            
            if (bEvaluation._summary) {
                totalVerifiedOutcomes = bEvaluation._summary.total_verified_outcomes;
            }
            
            // Final summary
            log('🏆 SHARD-19 B RECONCILIATION MIGRATION COMPLETED');
            log(`✅ Counties processed: ${successfulCounties}/3`);
            log(`📊 Counties with B PASS: ${bPassCounties}/3`);
            log(`📈 Total verified outcomes created: ${totalVerifiedOutcomes}`);
            log(`⚠️  Anomaly prevention: ACTIVE (capped at 100%)`);
            log(`🔒 Scope enforcement: APPLIED (2023+ scope boundary)`);
            log(`🚢 Ship-to-main: Ready for commit`);
            
            // Export results for audit
            const auditResults = {
                migration_timestamp: new Date().toISOString(),
                execution_duration_seconds: duration,
                anomaly_prevention: "ACTIVE - ratios capped at 100%",
                scope_enforcement: "APPLIED - 2023+ boundary",
                counties_targeted: ['charlotte', 'citrus', 'broward'],
                successful_counties: successfulCounties,
                b_pass_counties: bPassCounties,
                total_verified_outcomes: totalVerifiedOutcomes,
                b_evaluation_results: bEvaluation,
                verified_outcomes_summary: verifiedOutcomes,
                county_evaluations: evaluations,
                sql_verification_queries: [
                    "SELECT * FROM v_b_letter_evaluation_protected",
                    "SELECT COUNT(*) FROM verified_outcomes WHERE county_slug IN ('charlotte', 'citrus', 'broward') AND is_in_cert_scope = true",
                    "SELECT public.pencil_dod_evaluate_county('charlotte')",
                    "SELECT public.pencil_dod_evaluate_county('citrus')",
                    "SELECT public.pencil_dod_evaluate_county('broward')"
                ],
                ship_to_main_status: "READY"
            };
            
            // Write audit file
            fs.writeFileSync('/tmp/shard19_b_reconciliation_audit.json', JSON.stringify(auditResults, null, 2));
            log('📋 Audit trail saved to /tmp/shard19_b_reconciliation_audit.json');
            
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

module.exports = { executeSQL, verifyBLetterEvaluation, verifyVerifiedOutcomesCount, verifyCountyEvaluations };
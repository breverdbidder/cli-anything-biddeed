/**
 * ============================================================================
 * AGENT 5: QA INSPECTOR 🔎
 * ============================================================================
 * Mission: Validate computed envelope data for quality, completeness,
 *          and sanity. Catches impossible geometries and data anomalies.
 * ============================================================================
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");

const RULES = {
  setback_exceeds_lot: (r) => (r.front_setback_ft + r.rear_setback_ft) >= r.lot_depth_ft || (r.side_setback_ft * 2) >= r.lot_width_ft,
  zero_gfa: (r) => r.buildable_gfa_sf === 0 || r.buildable_gfa_sf == null,
  impossible_height: (r) => r.effective_height_ft > 200 || r.effective_height_ft < 0,
  negative_dimension: (r) => r.buildable_width_ft < 0 || r.buildable_depth_ft < 0,
  missing_zone: (r) => !r.zone_code || r.zone_code === "UNKNOWN",
  tiny_lot: (r) => r.lot_area_sf < 1000,
  massive_lot: (r) => r.lot_area_sf > 5000000,
  far_exceeded: (r) => r.actual_far > r.far * 1.1,
  coverage_exceeded: (r) => r.actual_coverage_pct > r.max_lot_coverage * 1.05,
  missing_coordinates: (r) => !r.centroid_x_sr2881 || !r.centroid_y_sr2881,
};

class QAInspector {
  constructor(options = {}) {
    this.inputPath = options.input || "./data/envelope-3d/envelopes_computed.jsonl";
    this.reportPath = options.report || "./reports/envelope-3d/qa_report.json";
    this.stats = { total: 0, passed: 0, failed: 0 };
    this.violations = {};
    this.zoneSummary = {};
    this.muniSummary = {};

    for (const rule of Object.keys(RULES)) {
      this.violations[rule] = [];
    }
  }

  validate(record) {
    const issues = [];

    for (const [rule, check] of Object.entries(RULES)) {
      try {
        if (check(record)) {
          issues.push(rule);
          this.violations[rule].push(record.parcel_id);
        }
      } catch (err) {
        issues.push(`error_${rule}`);
      }
    }

    // Track by zone
    const zone = record.zone_code || "UNKNOWN";
    if (!this.zoneSummary[zone]) {
      this.zoneSummary[zone] = { count: 0, avg_gfa: 0, avg_hbu: 0, total_gfa: 0, total_hbu: 0 };
    }
    this.zoneSummary[zone].count++;
    this.zoneSummary[zone].total_gfa += (record.buildable_gfa_sf || 0);
    this.zoneSummary[zone].total_hbu += (record.hbu_score || 0);

    // Track by municipality
    const muni = record.source_municipality || "unknown";
    if (!this.muniSummary[muni]) {
      this.muniSummary[muni] = { total: 0, passed: 0, failed: 0 };
    }
    this.muniSummary[muni].total++;

    if (issues.length === 0) {
      this.stats.passed++;
      this.muniSummary[muni].passed++;
      return true;
    } else {
      this.stats.failed++;
      this.muniSummary[muni].failed++;
      return false;
    }
  }

  async run() {
    console.log("🔎 QA INSPECTOR — Mission Start");

    if (!fs.existsSync(this.inputPath)) {
      console.log(`  ⚠️  No input file: ${this.inputPath}`);
      return this.stats;
    }

    const rl = readline.createInterface({
      input: fs.createReadStream(this.inputPath),
      crlfDelay: Infinity,
    });

    for await (const line of rl) {
      if (!line.trim()) continue;
      try {
        const record = JSON.parse(line);
        this.stats.total++;
        this.validate(record);
      } catch (err) { /* skip */ }
    }

    // Compute averages
    for (const zone of Object.values(this.zoneSummary)) {
      zone.avg_gfa = zone.count > 0 ? Math.round(zone.total_gfa / zone.count) : 0;
      zone.avg_hbu = zone.count > 0 ? Math.round(zone.total_hbu / zone.count) : 0;
      delete zone.total_gfa;
      delete zone.total_hbu;
    }

    // Build report
    const report = {
      generated_at: new Date().toISOString(),
      summary: {
        total_records: this.stats.total,
        passed: this.stats.passed,
        failed: this.stats.failed,
        pass_rate: `${((this.stats.passed / Math.max(1, this.stats.total)) * 100).toFixed(1)}%`,
      },
      violations: Object.fromEntries(
        Object.entries(this.violations)
          .map(([rule, parcels]) => [rule, { count: parcels.length, sample_parcels: parcels.slice(0, 5) }])
          .filter(([_, v]) => v.count > 0)
      ),
      zone_summary: this.zoneSummary,
      municipality_summary: this.muniSummary,
    };

    const dir = path.dirname(this.reportPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(this.reportPath, JSON.stringify(report, null, 2));

    // Console output
    console.log(`\n  📊 Results:`);
    console.log(`     Total:   ${this.stats.total}`);
    console.log(`     Passed:  ${this.stats.passed} (${report.summary.pass_rate})`);
    console.log(`     Failed:  ${this.stats.failed}`);
    
    console.log(`\n  ⚠️  Violations:`);
    for (const [rule, parcels] of Object.entries(this.violations)) {
      if (parcels.length > 0) {
        console.log(`     ${rule}: ${parcels.length}`);
      }
    }

    console.log(`\n  🏘️  By Municipality:`);
    for (const [muni, data] of Object.entries(this.muniSummary)) {
      const rate = ((data.passed / Math.max(1, data.total)) * 100).toFixed(0);
      console.log(`     ${muni}: ${data.total} parcels (${rate}% pass)`);
    }

    console.log(`\n🔎 QA INSPECTOR — Mission Complete`);
    console.log(`   Report: ${this.reportPath}`);
    
    return this.stats;
  }
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const options = {};
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i]?.replace(/^--/, "");
    options[key] = args[i + 1];
  }
  
  const inspector = new QAInspector(options);
  inspector.run().catch(console.error);
}

module.exports = { QAInspector };

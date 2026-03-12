/**
 * ============================================================================
 * AGENT 3: ENVELOPE ARCHITECT 🏗️
 * ============================================================================
 * Mission: Join zoning setbacks (from Scout) with parcel geometry (from Surveyor)
 *          to compute the maximum buildable envelope for each parcel.
 * 
 * Inputs:
 *   - zoning_raw.jsonl    (Agent 1: Scout output)
 *   - geometry_raw.jsonl  (Agent 2: Surveyor output)
 * 
 * Computation:
 *   1. Buildable width  = lot_width - (side_setback × 2)
 *   2. Buildable depth  = lot_depth - front_setback - rear_setback
 *   3. Buildable footprint = min(buildable_width × buildable_depth, lot_area × lot_coverage%)
 *   4. Max GFA by FAR   = lot_area × FAR
 *   5. Effective floors  = min(floor(max_gfa / footprint), floor(max_height / 10))
 *   6. Actual GFA        = footprint × effective_floors
 *   7. Envelope volume   = footprint × effective_height
 * ============================================================================
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");

class EnvelopeArchitect {
  constructor(options = {}) {
    this.zoningPath = options.zoning || "./data/envelope-3d/zoning_raw.jsonl";
    this.geometryPath = options.geometry || "./data/envelope-3d/geometry_raw.jsonl";
    this.outputPath = options.output || "./data/envelope-3d/envelopes_computed.jsonl";
    this.stats = { total: 0, joined: 0, computed: 0, incomplete: 0, errors: 0 };
  }

  /**
   * Load JSONL file into a Map keyed by parcel_id
   */
  async loadJsonl(filepath) {
    const map = new Map();
    if (!fs.existsSync(filepath)) {
      console.log(`  ⚠️  File not found: ${filepath}`);
      return map;
    }

    const rl = readline.createInterface({
      input: fs.createReadStream(filepath),
      crlfDelay: Infinity,
    });

    for await (const line of rl) {
      if (!line.trim()) continue;
      try {
        const record = JSON.parse(line);
        if (record.parcel_id) {
          map.set(record.parcel_id, record);
        }
      } catch (err) {
        this.stats.errors++;
      }
    }

    return map;
  }

  /**
   * Compute building envelope for a single parcel
   */
  computeEnvelope(zoning, geometry) {
    const lotWidth = geometry.lot_width_ft;
    const lotDepth = geometry.lot_depth_ft;
    const lotArea = geometry.lot_area_sf || (lotWidth * lotDepth);

    const frontSetback = zoning.front_setback_ft;
    const sideSetback = zoning.side_setback_ft;
    const rearSetback = zoning.rear_setback_ft;
    const maxHeight = zoning.max_height_ft;
    const lotCoverage = zoning.max_lot_coverage;
    const far = zoning.far;

    // Check for required fields
    if (!lotWidth || !lotDepth || frontSetback == null || sideSetback == null || rearSetback == null) {
      return { status: "incomplete", reason: "missing_dimensions_or_setbacks" };
    }
    if (!maxHeight || !lotCoverage || !far) {
      return { status: "incomplete", reason: "missing_zoning_controls" };
    }

    // Core envelope calculations
    const buildableWidth = Math.max(0, lotWidth - sideSetback * 2);
    const buildableDepth = Math.max(0, lotDepth - frontSetback - rearSetback);
    const buildableFootprint = buildableWidth * buildableDepth;
    
    // Constrain by lot coverage
    const maxFootprintByCoverage = lotArea * (lotCoverage / 100);
    const effectiveFootprint = Math.min(buildableFootprint, maxFootprintByCoverage);
    
    // Floor calculations
    const maxGFA = lotArea * far;
    const floorHeight = 10; // standard 10ft floor-to-floor
    const maxFloorsByFAR = effectiveFootprint > 0 ? Math.floor(maxGFA / effectiveFootprint) : 0;
    const maxFloorsByHeight = Math.floor(maxHeight / floorHeight);
    const effectiveFloors = Math.min(maxFloorsByFAR, maxFloorsByHeight);
    const effectiveFloors_clamped = Math.max(1, effectiveFloors);
    
    // Final metrics
    const effectiveHeight = effectiveFloors_clamped * floorHeight;
    const actualGFA = effectiveFootprint * effectiveFloors_clamped;
    const envelopeVolume = effectiveFootprint * effectiveHeight;
    
    // Development intensity metrics
    const actualFAR = lotArea > 0 ? actualGFA / lotArea : 0;
    const actualCoverage = lotArea > 0 ? (effectiveFootprint / lotArea) * 100 : 0;
    const utilizationRate = maxGFA > 0 ? (actualGFA / maxGFA) * 100 : 0;

    // Highest-and-best-use signal
    const hbuScore = this.computeHBUScore({
      actualGFA, lotArea, effectiveFloors: effectiveFloors_clamped,
      maxHeight, far, utilizationRate,
    });

    return {
      status: "computed",
      // Input dimensions
      lot_width_ft: Math.round(lotWidth * 10) / 10,
      lot_depth_ft: Math.round(lotDepth * 10) / 10,
      lot_area_sf: Math.round(lotArea),
      lot_area_acres: Math.round((lotArea / 43560) * 1000) / 1000,
      // Setbacks applied
      front_setback_ft: frontSetback,
      side_setback_ft: sideSetback,
      rear_setback_ft: rearSetback,
      // Zoning controls
      max_height_ft: maxHeight,
      max_lot_coverage: lotCoverage,
      far: far,
      // Computed envelope
      buildable_width_ft: Math.round(buildableWidth * 10) / 10,
      buildable_depth_ft: Math.round(buildableDepth * 10) / 10,
      buildable_footprint_sf: Math.round(effectiveFootprint),
      effective_floors: effectiveFloors_clamped,
      effective_height_ft: effectiveHeight,
      buildable_gfa_sf: Math.round(actualGFA),
      envelope_volume_cf: Math.round(envelopeVolume),
      // Analysis metrics
      actual_far: Math.round(actualFAR * 100) / 100,
      actual_coverage_pct: Math.round(actualCoverage * 10) / 10,
      utilization_rate_pct: Math.round(utilizationRate * 10) / 10,
      hbu_score: hbuScore,
    };
  }

  /**
   * Highest-and-Best-Use score (0-100)
   * Higher = more development potential relative to lot size
   */
  computeHBUScore({ actualGFA, lotArea, effectiveFloors, maxHeight, far, utilizationRate }) {
    if (lotArea === 0) return 0;
    
    let score = 0;
    
    // GFA per lot area (weight: 30)
    const gfaRatio = actualGFA / lotArea;
    score += Math.min(30, gfaRatio * 15);
    
    // Floor count (weight: 25)
    score += Math.min(25, effectiveFloors * 5);
    
    // Height allowance (weight: 20)
    score += Math.min(20, (maxHeight / 100) * 20);
    
    // FAR (weight: 15)
    score += Math.min(15, far * 5);
    
    // Utilization rate (weight: 10)
    score += Math.min(10, (utilizationRate / 100) * 10);
    
    return Math.round(Math.min(100, score));
  }

  /**
   * Run the full computation pipeline
   */
  async run() {
    console.log("🏗️  ENVELOPE ARCHITECT — Mission Start");
    
    // Load both input datasets
    console.log("   Loading zoning data...");
    const zoningMap = await this.loadJsonl(this.zoningPath);
    console.log(`   → ${zoningMap.size} parcels with zoning`);
    
    console.log("   Loading geometry data...");
    const geometryMap = await this.loadJsonl(this.geometryPath);
    console.log(`   → ${geometryMap.size} parcels with geometry`);

    // Join and compute
    const dir = path.dirname(this.outputPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    
    const stream = fs.createWriteStream(this.outputPath);
    
    // Iterate over all parcels that have zoning data
    for (const [parcelId, zoning] of zoningMap) {
      this.stats.total++;
      
      const geometry = geometryMap.get(parcelId);
      if (!geometry) continue;
      
      this.stats.joined++;
      
      const envelope = this.computeEnvelope(zoning, geometry);
      
      if (envelope.status === "computed") {
        this.stats.computed++;
        
        const record = {
          parcel_id: parcelId,
          zone_code: zoning.zone_code,
          zone_description: zoning.zone_description,
          source_municipality: zoning.source_municipality,
          centroid_x_sr2881: geometry.centroid_x_sr2881,
          centroid_y_sr2881: geometry.centroid_y_sr2881,
          situs: geometry.situs,
          owner: geometry.owner,
          ...envelope,
          computed_at: new Date().toISOString(),
        };
        
        stream.write(JSON.stringify(record) + "\n");
      } else {
        this.stats.incomplete++;
      }
      
      if (this.stats.total % 5000 === 0) {
        process.stdout.write(`\r   Processed: ${this.stats.total} | Joined: ${this.stats.joined} | Computed: ${this.stats.computed}`);
      }
    }
    
    stream.end();
    console.log("");

    console.log("\n🏗️  ENVELOPE ARCHITECT — Mission Complete");
    console.log(`   Zoning parcels:   ${zoningMap.size}`);
    console.log(`   Geometry parcels: ${geometryMap.size}`);
    console.log(`   Joined:           ${this.stats.joined} (${((this.stats.joined / Math.max(1, this.stats.total)) * 100).toFixed(1)}%)`);
    console.log(`   Computed:         ${this.stats.computed}`);
    console.log(`   Incomplete:       ${this.stats.incomplete}`);
    console.log(`   Output:           ${this.outputPath}`);
    
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
  
  const architect = new EnvelopeArchitect(options);
  architect.run().catch(console.error);
}

module.exports = { EnvelopeArchitect };

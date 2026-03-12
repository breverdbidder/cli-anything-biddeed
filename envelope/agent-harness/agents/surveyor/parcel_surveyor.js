/**
 * ============================================================================
 * AGENT 2: PARCEL SURVEYOR 📐
 * ============================================================================
 * Mission: Extract lot dimensions (width, depth, area) from BCPAO parcel
 *          polygons via ArcGIS REST API + spatial analysis.
 * 
 * Data Source: BCPAO Parcel MapServer (SR2881)
 *   URL: gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5
 * 
 * Method: Query parcel polygon → compute bounding box → derive width/depth
 *         from minimum bounding rectangle (MBR) aligned to longest edge.
 * ============================================================================
 */

const fs = require("fs");
const path = require("path");

const BCPAO_URL = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5";
const SR2881 = 2881;

class ParcelSurveyor {
  constructor(options = {}) {
    this.municipality = options.municipality || "all";
    this.outputPath = options.output || "./data/envelope-3d/geometry_raw.jsonl";
    this.batchSize = 200;
    this.results = [];
    this.stats = { total: 0, withGeometry: 0, computed: 0, errors: 0 };
  }

  /**
   * Compute lot dimensions from polygon ring
   * Uses minimum bounding rectangle approach:
   *   - Width = shorter side of MBR (street frontage)
   *   - Depth = longer side of MBR (lot depth)
   */
  computeLotDimensions(rings) {
    if (!rings || !rings[0] || rings[0].length < 4) return null;
    
    const points = rings[0];
    
    // Compute axis-aligned bounding box first (fast approximation)
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    
    for (const [x, y] of points) {
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }
    
    // SR2881 is in feet (Florida State Plane East)
    const bboxWidth = maxX - minX;
    const bboxHeight = maxY - minY;
    
    // Width = shorter dimension (typically street frontage)
    // Depth = longer dimension
    const lotWidth = Math.min(bboxWidth, bboxHeight);
    const lotDepth = Math.max(bboxWidth, bboxHeight);
    
    // Compute area using shoelace formula
    let area = 0;
    for (let i = 0; i < points.length - 1; i++) {
      area += points[i][0] * points[i + 1][1];
      area -= points[i + 1][0] * points[i][1];
    }
    area = Math.abs(area) / 2;
    
    // Centroid
    const centroidX = (minX + maxX) / 2;
    const centroidY = (minY + maxY) / 2;
    
    return {
      lot_width_ft: Math.round(lotWidth * 100) / 100,
      lot_depth_ft: Math.round(lotDepth * 100) / 100,
      lot_area_sf: Math.round(area * 100) / 100,
      lot_area_acres: Math.round((area / 43560) * 1000) / 1000,
      centroid_x: centroidX,
      centroid_y: centroidY,
      bbox: { minX, maxX, minY, maxY },
      point_count: points.length,
    };
  }

  /**
   * Query BCPAO for parcel geometries
   */
  async queryParcels(where, offset = 0) {
    const params = new URLSearchParams({
      where,
      outFields: "PARCELNO,ACCOUNT,OWNER,SITUS,LEGAL,USE_CODE,ACRES",
      returnGeometry: true,
      outSR: SR2881,
      f: "json",
      resultOffset: offset,
      resultRecordCount: this.batchSize,
    });

    try {
      const url = `${BCPAO_URL}/query?${params}`;
      const response = await fetch(url, {
        headers: { "User-Agent": "BidDeedAI-Surveyor/1.0" },
        signal: AbortSignal.timeout(30000),
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      if (data.error) throw new Error(data.error.message);
      return data.features || [];
    } catch (err) {
      console.error(`  ❌ BCPAO query failed (offset ${offset}): ${err.message}`);
      this.stats.errors++;
      return [];
    }
  }

  /**
   * Build where clause for municipality filtering
   */
  getWhereClause(municipality) {
    // Municipality-specific OBJECTID ranges or spatial filters
    // For county-wide, use simple pagination
    const muniFilters = {
      palm_bay:              "SITUS LIKE '%PALM BAY%' OR SITUS LIKE '%NE Palm Bay%'",
      melbourne:             "SITUS LIKE '%MELBOURNE%'",
      satellite_beach:       "SITUS LIKE '%SATELLITE%'",
      indian_harbour_beach:  "SITUS LIKE '%INDIAN HARBOUR%' OR SITUS LIKE '%IHB%'",
      cocoa_beach:           "SITUS LIKE '%COCOA BEACH%'",
      titusville:            "SITUS LIKE '%TITUSVILLE%'",
      cocoa:                 "SITUS LIKE '%COCOA%' AND SITUS NOT LIKE '%COCOA BEACH%'",
      rockledge:             "SITUS LIKE '%ROCKLEDGE%'",
      all:                   "1=1",
    };
    
    return muniFilters[municipality] || "1=1";
  }

  /**
   * Process a batch of parcel features
   */
  processBatch(features) {
    for (const feature of features) {
      this.stats.total++;
      const attrs = feature.attributes || {};
      const geometry = feature.geometry;
      
      const parcelId = attrs.PARCELNO || attrs.ACCOUNT;
      if (!parcelId) continue;
      
      let dimensions = null;
      if (geometry?.rings) {
        this.stats.withGeometry++;
        dimensions = this.computeLotDimensions(geometry.rings);
        if (dimensions) this.stats.computed++;
      }

      this.results.push({
        parcel_id: parcelId,
        account: attrs.ACCOUNT,
        owner: attrs.OWNER,
        situs: attrs.SITUS,
        use_code: attrs.USE_CODE,
        acres: attrs.ACRES,
        lot_width_ft: dimensions?.lot_width_ft || null,
        lot_depth_ft: dimensions?.lot_depth_ft || null,
        lot_area_sf: dimensions?.lot_area_sf || null,
        lot_area_acres: dimensions?.lot_area_acres || null,
        centroid_x_sr2881: dimensions?.centroid_x || null,
        centroid_y_sr2881: dimensions?.centroid_y || null,
        point_count: dimensions?.point_count || 0,
        surveyed_at: new Date().toISOString(),
      });
    }
  }

  /**
   * Run the full survey mission
   */
  async run() {
    console.log("📐 PARCEL SURVEYOR — Mission Start");
    console.log(`   Target: ${this.municipality}`);
    console.log(`   Source: BCPAO SR${SR2881}`);

    const where = this.getWhereClause(this.municipality);
    let offset = 0;
    let batch;
    let totalFetched = 0;

    do {
      batch = await this.queryParcels(where, offset);
      this.processBatch(batch);
      totalFetched += batch.length;
      offset += this.batchSize;
      
      process.stdout.write(`\r   Surveyed: ${totalFetched} parcels | Geometry: ${this.stats.withGeometry} | Computed: ${this.stats.computed}`);
      
      // Rate limiting
      if (batch.length > 0) {
        await new Promise(r => setTimeout(r, 200));
      }
    } while (batch.length === this.batchSize);
    
    console.log("");

    // Write JSONL output
    const dir = path.dirname(this.outputPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    
    const stream = fs.createWriteStream(this.outputPath);
    for (const record of this.results) {
      stream.write(JSON.stringify(record) + "\n");
    }
    stream.end();

    console.log("\n📐 PARCEL SURVEYOR — Mission Complete");
    console.log(`   Total parcels:    ${this.stats.total}`);
    console.log(`   With geometry:    ${this.stats.withGeometry}`);
    console.log(`   Dimensions computed: ${this.stats.computed}`);
    console.log(`   Errors:           ${this.stats.errors}`);
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
  
  const surveyor = new ParcelSurveyor(options);
  surveyor.run().catch(console.error);
}

module.exports = { ParcelSurveyor };

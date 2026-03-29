/**
 * ============================================================================
 * AGENT 1: ZONING SCOUT 🔍
 * ============================================================================
 * Mission: Extract zoning setbacks, height limits, FAR, lot coverage from
 *          municipal GIS layers across all Brevard County municipalities.
 * 
 * Data Sources:
 *   - Palm Bay:      gis.palmbayflorida.org/Zoning/MapServer/0
 *   - Melbourne:     gis.melbourneflorida.org (TBD endpoint)
 *   - Satellite Bch: Brevard County fallback
 *   - Unincorporated: Brevard County zoning ordinance defaults
 * 
 * Pipeline: ZoneWise Scraper V4 → Firecrawl → Gemini → Claude waterfall
 * Pattern:  cli-anything harness, summit YAML per municipality
 * ============================================================================
 */

const fs = require("fs");
const path = require("path");

// Brevard County zoning district → setback/height/FAR lookup
// Source: Brevard County Land Development Code + municipal ordinances
const ZONING_DISTRICTS = {
  // RESIDENTIAL
  "AU":    { front: 50, side: 25, rear: 50, maxHeight: 35, lotCoverage: 20, far: 0.15, desc: "Agricultural Use" },
  "SR":    { front: 30, side: 10, rear: 25, maxHeight: 35, lotCoverage: 30, far: 0.3,  desc: "Suburban Residential" },
  "RR-1":  { front: 25, side: 7.5, rear: 20, maxHeight: 35, lotCoverage: 35, far: 0.4, desc: "Rural Residential" },
  "RS-1":  { front: 25, side: 7.5, rear: 20, maxHeight: 35, lotCoverage: 40, far: 0.5, desc: "Single Family Residential" },
  "RS-2":  { front: 25, side: 7.5, rear: 20, maxHeight: 35, lotCoverage: 40, far: 0.5, desc: "Single Family Residential (small lot)" },
  "RS-3":  { front: 20, side: 5, rear: 15, maxHeight: 35, lotCoverage: 45, far: 0.55, desc: "Single Family Residential (compact)" },
  "RU-1":  { front: 25, side: 10, rear: 20, maxHeight: 35, lotCoverage: 40, far: 0.5, desc: "Residential Urban" },
  "RU-2":  { front: 25, side: 10, rear: 20, maxHeight: 45, lotCoverage: 45, far: 0.6, desc: "Residential Urban (medium)" },
  "RM-6":  { front: 25, side: 10, rear: 20, maxHeight: 45, lotCoverage: 50, far: 0.8, desc: "Multi-Family (6 units/acre)" },
  "RM-10": { front: 25, side: 15, rear: 20, maxHeight: 55, lotCoverage: 50, far: 1.0, desc: "Multi-Family (10 units/acre)" },
  "RM-15": { front: 25, side: 15, rear: 25, maxHeight: 65, lotCoverage: 55, far: 1.5, desc: "Multi-Family (15 units/acre)" },
  
  // COMMERCIAL
  "BU-1":  { front: 0, side: 0, rear: 10, maxHeight: 65, lotCoverage: 80, far: 2.0, desc: "General Commercial" },
  "BU-1-A":{ front: 0, side: 0, rear: 10, maxHeight: 65, lotCoverage: 80, far: 2.0, desc: "Limited Commercial" },
  "BU-2":  { front: 0, side: 0, rear: 5, maxHeight: 80, lotCoverage: 90, far: 3.0, desc: "Retail/Office/Mixed Use" },
  "CC":    { front: 0, side: 0, rear: 0, maxHeight: 100, lotCoverage: 95, far: 4.0, desc: "Community Commercial" },
  
  // INDUSTRIAL
  "IU":    { front: 25, side: 15, rear: 20, maxHeight: 50, lotCoverage: 60, far: 1.0, desc: "Light Industrial" },
  "IU-1":  { front: 25, side: 15, rear: 20, maxHeight: 50, lotCoverage: 60, far: 1.0, desc: "Industrial (limited)" },
  "IH":    { front: 30, side: 20, rear: 25, maxHeight: 65, lotCoverage: 65, far: 1.5, desc: "Heavy Industrial" },
  
  // SATELLITE BEACH MUNICIPAL CODES (R-series)
  "R-1":   { front: 25, side: 7.5, rear: 20, maxHeight: 35, lotCoverage: 40, far: 0.5, desc: "SB Single Family Residential" },
  "R-2":   { front: 25, side: 7.5, rear: 20, maxHeight: 35, lotCoverage: 40, far: 0.5, desc: "SB Single Family Residential (small)" },
  "RM-1":  { front: 25, side: 10, rear: 20, maxHeight: 45, lotCoverage: 50, far: 0.8, desc: "SB Multi-Family Residential" },
  "RM-2":  { front: 25, side: 10, rear: 25, maxHeight: 55, lotCoverage: 55, far: 1.0, desc: "SB Multi-Family (high density)" },
  "C-1":   { front: 0, side: 0, rear: 10, maxHeight: 65, lotCoverage: 80, far: 2.0, desc: "SB General Commercial" },
  "C-2":   { front: 0, side: 0, rear: 5, maxHeight: 80, lotCoverage: 90, far: 3.0, desc: "SB Highway Commercial" },
  "I-1":   { front: 25, side: 15, rear: 20, maxHeight: 50, lotCoverage: 60, far: 1.0, desc: "SB Light Industrial" },
  "PCS-2": { front: 20, side: 5, rear: 15, maxHeight: 45, lotCoverage: 50, far: 0.8, desc: "SB Planned Commercial/Special" },
  // GENERIC FALLBACK CODES
  "AG":    { front: 50, side: 25, rear: 50, maxHeight: 35, lotCoverage: 20, far: 0.15, desc: "Agricultural" },
  "RR-65": { front: 50, side: 25, rear: 50, maxHeight: 35, lotCoverage: 20, far: 0.15, desc: "Rural Residential (1 DU/65 acres)" },

  // PLANNED / SPECIAL
  "PUD":   { front: 20, side: 5, rear: 15, maxHeight: 45, lotCoverage: 50, far: 0.8, desc: "Planned Unit Development" },
  "PIP":   { front: 25, side: 15, rear: 20, maxHeight: 50, lotCoverage: 60, far: 1.0, desc: "Planned Industrial Park" },
  "TU-1":  { front: 15, side: 5, rear: 10, maxHeight: 55, lotCoverage: 60, far: 1.5, desc: "Traditional Urban" },
  "TU-2":  { front: 10, side: 5, rear: 10, maxHeight: 65, lotCoverage: 70, far: 2.0, desc: "Traditional Urban (core)" },
  "GU":    { front: 25, side: 7.5, rear: 20, maxHeight: 35, lotCoverage: 35, far: 0.4, desc: "General Use" },
  "SEU":   { front: 25, side: 7.5, rear: 20, maxHeight: 35, lotCoverage: 40, far: 0.5, desc: "Suburban Estate Use" },

  // FL MUNICIPAL B-SERIES COMMERCIAL (Titusville, Cocoa, and other FL cities)
  "B-1":   { front: 15, side: 0,    rear: 10, maxHeight: 35, lotCoverage: 70, far: 1.5, desc: "Neighborhood Commercial" },
  "B-2":   { front: 15, side: 0,    rear: 10, maxHeight: 45, lotCoverage: 75, far: 2.0, desc: "General Commercial" },
  "B-3":   { front: 15, side: 5,    rear: 15, maxHeight: 45, lotCoverage: 70, far: 1.5, desc: "Highway Commercial" },
  "B-4":   { front: 0,  side: 0,    rear: 0,  maxHeight: 65, lotCoverage: 90, far: 3.0, desc: "Central Business District" },
  "B-5":   { front: 0,  side: 0,    rear: 5,  maxHeight: 80, lotCoverage: 90, far: 4.0, desc: "Downtown Commercial" },

  // FL MUNICIPAL I-SERIES INDUSTRIAL
  "I-1":   { front: 25, side: 10,   rear: 15, maxHeight: 40, lotCoverage: 60, far: 1.0, desc: "Light Industrial" },
  "I-2":   { front: 30, side: 15,   rear: 20, maxHeight: 50, lotCoverage: 65, far: 1.5, desc: "Heavy Industrial" },

  // FL MUNICIPAL R-SERIES (Titusville, Cocoa, and other FL cities)
  "R-1A":  { front: 30, side: 10,   rear: 25, maxHeight: 35, lotCoverage: 30, far: 0.35, desc: "Single Family Residential (large lot)" },
  "R-1AA": { front: 35, side: 10,   rear: 30, maxHeight: 35, lotCoverage: 25, far: 0.30, desc: "Single Family Residential (estate lot)" },
  "R-2":   { front: 25, side: 7.5,  rear: 20, maxHeight: 35, lotCoverage: 40, far: 0.50, desc: "Two-Family Residential" },
  "R-3":   { front: 25, side: 8,    rear: 20, maxHeight: 40, lotCoverage: 50, far: 0.80, desc: "Multi-Family Residential" },
  "R-3A":  { front: 25, side: 8,    rear: 20, maxHeight: 40, lotCoverage: 50, far: 0.80, desc: "Multi-Family Residential (alt)" },
  "R-4":   { front: 20, side: 8,    rear: 15, maxHeight: 55, lotCoverage: 65, far: 1.50, desc: "High Density Multi-Family" },

  // COCOA BEACH SPECIFIC (coastal city RSF/RMF/CN codes)
  "RSF-1": { front: 20, side: 7.5,  rear: 15, maxHeight: 35, lotCoverage: 35, far: 0.45, desc: "CB Single Family (standard)" },
  "RSF-2": { front: 15, side: 5,    rear: 10, maxHeight: 35, lotCoverage: 40, far: 0.50, desc: "CB Single Family (small lot)" },
  "RMF-1": { front: 20, side: 7.5,  rear: 15, maxHeight: 40, lotCoverage: 50, far: 0.80, desc: "CB Multi-Family (low density)" },
  "RMF-2": { front: 20, side: 8,    rear: 15, maxHeight: 50, lotCoverage: 60, far: 1.20, desc: "CB Multi-Family (medium density)" },
  "RMF-3": { front: 20, side: 8,    rear: 15, maxHeight: 65, lotCoverage: 70, far: 2.00, desc: "CB Multi-Family (high density)" },
  "C-N":   { front: 15, side: 0,    rear: 10, maxHeight: 35, lotCoverage: 75, far: 1.50, desc: "CB Neighborhood Commercial" },
  "C-G":   { front: 15, side: 0,    rear: 10, maxHeight: 45, lotCoverage: 80, far: 2.50, desc: "CB General Commercial" },
  "C-T":   { front: 15, side: 5,    rear: 15, maxHeight: 45, lotCoverage: 75, far: 2.00, desc: "CB Tourist Commercial" },
  "CBD":   { front: 0,  side: 0,    rear: 0,  maxHeight: 65, lotCoverage: 90, far: 3.50, desc: "Central Business District" },

  // GENERIC FL MUNICIPAL FALLBACKS (A-series agricultural/residential)
  "A-1":   { front: 50, side: 25,   rear: 50, maxHeight: 35, lotCoverage: 20, far: 0.15, desc: "Agriculture" },
  "A-2":   { front: 50, side: 25,   rear: 50, maxHeight: 35, lotCoverage: 20, far: 0.15, desc: "Agriculture (rural)" },
  "R-O":   { front: 25, side: 7.5,  rear: 20, maxHeight: 35, lotCoverage: 40, far: 0.50, desc: "Residential Office" },
  "P":     { front: 25, side: 15,   rear: 25, maxHeight: 35, lotCoverage: 20, far: 0.10, desc: "Public/Institutional" },
  "OS":    { front: 25, side: 25,   rear: 25, maxHeight: 35, lotCoverage: 10, far: 0.05, desc: "Open Space" },
};

// Municipal GIS endpoint registry
const MUNICIPALITIES = {
  palm_bay: {
    name: "Palm Bay",
    gis_url: "https://gis.palmbayflorida.org/arcgis/rest/services/Zoning/MapServer/0",
    sr: 2881,
    parcel_count: 78000,
    status: "CONQUERED",
  },
  melbourne: {
    name: "Melbourne",
    gis_url: null, // TBD — needs GIS endpoint discovery
    sr: 2881,
    parcel_count: 45000,
    status: "PENDING",
  },
  satellite_beach: {
    name: "Satellite Beach",
    gis_url: null,
    sr: 2881,
    parcel_count: 5000,
    status: "PENDING",
  },
  indian_harbour_beach: {
    name: "Indian Harbour Beach",
    gis_url: null,
    sr: 2881,
    parcel_count: 4500,
    status: "PENDING",
  },
  cocoa_beach: {
    name: "Cocoa Beach",
    // AGOL — CBParcelsMaster2021 has Zoning field + Name for parcel ID
    gis_url: "https://services5.arcgis.com/U4PMgBw5XA2nmleg/arcgis/rest/services/CBParcelsMaster2021/FeatureServer/0",
    zone_field: "Zoning",
    parcel_id_field: "Name",
    sr: 2881,
    parcel_count: 10843,
    status: "CONQUERED",
  },
  titusville: {
    name: "Titusville",
    // City GIS — CommunityDevelopment/MapServer/15 has Zone_Code field
    gis_url: "https://gis.titusville.com/arcgis/rest/services/CommunityDevelopment/MapServer/15",
    zone_field: "Zone_Code",
    parcel_id_field: "PARCEL_ID",
    sr: 2881,
    parcel_count: 28118,
    status: "CONQUERED",
  },
  cocoa: {
    name: "Cocoa",
    // AGOL — Cocoa_Zoning_with_Split_Lots has Zoning field + Name for parcel ID
    gis_url: "https://services1.arcgis.com/Tex1uhbqnOZPx6qT/arcgis/rest/services/Cocoa_Zoning_with_Split_Lots/FeatureServer/0",
    zone_field: "Zoning",
    parcel_id_field: "Name",
    sr: 2881,
    parcel_count: 29882,
    status: "CONQUERED",
  },
  rockledge: {
    name: "Rockledge",
    gis_url: null,
    sr: 2881,
    parcel_count: 15000,
    status: "PENDING",
  },
  unincorporated: {
    name: "Unincorporated Brevard",
    gis_url: "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5",
    sr: 2881,
    parcel_count: 80000,
    status: "PARTIAL",
  },
};

class ZoningScout {
  constructor(options = {}) {
    this.municipality = options.municipality || "all";
    this.outputPath = options.output || "./data/envelope-3d/zoning_raw.jsonl";
    this.batchSize = 500;
    this.results = [];
    this.stats = { total: 0, matched: 0, unknown: 0, errors: 0 };
  }

  /**
   * Resolve zone code to setback parameters
   * Handles compound codes: "RS-1/PUD" → use RS-1 base with PUD overlay
   */
  resolveZoneCode(rawCode) {
    if (!rawCode) return null;
    
    const code = rawCode.trim().toUpperCase().replace(/\s+/g, "-");
    
    // Direct match
    if (ZONING_DISTRICTS[code]) {
      return { ...ZONING_DISTRICTS[code], zone_code: code, resolution: "direct" };
    }
    
    // Compound code: take first part
    if (code.includes("/")) {
      const primary = code.split("/")[0];
      if (ZONING_DISTRICTS[primary]) {
        return { ...ZONING_DISTRICTS[primary], zone_code: code, resolution: "compound_primary" };
      }
    }
    
    // Prefix match: "RS-1-A" → "RS-1"
    const prefixMatch = Object.keys(ZONING_DISTRICTS).find(k => code.startsWith(k));
    if (prefixMatch) {
      return { ...ZONING_DISTRICTS[prefixMatch], zone_code: code, resolution: "prefix" };
    }
    
    // FL pattern-based fallback — infer setbacks from first letter + category
    // This handles municipal codes not in ZONING_DISTRICTS lookup
    const flFallback = this.getFlPatternFallback(code);
    if (flFallback) {
      return { ...flFallback, zone_code: code, resolution: "fl_pattern_fallback" };
    }

    // Unknown — flag for manual review
    return {
      zone_code: code,
      front: null, side: null, rear: null,
      maxHeight: null, lotCoverage: null, far: null,
      desc: "UNKNOWN — requires manual mapping",
      resolution: "unknown",
    };
  }

  /**
   * FL pattern-based fallback for unrecognized zone codes.
   * Handles codes like "RS-1B", "RMF-4", "B-2A", "I-3", etc.
   * that vary by municipality but follow common FL patterns.
   */
  getFlPatternFallback(code) {
    const c = code.toUpperCase();
    // Industrial
    if (/^I[-_]?[0-9]/.test(c) || c.startsWith("IND") || c.startsWith("LI") || c.startsWith("IU"))
      return { front: 25, side: 10, rear: 15, maxHeight: 45, lotCoverage: 62, far: 1.0, desc: "Industrial (FL pattern fallback)" };
    // Commercial B-series
    if (/^B[-_]?[0-9]/.test(c) || c.startsWith("BC") || c.startsWith("CB") || c.startsWith("GC"))
      return { front: 15, side: 0, rear: 10, maxHeight: 45, lotCoverage: 75, far: 2.0, desc: "Commercial (FL pattern fallback)" };
    // Commercial C-series
    if (/^C[-_]?[0-9A-Z]/.test(c) && !c.startsWith("CBD"))
      return { front: 15, side: 0, rear: 10, maxHeight: 45, lotCoverage: 75, far: 2.0, desc: "Commercial C-series (FL pattern fallback)" };
    // Multi-family R or RMF
    if (/^R(MF|M|U-2|[-_]?[34])/.test(c))
      return { front: 20, side: 8, rear: 15, maxHeight: 45, lotCoverage: 55, far: 1.0, desc: "Multi-Family (FL pattern fallback)" };
    // Single-family R-series
    if (/^R[-_]?[1-2]/.test(c) || /^RS/.test(c) || /^RSF/.test(c))
      return { front: 25, side: 7.5, rear: 20, maxHeight: 35, lotCoverage: 35, far: 0.45, desc: "Single Family (FL pattern fallback)" };
    // Agricultural / large lot
    if (/^(A|AG|AU|AR|RE|EU|SR|RR)/.test(c))
      return { front: 50, side: 25, rear: 50, maxHeight: 35, lotCoverage: 20, far: 0.15, desc: "Agricultural/Estate (FL pattern fallback)" };
    // Institutional / public
    if (/^(P|INST|PARK|PF|CF|MH$)/.test(c))
      return { front: 25, side: 15, rear: 25, maxHeight: 35, lotCoverage: 20, far: 0.10, desc: "Public/Institutional (FL pattern fallback)" };
    return null;
  }

  /**
   * Query municipal GIS for parcels with zoning
   * Uses ArcGIS REST API query endpoint
   */
  async queryMunicipalGIS(municipality, offset = 0) {
    const config = MUNICIPALITIES[municipality];
    if (!config || !config.gis_url) {
      console.log(`  ⚠️  ${config?.name || municipality}: No GIS endpoint — using county fallback`);
      return [];
    }

    // Use per-municipality field names (AGOL endpoints may differ from ArcGIS MapServer)
    const zoneField = config.zone_field || "ZONING";
    const pidField = config.parcel_id_field || "PARCEL_ID";
    const outFields = [pidField, zoneField, "OBJECTID"].filter((v, i, a) => a.indexOf(v) === i).join(",");

    const params = new URLSearchParams({
      where: "1=1",
      outFields,
      returnGeometry: false,
      f: "json",
      resultOffset: offset,
      resultRecordCount: this.batchSize,
    });

    try {
      const url = `${config.gis_url}/query?${params}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.error) throw new Error(data.error.message || JSON.stringify(data.error));
      return data.features || [];
    } catch (err) {
      console.error(`  ❌ GIS query failed for ${config.name}: ${err.message}`);
      this.stats.errors++;
      return [];
    }
  }

  /**
   * Process parcels from ZoneWise Supabase data (already scraped)
   * Falls back to this when municipal GIS isn't directly queryable
   */
  async queryZoneWiseSupabase(municipality) {
    // Municipality → BCPAO section prefix for parcel_id filtering
    // BCPAO parcel_id section prefixes — first 2 digits of parcel_id
    // Source: envelope-conquest.yml PREFIX_MAP (authoritative)
    const SECTION_PREFIXES = {
      satellite_beach:      "20",  // was "27" — BUG FIX
      titusville:           "21",
      cocoa:                "22",  // was "23" — BUG FIX (was pointing to rockledge!)
      rockledge:            "23",
      cocoa_beach:          "24",
      melbourne:            "25",  // was "28" — BUG FIX
      palm_bay:             "26",  // "29" is also palm_bay (palm_bay_29)
      indian_harbour_beach: "20",  // satellite beach / IHB share prefix area
      unincorporated:       null, // no prefix filter — fetch all
    };
    const prefix = SECTION_PREFIXES[municipality];
    const filter = prefix ? `&parcel_id=like.${prefix}*` : "";
    try {
      // Table is parcel_zones, paginate up to 10K records
      let all = [];
      let offset = 0;
      const pageSize = 1000;
      while (true) {
        const url = `${process.env.SUPABASE_URL}/rest/v1/parcel_zones?select=parcel_id,zone_code${filter}&limit=${pageSize}&offset=${offset}`;
        const response = await fetch(url, {
          headers: {
            apikey: process.env.SUPABASE_SERVICE_ROLE_KEY,
            Authorization: `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY}`,
          },
        });
        if (!response.ok) break;
        const batch = await response.json();
        all = all.concat(batch);
        if (batch.length < pageSize) break;
        offset += pageSize;
      }
      return all;
    } catch (err) {
      console.error(`  ⚠️  ZoneWise Supabase query failed: ${err.message}`);
      return [];
    }
  }

  /**
   * Main extraction pipeline for one municipality
   */
  async extractMunicipality(municipality) {
    const config = MUNICIPALITIES[municipality];
    console.log(`\n  🏘️  ${config.name} (${config.status})`);
    
    let parcels = [];
    
    // Strategy 1: Direct GIS query
    if (config.gis_url && config.status === "CONQUERED") {
      let offset = 0;
      let batch;
      do {
        batch = await this.queryMunicipalGIS(municipality, offset);
        parcels = parcels.concat(batch);
        offset += this.batchSize;
        process.stdout.write(`\r    Fetched: ${parcels.length} parcels`);
      } while (batch.length === this.batchSize);
      console.log("");
    }
    
    // Strategy 2: ZoneWise Supabase data
    if (parcels.length === 0) {
      parcels = await this.queryZoneWiseSupabase(municipality);
      if (parcels.length > 0) {
        console.log(`    ZoneWise cache: ${parcels.length} parcels`);
      }
    }

    // Resolve each parcel's zone code to setback params
    for (const parcel of parcels) {
      // Handle different field names across GIS providers:
      // - ArcGIS MapServer: PARCEL_ID, ZONING or ZONE_CODE
      // - AGOL FeatureServer (Cocoa, Cocoa Beach): Name (parcel ID), Zoning
      // - Titusville CommunityDevelopment: Zone_Code
      const rawCode = parcel.attributes?.Zoning || parcel.attributes?.ZONING ||
                      parcel.attributes?.Zone_Code || parcel.attributes?.ZONE_CODE ||
                      parcel.zone_code;
      const parcelId = parcel.attributes?.PARCEL_ID || parcel.attributes?.Name ||
                       parcel.parcel_id;
      
      if (!parcelId) continue;
      
      const resolved = this.resolveZoneCode(rawCode);
      this.stats.total++;
      
      if (resolved?.resolution === "unknown") {
        this.stats.unknown++;
      } else {
        this.stats.matched++;
      }

      this.results.push({
        parcel_id: parcelId,
        source_municipality: municipality,
        zone_code: resolved?.zone_code || rawCode,
        front_setback_ft: resolved?.front,
        side_setback_ft: resolved?.side,
        rear_setback_ft: resolved?.rear,
        max_height_ft: resolved?.maxHeight,
        max_lot_coverage: resolved?.lotCoverage,
        far: resolved?.far,
        zone_description: resolved?.desc,
        resolution_method: resolved?.resolution || "none",
        scraped_at: new Date().toISOString(),
      });
    }
  }

  /**
   * Run the full scout mission
   */
  async run() {
    console.log("🔍 ZONING SCOUT — Mission Start");
    console.log(`   Target: ${this.municipality}`);

    const targets = this.municipality === "all"
      ? Object.keys(MUNICIPALITIES)
      : [this.municipality];

    for (const muni of targets) {
      if (!MUNICIPALITIES[muni]) {
        console.log(`  ⚠️  Unknown municipality: ${muni}`);
        continue;
      }
      await this.extractMunicipality(muni);
    }

    // Write JSONL output
    const dir = path.dirname(this.outputPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    
    const stream = fs.createWriteStream(this.outputPath);
    for (const record of this.results) {
      stream.write(JSON.stringify(record) + "\n");
    }
    stream.end();

    console.log("\n🔍 ZONING SCOUT — Mission Complete");
    console.log(`   Total parcels:  ${this.stats.total}`);
    console.log(`   Zone matched:   ${this.stats.matched} (${((this.stats.matched / Math.max(1, this.stats.total)) * 100).toFixed(1)}%)`);
    console.log(`   Unknown zones:  ${this.stats.unknown}`);
    console.log(`   Errors:         ${this.stats.errors}`);
    console.log(`   Output:         ${this.outputPath}`);
    
    return this.stats;
  }
}

// CLI execution
if (require.main === module) {
  const args = process.argv.slice(2);
  const options = {};
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i]?.replace(/^--/, "");
    options[key] = args[i + 1];
  }
  
  const scout = new ZoningScout(options);
  scout.run().catch(console.error);
}

module.exports = { ZoningScout, ZONING_DISTRICTS, MUNICIPALITIES };

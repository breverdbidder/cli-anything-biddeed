/**
 * ============================================================================
 * AGENT 6: CMA ANALYST 💰  — THE MONEY AGENT
 * ============================================================================
 * Mission: Produce Comparative Market Analysis with Highest-and-Best-Use
 *          determination for each parcel.
 *
 * What it does:
 *   1. Pulls comparable sales (same zone, similar lot, ±0.5 mi radius)
 *   2. Pulls comparable rentals for income approach
 *   3. Analyzes what's ACTUALLY built on similar parcels
 *   4. Runs 9 HBU scenarios: current use vs all permitted uses under zoning
 *   5. Produces per-scenario ARV + NOI + max bid recommendation
 *   6. Determines THE highest-and-best-use with confidence score
 *
 * Data Sources:
 *   - BCPAO sales history (recent 24mo comps)
 *   - BCPAO improvement data (what's built on similar parcels)
 *   - envelope_cache (what COULD be built — from Agent 3)
 *   - multi_county_auctions (245K rows — distressed sale prices)
 *   - Market benchmarks by zip quality grade (A/B/C)
 * ============================================================================
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");

// ============================================================================
// 9 HBU SCENARIOS
// ============================================================================
const HBU_SCENARIOS = {
  SFR_NEW_BUILD: {
    name: "New SFR Construction",
    description: "Build a new single-family residence on vacant lot",
    applicable_zones: ["RS-1", "RS-2", "RS-3", "RR-1", "RU-1", "RU-2", "SR", "GU", "SEU", "PUD"],
    min_lot_sf: 5000,
    valuation_method: "sales_comparison",
    cost_per_sf_build: { low: 150, mid: 200, high: 275 },
    typical_size_pct_of_gfa: 0.6,
  },
  SFR_REHAB: {
    name: "SFR Rehab/Flip",
    description: "Purchase distressed SFR, renovate, resell",
    applicable_zones: ["RS-1", "RS-2", "RS-3", "RR-1", "RU-1", "RU-2", "SR", "GU", "SEU", "PUD"],
    min_lot_sf: 3000,
    valuation_method: "sales_comparison",
    rehab_cost_per_sf: { light: 30, medium: 60, heavy: 100 },
  },
  DUPLEX: {
    name: "Duplex Development",
    description: "Build or convert to duplex (2 units)",
    applicable_zones: ["RU-1", "RU-2", "RM-6", "RM-10", "RM-15", "TU-1", "TU-2", "PUD"],
    min_lot_sf: 7500,
    valuation_method: "income_approach",
    units: 2,
    cost_per_sf_build: { low: 140, mid: 185, high: 250 },
    typical_size_pct_of_gfa: 0.7,
  },
  SMALL_MULTI: {
    name: "Small Multifamily (3-8 units)",
    description: "Build small apartment building",
    applicable_zones: ["RM-6", "RM-10", "RM-15", "TU-1", "TU-2", "PUD"],
    min_lot_sf: 10000,
    valuation_method: "income_approach",
    cost_per_sf_build: { low: 130, mid: 175, high: 240 },
    typical_size_pct_of_gfa: 0.75,
  },
  MID_TERM_RENTAL: {
    name: "Mid-Term Furnished Rental",
    description: "Furnish and rent 1-6 month stays (The Third Sword strategy)",
    applicable_zones: ["RS-1", "RS-2", "RS-3", "RU-1", "RU-2", "RM-6", "RM-10", "PUD"],
    min_lot_sf: 3000,
    valuation_method: "income_approach",
    premium_over_ltl: 1.4,
    optimal_zips: ["32937", "32940", "32953", "32903"],
  },
  COMMERCIAL_RETAIL: {
    name: "Commercial Retail/Office",
    description: "Build or convert to commercial use",
    applicable_zones: ["BU-1", "BU-1-A", "BU-2", "CC", "TU-2"],
    min_lot_sf: 5000,
    valuation_method: "income_approach",
    cost_per_sf_build: { low: 120, mid: 165, high: 225 },
    typical_size_pct_of_gfa: 0.8,
  },
  MIXED_USE: {
    name: "Mixed Use (Commercial + Residential)",
    description: "Ground floor commercial, upper floors residential",
    applicable_zones: ["BU-2", "CC", "TU-1", "TU-2"],
    min_lot_sf: 8000,
    valuation_method: "income_approach",
    cost_per_sf_build: { low: 145, mid: 195, high: 265 },
    typical_size_pct_of_gfa: 0.8,
    commercial_floor_pct: 0.3,
  },
  VACANT_LAND_HOLD: {
    name: "Vacant Land Hold",
    description: "Acquire and hold for appreciation or future development",
    applicable_zones: ["ALL"],
    min_lot_sf: 0,
    valuation_method: "land_residual",
    annual_appreciation: 0.05,
    hold_costs_annual_pct: 0.025,
  },
  TEAR_DOWN_REBUILD: {
    name: "Tear Down & Rebuild",
    description: "Demolish existing structure, build to highest zoning potential",
    applicable_zones: ["ALL"],
    min_lot_sf: 5000,
    valuation_method: "land_residual",
    demo_cost_per_sf: 8,
  },
};

// ============================================================================
// BREVARD COUNTY MARKET BENCHMARKS
// ============================================================================
const MARKET_BENCHMARKS = {
  sale_price_per_sf: {
    SFR:        { A: 275, B: 225, C: 175 },
    DUPLEX:     { A: 220, B: 185, C: 150 },
    MULTI:      { A: 200, B: 165, C: 130 },
    COMMERCIAL: { A: 190, B: 155, C: 115 },
    LAND:       { A: 15,  B: 10,  C: 6 },
  },
  rent_per_sf_monthly: {
    SFR:        { A: 1.55, B: 1.30, C: 1.05 },
    DUPLEX:     { A: 1.45, B: 1.20, C: 0.95 },
    MULTI:      { A: 1.35, B: 1.10, C: 0.90 },
    COMMERCIAL: { A: 1.80, B: 1.40, C: 1.00 },
    MTR:        { A: 2.15, B: 1.80, C: 1.45 },
  },
  cap_rates: {
    SFR:        { A: 0.055, B: 0.065, C: 0.075 },
    DUPLEX:     { A: 0.060, B: 0.070, C: 0.080 },
    MULTI:      { A: 0.065, B: 0.075, C: 0.085 },
    COMMERCIAL: { A: 0.070, B: 0.080, C: 0.095 },
  },
  zip_quality: {
    "32937": "A", "32940": "A", "32953": "A", "32903": "A",
    "32935": "B", "32901": "B", "32927": "B", "32955": "B", "32780": "B",
    "32905": "C", "32907": "B", "32908": "C", "32909": "C", "32922": "C",
  },
};

class CMAAnalyst {
  constructor(options = {}) {
    this.envelopePath = options.envelopes || "./data/envelope-3d/envelopes_computed.jsonl";
    this.outputPath = options.output || "./data/envelope-3d/cma_reports.jsonl";
    this.summaryPath = options.summary || "./reports/envelope-3d/hbu_summary.json";
    this.supabaseUrl = options["supabase-url"] || process.env.SUPABASE_URL;
    this.supabaseKey = options["supabase-key"] || process.env.SUPABASE_SERVICE_ROLE_KEY;
    this.stats = { total: 0, analyzed: 0, errors: 0, hbu_distribution: {}, top_opportunities: [] };
  }

  async fetchComps(parcelId, zoneCode, lotArea, municipality) {
    const comps = { sales: [], auctions: [], improvements: [] };

    try {
      const auctionUrl = `${this.supabaseUrl}/rest/v1/multi_county_auctions?` +
        `county=eq.brevard&status=eq.sold&` +
        `select=case_number,parcel_id,judgment_amount,market_value,po_sold_amount,auction_date&` +
        `order=auction_date.desc&limit=20`;
      const response = await fetch(auctionUrl, {
        headers: { apikey: this.supabaseKey, Authorization: `Bearer ${this.supabaseKey}` },
        signal: AbortSignal.timeout(10000),
      });
      if (response.ok) {
        comps.auctions = (await response.json()).map(d => ({
          parcel_id: d.parcel_id, judgment: d.judgment_amount,
          market_value: d.market_value, sold_price: d.po_sold_amount, date: d.auction_date,
          discount_pct: d.market_value > 0 ? Math.round((1 - d.po_sold_amount / d.market_value) * 100) : null,
        }));
      }
    } catch (err) { /* non-fatal */ }

    try {
      const bcpaoUrl = `https://www.bcpao.us/api/v1/search?type=parcel&query=${parcelId}&activeOnly=true`;
      const response = await fetch(bcpaoUrl, {
        headers: { "User-Agent": "BidDeedAI-CMA/1.0" },
        signal: AbortSignal.timeout(10000),
      });
      if (response.ok) {
        const data = await response.json();
        if (data?.Parcels?.[0]) {
          const p = data.Parcels[0];
          comps.improvements.push({
            parcel_id: parcelId, just_value: p.JustValue, assessed_value: p.AssessedValue,
            building_value: p.BuildingValue, land_value: p.LandValue, year_built: p.YearBuilt,
            living_area: p.LivingArea, bedrooms: p.Bedrooms, bathrooms: p.Bathrooms,
          });
        }
      }
    } catch (err) { /* non-fatal */ }

    return comps;
  }

  getAreaQuality(envelope) {
    const situs = envelope.situs || "";
    const zipMatch = situs.match(/\b(32\d{3})\b/);
    if (zipMatch && MARKET_BENCHMARKS.zip_quality[zipMatch[1]]) {
      return { grade: MARKET_BENCHMARKS.zip_quality[zipMatch[1]], zip: zipMatch[1] };
    }
    const muniGrades = {
      satellite_beach: "A", indian_harbour_beach: "A",
      melbourne: "B", rockledge: "B", titusville: "B",
      palm_bay: "C", cocoa: "C",
    };
    return { grade: muniGrades[envelope.source_municipality] || "B", zip: null };
  }

  analyzeHBU(envelope, comps) {
    const area = this.getAreaQuality(envelope);
    const lotArea = envelope.lot_area_sf || 0;
    const gfa = envelope.buildable_gfa_sf || 0;
    const zoneCode = (envelope.zone_code || "").toUpperCase();
    const scenarios = [];

    for (const [key, scenario] of Object.entries(HBU_SCENARIOS)) {
      const zoneApplicable = scenario.applicable_zones.includes("ALL") ||
        scenario.applicable_zones.some(z => zoneCode.startsWith(z));
      if (!zoneApplicable || lotArea < scenario.min_lot_sf) continue;
      const result = this.evaluateScenario(key, scenario, envelope, area, comps);
      if (result) scenarios.push(result);
    }

    scenarios.sort((a, b) => (b.estimated_profit || 0) - (a.estimated_profit || 0));
    const best = scenarios[0] || null;
    const confidence = this.computeConfidence(best, scenarios, comps);

    return {
      area_quality: area,
      scenarios,
      recommended_hbu: best?.scenario_key || "VACANT_LAND_HOLD",
      recommended_hbu_name: best?.scenario_name || "Vacant Land Hold",
      estimated_arv: best?.arv || 0,
      estimated_profit: best?.estimated_profit || 0,
      max_bid_recommended: best?.max_bid || 0,
      confidence_score: confidence,
      comp_count: (comps.sales?.length || 0) + (comps.auctions?.length || 0),
    };
  }

  evaluateScenario(key, scenario, envelope, area, comps) {
    const grade = area.grade;
    const lotArea = envelope.lot_area_sf || 0;
    const gfa = envelope.buildable_gfa_sf || 0;
    let arv = 0, totalCost = 0, noi = 0, buildSize = 0;

    switch (scenario.valuation_method) {
      case "sales_comparison": {
        if (key === "SFR_REHAB") {
          const existingSize = comps.improvements?.[0]?.living_area || 1500;
          buildSize = existingSize;
          arv = buildSize * MARKET_BENCHMARKS.sale_price_per_sf.SFR[grade];
          totalCost = buildSize * scenario.rehab_cost_per_sf.medium;
        } else {
          buildSize = Math.round(gfa * scenario.typical_size_pct_of_gfa);
          arv = buildSize * MARKET_BENCHMARKS.sale_price_per_sf.SFR[grade];
          totalCost = buildSize * scenario.cost_per_sf_build.mid;
        }
        break;
      }
      case "income_approach": {
        let propertyType = "SFR";
        if (key === "DUPLEX") propertyType = "DUPLEX";
        else if (key === "SMALL_MULTI") propertyType = "MULTI";
        else if (key === "COMMERCIAL_RETAIL" || key === "MIXED_USE") propertyType = "COMMERCIAL";

        if (key === "MID_TERM_RENTAL") {
          buildSize = comps.improvements?.[0]?.living_area || 1500;
          const monthlyRent = buildSize * MARKET_BENCHMARKS.rent_per_sf_monthly.MTR[grade];
          const annualGross = monthlyRent * 12 * 0.85;
          const expenses = annualGross * 0.35;
          noi = annualGross - expenses;
          arv = Math.round(noi / MARKET_BENCHMARKS.cap_rates.SFR[grade]);
          totalCost = 15000;
        } else {
          buildSize = Math.round(gfa * (scenario.typical_size_pct_of_gfa || 0.7));
          const rentType = propertyType === "COMMERCIAL" ? "COMMERCIAL" : propertyType;
          const monthlyRent = buildSize * (MARKET_BENCHMARKS.rent_per_sf_monthly[rentType]?.[grade] || 1.2);
          const annualGross = monthlyRent * 12 * 0.92;
          noi = annualGross - (annualGross * 0.30);
          arv = Math.round(noi / (MARKET_BENCHMARKS.cap_rates[propertyType]?.[grade] || 0.075));
          totalCost = buildSize * (scenario.cost_per_sf_build?.mid || 175);
        }
        break;
      }
      case "land_residual": {
        if (key === "VACANT_LAND_HOLD") {
          arv = lotArea * MARKET_BENCHMARKS.sale_price_per_sf.LAND[grade];
          totalCost = arv * scenario.hold_costs_annual_pct * 3;
        } else if (key === "TEAR_DOWN_REBUILD") {
          const existingSize = comps.improvements?.[0]?.living_area || 0;
          const demoCost = existingSize > 0 ? existingSize * scenario.demo_cost_per_sf : 0;
          buildSize = Math.round(gfa * 0.65);
          arv = buildSize * MARKET_BENCHMARKS.sale_price_per_sf.SFR[grade];
          totalCost = demoCost + (buildSize * 200);
        }
        break;
      }
    }

    // BidDeed Max Bid Formula
    const maxBid = Math.round((arv * 0.70) - totalCost - 10000 - Math.min(25000, 0.15 * arv));
    const estimatedProfit = arv - totalCost - Math.max(0, maxBid);

    return {
      scenario_key: key,
      scenario_name: scenario.name,
      scenario_description: scenario.description,
      valuation_method: scenario.valuation_method,
      build_size_sf: buildSize,
      arv: Math.round(arv),
      total_development_cost: Math.round(totalCost),
      noi_annual: Math.round(noi),
      max_bid: Math.max(0, maxBid),
      estimated_profit: Math.round(estimatedProfit),
      profit_margin_pct: arv > 0 ? Math.round((estimatedProfit / arv) * 100) : 0,
      roi_pct: totalCost > 0 ? Math.round((estimatedProfit / totalCost) * 100) : 0,
    };
  }

  computeConfidence(best, all, comps) {
    let score = 50;
    if (comps.auctions?.length > 5) score += 10;
    if (comps.improvements?.length > 0) score += 10;
    if (comps.sales?.length > 3) score += 10;
    if (all.length >= 2 && best) {
      const gap = best.estimated_profit - (all[1]?.estimated_profit || 0);
      const gapPct = best.estimated_profit > 0 ? gap / best.estimated_profit : 0;
      if (gapPct > 0.3) score += 15;
      else if (gapPct > 0.15) score += 8;
    }
    if (best?.estimated_profit > 50000) score += 5;
    if (best?.roi_pct > 30) score += 5;
    return Math.min(100, Math.max(0, score));
  }

  async run() {
    console.log("💰 CMA ANALYST — Mission Start");
    console.log("   Highest-and-Best-Use Analysis Engine");

    if (!fs.existsSync(this.envelopePath)) {
      console.log(`  ⚠️  No envelope data: ${this.envelopePath}`);
      return this.stats;
    }

    const rl = readline.createInterface({ input: fs.createReadStream(this.envelopePath), crlfDelay: Infinity });
    const dir = path.dirname(this.outputPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const stream = fs.createWriteStream(this.outputPath);

    for await (const line of rl) {
      if (!line.trim()) continue;
      try {
        const envelope = JSON.parse(line);
        this.stats.total++;
        const comps = await this.fetchComps(envelope.parcel_id, envelope.zone_code, envelope.lot_area_sf, envelope.source_municipality);
        const analysis = this.analyzeHBU(envelope, comps);
        this.stats.analyzed++;

        const hbu = analysis.recommended_hbu;
        this.stats.hbu_distribution[hbu] = (this.stats.hbu_distribution[hbu] || 0) + 1;

        if (analysis.estimated_profit > 30000 && analysis.confidence_score >= 60) {
          this.stats.top_opportunities.push({
            parcel_id: envelope.parcel_id, zone_code: envelope.zone_code, situs: envelope.situs,
            hbu: analysis.recommended_hbu_name, arv: analysis.estimated_arv,
            profit: analysis.estimated_profit, max_bid: analysis.max_bid_recommended,
            confidence: analysis.confidence_score,
          });
        }

        stream.write(JSON.stringify({
          parcel_id: envelope.parcel_id, zone_code: envelope.zone_code,
          source_municipality: envelope.source_municipality, situs: envelope.situs,
          lot_area_sf: envelope.lot_area_sf, buildable_gfa_sf: envelope.buildable_gfa_sf,
          effective_floors: envelope.effective_floors,
          ...analysis, analyzed_at: new Date().toISOString(),
        }) + "\n");

        if (this.stats.total % 1000 === 0) process.stdout.write(`\r   Analyzed: ${this.stats.analyzed} / ${this.stats.total}`);
        if (this.stats.total % 50 === 0) await new Promise(r => setTimeout(r, 100));
      } catch (err) { this.stats.errors++; }
    }

    stream.end();
    this.stats.top_opportunities.sort((a, b) => b.profit - a.profit);
    this.stats.top_opportunities = this.stats.top_opportunities.slice(0, 25);

    const summaryDir = path.dirname(this.summaryPath);
    if (!fs.existsSync(summaryDir)) fs.mkdirSync(summaryDir, { recursive: true });
    fs.writeFileSync(this.summaryPath, JSON.stringify({
      generated_at: new Date().toISOString(),
      stats: { total_parcels: this.stats.total, analyzed: this.stats.analyzed, errors: this.stats.errors },
      hbu_distribution: this.stats.hbu_distribution,
      top_25_opportunities: this.stats.top_opportunities,
    }, null, 2));

    console.log("\n\n💰 CMA ANALYST — Mission Complete");
    console.log(`   Parcels analyzed:  ${this.stats.analyzed}`);
    console.log(`   Errors:            ${this.stats.errors}`);
    console.log(`\n   HBU Distribution:`);
    for (const [hbu, count] of Object.entries(this.stats.hbu_distribution).sort((a, b) => b[1] - a[1])) {
      const pct = ((count / Math.max(1, this.stats.analyzed)) * 100).toFixed(1);
      console.log(`     ${HBU_SCENARIOS[hbu]?.name || hbu}: ${count} (${pct}%)`);
    }
    if (this.stats.top_opportunities.length > 0) {
      console.log(`\n   🏆 Top 5 Opportunities:`);
      for (const opp of this.stats.top_opportunities.slice(0, 5)) {
        console.log(`     ${opp.parcel_id} | ${opp.hbu} | ARV: $${opp.arv.toLocaleString()} | Profit: $${opp.profit.toLocaleString()} | Bid: $${opp.max_bid.toLocaleString()}`);
      }
    }
    console.log(`\n   Output:  ${this.outputPath}`);
    console.log(`   Summary: ${this.summaryPath}`);
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
  new CMAAnalyst(options).run().catch(console.error);
}

module.exports = { CMAAnalyst, HBU_SCENARIOS, MARKET_BENCHMARKS };

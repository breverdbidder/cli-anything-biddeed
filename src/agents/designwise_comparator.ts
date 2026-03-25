#!/usr/bin/env node
/**
 * DesignWise Comparator — Generic Platform Comparison Agent
 * cli-anything harness: cli_anything.designwise_comparator
 *
 * Commands:
 *   designwise compare --platforms "ZoneWise,PropZone,Reonomy,CoStar" --category zoning
 *   designwise matrix --category <category>          Feature matrix for category
 *   designwise score --platform <platform>           Detailed score breakdown
 *   designwise export --platforms "..." --category "..." --out <file>
 *
 * Reuses the same visual engine as parity_engine.ts
 */

import { writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";

// ─── Types ────────────────────────────────────────────────────────────────────
type Category = "zoning" | "data" | "ai" | "pricing" | "api" | "ux";

interface FeatureScore {
  dataCoverage: number;
  uiUx: number;
  aiCapabilities: number;
  pricing: number;    // Higher = better value (inverted from cost)
  apiAccess: number;
  mobile: number;
  integrations: number;
}

interface PlatformDef {
  name: string;
  tagline: string;
  url: string;
  type: "saas" | "api" | "free" | "enterprise";
  scores: FeatureScore;
  features: Record<Category, FeatureDetail[]>;
  pricing: string;
  coverage: string;
  founded: string;
}

interface FeatureDetail {
  name: string;
  status: "yes" | "partial" | "no" | "beta";
  note: string;
}

interface CompareOptions {
  platforms: string[];
  category: Category;
  outputFile?: string;
}

// ─── Platform Database ────────────────────────────────────────────────────────
const PLATFORM_DB: Record<string, PlatformDef> = {
  ZoneWise: {
    name: "ZoneWise",
    tagline: "AI-powered zoning intelligence for FL investors",
    url: "zonewise.biddeed.ai",
    type: "free",
    pricing: "Free (BidDeed.AI suite)",
    coverage: "67 FL counties",
    founded: "2024",
    scores: {
      dataCoverage: 78, uiUx: 90, aiCapabilities: 95,
      pricing: 100, apiAccess: 70, mobile: 85, integrations: 60,
    },
    features: {
      zoning: [
        { name: "Zone Code Lookup",      status: "yes",     note: "All 67 FL counties" },
        { name: "Zone Description",      status: "partial", note: "~80% coverage" },
        { name: "Overlay Layers",        status: "no",      note: "P1 roadmap item" },
        { name: "Setback Matrix",        status: "partial", note: "Available ~65% parcels" },
        { name: "Capacity (FAR/Height)", status: "partial", note: "~70% coverage" },
        { name: "Permitted Uses",        status: "no",      note: "P1 roadmap item" },
        { name: "AI Zoning Q&A",         status: "yes",     note: "GPT-4 powered chatbot" },
        { name: "3D Massing Preview",    status: "yes",     note: "Three.js live render" },
      ],
      data: [
        { name: "Parcel Data (BCPAO)",   status: "yes",     note: "61-field card" },
        { name: "Owner + Valuation",     status: "yes",     note: "From BCPAO" },
        { name: "Sales History",         status: "partial", note: "BCPAO transfers" },
        { name: "Tax Records",           status: "yes",     note: "Assessed + market value" },
        { name: "Building Permits",      status: "no",      note: "Not yet integrated" },
        { name: "Environmental Flags",   status: "no",      note: "Future roadmap" },
      ],
      ai: [
        { name: "Natural Language Q&A",  status: "yes",     note: "Ask any zoning question" },
        { name: "Investment Analysis",   status: "yes",     note: "ARV, bid, ROI model" },
        { name: "Comparable Sales",      status: "partial", note: "Limited comp dataset" },
        { name: "Risk Scoring",          status: "beta",    note: "ML model in beta" },
        { name: "Automated Reports",     status: "beta",    note: "PDF export P1" },
      ],
      pricing: [
        { name: "Free Tier",             status: "yes",     note: "Full access free" },
        { name: "API Access",            status: "partial", note: "Internal only today" },
        { name: "Enterprise Plan",       status: "no",      note: "Roadmap Q3 2026" },
      ],
      api: [
        { name: "REST API",              status: "partial", note: "Internal endpoints" },
        { name: "Webhooks",              status: "no",      note: "Roadmap" },
        { name: "Bulk Export",           status: "yes",     note: "Via CLI harness" },
      ],
      ux: [
        { name: "Mobile Responsive",     status: "yes",     note: "Tailwind responsive" },
        { name: "Dark Mode",             status: "yes",     note: "Default dark" },
        { name: "Map Interface",         status: "yes",     note: "Mapbox GL" },
        { name: "Print/Export",          status: "partial", note: "HTML export; PDF P1" },
      ],
    },
  },

  PropZone: {
    name: "PropZone (Gridics)",
    tagline: "Zoning compliance & capacity platform",
    url: "propzone.gridics.com",
    type: "saas",
    pricing: "$299-999/mo (city license)",
    coverage: "~50 US cities (6 FL)",
    founded: "2016",
    scores: {
      dataCoverage: 85, uiUx: 72, aiCapabilities: 35,
      pricing: 25, apiAccess: 55, mobile: 60, integrations: 70,
    },
    features: {
      zoning: [
        { name: "Zone Code Lookup",      status: "yes",     note: "Full code integration" },
        { name: "Zone Description",      status: "yes",     note: "Plain-language text" },
        { name: "Overlay Layers",        status: "yes",     note: "Flood, historic, CRA" },
        { name: "Setback Matrix",        status: "yes",     note: "Full front/side/rear/water" },
        { name: "Capacity (FAR/Height)", status: "yes",     note: "Complete capacity matrix" },
        { name: "Permitted Uses",        status: "yes",     note: "Full use table" },
        { name: "AI Zoning Q&A",         status: "no",      note: "No AI features" },
        { name: "3D Massing Preview",    status: "no",      note: "No 3D visualization" },
      ],
      data: [
        { name: "Parcel Data (BCPAO)",   status: "yes",     note: "Via county API" },
        { name: "Owner + Valuation",     status: "partial", note: "Basic owner data" },
        { name: "Sales History",         status: "no",      note: "Not included" },
        { name: "Tax Records",           status: "partial", note: "Assessed value only" },
        { name: "Building Permits",      status: "no",      note: "Not integrated" },
        { name: "Environmental Flags",   status: "partial", note: "Flood zones only" },
      ],
      ai: [
        { name: "Natural Language Q&A",  status: "no",      note: "No AI" },
        { name: "Investment Analysis",   status: "no",      note: "No AI analysis" },
        { name: "Comparable Sales",      status: "no",      note: "Not available" },
        { name: "Risk Scoring",          status: "no",      note: "Not available" },
        { name: "Automated Reports",     status: "partial", note: "Basic PDF export" },
      ],
      pricing: [
        { name: "Free Tier",             status: "no",      note: "No free tier" },
        { name: "API Access",            status: "yes",     note: "API available (paid)" },
        { name: "Enterprise Plan",       status: "yes",     note: "City-wide licenses" },
      ],
      api: [
        { name: "REST API",              status: "yes",     note: "Documented API" },
        { name: "Webhooks",              status: "partial", note: "Limited webhooks" },
        { name: "Bulk Export",           status: "yes",     note: "CSV/JSON export" },
      ],
      ux: [
        { name: "Mobile Responsive",     status: "partial", note: "Desktop-first" },
        { name: "Dark Mode",             status: "no",      note: "Light only" },
        { name: "Map Interface",         status: "yes",     note: "Mapbox + vector tiles" },
        { name: "Print/Export",          status: "yes",     note: "PDF reports" },
      ],
    },
  },

  Reonomy: {
    name: "Reonomy",
    tagline: "Commercial real estate data intelligence",
    url: "reonomy.com",
    type: "enterprise",
    pricing: "$500-2000+/mo (enterprise)",
    coverage: "National (US CRE)",
    founded: "2013",
    scores: {
      dataCoverage: 90, uiUx: 72, aiCapabilities: 55,
      pricing: 15, apiAccess: 85, mobile: 65, integrations: 85,
    },
    features: {
      zoning: [
        { name: "Zone Code Lookup",      status: "partial", note: "Basic code only" },
        { name: "Zone Description",      status: "no",      note: "Not available" },
        { name: "Overlay Layers",        status: "no",      note: "Not available" },
        { name: "Setback Matrix",        status: "no",      note: "Not available" },
        { name: "Capacity (FAR/Height)", status: "no",      note: "Not available" },
        { name: "Permitted Uses",        status: "no",      note: "Not available" },
        { name: "AI Zoning Q&A",         status: "no",      note: "Not available" },
        { name: "3D Massing Preview",    status: "no",      note: "Not available" },
      ],
      data: [
        { name: "Parcel Data",           status: "yes",     note: "National parcel database" },
        { name: "Owner + Valuation",     status: "yes",     note: "Ownership graph + value" },
        { name: "Sales History",         status: "yes",     note: "Full transaction history" },
        { name: "Tax Records",           status: "yes",     note: "Complete tax history" },
        { name: "Building Permits",      status: "yes",     note: "Permit history" },
        { name: "Environmental Flags",   status: "partial", note: "Limited env data" },
      ],
      ai: [
        { name: "Natural Language Q&A",  status: "no",      note: "No conversational AI" },
        { name: "Investment Analysis",   status: "partial", note: "Basic scoring" },
        { name: "Comparable Sales",      status: "yes",     note: "Strong comp engine" },
        { name: "Risk Scoring",          status: "yes",     note: "Proprietary risk score" },
        { name: "Automated Reports",     status: "yes",     note: "PDF + data exports" },
      ],
      pricing: [
        { name: "Free Tier",             status: "no",      note: "No free tier" },
        { name: "API Access",            status: "yes",     note: "Robust API" },
        { name: "Enterprise Plan",       status: "yes",     note: "Enterprise contracts" },
      ],
      api: [
        { name: "REST API",              status: "yes",     note: "Full REST API" },
        { name: "Webhooks",              status: "yes",     note: "Event webhooks" },
        { name: "Bulk Export",           status: "yes",     note: "Bulk data feeds" },
      ],
      ux: [
        { name: "Mobile Responsive",     status: "partial", note: "Tablet-friendly" },
        { name: "Dark Mode",             status: "no",      note: "Light only" },
        { name: "Map Interface",         status: "yes",     note: "Good map UI" },
        { name: "Print/Export",          status: "yes",     note: "PDF + CSV" },
      ],
    },
  },

  CoStar: {
    name: "CoStar",
    tagline: "Commercial real estate information standard",
    url: "costar.com",
    type: "enterprise",
    pricing: "$5000-20000+/mo (enterprise seat)",
    coverage: "National + International",
    founded: "1987",
    scores: {
      dataCoverage: 95, uiUx: 62, aiCapabilities: 50,
      pricing: 5, apiAccess: 80, mobile: 55, integrations: 90,
    },
    features: {
      zoning: [
        { name: "Zone Code Lookup",      status: "partial", note: "Limited zoning data" },
        { name: "Zone Description",      status: "no",      note: "Not a focus" },
        { name: "Overlay Layers",        status: "no",      note: "Not available" },
        { name: "Setback Matrix",        status: "no",      note: "Not available" },
        { name: "Capacity (FAR/Height)", status: "no",      note: "Not available" },
        { name: "Permitted Uses",        status: "no",      note: "Not available" },
        { name: "AI Zoning Q&A",         status: "no",      note: "No zoning AI" },
        { name: "3D Massing Preview",    status: "no",      note: "Not available" },
      ],
      data: [
        { name: "Parcel Data",           status: "yes",     note: "Deep CRE data" },
        { name: "Owner + Valuation",     status: "yes",     note: "Extensive ownership data" },
        { name: "Sales History",         status: "yes",     note: "Comprehensive history" },
        { name: "Tax Records",           status: "yes",     note: "Full tax data" },
        { name: "Building Permits",      status: "yes",     note: "National permit data" },
        { name: "Environmental Flags",   status: "yes",     note: "Phase I/II reports" },
      ],
      ai: [
        { name: "Natural Language Q&A",  status: "no",      note: "No conversational AI" },
        { name: "Investment Analysis",   status: "partial", note: "Stacking analysis tools" },
        { name: "Comparable Sales",      status: "yes",     note: "Industry-leading comps" },
        { name: "Risk Scoring",          status: "yes",     note: "Cap rate + risk tools" },
        { name: "Automated Reports",     status: "yes",     note: "Professional reports" },
      ],
      pricing: [
        { name: "Free Tier",             status: "no",      note: "Enterprise only" },
        { name: "API Access",            status: "yes",     note: "CoStar API (paid)" },
        { name: "Enterprise Plan",       status: "yes",     note: "Per-seat licensing" },
      ],
      api: [
        { name: "REST API",              status: "yes",     note: "Full CoStar API" },
        { name: "Webhooks",              status: "partial", note: "Limited webhooks" },
        { name: "Bulk Export",           status: "yes",     note: "Data subscriptions" },
      ],
      ux: [
        { name: "Mobile Responsive",     status: "no",      note: "Desktop-first" },
        { name: "Dark Mode",             status: "no",      note: "Light only" },
        { name: "Map Interface",         status: "yes",     note: "Comprehensive map" },
        { name: "Print/Export",          status: "yes",     note: "Professional exports" },
      ],
    },
  },
};

// ─── HTML Report Generator ────────────────────────────────────────────────────
function generateCompareHTML(opts: CompareOptions): string {
  const platforms = opts.platforms
    .map((p) => PLATFORM_DB[p])
    .filter(Boolean);

  if (platforms.length < 2) {
    throw new Error(`Need at least 2 valid platforms. Available: ${Object.keys(PLATFORM_DB).join(", ")}`);
  }

  const category = opts.category;
  const now = new Date().toLocaleDateString("en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  });

  const COLORS: Record<string, string> = {
    ZoneWise: "#F59E0B",
    PropZone: "#60A5FA",
    Reonomy: "#34D399",
    CoStar:   "#A78BFA",
  };

  function scoreRing(pct: number, label: string, color: string): string {
    const r = 44;
    const circ = 2 * Math.PI * r;
    const offset = circ - (pct / 100) * circ;
    return `<svg width="110" height="110" viewBox="0 0 110 110">
      <circle cx="55" cy="55" r="${r}" fill="none" stroke="#1E3A5F" stroke-width="9"/>
      <circle cx="55" cy="55" r="${r}" fill="none" stroke="${color}" stroke-width="9"
        stroke-dasharray="${circ.toFixed(2)}" stroke-dashoffset="${offset.toFixed(2)}"
        stroke-linecap="round" transform="rotate(-90 55 55)"/>
      <text x="55" y="51" text-anchor="middle" fill="white" font-size="17" font-weight="700" font-family="Inter,sans-serif">${pct}</text>
      <text x="55" y="67" text-anchor="middle" fill="#94A3B8" font-size="9" font-family="Inter,sans-serif">${label}</text>
    </svg>`;
  }

  const featureCategories = Object.keys(platforms[0].scores) as (keyof FeatureScore)[];

  const featureMatrixRows = platforms[0].features[category].map((feat, i) => {
    const cells = platforms.map((p) => {
      const f = p.features[category][i];
      if (!f) return `<td>—</td>`;
      const icon = f.status === "yes" ? "✅"
        : f.status === "partial" ? "◐"
        : f.status === "beta" ? "🔬"
        : "○";
      const cls = f.status === "yes" ? "s-yes"
        : f.status === "partial" ? "s-partial"
        : f.status === "beta" ? "s-beta"
        : "s-no";
      return `<td class="${cls}" title="${f.note}">${icon} <small>${f.note}</small></td>`;
    }).join("");
    return `<tr><td class="feat-name">${feat.name}</td>${cells}</tr>`;
  }).join("\n");

  const platformHeaders = platforms.map((p) =>
    `<th style="color:${COLORS[p.name] || "#F59E0B"}">${p.name}</th>`
  ).join("");

  const scoreBarRows = featureCategories.map((fc) => {
    const bars = platforms.map((p) => {
      const v = p.scores[fc];
      const color = COLORS[p.name] || "#F59E0B";
      return `<div class="bar-wrap">
        <div class="bar-label"><span style="color:${color}">${p.name}</span><span>${v}</span></div>
        <div class="bar-bg"><div class="bar-fill" style="width:${v}%;background:${color}"></div></div>
      </div>`;
    }).join("");
    const label = fc.replace(/([A-Z])/g, " $1").trim();
    return `<div class="score-section"><h4>${label}</h4>${bars}</div>`;
  }).join("\n");

  const ringRow = platforms.map((p) => {
    const overall = Math.round(
      Object.values(p.scores).reduce((a, b) => a + b, 0) / Object.values(p.scores).length
    );
    return `<div class="ring-item">${scoreRing(overall, p.name.split(" ")[0], COLORS[p.name] || "#F59E0B")}</div>`;
  }).join("");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DesignWise Platform Comparator — ${opts.platforms.join(" vs ")} (${category})</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#1E3A5F;--orange:#F59E0B;--slate:#0F172A;--green:#22C55E;--red:#EF4444;--text:#E2E8F0;--muted:#94A3B8;--border:#1E3A5F;--card:#0F172A}
body{background:var(--slate);color:var(--text);font-family:Inter,system-ui,sans-serif;font-size:14px;line-height:1.5}
h1,h2,h3,h4{font-weight:700}
.container{max-width:1100px;margin:0 auto;padding:24px 16px}
.header{text-align:center;padding:28px 0 20px;border-bottom:1px solid var(--border);margin-bottom:24px}
.header h1{font-size:1.6rem;color:white}
.header h1 span{color:var(--orange)}
.subtitle{color:var(--muted);font-size:.85rem;margin-top:6px}
.rings{display:flex;flex-wrap:wrap;justify-content:center;gap:24px;margin-bottom:24px}
.ring-item{text-align:center}
.section{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}
.section h2{font-size:1rem;color:white;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid var(--border)}
table{width:100%;border-collapse:collapse}
th{background:var(--navy);padding:10px 12px;text-align:left;font-size:.78rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
td{padding:9px 12px;border-bottom:1px solid #1E293B;font-size:.82rem;vertical-align:top}
tr:last-child td{border-bottom:none}
tr:hover td{background:#111827}
.feat-name{font-weight:600;color:white;white-space:nowrap;min-width:160px}
td small{display:block;color:var(--muted);font-size:.72rem;margin-top:2px}
.s-yes{color:var(--green)}
.s-partial{color:var(--orange)}
.s-beta{color:#60A5FA}
.s-no{color:var(--red)}
.score-section{margin-bottom:16px}
.score-section h4{font-size:.82rem;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px}
.bar-wrap{margin-bottom:6px}
.bar-label{display:flex;justify-content:space-between;font-size:.78rem;margin-bottom:3px}
.bar-bg{background:#1E293B;border-radius:3px;height:6px}
.bar-fill{height:6px;border-radius:3px;transition:width .3s}
.platform-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:24px}
.meta-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px}
.meta-card h3{font-size:.9rem;margin-bottom:8px}
.meta-row{display:flex;justify-content:space-between;font-size:.78rem;margin-bottom:4px}
.meta-row span:first-child{color:var(--muted)}
.meta-row span:last-child{color:white;font-weight:500}
@media(max-width:640px){td,th{padding:7px 8px;font-size:.73rem}}
@media print{body{background:white;color:black}.container{max-width:100%}}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>DesignWise <span>Platform Comparator</span></h1>
  <h1 style="font-size:1rem;font-weight:400;color:var(--muted);margin-top:4px">
    ${opts.platforms.join(" · ")} — Category: <strong style="color:var(--orange)">${category.toUpperCase()}</strong>
  </h1>
  <div class="subtitle">BidDeed.AI Competitive Intelligence · Generated: ${now}</div>
</div>

<!-- Overall Score Rings -->
<div class="rings">${ringRow}</div>

<!-- Platform Metadata -->
<div class="platform-meta">
  ${platforms.map((p) => `
  <div class="meta-card">
    <h3 style="color:${COLORS[p.name] || "#F59E0B"}">${p.name}</h3>
    <div class="meta-row"><span>Type</span><span>${p.type}</span></div>
    <div class="meta-row"><span>Pricing</span><span>${p.pricing}</span></div>
    <div class="meta-row"><span>Coverage</span><span>${p.coverage}</span></div>
    <div class="meta-row"><span>Founded</span><span>${p.founded}</span></div>
    <div style="color:var(--muted);font-size:.72rem;margin-top:6px">${p.tagline}</div>
  </div>`).join("")}
</div>

<!-- Feature Matrix for Selected Category -->
<div class="section">
  <h2>Feature Matrix — ${category.toUpperCase()}</h2>
  <div style="overflow-x:auto">
    <table>
      <thead><tr><th>Feature</th>${platformHeaders}</tr></thead>
      <tbody>${featureMatrixRows}</tbody>
    </table>
  </div>
</div>

<!-- Score Comparison Bars -->
<div class="section">
  <h2>Score Breakdown — All Dimensions</h2>
  ${scoreBarRows}
</div>

</div>
</body>
</html>`;
}

// ─── Commands ─────────────────────────────────────────────────────────────────
function cmdCompare(opts: CompareOptions): void {
  const platforms = opts.platforms.map((p) => PLATFORM_DB[p]).filter(Boolean);
  if (platforms.length < 2) {
    console.error(`Need 2+ valid platforms. Available: ${Object.keys(PLATFORM_DB).join(", ")}`);
    process.exit(1);
  }

  console.log(`\n🔄 Platform Comparison: ${opts.platforms.join(" vs ")} [${opts.category}]\n`);

  const featureCategories = Object.keys(platforms[0].scores) as (keyof FeatureScore)[];
  featureCategories.forEach((fc) => {
    const label = fc.replace(/([A-Z])/g, " $1").trim().padEnd(18);
    const row = platforms.map((p) => `${p.name.split(" ")[0].padEnd(10)} ${String(p.scores[fc]).padStart(3)}`).join("  |  ");
    console.log(`  ${label}  ${row}`);
  });

  console.log(`\n  ${opts.category.toUpperCase()} Feature Matrix:`);
  platforms[0].features[opts.category].forEach((feat, i) => {
    const row = platforms.map((p) => {
      const f = p.features[opts.category][i];
      if (!f) return "—  ";
      return f.status === "yes" ? "✅" : f.status === "partial" ? "◐ " : f.status === "beta" ? "🔬" : "○ ";
    }).join("  ");
    console.log(`    ${feat.name.padEnd(24)} ${row}`);
  });

  console.log(`\n  Use 'designwise export --platforms "${opts.platforms.join(",")}" --category ${opts.category}' to generate HTML report`);
}

function cmdMatrix(category: Category): void {
  const allPlatforms = Object.values(PLATFORM_DB);
  console.log(`\n📊 Feature Matrix — ${category.toUpperCase()} — All Platforms\n`);

  allPlatforms[0].features[category].forEach((feat, i) => {
    const row = allPlatforms.map((p) => {
      const f = p.features[category][i];
      if (!f) return "—";
      return f.status === "yes" ? "✅" : f.status === "partial" ? "◐" : f.status === "beta" ? "🔬" : "○";
    }).join("  ");
    console.log(`  ${feat.name.padEnd(26)} ${row}`);
  });

  const header = "  " + "Feature".padEnd(26) + allPlatforms.map((p) => p.name.split(" ")[0].padEnd(10)).join("  ");
  console.log(`\n${header}`);
}

function cmdScore(platformName: string): void {
  const p = PLATFORM_DB[platformName];
  if (!p) {
    console.error(`Platform "${platformName}" not found. Available: ${Object.keys(PLATFORM_DB).join(", ")}`);
    process.exit(1);
  }

  const overall = Math.round(
    Object.values(p.scores).reduce((a, b) => a + b, 0) / Object.values(p.scores).length
  );

  console.log(`\n📊 ${p.name} — Score Breakdown\n`);
  console.log(`  Overall: ${overall}/100`);
  console.log(`  Type:    ${p.type}  |  Pricing: ${p.pricing}`);
  console.log(`  Coverage: ${p.coverage}\n`);

  Object.entries(p.scores).forEach(([k, v]) => {
    const label = k.replace(/([A-Z])/g, " $1").trim().padEnd(18);
    const bar = "█".repeat(Math.round(v / 5)).padEnd(20);
    console.log(`  ${label}  ${bar}  ${v}/100`);
  });
}

function cmdExport(opts: CompareOptions): void {
  const html = generateCompareHTML(opts);
  const outDir = opts.outputFile
    ? join(process.cwd(), "docs", "reports")
    : join(process.cwd(), "docs", "reports");

  if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });

  const slug = opts.platforms.join("-").toLowerCase().replace(/[^a-z0-9-]/g, "") + `-${opts.category}`;
  const outFile = opts.outputFile || join(outDir, `compare-${slug}.html`);
  writeFileSync(outFile, html, "utf8");

  console.log(`\n✅ Exported: ${outFile}`);
  console.log(`   Platforms: ${opts.platforms.join(", ")}`);
  console.log(`   Category: ${opts.category}`);
  console.log(`   Size: ${(html.length / 1024).toFixed(1)} KB`);
}

// ─── CLI Entry Point ──────────────────────────────────────────────────────────
async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const command = args[0];

  const parseFlag = (flag: string): string | undefined => {
    const i = args.indexOf(flag);
    return i !== -1 ? args[i + 1] : undefined;
  };

  if (!command || command === "--help" || command === "-h") {
    console.log(`
DesignWise Comparator — Generic Platform Comparison Agent
BidDeed.AI / Everest Capital USA

Usage:
  designwise compare --platforms "ZoneWise,PropZone" --category zoning
  designwise matrix  --category <category>
  designwise score   --platform <platform>
  designwise export  --platforms "ZoneWise,PropZone,Reonomy,CoStar" --category zoning [--out file.html]

Categories: zoning | data | ai | pricing | api | ux
Platforms:  ${Object.keys(PLATFORM_DB).join(" | ")}

Examples:
  designwise compare --platforms "ZoneWise,PropZone" --category zoning
  designwise compare --platforms "ZoneWise,PropZone,Reonomy,CoStar" --category ai
  designwise matrix  --category data
  designwise score   --platform ZoneWise
  designwise export  --platforms "ZoneWise,PropZone,Reonomy,CoStar" --category zoning
    `);
    return;
  }

  const platformsRaw = parseFlag("--platforms");
  const categoryRaw  = parseFlag("--category");
  const platformRaw  = parseFlag("--platform");
  const outFile      = parseFlag("--out");

  const platforms = platformsRaw
    ? platformsRaw.split(",").map((p) => p.trim())
    : ["ZoneWise", "PropZone"];
  const category = (categoryRaw as Category) || "zoning";

  switch (command) {
    case "compare": cmdCompare({ platforms, category }); break;
    case "matrix":  cmdMatrix(category);                 break;
    case "score":   cmdScore(platformRaw || "ZoneWise"); break;
    case "export":  cmdExport({ platforms, category, outputFile: outFile }); break;
    default:
      console.error(`Unknown command: ${command}. Run --help for usage.`);
      process.exit(1);
  }
}

main().catch((err) => {
  console.error(`❌ Fatal: ${err.message}`);
  process.exit(1);
});

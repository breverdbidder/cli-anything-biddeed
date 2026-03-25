#!/usr/bin/env node
/**
 * Parity Engine — ZoneWise vs PropZone Comparison CLI
 * cli-anything harness: cli_anything.parity_engine
 *
 * Commands:
 *   parity dashboard              Generate full HTML comparison dashboard
 *   parity score                  Show current parity score (X/37 PropZone features matched)
 *   parity gaps                   List all P1/P2/P3 gaps with status
 *   parity compare <p1> <p2>      Compare any two platforms side-by-side
 *   parity export                 Export comparison as self-contained HTML to docs/reports/
 */

import { writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";

// ─── Types ────────────────────────────────────────────────────────────────────
type KpiStatus = "done" | "partial" | "gap" | "advantage";
type Priority = "P1" | "P2" | "P3" | null;
type Category =
  | "LOT"
  | "PROPERTY"
  | "ZONING"
  | "CAPACITY"
  | "SETBACKS"
  | "USES"
  | "MAPS"
  | "ADVANTAGE";

interface KpiRow {
  id: number;
  category: Category;
  feature: string;
  propzone: boolean | "partial";
  zonewise: boolean | "partial" | "pending";
  status: KpiStatus;
  priority: Priority;
  notes: string;
}

interface CheckpointRow {
  id: string;
  name: string;
  target: string;
  status: "complete" | "in-progress" | "pending";
  score: number;
  milestone: string;
}

interface Platform {
  name: string;
  score: number;
  features: {
    dataCoverage: number;
    uiUx: number;
    aiCapabilities: number;
    pricing: number;
    apiAccess: number;
  };
  highlights: string[];
  gaps: string[];
}

// ─── Data: 45 KPIs (37 PropZone + 8 ZoneWise Advantages) ─────────────────────
const KPI_DATA: KpiRow[] = [
  // LOT (6)
  { id: 1,  category: "LOT",       feature: "Parcel ID",          propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "BCPAO primary key" },
  { id: 2,  category: "LOT",       feature: "Lot Area",           propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "sqft from BCPAO" },
  { id: 3,  category: "LOT",       feature: "Lot Type",           propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Corner/interior detected via geometry; flag type partial" },
  { id: 4,  category: "LOT",       feature: "Frontage",           propzone: true,      zonewise: false,     status: "gap",       priority: "P3", notes: "Street frontage width" },
  { id: 5,  category: "LOT",       feature: "Vacancy",            propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "Vacant flag from BCPAO" },
  { id: 6,  category: "LOT",       feature: "Legal Description",  propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "Full legal desc from BCPAO" },
  // PROPERTY (4)
  { id: 7,  category: "PROPERTY",  feature: "Building Area",      propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "Total sq ft from BCPAO" },
  { id: 8,  category: "PROPERTY",  feature: "Existing Use",       propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "DOR use code mapped" },
  { id: 9,  category: "PROPERTY",  feature: "Year Built",         propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "From BCPAO card" },
  { id: 10, category: "PROPERTY",  feature: "Subdivision",        propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "Subdivision name from BCPAO" },
  // ZONING (6)
  { id: 11, category: "ZONING",    feature: "Zone Code",          propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "Full code coverage across all 67 FL counties" },
  { id: 12, category: "ZONING",    feature: "Zone District",      propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "District name confirmed via BCPAO + GIS" },
  { id: 13, category: "ZONING",    feature: "Description",        propzone: true,      zonewise: "partial", status: "partial",   priority: "P1", notes: "Plain-language zone description needed" },
  { id: 14, category: "ZONING",    feature: "Overlays",           propzone: true,      zonewise: false,     status: "gap",       priority: "P1", notes: "Flood, historic, CRA overlays not tracked" },
  { id: 15, category: "ZONING",    feature: "Code Link",          propzone: true,      zonewise: false,     status: "gap",       priority: "P2", notes: "Link to municipal code doc" },
  { id: 16, category: "ZONING",    feature: "Jurisdiction",       propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "Municipality + county confirmed" },
  // CAPACITY (11)
  { id: 17, category: "CAPACITY",  feature: "Max Height",         propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Available for ~70% parcels" },
  { id: 18, category: "CAPACITY",  feature: "Stories",            propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Derived from height where available" },
  { id: 19, category: "CAPACITY",  feature: "FAR",                propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Floor-area ratio partial coverage" },
  { id: 20, category: "CAPACITY",  feature: "Lot Coverage",       propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Max lot coverage % partial" },
  { id: 21, category: "CAPACITY",  feature: "Max Built Area",     propzone: true,      zonewise: false,     status: "gap",       priority: "P1", notes: "Gross floor area cap not computed" },
  { id: 22, category: "CAPACITY",  feature: "Footprint",          propzone: true,      zonewise: false,     status: "gap",       priority: "P2", notes: "Max building footprint not tracked" },
  { id: 23, category: "CAPACITY",  feature: "Open Space",         propzone: true,      zonewise: false,     status: "gap",       priority: "P2", notes: "Min open space % not tracked" },
  { id: 24, category: "CAPACITY",  feature: "Density",            propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Res density partial; missing commercial" },
  { id: 25, category: "CAPACITY",  feature: "Max Units",          propzone: true,      zonewise: false,     status: "gap",       priority: "P1", notes: "Max dwelling units not computed" },
  { id: 26, category: "CAPACITY",  feature: "Lodging",            propzone: true,      zonewise: false,     status: "gap",       priority: "P3", notes: "Max hotel/lodging rooms" },
  { id: 27, category: "CAPACITY",  feature: "Office/Comm Area",   propzone: true,      zonewise: false,     status: "gap",       priority: "P3", notes: "Max office/commercial area" },
  // SETBACKS (5)
  { id: 28, category: "SETBACKS",  feature: "Front Setback",      propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Available ~65% Brevard parcels" },
  { id: 29, category: "SETBACKS",  feature: "Side Setback",       propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Available ~65% Brevard parcels" },
  { id: 30, category: "SETBACKS",  feature: "Rear Setback",       propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Available ~65% Brevard parcels" },
  { id: 31, category: "SETBACKS",  feature: "Secondary Setback",  propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Corner lot secondary setback — partial via GIS corner detection" },
  { id: 32, category: "SETBACKS",  feature: "Water Setback",      propzone: true,      zonewise: "partial", status: "partial",   priority: null, notes: "Waterfront setback — partial via flood zone overlay" },
  // USES (3)
  { id: 33, category: "USES",      feature: "Permitted Uses",     propzone: true,      zonewise: false,     status: "gap",       priority: "P1", notes: "Use table not imported from municipal code" },
  { id: 34, category: "USES",      feature: "Permission Type",    propzone: true,      zonewise: false,     status: "gap",       priority: "P2", notes: "By-right vs conditional vs prohibited" },
  { id: 35, category: "USES",      feature: "Use Categories",     propzone: true,      zonewise: false,     status: "gap",       priority: "P3", notes: "Residential / commercial / industrial" },
  // MAPS (2)
  { id: 36, category: "MAPS",      feature: "Aerial Map",         propzone: true,      zonewise: true,      status: "done",      priority: null, notes: "Mapbox satellite via ZoneWise UI" },
  { id: 37, category: "MAPS",      feature: "Zoning Map",         propzone: true,      zonewise: false,     status: "gap",       priority: "P2", notes: "Vector zoning layer not overlaid" },
  // ZONEWISE ADVANTAGES (8) — PropZone does NOT have these
  { id: 38, category: "ADVANTAGE", feature: "AI Chatbot",         propzone: false,     zonewise: true,      status: "advantage", priority: null, notes: "Natural-language zoning Q&A — live" },
  { id: 39, category: "ADVANTAGE", feature: "AI Analysis",        propzone: false,     zonewise: true,      status: "advantage", priority: null, notes: "GPT-powered investment analysis" },
  { id: 40, category: "ADVANTAGE", feature: "3D Massing",         propzone: false,     zonewise: true,      status: "advantage", priority: null, notes: "Three.js buildable envelope render" },
  { id: 41, category: "ADVANTAGE", feature: "Owner + Valuation",  propzone: false,     zonewise: true,      status: "advantage", priority: null, notes: "Owner name, assessed value, market est" },
  { id: 42, category: "ADVANTAGE", feature: "BCPAO Card (61 fld)",propzone: false,     zonewise: true,      status: "advantage", priority: null, notes: "Full 61-field BCPAO property record" },
  { id: 43, category: "ADVANTAGE", feature: "67-County Coverage", propzone: false,     zonewise: true,      status: "advantage", priority: null, notes: "All FL counties — PropZone covers ~6" },
  { id: 44, category: "ADVANTAGE", feature: "ML Predictions",     propzone: false,     zonewise: true,      status: "advantage", priority: null, notes: "ARV / auction bid / ROI predictions" },
  { id: 45, category: "ADVANTAGE", feature: "Free PDF Report",    propzone: false,     zonewise: "pending", status: "advantage", priority: "P1", notes: "One-click downloadable zoning report — P1" },
];

const CHECKPOINTS: CheckpointRow[] = [
  { id: "CP1", name: "Foundation",      target: "Week 1-2",  status: "complete",   score: 32,  milestone: "12 done / 10 partial — core data confirmed" },
  { id: "CP2", name: "Capacity Parity", target: "Week 3-4",  status: "in-progress",score: 55,  milestone: "Compute max built area, max units, open space" },
  { id: "CP3", name: "Uses + Overlays", target: "Week 5-6",  status: "pending",    score: 70,  milestone: "Import use tables, map overlay layers" },
  { id: "CP4", name: "Full Parity",     target: "Week 7-8",  status: "pending",    score: 85,  milestone: "Setbacks complete, code links, zoning map" },
  { id: "CP5", name: "Beyond Parity",   target: "Week 9-12", status: "pending",    score: 100, milestone: "PDF report, enhanced AI, public launch" },
];

const PLATFORMS: Record<string, Platform> = {
  ZoneWise: {
    name: "ZoneWise",
    score: 82,
    features: { dataCoverage: 78, uiUx: 90, aiCapabilities: 95, pricing: 95, apiAccess: 70 },
    highlights: ["AI Chatbot", "3D Massing", "67-County FL Coverage", "ML Predictions", "Free"],
    gaps: ["Permitted Uses table", "Overlays", "Full Setback Coverage"],
  },
  PropZone: {
    name: "PropZone (Gridics)",
    score: 74,
    features: { dataCoverage: 85, uiUx: 75, aiCapabilities: 40, pricing: 30, apiAccess: 60 },
    highlights: ["Capacity Matrix", "Use Tables", "Overlay Layers", "Code Links"],
    gaps: ["No AI", "No 3D", "~6 FL cities only", "Paid SaaS"],
  },
  Reonomy: {
    name: "Reonomy",
    score: 68,
    features: { dataCoverage: 90, uiUx: 72, aiCapabilities: 55, pricing: 20, apiAccess: 85 },
    highlights: ["National Coverage", "Owner Data", "Sales History", "API Access"],
    gaps: ["No AI Q&A", "No Zoning Details", "Enterprise pricing"],
  },
  CoStar: {
    name: "CoStar",
    score: 72,
    features: { dataCoverage: 95, uiUx: 65, aiCapabilities: 50, pricing: 10, apiAccess: 80 },
    highlights: ["Industry Standard", "National CRE Data", "Lease Comps", "Full API"],
    gaps: ["No FL residential zoning", "Very expensive", "No AI", "No 3D"],
  },
};

// ─── Score calculation ─────────────────────────────────────────────────────────
function calcScore(): {
  done: number; partial: number; gaps: number; advantages: number;
  total: number; pctDone: number; pctWithPartials: number;
} {
  const propzoneFeatures = KPI_DATA.filter((k) => k.category !== "ADVANTAGE");
  const done = propzoneFeatures.filter((k) => k.status === "done").length;
  const partial = propzoneFeatures.filter((k) => k.status === "partial").length;
  const gaps = propzoneFeatures.filter((k) => k.status === "gap").length;
  const advantages = KPI_DATA.filter((k) => k.status === "advantage").length;
  const total = propzoneFeatures.length;
  return {
    done, partial, gaps, advantages, total,
    pctDone: Math.round((done / total) * 100),
    pctWithPartials: Math.round(((done + partial) / total) * 100),
  };
}

// ─── HTML Generator ───────────────────────────────────────────────────────────
function generateHTML(): string {
  const score = calcScore();
  const now = new Date().toLocaleDateString("en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  });

  const rowsHtml = KPI_DATA.map((k) => {
    const statusClass = k.status === "done" ? "status-done"
      : k.status === "partial" ? "status-partial"
      : k.status === "advantage" ? "status-advantage"
      : "status-gap";
    const statusLabel = k.status === "done" ? "✅ Done"
      : k.status === "partial" ? "◐ Partial"
      : k.status === "advantage" ? "⭐ Advantage"
      : "○ Gap";
    const pzCell = k.category === "ADVANTAGE" ? "—"
      : k.propzone === true ? "✅" : k.propzone === "partial" ? "◐" : "—";
    const zwCell = k.zonewise === true ? "✅"
      : k.zonewise === "partial" ? "◐"
      : k.zonewise === "pending" ? "🔜 P1"
      : "○";
    const priorCell = k.priority
      ? `<span class="priority priority-${k.priority.toLowerCase()}">${k.priority}</span>`
      : "";
    const dataStatus = k.status === "advantage" ? "advantage"
      : k.status === "done" ? "done"
      : k.status === "partial" ? "partial"
      : "gap";
    const dataPriority = k.priority ? k.priority.toLowerCase() : "none";

    return `<tr data-status="${dataStatus}" data-priority="${dataPriority}" data-category="${k.category.toLowerCase()}">
      <td class="td-id">${k.id}</td>
      <td><span class="badge badge-${k.category.toLowerCase()}">${k.category}</span></td>
      <td class="td-feature">${k.feature}</td>
      <td class="td-center">${pzCell}</td>
      <td class="td-center">${zwCell}</td>
      <td><span class="${statusClass}">${statusLabel}</span></td>
      <td>${priorCell}</td>
      <td class="td-notes">${k.notes}</td>
    </tr>`;
  }).join("\n");

  const checkpointsHtml = CHECKPOINTS.map((cp) => {
    const cpClass = cp.status === "complete" ? "cp-complete"
      : cp.status === "in-progress" ? "cp-inprogress"
      : "cp-pending";
    const cpIcon = cp.status === "complete" ? "✅"
      : cp.status === "in-progress" ? "🔄"
      : "⏳";
    return `<div class="checkpoint ${cpClass}">
      <div class="cp-header">
        <span class="cp-icon">${cpIcon}</span>
        <span class="cp-id">${cp.id}</span>
        <span class="cp-name">${cp.name}</span>
        <span class="cp-target">${cp.target}</span>
        <span class="cp-score">${cp.score}%</span>
      </div>
      <div class="cp-milestone">${cp.milestone}</div>
      <div class="cp-bar"><div class="cp-fill" style="width:${cp.score}%"></div></div>
    </div>`;
  }).join("\n");

  // Score ring SVG helper
  function scoreRing(pct: number, label: string, color: string, r = 52): string {
    const circumference = 2 * Math.PI * r;
    const offset = circumference - (pct / 100) * circumference;
    return `<svg width="130" height="130" viewBox="0 0 130 130">
      <circle cx="65" cy="65" r="${r}" fill="none" stroke="#1E3A5F" stroke-width="10"/>
      <circle cx="65" cy="65" r="${r}" fill="none" stroke="${color}" stroke-width="10"
        stroke-dasharray="${circumference.toFixed(2)}" stroke-dashoffset="${offset.toFixed(2)}"
        stroke-linecap="round" transform="rotate(-90 65 65)"/>
      <text x="65" y="60" text-anchor="middle" fill="white" font-size="20" font-weight="700" font-family="Inter,sans-serif">${pct}%</text>
      <text x="65" y="80" text-anchor="middle" fill="#94A3B8" font-size="11" font-family="Inter,sans-serif">${label}</text>
    </svg>`;
  }

  // Pipeline SVG (inline, no Mermaid CDN)
  const pipelineSvg = `<svg viewBox="0 0 900 320" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:900px;font-family:Inter,sans-serif">
    <defs>
      <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#F59E0B"/>
      </marker>
    </defs>
    <!-- Nodes -->
    <rect x="10" y="130" width="120" height="50" rx="8" fill="#1E3A5F" stroke="#F59E0B" stroke-width="1.5"/>
    <text x="70" y="150" text-anchor="middle" fill="white" font-size="11" font-weight="600">PropZone Intel</text>
    <text x="70" y="167" text-anchor="middle" fill="#94A3B8" font-size="10">API Scraper</text>

    <rect x="175" y="130" width="120" height="50" rx="8" fill="#1E3A5F" stroke="#F59E0B" stroke-width="1.5"/>
    <text x="235" y="150" text-anchor="middle" fill="white" font-size="11" font-weight="600">Supabase</text>
    <text x="235" y="167" text-anchor="middle" fill="#94A3B8" font-size="10">propzone_intel</text>

    <rect x="340" y="60" width="130" height="50" rx="8" fill="#0F172A" stroke="#22C55E" stroke-width="1.5"/>
    <text x="405" y="80" text-anchor="middle" fill="white" font-size="11" font-weight="600">ZoneWise Data</text>
    <text x="405" y="97" text-anchor="middle" fill="#94A3B8" font-size="10">zoning_assignments</text>

    <rect x="340" y="200" width="130" height="50" rx="8" fill="#0F172A" stroke="#22C55E" stroke-width="1.5"/>
    <text x="405" y="220" text-anchor="middle" fill="white" font-size="11" font-weight="600">Envelope Squad</text>
    <text x="405" y="237" text-anchor="middle" fill="#94A3B8" font-size="10">3D + Capacity</text>

    <rect x="520" y="130" width="130" height="50" rx="8" fill="#1E3A5F" stroke="#F59E0B" stroke-width="2"/>
    <text x="585" y="150" text-anchor="middle" fill="#F59E0B" font-size="11" font-weight="700">Parity Engine</text>
    <text x="585" y="167" text-anchor="middle" fill="#94A3B8" font-size="10">Gap Analysis</text>

    <rect x="700" y="80" width="120" height="50" rx="8" fill="#0F172A" stroke="#22C55E" stroke-width="1.5"/>
    <text x="760" y="100" text-anchor="middle" fill="white" font-size="11" font-weight="600">HTML Dashboard</text>
    <text x="760" y="117" text-anchor="middle" fill="#94A3B8" font-size="10">docs/reports/</text>

    <rect x="700" y="180" width="120" height="50" rx="8" fill="#0F172A" stroke="#22C55E" stroke-width="1.5"/>
    <text x="760" y="200" text-anchor="middle" fill="white" font-size="11" font-weight="600">Telegram</text>
    <text x="760" y="217" text-anchor="middle" fill="#94A3B8" font-size="10">Weekly Digest</text>

    <!-- Arrows -->
    <line x1="130" y1="155" x2="172" y2="155" stroke="#F59E0B" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="295" y1="145" x2="337" y2="95"  stroke="#F59E0B" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="295" y1="165" x2="337" y2="215" stroke="#F59E0B" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="470" y1="85"  x2="517" y2="145" stroke="#22C55E" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="470" y1="225" x2="517" y2="170" stroke="#22C55E" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="650" y1="145" x2="697" y2="105" stroke="#F59E0B" stroke-width="1.5" marker-end="url(#arr)"/>
    <line x1="650" y1="165" x2="697" y2="205" stroke="#F59E0B" stroke-width="1.5" marker-end="url(#arr)"/>

    <!-- Labels -->
    <text x="450" y="40" text-anchor="middle" fill="#F59E0B" font-size="13" font-weight="700">Parity Engine — Data Flow</text>
    <text x="450" y="290" text-anchor="middle" fill="#475569" font-size="10">Weekly GHA: Sundays 10AM EST → auto-commits updated dashboard</text>
  </svg>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZoneWise vs PropZone — Parity Dashboard</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --navy:#1E3A5F;--orange:#F59E0B;--slate:#0F172A;
  --green:#22C55E;--red:#EF4444;--text:#E2E8F0;
  --muted:#94A3B8;--border:#1E3A5F;--card:#0F172A;
}
body{background:var(--slate);color:var(--text);font-family:Inter,system-ui,sans-serif;font-size:14px;line-height:1.5}
a{color:var(--orange);text-decoration:none}
h1,h2,h3{font-weight:700;letter-spacing:-.02em}

/* ── Layout ── */
.container{max-width:1200px;margin:0 auto;padding:24px 16px}
.header{text-align:center;padding:32px 0 24px;border-bottom:1px solid var(--border)}
.header h1{font-size:1.8rem;color:white}
.header h1 span{color:var(--orange)}
.header .subtitle{color:var(--muted);margin-top:6px;font-size:.9rem}
.header .updated{color:var(--muted);font-size:.8rem;margin-top:4px}

/* ── Score Summary ── */
.score-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:16px;padding:24px 0}
.score-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;text-align:center}
.score-card .val{font-size:2rem;font-weight:800;line-height:1}
.score-card .lbl{color:var(--muted);font-size:.75rem;margin-top:4px;text-transform:uppercase;letter-spacing:.08em}
.score-card.done .val{color:var(--green)}
.score-card.partial .val{color:var(--orange)}
.score-card.gap .val{color:var(--red)}
.score-card.adv .val{color:#A78BFA}
.score-card.pct .val{color:white}

/* ── Rings ── */
.rings{display:flex;flex-wrap:wrap;justify-content:center;gap:32px;padding:24px 0}

/* ── Tabs ── */
.tabs{display:flex;gap:8px;padding:16px 0;border-bottom:1px solid var(--border)}
.tab-btn{background:var(--card);border:1px solid var(--border);color:var(--muted);padding:8px 20px;border-radius:8px;cursor:pointer;font-size:.85rem;font-weight:600;transition:all .2s}
.tab-btn.active,.tab-btn:hover{background:var(--navy);color:white;border-color:var(--orange)}
.tab-pane{display:none;padding:16px 0}
.tab-pane.active{display:block}

/* ── Filters ── */
.filters{display:flex;flex-wrap:wrap;gap:8px;padding:12px 0}
.filter-btn{background:var(--card);border:1px solid var(--border);color:var(--muted);padding:6px 14px;border-radius:6px;cursor:pointer;font-size:.8rem;font-weight:600;transition:all .15s}
.filter-btn.active,.filter-btn:hover{color:white;border-color:var(--orange)}
.filter-btn[data-f="all"].active{background:#1E3A5F}
.filter-btn[data-f="done"].active{background:#166534;border-color:var(--green);color:var(--green)}
.filter-btn[data-f="partial"].active{background:#78350F;border-color:var(--orange);color:var(--orange)}
.filter-btn[data-f="gap"].active{background:#7F1D1D;border-color:var(--red);color:var(--red)}
.filter-btn[data-f="advantage"].active{background:#4C1D95;border-color:#A78BFA;color:#A78BFA}
.filter-btn[data-f="p1"].active{background:#7F1D1D;border-color:var(--red);color:var(--red)}
.filter-btn[data-f="p2"].active{background:#92400E;border-color:var(--orange);color:var(--orange)}
.filter-btn[data-f="p3"].active{background:#1E3A5F;border-color:#60A5FA;color:#60A5FA}

/* ── Table ── */
.table-wrap{overflow-x:auto;border-radius:10px;border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;min-width:720px}
th{background:var(--navy);padding:10px 12px;text-align:left;font-size:.78rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);white-space:nowrap}
td{padding:9px 12px;border-bottom:1px solid #1E293B;vertical-align:middle;font-size:.83rem}
tr:last-child td{border-bottom:none}
tr:hover td{background:#111827}
tr.hidden{display:none}
.td-id{color:var(--muted);font-size:.75rem;width:36px}
.td-feature{font-weight:500;color:white}
.td-center{text-align:center}
.td-notes{color:var(--muted);font-size:.78rem;max-width:240px}

/* ── Badges ── */
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.badge-lot{background:#1E3A5F;color:#60A5FA}
.badge-property{background:#1E3A5F;color:#34D399}
.badge-zoning{background:#1E3A5F;color:#F59E0B}
.badge-capacity{background:#1E3A5F;color:#A78BFA}
.badge-setbacks{background:#1E3A5F;color:#FB7185}
.badge-uses{background:#1E3A5F;color:#FCD34D}
.badge-maps{background:#1E3A5F;color:#38BDF8}
.badge-advantage{background:#4C1D95;color:#C4B5FD}

/* ── Status ── */
.status-done{color:var(--green);font-weight:600;font-size:.8rem}
.status-partial{color:var(--orange);font-weight:600;font-size:.8rem}
.status-gap{color:var(--red);font-weight:600;font-size:.8rem}
.status-advantage{color:#A78BFA;font-weight:600;font-size:.8rem}

/* ── Priority ── */
.priority{display:inline-block;padding:2px 7px;border-radius:4px;font-size:.7rem;font-weight:700}
.priority-p1{background:#7F1D1D;color:var(--red)}
.priority-p2{background:#78350F;color:var(--orange)}
.priority-p3{background:#1E3A5F;color:#60A5FA}

/* ── Checkpoints ── */
.checkpoint{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:10px}
.cp-header{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.cp-icon{font-size:1.1rem}
.cp-id{font-weight:800;color:var(--orange);font-size:.85rem;min-width:36px}
.cp-name{font-weight:700;color:white;flex:1}
.cp-target{color:var(--muted);font-size:.8rem}
.cp-score{font-weight:800;color:white;font-size:1rem;min-width:42px;text-align:right}
.cp-milestone{color:var(--muted);font-size:.8rem;margin-top:6px;padding-left:46px}
.cp-bar{background:#1E293B;border-radius:4px;height:6px;margin-top:8px}
.cp-fill{height:6px;border-radius:4px;background:var(--orange);transition:width .4s}
.cp-complete .cp-fill{background:var(--green)}
.cp-inprogress .cp-fill{background:var(--orange)}
.cp-pending .cp-fill{background:#475569}
.cp-complete{border-color:#166534}
.cp-inprogress{border-color:var(--orange)}

/* ── Compare ── */
.compare-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-top:16px}
.platform-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}
.platform-card h3{font-size:1rem;color:white;margin-bottom:12px}
.platform-score{font-size:2.5rem;font-weight:900;color:var(--orange);line-height:1}
.platform-score small{font-size:1rem;color:var(--muted)}
.feature-bars{margin-top:14px}
.feat-row{margin-bottom:8px}
.feat-label{display:flex;justify-content:space-between;font-size:.78rem;color:var(--muted);margin-bottom:3px}
.feat-bar{background:#1E293B;border-radius:3px;height:5px}
.feat-fill{height:5px;border-radius:3px;background:var(--orange)}
.platform-highlights{margin-top:12px}
.platform-highlights h4{font-size:.75rem;color:var(--green);text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px}
.platform-highlights li,.platform-gaps li{font-size:.78rem;color:var(--muted);padding:2px 0;list-style:none;padding-left:14px;position:relative}
.platform-highlights li::before{content:"✅";position:absolute;left:0;font-size:.65rem}
.platform-gaps h4{font-size:.75rem;color:var(--red);text-transform:uppercase;letter-spacing:.07em;margin:10px 0 6px}
.platform-gaps li::before{content:"○";position:absolute;left:0;font-size:.7rem;color:var(--red)}

/* ── Pipeline ── */
.pipeline-wrap{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}

/* ── Print ── */
@media print{
  body{background:white;color:black}
  .tabs,.filters,.filter-btn,.tab-btn{display:none!important}
  .tab-pane{display:block!important}
  .container{max-width:100%}
  tr.hidden{display:table-row!important}
  .score-card .val,.status-done{color:inherit}
}

/* ── Mobile ── */
@media(max-width:640px){
  .score-grid{grid-template-columns:repeat(3,1fr)}
  .rings{gap:16px}
  .tabs{flex-wrap:wrap}
  td,th{padding:7px 8px;font-size:.75rem}
  .td-notes{display:none}
}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
  <h1>ZoneWise <span>vs</span> PropZone</h1>
  <h1 style="font-size:1.1rem;font-weight:400;color:var(--muted);margin-top:4px">Parity Comparison Dashboard — BidDeed.AI</h1>
  <div class="updated">Generated: ${now} · 45 KPIs · 37 PropZone Features Tracked</div>
</div>

<!-- Score Summary Cards -->
<div class="score-grid">
  <div class="score-card done"><div class="val">${score.done}</div><div class="lbl">Done</div></div>
  <div class="score-card partial"><div class="val">${score.partial}</div><div class="lbl">Partial</div></div>
  <div class="score-card gap"><div class="val">${score.gaps}</div><div class="lbl">Gaps</div></div>
  <div class="score-card adv"><div class="val">${score.advantages}</div><div class="lbl">Advantages</div></div>
  <div class="score-card pct"><div class="val">${score.pctDone}%</div><div class="lbl">Done</div></div>
  <div class="score-card pct"><div class="val">${score.pctWithPartials}%</div><div class="lbl">w/ Partials</div></div>
</div>

<!-- Score Rings -->
<div class="rings">
  ${scoreRing(score.pctDone, "Parity Done", "#22C55E")}
  ${scoreRing(score.pctWithPartials, "w/ Partials", "#F59E0B")}
  ${scoreRing(Math.round((score.advantages / 8) * 100), "Advantages", "#A78BFA")}
  ${scoreRing(Math.round(((score.done + score.partial * 0.5) / score.total) * 100), "Weighted", "#38BDF8")}
</div>

<!-- Tabs -->
<div class="tabs">
  <button class="tab-btn active" onclick="showTab('matrix',this)">KPI Matrix</button>
  <button class="tab-btn" onclick="showTab('checkpoints',this)">Checkpoint Roadmap</button>
  <button class="tab-btn" onclick="showTab('compare',this)">Platform Compare</button>
  <button class="tab-btn" onclick="showTab('pipeline',this)">Pipeline</button>
</div>

<!-- KPI Matrix Tab -->
<div id="tab-matrix" class="tab-pane active">
  <div class="filters">
    <button class="filter-btn active" data-f="all" onclick="filterRows('all',this)">All (45)</button>
    <button class="filter-btn" data-f="done" onclick="filterRows('done',this)">✅ Done (${score.done})</button>
    <button class="filter-btn" data-f="partial" onclick="filterRows('partial',this)">◐ Partial (${score.partial})</button>
    <button class="filter-btn" data-f="gap" onclick="filterRows('gap',this)">○ Gaps (${score.gaps})</button>
    <button class="filter-btn" data-f="advantage" onclick="filterRows('advantage',this)">⭐ Advantages (${score.advantages})</button>
    <button class="filter-btn" data-f="p1" onclick="filterRows('p1',this)">P1</button>
    <button class="filter-btn" data-f="p2" onclick="filterRows('p2',this)">P2</button>
    <button class="filter-btn" data-f="p3" onclick="filterRows('p3',this)">P3</button>
  </div>
  <div class="table-wrap">
    <table id="kpi-table">
      <thead>
        <tr>
          <th>#</th><th>Category</th><th>Feature</th>
          <th>PropZone</th><th>ZoneWise</th>
          <th>Status</th><th>Priority</th><th>Notes</th>
        </tr>
      </thead>
      <tbody>
${rowsHtml}
      </tbody>
    </table>
  </div>
</div>

<!-- Checkpoints Tab -->
<div id="tab-checkpoints" class="tab-pane">
  <h2 style="margin:16px 0 12px;font-size:1.1rem">Execution Roadmap — CP1 → CP5</h2>
  ${checkpointsHtml}
</div>

<!-- Platform Compare Tab -->
<div id="tab-compare" class="tab-pane">
  <h2 style="margin:16px 0 12px;font-size:1.1rem">Platform Comparison — 4 Players</h2>
  <div class="compare-grid">
    ${Object.values(PLATFORMS).map((p) => `
    <div class="platform-card">
      <h3>${p.name}</h3>
      <div class="platform-score">${p.score}<small>/100</small></div>
      <div class="feature-bars">
        ${Object.entries(p.features).map(([k, v]) => `
        <div class="feat-row">
          <div class="feat-label"><span>${k.replace(/([A-Z])/g, " $1").trim()}</span><span>${v}</span></div>
          <div class="feat-bar"><div class="feat-fill" style="width:${v}%"></div></div>
        </div>`).join("")}
      </div>
      <div class="platform-highlights">
        <h4>Highlights</h4>
        <ul>${p.highlights.map((h) => `<li>${h}</li>`).join("")}</ul>
      </div>
      <div class="platform-gaps">
        <h4>Gaps</h4>
        <ul>${p.gaps.map((g) => `<li>${g}</li>`).join("")}</ul>
      </div>
    </div>`).join("")}
  </div>
</div>

<!-- Pipeline Tab -->
<div id="tab-pipeline" class="tab-pane">
  <h2 style="margin:16px 0 12px;font-size:1.1rem">Data Pipeline</h2>
  <div class="pipeline-wrap">
    ${pipelineSvg}
  </div>
  <div style="margin-top:16px;color:var(--muted);font-size:.82rem">
    <strong style="color:white">Weekly CI:</strong> GHA runs every Sunday 10AM EST.
    Queries Supabase for fresh propzone_intel + zoning_assignments data,
    re-generates this dashboard, commits to <code>docs/reports/parity-latest.html</code>,
    and sends Telegram digest with parity score + top P1 gaps.
  </div>
</div>

</div><!-- /container -->

<script>
function showTab(id,btn){
  document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  btn.classList.add('active');
}
function filterRows(f,btn){
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#kpi-table tbody tr').forEach(row=>{
    if(f==='all'){row.classList.remove('hidden');return;}
    const status=row.dataset.status;
    const priority=row.dataset.priority;
    let show=false;
    if(f==='done'&&status==='done')show=true;
    else if(f==='partial'&&status==='partial')show=true;
    else if(f==='gap'&&status==='gap')show=true;
    else if(f==='advantage'&&status==='advantage')show=true;
    else if(f==='p1'&&priority==='p1')show=true;
    else if(f==='p2'&&priority==='p2')show=true;
    else if(f==='p3'&&priority==='p3')show=true;
    row.classList.toggle('hidden',!show);
  });
}
</script>
</body>
</html>`;
}

// ─── Commands ─────────────────────────────────────────────────────────────────
function cmdScore(): void {
  const score = calcScore();
  console.log(`\n📊 ZoneWise vs PropZone — Parity Score\n`);
  console.log(`  PropZone Features: ${score.total}`);
  console.log(`  ✅ Done:        ${String(score.done).padStart(3)} / ${score.total}  (${score.pctDone}%)`);
  console.log(`  ◐  Partial:     ${String(score.partial).padStart(3)} / ${score.total}`);
  console.log(`  ○  Gaps:        ${String(score.gaps).padStart(3)} / ${score.total}`);
  console.log(`  ⭐ Advantages:   ${String(score.advantages).padStart(3)} (PropZone doesn't have)`);
  console.log(`\n  Parity Score (done):         ${score.pctDone}%`);
  console.log(`  Parity Score (w/ partials):  ${score.pctWithPartials}%`);
  console.log(`\n  Current Checkpoint: CP2 — Capacity Parity (in-progress)`);
}

function cmdGaps(): void {
  const p1 = KPI_DATA.filter((k) => k.priority === "P1");
  const p2 = KPI_DATA.filter((k) => k.priority === "P2");
  const p3 = KPI_DATA.filter((k) => k.priority === "P3");

  console.log(`\n🔴 P1 Gaps (Critical — ${p1.length}):\n`);
  p1.forEach((k) => console.log(`  [${k.category}] ${k.feature}: ${k.notes}`));

  console.log(`\n🟠 P2 Gaps (Important — ${p2.length}):\n`);
  p2.forEach((k) => console.log(`  [${k.category}] ${k.feature}: ${k.notes}`));

  console.log(`\n🔵 P3 Gaps (Nice-to-have — ${p3.length}):\n`);
  p3.forEach((k) => console.log(`  [${k.category}] ${k.feature}: ${k.notes}`));

  console.log(`\n  Total: ${p1.length + p2.length + p3.length} gaps tracked`);
}

function cmdDashboard(): void {
  const html = generateHTML();
  console.log(`\n📊 Dashboard generated (${(html.length / 1024).toFixed(1)} KB)`);
  console.log(html.substring(0, 200) + "...");
  console.log(`\n  Use 'parity export' to save to docs/reports/parity-latest.html`);
}

function cmdCompare(p1: string, p2: string): void {
  const plat1 = PLATFORMS[p1] || PLATFORMS[Object.keys(PLATFORMS)[0]];
  const plat2 = PLATFORMS[p2] || PLATFORMS[Object.keys(PLATFORMS)[1]];

  console.log(`\n🔄 Platform Comparison: ${plat1.name} vs ${plat2.name}\n`);
  console.log(`  Overall Score:    ${plat1.name} ${plat1.score}/100  |  ${plat2.name} ${plat2.score}/100`);
  console.log(`\n  Feature Scores:`);

  const features = Object.keys(plat1.features) as (keyof typeof plat1.features)[];
  features.forEach((feat) => {
    const f1 = plat1.features[feat];
    const f2 = plat2.features[feat];
    const winner = f1 > f2 ? `← ${plat1.name}` : f2 > f1 ? `← ${plat2.name}` : "tie";
    const label = feat.replace(/([A-Z])/g, " $1").trim().padEnd(20);
    console.log(`    ${label} ${String(f1).padStart(3)}  vs  ${String(f2).padEnd(3)}  ${winner}`);
  });

  console.log(`\n  ${plat1.name} Highlights: ${plat1.highlights.join(", ")}`);
  console.log(`  ${plat2.name} Highlights: ${plat2.highlights.join(", ")}`);
}

function cmdExport(): void {
  const html = generateHTML();
  const outDir = join(process.cwd(), "docs", "reports");
  if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });

  const outFile = join(outDir, "parity-latest.html");
  writeFileSync(outFile, html, "utf8");

  const score = calcScore();
  console.log(`\n✅ Exported: ${outFile}`);
  console.log(`   Size: ${(html.length / 1024).toFixed(1)} KB`);
  console.log(`   Score: ${score.done}/${score.total} done (${score.pctDone}%), ${score.pctWithPartials}% w/ partials`);
  console.log(`   Gaps: ${score.gaps} remaining (${KPI_DATA.filter((k) => k.priority === "P1").length} P1)`);
}

// ─── CLI Entry Point ──────────────────────────────────────────────────────────
async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === "--help" || command === "-h") {
    console.log(`
Parity Engine — ZoneWise vs PropZone Comparison
BidDeed.AI / Everest Capital USA

Usage:
  parity dashboard              Generate full HTML comparison dashboard
  parity score                  Show current parity score (X/37 features matched)
  parity gaps                   List all P1/P2/P3 gaps with status
  parity compare <p1> <p2>      Compare two platforms (ZoneWise|PropZone|Reonomy|CoStar)
  parity export                 Export self-contained HTML to docs/reports/parity-latest.html

Examples:
  parity score
  parity gaps
  parity compare ZoneWise PropZone
  parity compare ZoneWise CoStar
  parity export
    `);
    return;
  }

  switch (command) {
    case "dashboard": cmdDashboard(); break;
    case "score":     cmdScore();     break;
    case "gaps":      cmdGaps();      break;
    case "compare": {
      const p1 = args[1] || "ZoneWise";
      const p2 = args[2] || "PropZone";
      cmdCompare(p1, p2);
      break;
    }
    case "export":    cmdExport();    break;
    default:
      console.error(`Unknown command: ${command}. Run --help for usage.`);
      process.exit(1);
  }
}

main().catch((err) => {
  console.error(`❌ Fatal: ${err.message}`);
  process.exit(1);
});

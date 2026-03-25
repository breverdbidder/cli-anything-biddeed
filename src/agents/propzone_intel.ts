#!/usr/bin/env node
/**
 * PropZone Intel Agent — Reverse-engineered Gridics/PropZone API scraper
 * cli-anything harness: cli_anything.propzone_intel
 *
 * Pipeline: GraphQL Settings → Place Lookup → Property Records → Supabase Store → Gap Report
 *
 * Endpoints:
 *   propzone.gridics.com/graphql    — Apollo Client (mainSettings, publicToken)
 *   pr1-api.gridics.com             — Drupal 10 REST API (property records, places)
 *   dar6mh8qr5ku2.cloudfront.net    — Gridics Tiles Service (vector tiles)
 *
 * Commands:
 *   propzone scrape <city>          — Scrape all parcel zoning data for a city
 *   propzone compare <parcelId>     — Compare ZoneWise vs PropZone for a parcel
 *   propzone fields                 — List all available PropZone fields
 *   propzone test                   — Verify API access and token validity
 */

import { writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";

// ─── Config ───────────────────────────────────────────────────────────────────
const GRIDICS_GRAPHQL   = "https://propzone.gridics.com/graphql";
const GRIDICS_API_BASE  = "https://pr1-api.gridics.com/api/ui-api";
const STATE_ENV         = "fl";
const DEFAULT_CITY      = "satellite-beach";
const PAGE_SIZE         = 100;
const MAX_RETRIES       = 3;
const OUTPUT_DIR        = join(process.cwd(), "propzone-output");

const SUPABASE_URL      = process.env.SUPABASE_URL || "";
const SUPABASE_KEY      = process.env.SUPABASE_KEY || "";

// All fields the PropZone UI renders per parcel
const PROPERTY_FIELDS = [
  "id", "title", "parcel_id", "zone_code", "zone_subzone", "zone_type",
  "existing_use", "allowed_uses_residential", "allowed_uses_commercial", "allowed_uses_lodging",
  "residential_density", "max_units", "max_lodging_rooms",
  "max_office_area", "max_commercial_area", "max_built_area",
  "max_building_footprint", "lot_coverage", "far",
  "max_height", "max_stories", "min_open_space",
  "setback_front", "setback_side", "setback_rear", "setback_water", "setback_other",
  "tax_assessed_value", "tax_year", "owner_name", "owner_address",
  "lot_size_sqft", "year_built", "address", "lat", "lng", "place_id",
];

// ─── Types ────────────────────────────────────────────────────────────────────
interface PublicTokenResponse {
  data: {
    mainSettings: {
      publicToken: string;
      mapboxToken: string;
    };
  };
}

interface PlaceRecord {
  id: string;
  title: string;
  extent: number[];
}

interface PropertyRecord {
  id: string;
  title: string;
  parcel_id?: string;
  zone_code?: string;
  zone_subzone?: string;
  zone_type?: string;
  existing_use?: string;
  max_height?: number;
  max_stories?: number;
  far?: number;
  lot_coverage?: number;
  residential_density?: number;
  max_units?: number;
  setback_front?: number;
  setback_side?: number;
  setback_rear?: number;
  setback_water?: number;
  lot_size_sqft?: number;
  owner_name?: string;
  address?: string;
  [key: string]: unknown;
}

interface ScrapeResult {
  city: string;
  placeId: string;
  totalRecords: number;
  stored: number;
  errors: number;
  durationMs: number;
}

interface CompareResult {
  parcelId: string;
  propzone: Record<string, unknown> | null;
  zonewise: Record<string, unknown> | null;
  gaps: string[];
  matches: string[];
}

// ─── Auth: Fetch publicToken via GraphQL ─────────────────────────────────────
async function fetchPublicToken(): Promise<{ publicToken: string; mapboxToken: string }> {
  const query = `
    query mainSettings {
      mainSettings {
        publicToken
        mapboxToken
      }
    }
  `;

  const res = await fetchWithRetry(GRIDICS_GRAPHQL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
      "Origin": "https://propzone.gridics.com",
      "Referer": "https://propzone.gridics.com/",
    },
    body: JSON.stringify({ query }),
  });

  const data: PublicTokenResponse = await res.json();
  const { publicToken, mapboxToken } = data.data.mainSettings;

  if (!publicToken) throw new Error("No publicToken returned from GraphQL mainSettings");
  console.log(`✅ publicToken acquired (${publicToken.substring(0, 20)}...)`);
  return { publicToken, mapboxToken };
}

// ─── Places: Resolve city name → place ID ────────────────────────────────────
async function fetchPlaces(publicToken: string): Promise<PlaceRecord[]> {
  const params = new URLSearchParams({
    type: "_place",
    action: "_place",
    featureLayer: "state",
    "fields[]": "id",
    publicToken,
    state_env: STATE_ENV,
  });
  // Multi-value fields need separate params
  const url = `${GRIDICS_API_BASE}?type=_place&action=_place&featureLayer=state&fields[]=id&fields[]=title&fields[]=extent&publicToken=${publicToken}&state_env=${STATE_ENV}`;

  const res = await fetchWithRetry(url);
  const data = await res.json();
  return data?.data || data?.rows || data || [];
}

function resolvePlaceId(places: PlaceRecord[], city: string): PlaceRecord {
  const normalized = city.toLowerCase().replace(/\s+/g, "-");
  const match = places.find(
    (p) =>
      p.title?.toLowerCase().replace(/\s+/g, "-") === normalized ||
      p.id?.toLowerCase().includes(normalized)
  );
  if (!match) {
    const available = places.slice(0, 10).map((p) => p.title || p.id).join(", ");
    throw new Error(`City "${city}" not found. Available (sample): ${available}`);
  }
  console.log(`✅ Place resolved: ${match.title} (${match.id})`);
  return match;
}

// ─── Properties: Paginated fetch ─────────────────────────────────────────────
async function fetchPropertyPage(
  publicToken: string,
  placeId: string,
  offset: number
): Promise<{ rows: PropertyRecord[]; total: number }> {
  const fieldParams = PROPERTY_FIELDS.map((f) => `fields[]=${encodeURIComponent(f)}`).join("&");
  const url =
    `${GRIDICS_API_BASE}?type=_property_record&action=_property_record` +
    `&featureLayer=state&publicToken=${publicToken}&${fieldParams}` +
    `&rows=${PAGE_SIZE}&offset=${offset}&state_env=${STATE_ENV}&place=${placeId}`;

  const res = await fetchWithRetry(url);
  const data = await res.json();
  return {
    rows: data?.data || data?.rows || [],
    total: data?.total || data?.count || 0,
  };
}

async function fetchAllProperties(
  publicToken: string,
  placeId: string
): Promise<PropertyRecord[]> {
  const all: PropertyRecord[] = [];
  let offset = 0;
  let total = Infinity;

  while (offset < total) {
    console.log(`  Fetching offset=${offset}/${total === Infinity ? "?" : total}...`);
    const { rows, total: t } = await fetchPropertyPage(publicToken, placeId, offset);
    if (t > 0) total = t;
    if (rows.length === 0) break;
    all.push(...rows);
    offset += PAGE_SIZE;
  }

  return all;
}

// ─── Supabase: Upsert propzone_intel ─────────────────────────────────────────
async function upsertToSupabase(records: PropertyRecord[]): Promise<number> {
  if (!SUPABASE_URL || !SUPABASE_KEY) {
    console.warn("⚠️  SUPABASE_URL/SUPABASE_KEY not set — skipping storage");
    return 0;
  }

  const rows = records.map((r) => ({
    parcel_id: r.parcel_id || r.id,
    zone_code: r.zone_code || null,
    zone_subzone: r.zone_subzone || null,
    zone_type: r.zone_type || null,
    max_height: r.max_height ?? null,
    max_stories: r.max_stories ?? null,
    far: r.far ?? null,
    lot_coverage: r.lot_coverage ?? null,
    residential_density: r.residential_density ?? null,
    max_units: r.max_units ?? null,
    setbacks: {
      front: r.setback_front ?? null,
      side: r.setback_side ?? null,
      rear: r.setback_rear ?? null,
      water: r.setback_water ?? null,
    },
    owner_name: r.owner_name || null,
    address: r.address || r.title || null,
    lot_size_sqft: r.lot_size_sqft ?? null,
    raw_data: r,
    scraped_at: new Date().toISOString(),
  }));

  const BATCH = 500;
  let stored = 0;

  for (let i = 0; i < rows.length; i += BATCH) {
    const batch = rows.slice(i, i + BATCH);
    const res = await fetch(`${SUPABASE_URL}/rest/v1/propzone_intel`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "apikey": SUPABASE_KEY,
        "Authorization": `Bearer ${SUPABASE_KEY}`,
        "Prefer": "resolution=merge-duplicates",
      },
      body: JSON.stringify(batch),
    });

    if (!res.ok) {
      const err = await res.text();
      console.error(`  Supabase batch error: ${err}`);
    } else {
      stored += batch.length;
      console.log(`  Stored batch ${Math.floor(i / BATCH) + 1}: ${batch.length} records`);
    }
  }

  return stored;
}

// ─── ZoneWise comparison fetch ────────────────────────────────────────────────
async function fetchZoneWiseRecord(parcelId: string): Promise<Record<string, unknown> | null> {
  if (!SUPABASE_URL || !SUPABASE_KEY) return null;

  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/zoning_assignments?parcel_id=eq.${encodeURIComponent(parcelId)}&limit=1`,
    {
      headers: {
        "apikey": SUPABASE_KEY,
        "Authorization": `Bearer ${SUPABASE_KEY}`,
      },
    }
  );

  if (!res.ok) return null;
  const data = await res.json();
  return data?.[0] || null;
}

async function fetchPropZoneRecord(parcelId: string): Promise<Record<string, unknown> | null> {
  if (!SUPABASE_URL || !SUPABASE_KEY) return null;

  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/propzone_intel?parcel_id=eq.${encodeURIComponent(parcelId)}&limit=1`,
    {
      headers: {
        "apikey": SUPABASE_KEY,
        "Authorization": `Bearer ${SUPABASE_KEY}`,
      },
    }
  );

  if (!res.ok) return null;
  const data = await res.json();
  return data?.[0] || null;
}

// ─── Gap analysis ─────────────────────────────────────────────────────────────
const COMPARE_FIELDS = [
  "zone_code", "max_height", "max_stories", "far", "lot_coverage",
  "residential_density", "max_units", "setback_front", "setback_side",
  "setback_rear", "setback_water",
];

function analyzeGaps(
  propzone: Record<string, unknown>,
  zonewise: Record<string, unknown>
): { gaps: string[]; matches: string[] } {
  const gaps: string[] = [];
  const matches: string[] = [];

  for (const field of COMPARE_FIELDS) {
    const pz = propzone[field];
    const zw = zonewise[field];

    if (pz !== undefined && pz !== null) {
      if (zw !== undefined && zw !== null) {
        matches.push(field);
      } else {
        gaps.push(`${field}: PropZone has value (${pz}), ZoneWise missing`);
      }
    }
  }

  return { gaps, matches };
}

// ─── Telegram notification ────────────────────────────────────────────────────
async function sendTelegram(message: string): Promise<void> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) return;

  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text: message,
      parse_mode: "Markdown",
    }),
  });
}

// ─── HTTP helper with retry ───────────────────────────────────────────────────
async function fetchWithRetry(url: string, options?: RequestInit): Promise<Response> {
  let lastErr: Error | undefined;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(url, {
        ...options,
        headers: {
          "User-Agent": "Mozilla/5.0 (compatible; BidDeedBot/1.0)",
          ...(options?.headers || {}),
        },
      });
      if (res.ok) return res;
      throw new Error(`HTTP ${res.status} ${res.statusText}`);
    } catch (err: any) {
      lastErr = err;
      if (attempt < MAX_RETRIES) {
        const delay = 1000 * attempt;
        console.warn(`  Retry ${attempt}/${MAX_RETRIES} after ${delay}ms: ${err.message}`);
        await new Promise((r) => setTimeout(r, delay));
      }
    }
  }

  throw lastErr || new Error("fetchWithRetry exhausted");
}

// ─── Commands ─────────────────────────────────────────────────────────────────
async function cmdScrape(city: string): Promise<void> {
  const start = Date.now();
  console.log(`\n🔍 PropZone Intel — Scraping: ${city}\n`);

  if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });

  // Step 1: Auth
  const { publicToken } = await fetchPublicToken();

  // Step 2: Resolve place
  const places = await fetchPlaces(publicToken);
  const place = resolvePlaceId(places, city);

  // Step 3: Fetch all parcels
  console.log(`\n📦 Fetching property records...`);
  const records = await fetchAllProperties(publicToken, place.id);
  console.log(`✅ Fetched ${records.length} records`);

  // Step 4: Store in Supabase
  console.log(`\n💾 Storing in Supabase propzone_intel...`);
  const stored = await upsertToSupabase(records);

  // Step 5: Save local JSON backup
  const outFile = join(OUTPUT_DIR, `${city}-${Date.now()}.json`);
  writeFileSync(outFile, JSON.stringify({ city, placeId: place.id, records }, null, 2));

  const result: ScrapeResult = {
    city,
    placeId: place.id,
    totalRecords: records.length,
    stored,
    errors: records.length - stored,
    durationMs: Date.now() - start,
  };

  console.log(`\n✅ DONE`);
  console.log(`   City: ${result.city} (${result.placeId})`);
  console.log(`   Records: ${result.totalRecords}`);
  console.log(`   Stored: ${result.stored}`);
  console.log(`   Duration: ${(result.durationMs / 1000).toFixed(1)}s`);
  console.log(`   Backup: ${outFile}`);

  await sendTelegram(
    `*PropZone Intel* ✅\n` +
    `City: ${city}\nRecords: ${result.totalRecords}\nStored: ${result.stored}\n` +
    `Duration: ${(result.durationMs / 1000).toFixed(1)}s`
  );
}

async function cmdCompare(parcelId: string): Promise<void> {
  console.log(`\n🔄 Comparing parcel: ${parcelId}\n`);

  const [propzone, zonewise] = await Promise.all([
    fetchPropZoneRecord(parcelId),
    fetchZoneWiseRecord(parcelId),
  ]);

  if (!propzone && !zonewise) {
    console.error(`❌ Parcel ${parcelId} not found in either system`);
    process.exit(1);
  }

  const result: CompareResult = {
    parcelId,
    propzone,
    zonewise,
    gaps: [],
    matches: [],
  };

  if (propzone && zonewise) {
    const { gaps, matches } = analyzeGaps(
      propzone as Record<string, unknown>,
      zonewise as Record<string, unknown>
    );
    result.gaps = gaps;
    result.matches = matches;
  } else if (propzone && !zonewise) {
    result.gaps = ["ZoneWise record not found for this parcel"];
  } else {
    result.gaps = ["PropZone record not found for this parcel"];
  }

  console.log(`📊 Comparison Results:`);
  console.log(`   Parcel: ${parcelId}`);
  console.log(`   PropZone: ${propzone ? "✅ found" : "❌ missing"}`);
  console.log(`   ZoneWise: ${zonewise ? "✅ found" : "❌ missing"}`);
  console.log(`\n✅ Matches (${result.matches.length}): ${result.matches.join(", ") || "none"}`);
  console.log(`\n⚠️  Gaps (${result.gaps.length}):`);
  result.gaps.forEach((g) => console.log(`   - ${g}`));
}

async function cmdFields(): Promise<void> {
  console.log(`\n📋 PropZone Available Fields (${PROPERTY_FIELDS.length}):\n`);
  PROPERTY_FIELDS.forEach((f, i) => {
    console.log(`  ${String(i + 1).padStart(2)}. ${f}`);
  });
}

async function cmdTest(): Promise<void> {
  console.log(`\n🧪 PropZone API Connection Test\n`);

  // Test 1: GraphQL auth
  console.log(`[1/3] Testing GraphQL mainSettings...`);
  const { publicToken, mapboxToken } = await fetchPublicToken();
  console.log(`      publicToken: ${publicToken.substring(0, 30)}...`);
  console.log(`      mapboxToken: ${mapboxToken ? mapboxToken.substring(0, 20) + "..." : "N/A"}`);

  // Test 2: Places endpoint
  console.log(`\n[2/3] Testing places endpoint...`);
  const places = await fetchPlaces(publicToken);
  console.log(`      Found ${places.length} FL places`);
  if (places.length > 0) {
    console.log(`      Sample: ${places.slice(0, 3).map((p) => p.title || p.id).join(", ")}`);
  }

  // Test 3: Property record fetch (1 record)
  console.log(`\n[3/3] Testing property record fetch (1 record)...`);
  if (places.length > 0) {
    const place = places[0];
    const { rows, total } = await fetchPropertyPage(publicToken, place.id, 0);
    console.log(`      Place: ${place.title || place.id} → ${total} total records`);
    console.log(`      Sample keys: ${rows.length > 0 ? Object.keys(rows[0]).slice(0, 8).join(", ") : "no data"}`);
  }

  console.log(`\n✅ All tests passed — PropZone API accessible`);
}

// ─── CLI Entry Point ──────────────────────────────────────────────────────────
async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === "--help" || command === "-h") {
    console.log(`
PropZone Intel — Gridics/PropZone API Scraper
BidDeed.AI / Everest Capital USA

Usage:
  propzone scrape <city>      Scrape all parcel zoning data for a city
  propzone compare <parcelId> Compare ZoneWise vs PropZone data for a parcel
  propzone fields             List all available PropZone fields
  propzone test               Verify API access

Cities (Brevard County FL):
  satellite-beach, melbourne, palm-bay, cocoa, titusville,
  rockledge, indialantic, indian-harbour-beach, cape-canaveral

Env vars:
  SUPABASE_URL     Supabase project URL (for storage + comparison)
  SUPABASE_KEY     Supabase service role key
  TELEGRAM_BOT_TOKEN  Telegram bot token (optional notifications)
  TELEGRAM_CHAT_ID    Telegram chat ID (optional notifications)
    `);
    return;
  }

  switch (command) {
    case "scrape": {
      const city = args[1] || DEFAULT_CITY;
      await cmdScrape(city);
      break;
    }
    case "compare": {
      const parcelId = args[1];
      if (!parcelId) {
        console.error("Usage: propzone compare <parcelId>");
        process.exit(1);
      }
      await cmdCompare(parcelId);
      break;
    }
    case "fields": {
      await cmdFields();
      break;
    }
    case "test": {
      await cmdTest();
      break;
    }
    default:
      console.error(`Unknown command: ${command}. Run --help for usage.`);
      process.exit(1);
  }
}

main().catch((err) => {
  console.error(`❌ Fatal: ${err.message}`);
  process.exit(1);
});

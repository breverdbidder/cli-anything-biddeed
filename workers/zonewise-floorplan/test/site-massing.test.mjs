/**
 * Real-parcel test for site-massing.js — no mocking of geometry or zoning
 * standards. Fixtures are live snapshots (fetched 2026-08-16) of 3 real
 * Brevard County (co_no=15) parcels from zw_parcels + their matching
 * zone_standards row, via the same Supabase project this Worker reads at
 * runtime. Run: `node test/site-massing.test.mjs` from workers/zonewise-floorplan/.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { reprojectParcelBoundary, stateplaneZoneForCoNo } from "../geo.js";
import { computeBuildableEnvelope, generateSiteMassing } from "../site-massing.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixture = (name) => JSON.parse(readFileSync(path.join(__dirname, "fixtures", name), "utf8"));

const standards = fixture("zone_standards.json");
let passed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ok - ${name}`);
  } catch (err) {
    console.error(`  FAIL - ${name}\n    ${err.message}`);
    process.exitCode = 1;
  }
}

function loadParcelRing(fixtureFile) {
  const [row] = fixture(fixtureFile);
  const zone = stateplaneZoneForCoNo(row.co_no);
  assert.ok(zone, `co_no ${row.co_no} must resolve to a State Plane zone`);
  const { rings, partsDropped } = reprojectParcelBoundary(row.geom, zone.epsg);
  return { row, ring: rings[0], zone, partsDropped };
}

console.log("=== single_family (5045 Volusia Ave, RU-1-11) ===");
{
  const { row, ring, zone } = loadParcelRing("single_family.json");
  const std = standards.single_family;

  test("co_no 15 resolves to VERIFIED EPSG:2236", () => {
    assert.equal(zone.epsg, "EPSG:2236");
    assert.equal(zone.confidence, "VERIFIED");
  });

  test("reprojected parcel area matches deed acreage within 5%", () => {
    const env = computeBuildableEnvelope(ring, std);
    const acres = env.parcelAreaSqft / 43560;
    const deltaPct = Math.abs(acres - row.acres_deed) / row.acres_deed;
    assert.ok(deltaPct < 0.05, `reprojected ${acres.toFixed(3)} acres vs deed ${row.acres_deed} acres (${(deltaPct * 100).toFixed(1)}% off)`);
  });

  test("buildable envelope is positive and smaller than the parcel bbox", () => {
    const env = computeBuildableEnvelope(ring, std);
    assert.ok(env.widthFt > 0 && env.depthFt > 0, "envelope must have positive extent");
    assert.ok(env.widthFt * env.depthFt < env.parcelAreaSqft, "envelope must be smaller than the parcel area (setbacks were applied)");
  });

  test("generateSiteMassing returns single_family options, unit_count=1, within coverage+density caps", () => {
    const result = generateSiteMassing(ring, std, "single_family");
    assert.ok(result.options.length > 0, "expected at least one compliant single_family option");
    assert.ok(result.options.length <= 5, "must never return more than 5 options");
    for (const opt of result.options) {
      assert.equal(opt.unit_count, 1);
      assert.ok(opt.lot_coverage_pct <= std.max_lot_coverage_pct, `coverage ${opt.lot_coverage_pct}% must be <= zone max ${std.max_lot_coverage_pct}%`);
      assert.equal(opt.setback_compliant, true);
      assert.equal(opt.footprints.length, 1);
      assert.equal(opt.footprints[0].kind, "building");
    }
    // ranks are 1..N, best (highest score) first
    for (let i = 1; i < result.options.length; i++) {
      assert.ok(result.options[i - 1].score >= result.options[i].score, "options must be ranked by descending score");
      assert.equal(result.options[i].option_rank, i + 1);
    }
  });
}

console.log("=== townhome_row (2916 Nicholson St, RU-2-10) ===");
{
  const { ring } = loadParcelRing("townhome.json");
  const std = standards.townhome;

  test("generateSiteMassing returns townhome_row options, each unit_count >= 2, within density cap", () => {
    const result = generateSiteMassing(ring, std, "townhome_row");
    assert.ok(result.options.length > 0, "expected at least one compliant townhome_row option");
    const densityCapUnits = Math.floor((std.max_density_du_acre * result.envelope.parcelAreaSqft) / 43560);
    for (const opt of result.options) {
      assert.ok(opt.unit_count >= 2, "a townhome row must place at least 2 units");
      assert.ok(opt.unit_count <= densityCapUnits, `unit_count ${opt.unit_count} must be <= density cap ${densityCapUnits}`);
      assert.ok(opt.lot_coverage_pct <= std.max_lot_coverage_pct);
      const hasAccessDrive = opt.footprints.some((f) => f.kind === "access_drive");
      assert.ok(hasAccessDrive, "townhome_row must reserve an access-drive footprint");
    }
  });
}

console.log("=== multifamily_grid (546 Player Ln, RU-2-30) ===");
{
  const { ring } = loadParcelRing("multifamily.json");
  const std = standards.multifamily;

  test("generateSiteMassing returns multifamily_grid options with plausible unit counts", () => {
    const result = generateSiteMassing(ring, std, "multifamily_grid");
    assert.ok(result.options.length > 0, "expected at least one compliant multifamily_grid option");
    const densityCapUnits = Math.floor((std.max_density_du_acre * result.envelope.parcelAreaSqft) / 43560);
    for (const opt of result.options) {
      assert.ok(opt.unit_count >= 1);
      assert.ok(opt.unit_count <= densityCapUnits);
      assert.ok(opt.lot_coverage_pct <= std.max_lot_coverage_pct);
      assert.ok(opt.footprints.some((f) => f.kind === "building"));
    }
  });
}

console.log("=== min_lot_sqft gate ===");
{
  const { ring } = loadParcelRing("multifamily.json");
  test("a parcel below min_lot_sqft returns zero options with an explicit skipped_reason", () => {
    const impossibleStandards = { ...standards.multifamily, min_lot_sqft: 10_000_000 };
    const result = generateSiteMassing(ring, impossibleStandards, "multifamily_grid");
    assert.equal(result.options.length, 0);
    assert.ok(typeof result.skipped_reason === "string" && result.skipped_reason.length > 0);
  });
}

console.log(`\n${passed} assertions passed`);
if (process.exitCode) {
  console.error("SOME TESTS FAILED");
  process.exit(1);
}

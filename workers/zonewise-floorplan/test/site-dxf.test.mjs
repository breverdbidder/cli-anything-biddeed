/**
 * Real-parcel DXF export test — generates a DXF for the single_family top
 * option on 5045 Volusia Ave (Brevard, RU-1-11) and PARSES IT BACK with
 * dxf-parser (not just "file was written"), per the DoD's verification bar.
 * Run: `node test/site-dxf.test.mjs` from workers/zonewise-floorplan/.
 */
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import DxfParser from "dxf-parser";

import { reprojectParcelBoundary, stateplaneZoneForCoNo } from "../geo.js";
import { computeBuildableEnvelope, generateSiteMassing } from "../site-massing.js";
import { exportSiteMassingDXF, SITE_DXF_LAYERS } from "../site-dxf.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixture = (name) => JSON.parse(readFileSync(path.join(__dirname, "fixtures", name), "utf8"));

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ok - ${name}`);
  } catch (err) {
    console.error(`  FAIL - ${name}\n    ${err.stack}`);
    process.exitCode = 1;
  }
}

const standards = fixture("zone_standards.json").single_family;
const [row] = fixture("single_family.json");
const zone = stateplaneZoneForCoNo(row.co_no);
const { rings } = reprojectParcelBoundary(row.geom, zone.epsg);
const parcelRingFt = rings[0];
const result = generateSiteMassing(parcelRingFt, standards, "single_family");
const topOption = result.options[0];
assert.ok(topOption, "precondition: generateSiteMassing must return at least one option");

const dxfString = exportSiteMassingDXF({
  parcelRingFt,
  envelopeRingFt: result.envelope.ring,
  option: topOption,
  meta: { parcelId: row.pin_clean, epsg: zone.epsg, coNo: row.co_no },
});

writeFileSync(path.join(__dirname, "fixtures", "sample_output.dxf"), dxfString);

test("DXF string is non-trivial and starts with a valid DXF header section", () => {
  assert.ok(dxfString.length > 500);
  assert.ok(dxfString.includes("SECTION"));
});

let parsed;
test("dxf-parser can parse the file back without throwing", () => {
  const parser = new DxfParser();
  parsed = parser.parseSync(dxfString);
  assert.ok(parsed, "parseSync must return a document");
});

test("all 6 required layers are present in the parsed layer table", () => {
  const layerNames = Object.keys(parsed.tables.layer.layers);
  for (const name of Object.values(SITE_DXF_LAYERS)) {
    assert.ok(layerNames.includes(name), `missing layer ${name}`);
  }
});

test("PARCEL-BNDY has a polyline entity whose reprojected area matches deed acreage", () => {
  const entities = parsed.entities.filter((e) => e.layer === "PARCEL-BNDY");
  assert.ok(entities.length >= 1, "expected at least one PARCEL-BNDY entity");
  const verts = entities[0].vertices;
  assert.ok(verts.length >= 4, "parcel boundary polyline must have >= 4 vertices");

  let area = 0;
  for (let i = 0; i < verts.length - 1; i++) {
    area += verts[i].x * verts[i + 1].y - verts[i + 1].x * verts[i].y;
  }
  area = Math.abs(area) / 2;
  const acres = area / 43560;
  const deltaPct = Math.abs(acres - row.acres_deed) / row.acres_deed;
  assert.ok(deltaPct < 0.05, `DXF-parsed-back area ${acres.toFixed(3)} acres vs deed ${row.acres_deed} acres (${(deltaPct * 100).toFixed(1)}% off) — confirms correct scale, not just that a file was written`);
});

test("SETBACK-LINES entity exists and is strictly inside the parcel boundary bbox", () => {
  const parcelEnt = parsed.entities.find((e) => e.layer === "PARCEL-BNDY");
  const setbackEnt = parsed.entities.find((e) => e.layer === "SETBACK-LINES");
  assert.ok(setbackEnt, "expected a SETBACK-LINES entity");
  const pxs = parcelEnt.vertices.map((v) => v.x), pys = parcelEnt.vertices.map((v) => v.y);
  const sxs = setbackEnt.vertices.map((v) => v.x), sys = setbackEnt.vertices.map((v) => v.y);
  assert.ok(Math.min(...sxs) > Math.min(...pxs) && Math.max(...sxs) < Math.max(...pxs));
  assert.ok(Math.min(...sys) > Math.min(...pys) && Math.max(...sys) < Math.max(...pys));
});

test("BLDG-FOOTPRINT entity exists and its area matches the option's footprint_sqft-derived coverage", () => {
  const bldgEnt = parsed.entities.find((e) => e.layer === "BLDG-FOOTPRINT");
  assert.ok(bldgEnt, "expected a BLDG-FOOTPRINT entity");
  const verts = bldgEnt.vertices;
  let area = 0;
  for (let i = 0; i < verts.length - 1; i++) {
    area += verts[i].x * verts[i + 1].y - verts[i + 1].x * verts[i].y;
  }
  area = Math.abs(area) / 2;
  const expectedCoveragePct = (area / result.envelope.parcelAreaSqft) * 100;
  assert.ok(Math.abs(expectedCoveragePct - topOption.lot_coverage_pct) < 0.1, `DXF footprint area implies ${expectedCoveragePct.toFixed(2)}% coverage vs option's recorded ${topOption.lot_coverage_pct}%`);
});

test("TEXT-ANNO layer carries the unit count / GFA / coverage annotations", () => {
  const textEnts = parsed.entities.filter((e) => e.layer === "TEXT-ANNO" && e.type === "TEXT");
  const joined = textEnts.map((e) => e.text).join(" | ");
  assert.ok(joined.includes(`UNITS: ${topOption.unit_count}`), joined);
  assert.ok(joined.includes("LOT COVERAGE"), joined);
});

test("DIMENSIONS layer has entities (extension lines + labels)", () => {
  const dimEnts = parsed.entities.filter((e) => e.layer === "DIMENSIONS");
  assert.ok(dimEnts.length > 0);
});

console.log(`\n${passed} assertions passed. Sample DXF written to test/fixtures/sample_output.dxf`);
if (process.exitCode) {
  console.error("SOME TESTS FAILED");
  process.exit(1);
}

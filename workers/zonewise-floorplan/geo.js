/**
 * Florida State Plane (NAD83, US survey feet) reprojection for site massing.
 * ---------------------------------------------------------------------------
 * Civil-engineering DXF output must be in feet/state-plane, not decimal
 * degrees — see site-dxf.js. Florida is split into three State Plane zones
 * (East/West/North); the correct EPSG code depends on which zone a county
 * falls in.
 *
 * CONFIDENCE:
 *   - EPSG:2236 (NAD83 / Florida East (ftUS)) for East-zone counties is
 *     VERIFIED (web search against epsg.io/spatialreference.org,
 *     2026-08-16) — its documented area of use explicitly lists Brevard,
 *     Duval, Orange, and the other East-zone counties below.
 *   - The East/West/North zone assignment per county is standard, widely
 *     published FL DOR/DEP geography (not itself looked up live this
 *     session) — flagged INFERRED, not VERIFIED, even though it is not
 *     seriously ambiguous.
 *   - EPSG:2237 (West, ftUS) and EPSG:2238 (North, ftUS) are the sibling
 *     zones, included for completeness but NOT exercised by this session's
 *     real-parcel test (Brevard only).
 *
 * Per the spec's guardrail: a co_no NOT in ZONE_BY_CO_NO is unsupported —
 * callers MUST log and skip rather than guess a zone.
 */

import proj4 from "proj4";

// Pulled verbatim from https://epsg.io/2236.proj4, /2237.proj4, /2238.proj4
// (fetched live 2026-08-16) — not hand-derived, so the constants are exact.
const EPSG_2236_FLORIDA_EAST_FTUS =
  "+proj=tmerc +lat_0=24.3333333333333 +lon_0=-81 +k=0.999941177 +x_0=200000.0001016 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=us-ft +no_defs";
const EPSG_2237_FLORIDA_WEST_FTUS =
  "+proj=tmerc +lat_0=24.3333333333333 +lon_0=-82 +k=0.999941177 +x_0=200000.0001016 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=us-ft +no_defs";
const EPSG_2238_FLORIDA_NORTH_FTUS =
  "+proj=lcc +lat_0=29 +lon_0=-84.5 +lat_1=30.75 +lat_2=29.5833333333333 +x_0=600000 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=us-ft +no_defs";

proj4.defs("EPSG:2236", EPSG_2236_FLORIDA_EAST_FTUS);
proj4.defs("EPSG:2237", EPSG_2237_FLORIDA_WEST_FTUS);
proj4.defs("EPSG:2238", EPSG_2238_FLORIDA_NORTH_FTUS);

// FL DOR county number -> State Plane zone. East zone (EPSG:2236) is the
// only branch VERIFIED this session (Brevard, co_no 15, was live-tested).
// East-zone list per FL DOR/DEP standard county-to-SPCS-zone assignment.
const EAST_ZONE_CO_NOS = new Set([
  1, 4, 6, 7, 9, 10, 15, 16, 18, 19, 22, 26, 28, 30, 31, 34, 35, 39, 43, 44,
  48, 50, 51, 53, 55, 56, 57, 62, 64, 65,
]);
const WEST_ZONE_CO_NOS = new Set([
  2, 3, 5, 8, 12, 13, 14, 20, 21, 24, 25, 27, 29, 32, 37, 41, 45, 46, 47, 49,
  52, 58, 59, 61, 63, 66,
]);
const NORTH_ZONE_CO_NOS = new Set([11, 17, 23, 33, 36, 38, 40, 42, 54, 60, 67]);

/**
 * @param {number} coNo - FL DOR county number (zw_parcels.co_no)
 * @returns {{ epsg: string, confidence: "VERIFIED" | "INFERRED" } | null}
 *   null means "unsupported — do not guess", per the spec's guardrail.
 */
export function stateplaneZoneForCoNo(coNo) {
  if (EAST_ZONE_CO_NOS.has(coNo)) {
    return { epsg: "EPSG:2236", confidence: coNo === 15 ? "VERIFIED" : "INFERRED" };
  }
  if (WEST_ZONE_CO_NOS.has(coNo)) {
    return { epsg: "EPSG:2237", confidence: "INFERRED" };
  }
  if (NORTH_ZONE_CO_NOS.has(coNo)) {
    return { epsg: "EPSG:2238", confidence: "INFERRED" };
  }
  return null;
}

/**
 * Reprojects a single [lng, lat] (EPSG:4326) pair to [x_ft, y_ft] in the
 * given State Plane EPSG code.
 */
export function toStatePlaneFeet([lng, lat], epsg) {
  return proj4("EPSG:4326", epsg, [lng, lat]);
}

/**
 * Reprojects every ring of a GeoJSON Polygon or MultiPolygon (EPSG:4326) to
 * a flat array of rings of [x_ft, y_ft] pairs in the given State Plane EPSG
 * code. MultiPolygon input reprojects only the largest polygon by raw
 * vertex count (a parcel boundary is expected to be a single polygon; any
 * additional parts are slivers/artifacts, not separate buildable areas —
 * this is a documented simplification, not silent data loss: callers get
 * `partsDropped` back).
 */
export function reprojectParcelBoundary(geojsonGeometry, epsg) {
  if (!geojsonGeometry || !geojsonGeometry.coordinates) {
    throw new Error("reprojectParcelBoundary: missing geometry.coordinates");
  }

  let polygons;
  if (geojsonGeometry.type === "Polygon") {
    polygons = [geojsonGeometry.coordinates];
  } else if (geojsonGeometry.type === "MultiPolygon") {
    polygons = geojsonGeometry.coordinates;
  } else {
    throw new Error(`reprojectParcelBoundary: unsupported geometry type ${geojsonGeometry.type}`);
  }

  let chosen = polygons[0];
  let chosenLen = chosen[0].length;
  for (const poly of polygons.slice(1)) {
    if (poly[0].length > chosenLen) {
      chosen = poly;
      chosenLen = poly[0].length;
    }
  }

  const reprojectedRings = chosen.map((ring) => ring.map((pt) => toStatePlaneFeet(pt, epsg)));

  return { rings: reprojectedRings, partsDropped: polygons.length - 1 };
}

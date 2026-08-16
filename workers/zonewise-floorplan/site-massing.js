/**
 * ZoneWise Site Massing solver.
 * ---------------------------------------------------------------------------
 * Geometric constraint-solving over a parcel's buildable envelope — NOT
 * image generation. Pure functions, operates entirely in feet (State Plane,
 * via geo.js), independent of the Worker/persistence layer so it can be
 * unit-tested directly against real parcel geometry.
 *
 * SCOPE / HONEST LIMITATIONS (v1, matches the non-goals in the issue):
 *   - No topography/grading. No 3D/multi-story volumetric optimization —
 *     `stories` is a flat input the caller passes, never solved for.
 *   - Buildable envelope is an AXIS-ALIGNED RECTANGLE inset from the
 *     parcel's bounding box by the zone's setbacks, exactly mirroring the
 *     bbox-based "dimensional_fit" approximation zoning.js already uses for
 *     the floorplan tool (see zoning.js's own documented limitations). This
 *     is NOT true per-edge polygon offsetting on an irregular lot boundary
 *     — for a non-rectangular parcel the true buildable area may be smaller
 *     than this envelope. `envelopeFullyInsideParcel` in the returned
 *     envelope object tells the caller whether the parcel is regular enough
 *     for this approximation to hold; irregular lots still produce options,
 *     but with that flag false so the caller can surface the caveat.
 *   - Front/rear vs. side setback assignment is a HEURISTIC: the shorter
 *     bbox dimension is assumed to be the street-facing frontage (side
 *     setbacks applied there), the longer dimension the depth (front+rear
 *     applied there). There is no street-centerline data feeding this — for
 *     an oddly-proportioned or corner lot this can be wrong. Documented,
 *     not silently assumed correct.
 *   - single_family templates are rectangles only in v1 — L/T footprint
 *     templates from the original spec text are deferred, not built.
 *   - Footprint coordinates are returned in the SAME feet/State-Plane frame
 *     as the envelope (not re-projected to WGS84) so site-dxf.js can place
 *     them directly with no second reprojection pass.
 */

const SQFT_PER_ACRE = 43560;
const MAX_RAW_PLACEMENTS = 500;
const GRID_STEP_FT = 5;
const ACCESS_DRIVE_WIDTH_FT = 24; // typical FL fire-lane/access-drive minimum

function polygonAreaFt(ring) {
  let area = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[i + 1];
    area += x1 * y2 - x2 * y1;
  }
  return Math.abs(area) / 2;
}

function bboxOf(ring) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [x, y] of ring) {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }
  return { minX, minY, maxX, maxY };
}

/** Even-odd point-in-polygon test, ring = closed [[x,y],...]. */
function pointInRing([px, py], ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 2; i < ring.length - 1; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    const intersects = yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

/**
 * @param {Array<[number,number]>} ringFt - closed parcel boundary ring, feet
 * @param {object} standards - zone_standards row (front_setback_ft, side_setback_ft,
 *   rear_setback_ft, min_lot_sqft, max_lot_coverage_pct, max_density_du_acre, ...)
 */
export function computeBuildableEnvelope(ringFt, standards) {
  if (!Array.isArray(ringFt) || ringFt.length < 4) {
    throw new Error("computeBuildableEnvelope: ringFt must be a closed ring with >= 4 points");
  }
  const front = standards.front_setback_ft ?? 0;
  const rear = standards.rear_setback_ft ?? 0;
  const side = standards.side_setback_ft ?? 0;

  const parcelAreaSqft = polygonAreaFt(ringFt);
  const box = bboxOf(ringFt);
  const bboxWidth = box.maxX - box.minX; // x-extent
  const bboxHeight = box.maxY - box.minY; // y-extent

  // Heuristic: shorter bbox dimension = frontage (side setbacks), longer = depth (front+rear).
  const xIsFrontage = bboxWidth <= bboxHeight;

  const envMinX = xIsFrontage ? box.minX + side : box.minX + front;
  const envMaxX = xIsFrontage ? box.maxX - side : box.maxX - rear;
  const envMinY = xIsFrontage ? box.minY + front : box.minY + side;
  const envMaxY = xIsFrontage ? box.maxY - rear : box.maxY - side;

  const widthFt = envMaxX - envMinX;
  const depthFt = envMaxY - envMinY;

  const envelopeRing = [
    [envMinX, envMinY],
    [envMaxX, envMinY],
    [envMaxX, envMaxY],
    [envMinX, envMaxY],
    [envMinX, envMinY],
  ];
  const envelopeFullyInsideParcel =
    widthFt > 0 && depthFt > 0 && envelopeRing.every((pt) => pointInRing(pt, ringFt));

  return {
    minX: envMinX,
    minY: envMinY,
    maxX: envMaxX,
    maxY: envMaxY,
    widthFt,
    depthFt,
    ring: envelopeRing,
    parcelAreaSqft,
    frontageAxis: xIsFrontage ? "x" : "y",
    envelopeFullyInsideParcel,
  };
}

function densityCapUnits(parcelAreaSqft, standards) {
  if (typeof standards.max_density_du_acre !== "number") return Infinity;
  return Math.floor((standards.max_density_du_acre * parcelAreaSqft) / SQFT_PER_ACRE);
}

/**
 * Lot-coverage is almost always the binding constraint (an envelope-fit
 * footprint routinely exceeds it), so every generator sizes footprints
 * against this ceiling directly rather than against the raw envelope size.
 */
function maxFootprintSqftFor(envelope, standards) {
  const pct = standards.max_lot_coverage_pct ?? 100;
  return envelope.parcelAreaSqft * (pct / 100);
}

// --- single_family --------------------------------------------------------

function generateSingleFamilyCandidates(envelope, standards, opts) {
  const stories = opts.stories ?? 1;
  const raw = [];
  const aspectRatios = [1.0, 1.3, 1.6, 2.0];
  const sizeFractions = [0.95, 0.8, 0.6, 0.4];
  const maxFootprintSqft = maxFootprintSqftFor(envelope, standards);

  for (const aspect of aspectRatios) {
    for (const frac of sizeFractions) {
      for (const rotated of [false, true]) {
        const envW = rotated ? envelope.depthFt : envelope.widthFt;
        const envD = rotated ? envelope.widthFt : envelope.depthFt;
        if (envW <= 0 || envD <= 0) continue;

        // Target footprint area = frac of the coverage-cap ceiling, at this aspect ratio.
        const targetArea = maxFootprintSqft * frac;
        let fpW = Math.sqrt(targetArea * aspect);
        let fpD = targetArea / fpW;
        if (fpW > envW || fpD > envD) continue; // doesn't fit this envelope orientation
        if (fpW < 10 || fpD < 10) continue; // below any plausible dwelling footprint

        const slackX = (rotated ? envelope.depthFt : envelope.widthFt) - fpW;
        const slackY = (rotated ? envelope.widthFt : envelope.depthFt) - fpD;
        const stepsX = Math.max(1, Math.floor(slackX / GRID_STEP_FT) + 1);
        const stepsY = Math.max(1, Math.floor(slackY / GRID_STEP_FT) + 1);

        for (let sx = 0; sx < stepsX && raw.length < MAX_RAW_PLACEMENTS; sx++) {
          for (let sy = 0; sy < stepsY && raw.length < MAX_RAW_PLACEMENTS; sy++) {
            const offX = envelope.minX + sx * GRID_STEP_FT;
            const offY = envelope.minY + sy * GRID_STEP_FT;
            const w = rotated ? fpD : fpW;
            const d = rotated ? fpW : fpD;
            raw.push({
              layout_type: "single_family",
              footprints: [rect(offX, offY, w, d, "building")],
              unit_count: 1,
              gross_floor_area_sqft: w * d * stories,
              footprint_sqft: w * d,
              stories,
            });
          }
        }
      }
    }
  }
  return raw;
}

// --- townhome_row -----------------------------------------------------------

function generateTownhomeCandidates(envelope, standards, opts) {
  const stories = opts.stories ?? 2;
  const unitWidth = opts.unitWidthFt ?? 24;
  const unitDepth = opts.unitDepthFt ?? 40;
  const raw = [];
  const maxFootprintSqft = maxFootprintSqftFor(envelope, standards);
  const coverageUnitCap = Math.floor(maxFootprintSqft / (unitWidth * unitDepth));
  const densityUnitCap = densityCapUnits(envelope.parcelAreaSqft, standards);

  for (const rotated of [false, true]) {
    const envW = rotated ? envelope.depthFt : envelope.widthFt;
    const envD = rotated ? envelope.widthFt : envelope.depthFt;
    if (envW <= 0 || envD <= 0) continue;

    // Row runs along envW; a single access-drive strip reserved along the
    // near edge of envD, units occupy the remaining depth.
    const availableDepth = envD - ACCESS_DRIVE_WIDTH_FT;
    if (availableDepth < unitDepth) continue;

    const maxUnitsInRow = Math.min(Math.floor(envW / unitWidth), coverageUnitCap, densityUnitCap);
    if (maxUnitsInRow < 2) continue; // need >= 2 units to be a "row"

    for (const unitCount of [maxUnitsInRow, Math.max(2, Math.floor(maxUnitsInRow * 0.75)), Math.max(2, Math.floor(maxUnitsInRow * 0.5))]) {
      if (raw.length >= MAX_RAW_PLACEMENTS) break;
      const rowWidth = unitCount * unitWidth;
      const slackX = envW - rowWidth;
      const steps = Math.max(1, Math.floor(slackX / GRID_STEP_FT) + 1);

      for (let s = 0; s < steps && raw.length < MAX_RAW_PLACEMENTS; s++) {
        const baseX = (rotated ? envelope.minY : envelope.minX) + s * GRID_STEP_FT;
        const baseY = rotated ? envelope.minX : envelope.minY;

        const footprints = [];
        for (let u = 0; u < unitCount; u++) {
          const ux = baseX + u * unitWidth;
          const w = rotated ? unitDepth : unitWidth;
          const d = rotated ? unitWidth : unitDepth;
          const px = rotated ? baseY + ACCESS_DRIVE_WIDTH_FT : ux;
          const py = rotated ? ux : baseY + ACCESS_DRIVE_WIDTH_FT;
          footprints.push(rect(px, py, w, d, "building", `unit_${u + 1}`));
        }
        const driveW = rotated ? ACCESS_DRIVE_WIDTH_FT : rowWidth;
        const driveD = rotated ? rowWidth : ACCESS_DRIVE_WIDTH_FT;
        const drivePx = rotated ? baseY : baseX;
        const drivePy = rotated ? baseX : baseY;
        footprints.push(rect(drivePx, drivePy, driveW, driveD, "access_drive"));

        raw.push({
          layout_type: "townhome_row",
          footprints,
          unit_count: unitCount,
          gross_floor_area_sqft: unitCount * unitWidth * unitDepth * stories,
          footprint_sqft: unitCount * unitWidth * unitDepth,
          stories,
        });
      }
    }
  }
  return raw;
}

// --- multifamily_grid ---------------------------------------------------

function generateMultifamilyCandidates(envelope, standards, opts) {
  const stories = opts.stories ?? 3;
  const sqftPerUnit = opts.sqftPerUnit ?? 900;
  const raw = [];
  const maxFootprintSqft = maxFootprintSqftFor(envelope, standards);

  const gridConfigs = [
    { rows: 1, cols: 1 },
    { rows: 1, cols: 2 },
    { rows: 2, cols: 1 },
    { rows: 2, cols: 2 },
  ];

  for (const { rows, cols } of gridConfigs) {
    if (raw.length >= MAX_RAW_PLACEMENTS) break;
    const totalDriveW = (cols - 1) * ACCESS_DRIVE_WIDTH_FT;
    const totalDriveD = (rows - 1) * ACCESS_DRIVE_WIDTH_FT;
    const usableW = envelope.widthFt - totalDriveW;
    const usableD = envelope.depthFt - totalDriveD;
    if (usableW <= 0 || usableD <= 0) continue;

    for (const frac of [0.9, 0.7, 0.5]) {
      // Target TOTAL building footprint (all cells) = frac of the coverage-cap
      // ceiling, distributed evenly across the grid, aspect matched to the
      // per-cell usable rectangle (not the raw envelope) so cells stay
      // proportional instead of degenerating into slivers.
      const targetTotalFootprint = maxFootprintSqft * frac;
      const perCellTarget = targetTotalFootprint / (rows * cols);
      const cellAspect = usableW / cols / (usableD / rows);
      let bldgW = Math.sqrt(perCellTarget * cellAspect);
      let bldgD = perCellTarget / bldgW;
      if (bldgW > usableW / cols) {
        bldgW = usableW / cols;
        bldgD = perCellTarget / bldgW;
      }
      if (bldgD > usableD / rows) {
        bldgD = usableD / rows;
        bldgW = perCellTarget / bldgD;
      }
      if (bldgW < 20 || bldgD < 20) continue;

      const totalW = cols * bldgW + totalDriveW;
      const totalD = rows * bldgD + totalDriveD;
      const slackX = envelope.widthFt - totalW;
      const slackY = envelope.depthFt - totalD;
      if (slackX < 0 || slackY < 0) continue;
      const stepsX = Math.max(1, Math.floor(slackX / GRID_STEP_FT) + 1);
      const stepsY = Math.max(1, Math.floor(slackY / GRID_STEP_FT) + 1);

      for (let sx = 0; sx < stepsX && raw.length < MAX_RAW_PLACEMENTS; sx++) {
        for (let sy = 0; sy < stepsY && raw.length < MAX_RAW_PLACEMENTS; sy++) {
          const originX = envelope.minX + sx * GRID_STEP_FT;
          const originY = envelope.minY + sy * GRID_STEP_FT;
          const footprints = [];
          for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
              const px = originX + c * (bldgW + ACCESS_DRIVE_WIDTH_FT);
              const py = originY + r * (bldgD + ACCESS_DRIVE_WIDTH_FT);
              footprints.push(rect(px, py, bldgW, bldgD, "building", `bldg_${r + 1}_${c + 1}`));
            }
          }
          // one internal access drive spanning the grid footprint, if more than 1 building
          if (rows * cols > 1) {
            footprints.push(rect(originX, originY, totalW, totalD, "access_drive_envelope"));
          }
          const buildingFootprintSqft = rows * cols * bldgW * bldgD;
          const unitsPerBuilding = Math.max(1, Math.floor((bldgW * bldgD * stories) / sqftPerUnit));
          raw.push({
            layout_type: "multifamily_grid",
            footprints,
            unit_count: unitsPerBuilding * rows * cols,
            gross_floor_area_sqft: buildingFootprintSqft * stories,
            footprint_sqft: buildingFootprintSqft,
            stories,
          });
        }
      }
    }
  }
  return raw;
}

function rect(x, y, w, d, kind, label) {
  return {
    kind,
    label: label ?? kind,
    vertices: [
      [x, y],
      [x + w, y],
      [x + w, y + d],
      [x, y + d],
      [x, y],
    ],
  };
}

/**
 * Filters raw placements against zoning limits and scores survivors.
 * Returns the full filtered+scored list (caller ranks/truncates to top 5).
 */
function filterAndScore(raw, envelope, standards) {
  // max_density_du_acre governs subdividable/multi-unit layouts. It does NOT
  // apply to single_family: a single already-platted lot's density is
  // enforced by min_lot_sqft (checked once, upfront, in generateSiteMassing)
  // — re-applying a du/acre cap to a sub-acre single-family lot would reject
  // every candidate (floor(1.0 du/acre * 0.39 acre) = 0 units).
  const densityCap = densityCapUnits(envelope.parcelAreaSqft, standards);
  const maxCoveragePct = standards.max_lot_coverage_pct ?? 100;
  const targetCoveragePct = Math.min(maxCoveragePct, 60); // aim for a reasonable buildout, capped by the zone max

  const survivors = raw
    .map((c) => {
      const coveragePct = (c.footprint_sqft / envelope.parcelAreaSqft) * 100;
      const setbackCompliant = envelope.envelopeFullyInsideParcel !== false; // built entirely within the setback-inset envelope
      const withinCoverage = coveragePct <= maxCoveragePct;
      const withinDensity = c.layout_type === "single_family" || c.unit_count <= densityCap;
      return { ...c, coveragePct, setbackCompliant, withinCoverage, withinDensity };
    })
    .filter((c) => c.withinCoverage && c.withinDensity);

  if (survivors.length === 0) return [];

  const maxUnits = Math.max(...survivors.map((c) => c.unit_count));
  const maxGfa = Math.max(...survivors.map((c) => c.gross_floor_area_sqft));

  return survivors.map((c) => {
    const unitNorm = maxUnits > 0 ? c.unit_count / maxUnits : 0;
    const gfaNorm = maxGfa > 0 ? c.gross_floor_area_sqft / maxGfa : 0;
    const coverageFit = 1 - Math.min(1, Math.abs(c.coveragePct - targetCoveragePct) / 100);
    const hasAccessDrive = c.footprints.some((f) => f.kind.startsWith("access_drive"));
    const accessQuality = c.layout_type === "single_family" ? 1 : hasAccessDrive ? 1 : 0.5;

    const score = 0.4 * unitNorm + 0.3 * gfaNorm + 0.2 * coverageFit + 0.1 * accessQuality;
    return { ...c, score };
  });
}

/**
 * Top-level entry point.
 * @param {Array<[number,number]>} ringFt - closed parcel boundary ring, feet
 * @param {object} standards - zone_standards row for the parcel's zoning district
 * @param {"single_family"|"townhome_row"|"multifamily_grid"} layoutType
 * @param {object} [opts] - stories, unitWidthFt, unitDepthFt, sqftPerUnit (layout-specific overrides)
 * @returns {{ envelope: object, options: Array }} top 5 ranked options, option_rank 1-5
 */
export function generateSiteMassing(ringFt, standards, layoutType, opts = {}) {
  const envelope = computeBuildableEnvelope(ringFt, standards);

  if (typeof standards.min_lot_sqft === "number" && envelope.parcelAreaSqft < standards.min_lot_sqft) {
    return {
      envelope,
      options: [],
      skipped_reason: `Parcel area ${Math.round(envelope.parcelAreaSqft)} sqft is below the zone's min_lot_sqft (${standards.min_lot_sqft}) — no compliant layout is possible.`,
    };
  }

  let raw;
  if (layoutType === "single_family") raw = generateSingleFamilyCandidates(envelope, standards, opts);
  else if (layoutType === "townhome_row") raw = generateTownhomeCandidates(envelope, standards, opts);
  else if (layoutType === "multifamily_grid") raw = generateMultifamilyCandidates(envelope, standards, opts);
  else throw new Error(`generateSiteMassing: unknown layout_type "${layoutType}"`);

  const scored = filterAndScore(raw, envelope, standards);
  scored.sort((a, b) => b.score - a.score);

  const top5 = scored.slice(0, 5).map((c, i) => ({
    option_rank: i + 1,
    layout_type: c.layout_type,
    footprints: c.footprints,
    unit_count: c.unit_count,
    gross_floor_area_sqft: Math.round(c.gross_floor_area_sqft * 10) / 10,
    lot_coverage_pct: Math.round(c.coveragePct * 100) / 100,
    setback_compliant: c.setbackCompliant,
    score: Math.round(c.score * 10000) / 10000,
  }));

  return { envelope, options: top5, raw_candidate_count: raw.length, filtered_candidate_count: scored.length };
}

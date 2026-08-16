/**
 * ZoneWise Site Massing DXF exporter.
 * ---------------------------------------------------------------------------
 * Pure function, sibling to zoning.js/site-massing.js — no fs/child_process,
 * safe in the Workers isolate (dxf-writer is zero-dependency string
 * generation, see workers/zonewise-floorplan test run 2026-08-16).
 *
 * NOTE on the original spec text ("extend the existing ArchLang DXF compile
 * path"): checked live 2026-08-16 — no DXF path exists anywhere in this
 * Worker or in @chanmeng666/archlang. ArchLang only produces SVG (reliable)
 * and PDF (confirmed broken in Workers, see worker.js's handleCompilePdf
 * comment). This module is a NEW DXF path built directly on `dxf-writer`,
 * not an extension of anything pre-existing.
 *
 * All coordinates in and out of this module are feet, State Plane (NAD83,
 * ftUS) — the same frame site-massing.js already computed the envelope and
 * footprints in (see geo.js). No second reprojection happens here.
 *
 * Six standard layers, per the spec:
 *   PARCEL-BNDY     parcel boundary, continuous
 *   SETBACK-LINES   buildable envelope, dashed
 *   BLDG-FOOTPRINT  selected footprint(s), continuous
 *   ACCESS-DRIVE    driveway/internal access, continuous
 *   DIMENSIONS      dimension annotations
 *   TEXT-ANNO       unit count / GFA / coverage% / north arrow
 *
 * DIMENSIONS honesty note: dxf-writer has no DIMENSION entity type (checked
 * its prototype directly — draw{Line,Polyline,Text,Circle,Arc,...} only).
 * "Dimension annotations" here are manually composed extension lines +
 * text, not a true parametric DXF DIMENSION block. A civil engineer opening
 * this file will see readable dimension callouts, not associative
 * dimensions — documented, not silently overclaimed.
 */

import Drawing from "dxf-writer";

const LAYERS = {
  PARCEL_BNDY: "PARCEL-BNDY",
  SETBACK_LINES: "SETBACK-LINES",
  BLDG_FOOTPRINT: "BLDG-FOOTPRINT",
  ACCESS_DRIVE: "ACCESS-DRIVE",
  DIMENSIONS: "DIMENSIONS",
  TEXT_ANNO: "TEXT-ANNO",
};

function closeRing(ring) {
  const [x0, y0] = ring[0];
  const [xn, yn] = ring[ring.length - 1];
  if (x0 === xn && y0 === yn) return ring;
  return [...ring, [x0, y0]];
}

function drawDimensionLine(d, [x1, y1], [x2, y2], label, offsetFt = 8) {
  // Simple linear dimension: extension lines out from each endpoint, a
  // dimension line between them, and a text label at the midpoint. Not a
  // DXF DIMENSION entity — see module doc.
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const nx = (-dy / len) * offsetFt;
  const ny = (dx / len) * offsetFt;

  d.drawLine(x1, y1, x1 + nx, y1 + ny);
  d.drawLine(x2, y2, x2 + nx, y2 + ny);
  d.drawLine(x1 + nx, y1 + ny, x2 + nx, y2 + ny);
  const midX = (x1 + x2) / 2 + nx;
  const midY = (y1 + y2) / 2 + ny;
  d.drawText(midX, midY, 3, 0, label, "center", "middle");
}

/**
 * @param {object} params
 * @param {Array<[number,number]>} params.parcelRingFt - closed parcel boundary, feet
 * @param {Array<[number,number]>} params.envelopeRingFt - closed buildable-envelope ring, feet (from computeBuildableEnvelope(...).ring)
 * @param {object} params.option - one site_massing_options row (footprints, unit_count, gross_floor_area_sqft, lot_coverage_pct, layout_type, option_rank)
 * @param {object} params.meta - { parcelId, epsg, coNo }
 * @returns {string} DXF file contents (R12 ASCII, via dxf-writer's toDxfString)
 */
export function exportSiteMassingDXF({ parcelRingFt, envelopeRingFt, option, meta }) {
  if (!Array.isArray(parcelRingFt) || parcelRingFt.length < 4) {
    throw new Error("exportSiteMassingDXF: parcelRingFt must be a closed ring with >= 4 points");
  }
  if (!Array.isArray(envelopeRingFt) || envelopeRingFt.length < 4) {
    throw new Error("exportSiteMassingDXF: envelopeRingFt must be a closed ring with >= 4 points");
  }
  if (!option || !Array.isArray(option.footprints)) {
    throw new Error("exportSiteMassingDXF: option.footprints is required");
  }

  const d = new Drawing();
  d.setUnits("Feet");

  d.addLayer(LAYERS.PARCEL_BNDY, Drawing.ACI.WHITE, "CONTINUOUS");
  d.addLayer(LAYERS.SETBACK_LINES, Drawing.ACI.YELLOW, "DASHED");
  d.addLayer(LAYERS.BLDG_FOOTPRINT, Drawing.ACI.CYAN, "CONTINUOUS");
  d.addLayer(LAYERS.ACCESS_DRIVE, Drawing.ACI.MAGENTA, "CONTINUOUS");
  d.addLayer(LAYERS.DIMENSIONS, Drawing.ACI.GREEN, "CONTINUOUS");
  d.addLayer(LAYERS.TEXT_ANNO, Drawing.ACI.WHITE, "CONTINUOUS");

  d.setActiveLayer(LAYERS.PARCEL_BNDY);
  d.drawPolyline(closeRing(parcelRingFt));

  d.setActiveLayer(LAYERS.SETBACK_LINES);
  d.drawPolyline(closeRing(envelopeRingFt));

  d.setActiveLayer(LAYERS.BLDG_FOOTPRINT);
  for (const fp of option.footprints) {
    if (fp.kind === "building") d.drawPolyline(closeRing(fp.vertices));
  }

  d.setActiveLayer(LAYERS.ACCESS_DRIVE);
  for (const fp of option.footprints) {
    if (fp.kind.startsWith("access_drive")) d.drawPolyline(closeRing(fp.vertices));
  }

  // --- DIMENSIONS: overall parcel bbox width/depth -------------------------
  d.setActiveLayer(LAYERS.DIMENSIONS);
  const xs = parcelRingFt.map((p) => p[0]);
  const ys = parcelRingFt.map((p) => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  drawDimensionLine(d, [minX, minY], [maxX, minY], `${(maxX - minX).toFixed(1)}'`, -12);
  drawDimensionLine(d, [minX, minY], [minX, maxY], `${(maxY - minY).toFixed(1)}'`, -12);
  // First building footprint's own width/depth, if present.
  const firstBuilding = option.footprints.find((fp) => fp.kind === "building");
  if (firstBuilding) {
    const bx = firstBuilding.vertices.map((p) => p[0]);
    const by = firstBuilding.vertices.map((p) => p[1]);
    const bw = Math.max(...bx) - Math.min(...bx);
    const bd = Math.max(...by) - Math.min(...by);
    drawDimensionLine(
      d,
      [Math.min(...bx), Math.min(...by)],
      [Math.max(...bx), Math.min(...by)],
      `${bw.toFixed(1)}'`,
      6
    );
    drawDimensionLine(
      d,
      [Math.min(...bx), Math.min(...by)],
      [Math.min(...bx), Math.max(...by)],
      `${bd.toFixed(1)}'`,
      -6
    );
  }

  // --- TEXT-ANNO: metrics + north arrow -------------------------------------
  d.setActiveLayer(LAYERS.TEXT_ANNO);
  const textX = minX;
  let textY = maxY + 20;
  const lines = [
    `PARCEL ${meta.parcelId ?? ""} (co_no ${meta.coNo ?? "?"})`,
    `LAYOUT: ${option.layout_type} — OPTION ${option.option_rank ?? "?"}`,
    `UNITS: ${option.unit_count}`,
    `GFA: ${Math.round(option.gross_floor_area_sqft)} SF`,
    `LOT COVERAGE: ${option.lot_coverage_pct}%`,
    `SETBACK COMPLIANT: ${option.setback_compliant ? "YES" : "NO"}`,
    `CRS: ${meta.epsg ?? "?"} (State Plane, US survey feet)`,
  ];
  for (const line of lines) {
    d.drawText(textX, textY, 4, 0, line, "left", "baseline");
    textY += 6;
  }
  // North arrow: a simple line + arrowhead + "N" label, offset to the right of the text block.
  const arrowX = maxX + 20;
  const arrowBaseY = maxY;
  const arrowTipY = arrowBaseY + 20;
  d.drawLine(arrowX, arrowBaseY, arrowX, arrowTipY);
  d.drawLine(arrowX, arrowTipY, arrowX - 3, arrowTipY - 6);
  d.drawLine(arrowX, arrowTipY, arrowX + 3, arrowTipY - 6);
  d.drawText(arrowX, arrowTipY + 3, 4, 0, "N", "center", "baseline");

  return d.toDxfString();
}

export { LAYERS as SITE_DXF_LAYERS };

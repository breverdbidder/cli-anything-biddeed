/**
 * ZoneWise zoning-constraint checker.
 * ---------------------------------------------------------------------------
 * Pure function, zero dependencies — takes ArchLang's `describe()` summary
 * (building geometry) and a parcel's buildable-envelope constraints (from
 * ZoneWise's own GIS/zoning pipeline) and checks the compiled plan against
 * that SPECIFIC parcel's legal limits.
 *
 * SCOPE / HONEST LIMITATIONS (v1):
 *   - ArchLang plans are a building's own floor geometry — they carry no
 *     site placement (where the building sits on the lot, or its rotation).
 *     So "does it fit" here means "are the building's overall footprint
 *     dimensions smaller than the buildable envelope's dimensions" — a
 *     necessary check, not a sufficient one. It does NOT confirm the
 *     building is actually sited within the envelope on a real site plan.
 *     Two orientations (as-drawn, and rotated 90°) are both checked since
 *     ArchLang has no fixed site orientation either.
 *   - Lot coverage uses the building's footprint (bbox_outer, outside face
 *     to outside face) as a proxy for ground-floor footprint. For a
 *     multi-storey `.arch` plan, pass the LEVEL 1 (ground floor) summary —
 *     upper floors don't add lot coverage. This module doesn't know which
 *     level it was given; that's the caller's responsibility.
 *   - Height is not checked — ArchLang plans are 2D floor plans; they carry
 *     no building height / story count as structured data.
 *   - Setback compliance in the strict sense (walls sitting outside a
 *     setback line on an actual site plan) is NOT checked. This is an
 *     envelope-fit check, not a site-plan check. Flagged clearly in output
 *     as `dimensional_fit`, not `setback_compliance`, to avoid overclaiming.
 */

const MM_PER_FT = 304.8;
const SQFT_PER_M2 = 10.7639;

function mmToFt(mm) {
  return mm / MM_PER_FT;
}

/**
 * @param {object} summary - result of ArchLang's describe(source) — needs
 *   at minimum { bbox_outer: {w,h}, rooms: [{uses: string[], area_m2}] }
 * @param {object} parcel - buildable-envelope constraints, feet/sqft (US
 *   convention, matches how FL zoning codes state setbacks/lot size):
 *   {
 *     lot_width_ft: number,
 *     lot_depth_ft: number,
 *     lot_area_sqft?: number,          // else computed as width * depth
 *     setbacks_ft: { front, rear, side },
 *     max_lot_coverage_pct?: number,   // 0-100
 *     septic_bedroom_cap?: number,     // omit if on central sewer
 *     utility_tier?: string            // pass-through for the report, e.g. "central" | "septic" | "UNDETERMINED"
 *   }
 * @returns {object} compliance report — never throws; a missing/invalid
 *   parcel field produces a `checks[].status: "skipped"` entry with a
 *   reason, not a crash.
 */
export function checkZoningCompliance(summary, parcel) {
  const checks = [];
  const problems = [];

  if (!summary || !summary.bbox_outer) {
    return {
      ok: false,
      error: "Summary missing bbox_outer — pass the result of describe(source), not compile()'s result.",
      checks: [],
    };
  }
  if (!parcel || typeof parcel !== "object") {
    return { ok: false, error: "Missing parcel constraints object.", checks: [] };
  }

  const buildingWFt = mmToFt(summary.bbox_outer.w);
  const buildingHFt = mmToFt(summary.bbox_outer.h);

  // --- Dimensional fit within the buildable envelope -----------------------
  if (
    typeof parcel.lot_width_ft === "number" &&
    typeof parcel.lot_depth_ft === "number" &&
    parcel.setbacks_ft
  ) {
    const { front = 0, rear = 0, side = 0 } = parcel.setbacks_ft;
    const buildableWidthFt = parcel.lot_width_ft - 2 * side;
    const buildableDepthFt = parcel.lot_depth_ft - front - rear;

    const fitsAsDrawn = buildingWFt <= buildableWidthFt && buildingHFt <= buildableDepthFt;
    const fitsRotated = buildingHFt <= buildableWidthFt && buildingWFt <= buildableDepthFt;
    const fits = fitsAsDrawn || fitsRotated;

    checks.push({
      rule: "dimensional_fit",
      status: fits ? "pass" : "fail",
      detail: {
        building_footprint_ft: { w: round1(buildingWFt), h: round1(buildingHFt) },
        buildable_envelope_ft: { w: round1(buildableWidthFt), h: round1(buildableDepthFt) },
        fits_as_drawn: fitsAsDrawn,
        fits_rotated_90: fitsRotated,
      },
      note: "Checks whether the building's footprint dimensions are smaller than the buildable envelope. Does NOT confirm actual site placement — no site plan / building position on the lot is modeled here.",
    });
    if (!fits) {
      problems.push(
        `Building footprint (${round1(buildingWFt)}' x ${round1(buildingHFt)}') exceeds the buildable envelope (${round1(buildableWidthFt)}' x ${round1(buildableDepthFt)}') in both orientations.`
      );
    }
  } else {
    checks.push({
      rule: "dimensional_fit",
      status: "skipped",
      reason: "parcel.lot_width_ft, lot_depth_ft, or setbacks_ft missing.",
    });
  }

  // --- Lot coverage ----------------------------------------------------------
  if (typeof parcel.max_lot_coverage_pct === "number") {
    const lotAreaSqft =
      typeof parcel.lot_area_sqft === "number"
        ? parcel.lot_area_sqft
        : typeof parcel.lot_width_ft === "number" && typeof parcel.lot_depth_ft === "number"
        ? parcel.lot_width_ft * parcel.lot_depth_ft
        : null;

    if (lotAreaSqft) {
      const footprintSqft = buildingWFt * buildingHFt;
      const coveragePct = (footprintSqft / lotAreaSqft) * 100;
      const coverageOk = coveragePct <= parcel.max_lot_coverage_pct;

      checks.push({
        rule: "lot_coverage",
        status: coverageOk ? "pass" : "fail",
        detail: {
          building_footprint_sqft: round1(footprintSqft),
          lot_area_sqft: round1(lotAreaSqft),
          coverage_pct: round1(coveragePct),
          max_allowed_pct: parcel.max_lot_coverage_pct,
        },
        note: "Footprint is bbox_outer of the plan passed in — for a multi-storey building, pass the ground-floor level's summary only; upper floors don't add lot coverage.",
      });
      if (!coverageOk) {
        problems.push(
          `Lot coverage ${round1(coveragePct)}% exceeds the ${parcel.max_lot_coverage_pct}% max.`
        );
      }
    } else {
      checks.push({
        rule: "lot_coverage",
        status: "skipped",
        reason: "Could not determine lot area (need lot_area_sqft, or both lot_width_ft and lot_depth_ft).",
      });
    }
  } else {
    checks.push({ rule: "lot_coverage", status: "skipped", reason: "parcel.max_lot_coverage_pct not provided." });
  }

  // --- Septic bedroom cap -----------------------------------------------------
  if (typeof parcel.septic_bedroom_cap === "number") {
    const bedroomCount = (summary.rooms || []).filter(
      (r) => Array.isArray(r.uses) && r.uses.includes("bedroom")
    ).length;
    const septicOk = bedroomCount <= parcel.septic_bedroom_cap;

    checks.push({
      rule: "septic_bedroom_cap",
      status: septicOk ? "pass" : "fail",
      detail: {
        bedroom_count: bedroomCount,
        cap: parcel.septic_bedroom_cap,
        utility_tier: parcel.utility_tier || "UNDETERMINED",
      },
      note: "Counts every room whose `uses` includes \"bedroom\" across the whole plan. For a multi-unit building this is a PLAN-WIDE total, not per-unit — if the cap is per-unit, the caller must compile/check each unit separately.",
    });
    if (!septicOk) {
      problems.push(
        `${bedroomCount} bedrooms exceeds the septic system's ${parcel.septic_bedroom_cap}-bedroom cap.`
      );
    }
  } else {
    checks.push({
      rule: "septic_bedroom_cap",
      status: "skipped",
      reason: "parcel.septic_bedroom_cap not provided (central sewer, or unknown utility tier).",
    });
  }

  const failedChecks = checks.filter((c) => c.status === "fail");
  const ok = failedChecks.length === 0;

  return {
    ok,
    checks,
    problems, // human-readable, one line per failure — empty array if ok
  };
}

function round1(n) {
  return Math.round(n * 10) / 10;
}

// GTM-22 S5 REPORT ENGINE — SECTION ZW (ZoneWise.AI Land & Zoning
// Intelligence), per issue #12853 Amendment 1. Orange band, "NO HC
// EQUIVALENT — THE PAIRING". Reads fl_parcels + zoning_assignments
// (READ-ONLY) — never writes, never infers a district that isn't assigned.
import { get as defaultGet } from '../supabase.js';

const DOR_UC_LABELS = {
  '000': 'Vacant residential',
  '001': 'Single family',
  '002': 'Mobile home',
  '004': 'Condominium',
  '010': 'Vacant commercial',
};

// match: the caller's already-resolved matchStateParcel() result (composer.js
// resolves it once for both the CMA/model path and this section) — perf fix
// for the /report/json timeout: this module used to call matchStateParcel a
// second time itself, doubling that lookup's cost on every report.
export async function buildZwSection(auction, match, { get = defaultGet } = {}) {
  if (!auction.property_address) {
    return {
      section_key: 'zoning',
      band: 'orange',
      label: 'NO HC EQUIVALENT — THE PAIRING',
      matched: false,
      verdict: 'ZoneWise cannot analyze an unlocatable subject; the pairing declines together.',
    };
  }

  if (!match.matched) {
    return {
      section_key: 'zoning',
      band: 'orange',
      label: 'NO HC EQUIVALENT — THE PAIRING',
      matched: false,
      reason: match.reason,
      verdict: 'ZoneWise cannot resolve a state parcel match for this subject; land/zoning intelligence unavailable — decision must proceed on auction data alone.',
    };
  }

  const parcel = match.parcel;
  const landSqft = parcel.lnd_sqfoot || 0;
  const landPsf = landSqft > 0 ? parcel.lnd_val / landSqft : null;
  const landShareOfJv = parcel.jv > 0 ? parcel.lnd_val / parcel.jv : null;

  const assignmentRows = await get(
    `zoning_assignments?parcel_id=eq.${encodeURIComponent(parcel.parcel_id)}&select=zone_code,jurisdiction&limit=1`
  ).catch(() => []);
  const assignment = assignmentRows[0] || null;

  return {
    section_key: 'zoning',
    band: 'orange',
    label: 'NO HC EQUIVALENT — THE PAIRING',
    matched: true,
    state_parcel_id: parcel.parcel_id,
    co_no: match.co_no,
    jurisdiction: parcel.municipality || 'Unincorporated',
    dor_use_code: parcel.dor_uc,
    dor_use_meaning: DOR_UC_LABELS[parcel.dor_uc] || 'Unclassified',
    dor_just_value: parcel.jv,
    land_value: parcel.lnd_val,
    land_sqft: landSqft,
    land_psf: landPsf ? Number(landPsf.toFixed(2)) : null,
    land_share_of_jv: landShareOfJv ? Number(landShareOfJv.toFixed(3)) : null,
    zoning_district: assignment ? assignment.zone_code : 'PENDING',
    zoning_coverage_note: assignment ? null : `No zoning_assignments row exists for this parcel — coverage for ${auction.county} is not yet extracted. District rendered PENDING, never inferred.`,
    conforming_use_read: assignment
      ? `Presumptively conforming under ${assignment.zone_code}, subject to district confirmation.`
      : 'Presumptively conforming per DOR use code only — district not yet assigned, confirm before relying on this.',
    dor_jv_vs_assessed_divergence: (auction.assessed_value && parcel.jv && parcel.jv !== auction.assessed_value)
      ? { dor_jv: parcel.jv, pa_assessed: auction.assessed_value, delta: parcel.jv - auction.assessed_value }
      : null,
    verdict: `Land value $${parcel.lnd_val?.toLocaleString()} on ${landSqft.toLocaleString()} sqft ($${landPsf ? landPsf.toFixed(2) : '—'}/sqft)${landShareOfJv ? `, ${Math.round(landShareOfJv * 100)}% of DOR just value` : ''}.`,
  };
}

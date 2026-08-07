// GTM-22 S5 REPORT ENGINE — red/amber flag derivation.
//
// HEURISTIC, not ground-truth: no source document (title search, occupancy
// inspection, condition report) is wired into this pipeline today. Flags
// derived from columns that exist are marked "risk" (red); everything this
// system cannot verify from the DB alone is marked "pending" (amber) rather
// than silently omitted or guessed — per the brief's honesty rule that
// unenrichable fields render "Pending <reason>", never estimated silently.
const ESTATE_RE  = /\b(ESTATE OF|HEIRS OF|DECEASED|SURVIVING)\b/i;

// Junior / HOA lien patterns — CC case numbers + plaintiff name keywords.
// CC (County Court) = junior/HOA lien; CA (Circuit Court) = primary mortgage.
// When both conditions match AND lien_survival is Pending, a BID verdict is
// suppressed to REVIEW — the first mortgage may survive and wipe investor equity.
// Worst observed: Lee 25-CC-002922, $33,135 opening vs $972,909 assessed (3.4%).
const JUNIOR_CASE_RE      = /\bCC\b/;
const JUNIOR_PLAINTIFF_RE = /\b(ASSOCIATION|CONDOMINIUM|HOA|MASTER|VILLAS|HOMEOWNERS)\b/i;

export function deriveRedFlags(auction) {
  const flags = [];

  if (/MOBILE|MH/i.test(auction.property_type || '')) {
    flags.push({ code: 'MH_TITLE', severity: 'risk', text: 'Mobile home — title may be titled as personal property (HSMV) rather than real property; confirm real-property conversion (FL FS 320.0815) before bidding.' });
    if (auction.year_built && auction.year_built < 1990) {
      flags.push({ code: 'PRE_1990_MH', severity: 'risk', text: `Mobile home built ${auction.year_built} — pre-1990 HUD code units carry elevated financing/insurability risk.` });
    }
  }

  if (ESTATE_RE.test(auction.owner_name || '')) {
    flags.push({ code: 'HEIRS_OCCUPANCY', severity: 'risk', text: 'Owner-of-record name pattern suggests an estate/heirs situation — occupancy and clear-title risk elevated.' });
  } else {
    flags.push({ code: 'OCCUPANCY', severity: 'pending', text: 'Pending — no occupancy inspection data available for this property.' });
  }

  flags.push({ code: 'CONDITION', severity: 'pending', text: 'Pending — no condition/inspection report available; assume as-is, unseen-interior risk.' });
  flags.push({ code: 'FEDERAL_LIENS', severity: 'pending', text: 'Pending — federal tax lien search not run for this parcel (survives foreclosure if IRS not properly joined, FL FS 45).' });

  if (auction.homestead_status === 'homestead') {
    flags.push({ code: 'HOMESTEAD_OCCUPIED', severity: 'risk', text: 'Homestead-exempt — likely owner-occupied; eviction/possession risk after sale.' });
  }

  if (auction.judgment_amount > 0 && auction.assessed_value > 0) {
    const ratio = auction.judgment_amount / auction.assessed_value;
    if (ratio > 1.5) {
      flags.push({ code: 'JUDGMENT_INVERSION', severity: 'risk', text: `Judgment ($${auction.judgment_amount.toLocaleString()}) is ${Math.round(ratio * 100)}% of assessed value — inverted judgment-to-value, expect thin or negative bid margin.` });
    }
  }

  if (auction.plaintiff_max_bid == null) {
    flags.push({ code: 'HIDDEN_CAP', severity: 'pending', text: 'Hidden — plaintiff max bid not disclosed on the docket/render as of report time.' });
  }

  // Junior / HOA lien detection — CC case number pattern + plaintiff name
  const caseNo   = auction.case_number || '';
  const plaintiff = auction.plaintiff   || '';
  if (JUNIOR_CASE_RE.test(caseNo) || JUNIOR_PLAINTIFF_RE.test(plaintiff)) {
    flags.push({
      code:     'JUNIOR_LIEN_RISK',
      severity: 'risk',
      text:     `Case number pattern (${caseNo}) or plaintiff name (${plaintiff || 'unknown'}) suggests a junior / HOA lien rather than a primary mortgage. The first mortgage likely SURVIVES this foreclosure — verify lien priority before bidding. BID verdict suppressed to REVIEW until lien survival confirmed.`,
    });
  }

  return flags;
}

// Export the detection function so composer.js can gate the verdict
export function hasJuniorLienRisk(flags) {
  return flags.some(f => f.code === 'JUNIOR_LIEN_RISK');
}

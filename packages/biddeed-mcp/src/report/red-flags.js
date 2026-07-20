// GTM-22 S5 REPORT ENGINE — red/amber flag derivation.
//
// HEURISTIC, not ground-truth: no source document (title search, occupancy
// inspection, condition report) is wired into this pipeline today. Flags
// derived from columns that exist are marked "risk" (red); everything this
// system cannot verify from the DB alone is marked "pending" (amber) rather
// than silently omitted or guessed — per the brief's honesty rule that
// unenrichable fields render "Pending <reason>", never estimated silently.
const ESTATE_RE = /\b(ESTATE OF|HEIRS OF|DECEASED|SURVIVING)\b/i;

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

  return flags;
}

// GTM-22 S5 REPORT ENGINE — red/amber flag derivation.
//
// ONE ENGINE, TWO PATHS:
//   deriveRedFlags(auction) — branches internally on sale_type
//   Foreclosure flags: MH_TITLE, HEIRS_OCCUPANCY, HOMESTEAD_OCCUPIED,
//                      JUDGMENT_INVERSION, HIDDEN_CAP, JUNIOR_LIEN_RISK
//   Tax Deed flags:    MH_TITLE, HEIRS_OCCUPANCY, HOMESTEAD_OCCUPIED,
//                      IRS_LIEN_SURVIVAL, HOA_LIEN_SURVIVAL, TITLE_INSURANCE_RISK
//
// HEURISTIC, not ground-truth — flags derived from available DB columns only.
// Missing data renders "pending" (amber), never estimated silently.

const ESTATE_RE         = /\b(ESTATE OF|HEIRS OF|DECEASED|SURVIVING)\b/i;
const JUNIOR_CASE_RE    = /\bCC\b/;
const JUNIOR_PLAINTIFF_RE = /\b(ASSOCIATION|CONDOMINIUM|HOA|MASTER|VILLAS|HOMEOWNERS)\b/i;
// A first-mortgage final judgment is essentially never this small a share of
// assessed value. A judgment below this ratio is junior/HOA scale. Exported
// because the composer's judgment-ratio clearing anchor keys off the same
// constant — the two checks must never drift apart.
export const JUNIOR_JUDGMENT_TO_ASSESSED = 0.15;
// Bank-name guard: "US BANK TRUST NATIONAL ASSOCIATION", "FEDERAL NATIONAL
// MORTGAGE ASSOCIATION" et al. contain ASSOCIATION but are first-mortgage
// plaintiffs. Without this guard every spelled-out national-association bank
// was falsely flagged junior (caught live on the Marion reference card).
const BANKLIKE_PLAINTIFF_RE = /\b(NATIONAL ASSOCIATION|BANK|MORTGAGE|CREDIT UNION|SAVINGS)\b/i;

// ── Shared flags (both sale types) ─────────────────────────────────────────
function sharedFlags(auction) {
  const flags = [];

  if (/MOBILE|MH/i.test(auction.property_type || '')) {
    flags.push({ code: 'MH_TITLE', severity: 'risk',
      text: 'Mobile home — title may be personal property (HSMV) rather than real property; confirm real-property conversion (FL FS 320.0815) before bidding.' });
    if (auction.year_built && auction.year_built < 1990)
      flags.push({ code: 'PRE_1990_MH', severity: 'risk',
        text: `Mobile home built ${auction.year_built} — pre-1990 HUD code units carry elevated financing/insurability risk.` });
  }

  if (ESTATE_RE.test(auction.owner_name || '')) {
    flags.push({ code: 'HEIRS_OCCUPANCY', severity: 'risk',
      text: 'Owner-of-record name suggests estate/heirs — occupancy and clear-title risk elevated.' });
  } else {
    flags.push({ code: 'OCCUPANCY', severity: 'pending',
      text: 'Pending — no occupancy inspection data available for this property.' });
  }

  flags.push({ code: 'CONDITION', severity: 'pending',
    text: 'Pending — no condition/inspection report available; assume as-is, unseen-interior risk.' });

  flags.push({ code: 'MECHANIC_LIEN_RISK', severity: 'pending',
    text: 'Pending — mechanic/construction lien search not run. Mechanic liens filed within 90 days of work completion may survive both foreclosure and tax deed sales regardless of sale date (FL FS 713.07 / 713.10). Visible signs of recent construction, renovation, or unpermitted work elevate this risk. Order a mechanic lien search independently before closing.' });

  if (auction.homestead_status === 'homestead')
    flags.push({ code: 'HOMESTEAD_OCCUPIED', severity: 'risk',
      text: 'Homestead-exempt — likely owner-occupied; eviction/possession risk after sale.' });

  return flags;
}

// ── Foreclosure-specific flags ──────────────────────────────────────────────
function foreclosureFlags(auction) {
  const flags = [];

  flags.push({ code: 'FEDERAL_LIENS', severity: 'pending',
    text: 'Pending — federal tax lien search not run (survives foreclosure if IRS not properly joined, FL FS 45).' });

  if (auction.judgment_amount > 0 && auction.assessed_value > 0) {
    const ratio = auction.judgment_amount / auction.assessed_value;
    if (ratio > 1.5)
      flags.push({ code: 'JUDGMENT_INVERSION', severity: 'risk',
        text: `Judgment ($${auction.judgment_amount.toLocaleString()}) is ${Math.round(ratio * 100)}% of assessed value — inverted judgment-to-value, expect thin or negative bid margin.` });
  }

  if (auction.plaintiff_max_bid == null)
    flags.push({ code: 'HIDDEN_CAP', severity: 'pending',
      text: 'Hidden — plaintiff max bid not disclosed on the docket/render as of report time.' });

  // Junior / HOA lien — CC case number OR HOA plaintiff pattern OR a judgment
  // too small to be a first-mortgage FJ. The third trigger exists because of
  // Palm Beach 502025CA005319XXXAMB: a $17,403.61 judgment on a $457,184
  // assessed house (3.8%) — an HOA-style foreclosure filed under a CA case
  // number with no plaintiff on file, invisible to the two pattern checks.
  const caseNo    = auction.case_number || '';
  const plaintiff = auction.plaintiff   || '';
  const jRatio    = (auction.judgment_amount > 0 && auction.assessed_value > 0)
    ? auction.judgment_amount / auction.assessed_value : null;
  const tinyJudgment = jRatio != null && jRatio < JUNIOR_JUDGMENT_TO_ASSESSED;
  const plaintiffJunior = JUNIOR_PLAINTIFF_RE.test(plaintiff) && !BANKLIKE_PLAINTIFF_RE.test(plaintiff);
  if (tinyJudgment && !JUNIOR_CASE_RE.test(caseNo) && !plaintiffJunior)
    flags.push({ code: 'JUNIOR_LIEN_RISK', severity: 'risk',
      text: `Judgment ($${auction.judgment_amount.toLocaleString()}) is only ${Math.round(jRatio * 100)}% of assessed value ($${auction.assessed_value.toLocaleString()}) — inconsistent with a first-mortgage foreclosure. This is junior/HOA-lien scale: the first mortgage likely SURVIVES the sale, and the clearing price will track equity above the surviving debt, not property value. BID suppressed to REVIEW until lien priority is confirmed.` });
  else if (JUNIOR_CASE_RE.test(caseNo) || plaintiffJunior)
    flags.push({ code: 'JUNIOR_LIEN_RISK', severity: 'risk',
      text: `Case number (${caseNo}) or plaintiff (${plaintiff || 'unknown'}) suggests a junior/HOA lien rather than a primary mortgage. The first mortgage likely SURVIVES — verify lien priority before bidding. BID suppressed to REVIEW until lien survival confirmed.` });

  return flags;
}

// ── Tax Deed-specific flags ─────────────────────────────────────────────────
function taxDeedFlags(auction) {
  const flags = [];

  // IRS lien survival — hard risk, federal law supersedes FL FS 197.502
  flags.push({ code: 'IRS_LIEN_SURVIVAL', severity: 'risk',
    text: 'IRS federal tax liens survive Florida tax deed sales (26 U.S.C. § 7425; Rev. Rul. 2005-38) unless the IRS was given proper notice and failed to redeem within 120 days. Always order an IRS lien search before bidding. This is not extinguished by the tax deed.' });

  // HOA lien survival — FL FS 720/718 — partial survival
  flags.push({ code: 'HOA_LIEN_SURVIVAL', severity: 'risk',
    text: 'HOA/COA liens may survive or re-attach after a Florida tax deed sale (FL FS 720.3085 / 718.116). The association may claim up to 12 months of past-due assessments plus fees regardless of the tax deed. Confirm HOA status and any outstanding balance before bidding.' });

  // Title insurance risk — underwriters are reluctant on fresh tax deed titles
  flags.push({ code: 'TITLE_INSURANCE_RISK', severity: 'risk',
    text: 'Title insurance on tax deed properties is harder to obtain and more expensive than on market sales. Many underwriters require a quiet title action (typically 3-6 months, ~$1,500-3,000) before issuing a policy. Budget for this or plan for a cash-only/hard-money hold.' });

  // Federal liens general (IRS already called out above; catch other federal liens)
  flags.push({ code: 'FEDERAL_LIENS', severity: 'pending',
    text: 'Pending — full federal lien search not run. Tax deed extinguishes most state liens (FL FS 197.552) but NOT federal liens (IRS, SBA, USDA). Order a federal lien search independently.' });

  return flags;
}

// ── Main export ─────────────────────────────────────────────────────────────
export function deriveRedFlags(auction) {
  const isTaxDeed = (auction.sale_type || '').toLowerCase() === 'tax_deed';
  return [
    ...sharedFlags(auction),
    ...(isTaxDeed ? taxDeedFlags(auction) : foreclosureFlags(auction)),
  ];
}

export function hasJuniorLienRisk(flags) {
  return flags.some(f => f.code === 'JUNIOR_LIEN_RISK');
}

export function hasTaxDeedLienRisk(flags) {
  return flags.some(f => ['IRS_LIEN_SURVIVAL', 'HOA_LIEN_SURVIVAL'].includes(f.code));
}

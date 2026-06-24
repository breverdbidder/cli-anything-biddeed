// Revenue stream config and tier hierarchy
export const TIER_RANK = { free: 0, investor: 1, pro: 2, proplus: 3, enterprise: 4 };

// 7 revenue streams — S1 through S7
export const STREAM_GATE = {
  s1: 'free',
  s2: 'investor',
  s3: 'pro',
  s4: 'pro',
  s5: 'pro',
  s6: 'free',      // S6 Market Data — free tier (FRED/HUD public data)
  s7: 'investor',  // S7 Property Intel — investor tier
  fee: 'enterprise',
};

export const STREAM_PRICE = {
  s1: 0.05,
  s2: 0.40,
  s3: 5.00,
  s4: 0.00,
  s5: 25.00,
  s6: 0.05,   // S6 Market Data — $0.05/call
  s7: 0.25,   // S7 Property Intel — $0.25/call
  fee: 0.00,
};

// Maps every tool to its stream (7 streams total)
export const TOOL_STREAM = {
  // S1 Discovery — $0.05/call, free tier
  search_auctions:          's1',
  get_auction_detail:       's1',
  browse_deals:             's1',
  get_deposit_requirements: 's1',
  find_local_partners:      's1',
  // S2 Qualification — $0.40/call, investor tier
  search_distressed:        's2',
  get_owner_intel:          's2',
  get_lien_stack:           's2',
  get_rent_estimate:        's2',
  analyze_market:           's2',
  get_zip_market_data:      's2',
  // S3 Fusion — $5.00/call, pro tier
  check_zoning:             's3',
  underwrite_deal:          's3',
  analyze_coliving:         's3',
  get_sales_comps:          's3',
  generate_deal_memo:       's3',
  get_bid_package:          's3',
  get_title_chain:          's3',
  skip_trace:               's3',
  // S4 Monitoring — subscription, pro tier
  watch_auction:            's4',
  // S5 Shapira — $25/call, pro tier + CERT REQUIRED
  predict_auction_outcome:  's5',
  // S6 Market Data — $0.05/call, free tier (FRED/HUD public data)
  get_interest_rate:        's6',
  get_market_data:          's6',
  // S7 Property Intel — $0.25/call, investor tier
  search_properties:        's7',
  get_property_detail:      's7',
};

// FL county clerk URLs for deposit payment
export const CLERK_LINKS = {
  brevard:   'https://brevardclerk.us/tax-deed-sales',
  duval:     'https://www.duvalclerk.com/public-access/tax-deeds',
  orange:    'https://www.myorangeclerk.com/divisions/real-property/tax-deed',
  hillsborough: 'https://www.hillsclerk.com/real-property/tax-deed-sales',
  miami_dade: 'https://www.miami-dadeclerk.com/dadecoc/tax_deed.asp',
  palm_beach: 'https://mypalmbeachclerk.clerkofcourts.com/tax-deed-sales',
  pinellas:  'https://www.pinellasclerk.org/divisions/real-property/tax-deed-sales',
  lee:       'https://www.leeclerk.org/divisions/clerk-of-courts/tax-deed',
  collier:   'https://www.collierclerk.com/courts-judiciary/tax-deed',
  polk:      'https://www.polkcountyclerk.net/departments/property-records/tax-deed',
};

export function getClerkLink(county) {
  const key = county?.toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_');
  return CLERK_LINKS[key] || `https://www.${key}clerk.com`;
}

// FL lien survival rules by sale type
export const LIEN_RULES = {
  tax_deed: {
    statute: 'FL FS 197',
    survive: [
      'Federal tax liens (IRC § 6323 — IRS must be properly noticed)',
      'Federal government superior claims',
      'Utility assessment liens held by government entities',
      'Community Development District (CDD) assessments (some counties)',
    ],
    extinguished: [
      'Mortgage liens (all positions)',
      'HOA and COA liens',
      'Judgment liens',
      'Mechanic and materialmen liens',
      'Code enforcement liens',
      'Municipal and county special assessment liens (typically)',
      'Lis pendens',
      'Second mortgages and HELOCs',
    ],
    note: 'FL tax deed extinguishes most private liens. Title insurance recommended. Redemption period: 2 years from deed recording.',
  },
  foreclosure: {
    statute: 'FL FS 45',
    survive: [
      'Property tax liens and assessments (always superior)',
      'Senior mortgage liens (recorded before foreclosed mortgage)',
      'Federal tax liens if IRS not properly joined as party',
      'HOA super-lien — first 12 months unpaid assessments per FL FS 718/720',
      'CDD assessments',
    ],
    extinguished: [
      'Junior mortgage liens (recorded after foreclosed mortgage)',
      'Junior judgment liens',
      'Subordinate mechanic liens',
      'Lis pendens recorded after the foreclosed mortgage',
    ],
    note: 'Only liens junior to the foreclosed mortgage are extinguished. Always do O&E title search before bidding.',
  },
};

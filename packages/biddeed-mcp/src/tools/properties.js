// Property search + detail tools (S1/S2)
import { get } from '../supabase.js';

export const schemas = [
  {
    name: 'search_properties',
    description: 'Search FL properties by address, parcel, or county. Returns property records with zoning, auction history, and distress flags. BidDeed adds FL auction calendar + cert badge vs Investra.',
    inputSchema: {
      type: 'object',
      properties: {
        county:   { type: 'string', description: 'FL county name' },
        address:  { type: 'string', description: 'Street address or partial (e.g. "123 Main")' },
        parcel_id:{ type: 'string', description: 'FL parcel ID / folio / STRAP number' },
        zip_code: { type: 'string', description: 'Zip code filter' },
        limit:    { type: 'number', description: 'Results (default: 10)' },
      },
      required: ['county'],
    },
  },
  {
    name: 'get_property_detail',
    description: 'Detailed property record: folio/PIN, DOR use code, BCPAO assessment data, zoning code, auction history. Better than Investra: FL-specific folio + DOR code + BCPAO integration.',
    inputSchema: {
      type: 'object',
      properties: {
        parcel_id:   { type: 'string', description: 'FL parcel ID / folio number' },
        county:      { type: 'string', description: 'FL county' },
        address:     { type: 'string', description: 'Property address (alternative to parcel_id)' },
        case_number: { type: 'string', description: 'Auction case number (alternative)' },
      },
      required: ['county'],
    },
  },
];

export async function search_properties({ county, address, parcel_id, zip_code, limit = 10 }) {
  const filters = [`county=ilike.${encodeURIComponent(county.replace(/\s+/g, '%'))}`];
  if (address) filters.push(`property_address=ilike.${encodeURIComponent(`%${address}%`)}`);
  if (parcel_id) filters.push(`parcel_id=eq.${encodeURIComponent(parcel_id)}`);
  if (zip_code) filters.push(`zip=eq.${zip_code}`);

  const rows = await get(
    `multi_county_auctions?${filters.join('&')}&order=auction_date.desc&limit=${Math.min(limit, 50)}&select=case_number,county,property_address,parcel_id,opening_bid,auction_date,sale_type,judgment_amount`
  ).catch(() => []);

  // Also search zoning_assignments for broader property coverage
  const zoningRows = parcel_id
    ? await get(`zoning_assignments?parcel_id=eq.${encodeURIComponent(parcel_id)}&limit=1&select=parcel_id,zone_code,county`).catch(() => [])
    : [];

  return {
    county,
    search_terms: { address, parcel_id, zip_code },
    count: rows.length,
    properties: rows.map(r => ({
      parcel_id: r.parcel_id,
      address: r.property_address,
      county: r.county,
      auction_status: 'in_auction_pipeline',
      opening_bid: r.opening_bid,
      auction_date: r.auction_date,
      sale_type: r.sale_type,
      case_number: r.case_number,
    })),
    zoning_match: zoningRows[0] || null,
    note: rows.length === 0 ? 'Property not in active auction pipeline. It may not be distressed or may be in a county not yet covered.' : null,
  };
}

export async function get_property_detail({ parcel_id, county, address, case_number }) {
  const filters = [`county=ilike.${encodeURIComponent((county || '').replace(/\s+/g, '%'))}`];
  if (parcel_id) filters.push(`parcel_id=eq.${encodeURIComponent(parcel_id)}`);
  else if (case_number) filters.push(`case_number=eq.${encodeURIComponent(case_number)}`);
  else if (address) filters.push(`property_address=ilike.${encodeURIComponent(`%${address}%`)}`);

  const [auction, zoning] = await Promise.all([
    get(`multi_county_auctions?${filters.join('&')}&limit=1&select=case_number,county,property_address,parcel_id,opening_bid,auction_date,sale_type,judgment_amount,plaintiff,beds,baths,sqft,year_built`).catch(() => []),
    parcel_id
      ? get(`zoning_assignments?parcel_id=eq.${encodeURIComponent(parcel_id)}&limit=1&select=parcel_id,zone_code,zone_source,county,dor_uc`).catch(() => [])
      : Promise.resolve([]),
  ]);

  const a = auction[0];
  const z = zoning[0];

  if (!a && !z) {
    return {
      found: false,
      parcel_id,
      county,
      message: 'Property not found in BidDeed database.',
      bcpao_link: county?.toLowerCase().includes('brevard')
        ? `https://www.bcpao.us/PropertySearch/#search`
        : 'Run find_local_partners (S1) to get county property appraiser link',
    };
  }

  // DOR use code crosswalk (FL Department of Revenue)
  const DOR_UC = {
    '01': 'Single Family Residential',
    '02': 'Mobile Home',
    '03': 'Multi-Family (2–9 units)',
    '04': 'Condominium',
    '06': 'Retirement Home / ALF',
    '07': 'Miscellaneous Residential',
    '08': 'Multi-Family (10+ units)',
    '10': 'Vacant Residential',
    '11': 'Stores',
    '17': 'Office Building',
    '20': 'Airport',
    '40': 'Vacant Industrial',
    '50': 'Cropland',
    '69': 'Ornamentals / Misc Agri',
  };

  return {
    found: true,
    parcel_id: a?.parcel_id || parcel_id,
    county: a?.county || county,
    property_address: a?.property_address || address,
    auction_record: a || null,
    zoning: z
      ? { zone_code: z.zone_code, source: z.zone_source }
      : { note: 'Run check_zoning (S3) for full zoning detail' },
    dor_use_code: z?.dor_uc || null,
    dor_use_description: DOR_UC[z?.dor_uc] || null,
    fl_appraiser_link: county?.toLowerCase().includes('brevard')
      ? `https://www.bcpao.us/PropertySearch/#parcel/${parcel_id}`
      : `https://www.${county?.toLowerCase().replace(/\s+/g, '')}propertyappraiser.com`,
    auction_history: a
      ? {
          case_number: a.case_number,
          sale_type: a.sale_type,
          auction_date: a.auction_date,
          opening_bid: a.opening_bid,
          final_judgment: a.judgment_amount,
        }
      : null,
  };
}

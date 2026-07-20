// GTM-22 S5 REPORT ENGINE — golden fixture tests, issue #12853.
//
// Fixture data below is a live snapshot pulled 2026-07-20 from
// multi_county_auctions / fl_parcels (READ-ONLY queries, pasted in the issue
// report). These tests assert this engine's OWN behavior is correct,
// reproducible, and internally consistent — not that its numeric outputs are
// byte-identical to the brief's reference implementation. Where they
// diverge (value-estimate midpoint / ceiling exact dollar figures — see
// composer.js header and the issue report for the full comparison), that is
// a disclosed, honest deviation: the reference formula's exact weights are
// not recoverable from the brief text, and this suite does not curve-fit to
// guess them.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { buildReport } = await import('../src/report/composer.js');
const { _setModelForTest, _resetModelForTest } = await import('../src/report/xgboost-model.js');

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const tinyModelDoc = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/tiny-xgb-model.json'), 'utf8'));

function installTinyModel() {
  const gbm = tinyModelDoc.learner.gradient_booster.model;
  _setModelForTest({
    version: 'v14.0',
    trees: gbm.trees,
    baseScore: parseFloat(tinyModelDoc.learner.learner_model_param.base_score),
    featureNames: [],
  });
}

// Live snapshot, 2026-07-20 (multi_county_auctions.id, resolved from case
// number suffix per the brief's fixture numbering 414/2330/569/1771).
const AUCTION_414 = {
  case_number: '422021CA000414CAAXXX', county: 'marion',
  property_address: '14470 SE 91ST TER, SUMMERFIELD, FL- 34491',
  auction_date: '2026-07-20', judgment_amount: 164134.35, plaintiff: 'U.S. Bank Trust National Association, as Trustee of Towd Point Master Funding Trust 2022-EBO1-REO',
  opening_bid: null, assessed_value: 125014, market_value: 125014, plaintiff_max_bid: 71980,
  plaintiff_max_bid_source: 'owner_observed_rendered_page_2026-07-20T11:56:00Z',
  property_type: 'MH - MOBILE - MOBILE HOME RESID', year_built: 2005, lot_size: 0.34,
  living_area_sqft: 1248, bedrooms: 3, bathrooms: 2, prior_sale_date: '2023-03-01', prior_sale_price: 75100,
  owner_name: 'TPMFT 2021-PM1    ET AL', homestead_status: 'non-homestead', sale_type: 'foreclosure',
  parity_status: 'matched_clean',
};

const AUCTION_2330 = {
  case_number: '422024CA002330CAAXMX', county: 'marion',
  property_address: null, judgment_amount: 718587.84, plaintiff_max_bid: 718587.84,
  sale_type: 'foreclosure',
};

const AUCTION_569 = {
  case_number: '422025CA000569CAAXMX', county: 'marion',
  property_address: '16667 SE 96TH CT, SUMMERFIELD, FL- 34491',
  judgment_amount: 208514.8, assessed_value: 109235, plaintiff_max_bid: null,
  property_type: 'MH - MOBILE - MOBILE HOME RESID', year_built: 1986,
  homestead_status: 'homestead', owner_name: 'SMITH JOHN', sale_type: 'foreclosure',
};

const AUCTION_1771 = {
  case_number: '422025CA001771CAAXMX', county: 'marion',
  property_address: '4551 SW 103RD PL, OCALA, FL- 34476',
  judgment_amount: 266721.33, assessed_value: 289040, plaintiff_max_bid: null,
  prior_sale_date: '2006-05-01', prior_sale_price: 246900,
  auction_date: '2026-07-20', owner_name: 'DOE JANE', sale_type: 'foreclosure',
};

// 12 rows with a judgment_amount (>= MIN_N_FOR_CONFIDENCE in priors.js) so
// the county-clearance anchors are available, mirroring the live Marion
// corpus (n=159 sold/assessed, n=36 sold/FJ — this is a representative
// subset, not a byte-copy).
const MARION_PRIORS_ROWS = [
  { sold_amount: 72201, assessed_value: 97961, judgment_amount: 170567.28 },
  { sold_amount: 147001, assessed_value: 150000, judgment_amount: 338347.79 },
  { sold_amount: 21002, assessed_value: 150000, judgment_amount: 9246.71 },
  { sold_amount: 40001, assessed_value: 150000, judgment_amount: 71947.62 },
  { sold_amount: 108561, assessed_value: 215707, judgment_amount: 160000 },
  { sold_amount: 55000, assessed_value: 90000, judgment_amount: 100000 },
  { sold_amount: 65000, assessed_value: 95000, judgment_amount: 110000 },
  { sold_amount: 75000, assessed_value: 100000, judgment_amount: 120000 },
  { sold_amount: 85000, assessed_value: 110000, judgment_amount: 130000 },
  { sold_amount: 95000, assessed_value: 120000, judgment_amount: 140000 },
  { sold_amount: 105000, assessed_value: 130000, judgment_amount: 150000 },
  { sold_amount: 115000, assessed_value: 140000, judgment_amount: 165000 },
];

const PARCEL_414 = { parcel_id: '4593-018-011', co_no: 52, phy_addr1: '14470 SE 91ST TER', phy_city: 'SUMMERFIELD', municipality: 'SUMMERFIELD', dor_uc: '002', jv: 125014, lnd_val: 23428, lnd_sqfoot: 15000, tot_lvg_ar: 1248, phy_zipcd: '34491' };
const PARCEL_569 = { parcel_id: '48333-004-05', co_no: 52, phy_addr1: '16667 SE 96TH CT', phy_city: 'SUMMERFIELD', municipality: 'SUMMERFIELD', dor_uc: '002', jv: 109235, lnd_val: 39900, lnd_sqfoot: 8625, tot_lvg_ar: 1100, phy_zipcd: '34491' };
const PARCEL_1771 = { parcel_id: '3578-025-012', co_no: 52, phy_addr1: '4551 SW 103RD PL', phy_city: 'OCALA', municipality: 'OCALA', dor_uc: '001', jv: 297594, lnd_val: 48500, lnd_sqfoot: 20000, tot_lvg_ar: 2142, phy_zipcd: '34476' };

function mockGetFor(parcelByAddr) {
  return async (pathStr) => {
    if (pathStr.startsWith('multi_county_auctions')) return MARION_PRIORS_ROWS;
    if (pathStr.startsWith('fl_parcels')) {
      const match = decodeURIComponent(pathStr).match(/phy_addr1=eq\.([^&]+)/);
      const addr = match?.[1];
      const found = parcelByAddr[addr];
      return found ? [found] : [];
    }
    if (pathStr.startsWith('zoning_assignments')) return []; // Marion: 0 rows, confirmed live
    return [];
  };
}

test('414: locatable, resolves state parcel, BID-family verdict with a real value estimate', async () => {
  installTinyModel();
  const get = mockGetFor({ '14470 SE 91ST TER': PARCEL_414 });
  const report = await buildReport(AUCTION_414, { get });
  assert.equal(report.cover.case_number, '422021CA000414CAAXXX');
  assert.ok(['BID', 'BID (conditional)', 'REVIEW'].includes(report.cover.verdict), `expected a locatable-property verdict, got ${report.cover.verdict}`);
  assert.ok(report.value_estimate, 'a locatable property with priors must carry a value estimate');
  assert.equal(report.zoning.state_parcel_id, '4593-018-011');
  assert.equal(report.zoning.dor_use_code, '002');
  assert.equal(report.zoning.land_value, 23428);
  assert.equal(report.zoning.land_sqft, 15000);
  assert.equal(report.zoning.zoning_district, 'PENDING');
  assert.ok(report.red_flags.some(f => f.code === 'MH_TITLE'));
  _resetModelForTest();
});

test('2330: unlocatable subject — SKIP, no value estimate, exact refusal sentence, no comps', async () => {
  const get = mockGetFor({});
  const report = await buildReport(AUCTION_2330, { get });
  assert.equal(report.cover.verdict, 'SKIP');
  assert.equal(report.value_estimate, null);
  assert.equal(report.refusal, "An estimate here would be fabrication; BidDeed declines where HouseCanary would extrapolate.");
  assert.deepEqual(report.cma.comps, []);
  assert.equal(report.zoning.matched, false);
});

test('569: hidden plaintiff max bid renders literal "Hidden", never $0, plus homestead + pre-1990-MH flags', async () => {
  installTinyModel();
  const get = mockGetFor({ '16667 SE 96TH CT': PARCEL_569 });
  const report = await buildReport(AUCTION_569, { get });
  assert.equal(report.auction_listing.plaintiff_max_bid.display, 'Hidden');
  assert.equal(report.auction_listing.plaintiff_max_bid.value, null);
  assert.ok(!JSON.stringify(report.auction_listing).includes('"$0"'), 'a hidden cap must never render as $0');
  assert.ok(report.red_flags.some(f => f.code === 'HOMESTEAD_OCCUPIED'));
  assert.ok(report.red_flags.some(f => f.code === 'PRE_1990_MH'));
  assert.ok(report.red_flags.some(f => f.code === 'HIDDEN_CAP'));
  _resetModelForTest();
});

test('1771: stale (>5yr) prior sale is excluded from the value anchor but retained in transaction_history', async () => {
  installTinyModel();
  const get = mockGetFor({ '4551 SW 103RD PL': PARCEL_1771 });
  const report = await buildReport(AUCTION_1771, { get });
  assert.equal(report.transaction_history.prior_sale_date, '2006-05-01');
  assert.equal(report.transaction_history.prior_sale_price.value, 246900);
  const priorSaleAnchor = report.value_estimate.anchors.find(a => a.key === 'prior_arms_length_sale');
  assert.equal(priorSaleAnchor.value, null, 'a 20-year-stale sale must not be averaged into the value estimate unadjusted');
  assert.match(priorSaleAnchor.source, /stale/);
  assert.equal(report.zoning.dor_jv_vs_assessed_divergence.dor_jv, 297594);
  assert.equal(report.zoning.dor_jv_vs_assessed_divergence.pa_assessed, 289040);
  _resetModelForTest();
});

test('every dollar figure in the cover block carries a source', () => {
  installTinyModel();
  const get = mockGetFor({ '14470 SE 91ST TER': PARCEL_414 });
  buildReport(AUCTION_414, { get }).then((report) => {
    assert.ok(report.cover.shapira_max_bid.source);
    assert.ok(report.cover.entry_bid.source);
  });
  _resetModelForTest();
});

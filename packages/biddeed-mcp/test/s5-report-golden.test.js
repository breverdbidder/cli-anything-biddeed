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
import path from 'path';
import { fileURLToPath } from 'url';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { buildReport } = await import('../src/report/composer.js');

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// FIX (S5 Report Integrity Mission, Aug 21 2026): this suite used to mock the
// retired v14.0 XGBoost model via xgboost-model.js's _setModelForTest, which
// composer.js has not called since the V4 ensemble cutover (it now calls
// ensemble-model.js's predictEnsemble exclusively — see composer.js
// scoreModel()). xgboost-model.js was also independently overwritten on
// Aug 7 with an unrelated ONNX-Node V4 module (issue found this session:
// top-level `import ort from 'onnxruntime-node'`, a package not even in
// package.json), so this suite's model-mock import crashed the entire test
// file at load time - `node --test` never ran a single assertion in it.
// None of the assertions below check model-score fields; scoreModel() in
// composer.js already catches predictEnsemble() failures non-fatally
// (available:false, model_version:null) so buildReport() completes fine
// without a live Modal/Supabase connection. The mock calls are removed
// rather than repaired because there is nothing left in the current
// architecture for them to mock.
function installTinyModel() {}

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
    if (pathStr.startsWith('county_co_no_resolution')) return [{ co_no: 52 }]; // marion, live-confirmed
    if (pathStr.startsWith('fl_parcels')) {
      const match = decodeURIComponent(pathStr).match(/phy_addr1=eq\.([^&]+)/);
      const addr = match?.[1];
      const found = parcelByAddr[addr];
      return found ? [found] : [];
    }
    if (pathStr.startsWith('zoning_assignments')) return []; // Marion: 0 rows, confirmed live
    // Live snapshot, 2026-08-01: marion/foreclosure "ALL" row from
    // shapira_formula_params (sample_size=514). Marion foreclosure plaintiffs
    // rarely discount off judgment (plaintiff_discount_factor=0.2872), which
    // is why fixture 414 below now lands SKIP under this formula even though
    // the old flat-buffer formula rendered it BID-family (see the updated
    // assertion below).
    if (pathStr.startsWith('shapira_formula_params')) return [{ optimal_bid_pct_of_assessed: 0.7647, bid_floor_pct: 0.7746, bid_ceiling_pct: 1.2920, plaintiff_discount_factor: 0.2872, sample_size: 514, model_version: 'formula_v1' }];
    return [];
  };
}

test('414: locatable, resolves state parcel, shapira_formula_params-driven verdict with a real value estimate', async () => {
  installTinyModel();
  const get = mockGetFor({ '14470 SE 91ST TER': PARCEL_414 });
  const report = await buildReport(AUCTION_414, { get });
  assert.equal(report.cover.case_number, '422021CA000414CAAXXX');
  // Under the county-calibrated shapira_formula_params formula (marion
  // foreclosure plaintiff_discount_factor=0.2872 — plaintiffs rarely
  // discount off judgment), the Shapira ceiling ($16,213) lands well below
  // the $71,980 entry bid, so this fixture is correctly SKIP — not the
  // BID-family result the old flat-buffer formula produced. See the
  // shapira_formula_params mock comment above.
  assert.equal(report.cover.verdict, 'SKIP', `expected SKIP under the recalibrated formula, got ${report.cover.verdict}`);
  assert.ok(report.cover.shapira_max_bid.source.includes('shapira_formula_params'), 'shapira_max_bid.source must disclose the shapira_formula_params provenance');
  assert.ok(report.value_estimate, 'a locatable property with priors must carry a value estimate');
  assert.equal(report.zoning.state_parcel_id, '4593-018-011');
  assert.equal(report.zoning.dor_use_code, '002');
  assert.equal(report.zoning.land_value, 23428);
  assert.equal(report.zoning.land_sqft, 15000);
  assert.equal(report.zoning.zoning_district, 'PENDING');
  assert.ok(report.red_flags.some(f => f.code === 'MH_TITLE'));
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
});

test('every dollar figure in the cover block carries a source', () => {
  installTinyModel();
  const get = mockGetFor({ '14470 SE 91ST TER': PARCEL_414 });
  buildReport(AUCTION_414, { get }).then((report) => {
    assert.ok(report.cover.shapira_max_bid.source);
    assert.ok(report.cover.entry_bid.source);
  });
});

// ── S5 REPORT INTEGRITY MISSION regression fixture ──────────────────────────
// Palm Beach 502025CA005319XXXAMB, mca_id cad5d07a-b9c7-433d-b365-3165637b7cbe.
// Live defect (verified against multi_county_auctions this session): a
// $17,403.61 judgment on a $457,184 assessed house (3.8% ratio) — an
// HOA-style junior-lien foreclosure filed under a CA case number with no
// plaintiff on file — shipped a $329K max bid on a lot that actually cleared
// at $50,100 (auction_status=completed, tier1_sold_amount=50100,
// tier1_sale_status=SOLD). This fixture pins the three fixes (red-flags.js
// c041784, composer.js 33d6996) so this exact defect class cannot silently
// regress: (1) JUNIOR_LIEN_RISK fires off the judgment/assessed ratio even
// with plaintiff null and a CA (not CC) case number, (2) the judgment-ratio
// clearing anchor is excluded (value:null) rather than dragging the average,
// (3) a completed auction carries AUCTION_COMPLETED and never a bare BID.
const PARCEL_PALM_BEACH = {
  parcel_id: 'PB-TEST-00531', co_no: 60, phy_addr1: '123 TEST LN',
  phy_city: 'WEST PALM BEACH', municipality: 'WEST PALM BEACH', dor_uc: '001',
  jv: 457184, lnd_val: 120000, lnd_sqfoot: 8000, tot_lvg_ar: 2400,
  phy_zipcd: '33401',
};

const AUCTION_PALM_BEACH = {
  case_number: '502025CA005319XXXAMB', county: 'palm_beach',
  property_address: '123 TEST LN, WEST PALM BEACH, FL- 33401',
  auction_date: '2026-06-01', judgment_amount: 17403.61, plaintiff: null,
  opening_bid: 17403.61, assessed_value: 457184, market_value: 457184,
  plaintiff_max_bid: null, sale_type: 'foreclosure',
  auction_status: 'completed', tier1_sold_amount: 50100,
  tier1_sale_status: 'SOLD', homestead_status: 'non-homestead',
  owner_name: 'TEST OWNER', parity_status: 'matched_clean',
};

// Palm Beach-shaped priors (roughly mirrors the live median_sold_to_assessed
// ~0.50 noted for this county) — not a byte-copy of the live corpus.
const PALM_BEACH_PRIORS_ROWS = [
  { sold_amount: 60000, assessed_value: 120000, judgment_amount: 140000 },
  { sold_amount: 75000, assessed_value: 150000, judgment_amount: 175000 },
  { sold_amount: 90000, assessed_value: 180000, judgment_amount: 210000 },
  { sold_amount: 50000, assessed_value: 100000, judgment_amount: 118000 },
  { sold_amount: 110000, assessed_value: 220000, judgment_amount: 255000 },
  { sold_amount: 65000, assessed_value: 130000, judgment_amount: 152000 },
  { sold_amount: 80000, assessed_value: 160000, judgment_amount: 188000 },
  { sold_amount: 95000, assessed_value: 190000, judgment_amount: 222000 },
  { sold_amount: 55000, assessed_value: 110000, judgment_amount: 129000 },
  { sold_amount: 100000, assessed_value: 200000, judgment_amount: 233000 },
  { sold_amount: 70000, assessed_value: 140000, judgment_amount: 163000 },
  { sold_amount: 85000, assessed_value: 170000, judgment_amount: 198000 },
];

function mockGetForPalmBeach() {
  return async (pathStr) => {
    if (pathStr.startsWith('multi_county_auctions')) return PALM_BEACH_PRIORS_ROWS;
    if (pathStr.startsWith('county_co_no_resolution')) return [{ co_no: 60 }]; // palm_beach, live-confirmed
    if (pathStr.startsWith('fl_parcels')) {
      const match = decodeURIComponent(pathStr).match(/phy_addr1=eq\.([^&]+)/);
      const addr = match?.[1];
      return addr === '123 TEST LN' ? [PARCEL_PALM_BEACH] : [];
    }
    if (pathStr.startsWith('zoning_assignments')) return [];
    if (pathStr.startsWith('shapira_formula_params')) return []; // falls to default params
    return [];
  };
}

test('Palm Beach 502025CA005319XXXAMB: junior-lien judgment ratio fires, garbage anchor excluded, completed sale never bare BID', async () => {
  installTinyModel();
  const get = mockGetForPalmBeach();
  const report = await buildReport(AUCTION_PALM_BEACH, { get });

  assert.ok(report.red_flags.some(f => f.code === 'JUNIOR_LIEN_RISK'),
    'a 3.8% judgment/assessed ratio must fire JUNIOR_LIEN_RISK even with plaintiff null and a CA case number');
  assert.ok(report.red_flags.some(f => f.code === 'AUCTION_COMPLETED'),
    'a completed auction (tier1_sold_amount set) must carry AUCTION_COMPLETED');
  assert.ok(report.value_estimate, 'a locatable property with priors must still carry a value estimate');
  const judgmentAnchor = report.value_estimate.anchors.find(a => a.key === 'judgment_ratio_prior');
  assert.equal(judgmentAnchor.value, null,
    'the judgment-ratio anchor must be excluded (null), not $17,403.61 x ratio dragging the clearing average');
  assert.match(judgmentAnchor.source, /junior-lien scale, excluded/);
  assert.ok(!report.cover.verdict.startsWith('BID'),
    `a completed junior-lien lot must never render a bare BID verdict, got ${report.cover.verdict}`);
  // The historical defect: a raw-assessed ARV fallback produced a ~$329K
  // ceiling. With that fallback removed, either there is no ceiling at all
  // (null) or, if clearing anchors alone produce one, it must be nowhere
  // near assessed value ($457,184) — the failure mode was ceiling tracking
  // assessed_value directly.
  const maxBid = report.cover.shapira_max_bid.value;
  if (maxBid != null) {
    assert.ok(maxBid < AUCTION_PALM_BEACH.assessed_value * 0.5,
      `shapira_max_bid ($${maxBid}) must not track raw assessed value ($${AUCTION_PALM_BEACH.assessed_value}) on a junior-lien lot`);
  }
});

// ── §16 lien_survival.classify — statute-cited survival + ship-gate ────────
// SIGNAL$ Property Report §16 (Judgment & Encumbrance Summary) issue: real
// lien_survival.classify wired through sectionComposition()'s ship-gate.
// Reuses the Palm Beach fixture's parcel/case shape.
const LIEN_RESULTS_ROWS = [
  { lien_type: 'First Mortgage', creditor: 'Test Bank NA', recording_date: '2015-01-10', book_page: '1001/200', priority: 'senior', survives_foreclosure: null, source: 'acclaim' },
  { lien_type: 'HOA Assessment Lien', creditor: 'Test HOA Inc', recording_date: '2024-03-01', book_page: '3002/50', priority: 'junior', survives_foreclosure: null, source: 'acclaim' },
];

const COMPOSITION_GATE_LIVE = [
  { section_key: 'lien_search', ship_status: 'blocked', disclosure_text: 'DISCLOSURE_LIEN_SEARCH' },
  { section_key: 'lien_survival', ship_status: 'live', disclosure_text: 'This section is provided for investment due-diligence purposes only. It is not title insurance, not a title opinion or abstract, and not legal advice.' },
  { section_key: 'title_search', ship_status: 'blocked', disclosure_text: 'DISCLOSURE_TITLE_SEARCH' },
];

const COMPOSITION_GATE_BLOCKED = [
  { section_key: 'lien_search', ship_status: 'blocked', disclosure_text: 'DISCLOSURE_LIEN_SEARCH' },
  { section_key: 'lien_survival', ship_status: 'blocked', disclosure_text: 'DISCLOSURE_LIEN_SURVIVAL' },
  { section_key: 'title_search', ship_status: 'blocked', disclosure_text: 'DISCLOSURE_TITLE_SEARCH' },
];

function mockGetForPalmBeachWithLiens(compositionGate) {
  const base = mockGetForPalmBeach();
  return async (pathStr) => {
    if (pathStr.startsWith('rpc/get_report_composition_gate')) return compositionGate;
    if (pathStr.startsWith('lien_results')) return LIEN_RESULTS_ROWS;
    return base(pathStr);
  };
}

test('§16 lien_survival: ship_status=live + recorded liens on file → statute-cited survive/extinguish lines + disclosure text', async () => {
  installTinyModel();
  const get = mockGetForPalmBeachWithLiens(COMPOSITION_GATE_LIVE);
  const report = await buildReport(AUCTION_PALM_BEACH, { get });

  assert.equal(report.composition.lien_survival.status, 'delivered',
    'ship_status=live must surface lien_survival as delivered, not the gated Pending string');
  assert.ok(report.composition.lien_survival.disclosure.includes('not title insurance'),
    'the delivered composition entry must carry the verbatim disclosure_text');
  assert.ok(report.lien_survival.available, 'classify() must find the mocked lien_results rows');
  assert.equal(report.lien_survival.items.length, 2);

  const senior = report.lien_survival.items.find(i => i.lien_type === 'First Mortgage');
  assert.equal(senior.survives, true, 'a senior-priority lien must be classified as surviving this foreclosure');
  assert.match(senior.statutory_basis, /recording priority|first in time/i,
    'survival must be statute/doctrine-cited, per the liability_note on this spec row');
  assert.doesNotMatch(senior.statement, /you (will )?owe|amount owed is/i,
    'output must never be an owed-amount conclusion — the sharpest UPL edge on this section');

  const junior = report.lien_survival.items.find(i => i.lien_type === 'HOA Assessment Lien');
  assert.equal(junior.survives, false, 'a junior-priority lien must be classified as extinguished by this foreclosure');
});

test('§16 lien_survival: ship_status=blocked → internal-preview-only, never rendered as delivered to a customer response', async () => {
  installTinyModel();
  const get = mockGetForPalmBeachWithLiens(COMPOSITION_GATE_BLOCKED);
  const report = await buildReport(AUCTION_PALM_BEACH, { get });

  assert.notEqual(report.composition.lien_survival.status, 'delivered',
    'a still-blocked ship_status must never render as delivered, even when classify() has real data available');
  assert.match(report.composition.lien_survival.status, /internal-preview-only/,
    'the ship-gate fix (B3) must name the gated state explicitly, not silently omit it');
  // The real classification is still computed (available for internal QA /
  // the moment ship_status flips) — it is the composition status gate that
  // withholds it from the customer path, not classify() itself.
  assert.ok(report.lien_survival.available, 'classify() output is always computed regardless of the ship gate');
});

// ── §16 lien_survival — issue #19661 pre-step fixes ─────────────────────────
// Fix 1: §197.122 property-tax-lien super-priority on the foreclosure path.
// Fix 2: the survives_foreclosure boolean fallback must not honor a raw
// harvester column default (priority=null) as if it were a derived call.
const LIEN_RESULTS_ROWS_197122 = [
  { lien_type: 'Property Tax Certificate', creditor: 'County Tax Collector', recording_date: '2026-01-05', book_page: '4001/10', priority: null, survives_foreclosure: null, source: 'acclaim' },
  { lien_type: 'Second Mortgage', creditor: 'Test Bank NA', recording_date: '2010-01-01', book_page: '900/1', priority: 'junior', survives_foreclosure: null, source: 'acclaim' },
];

function mockGetForPalmBeachWithTaxLien() {
  const base = mockGetForPalmBeach();
  return async (pathStr) => {
    if (pathStr.startsWith('rpc/get_report_composition_gate')) return COMPOSITION_GATE_LIVE;
    if (pathStr.startsWith('lien_results')) return LIEN_RESULTS_ROWS_197122;
    return base(pathStr);
  };
}

test('§16 lien_survival FIX 1: a property tax lien/certificate on the foreclosure path survives under §197.122 super-priority, regardless of recording date', async () => {
  installTinyModel();
  const get = mockGetForPalmBeachWithTaxLien();
  const report = await buildReport(AUCTION_PALM_BEACH, { get });

  const taxLien = report.lien_survival.items.find(i => i.lien_type === 'Property Tax Certificate');
  assert.equal(taxLien.survives, true, 'a property tax lien/certificate must survive foreclosure under §197.122 super-priority');
  assert.match(taxLien.statutory_basis, /197\.122/, 'the tax-lien exception must cite Fla. Stat. §197.122');
  assert.doesNotMatch(taxLien.statement, /you (will )?owe|amount owed is/i,
    'output must never be an owed-amount conclusion');

  const juniorMortgage = report.lien_survival.items.find(i => i.lien_type === 'Second Mortgage');
  assert.equal(juniorMortgage.survives, false, 'ordinary recording-priority classification is unaffected by the tax-lien exception');
});

const LIEN_RESULTS_ROWS_DEFAULTED = [
  // Mirrors the live Pasco pattern: survives_foreclosure=false written as a
  // raw harvester column default — priority/amount both null, no derivation.
  { lien_type: 'Code Enforcement/Municipal Lien', creditor: 'Test County BOCC', recording_date: '2024-05-09', book_page: '11008/688', priority: null, amount: null, survives_foreclosure: false, source: 'or_name_search' },
];

function mockGetForPalmBeachWithDefaultedFlag() {
  const base = mockGetForPalmBeach();
  return async (pathStr) => {
    if (pathStr.startsWith('rpc/get_report_composition_gate')) return COMPOSITION_GATE_LIVE;
    if (pathStr.startsWith('lien_results')) return LIEN_RESULTS_ROWS_DEFAULTED;
    return base(pathStr);
  };
}

test('§16 lien_survival FIX 2: a defaulted survives_foreclosure=false with no priority/amount on file classifies UNRESOLVED, never extinguished', async () => {
  installTinyModel();
  const get = mockGetForPalmBeachWithDefaultedFlag();
  const report = await buildReport(AUCTION_PALM_BEACH, { get });

  const item = report.lien_survival.items[0];
  assert.equal(item.survives, null, 'a raw harvester default (priority=null) must never masquerade as a derived survival call');
  assert.equal(item.statutory_basis, null);
  assert.equal(item.statement, "Insufficient recorded-document data on file to classify this lien's survival — recording date/priority not on file. Not classified as survives or extinguished.");
});

test('§16 lien_survival: ship_status=live but no recorded-document coverage on file → explicit insufficient-coverage Pending, never a silent heuristic-only fallback', async () => {
  installTinyModel();
  const get = async (pathStr) => {
    if (pathStr.startsWith('rpc/get_report_composition_gate')) return COMPOSITION_GATE_LIVE;
    if (pathStr.startsWith('lien_results')) return [];
    return mockGetForPalmBeach()(pathStr);
  };
  const report = await buildReport(AUCTION_PALM_BEACH, { get });
  assert.equal(report.lien_survival.available, false);
  assert.match(report.composition.lien_survival.status, /insufficient recorded-document coverage/,
    'no lien_results rows for this parcel must render the exact insufficient-coverage Pending reason, not fall back silently to only the red-flags heuristic');
});

// ── §1 tax-deed "Judgment Amount: Pending" fix (issue #19662) ──────────────
// Tax deed sales (FL FS Ch. 197) have no final judgment — that is a
// foreclosure (Ch. 45) concept. Live defect (Pasco 512026XX000100TDAXXX /
// 512026XX000105TDAXXX, verification/signal-report-INTERNAL-pasco-*.png):
// §1 rendered "Judgment Amount: Pending" on tax deed cases, which falsely
// implies a judgment exists and is forthcoming. Fixed at the source: the
// composer's auction_listing object for isTaxDeed never carries a
// judgment_amount key at all, only unpaid_taxes (the opening-bid basis) /
// outstanding_certs_total / cert_number — every renderer (worker.js, pdf.js,
// generate_internal_signal_report.mjs, which as of the consistency fix calls
// worker.js's renderS5ReportHtml directly rather than a second template)
// must brand on cover.sale_type and stop rendering a Judgment field for
// these cases.
const PARCEL_PASCO_TD = {
  parcel_id: 'PASCO-TD-TEST-01', co_no: 51, phy_addr1: '456 TAX DEED LN',
  phy_city: 'NEW PORT RICHEY', municipality: 'NEW PORT RICHEY', dor_uc: '000',
  jv: 45000, lnd_val: 20000, lnd_sqfoot: 6000, tot_lvg_ar: 0,
  phy_zipcd: '34652',
};

const AUCTION_PASCO_TAX_DEED = {
  case_number: '512026XX000100TDAXXX', county: 'pasco',
  property_address: '456 TAX DEED LN, NEW PORT RICHEY, FL- 34652',
  auction_date: '2026-09-15', sale_type: 'tax_deed',
  opening_bid: 10159.72, assessed_value: 45000, market_value: 45000,
  cert_number: null, outstanding_certs_total: null,
};

function mockGetForPascoTaxDeed() {
  return async (pathStr) => {
    if (pathStr.startsWith('multi_county_auctions')) return []; // insufficient priors — not the point of this fixture
    if (pathStr.startsWith('county_co_no_resolution')) return [{ co_no: 51 }]; // pasco
    if (pathStr.startsWith('fl_parcels')) {
      const match = decodeURIComponent(pathStr).match(/phy_addr1=eq\.([^&]+)/);
      const addr = match?.[1];
      return addr === '456 TAX DEED LN' ? [PARCEL_PASCO_TD] : [];
    }
    if (pathStr.startsWith('zoning_assignments')) return [];
    if (pathStr.startsWith('shapira_formula_params')) return []; // falls to default params
    if (pathStr.startsWith('rpc/get_report_composition_gate')) return [];
    if (pathStr.startsWith('lien_results')) return [];
    return [];
  };
}

test('Pasco tax deed 512026XX000100TDAXXX: auction_listing carries no judgment_amount key, opening_bid populated instead', async () => {
  installTinyModel();
  const get = mockGetForPascoTaxDeed();
  const report = await buildReport(AUCTION_PASCO_TAX_DEED, { get });

  assert.equal(report.cover.sale_type, 'tax_deed');
  assert.ok(!('judgment_amount' in report.auction_listing),
    'a tax deed auction_listing must never carry a judgment_amount key — a final judgment is a foreclosure (Ch. 45) concept');
  assert.equal(report.auction_listing.unpaid_taxes.value, 10159.72);
  assert.equal(report.auction_listing.unpaid_taxes.display, '$10,159.72');
  assert.ok(!('plaintiff' in report.auction_listing),
    'a tax deed sale has a taxing authority, not a plaintiff — the foreclosure-only field must not appear');
});

// worker.js's renderS5ReportHtml is the single renderer generate_internal_
// signal_report.mjs calls (post consistency-fix, issue #19661 follow-on) —
// it proves the fix end-to-end: real rendered HTML, not just the composer's
// data shape. See also packages/biddeed-mcp/test/s5-report-render-parity.test.js
// for the fuller internal-vs-production parity suite.
test('Pasco tax deed: rendered §1 HTML contains no "Judgment" and shows Opening Bid', async () => {
  installTinyModel();
  const { renderS5ReportHtml } = await import('../../../src/worker.js');
  const get = mockGetForPascoTaxDeed();
  const report = await buildReport(AUCTION_PASCO_TAX_DEED, { get });

  const html = renderS5ReportHtml(report, { mcaId: AUCTION_PASCO_TAX_DEED.case_number, keyLast8: 'TESTKEY1' });
  const sec1 = html.slice(html.indexOf('Subject Property Identification'), html.indexOf('Value Estimate'));

  assert.doesNotMatch(sec1, /Judgment/, '§1 must not render a "Judgment" field on a tax deed case');
  assert.match(sec1, /Opening Bid/, '§1 must render "Opening Bid" on a tax deed case');
  assert.match(sec1, /\$10,159\.72/, '§1 must render the real opening bid amount, not a placeholder');
});

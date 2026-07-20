// GTM-22 S5 REPORT ENGINE — county clearance priors unit tests (issue #12853).
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.SUPABASE_URL ||= 'https://test.supabase.co';
process.env.SUPABASE_SERVICE_ROLE_KEY ||= 'test-service-role-key';

const { getCountyClearancePriors } = await import('../src/report/priors.js');

test('getCountyClearancePriors: live-shaped Marion corpus reproduces the field-validated medians', async () => {
  // Snapshot pulled live 2026-07-20 (multi_county_auctions, county=marion,
  // sold_amount>100, auction_date>=2024-01-01): n=159 rows, 36 carry a
  // judgment_amount. This fixture is a representative subset, not the full
  // 159 rows — the assertion is on the formula, not a byte-copy of the corpus.
  const rows = [
    { sold_amount: 72201, assessed_value: 97961, judgment_amount: 170567.28 },
    { sold_amount: 147001, assessed_value: 150000, judgment_amount: 338347.79 },
    { sold_amount: 21002, assessed_value: 150000, judgment_amount: 9246.71 },
    { sold_amount: 40001, assessed_value: 150000, judgment_amount: 71947.62 },
    { sold_amount: 501, assessed_value: 150000, judgment_amount: 33608.68 },
    { sold_amount: 108561, assessed_value: 215707, judgment_amount: null },
    { sold_amount: 32483, assessed_value: 184393, judgment_amount: null },
    { sold_amount: 188701, assessed_value: 215707, judgment_amount: null },
    { sold_amount: 102070, assessed_value: 154284, judgment_amount: null },
    { sold_amount: 131201, assessed_value: 154284, judgment_amount: null },
  ];
  const mockGet = async () => rows;
  const result = await getCountyClearancePriors('marion', { get: mockGet });
  assert.equal(result.n_sold_to_assessed, 10);
  assert.equal(result.n_sold_to_judgment, 5);
  assert.ok(result.median_sold_to_assessed > 0);
  assert.ok(result.median_sold_to_judgment > 0);
});

test('getCountyClearancePriors: synthetic county with n<10 renders LOW confidence and does not borrow another county\'s priors', async () => {
  const rows = [
    { sold_amount: 50000, assessed_value: 80000, judgment_amount: 90000 },
    { sold_amount: 60000, assessed_value: 85000, judgment_amount: 95000 },
    { sold_amount: 70000, assessed_value: 90000, judgment_amount: 100000 },
  ];
  const mockGet = async () => rows;
  const result = await getCountyClearancePriors('synthetic_thin_county', { get: mockGet });
  assert.equal(result.n_sold_to_assessed, 3);
  assert.equal(result.confidence, 'LOW');
  assert.equal(result.insufficient, true);
  assert.match(result.note, /insufficient county priors \(n=3\)/);
  // No cross-county borrowing possible — the query is scoped to the county
  // argument only, so a thin result can only be this county's own data.
  assert.equal(result.county, 'synthetic_thin_county');
});

test('getCountyClearancePriors: empty corpus (n=0) is insufficient, not a crash', async () => {
  const mockGet = async () => [];
  const result = await getCountyClearancePriors('no_data_county', { get: mockGet });
  assert.equal(result.n_sold_to_assessed, 0);
  assert.equal(result.insufficient, true);
  assert.equal(result.median_sold_to_assessed, null);
});

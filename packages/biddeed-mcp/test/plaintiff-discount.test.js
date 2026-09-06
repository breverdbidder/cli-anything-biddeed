// Issue #20043 item 7 — Plaintiff Discount Index report band. Always prints
// n; renders "Pending — fewer than 3 observed third-party sales" below that
// threshold, per the issue's own DoD, never a fabricated ratio.
import { test } from 'node:test';
import assert from 'node:assert/strict';

const { buildPlaintiffDiscountBand } = await import('../src/report/plaintiff-discount.js');

test('no plaintiff_norm on file renders Pending with n=0, no query attempted', async () => {
  const result = await buildPlaintiffDiscountBand({ plaintiff_norm: null }, { get: async () => { throw new Error('should not be called'); } });
  assert.equal(result.available, false);
  assert.equal(result.n, 0);
  assert.match(result.reason, /Pending/);
});

test('fewer than 3 observed third-party sales renders Pending but still prints n', async () => {
  const get = async (path) => {
    if (path.startsWith('plaintiff_discount_index?period_type=eq.all_time')) {
      return [{ plaintiff_norm: 'ACME LLC', n_third_party_sales: 2, median_sold_to_judgment: 0.6 }];
    }
    return [];
  };
  const result = await buildPlaintiffDiscountBand({ plaintiff_norm: 'ACME LLC' }, { get });
  assert.equal(result.available, false);
  assert.equal(result.n, 2);
  assert.match(result.reason, /fewer than 3/);
});

test('n>=3 renders the full band with rank and quarter-of-sale', async () => {
  const get = async (path) => {
    if (path.startsWith('plaintiff_discount_index?period_type=eq.all_time')) {
      return [{ plaintiff_norm: 'ACME LLC', n_third_party_sales: 5, median_sold_to_judgment: 0.72, min_sold_to_judgment: 0.4, third_party_share: 0.3 }];
    }
    if (path.startsWith('plaintiff_discount_index?period_type=eq.quarter')) {
      return [{ quarter: '2026-07-01', n_third_party_sales: 3, median_sold_to_judgment: 0.65 }];
    }
    if (path.startsWith('v_plaintiff_discount_rank')) {
      return [{ rank_by_discount: 4 }];
    }
    return [];
  };
  const result = await buildPlaintiffDiscountBand({ plaintiff_norm: 'ACME LLC' }, { get });
  assert.equal(result.available, true);
  assert.equal(result.n, 5);
  assert.equal(result.median_sold_to_judgment, 0.72);
  assert.equal(result.rank_among_n_gte_3, 4);
  assert.equal(result.quarter_of_sale.n, 3);
});

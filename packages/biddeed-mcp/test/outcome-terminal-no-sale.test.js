// Issue #20043 item 1 — a past-dated auction resolved with tier1_sale_status
// CANCELED (no sold_amount, no winning_bidder) must render "Canceled — no
// sale occurred", never "Pending — outcome not captured". The latter implies
// the post-sale loop simply hasn't run yet, which is false: the outcome is
// known, and it isn't a sale. Regression case: Brevard case 250104
// (mca_id 19499973-5191-4e5b-bb96-c0f59fb14101), auction_date 2025-10-16,
// tier1_sale_status='CANCELED'.
import { test } from 'node:test';
import assert from 'node:assert/strict';

const { buildOutcomeSection } = await import('../src/report/outcome.js');

test('canceled auction renders Canceled, not Pending', () => {
  const section = buildOutcomeSection({
    auction_date: '2025-10-16',
    tier1_sale_status: 'CANCELED',
    auction_status: 'cancelled',
    sold_amount: null,
    tier1_sold_amount: null,
    winning_bidder: null,
    sale_result_date: null,
  });

  assert.match(section.status, /^Canceled — no sale occurred/);
  assert.equal(section.terminal_no_sale, 'CANCELED');
  assert.equal(section.outcome_captured, false);
  assert.equal(section.scorecard.available, false);
  assert.match(section.scorecard.note, /no sale occurred/);
});

test('true pending (no status, no sale) is unchanged', () => {
  const section = buildOutcomeSection({
    auction_date: '2025-10-16',
    tier1_sale_status: null,
    sold_amount: null,
  });

  assert.match(section.status, /^Pending — outcome not captured/);
  assert.equal(section.terminal_no_sale, null);
});

test('a captured sale still renders Captured even with a stray tier1_sale_status', () => {
  const section = buildOutcomeSection({
    auction_date: '2025-10-16',
    tier1_sale_status: 'SOLD',
    sold_amount: 150000,
    winning_bidder: 'THIRD PARTY LLC',
  });

  assert.equal(section.status, 'Captured');
  assert.equal(section.outcome_captured, true);
});

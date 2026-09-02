// Unit tests for workers/winnerdata-ff/src/ff_format.js (issue #19747).
// Plain Node test runner, no bundler/build step needed -- ff_format.js has
// no .html imports. Run: node --test workers/winnerdata-ff/test/

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeBuyerName, callScript } from '../src/ff_format.js';

// The exact raw deed boilerplate from FF 7dd22ccb (case 25001204CAAXMX,
// Martin County) -- reference case for issue #19747 defect 2.
const DEED_BOILERPLATE =
  '5755 Land Trust, WESTON PROPERTY HOLDING CORP as trustee, with full power ' +
  'and authority to protect, conserve and to sell, or to lease, or to ' +
  'encumber or otherwise to manage and dispose of the hereinafter described ' +
  'property in accordance with Section 689.071, Florida Statutes';

test('normalizeBuyerName strips deed boilerplate and formats trust/trustee', () => {
  assert.equal(
    normalizeBuyerName(DEED_BOILERPLATE),
    '5755 Land Trust — Weston Property Holding Corp, trustee'
  );
});

test('normalizeBuyerName negative test: non-trust name passes through unchanged', () => {
  assert.equal(normalizeBuyerName('SMITH JOHN'), 'SMITH JOHN');
});

test('normalizeBuyerName negative test: null/undefined pass through', () => {
  assert.equal(normalizeBuyerName(null), null);
  assert.equal(normalizeBuyerName(undefined), undefined);
  assert.equal(normalizeBuyerName(''), '');
});

test('normalizeBuyerName: boilerplate clause without a parseable trust/trustee prefix still strips the clause', () => {
  assert.equal(
    normalizeBuyerName('Some Unusual Trust Format with full power and authority to do things'),
    'Some Unusual Trust Format'
  );
});

test('callScript: certificate recorded reads ct_recording_date, never says "days ago"', () => {
  const script = callScript('5755 Land Trust — Weston Property Holding Corp, trustee', {
    case_number: '25001204CAAXMX',
    auction_date: '2026-09-01',
    sold_amount: 826200,
  }, '2026-09-02');
  assert.match(script, /Certificate of title recorded 2026-09-02, case 25001204CAAXMX\./);
  assert.doesNotMatch(script, /days ago/);
});

test('callScript: certificate NOT recorded says "not yet recorded", never "recorded N days ago"', () => {
  const script = callScript('5755 Land Trust — Weston Property Holding Corp, trustee', {
    case_number: '25001204CAAXMX',
    auction_date: '2026-09-01',
    sold_amount: 826200,
  }, null);
  assert.match(script, /Sale held 2026-09-01, certificate of title not yet recorded\./);
  assert.doesNotMatch(script, /days ago/);
  assert.doesNotMatch(script, /Certificate of title recorded,/);
});

test('callScript: still includes winning bid and buyer name', () => {
  const script = callScript('SMITH JOHN', {
    case_number: 'C1',
    auction_date: '2026-09-01',
    sold_amount: 100000,
  }, null);
  assert.match(script, /Winning bid was \$100,000\./);
  assert.match(script, /Calling SMITH JOHN re: property insurance on the new acquisition\./);
});

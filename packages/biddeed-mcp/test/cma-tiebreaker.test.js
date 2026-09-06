// Issue #20043 item 8 — CMA comps tied on sqft proximity used to fall back to
// whatever order PostgREST returned them in (unstable across requests, since
// no ORDER BY was specified on the tie dimension). Both CMA layers now break
// ties deterministically: sale date desc, then parcel_id/case_number asc.
import { test } from 'node:test';
import assert from 'node:assert/strict';

const { buildDistressedCma, buildCma } = await import('../src/report/cma.js');

test('Layer 1 (distressed CMA): sqft ties break by auction_date desc', async () => {
  const rows = [
    { case_number: '1', parcel_id: 'B', property_address: 'B ST', property_zip: '32901', living_area_sqft: 1500, assessed_value: 200000, tier1_sold_amount: 100000, auction_date: '2024-01-01' },
    { case_number: '2', parcel_id: 'A', property_address: 'A ST', property_zip: '32901', living_area_sqft: 1500, assessed_value: 200000, tier1_sold_amount: 110000, auction_date: '2024-06-01' },
    { case_number: '3', parcel_id: 'C', property_address: 'C ST', property_zip: '32901', living_area_sqft: 1502, assessed_value: 200000, tier1_sold_amount: 120000, auction_date: '2024-12-01' },
  ];
  const get = async (url) => (url.includes('property_zip=eq.') ? rows : []);

  const result = await buildDistressedCma(
    { tot_lvg_ar: 1500, phy_zipcd: '32901', dor_uc: '001', jv: 200000 },
    { county: 'brevard' },
    { get }
  );

  // Both "B ST" and "A ST" tie at sqft_delta=0; "A ST" (2024-06-01) must sort
  // before "B ST" (2024-01-01). "C ST" (sqft_delta=2) sorts last regardless
  // of its later date.
  assert.deepEqual(result.comps.map(c => c.address), ['A ST', 'B ST', 'C ST']);
});

test('Layer 2 (retail CMA): sqft ties break by sale_yr1/sale_mo1 desc, then parcel_id', async () => {
  const rows = [
    { parcel_id: 'ZZZ', phy_addr1: 'Z ADDR', tot_lvg_ar: 1500, sale_prc1: 200000, sale_yr1: 2024, sale_mo1: 3, jv: 200000, lnd_sqfoot: 8000 },
    { parcel_id: 'AAA', phy_addr1: 'A ADDR', tot_lvg_ar: 1500, sale_prc1: 210000, sale_yr1: 2024, sale_mo1: 3, jv: 200000, lnd_sqfoot: 8000 },
    { parcel_id: 'MMM', phy_addr1: 'M ADDR', tot_lvg_ar: 1500, sale_prc1: 220000, sale_yr1: 2024, sale_mo1: 9, jv: 200000, lnd_sqfoot: 8000 },
  ];
  const get = async () => rows;

  const result = await buildCma(
    { co_no: 5, phy_zipcd: '32901', dor_uc: '001', parcel_id: 'SUBJECT', jv: 200000, lnd_sqfoot: 8000 },
    { get }
  );

  // All three tie on sqft_delta=0. "M ADDR" (2024-09) sorts first (latest
  // sale). "Z ADDR" and "A ADDR" both tie on 2024-03 and break by parcel_id
  // asc: "AAA" < "ZZZ".
  assert.deepEqual(result.comps.map(c => c.address), ['M ADDR', 'A ADDR', 'Z ADDR']);
});

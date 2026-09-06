// One-off verification script for issue #20051. Fetches CENSUS_API_KEY from
// the Supabase vault into process.env (never logged) for this process only,
// then calls buildReport() directly against the live multi_county_auctions
// row for Martin County case 26000299CAAXMX — same code path the deployed
// Worker runs, invoked in-process per the #20044 precedent (docs/spec/20044.md)
// because this session has no bd_live_ API key to round-trip through the
// deployed HTTP endpoint. Prints only non-secret report fields.
import { buildReport } from '../src/report/composer.js';
import { renderReportPdf } from '../src/report/pdf.js';
import fs from 'node:fs';

async function fetchVaultSecret(name) {
  const resp = await fetch(
    'https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query',
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${process.env.SUPABASE_ACCESS_TOKEN}`,
        'Content-Type': 'application/json',
        'User-Agent': 'cli-anything-biddeed-cc/1.0',
      },
      body: JSON.stringify({ query: `SELECT vault_secret('${name}') AS v;` }),
    }
  );
  const rows = await resp.json();
  return rows?.[0]?.v || null;
}

const key = await fetchVaultSecret('CENSUS_API_KEY');
if (!key) {
  console.error('CENSUS_API_KEY not returned from vault');
  process.exit(1);
}
process.env.CENSUS_API_KEY = key;

const caseNumber = process.argv[2] || '26000299CAAXMX';
const res = await fetch(
  `${process.env.SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.${caseNumber}&select=*&limit=1`,
  {
    headers: {
      apikey: process.env.SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY}`,
    },
  }
);
const [auction] = await res.json();
if (!auction) {
  console.error('auction not found for', caseNumber);
  process.exit(1);
}

const report = await buildReport(auction, {});
console.log(JSON.stringify({
  case_number: auction.case_number,
  zip: auction.zip,
  context_layers: report.context_layers,
}, null, 2));

if (process.argv[3] === '--pdf') {
  const pdfBuf = await renderReportPdf(report, {});
  const outPath = `/tmp/20051-${caseNumber}.pdf`;
  fs.writeFileSync(outPath, pdfBuf);
  console.log('PDF written:', outPath, pdfBuf.length, 'bytes');
}

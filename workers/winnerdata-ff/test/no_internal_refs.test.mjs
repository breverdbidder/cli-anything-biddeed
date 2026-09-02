// issue #19751: client-facing Fact Finder HTML leaked internal build
// artifacts -- issue numbers, comment ids, "rebuilt from" notes -- visible
// in page source (they live in an HTML <!-- comment --> block, which
// browsers ship in view-source even though it never renders). Guards the
// template(s) workers/winnerdata-ff actually serves (src/index.js only
// imports FF_TEMPLATE_B_HOMEOWNER.html -- see the import comment there for
// why FF_TEMPLATE_A_AUCTION_SALES.html is never rendered by this Worker).
//
// Plain Node test runner, no bundler needed -- reads the template file
// directly as text, same approach as ff_format.test.mjs.
// Run: node --test workers/winnerdata-ff/test/

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATE_B_PATH = path.join(__dirname, '../../../templates/FF_TEMPLATE_B_HOMEOWNER.html');

// Per CC_META_PROMPT.md M3 / issue #19751 step 3 -- internal issue/comment
// ids and internal vendor/tool names must never appear in client-facing
// Fact Finder output. AskFetch is intentionally excluded: it is a real
// external insurance-underwriting SaaS the producer uses directly (verified
// 2026-09-02), not an internal enrichment vendor -- it stays, with the
// heading renamed to plain English (see the template's "Underwriting Quote
// Details" block).
const INTERNAL_REF_PATTERN = /issue\s*#?\d{4,}|#1[0-9]{4}\b|comment \d{6,}|apify|tracerfy|bright ?data|summitleads/i;

test('FF_TEMPLATE_B_HOMEOWNER.html carries no internal issue/comment/vendor references', () => {
  const html = readFileSync(TEMPLATE_B_PATH, 'utf8');
  const match = html.match(INTERNAL_REF_PATTERN);
  assert.equal(match, null, `found internal reference "${match && match[0]}" in shipped template`);
});

// Negative test: prove the regex itself actually catches the class of leak
// this guards against, so a future edit to the pattern can't silently stop
// matching anything.
test('negative test: the internal-ref pattern matches known-leaky text', () => {
  assert.match('Rebuilt from issue #19392 comment 5390376020', INTERNAL_REF_PATTERN);
  assert.match('see pre-#19434 behavior', INTERNAL_REF_PATTERN);
  assert.match('sourced via Tracerfy', INTERNAL_REF_PATTERN);
  assert.doesNotMatch('Open in AskFetch for underwriting quotes', INTERNAL_REF_PATTERN);
});

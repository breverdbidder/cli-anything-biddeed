#!/usr/bin/env node
// Generates tokens.css from tokens.json. Run after editing tokens.json:
//   node packages/tokens/generate.mjs
//
// This is intentionally a small, dependency-free script — the token set is
// small and stable (see docs/spec/19828.md for why a full build pipeline
// wasn't introduced in this pass).

import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const tokens = JSON.parse(readFileSync(path.join(__dirname, 'tokens.json'), 'utf8'));

const kebab = (s) => s.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();

function colorVars(scale, indent = '  ') {
  return Object.entries(scale)
    .map(([key, val]) => `${indent}--${kebab(key)}: ${val.hex};`)
    .join('\n');
}

const css = `/* GENERATED FILE — do not hand-edit. Source: packages/tokens/tokens.json.
   Regenerate with: node packages/tokens/generate.mjs
   SSOT for these values is biddeed-web/app/globals.css :root — see tokens.json
   $comment field. Both the Worker (src/worker.js) and biddeed-web should
   consume this file rather than hardcoding hex; see docs/spec/19828.md for
   the current adoption status (partial — Worker migration is follow-up work,
   not completed in issue #19828). */

:root {
${colorVars(tokens.color.light)}
  --amber: ${tokens.color.data.amber.hex};
  --radius: ${tokens.radius.base};
  --font-sans: '${tokens.font.sans.family}', ${tokens.font.sans.fallback.join(', ')};
  --font-display: '${tokens.font.display.family}', ${tokens.font.display.fallback.join(', ')};
  --font-mono: '${tokens.font.mono.family}', ui-monospace, monospace;
}

html[data-theme='dark'],
html.dark {
${colorVars(tokens.color.dark)}
}

.tabular-figures {
  font-variant-numeric: ${tokens.font.numericVariant};
}
`;

writeFileSync(path.join(__dirname, 'tokens.css'), css);
console.log('Wrote packages/tokens/tokens.css');

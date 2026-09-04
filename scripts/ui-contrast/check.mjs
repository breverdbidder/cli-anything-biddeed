#!/usr/bin/env node
// ui-contrast gate — issue #19828 item 3.
//
// Visits every route in routes.json at every configured viewport and fails
// (non-zero exit) if it finds: a visible text node under 4.5:1 contrast, an
// inline hex color in a `style` attribute, an inline `!important`, or a
// heading-hierarchy violation (zero or more than one <h1>).
//
// NOT wired into any GitHub Actions workflow. Standing mandate M5 on this
// session ("no workflow-file edits") blocks that step — see docs/spec/19828.md
// for the BLOCKED note. Run manually or wire in by hand:
//   node scripts/ui-contrast/check.mjs --base https://biddeed.ai
//   node scripts/ui-contrast/check.mjs --base http://127.0.0.1:8787 --screenshots
//
// Requires the `playwright` package with a chromium browser installed
// (`npx playwright install chromium`) — not a repo dependency by default,
// since this is a manually-run gate, not a build-time one yet.

import { chromium } from 'playwright';
import { readFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const getArg = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i !== -1 && args[i + 1] ? args[i + 1] : fallback;
};
const baseUrl = getArg('base', 'https://biddeed.ai');
const wantScreenshots = args.includes('--screenshots');
const screenshotDir = path.join(__dirname, 'screenshots');

const config = JSON.parse(readFileSync(path.join(__dirname, 'routes.json'), 'utf8'));

const CONTRAST_MIN = 4.5;

function relLum([r, g, b]) {
  const f = (c) => {
    c /= 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const [R, G, B] = [f(r), f(g), f(b)];
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

// Runs inside the page. Kept dependency-free (no DOM libs) since it's
// serialized into page.evaluate.
function pageEvalFn() {
  function relLum([r, g, b]) {
    const f = (c) => {
      c /= 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    const [R, G, B] = [f(r), f(g), f(b)];
    return 0.2126 * R + 0.7152 * G + 0.0722 * B;
  }
  function parseColor(str) {
    const m = str.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
    if (!m) return null;
    return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
  }
  function gradientColor(bgImage) {
    const matches = bgImage.match(/rgba?\([^)]+\)/g);
    if (!matches || !matches.length) return null;
    let r = 0, g = 0, b = 0, n = 0;
    for (const m of matches) {
      const c = parseColor(m);
      if (c) { r += c[0]; g += c[1]; b += c[2]; n++; }
    }
    return n ? [r / n, g / n, b / n] : null;
  }
  function bgFor(el) {
    let node = el;
    while (node) {
      const cs = getComputedStyle(node);
      const bc = parseColor(cs.backgroundColor);
      if (bc && bc[3] > 0.05) return [bc[0], bc[1], bc[2]];
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        const g = gradientColor(cs.backgroundImage);
        if (g) return g;
      }
      node = node.parentElement;
    }
    return [255, 255, 255];
  }

  const contrastFailures = [];
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const text = n.textContent.trim();
    if (!text) continue;
    const el = n.parentElement;
    if (!el) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    if (cs.webkitBackgroundClip === 'text' || cs.backgroundClip === 'text') continue;
    const fg = parseColor(cs.color);
    if (!fg) continue;
    const bg = bgFor(el);
    const l1 = relLum(fg), l2 = relLum(bg);
    const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
    const ratio = (hi + 0.05) / (lo + 0.05);
    if (ratio < 4.5) {
      const key = `${el.tagName}|${el.className}|${cs.color}|${bg.join(',')}`;
      if (seen.has(key)) continue;
      seen.add(key);
      contrastFailures.push({
        tag: el.tagName,
        cls: el.className || '',
        text: text.slice(0, 60),
        fg: cs.color,
        bg: `rgb(${bg.map(Math.round).join(',')})`,
        ratio: +ratio.toFixed(2),
      });
    }
  }

  const inlineHexEls = [...document.querySelectorAll('[style]')].filter((el) =>
    /#[0-9a-fA-F]{3,8}\b/.test(el.getAttribute('style') || '')
  );
  const inlineImportantEls = [...document.querySelectorAll('[style]')].filter((el) =>
    /!important/i.test(el.getAttribute('style') || '')
  );

  const h1s = [...document.querySelectorAll('h1')].filter((el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
  });

  return {
    contrastFailures,
    inlineHexCount: inlineHexEls.length,
    inlineHexSample: inlineHexEls.slice(0, 5).map((el) => el.getAttribute('style').slice(0, 120)),
    inlineImportantCount: inlineImportantEls.length,
    visibleH1Count: h1s.length,
  };
}

async function main() {
  if (wantScreenshots) mkdirSync(screenshotDir, { recursive: true });
  const browser = await chromium.launch();
  const results = [];

  for (const routePath of config.routes) {
    for (const vp of config.viewports) {
      const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
      const url = `${baseUrl}${routePath}`;
      let navError = null;
      try {
        await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
      } catch (e) {
        navError = e.message;
      }
      let report = null;
      if (!navError) {
        report = await page.evaluate(pageEvalFn);
        if (wantScreenshots) {
          const safeName = `${routePath.replace(/[^a-z0-9]+/gi, '_') || 'root'}_${vp.name}.png`;
          await page.screenshot({ path: path.join(screenshotDir, safeName), fullPage: true }).catch(() => {});
        }
      }
      results.push({ route: routePath, viewport: vp.name, navError, report });
      await page.close();
    }
  }
  await browser.close();

  let failCount = 0;
  console.log(`\nui-contrast gate — base: ${baseUrl}\n`);
  for (const r of results) {
    if (r.navError) {
      failCount++;
      console.log(`FAIL  ${r.route} [${r.viewport}] — navigation error: ${r.navError}`);
      continue;
    }
    const { contrastFailures, inlineHexCount, inlineImportantCount, visibleH1Count } = r.report;
    const problems = [];
    if (contrastFailures.length) problems.push(`${contrastFailures.length} low-contrast text node(s)`);
    if (inlineHexCount) problems.push(`${inlineHexCount} inline hex color(s)`);
    if (inlineImportantCount) problems.push(`${inlineImportantCount} inline !important`);
    if (visibleH1Count !== 1) problems.push(`${visibleH1Count} visible <h1> (want exactly 1)`);
    if (problems.length) {
      failCount++;
      console.log(`FAIL  ${r.route} [${r.viewport}] — ${problems.join(', ')}`);
      for (const f of contrastFailures) {
        console.log(`        ${f.tag}.${f.cls || '(no class)'} "${f.text}" fg=${f.fg} bg=${f.bg} ratio=${f.ratio}`);
      }
    } else {
      console.log(`PASS  ${r.route} [${r.viewport}]`);
    }
  }
  console.log(`\n${results.length - failCount}/${results.length} route x viewport checks passed.`);
  if (failCount > 0) process.exitCode = 1;
}

main();

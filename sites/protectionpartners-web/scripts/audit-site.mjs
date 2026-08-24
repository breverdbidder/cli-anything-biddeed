#!/usr/bin/env node
// Design-bar audit, per the zonewise-web audit-site.mjs convention referenced
// in issue #19405: no horizontal overflow at 320/393/768/1440, no JS errors.
// Usage: node scripts/audit-site.mjs [baseUrl]  (defaults to http://localhost:4321)
import { chromium } from "playwright";

const baseUrl = process.argv[2] || "http://localhost:4321";
const viewports = [320, 393, 768, 1440];
const pages = [
  "/",
  "/get-a-quote",
  "/commercial-business-auto",
  "/personal-lines",
  "/about",
  "/client-service",
];

let failures = 0;

const browser = await chromium.launch();
const context = await browser.newContext();

for (const path of pages) {
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => pageErrors.push(err.message));

  const url = `${baseUrl}${path}`;
  const response = await page.goto(url, { waitUntil: "networkidle" });

  if (!response || response.status() >= 400) {
    console.error(`FAIL ${path}: HTTP ${response ? response.status() : "no response"}`);
    failures++;
  }

  for (const width of viewports) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(100);
    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      return doc.scrollWidth - doc.clientWidth;
    });
    if (overflow > 1) {
      console.error(`FAIL ${path} @ ${width}px: horizontal overflow of ${overflow}px`);
      failures++;
    } else {
      console.log(`OK   ${path} @ ${width}px: no horizontal overflow`);
    }
  }

  if (consoleErrors.length > 0) {
    console.error(`FAIL ${path}: ${consoleErrors.length} console error(s):\n  ${consoleErrors.join("\n  ")}`);
    failures++;
  }
  if (pageErrors.length > 0) {
    console.error(`FAIL ${path}: ${pageErrors.length} uncaught JS error(s):\n  ${pageErrors.join("\n  ")}`);
    failures++;
  }
  if (consoleErrors.length === 0 && pageErrors.length === 0) {
    console.log(`OK   ${path}: no JS errors`);
  }

  await page.close();
}

await browser.close();

if (failures > 0) {
  console.error(`\nAUDIT FAILED: ${failures} issue(s) found.`);
  process.exit(1);
}
console.log("\nAUDIT PASSED: no overflow, no JS errors across all pages/viewports.");

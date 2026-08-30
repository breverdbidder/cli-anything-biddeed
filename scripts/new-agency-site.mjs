#!/usr/bin/env node
// Agency site factory generator (issue #19600, Task 3).
//
// Takes an agency.config.json (validated against
// sites/_template-agency-web/agency.config.schema.json's required-field
// list) and a slug, and produces a new sites/<slug>-web/ Astro project by
// copying sites/_template-agency-web/ and stamping in the config. This is
// the ONLY supported way to start a new agency site -- hand-copying an
// existing sites/<slug>-web/ directory is the anti-pattern this script
// exists to eliminate (see the top-level README).
//
// Usage:
//   node scripts/new-agency-site.mjs --config agency-configs/acme.config.json --slug acme [--force]
//
// --force overwrites an existing sites/<slug>-web/ directory (used to
// re-point an already-generated site at an updated template/config, e.g.
// regenerating sites/protectionpartners-web/ in this same issue).
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync, rmSync, cpSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const TEMPLATE_DIR = path.join(REPO_ROOT, "sites", "_template-agency-web");
const SCHEMA_PATH = path.join(TEMPLATE_DIR, "agency.config.schema.json");

function parseArgs(argv) {
  const out = { force: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--config") out.config = argv[++i];
    else if (argv[i] === "--slug") out.slug = argv[++i];
    else if (argv[i] === "--force") out.force = true;
  }
  return out;
}

function fail(msg) {
  console.error(`[new-agency-site] ERROR: ${msg}`);
  process.exit(1);
}

function validateConfig(config, schema) {
  const errors = [];
  for (const field of schema.required || []) {
    if (config[field] === undefined || config[field] === null) {
      errors.push(`missing required field: ${field}`);
    }
  }
  if (config.slug && !/^[a-z0-9-]+$/.test(config.slug)) {
    errors.push(`config.slug "${config.slug}" must match ^[a-z0-9-]+$`);
  }
  if (Array.isArray(config.lines_of_business)) {
    for (const line of config.lines_of_business) {
      for (const field of ["slug", "nav_label", "page_title", "meta_description", "eyebrow", "h1", "intro", "coverages", "final_cta_heading", "final_cta_text"]) {
        if (line[field] === undefined || line[field] === null) {
          errors.push(`lines_of_business[${line.slug || "?"}] missing required field: ${field}`);
        }
      }
    }
  }
  return errors;
}

const RESERVED_COPY_NAMES = new Set([
  "agency.config.schema.json",
  "_ci-template.yml",
  "node_modules",
  "dist",
  ".astro",
  ".wrangler",
  ".dev.vars",
]);

function copyTemplateTree(srcDir, destDir) {
  mkdirSync(destDir, { recursive: true });
  for (const entry of readdirSync(srcDir)) {
    if (RESERVED_COPY_NAMES.has(entry)) continue;
    const srcPath = path.join(srcDir, entry);
    const destPath = path.join(destDir, entry);
    const st = statSync(srcPath);
    if (st.isDirectory()) {
      copyTemplateTree(srcPath, destPath);
    } else {
      cpSync(srcPath, destPath);
    }
  }
}

function replaceInFile(filePath, replacements) {
  let content = readFileSync(filePath, "utf-8");
  for (const [token, value] of Object.entries(replacements)) {
    content = content.replaceAll(token, value);
  }
  writeFileSync(filePath, content);
}

function patchBrandOverrides(cssPath, brand) {
  if (!brand) return;
  const content = readFileSync(cssPath, "utf-8");
  const startMarker = "/* AGENCY_BRAND_OVERRIDES_START */";
  const endMarker = "/* AGENCY_BRAND_OVERRIDES_END */";
  const startIdx = content.indexOf(startMarker);
  const endIdx = content.indexOf(endMarker);
  if (startIdx === -1 || endIdx === -1) return;

  const keyToVar = {
    ink: "--color-ink",
    ink2: "--color-ink-2",
    brass: "--color-brass",
    brassLight: "--color-brass-light",
    paper: "--color-paper",
    paper2: "--color-paper-2",
    slate: "--color-slate",
    evergreen: "--color-evergreen",
    fontDisplay: "--font-display",
    fontSans: "--font-sans",
  };

  const before = content.slice(0, startIdx + startMarker.length);
  const after = content.slice(endIdx);
  const lines = Object.entries(brand)
    .filter(([k]) => keyToVar[k])
    .map(([k, v]) => `  ${keyToVar[k]}: ${v};`);
  const patched = `${before}\n${lines.join("\n")}\n  ${after}`;
  writeFileSync(cssPath, patched);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.config) fail("--config <path-to-agency.config.json> is required");
  if (!args.slug) fail("--slug <slug> is required");
  if (!/^[a-z0-9-]+$/.test(args.slug)) fail(`--slug "${args.slug}" must match ^[a-z0-9-]+$`);

  const configPath = path.resolve(process.cwd(), args.config);
  if (!existsSync(configPath)) fail(`config file not found: ${configPath}`);
  if (!existsSync(TEMPLATE_DIR)) fail(`template not found at ${TEMPLATE_DIR}`);

  const config = JSON.parse(readFileSync(configPath, "utf-8"));
  const schema = JSON.parse(readFileSync(SCHEMA_PATH, "utf-8"));
  const errors = validateConfig(config, schema);
  if (errors.length > 0) {
    fail(`config validation failed:\n  - ${errors.join("\n  - ")}`);
  }
  if (config.slug !== args.slug) {
    fail(`config.slug ("${config.slug}") does not match --slug ("${args.slug}") -- keep them in sync`);
  }

  const siteDir = path.join(REPO_ROOT, "sites", `${args.slug}-web`);
  if (existsSync(siteDir)) {
    if (!args.force) {
      fail(`sites/${args.slug}-web/ already exists. Pass --force to regenerate it from the template/config.`);
    }
    console.log(`[new-agency-site] --force set, removing existing sites/${args.slug}-web/`);
    rmSync(siteDir, { recursive: true, force: true });
  }

  console.log(`[new-agency-site] Generating sites/${args.slug}-web/ from ${path.relative(REPO_ROOT, TEMPLATE_DIR)}/ + ${path.relative(REPO_ROOT, configPath)}`);
  copyTemplateTree(TEMPLATE_DIR, siteDir);

  // Embed the config into the generated site so it builds standalone
  // (Cloudflare Pages only checks out the repo, it doesn't run this script).
  writeFileSync(path.join(siteDir, "agency.config.json"), JSON.stringify(config, null, 2) + "\n");

  const supabaseTable = config.supabase_table || `${args.slug.replace(/-/g, "_")}_intake`;
  const supabaseStorageBucket = config.supabase_storage_bucket || `${args.slug}-dec-uploads`;
  const wranglerName = `${args.slug}-web`;

  replaceInFile(path.join(siteDir, "package.json"), {
    __SLUG___WEB_PACKAGE_NAME_PLACEHOLDER__: wranglerName,
  });
  replaceInFile(path.join(siteDir, "wrangler.toml"), {
    __WRANGLER_NAME_PLACEHOLDER__: wranglerName,
    __SITE_DOMAIN_PLACEHOLDER__: config.domain.default,
    __SUPABASE_TABLE_PLACEHOLDER__: supabaseTable,
    __SUPABASE_STORAGE_BUCKET_PLACEHOLDER__: supabaseStorageBucket,
  });
  replaceInFile(path.join(siteDir, ".dev.vars.example"), {
    __SUPABASE_TABLE_PLACEHOLDER__: supabaseTable,
    __SUPABASE_STORAGE_BUCKET_PLACEHOLDER__: supabaseStorageBucket,
  });
  replaceInFile(path.join(siteDir, "README.md"), {
    __AGENCY_NAME_PLACEHOLDER__: config.agency_name,
    __SLUG_PLACEHOLDER__: args.slug,
  });

  patchBrandOverrides(path.join(siteDir, "src", "styles", "global.css"), config.brand);

  // CI workflow must live at the repo-root .github/workflows/ (GHA doesn't
  // discover workflows anywhere else) -- stamped from the template's
  // _ci-template.yml, one file per generated site, path-filtered to it.
  const ciTemplate = readFileSync(path.join(TEMPLATE_DIR, "_ci-template.yml"), "utf-8");
  const ciContent = ciTemplate
    .replaceAll("__AGENCY_NAME_PLACEHOLDER__", config.agency_name)
    .replaceAll("__SLUG_PLACEHOLDER__", args.slug)
    .replaceAll("__SITE_DOMAIN_PLACEHOLDER__", config.domain.default);
  const workflowsDir = path.join(REPO_ROOT, ".github", "workflows");
  mkdirSync(workflowsDir, { recursive: true });
  writeFileSync(path.join(workflowsDir, `${args.slug}-web-ci.yml`), ciContent);

  console.log(`[new-agency-site] Done. sites/${args.slug}-web/ + .github/workflows/${args.slug}-web-ci.yml written.`);
  console.log(`[new-agency-site] Next: cd sites/${args.slug}-web && npm install && npm run build`);
  console.log(`[new-agency-site] Supabase table expected: public.${supabaseTable} (not created by this script -- write and apply a migration before go-live).`);
  console.log(`[new-agency-site] Supabase Storage bucket expected: ${supabaseStorageBucket} (not created by this script -- create it before go-live if the decUpload fallback is enabled).`);
}

main();

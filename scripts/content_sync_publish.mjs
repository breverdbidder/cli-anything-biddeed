#!/usr/bin/env node
// content-sync.yml (SPR-02, issue #19830): push to main touching content/**
// -> upsert into site.site_content (published=true) via
// public.upsert_site_content() (service_role only — see
// supabase/migrations/20260904a_spr02_site_content_rpc.sql).
//
// Usage: node scripts/content_sync_publish.mjs <file1.md> <file2.md> ...
// Prints one JSON line per file: {file, slug, ok, error?}. Exits non-zero
// if any file failed — content-sync.yml treats that as a workflow failure.
import { readFileSync } from 'node:fs';
import { parseAnswerAsset } from './lib/parse_answer_asset.mjs';

const SUPABASE_URL = process.env.SUPABASE_URL;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error('SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set');
  process.exit(1);
}

async function upsert(row) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/upsert_site_content`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
    },
    body: JSON.stringify({
      p_slug: row.slug,
      p_title: row.title,
      p_hero_copy: row.hero_copy,
      p_body_jsonb: row.body_jsonb,
      p_published: row.published,
    }),
  });
  if (!res.ok) throw new Error(`upsert_site_content ${res.status}: ${await res.text()}`);
  return res.json();
}

async function unpublish(slug) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/delete_site_content`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
    },
    body: JSON.stringify({ p_slug: slug }),
  });
  if (!res.ok) throw new Error(`delete_site_content ${res.status}: ${await res.text()}`);
}

async function main() {
  const args = process.argv.slice(2);
  const unpublishIdx = args.indexOf('--unpublish-slugs');
  if (unpublishIdx !== -1) {
    const slugs = args.slice(unpublishIdx + 1).filter(Boolean);
    let failed = 0;
    for (const slug of slugs) {
      try {
        await unpublish(slug);
        console.log(JSON.stringify({ slug, ok: true, action: 'unpublish' }));
      } catch (e) {
        failed++;
        console.log(JSON.stringify({ slug, ok: false, action: 'unpublish', error: String(e.message || e) }));
      }
    }
    if (failed) process.exit(1);
    return;
  }

  const files = args;
  if (!files.length) {
    console.error('no files given');
    process.exit(1);
  }
  let failed = 0;
  for (const file of files) {
    try {
      const raw = readFileSync(file, 'utf8');
      const row = parseAnswerAsset(raw, file);
      const result = await upsert(row);
      console.log(JSON.stringify({ file, slug: row.slug, ok: true, published: result.published }));
    } catch (e) {
      failed++;
      console.log(JSON.stringify({ file, ok: false, error: String(e.message || e) }));
    }
  }
  if (failed) process.exit(1);
}

main();

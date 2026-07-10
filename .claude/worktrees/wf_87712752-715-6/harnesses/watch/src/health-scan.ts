// Claude Watch — Health Scanner
// Walks CWD, classifies logic files, inserts into watch_health via Supabase REST
// Zero shell execution policy: no child_process, no execSync

import * as fs from "fs";
import * as path from "path";
import * as https from "https";
import { classifyFile, SKIP_DIRS } from "./utils/classify.js";
import { sha256 } from "./utils/hash.js";
import type { LogicFile, ScanType } from "./types.js";

const MAX_FILE_SIZE = 100 * 1024; // 100KB
const MAX_DEPTH = 4;
const PREVIEW_MAX = 500;

// Read env
const SCAN_TYPE = (process.env.SCAN_TYPE || "nightly") as ScanType;
const REPO_NAME = process.env.REPO_NAME || path.basename(process.cwd());
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
  console.error("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set");
  process.exit(1);
}

// Walk directory tree using only fs.readdirSync — no shell
function walkDir(
  dir: string,
  rootDir: string,
  depth: number,
  results: LogicFile[]
): void {
  if (depth > MAX_DEPTH) return;

  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return; // skip unreadable dirs
  }

  for (const entry of entries) {
    if (SKIP_DIRS.has(entry.name)) continue;

    const fullPath = path.join(dir, entry.name);
    const relativePath = path.relative(rootDir, fullPath);

    if (entry.isDirectory()) {
      walkDir(fullPath, rootDir, depth + 1, results);
    } else if (entry.isFile()) {
      processFile(fullPath, relativePath, results);
    }
  }
}

function processFile(
  fullPath: string,
  relativePath: string,
  results: LogicFile[]
): void {
  let stat: fs.Stats;
  try {
    stat = fs.statSync(fullPath);
  } catch {
    return;
  }

  // Skip files over 100KB
  if (stat.size > MAX_FILE_SIZE) return;

  let content: string;
  try {
    content = fs.readFileSync(fullPath, "utf8");
  } catch {
    return; // skip binary or unreadable files
  }

  const classification = classifyFile(relativePath, content);
  if (!classification) return;

  const lines = content.split("\n");
  const preview = content.slice(0, PREVIEW_MAX);

  results.push({
    filePath: relativePath,
    category: classification.category,
    importance: classification.importance,
    signals: classification.signals,
    contentHash: sha256(content),
    lineCount: lines.length,
    sizeBytes: stat.size,
    contentPreview: preview,
  });
}

// POST to Supabase REST via https module (no fetch, no axios)
function supabaseInsert(records: object[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const url = new URL(`${SUPABASE_URL}/rest/v1/watch_health`);
    const body = JSON.stringify(records);

    const options: https.RequestOptions = {
      method: "POST",
      hostname: url.hostname,
      path: url.pathname,
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(body),
        apikey: SUPABASE_SERVICE_KEY!,
        Authorization: `Bearer ${SUPABASE_SERVICE_KEY}`,
        Prefer: "return=minimal",
      },
    };

    const req = https.request(options, (res) => {
      const chunks: Buffer[] = [];
      res.on("data", (chunk: Buffer) => chunks.push(chunk));
      res.on("end", () => {
        const responseBody = Buffer.concat(chunks).toString();
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
          resolve();
        } else {
          reject(
            new Error(
              `Supabase insert failed: HTTP ${res.statusCode} — ${responseBody}`
            )
          );
        }
      });
    });

    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

async function main(): Promise<void> {
  const rootDir = process.cwd();
  console.log(`Scanning ${REPO_NAME} (${SCAN_TYPE}) in ${rootDir}...`);

  const files: LogicFile[] = [];
  walkDir(rootDir, rootDir, 0, files);

  if (files.length === 0) {
    console.log(`Scanned ${REPO_NAME}: 0 logic files found`);
    return;
  }

  const scannedAt = new Date().toISOString();

  // Build rows for Supabase
  const rows = files.map((f) => ({
    scanned_at: scannedAt,
    scan_type: SCAN_TYPE,
    repo: REPO_NAME,
    file_path: f.filePath,
    category: f.category,
    content_hash: f.contentHash,
    signals: f.signals,
    importance: f.importance,
    line_count: f.lineCount,
    size_bytes: f.sizeBytes,
    content_preview: f.contentPreview,
  }));

  // Batch insert in chunks of 50 to avoid payload limits
  const BATCH_SIZE = 50;
  for (let i = 0; i < rows.length; i += BATCH_SIZE) {
    const batch = rows.slice(i, i + BATCH_SIZE);
    await supabaseInsert(batch);
  }

  const critical = files.filter((f) => f.importance === "critical").length;
  const high = files.filter((f) => f.importance === "high").length;

  console.log(
    `Scanned ${REPO_NAME}: ${files.length} logic files (${critical} critical, ${high} high)`
  );
}

main().catch((err) => {
  console.error("health-scan failed:", err.message);
  process.exit(1);
});

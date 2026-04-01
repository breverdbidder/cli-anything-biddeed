#!/usr/bin/env node
/**
 * PreToolUse Hook: Pre-commit Quality Check
 *
 * Runs quality checks before git commit commands:
 * - Detects staged files
 * - Runs linter on staged files (if available)
 * - Checks for common issues (console.log, debugger, etc.)
 * - Detects hardcoded secrets (OpenAI, GitHub, AWS, Supabase JWT, Mapbox, DeepSeek, Exa, Firecrawl)
 * - Validates commit message format (if provided)
 *
 * Cross-platform (Windows, macOS, Linux)
 *
 * Exit codes:
 *   0 - Success (allow commit)
 *   2 - Block commit (quality issues found)
 *
 * Source: affaan-m/everything-claude-code (MIT) — extended for BidDeed.AI ecosystem
 */

const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const MAX_STDIN = 1024 * 1024; // 1MB limit

function getStagedFiles() {
  const result = spawnSync('git', ['diff', '--cached', '--name-only', '--diff-filter=ACMR'], {
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe']
  });
  if (result.status !== 0) return [];
  return result.stdout.trim().split('\n').filter(f => f.length > 0);
}

function getStagedFileContent(filePath) {
  const result = spawnSync('git', ['show', `:${filePath}`], {
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe']
  });
  if (result.status !== 0) return null;
  return result.stdout;
}

function shouldCheckFile(filePath) {
  const checkableExtensions = ['.js', '.jsx', '.ts', '.tsx', '.py', '.go', '.rs'];
  return checkableExtensions.some(ext => filePath.endsWith(ext));
}

function findFileIssues(filePath) {
  const issues = [];

  try {
    const content = getStagedFileContent(filePath);
    if (content == null) return issues;
    const lines = content.split('\n');

    lines.forEach((line, index) => {
      const lineNum = index + 1;

      // console.log check
      if (line.includes('console.log') && !line.trim().startsWith('//') && !line.trim().startsWith('*')) {
        issues.push({ type: 'console.log', message: `console.log found at line ${lineNum}`, line: lineNum, severity: 'warning' });
      }

      // debugger check
      if (/\bdebugger\b/.test(line) && !line.trim().startsWith('//')) {
        issues.push({ type: 'debugger', message: `debugger statement at line ${lineNum}`, line: lineNum, severity: 'error' });
      }

      // TODO/FIXME without issue ref
      const todoMatch = line.match(/\/\/\s*(TODO|FIXME):?\s*(.+)/);
      if (todoMatch && !todoMatch[2].match(/#\d+|issue/i)) {
        issues.push({ type: 'todo', message: `TODO/FIXME without issue reference at line ${lineNum}: "${todoMatch[2].trim()}"`, line: lineNum, severity: 'info' });
      }

      // ── Secret detection (BidDeed.AI extended patterns) ──────────────────
      const secretPatterns = [
        // Original ECC patterns
        { pattern: /sk-[a-zA-Z0-9]{20,}/, name: 'OpenAI/DeepSeek API key (sk-)' },
        { pattern: /ghp_[a-zA-Z0-9]{36}/, name: 'GitHub PAT (ghp_)' },
        { pattern: /AKIA[A-Z0-9]{16}/, name: 'AWS Access Key (AKIA)' },
        { pattern: /api[_-]?key\s*[=:]\s*['"][^'"]{8,}['"]/i, name: 'Generic API key assignment' },

        // BidDeed.AI ecosystem additions
        { pattern: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/, name: 'Supabase/JWT token (eyJ...)' },
        { pattern: /pk\.eyJ[A-Za-z0-9_-]{10,}/, name: 'Mapbox public token (pk.eyJ...)' },
        { pattern: /sk-[a-zA-Z0-9]{32,}/, name: 'DeepSeek API key (sk-)' },
        { pattern: /exa[_-]?[a-zA-Z0-9]{20,}/i, name: 'Exa API key' },
        { pattern: /fc-[a-zA-Z0-9]{20,}/, name: 'Firecrawl API key (fc-)' },
        { pattern: /sd_[a-zA-Z0-9]{20,}/, name: 'Supadata API key (sd_)' },
      ];

      for (const { pattern, name } of secretPatterns) {
        if (pattern.test(line)) {
          issues.push({
            type: 'secret',
            message: `Potential ${name} exposed at line ${lineNum}`,
            line: lineNum,
            severity: 'error'
          });
        }
      }
    });
  } catch {
    // File not readable, skip
  }

  return issues;
}

function validateCommitMessage(command) {
  const messageMatch = command.match(/(?:-m|--message)[=\s]+["']?([^"']+)["']?/);
  if (!messageMatch) return null;

  const message = messageMatch[1];
  const issues = [];

  const conventionalCommit = /^(feat|fix|docs|style|refactor|test|chore|build|ci|perf|revert)(\(.+\))?:\s*.+/;
  if (!conventionalCommit.test(message)) {
    issues.push({
      type: 'format',
      message: 'Commit message does not follow conventional commit format',
      suggestion: 'Use format: type(scope): description (e.g., "fix(auth): handle expired tokens")'
    });
  }

  if (message.length > 72) {
    issues.push({
      type: 'length',
      message: `Commit message too long (${message.length} chars, max 72)`,
      suggestion: 'Keep the first line under 72 characters'
    });
  }

  if (conventionalCommit.test(message)) {
    const afterColon = message.split(':')[1];
    if (afterColon && /^[A-Z]/.test(afterColon.trim())) {
      issues.push({
        type: 'capitalization',
        message: 'Subject should start with lowercase after type',
        suggestion: 'Use lowercase for the first letter of the subject'
      });
    }
  }

  if (message.endsWith('.')) {
    issues.push({
      type: 'punctuation',
      message: 'Commit message should not end with a period',
      suggestion: 'Remove the trailing period'
    });
  }

  return { message, issues };
}

function runLinter(files) {
  const jsFiles = files.filter(f => /\.(js|jsx|ts|tsx)$/.test(f));
  const pyFiles = files.filter(f => f.endsWith('.py'));
  const goFiles = files.filter(f => f.endsWith('.go'));
  const results = { eslint: null, pylint: null, golint: null };

  if (jsFiles.length > 0) {
    const eslintBin = process.platform === 'win32' ? 'eslint.cmd' : 'eslint';
    const eslintPath = path.join(process.cwd(), 'node_modules', '.bin', eslintBin);
    if (fs.existsSync(eslintPath)) {
      const result = spawnSync(eslintPath, ['--format', 'compact', ...jsFiles], {
        encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], timeout: 30000
      });
      results.eslint = { success: result.status === 0, output: result.stdout || result.stderr };
    }
  }

  if (pyFiles.length > 0) {
    try {
      const result = spawnSync('pylint', ['--output-format=text', ...pyFiles], {
        encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], timeout: 30000
      });
      if (!result.error || result.error.code !== 'ENOENT') {
        results.pylint = { success: result.status === 0, output: result.stdout || result.stderr };
      }
    } catch { /* not available */ }
  }

  if (goFiles.length > 0) {
    try {
      const result = spawnSync('golint', goFiles, {
        encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], timeout: 30000
      });
      if (!result.error || result.error.code !== 'ENOENT') {
        results.golint = { success: !result.stdout || result.stdout.trim() === '', output: result.stdout };
      }
    } catch { /* not available */ }
  }

  return results;
}

function evaluate(rawInput) {
  try {
    const input = JSON.parse(rawInput);
    const command = input.tool_input?.command || '';

    if (!command.includes('git commit')) {
      return { output: rawInput, exitCode: 0 };
    }

    if (command.includes('--amend')) {
      return { output: rawInput, exitCode: 0 };
    }

    const stagedFiles = getStagedFiles();

    if (stagedFiles.length === 0) {
      console.error('[Hook] No staged files found. Use "git add" to stage files first.');
      return { output: rawInput, exitCode: 0 };
    }

    console.error(`[Hook] Checking ${stagedFiles.length} staged file(s)...`);

    const filesToCheck = stagedFiles.filter(shouldCheckFile);
    let totalIssues = 0;
    let errorCount = 0;
    let warningCount = 0;
    let infoCount = 0;

    for (const file of filesToCheck) {
      const fileIssues = findFileIssues(file);
      if (fileIssues.length > 0) {
        console.error(`\n[FILE] ${file}`);
        for (const issue of fileIssues) {
          const label = issue.severity === 'error' ? 'ERROR' : issue.severity === 'warning' ? 'WARNING' : 'INFO';
          console.error(`  ${label} Line ${issue.line}: ${issue.message}`);
          totalIssues++;
          if (issue.severity === 'error') errorCount++;
          if (issue.severity === 'warning') warningCount++;
          if (issue.severity === 'info') infoCount++;
        }
      }
    }

    const messageValidation = validateCommitMessage(command);
    if (messageValidation && messageValidation.issues.length > 0) {
      console.error('\nCommit Message Issues:');
      for (const issue of messageValidation.issues) {
        console.error(`  WARNING ${issue.message}`);
        if (issue.suggestion) console.error(`     TIP ${issue.suggestion}`);
        totalIssues++;
        warningCount++;
      }
    }

    const lintResults = runLinter(filesToCheck);

    if (lintResults.eslint && !lintResults.eslint.success) {
      console.error('\nESLint Issues:\n' + lintResults.eslint.output);
      totalIssues++; errorCount++;
    }
    if (lintResults.pylint && !lintResults.pylint.success) {
      console.error('\nPylint Issues:\n' + lintResults.pylint.output);
      totalIssues++; errorCount++;
    }
    if (lintResults.golint && !lintResults.golint.success) {
      console.error('\ngolint Issues:\n' + lintResults.golint.output);
      totalIssues++; errorCount++;
    }

    if (totalIssues > 0) {
      console.error(`\nSummary: ${totalIssues} issue(s) found (${errorCount} error(s), ${warningCount} warning(s), ${infoCount} info)`);
      if (errorCount > 0) {
        console.error('\n[Hook] ERROR: Commit BLOCKED — secrets or critical issues detected. Fix before committing.');
        return { output: rawInput, exitCode: 2 };
      } else {
        console.error('\n[Hook] WARNING: Non-critical issues found. Commit allowed. Fix when possible.');
        console.error('[Hook] To bypass: git commit --no-verify');
      }
    } else {
      console.error('\n[Hook] PASS: All checks passed!');
    }
  } catch (error) {
    console.error(`[Hook] Error: ${error.message}`);
    // Fail-open: non-blocking on hook errors
  }

  return { output: rawInput, exitCode: 0 };
}

function run(rawInput) {
  return evaluate(rawInput).output;
}

if (require.main === module) {
  let data = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => {
    if (data.length < MAX_STDIN) {
      const remaining = MAX_STDIN - data.length;
      data += chunk.substring(0, remaining);
    }
  });
  process.stdin.on('end', () => {
    const result = evaluate(data);
    process.stdout.write(result.output);
    process.exit(result.exitCode);
  });
}

module.exports = { run, evaluate };

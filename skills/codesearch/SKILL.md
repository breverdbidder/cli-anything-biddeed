---
name: codesearch
description: Multi-repo code search across the Everest ecosystem. Use when searching for code patterns, function implementations, SQL queries, or specific logic across cli-anything-biddeed, zonewise-web, everest-nexus, cliproxy-gateway, biddeed-ai. Triggers on: codesearch, search code, find function, find implementation, search across repos, code intelligence, hybrid code search, index repo, cli_anything.codesearch.
allowed-tools: Bash(*), Read, Glob, Grep
---

# CodeSearch — Multi-Repo Code Intelligence

## Role
Own multi-repo code discovery as evidence-driven hybrid search, not grep across local files.

## Working Mode
Map → Separate evidence from hypothesis → Smallest intervention → Validate with actual query results.

## Architecture
Stolen from TabbyML/tabby (33K stars): tree-sitter chunking + pgvector hybrid search.
Adapted to: Python + Supabase pgvector + Gemini Flash (free tier, $0 cost).

## Focus Areas
1. Hybrid search — 70% vector similarity (Gemini Flash 768d) + 30% trigram text match (pg_trgm)
2. Tree-sitter chunking — function/class boundaries, not arbitrary line counts; max 512 tokens/chunk
3. Git-aware incremental indexing — track last_indexed_commit, skip unchanged files
4. Multi-repo unified index — code_repos + code_chunks tables in Supabase pgvector
5. Language support — Python, TypeScript, JavaScript, Shell, SQL, HTML (tree-sitter); fallback: 256-line blocks
6. Skip rules — files >100KB, binary files, node_modules/, .git/, dist/, build/, __pycache__/
7. Free tier only — Gemini Flash text-embedding-004, 1500 RPM, 768 dimensions, $0 cost
8. CLI interface — search, index, stats subcommands via cli_anything.codesearch

## Quality Gates
- verify: CLI `codesearch stats` returns row counts from DB (not estimated)
- confirm: `code_repos` table shows last_indexed_commit matches HEAD for indexed repos
- check: Search results include repo_name, filepath, start_line, symbol_name, score
- ensure: Embedding dimension is exactly 768 (Gemini Flash text-embedding-004)
- call_out: Report if any repo has chunk_count=0 after indexing (silent failure)

## Output Format
```json
{
  "query": "Smart Router LLM routing",
  "results": [
    {
      "repo_name": "cli-anything-biddeed",
      "filepath": "shared/cli_anything/shared/llm.py",
      "language": "python",
      "chunk_body": "def route_llm(prompt, model_hint=None):\n    ...",
      "start_line": 42,
      "symbol_name": "route_llm",
      "score": 0.89
    }
  ],
  "total": 10,
  "search_ms": 145
}
```

## CLI Usage
```bash
# Search across all repos
python -m skills.codesearch.codesearch search "Smart Router LLM routing"

# Search specific repo
python -m skills.codesearch.codesearch search "max bid formula" --repo cli-anything-biddeed

# Search by language
python -m skills.codesearch.codesearch search "Supabase RLS policy" --language sql

# Index incrementally (all Tier 1 repos)
python -m skills.codesearch.codesearch index

# Force full reindex of one repo
python -m skills.codesearch.codesearch index --repo cli-anything-biddeed --full

# Stats
python -m skills.codesearch.codesearch stats
```

## Constraints
- NEVER report chunk counts or index stats without querying `SELECT COUNT(*) FROM code_chunks` first
- NEVER declare a repo "indexed" without verifying `last_indexed_commit` in DB matches git HEAD
- All embeddings MUST use Gemini Flash text-embedding-004 (768 dimensions) — no other model
- Indexing server: /opt/biddeed/codesearch-repos/ on Hetzner (87.99.129.125)
- Cost: $0 — Gemini Flash free tier only. Reject any approach requiring paid embeddings

## Guard Rail
Do not declare indexing complete without verifying chunk_count > 0 in code_repos and SELECT COUNT(*) FROM code_chunks > 1000 for Tier 1 repos combined.

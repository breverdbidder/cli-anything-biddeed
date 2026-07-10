# CODESEARCH — Multi-Repo Code Intelligence
# Stolen from: TabbyML/tabby (33K stars) tabby-crawler + tabby-index crates
# Adapted: Rust/Tantivy → Python/Supabase for Everest ecosystem
# Date: 2026-03-29
# Author: Claude AI Architect
# Executor: Claude Code via SUMMIT

---

## WHAT WE'RE STEALING

From Tabby's architecture:
1. **Tree-sitter code chunking** — split files at function/class boundaries (not arbitrary line counts)
2. **Embedding + keyword hybrid search** — vector similarity AND text matching combined
3. **Git-aware incremental indexing** — track last-indexed commit, only re-index changed files
4. **Multi-repo unified index** — search across all repos from one query

Adapted to our stack: Python + Supabase pgvector + Gemini Flash embeddings + cli-anything CLI

---

## ARCHITECTURE

```
github repos (100) → git clone/pull → tree-sitter chunk → embed (Gemini Flash) → Supabase pgvector
                                                                                        ↓
                                              CLI query → hybrid search (vector + trgm) → ranked results
```

### Supabase Schema

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Track indexed repos
CREATE TABLE code_repos (
  id SERIAL PRIMARY KEY,
  repo_name TEXT UNIQUE NOT NULL,
  last_indexed_commit TEXT,
  last_indexed_at TIMESTAMPTZ,
  file_count INT DEFAULT 0,
  chunk_count INT DEFAULT 0,
  total_tokens INT DEFAULT 0,
  language_breakdown JSONB DEFAULT '{}'
);

-- Code chunks with embeddings
CREATE TABLE code_chunks (
  id SERIAL PRIMARY KEY,
  repo_name TEXT NOT NULL,
  filepath TEXT NOT NULL,
  language TEXT NOT NULL,
  chunk_body TEXT NOT NULL,
  start_line INT,
  end_line INT,
  chunk_type TEXT, -- 'function', 'class', 'module', 'block'
  symbol_name TEXT, -- function/class name if applicable
  commit_sha TEXT NOT NULL,
  embedding vector(768), -- Gemini Flash embedding dimension
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(repo_name, filepath, start_line, commit_sha)
);

-- Indexes for hybrid search
CREATE INDEX idx_chunks_embedding ON code_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_chunks_body_trgm ON code_chunks USING gin (chunk_body gin_trgm_ops);
CREATE INDEX idx_chunks_repo ON code_chunks (repo_name);
CREATE INDEX idx_chunks_filepath ON code_chunks (filepath);
CREATE INDEX idx_chunks_language ON code_chunks (language);
CREATE INDEX idx_chunks_symbol ON code_chunks (symbol_name);

-- Hybrid search function
CREATE OR REPLACE FUNCTION hybrid_code_search(
  query_text TEXT,
  query_embedding vector(768),
  match_count INT DEFAULT 10,
  vector_weight FLOAT DEFAULT 0.7,
  text_weight FLOAT DEFAULT 0.3,
  filter_repo TEXT DEFAULT NULL,
  filter_language TEXT DEFAULT NULL
)
RETURNS TABLE (
  id INT,
  repo_name TEXT,
  filepath TEXT,
  language TEXT,
  chunk_body TEXT,
  start_line INT,
  symbol_name TEXT,
  score FLOAT
) AS $$
  WITH vector_results AS (
    SELECT id, 1 - (embedding <=> query_embedding) AS vector_score
    FROM code_chunks
    WHERE (filter_repo IS NULL OR code_chunks.repo_name = filter_repo)
      AND (filter_language IS NULL OR code_chunks.language = filter_language)
    ORDER BY embedding <=> query_embedding
    LIMIT match_count * 3
  ),
  text_results AS (
    SELECT id, similarity(chunk_body, query_text) AS text_score
    FROM code_chunks
    WHERE chunk_body % query_text
      AND (filter_repo IS NULL OR code_chunks.repo_name = filter_repo)
      AND (filter_language IS NULL OR code_chunks.language = filter_language)
    LIMIT match_count * 3
  ),
  combined AS (
    SELECT
      COALESCE(v.id, t.id) AS id,
      COALESCE(v.vector_score, 0) * vector_weight +
      COALESCE(t.text_score, 0) * text_weight AS combined_score
    FROM vector_results v
    FULL OUTER JOIN text_results t ON v.id = t.id
    ORDER BY combined_score DESC
    LIMIT match_count
  )
  SELECT
    c.id, c.repo_name, c.filepath, c.language,
    c.chunk_body, c.start_line, c.symbol_name,
    combined.combined_score AS score
  FROM combined
  JOIN code_chunks c ON c.id = combined.id
  ORDER BY combined.combined_score DESC;
$$ LANGUAGE sql;
```

### Core Repos to Index (Priority Tier)

**Tier 1 — Active development (index first):**
- cli-anything-biddeed (Python, 40MB)
- zonewise-web (TypeScript, 6MB)
- everest-nexus (Python)
- cliproxy-gateway (Shell)
- biddeed-ai (HTML/JS)

**Tier 2 — Supporting repos:**
- zonewise (Python)
- zonewise-desktop (TypeScript)
- brevard-bidder-landing (Python)
- biddeed-ai-ui (TypeScript)
- zonewise-agents (Python)

**Tier 3 — Skip (forks, dead, huge):**
- All repos >50MB that are forks (ChatDev, trivy, escrcpy, MiniCPM-o, etc)
- All repos with no language detected and last update >30 days ago

### Python Implementation

**File: `skills/codesearch/codesearch.py`**

Dependencies:
```
tree-sitter==0.24.0
tree-sitter-languages==1.10.2
supabase-py
httpx
```

Core pipeline:
1. `clone_or_pull(repo_name)` — shallow clone or fetch+pull
2. `detect_changed_files(repo_name, last_commit)` — git diff against stored commit
3. `chunk_file(filepath, language)` — tree-sitter parse → extract functions/classes/blocks → 512-token max chunks
4. `embed_chunks(chunks)` — batch embed via Gemini Flash (free tier, 1500 RPM)
5. `upsert_chunks(chunks)` — delete old chunks for changed files, insert new
6. `update_repo_state(repo_name, commit, stats)` — track progress

**File: `skills/codesearch/SKILL.md`**

CLI interface:
```bash
# Search across all repos
cli_anything.codesearch search "Smart Router LLM routing"

# Search specific repo
cli_anything.codesearch search "max bid formula" --repo cli-anything-biddeed

# Search by language
cli_anything.codesearch search "Supabase RLS policy" --language sql

# Index/reindex
cli_anything.codesearch index              # incremental all repos
cli_anything.codesearch index --repo X     # single repo
cli_anything.codesearch index --full       # force full reindex

# Stats
cli_anything.codesearch stats
```

### LLM Cost: $0

- Gemini Flash free tier: 1500 RPM, embedding dimension 768
- Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent`
- Key: use existing Gemini API key from CLIProxyAPI
- Estimated initial index: ~10K chunks across Tier 1+2 repos = ~10K embedding calls = well within free tier

### Cron Schedule

- **Nightly 3AM EST**: Incremental index of Tier 1 repos (via autoloop.yml or dedicated workflow)
- **Weekly Sunday 4AM**: Full reindex of Tier 1+2 repos
- GHA workflow: `codesearch-index.yml`

### CLIProxyAPI Endpoint

Add to CLIProxyAPI at 87.99.129.125:8317:
```
POST /codesearch
Body: {"query": "...", "repo": null, "language": null, "limit": 10}
Response: [{repo, filepath, chunk_body, start_line, symbol_name, score}]
```

This lets Claude Code sessions query the index mid-session without loading full repos.

---

## DEFINITION OF DONE

- [ ] `code_repos` and `code_chunks` tables created in Supabase
- [ ] `hybrid_code_search` function returns results
- [ ] Tier 1 repos (5) indexed with >1000 chunks total
- [ ] `cli_anything.codesearch search "Smart Router"` returns relevant code
- [ ] `cli_anything.codesearch stats` shows indexed repo count and chunk count
- [ ] CLIProxyAPI `/codesearch` endpoint responds
- [ ] GHA workflow `codesearch-index.yml` runs successfully
- [ ] All results VERIFIED with actual queries, not assumed working

## EXECUTION NOTES

- Use Gemini API key already in CLIProxyAPI secrets (GEMINI_API_KEY)
- Supabase creds from SUPABASE_CREDENTIALS.md in brevard-bidder-scraper
- Clone repos to /opt/biddeed/codesearch-repos/ on Hetzner
- Skip files >100KB, skip binary files, skip node_modules/.git/dist/build
- Tree-sitter fallback: if language not supported, use basic line-based chunking (256 lines)
- Max 50 iterations for AUTOLOOP compatibility

-- Migration: CodeSearch — Multi-Repo Code Intelligence
-- Date: 2026-03-29
-- Issue: breverdbidder/cli-anything-biddeed#19
-- Spec: specs/CODESEARCH-SPEC.md
-- Stolen from: TabbyML/tabby (33K stars) tabby-crawler + tabby-index
-- Adapted: Rust/Tantivy → Python/Supabase pgvector

-- ============================================================
-- 1. Enable required extensions
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- 2. code_repos — track indexed repositories
-- ============================================================

CREATE TABLE IF NOT EXISTS code_repos (
  id SERIAL PRIMARY KEY,
  repo_name TEXT UNIQUE NOT NULL,
  repo_url TEXT,
  last_indexed_commit TEXT,
  last_indexed_at TIMESTAMPTZ,
  file_count INT DEFAULT 0,
  chunk_count INT DEFAULT 0,
  total_tokens INT DEFAULT 0,
  language_breakdown JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE code_repos IS 'Tracks indexed git repositories for CodeSearch. One row per repo.';

-- ============================================================
-- 3. code_chunks — code segments with embeddings
-- ============================================================

CREATE TABLE IF NOT EXISTS code_chunks (
  id SERIAL PRIMARY KEY,
  repo_name TEXT NOT NULL REFERENCES code_repos(repo_name) ON DELETE CASCADE,
  filepath TEXT NOT NULL,
  language TEXT NOT NULL,
  chunk_body TEXT NOT NULL,
  start_line INT,
  end_line INT,
  chunk_type TEXT CHECK (chunk_type IN ('function', 'class', 'module', 'block', 'line')),
  symbol_name TEXT,
  commit_sha TEXT NOT NULL,
  embedding vector(768),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(repo_name, filepath, start_line, commit_sha)
);

COMMENT ON TABLE code_chunks IS 'Code segments with Gemini Flash embeddings (768d) for hybrid search.';
COMMENT ON COLUMN code_chunks.chunk_type IS 'function|class|module|block|line — tree-sitter or fallback chunking';
COMMENT ON COLUMN code_chunks.embedding IS 'Gemini Flash text-embedding-004, 768 dimensions, free tier';

-- ============================================================
-- 4. Indexes for hybrid search performance
-- ============================================================

-- IVFFlat index for vector similarity (cosine distance)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
  ON code_chunks USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- Trigram index for text search
CREATE INDEX IF NOT EXISTS idx_chunks_body_trgm
  ON code_chunks USING gin (chunk_body gin_trgm_ops);

-- Standard btree indexes for filtering
CREATE INDEX IF NOT EXISTS idx_chunks_repo ON code_chunks (repo_name);
CREATE INDEX IF NOT EXISTS idx_chunks_filepath ON code_chunks (filepath);
CREATE INDEX IF NOT EXISTS idx_chunks_language ON code_chunks (language);
CREATE INDEX IF NOT EXISTS idx_chunks_symbol ON code_chunks (symbol_name);
CREATE INDEX IF NOT EXISTS idx_chunks_commit ON code_chunks (commit_sha);

-- ============================================================
-- 5. hybrid_code_search function (Tabby-inspired)
-- ============================================================

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
    SELECT c.id, 1 - (c.embedding <=> query_embedding) AS vector_score
    FROM code_chunks c
    WHERE c.embedding IS NOT NULL
      AND (filter_repo IS NULL OR c.repo_name = filter_repo)
      AND (filter_language IS NULL OR c.language = filter_language)
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count * 3
  ),
  text_results AS (
    SELECT c.id, similarity(c.chunk_body, query_text) AS text_score
    FROM code_chunks c
    WHERE c.chunk_body % query_text
      AND (filter_repo IS NULL OR c.repo_name = filter_repo)
      AND (filter_language IS NULL OR c.language = filter_language)
    LIMIT match_count * 3
  ),
  combined AS (
    SELECT
      COALESCE(v.id, t.id) AS id,
      COALESCE(v.vector_score, 0.0) * vector_weight +
      COALESCE(t.text_score, 0.0) * text_weight AS combined_score
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
$$ LANGUAGE sql STABLE;

COMMENT ON FUNCTION hybrid_code_search IS
  'Tabby-inspired hybrid search: 70% vector similarity + 30% trigram text match. '
  'Filters by repo and/or language. Returns ranked code chunks.';

-- ============================================================
-- 6. RLS policies (service role full access)
-- ============================================================

ALTER TABLE code_repos ENABLE ROW LEVEL SECURITY;
ALTER TABLE code_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_full_access_repos" ON code_repos
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_full_access_chunks" ON code_chunks
  FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- 7. Verification query (run after migration)
-- ============================================================

-- SELECT
--   'code_repos' AS tbl, COUNT(*) AS rows FROM code_repos
-- UNION ALL
--   SELECT 'code_chunks', COUNT(*) FROM code_chunks;

-- Expected: both tables exist with 0 rows (empty — indexing happens via GHA)

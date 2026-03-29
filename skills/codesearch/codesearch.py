#!/usr/bin/env python3
"""
CodeSearch — Multi-Repo Code Intelligence
Stolen from TabbyML/tabby: tree-sitter chunking + pgvector hybrid search
Adapted: Rust/Tantivy → Python/Supabase pgvector + Gemini Flash
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import click
import httpx

# ============================================================
# Config
# ============================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
REPOS_DIR = Path(os.environ.get("CODESEARCH_REPOS_DIR", "/opt/biddeed/codesearch-repos"))
EMBEDDING_DIM = 768
MAX_CHUNK_TOKENS = 512
MAX_FILE_BYTES = 100_000  # 100KB

TIER1_REPOS = [
    ("cli-anything-biddeed", "https://github.com/breverdbidder/cli-anything-biddeed"),
    ("zonewise-web", "https://github.com/breverdbidder/zonewise-web"),
    ("everest-nexus", "https://github.com/breverdbidder/everest-nexus"),
    ("cliproxy-gateway", "https://github.com/breverdbidder/cliproxy-gateway"),
    ("biddeed-ai", "https://github.com/breverdbidder/biddeed-ai"),
]

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__",
    ".next", ".nuxt", "vendor", ".venv", "venv", "env",
}
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".zip", ".tar", ".gz", ".lock",
}
LANGUAGE_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}


# ============================================================
# Supabase client (lightweight, no SDK dependency)
# ============================================================
class SupabaseClient:
    def __init__(self):
        if not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY not set")
        self.base = SUPABASE_URL.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

    def select(self, table: str, params: dict = None) -> list:
        r = httpx.get(f"{self.base}/{table}", headers={**self.headers, "Prefer": "return=representation"}, params=params or {})
        r.raise_for_status()
        return r.json()

    def upsert(self, table: str, records: list, on_conflict: str = None) -> None:
        headers = {**self.headers, "Prefer": f"resolution=merge-duplicates,return=minimal"}
        r = httpx.post(f"{self.base}/{table}", headers=headers, json=records, timeout=30)
        r.raise_for_status()

    def delete(self, table: str, params: dict) -> None:
        r = httpx.delete(f"{self.base}/{table}", headers=self.headers, params=params)
        r.raise_for_status()

    def rpc(self, func: str, body: dict) -> list:
        r = httpx.post(
            f"{SUPABASE_URL}/rest/v1/rpc/{func}",
            headers={**self.headers, "Prefer": "return=representation"},
            json=body,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()


# ============================================================
# Gemini Flash embeddings (free tier, $0 cost)
# ============================================================
def embed_text(text: str) -> list[float]:
    """Single embed via Gemini Flash text-embedding-004 (768d, free tier)."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    r = httpx.post(
        f"{GEMINI_EMBED_URL}?key={GEMINI_API_KEY}",
        json={"model": "models/text-embedding-004", "content": {"parts": [{"text": text[:8000]}]}},
        timeout=15,
    )
    r.raise_for_status()
    values = r.json()["embedding"]["values"]
    assert len(values) == EMBEDDING_DIM, f"Expected {EMBEDDING_DIM}d, got {len(values)}d"
    return values


def embed_batch(texts: list[str], delay_ms: int = 50) -> list[list[float]]:
    """Batch embed with rate limiting (1500 RPM = 25 RPS → 40ms min gap)."""
    results = []
    for i, text in enumerate(texts):
        if i > 0:
            time.sleep(delay_ms / 1000)
        results.append(embed_text(text))
    return results


# ============================================================
# Tree-sitter chunking
# ============================================================
def chunk_file(filepath: Path, language: str) -> list[dict]:
    """
    Chunk a file into code segments. Attempts tree-sitter for Python/TS/JS,
    falls back to 256-line blocks for unsupported languages.
    """
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    if len(content.encode()) > MAX_FILE_BYTES:
        return []

    chunks = []
    lines = content.splitlines()

    if language in ("python", "typescript", "javascript"):
        chunks = _chunk_treesitter(content, lines, language, str(filepath))

    if not chunks:
        # Fallback: 256-line blocks
        chunks = _chunk_lines(lines, str(filepath), language)

    return chunks


def _chunk_treesitter(content: str, lines: list[str], language: str, filepath: str) -> list[dict]:
    """Tree-sitter chunking — extract function/class boundaries."""
    try:
        from tree_sitter_languages import get_language, get_parser
        lang = get_language(language)
        parser = get_parser(language)
        tree = parser.parse(content.encode())

        chunks = []
        node_types = {
            "python": ["function_definition", "class_definition", "decorated_definition"],
            "typescript": ["function_declaration", "class_declaration", "method_definition",
                           "arrow_function", "function_expression"],
            "javascript": ["function_declaration", "class_declaration", "method_definition",
                           "arrow_function", "function_expression"],
        }.get(language, [])

        def walk(node):
            if node.type in node_types:
                start = node.start_point[0]
                end = node.end_point[0]
                body = "\n".join(lines[start:end + 1])
                # Trim to MAX_CHUNK_TOKENS (approx 4 chars/token)
                if len(body) > MAX_CHUNK_TOKENS * 4:
                    body = body[:MAX_CHUNK_TOKENS * 4]

                # Extract symbol name
                symbol = None
                for child in node.children:
                    if child.type in ("identifier", "name"):
                        symbol = content[child.start_byte:child.end_byte]
                        break

                chunk_type = "function" if "function" in node.type else "class"
                chunks.append({
                    "filepath": filepath,
                    "chunk_body": body,
                    "start_line": start + 1,
                    "end_line": end + 1,
                    "chunk_type": chunk_type,
                    "symbol_name": symbol,
                    "language": language,
                })

            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return chunks

    except Exception:
        return []


def _chunk_lines(lines: list[str], filepath: str, language: str, block_size: int = 256) -> list[dict]:
    """Fallback: split file into fixed-size line blocks."""
    chunks = []
    for i in range(0, len(lines), block_size):
        block = lines[i:i + block_size]
        body = "\n".join(block)
        if body.strip():
            chunks.append({
                "filepath": filepath,
                "chunk_body": body[:MAX_CHUNK_TOKENS * 4],
                "start_line": i + 1,
                "end_line": min(i + block_size, len(lines)),
                "chunk_type": "block",
                "symbol_name": None,
                "language": language,
            })
    return chunks


# ============================================================
# Git operations
# ============================================================
def get_head_commit(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def clone_or_pull(repo_name: str, repo_url: str) -> Optional[Path]:
    """Clone repo or pull latest if already cloned."""
    repo_path = REPOS_DIR / repo_name
    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    if repo_path.exists():
        result = subprocess.run(
            ["git", "-C", str(repo_path), "pull", "--ff-only"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            click.echo(f"  WARN: git pull failed for {repo_name}: {result.stderr[:100]}")
    else:
        result = subprocess.run(
            ["git", "clone", "--depth=1", repo_url, str(repo_path)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            click.echo(f"  ERROR: git clone failed for {repo_name}: {result.stderr[:100]}")
            return None

    return repo_path


def get_changed_files(repo_path: Path, since_commit: Optional[str]) -> list[Path]:
    """Return changed files since last indexed commit, or all files if first index."""
    if not since_commit:
        return list_indexable_files(repo_path)

    result = subprocess.run(
        ["git", "-C", str(repo_path), "diff", "--name-only", since_commit, "HEAD"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return list_indexable_files(repo_path)

    changed = []
    for line in result.stdout.splitlines():
        p = repo_path / line.strip()
        if p.exists() and p.suffix in LANGUAGE_MAP:
            changed.append(p)
    return changed


def list_indexable_files(repo_path: Path) -> list[Path]:
    """List all indexable files in a repo."""
    files = []
    for p in repo_path.rglob("*"):
        if p.is_file() and p.suffix in LANGUAGE_MAP:
            parts = set(p.parts)
            if not parts.intersection(SKIP_DIRS) and p.suffix not in SKIP_EXTENSIONS:
                if p.stat().st_size <= MAX_FILE_BYTES:
                    files.append(p)
    return files


# ============================================================
# Core indexing pipeline
# ============================================================
def index_repo(db: SupabaseClient, repo_name: str, repo_url: str, full: bool = False) -> dict:
    """Full indexing pipeline for one repo."""
    click.echo(f"\n→ Indexing {repo_name}...")

    # 1. Clone or pull
    repo_path = clone_or_pull(repo_name, repo_url)
    if not repo_path:
        return {"repo_name": repo_name, "error": "clone/pull failed"}

    head_commit = get_head_commit(repo_path)
    if not head_commit:
        return {"repo_name": repo_name, "error": "could not get HEAD commit"}

    # 2. Check if up-to-date
    existing = db.select("code_repos", {"repo_name": f"eq.{repo_name}", "select": "last_indexed_commit"})
    last_commit = existing[0]["last_indexed_commit"] if existing else None

    if not full and last_commit == head_commit:
        click.echo(f"  SKIP: {repo_name} already up-to-date at {head_commit[:8]}")
        return {"repo_name": repo_name, "status": "up_to_date", "commit": head_commit}

    # 3. Find changed files
    files = get_changed_files(repo_path, last_commit if not full else None)
    click.echo(f"  Files to process: {len(files)}")

    if not files:
        click.echo(f"  No indexable files found")
        return {"repo_name": repo_name, "status": "no_files", "commit": head_commit}

    # 4. Chunk files
    all_chunks = []
    for f in files:
        lang = LANGUAGE_MAP.get(f.suffix, "text")
        chunks = chunk_file(f, lang)
        relative = str(f.relative_to(repo_path))
        for c in chunks:
            c["filepath"] = relative
            c["repo_name"] = repo_name
            c["commit_sha"] = head_commit
        all_chunks.extend(chunks)

    click.echo(f"  Chunks generated: {len(all_chunks)}")

    if not all_chunks:
        return {"repo_name": repo_name, "status": "no_chunks", "commit": head_commit}

    # 5. Embed chunks
    click.echo(f"  Embedding {len(all_chunks)} chunks (Gemini Flash free tier)...")
    bodies = [c["chunk_body"] for c in all_chunks]
    try:
        embeddings = embed_batch(bodies)
    except Exception as e:
        click.echo(f"  ERROR embedding: {e}")
        embeddings = [None] * len(all_chunks)

    for chunk, emb in zip(all_chunks, embeddings):
        chunk["embedding"] = emb

    # 6. Upsert to Supabase
    # Delete old chunks for changed files first
    changed_files = list({c["filepath"] for c in all_chunks})
    for fpath in changed_files:
        db.delete("code_chunks", {"repo_name": f"eq.{repo_name}", "filepath": f"eq.{fpath}"})

    # Insert new chunks in batches
    batch_size = 50
    inserted = 0
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        db.upsert("code_chunks", batch)
        inserted += len(batch)

    click.echo(f"  Upserted: {inserted} chunks")

    # 7. Update repo state
    lang_counts: dict[str, int] = {}
    for c in all_chunks:
        lang_counts[c["language"]] = lang_counts.get(c["language"], 0) + 1

    db.upsert("code_repos", [{
        "repo_name": repo_name,
        "repo_url": repo_url,
        "last_indexed_commit": head_commit,
        "last_indexed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "file_count": len(files),
        "chunk_count": inserted,
        "language_breakdown": lang_counts,
    }])

    return {
        "repo_name": repo_name,
        "status": "indexed",
        "commit": head_commit,
        "files": len(files),
        "chunks": inserted,
    }


# ============================================================
# CLI
# ============================================================
@click.group()
def cli():
    """CodeSearch — Multi-repo code intelligence for the Everest ecosystem."""
    pass


@cli.command()
@click.argument("query")
@click.option("--repo", default=None, help="Filter to specific repo")
@click.option("--language", default=None, help="Filter by language (python, typescript, sql...)")
@click.option("--limit", default=10, help="Max results")
@click.option("--vector-weight", default=0.7, help="Vector similarity weight (0-1)")
def search(query: str, repo: Optional[str], language: Optional[str], limit: int, vector_weight: float):
    """Search code across all indexed repos using hybrid search."""
    db = SupabaseClient()
    start = time.time()

    # Embed query
    try:
        query_embedding = embed_text(query)
    except Exception as e:
        click.echo(f"ERROR: embedding failed: {e}", err=True)
        sys.exit(1)

    # Call hybrid_code_search RPC
    try:
        results = db.rpc("hybrid_code_search", {
            "query_text": query,
            "query_embedding": query_embedding,
            "match_count": limit,
            "vector_weight": vector_weight,
            "text_weight": round(1.0 - vector_weight, 2),
            "filter_repo": repo,
            "filter_language": language,
        })
    except Exception as e:
        click.echo(f"ERROR: search failed: {e}", err=True)
        sys.exit(1)

    elapsed_ms = int((time.time() - start) * 1000)
    output = {
        "query": query,
        "results": results,
        "total": len(results),
        "search_ms": elapsed_ms,
    }
    click.echo(json.dumps(output, indent=2))


@cli.command()
@click.option("--repo", default=None, help="Index only this repo (default: all Tier 1)")
@click.option("--full", is_flag=True, help="Force full reindex (ignore last commit)")
def index(repo: Optional[str], full: bool):
    """Index repositories (incremental by default)."""
    db = SupabaseClient()

    repos_to_index = TIER1_REPOS
    if repo:
        repos_to_index = [(r, u) for r, u in TIER1_REPOS if r == repo]
        if not repos_to_index:
            click.echo(f"ERROR: unknown repo '{repo}'. Known: {[r for r, _ in TIER1_REPOS]}", err=True)
            sys.exit(1)

    results = []
    for repo_name, repo_url in repos_to_index:
        result = index_repo(db, repo_name, repo_url, full=full)
        results.append(result)

    click.echo("\n=== Index Summary ===")
    for r in results:
        status = r.get("status", r.get("error", "unknown"))
        chunks = r.get("chunks", "-")
        commit = r.get("commit", "")[:8] if r.get("commit") else "-"
        click.echo(f"  {r['repo_name']}: {status} | chunks={chunks} | commit={commit}")


@cli.command()
def stats():
    """Show index stats from database (VERIFIED — queries DB directly)."""
    db = SupabaseClient()

    repos = db.select("code_repos", {
        "select": "repo_name,chunk_count,file_count,last_indexed_at,last_indexed_commit,language_breakdown",
        "order": "chunk_count.desc",
    })

    total_chunks = sum(r.get("chunk_count", 0) or 0 for r in repos)
    total_files = sum(r.get("file_count", 0) or 0 for r in repos)

    click.echo(f"\n=== CodeSearch Stats (VERIFIED from DB) ===")
    click.echo(f"Repos indexed:  {len(repos)}")
    click.echo(f"Total chunks:   {total_chunks}")
    click.echo(f"Total files:    {total_files}")
    click.echo(f"\nPer-repo breakdown:")
    for r in repos:
        commit = r.get("last_indexed_commit", "")[:8] if r.get("last_indexed_commit") else "never"
        click.echo(f"  {r['repo_name']:30s} chunks={r.get('chunk_count', 0):6d}  commit={commit}")

    output = {
        "repos": len(repos),
        "total_chunks": total_chunks,
        "total_files": total_files,
        "detail": repos,
    }
    click.echo(json.dumps(output, indent=2))


if __name__ == "__main__":
    cli()

# SUMMIT: Add cli_anything.linkedin to cli-anything-biddeed

## Priority: P1
## Estimated: 45min
## Type: ADOPT + delta integration

## Context
Adopted `joeyism/linkedin_scraper` (Playwright async, Pydantic, PyPI, 82/100 REPOEVAL).
Added 504-line delta: `PostScraper` (single URL → structured text) + `PostScraperPublic` (meta-tag fast path).
Pattern matches YouTube transcript INSTANT SQUAD: `LinkedIn:` + URL → extract → insights → Supabase.

## Source Files
All delta code is in this directory. Core files:
- `linkedin_scraper/scrapers/post.py` — PostScraper + PostScraperPublic
- `samples/scrape_post.py` — CLI reference implementation
- Full upstream repo included (joeyism/linkedin_scraper v3.1.1, Apache 2.0)

## Tasks

### 1. Install upstream as dependency
```bash
# In cli-anything-biddeed
pip install linkedin-scraper  # PyPI package from joeyism
# OR vendor the linkedin_scraper/ directory into cli-anything-biddeed/vendor/
```
Preferred: vendor (we have custom delta in scrapers/post.py).
Copy `linkedin_scraper/` directory → `cli-anything-biddeed/vendor/linkedin_scraper/`

### 2. Create cli_anything.linkedin module
```
cli-anything-biddeed/
  cli_anything/
    linkedin/
      __init__.py
      scraper.py      ← wraps PostScraper + PostScraperPublic
      commands.py     ← CLI commands matching harness pattern
```

### 3. Commands to implement (HARNESS.md pattern)

```yaml
commands:
  linkedin:post:
    trigger: "LinkedIn:" + URL  OR  "linkedin post <url>"
    action: Extract post text → JSON → Supabase discovery_results
    flags: [--json, --supabase, --meta-only]
    
  linkedin:setup:
    trigger: "linkedin setup" 
    action: Launch Playwright, navigate to LinkedIn, save session.json
    note: One-time HITL on Hetzner
    
  linkedin:test:
    trigger: "linkedin test"
    action: Scrape a known public post, verify text extraction
```

### 4. Supabase integration
Table: `discovery_results` (already exists from Exa discovery)
```sql
-- No migration needed, reuse existing table
-- Columns used: source, source_url, content_type, title, content, metadata, mode
-- source = 'linkedin'
-- mode = 'linkedin_post'
-- content_type = 'post'
```

### 5. INSTANT SQUAD pattern
Wire into existing instant squad detection:
- If message starts with `LinkedIn:` or contains `linkedin.com/posts/` → auto-trigger extraction
- Same as `Transcript:` + YouTube URL pattern

### 6. Playwright session management
- `session.json` stored at: `~/.config/cli-anything/linkedin_session.json`
- Also available as GitHub secret: `LINKEDIN_SESSION_JSON` (base64 encoded)
- Session refresh: manual via `linkedin setup` command
- Cookie `li_at` typically lasts 1 year

### 7. Requirements additions
```
# In requirements.txt
playwright>=1.40.0
pydantic>=2.0.0
aiohttp>=3.9.0  # For PostScraperPublic fast path
```

### 8. Tests
```python
# tests/test_linkedin.py
def test_post_scraper_public_meta():
    """Test meta-tag extraction on a known public post."""
    # Use a LinkedIn blog/pulse post (always public)
    
def test_post_model_serialization():
    """Test Post Pydantic model."""
    
def test_normalize_url():
    """Test URL normalization strips params."""
```

## Acceptance Criteria
- [ ] `cli_anything.linkedin` module loads without error
- [ ] `python -m cli_anything.linkedin.commands post <url> --json` returns post text
- [ ] `--supabase` flag inserts row into discovery_results
- [ ] PostScraperPublic works without session.json (meta-tag path)
- [ ] PostScraper works with session.json (full Playwright path)
- [ ] 3+ tests passing
- [ ] Added to weekly-health check

## References
- Upstream: github.com/joeyism/linkedin_scraper (Apache 2.0)
- Delta selectors from: github.com/kkundanI/Linkedin_Post_Extractor_Website
- REPOEVAL: 82/100 ADOPT
- Rejected repos: asia930 (FAKE mock data), christophe-garon (stale 2023)

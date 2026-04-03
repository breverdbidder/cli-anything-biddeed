"""LinkedIn scraper wrapper for cli-anything harness.

Two extraction paths:
1. FAST: PostScraperPublic (meta tags, no auth, <2s)
2. FULL: PostScraper (Playwright + session cookie, ~10s)

Always tries fast path first. Falls back to full if text < 100 chars.
"""

import asyncio
import json
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Session file locations (priority order)
SESSION_PATHS = [
    os.path.expanduser("~/.config/cli-anything/linkedin_session.json"),
    os.path.join(os.path.dirname(__file__), "session.json"),
    "session.json",
]


def find_session() -> Optional[str]:
    """Find LinkedIn session.json file."""
    # Check env var first (base64 encoded for CI/CD)
    env_session = os.environ.get("LINKEDIN_SESSION_JSON")
    if env_session:
        import base64
        import tempfile
        decoded = base64.b64decode(env_session)
        tmp = tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False)
        tmp.write(decoded)
        tmp.close()
        return tmp.name
    
    for path in SESSION_PATHS:
        if os.path.exists(path):
            return path
    return None


async def extract_post(url: str, force_playwright: bool = False) -> Dict[str, Any]:
    """Extract LinkedIn post content.
    
    Args:
        url: LinkedIn post URL
        force_playwright: Skip meta-tag fast path
    
    Returns:
        Dict with text, metadata, source info
    """
    result = None
    
    # === FAST PATH ===
    if not force_playwright:
        try:
            from linkedin_scraper.scrapers.post import PostScraperPublic
            meta = await PostScraperPublic.extract_meta(url)
            if meta and len(meta.get('text', '')) > 100:
                result = {
                    'url': url,
                    'text': meta['text'],
                    'title': meta.get('title', ''),
                    'image': meta.get('image', ''),
                    'source': 'meta_tags',
                    'extracted_at': datetime.now(timezone.utc).isoformat(),
                }
                logger.info(f"Fast path: {len(result['text'])} chars from meta tags")
        except Exception as e:
            logger.warning(f"Fast path failed: {e}")
    
    # === FULL PATH ===
    if not result or len(result.get('text', '')) < 100:
        session_path = find_session()
        if not session_path:
            if result:
                logger.warning("No session.json, using partial meta result")
                return result
            raise FileNotFoundError(
                "No LinkedIn session found. Run: cli_anything linkedin setup"
            )
        
        from linkedin_scraper import BrowserManager
        from linkedin_scraper.scrapers.post import PostScraper
        
        async with BrowserManager(headless=True) as browser:
            await browser.load_session(session_path)
            scraper = PostScraper(browser.page)
            post = await scraper.scrape(url)
            
            result = {
                'url': post.linkedin_url,
                'urn': post.urn,
                'text': post.text,
                'posted_date': post.posted_date,
                'reactions_count': post.reactions_count,
                'comments_count': post.comments_count,
                'reposts_count': post.reposts_count,
                'image_urls': post.image_urls,
                'video_url': post.video_url,
                'article_url': post.article_url,
                'source': 'playwright',
                'extracted_at': datetime.now(timezone.utc).isoformat(),
            }
            logger.info(f"Full path: {len(post.text or '')} chars via Playwright")
    
    return result


async def push_to_supabase(data: Dict[str, Any]) -> Optional[str]:
    """Push extracted post to Supabase discovery_results.
    
    Returns inserted row ID or None on failure.
    """
    try:
        from supabase import create_client
        
        url = os.environ.get('SUPABASE_URL', '')
        key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
        
        if not url or not key:
            logger.error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
            return None
        
        client = create_client(url, key)
        
        row = {
            'source': 'linkedin',
            'source_url': data.get('url', ''),
            'content_type': 'post',
            'title': data.get('title') or data.get('urn') or 'LinkedIn Post',
            'content': data.get('text', ''),
            'metadata': json.dumps({
                k: v for k, v in data.items()
                if k not in ('text', 'url', 'title') and v is not None
            }),
            'mode': 'linkedin_post',
        }
        
        result = client.table('discovery_results').insert(row).execute()
        row_id = result.data[0]['id'] if result.data else None
        logger.info(f"Supabase insert: {row_id}")
        return row_id
        
    except Exception as e:
        logger.error(f"Supabase push failed: {e}")
        return None


def extract_post_sync(url: str, **kwargs) -> Dict[str, Any]:
    """Synchronous wrapper for extract_post."""
    return asyncio.run(extract_post(url, **kwargs))

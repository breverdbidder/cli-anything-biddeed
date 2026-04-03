#!/usr/bin/env python3
"""Scrape a single LinkedIn post by URL.

Usage (matches YouTube transcript pattern):
    python scrape_post.py "https://www.linkedin.com/posts/username_topic-activity-123-xxxx"
    python scrape_post.py "https://www.linkedin.com/posts/..." --json
    python scrape_post.py "https://www.linkedin.com/posts/..." --supabase

Requires: session.json (run create_session.py first)
"""

import asyncio
import argparse
import json
import sys
import os

# Add parent to path for local dev
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from linkedin_scraper import BrowserManager, PostScraper, PostScraperPublic


async def scrape_post(url: str, output_format: str = 'text', supabase: bool = False) -> dict:
    """Scrape a single LinkedIn post.
    
    Tries meta-tag extraction first (fast, no auth needed).
    Falls back to full Playwright scraping if meta tags are insufficient.
    """
    result = None
    
    # === FAST PATH: Try public meta tags first (no browser needed) ===
    print(f"[1/2] Trying meta-tag extraction (fast path)...")
    try:
        meta_result = await PostScraperPublic.extract_meta(url)
        if meta_result and len(meta_result.get('text', '')) > 100:
            print(f"  ✅ Got {len(meta_result['text'])} chars from meta tags")
            result = {
                'url': url,
                'text': meta_result['text'],
                'title': meta_result.get('title', ''),
                'image': meta_result.get('image', ''),
                'source': 'meta_tags',
            }
    except Exception as e:
        print(f"  ⚠️ Meta extraction failed: {e}")
    
    # === FULL PATH: Playwright with session cookies ===
    if not result or len(result.get('text', '')) < 100:
        print(f"[2/2] Full Playwright extraction...")
        session_path = os.path.join(os.path.dirname(__file__), 'session.json')
        
        if not os.path.exists(session_path):
            print(f"  ❌ No session.json found. Run create_session.py first.")
            if result:
                print(f"  Using partial meta-tag result instead.")
            else:
                sys.exit(1)
        else:
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
                }
                print(f"  ✅ Got {len(post.text or '')} chars via Playwright")
    
    # === OUTPUT ===
    if output_format == 'json':
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif output_format == 'text':
        print(f"\n{'='*60}")
        print(f"URL: {result.get('url', '')}")
        if result.get('urn'):
            print(f"URN: {result['urn']}")
        if result.get('posted_date'):
            print(f"Posted: {result['posted_date']}")
        print(f"{'='*60}")
        print(result.get('text', 'No text extracted'))
        print(f"{'='*60}")
        if result.get('reactions_count'):
            print(f"Reactions: {result['reactions_count']} | "
                  f"Comments: {result.get('comments_count', 0)} | "
                  f"Reposts: {result.get('reposts_count', 0)}")
    
    # === SUPABASE (like YouTube transcript pattern) ===
    if supabase and result:
        await push_to_supabase(result)
    
    return result


async def push_to_supabase(data: dict):
    """Push extracted post to Supabase discovery_results table.
    
    Matches the YouTube transcript INSTANT SQUAD pattern:
    URL → extract → insights → Supabase
    """
    try:
        from supabase import create_client
        
        supabase_url = os.environ.get('SUPABASE_URL', '')
        supabase_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
        
        if not supabase_url or not supabase_key:
            print("⚠️ SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
            return
        
        client = create_client(supabase_url, supabase_key)
        
        row = {
            'source': 'linkedin',
            'source_url': data.get('url', ''),
            'content_type': 'post',
            'title': data.get('title') or data.get('urn') or 'LinkedIn Post',
            'content': data.get('text', ''),
            'metadata': json.dumps({
                k: v for k, v in data.items()
                if k not in ('text', 'url') and v is not None
            }),
            'mode': 'linkedin_post',
        }
        
        result = client.table('discovery_results').insert(row).execute()
        print(f"✅ Pushed to Supabase: {result.data[0]['id'] if result.data else 'ok'}")
        
    except ImportError:
        print("⚠️ supabase-py not installed. pip install supabase")
    except Exception as e:
        print(f"❌ Supabase push failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Scrape a single LinkedIn post by URL',
        epilog='Examples:\n'
               '  python scrape_post.py "https://linkedin.com/posts/..."\n'
               '  python scrape_post.py "https://linkedin.com/posts/..." --json\n'
               '  python scrape_post.py "https://linkedin.com/posts/..." --supabase\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('url', help='LinkedIn post URL')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--supabase', action='store_true', 
                       help='Push to Supabase discovery_results table')
    
    args = parser.parse_args()
    output_format = 'json' if args.json else 'text'
    
    asyncio.run(scrape_post(args.url, output_format, args.supabase))


if __name__ == '__main__':
    main()

"""CLI commands for LinkedIn post extraction.

Follows cli-anything HARNESS.md pattern.
Matches YouTube transcript INSTANT SQUAD trigger.

Commands:
    linkedin post <url>           Extract post text
    linkedin post <url> --json    Output as JSON
    linkedin post <url> --supabase Push to discovery_results
    linkedin setup                One-time session cookie capture
    linkedin test                 Verify extraction works
"""

import argparse
import asyncio
import json
import sys
import os
import re
import logging

from .scraper import extract_post, push_to_supabase, find_session

logger = logging.getLogger(__name__)

# INSTANT SQUAD: detect LinkedIn URLs in raw input
LINKEDIN_POST_PATTERN = re.compile(
    r'https?://(?:www\.)?linkedin\.com/'
    r'(?:posts|pulse|feed/update)/[^\s]+'
)


def is_linkedin_trigger(text: str) -> bool:
    """Check if text triggers LinkedIn extraction.
    
    Triggers:
        - "LinkedIn:" + URL
        - Raw linkedin.com/posts/ URL
        - "linkedin post <url>"
    """
    if text.strip().lower().startswith('linkedin:'):
        return True
    if LINKEDIN_POST_PATTERN.search(text):
        return True
    return False


def extract_url_from_trigger(text: str) -> str:
    """Extract LinkedIn URL from trigger text."""
    # Strip "LinkedIn:" prefix
    clean = re.sub(r'^linkedin:\s*', '', text.strip(), flags=re.IGNORECASE)
    
    # Find URL in text
    match = LINKEDIN_POST_PATTERN.search(clean)
    if match:
        return match.group(0)
    
    # Maybe the whole thing is a URL
    if 'linkedin.com' in clean:
        return clean.strip()
    
    raise ValueError(f"No LinkedIn URL found in: {text}")


async def cmd_post(url: str, output_json: bool = False, supabase: bool = False,
                   meta_only: bool = False) -> int:
    """Extract a single LinkedIn post."""
    try:
        data = await extract_post(url, force_playwright=False)
        
        if not data or not data.get('text'):
            print("❌ No text extracted from post")
            return 1
        
        # Output
        if output_json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            text = data.get('text', '')
            source = data.get('source', 'unknown')
            print(f"✅ [{source}] {len(text)} chars extracted")
            print(f"{'─'*60}")
            print(text)
            print(f"{'─'*60}")
            
            if data.get('reactions_count'):
                print(f"📊 {data['reactions_count']} reactions | "
                      f"{data.get('comments_count', 0)} comments | "
                      f"{data.get('reposts_count', 0)} reposts")
        
        # Supabase
        if supabase:
            row_id = await push_to_supabase(data)
            if row_id:
                print(f"📦 Supabase: {row_id}")
            else:
                print("⚠️ Supabase push failed")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("Run: cli_anything linkedin setup")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("Post extraction failed")
        return 1


async def cmd_setup():
    """Interactive session setup — captures LinkedIn cookies via Playwright.
    
    One-time HITL: opens browser, user logs in, cookies saved.
    """
    from linkedin_scraper import BrowserManager
    
    session_dir = os.path.expanduser("~/.config/cli-anything")
    os.makedirs(session_dir, exist_ok=True)
    session_path = os.path.join(session_dir, "linkedin_session.json")
    
    print("🔐 LinkedIn Session Setup")
    print("A browser will open. Log into LinkedIn manually.")
    print("Once logged in, press Enter in this terminal.\n")
    
    async with BrowserManager(headless=False) as browser:
        await browser.page.goto("https://www.linkedin.com/login")
        input("Press Enter after logging in to LinkedIn...")
        await browser.save_session(session_path)
    
    print(f"✅ Session saved: {session_path}")
    return 0


async def cmd_test():
    """Test extraction on a known public LinkedIn post."""
    # Use LinkedIn's own blog post (always public)
    test_url = "https://www.linkedin.com/pulse/introducing-linkedin-ai-powered-messages-keren-baruch/"
    
    print(f"🧪 Testing extraction on: {test_url}")
    
    try:
        data = await extract_post(test_url)
        text = data.get('text', '')
        
        if len(text) > 50:
            print(f"✅ PASS — {len(text)} chars extracted via {data.get('source')}")
            print(f"Preview: {text[:200]}...")
            return 0
        else:
            print(f"⚠️ PARTIAL — only {len(text)} chars")
            session = find_session()
            if not session:
                print("No session.json found. Run: cli_anything linkedin setup")
            return 1
    except Exception as e:
        print(f"❌ FAIL — {e}")
        return 1


def main(argv=None):
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='cli_anything linkedin',
        description='LinkedIn post extraction for the Everest ecosystem',
    )
    sub = parser.add_subparsers(dest='command')
    
    # post
    post_parser = sub.add_parser('post', help='Extract a LinkedIn post')
    post_parser.add_argument('url', help='LinkedIn post URL')
    post_parser.add_argument('--json', action='store_true', dest='output_json',
                            help='Output as JSON')
    post_parser.add_argument('--supabase', action='store_true',
                            help='Push to Supabase discovery_results')
    post_parser.add_argument('--meta-only', action='store_true',
                            help='Only use meta-tag extraction (no Playwright)')
    
    # setup
    sub.add_parser('setup', help='One-time session cookie capture')
    
    # test
    sub.add_parser('test', help='Test extraction on a known post')
    
    args = parser.parse_args(argv)
    
    if args.command == 'post':
        return asyncio.run(cmd_post(
            args.url,
            output_json=args.output_json,
            supabase=args.supabase,
            meta_only=args.meta_only,
        ))
    elif args.command == 'setup':
        return asyncio.run(cmd_setup())
    elif args.command == 'test':
        return asyncio.run(cmd_test())
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())

"""Single LinkedIn post scraper - extract content from a post URL.

Usage pattern matches YouTube transcript extraction:
  URL in → structured Post data out → Supabase

Combines selectors from joeyism/linkedin_scraper + kkundanI/Linkedin_Post_Extractor_Website
for maximum coverage of LinkedIn's rotating DOM structure.
"""

import logging
import re
import json
from typing import Optional, Dict, Any
from playwright.async_api import Page

from ..models.post import Post
from ..callbacks import ProgressCallback, SilentCallback
from .base import BaseScraper

logger = logging.getLogger(__name__)


class PostScraper(BaseScraper):
    """Scrape a single LinkedIn post by URL.
    
    Designed for daily use: paste a LinkedIn post URL, get structured text back.
    Like Supadata for YouTube, but for LinkedIn.
    """
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        super().__init__(page, callback or SilentCallback())
    
    async def scrape(self, post_url: str) -> Post:
        """Extract content from a single LinkedIn post URL.
        
        Args:
            post_url: Full LinkedIn post URL 
                (e.g., https://www.linkedin.com/posts/username_topic-activity-123456-xxxx)
        
        Returns:
            Post object with text, engagement metrics, images, author info
        """
        logger.info(f"Scraping single post: {post_url}")
        await self.callback.on_start("post", post_url)
        
        # Normalize URL
        post_url = self._normalize_post_url(post_url)
        
        # Navigate
        await self.navigate_and_wait(post_url)
        await self.callback.on_progress("Navigated to post", 20)
        
        # Wait for content to render
        await self._wait_for_post_content()
        await self.callback.on_progress("Content loaded", 40)
        
        # Close any modals (login prompts, cookie banners)
        await self.close_modals()
        
        # Click "see more" to expand truncated text
        await self.click_all_see_more_buttons(max_attempts=3)
        await self.callback.on_progress("Expanded text", 60)
        
        # Extract all post data
        post = await self._extract_post_data(post_url)
        await self.callback.on_progress("Extracted content", 90)
        
        # Fallback: try og:description meta tag for public posts
        if not post.text or len(post.text) < 20:
            meta_text = await self._extract_from_meta_tags()
            if meta_text and len(meta_text) > len(post.text or ''):
                post.text = meta_text
                logger.info("Used meta tag fallback for text extraction")
        
        await self.callback.on_progress("Complete", 100)
        await self.callback.on_complete("post", post)
        
        logger.info(f"Extracted post: {len(post.text or '')} chars, "
                     f"{post.reactions_count or 0} reactions")
        return post
    
    def _normalize_post_url(self, url: str) -> str:
        """Normalize LinkedIn post URL to canonical form."""
        url = url.split('?')[0].rstrip('/')
        # Ensure it's a full URL
        if not url.startswith('http'):
            url = f"https://www.linkedin.com{url}"
        return url
    
    async def _wait_for_post_content(self, timeout: int = 15000) -> None:
        """Wait for post content to load."""
        # Try multiple selectors - LinkedIn changes these frequently
        content_selectors = [
            '[data-urn*="activity"]',
            '.feed-shared-update-v2',
            '.feed-shared-text',
            '.update-components-text',
            'article',
            '[data-test-id="main-feed-activity-card"]',
        ]
        
        for selector in content_selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=timeout // len(content_selectors))
                logger.debug(f"Content loaded via selector: {selector}")
                return
            except Exception:
                continue
        
        # Final fallback: just wait for DOM
        await self.page.wait_for_timeout(3000)
        logger.warning("No specific content selector found, proceeding with DOM")
    
    async def _extract_post_data(self, post_url: str) -> Post:
        """Extract all data from the loaded post page."""
        data = await self.page.evaluate('''() => {
            const result = {
                text: '',
                authorName: '',
                authorHeadline: '',
                authorUrl: '',
                timeText: '',
                reactions: '',
                comments: '',
                reposts: '',
                images: [],
                videoUrl: '',
                articleUrl: '',
                urn: ''
            };
            
            // === TEXT EXTRACTION (multi-selector, priority order) ===
            const textSelectors = [
                // Primary selectors (current LinkedIn DOM)
                '.feed-shared-update-v2__description .break-words',
                '.update-components-text .break-words',
                '[data-test-id="main-feed-activity-card__commentary"] .break-words',
                // Secondary selectors
                '.feed-shared-text span[dir="ltr"]',
                '[data-view-name="feed-shared-text"] span[dir="ltr"]',
                '.attributed-text-segment-list__content',
                '.feed-shared-update-v2__description',
                '.update-components-text',
                '.feed-shared-text',
                // Fallback selectors (from kkundanI repo)
                'article .break-words',
                '.break-words.whitespace-pre-wrap',
            ];
            
            for (const sel of textSelectors) {
                const el = document.querySelector(sel);
                if (el) {
                    const t = el.innerText?.trim() || '';
                    if (t.length > result.text.length && t.length > 10) {
                        result.text = t;
                    }
                }
            }
            
            // === AUTHOR INFO ===
            const authorEl = document.querySelector(
                '.feed-shared-actor__name, ' +
                '.update-components-actor__name, ' +
                '[data-test-id="main-feed-activity-card__entity-lockup"] .app-aware-link'
            );
            if (authorEl) {
                result.authorName = authorEl.innerText?.trim()?.split('\\n')[0] || '';
                const link = authorEl.closest('a') || authorEl.querySelector('a');
                if (link) result.authorUrl = link.href || '';
            }
            
            const headlineEl = document.querySelector(
                '.feed-shared-actor__description, ' +
                '.update-components-actor__description'
            );
            if (headlineEl) {
                result.authorHeadline = headlineEl.innerText?.trim()?.split('\\n')[0] || '';
            }
            
            // === TIME ===
            const timeEl = document.querySelector(
                '[class*="actor__sub-description"], ' +
                '[class*="update-components-actor__sub-description"], ' +
                'time'
            );
            if (timeEl) {
                result.timeText = timeEl.innerText?.trim() || timeEl.getAttribute('datetime') || '';
            }
            
            // === ENGAGEMENT METRICS ===
            const reactionsEl = document.querySelector(
                '[class*="social-details-social-counts__reactions"], ' +
                'button[aria-label*="reaction"]'
            );
            if (reactionsEl) result.reactions = reactionsEl.innerText?.trim() || '';
            
            const commentsEl = document.querySelector('button[aria-label*="comment"]');
            if (commentsEl) result.comments = commentsEl.innerText?.trim() || '';
            
            const repostsEl = document.querySelector('button[aria-label*="repost"]');
            if (repostsEl) result.reposts = repostsEl.innerText?.trim() || '';
            
            // === MEDIA ===
            document.querySelectorAll('img[src*="media"]').forEach(img => {
                if (img.src && !img.src.includes('profile') && !img.src.includes('logo')) {
                    result.images.push(img.src);
                }
            });
            
            const videoEl = document.querySelector('video source, video[src]');
            if (videoEl) {
                result.videoUrl = videoEl.getAttribute('src') || videoEl.src || '';
            }
            
            const articleEl = document.querySelector(
                '.feed-shared-article__link, ' +
                'a[data-test-id="feed-shared-article"]'
            );
            if (articleEl) {
                result.articleUrl = articleEl.href || '';
            }
            
            // === URN ===
            const urnMatch = document.body.innerHTML.match(/urn:li:activity:(\d+)/);
            if (urnMatch) result.urn = urnMatch[0];
            
            return result;
        }''')
        
        return Post(
            linkedin_url=post_url,
            urn=data.get('urn'),
            text=data.get('text'),
            posted_date=self._extract_time(data.get('timeText', '')),
            reactions_count=self._parse_count(data.get('reactions', '')),
            comments_count=self._parse_count(data.get('comments', '')),
            reposts_count=self._parse_count(data.get('reposts', '')),
            image_urls=data.get('images', []),
            video_url=data.get('videoUrl') or None,
            article_url=data.get('articleUrl') or None,
        )
    
    async def _extract_from_meta_tags(self) -> Optional[str]:
        """Fallback: extract text from og:description meta tag.
        Works on public posts without full JS rendering.
        Borrowed from kkundanI/Linkedin_Post_Extractor_Website.
        """
        return await self.page.evaluate('''() => {
            const og = document.querySelector('meta[property="og:description"]');
            if (og) return og.getAttribute('content') || '';
            const meta = document.querySelector('meta[name="description"]');
            if (meta) return meta.getAttribute('content') || '';
            return '';
        }''')
    
    def _extract_time(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = re.search(
            r'(\d+[hdwmy]|\d+\s*(?:hour|day|week|month|year)s?\s*ago)',
            text, re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        parts = text.split('•')
        return parts[0].strip() if parts else None
    
    def _parse_count(self, text: str) -> Optional[int]:
        if not text:
            return None
        try:
            numbers = re.findall(r'[\d,]+', text.replace(',', ''))
            if numbers:
                return int(numbers[0])
        except (ValueError, IndexError):
            pass
        return None


class PostScraperPublic:
    """Lightweight public post scraper using requests + meta tags only.
    
    No Playwright needed. Works for public posts where og:description
    contains the post text. Use as fast fallback before full PostScraper.
    """
    
    @staticmethod
    async def extract_meta(url: str) -> Optional[Dict[str, Any]]:
        """Extract post content from meta tags via simple HTTP request.
        
        Returns dict with text, author, description or None if post is private.
        """
        import aiohttp
        
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None
                    html = await resp.text()
            
            # Parse meta tags
            import re
            
            og_desc = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', html)
            og_title = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', html)
            og_image = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', html)
            
            text = og_desc.group(1) if og_desc else ''
            title = og_title.group(1) if og_title else ''
            image = og_image.group(1) if og_image else ''
            
            if not text:
                return None
            
            # Decode HTML entities
            import html as html_module
            text = html_module.unescape(text)
            title = html_module.unescape(title)
            
            return {
                'text': text,
                'title': title,
                'image': image,
                'url': url,
                'source': 'meta_tags'
            }
        except Exception as e:
            logger.warning(f"Meta extraction failed: {e}")
            return None

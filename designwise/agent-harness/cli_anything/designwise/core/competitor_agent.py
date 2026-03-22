"""
CompetitorWise Agent — SPEC Agent 12
Weekly competitor monitoring for ZoneWise.AI.
Targets: propertyonion.com, reventure.app, dono.ai, gridics.com, testfit.io.
Screenshot + DOM hash comparison. Wappalyzer-style tech stack detection.
Writes to: competitor_snapshots.
"""

import argparse
import asyncio
import hashlib
import json
import os
from typing import Any, Dict, List, Optional

COMPETITORS = [
    "propertyonion.com",
    "reventure.app",
    "dono.ai",
    "gridics.com",
    "testfit.io",
]

TECH_HEADERS = {
    "x-powered-by": "framework",
    "x-vercel-id": "vercel",
    "cf-cache-status": "cloudflare",
    "x-shopify-stage": "shopify",
    "server": "server_type",
}


class CompetitorWiseAgent:
    """
    Weekly competitor monitoring: screenshots, DOM diffs, pricing extraction, tech stack.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_KEY", "")
        self._playwright_available = self._check_playwright()

    def _check_playwright(self) -> bool:
        try:
            import playwright  # noqa
            return True
        except ImportError:
            return False

    def _get_db(self):
        try:
            from cli_anything.designwise.utils.supabase_client import DesignWiseDB
            return DesignWiseDB(url=self.supabase_url, key=self.supabase_key)
        except ImportError:
            return None

    def _dom_hash(self, html: str) -> str:
        """Generate a stable hash of page DOM structure."""
        import re
        # Strip scripts/styles/comments, normalize whitespace
        stripped = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        stripped = re.sub(r"<style[^>]*>.*?</style>", "", stripped, flags=re.DOTALL)
        stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.DOTALL)
        normalized = " ".join(stripped.split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    async def _fetch_page(self, url: str) -> Dict[str, Any]:
        """Fetch a competitor homepage and return html + headers."""
        if not url.startswith("http"):
            url = f"https://{url}"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ZoneWise-Monitor/1.0)"})
                return {"html": resp.text, "headers": dict(resp.headers), "status": resp.status_code, "url": url}
        except Exception as e:
            return {"error": str(e), "url": url}

    async def capture_homepage(self, competitor: str) -> Dict[str, Any]:
        """
        Capture homepage screenshot + DOM hash for a competitor.
        """
        import datetime
        url = f"https://{competitor}" if not competitor.startswith("http") else competitor
        page_data = await self._fetch_page(url)
        if "error" in page_data:
            return {"competitor": competitor, "error": page_data["error"]}

        dom_hash = self._dom_hash(page_data.get("html", ""))
        snapshot = {
            "competitor": competitor,
            "url": url,
            "dom_hash": dom_hash,
            "scan_date": datetime.date.today().isoformat(),
            "status": page_data.get("status"),
        }

        if self._playwright_available:
            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(headless=True)
                    page = await browser.new_page(viewport={"width": 1280, "height": 800})
                    await page.goto(url, timeout=20000)
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    screenshot_path = f"/tmp/competitor_{competitor.replace('.', '_')}.png"
                    await page.screenshot(path=screenshot_path)
                    snapshot["screenshot"] = screenshot_path
                    await browser.close()
            except Exception as e:
                snapshot["screenshot_error"] = str(e)

        db = self._get_db()
        if db:
            await db.upsert("competitor_snapshots", snapshot)

        return snapshot

    async def diff_dom(self, competitor: str) -> Dict[str, Any]:
        """Compare current DOM hash against stored baseline. Detect changes."""
        db = self._get_db()
        if not db:
            return {"competitor": competitor, "status": "no_db"}
        prev = await db.query("competitor_snapshots", {"competitor": f"eq.{competitor}", "order": "scan_date.desc", "limit": "2"})
        if not prev or "error" in prev or not isinstance(prev, list) or len(prev) < 2:
            return {"competitor": competitor, "status": "no_baseline", "action": "capture_baseline_first"}
        old_hash = prev[1].get("dom_hash", "")
        new_hash = prev[0].get("dom_hash", "")
        changed = old_hash != new_hash
        return {
            "competitor": competitor,
            "changed": changed,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "dates": [prev[0].get("scan_date"), prev[1].get("scan_date")],
        }

    async def extract_pricing(self, competitor: str) -> Dict[str, Any]:
        """Extract pricing information from competitor's pricing page."""
        import re
        url = f"https://{competitor}/pricing"
        page_data = await self._fetch_page(url)
        if "error" in page_data:
            return {"competitor": competitor, "error": page_data["error"]}
        html = page_data.get("html", "")
        # Look for price patterns like $99, $99/mo, $99/month
        price_pattern = re.compile(r'\$[\d,]+(?:\.\d{2})?(?:\s*/\s*(?:mo|month|year|yr|user|seat))?', re.IGNORECASE)
        prices = list(set(price_pattern.findall(html)))
        return {"competitor": competitor, "prices_found": prices[:20], "url": url}

    async def detect_new_routes(self, competitor: str) -> Dict[str, Any]:
        """Detect new pages/routes on competitor site by scraping sitemap."""
        sitemap_url = f"https://{competitor}/sitemap.xml"
        page_data = await self._fetch_page(sitemap_url)
        if "error" in page_data:
            return {"competitor": competitor, "routes": [], "error": page_data["error"]}
        import re
        locs = re.findall(r"<loc>(.*?)</loc>", page_data.get("html", ""), re.IGNORECASE)
        return {"competitor": competitor, "routes_found": len(locs), "sample": locs[:10]}

    async def analyze_tech_stack(self, competitor: str) -> Dict[str, Any]:
        """Wappalyzer-style analysis using response headers + HTML patterns."""
        url = f"https://{competitor}" if not competitor.startswith("http") else competitor
        page_data = await self._fetch_page(url)
        if "error" in page_data:
            return {"competitor": competitor, "error": page_data["error"], "stack": {}}

        headers = page_data.get("headers", {})
        html = page_data.get("html", "")
        stack: Dict[str, str] = {}

        # Header-based detection
        for header, tech_key in TECH_HEADERS.items():
            val = headers.get(header, "")
            if val:
                stack[tech_key] = val[:50]

        # HTML pattern detection
        import re
        if re.search(r"next[/\-]data|__NEXT_DATA__", html):
            stack["frontend"] = "Next.js"
        elif re.search(r"react\.js|react-dom", html, re.IGNORECASE):
            stack["frontend"] = "React"
        if re.search(r"gtag\(|google-analytics", html, re.IGNORECASE):
            stack["analytics"] = "Google Analytics"
        if re.search(r"posthog", html, re.IGNORECASE):
            stack["analytics"] = "PostHog"
        if re.search(r"segment\.com|segment\.io", html, re.IGNORECASE):
            stack["analytics"] = "Segment"
        if re.search(r"tailwind", html, re.IGNORECASE):
            stack["css"] = "Tailwind CSS"
        if re.search(r"wordpress|wp-content|wp-json", html, re.IGNORECASE):
            stack["cms"] = "WordPress"

        return {"competitor": competitor, "url": url, "tech_stack": stack}

    async def generate_weekly_digest(self) -> Dict[str, Any]:
        """Generate weekly digest of all competitor changes."""
        import datetime
        digest = {
            "generated": datetime.date.today().isoformat(),
            "competitors": {},
        }
        for comp in COMPETITORS:
            snapshot = await self.capture_homepage(comp)
            diff = await self.diff_dom(comp)
            tech = await self.analyze_tech_stack(comp)
            digest["competitors"][comp] = {
                "dom_changed": diff.get("changed", False),
                "tech_stack": tech.get("tech_stack", {}),
                "snapshot": snapshot.get("dom_hash", ""),
            }
        return digest

    async def run(self, target: Optional[str] = None, digest: bool = False, **kwargs) -> Dict[str, Any]:
        """Main async entry point."""
        if digest:
            return await self.generate_weekly_digest()
        if target:
            snapshot = await self.capture_homepage(target)
            tech = await self.analyze_tech_stack(target)
            pricing = await self.extract_pricing(target)
            return {"target": target, "snapshot": snapshot, "tech": tech, "pricing": pricing}
        return {"error": "Specify --target <competitor> or --digest", "agent": "competitor"}


def main():
    parser = argparse.ArgumentParser(description="CompetitorWise — Weekly competitor monitor")
    parser.add_argument("--target", help="Competitor URL", default=None)
    parser.add_argument("--digest", action="store_true", help="Weekly digest")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    agent = CompetitorWiseAgent()
    result = asyncio.run(agent.run(target=args.target, digest=args.digest))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

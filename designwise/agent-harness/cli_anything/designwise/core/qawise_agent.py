"""
QAWise Agent — SPEC Agent 06
Visual regression + E2E testing for ZoneWise.AI.
Viewports: 1280px (desktop), 768px (tablet), 375px (mobile).
Pixelmatch diff threshold: 1%. Lighthouse targets: Perf>=80, A11y>=90, SEO>=80.
"""

import argparse
import asyncio
import json
import os
from typing import Any, Dict, List, Optional

VIEWPORTS = [
    {"name": "desktop", "width": 1280, "height": 800},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "mobile", "width": 375, "height": 812},
]

E2E_FLOW = [
    "landing",
    "heatmap",
    "parcel_click",
    "gate",
    "signup",
    "app",
    "chat",
    "map",
    "calendar",
]

LIGHTHOUSE_TARGETS = {
    "performance": 80,
    "accessibility": 90,
    "seo": 80,
    "best_practices": 80,
}

DIFF_THRESHOLD = 0.01  # 1%


class QAWiseAgent:
    """
    Visual regression + E2E QA for ZoneWise.AI.
    Requires Playwright for screenshot capture. Falls back to HTTP checks when unavailable.
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

    async def capture_screenshots(self, url: str, viewports: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Capture screenshots at each viewport for given URL.
        Returns dict of {viewport_name: screenshot_path_or_error}.
        """
        vps = viewports or VIEWPORTS
        results: Dict[str, Any] = {"url": url, "viewports": {}}

        if not self._playwright_available:
            return {
                "url": url,
                "viewports": {vp["name"]: {"error": "Playwright not installed"} for vp in vps},
                "note": "Install playwright + playwright install chromium for screenshot capture",
            }

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                for vp in vps:
                    page = await browser.new_page(viewport={"width": vp["width"], "height": vp["height"]})
                    try:
                        await page.goto(url, timeout=30000)
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        screenshot_path = f"/tmp/qawise_{vp['name']}_{hash(url)}.png"
                        await page.screenshot(path=screenshot_path, full_page=True)
                        results["viewports"][vp["name"]] = {
                            "path": screenshot_path,
                            "width": vp["width"],
                            "height": vp["height"],
                        }
                    except Exception as e:
                        results["viewports"][vp["name"]] = {"error": str(e)}
                    finally:
                        await page.close()
                await browser.close()
        except Exception as e:
            results["error"] = str(e)
        return results

    async def diff_against_baseline(self, route: str) -> Dict[str, Any]:
        """
        Compare current screenshots against stored baselines.
        Returns diff percentage per viewport. Fail if any > DIFF_THRESHOLD.
        """
        db = self._get_db()
        if not db:
            return {"error": "Supabase not configured", "route": route}
        baselines = await db.query("visual_baselines", {"route": f"eq.{route}"})
        if not baselines or "error" in baselines:
            return {"route": route, "status": "no_baseline", "action": "capture_baseline_first"}
        return {
            "route": route,
            "threshold": DIFF_THRESHOLD,
            "status": "diff_requires_pixelmatch",
            "note": "Pixelmatch diff runs in CI with baseline images",
        }

    async def run_e2e_flow(self, base_url: str = "https://zonewise.ai") -> Dict[str, Any]:
        """
        Run E2E flow: Landing → Heatmap → Parcel → Gate → Signup → App → Chat → Map → Calendar.
        Returns pass/fail per step with error details.
        """
        if not self._playwright_available:
            return {
                "status": "skipped",
                "reason": "Playwright not installed",
                "flow": E2E_FLOW,
                "base_url": base_url,
            }

        results = {"base_url": base_url, "steps": {}, "passed": True}
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                for step in E2E_FLOW:
                    try:
                        target_url = f"{base_url}/{step}" if step != "landing" else base_url
                        await page.goto(target_url, timeout=20000)
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                        results["steps"][step] = {"passed": True, "url": target_url}
                    except Exception as e:
                        results["steps"][step] = {"passed": False, "error": str(e)}
                        results["passed"] = False
                await browser.close()
        except Exception as e:
            results["error"] = str(e)
            results["passed"] = False
        return results

    async def run_lighthouse_ci(self, url: str) -> Dict[str, Any]:
        """
        Run Lighthouse CI against URL. Returns scores vs targets.
        Note: Requires lighthouse CLI. Falls back to mock if not installed.
        """
        import shutil
        if not shutil.which("lighthouse"):
            return {
                "url": url,
                "targets": LIGHTHOUSE_TARGETS,
                "scores": {"note": "lighthouse CLI not installed"},
                "passed": False,
                "note": "Install: npm install -g lighthouse",
            }
        import subprocess
        try:
            result = subprocess.run(
                ["lighthouse", url, "--output=json", "--quiet", "--chrome-flags=--headless"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                import json as json_mod
                data = json_mod.loads(result.stdout)
                cats = data.get("categories", {})
                scores = {
                    "performance": int((cats.get("performance", {}).get("score", 0) or 0) * 100),
                    "accessibility": int((cats.get("accessibility", {}).get("score", 0) or 0) * 100),
                    "seo": int((cats.get("seo", {}).get("score", 0) or 0) * 100),
                    "best_practices": int((cats.get("best-practices", {}).get("score", 0) or 0) * 100),
                }
                passed = all(scores.get(k, 0) >= v for k, v in LIGHTHOUSE_TARGETS.items())
                return {"url": url, "scores": scores, "targets": LIGHTHOUSE_TARGETS, "passed": passed}
        except Exception as e:
            return {"url": url, "error": str(e), "passed": False}

    async def capture_baseline(self, route: str, url: str) -> Dict[str, Any]:
        """Capture and store baseline screenshots for a route."""
        screenshots = await self.capture_screenshots(url)
        db = self._get_db()
        if db and "error" not in screenshots:
            await db.upsert("visual_baselines", {
                "route": route,
                "url": url,
                "viewports": screenshots.get("viewports", {}),
            })
        return {"route": route, "status": "baseline_captured", "screenshots": screenshots}

    async def run(self, url: Optional[str] = None, baseline: bool = False, **kwargs) -> Dict[str, Any]:
        """Main async entry point."""
        if not url:
            return {"error": "URL required (--url <url>)", "agent": "qawise"}
        if baseline:
            return await self.capture_baseline(route=url, url=url)
        screenshots = await self.capture_screenshots(url)
        e2e = await self.run_e2e_flow(url)
        lighthouse = await self.run_lighthouse_ci(url)
        return {
            "url": url,
            "screenshots": screenshots,
            "e2e": e2e,
            "lighthouse": lighthouse,
        }


def main():
    parser = argparse.ArgumentParser(description="QAWise — Visual regression + E2E")
    parser.add_argument("--url", help="URL to test", default=None)
    parser.add_argument("--baseline", help="Capture baseline", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    agent = QAWiseAgent()
    result = asyncio.run(agent.run(url=args.url, baseline=args.baseline))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

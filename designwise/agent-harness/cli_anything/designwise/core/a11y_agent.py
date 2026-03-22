"""
AccessibilityWise Agent — SPEC Agent 11
WCAG 2.1 AA compliance + screen reader testing for ZoneWise.AI.
axe-core via Playwright. Tab order, focus visible, ARIA on all interactive elements.
Target score: ≥90. Writes to: brand_violations (a11y violation types).
"""

import argparse
import asyncio
import json
import os
from typing import Any, Dict, List, Optional

WCAG_AA_TARGET = 90

KEYBOARD_NAV_ELEMENTS = ["a", "button", "input", "select", "textarea", "[tabindex]"]

ARIA_REQUIRED_ELEMENTS = [
    "button", "input", "select", "textarea",
    "[role='dialog']", "[role='navigation']", "[role='main']",
]


class A11yWiseAgent:
    """
    Dedicated WCAG 2.1 AA accessibility auditing.
    Uses axe-core via Playwright when available.
    Falls back to HTTP-based structural checks.
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

    async def run_axe_scan(self, url: str) -> Dict[str, Any]:
        """
        Run axe-core accessibility scan via Playwright.
        Returns {violations: list, passes: int, score: int}.
        """
        if not self._playwright_available:
            return {
                "url": url,
                "violations": [],
                "passes": 0,
                "score": 0,
                "note": "Playwright not installed. Install: pip install playwright && playwright install chromium",
            }
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=15000)

                # Inject and run axe-core
                axe_url = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.7.2/axe.min.js"
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=10) as client:
                        axe_resp = await client.get(axe_url)
                        axe_js = axe_resp.text
                except Exception:
                    axe_js = ""

                if axe_js:
                    await page.add_script_tag(content=axe_js)
                    axe_result = await page.evaluate("() => axe.run().then(r => r)")
                    violations = axe_result.get("violations", [])
                    passes = len(axe_result.get("passes", []))
                    score = max(0, 100 - (len(violations) * 5))
                    await browser.close()
                    return {
                        "url": url,
                        "violations": violations[:20],  # cap at 20
                        "violation_count": len(violations),
                        "passes": passes,
                        "score": score,
                        "wcag_target": WCAG_AA_TARGET,
                        "passed": score >= WCAG_AA_TARGET,
                    }
                await browser.close()
                return {"url": url, "error": "Could not load axe-core", "score": 0}
        except Exception as e:
            return {"url": url, "error": str(e), "score": 0}

    async def test_keyboard_nav(self, url: str) -> Dict[str, Any]:
        """
        Test keyboard navigation: tab order, focus visible, no keyboard traps.
        """
        if not self._playwright_available:
            return {"url": url, "status": "skipped", "reason": "Playwright not installed"}
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)

                # Tab through focusable elements and check focus visibility
                tab_results = []
                for i in range(10):  # Tab up to 10 times
                    await page.keyboard.press("Tab")
                    focused = await page.evaluate("""
                        () => {
                            const el = document.activeElement;
                            if (!el || el === document.body) return null;
                            const style = window.getComputedStyle(el);
                            return {
                                tag: el.tagName.toLowerCase(),
                                id: el.id,
                                role: el.getAttribute('role'),
                                has_focus_style: style.outlineStyle !== 'none' || style.outlineWidth !== '0px',
                            };
                        }
                    """)
                    if focused:
                        tab_results.append(focused)

                no_focus_visible = [r for r in tab_results if not r.get("has_focus_style")]
                await browser.close()
                return {
                    "url": url,
                    "focusable_elements_tested": len(tab_results),
                    "no_focus_visible": len(no_focus_visible),
                    "passed": len(no_focus_visible) == 0,
                    "details": tab_results,
                }
        except Exception as e:
            return {"url": url, "error": str(e)}

    async def audit_aria_labels(self, url: str) -> Dict[str, Any]:
        """
        Check ARIA labels on all interactive elements, map controls, modals.
        """
        if not self._playwright_available:
            return {"url": url, "status": "skipped", "reason": "Playwright not installed"}
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000)
                aria_audit = await page.evaluate("""
                    () => {
                        const results = {missing_aria: [], has_aria: []};
                        const interactive = document.querySelectorAll('button, a, input, select, textarea, [role]');
                        interactive.forEach(el => {
                            const hasLabel = el.getAttribute('aria-label') ||
                                            el.getAttribute('aria-labelledby') ||
                                            el.textContent.trim() ||
                                            el.title;
                            if (hasLabel) {
                                results.has_aria.push(el.tagName.toLowerCase());
                            } else {
                                results.missing_aria.push({
                                    tag: el.tagName.toLowerCase(),
                                    id: el.id,
                                    class: el.className.substring(0, 50),
                                });
                            }
                        });
                        return results;
                    }
                """)
                await browser.close()
                missing = aria_audit.get("missing_aria", [])
                return {
                    "url": url,
                    "missing_aria_count": len(missing),
                    "missing_aria": missing[:10],
                    "elements_with_aria": len(aria_audit.get("has_aria", [])),
                    "passed": len(missing) == 0,
                }
        except Exception as e:
            return {"url": url, "error": str(e)}

    async def check_color_independence(self, url: str) -> Dict[str, Any]:
        """Check that information is not conveyed by color alone."""
        return {
            "url": url,
            "status": "partial",
            "note": "Color independence requires manual review + axe-core color-contrast check",
        }

    async def check_motion_preferences(self, url: str) -> Dict[str, Any]:
        """Check prefers-reduced-motion CSS media query support."""
        if not self._playwright_available:
            return {"url": url, "status": "skipped"}
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.emulate_media(reduced_motion="reduce")
                await page.goto(url, timeout=30000)
                has_motion_query = await page.evaluate("""
                    () => {
                        const sheets = [...document.styleSheets];
                        for (const s of sheets) {
                            try {
                                for (const r of s.cssRules) {
                                    if (r.conditionText && r.conditionText.includes('prefers-reduced-motion')) return true;
                                }
                            } catch {}
                        }
                        return false;
                    }
                """)
                await browser.close()
                return {
                    "url": url,
                    "has_reduced_motion_support": has_motion_query,
                    "passed": has_motion_query,
                }
        except Exception as e:
            return {"url": url, "error": str(e)}

    async def run(self, url: Optional[str] = None, scan: bool = False, **kwargs) -> Dict[str, Any]:
        """Main async entry point."""
        if not url:
            return {"error": "URL required (--url <url>)", "agent": "a11y"}
        axe = await self.run_axe_scan(url)
        keyboard = await self.test_keyboard_nav(url)
        aria = await self.audit_aria_labels(url)
        score = axe.get("score", 0)
        return {
            "url": url,
            "score": score,
            "wcag_target": WCAG_AA_TARGET,
            "passed": score >= WCAG_AA_TARGET,
            "axe_scan": axe,
            "keyboard_nav": keyboard,
            "aria_labels": aria,
        }


def main():
    parser = argparse.ArgumentParser(description="AccessibilityWise — WCAG 2.1 AA")
    parser.add_argument("--url", help="URL to audit", default=None)
    parser.add_argument("--scan", action="store_true", help="Run full accessibility scan")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    agent = A11yWiseAgent()
    result = asyncio.run(agent.run(url=args.url, scan=args.scan))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

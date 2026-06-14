"""
Render layer. Both Municode and American Legal are JavaScript single-page apps that
return an empty shell to plain HTTP clients (this is why web_fetch got nothing).
Headless Chromium executes the JS and gives us the real content.

This is the ONLY brittle surface in the pipeline, and it's deliberately small:
navigate -> wait for content -> dump text. Layout robustness lives in the LLM layer.
"""
import time
from playwright.sync_api import sync_playwright
from tenacity import retry, stop_after_attempt, wait_exponential
import config


def node_url(platform: str, base_url: str, node_hint: str) -> str:
    """Build the deep-link URL to a code node from the source-map locator."""
    if platform == "american_legal":
        return f"{base_url.rstrip('/')}/{node_hint}"
    # municode
    return f"{base_url}?nodeId={node_hint}"


def _extract_text(page, platform: str) -> str:
    for sel in config.CONTENT_SELECTORS.get(platform, ["body"]):
        try:
            el = page.query_selector(sel)
            if el:
                txt = el.inner_text().strip()
                if len(txt) > 400:  # got real content, not a nav stub
                    return txt
        except Exception:
            continue
    return page.inner_text("body")


@retry(stop=stop_after_attempt(config.MAX_RETRIES),
       wait=wait_exponential(multiplier=1.5, min=2, max=20))
def render_node(url: str, platform: str) -> str:
    """Return the rendered visible text of an ordinance node. Retries with backoff."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=config.USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="en-US",
        )
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=config.NAV_TIMEOUT_MS)
            page.wait_for_timeout(config.RENDER_SETTLE_MS)
            text = _extract_text(page, platform)
            if len(text) < 400:
                raise RuntimeError(f"Content too short ({len(text)} chars) — likely blocked/unrendered")
            return text
        finally:
            browser.close()
            time.sleep(config.POLITE_DELAY_S)

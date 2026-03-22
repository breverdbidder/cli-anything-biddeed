#!/usr/bin/env python3
"""
CompetitorLens — Stage 1: Firecrawl Integration
Scrapes competitor URLs → raw HTML + screenshot URL + metadata.

Environment:
    FIRECRAWL_API_KEY — Firecrawl API key (required)
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")


def _firecrawl_request(endpoint: str, payload: dict) -> dict:
    """POST to Firecrawl API with auth header."""
    if not FIRECRAWL_API_KEY:
        return {"error": "FIRECRAWL_API_KEY not set in environment"}

    url = f"{FIRECRAWL_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}: {e.reason}", "detail": error_body}
    except urllib.error.URLError as e:
        return {"error": f"URLError: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def crawl_url(url: str, include_screenshot: bool = True) -> dict:
    """
    Scrape a competitor URL via Firecrawl.

    Returns:
        {
            "url": str,
            "html": str,          # Raw HTML content
            "markdown": str,      # Cleaned markdown (Firecrawl output)
            "screenshot": str,    # Screenshot URL (if available)
            "metadata": dict,     # Title, description, etc.
            "crawled_at": str,    # ISO timestamp
        }
    """
    formats = ["html", "markdown"]
    if include_screenshot:
        formats.append("screenshot")

    payload = {
        "url": url,
        "formats": formats,
        "onlyMainContent": False,  # We want full page for layout analysis
        "includeTags": ["nav", "header", "main", "section", "aside", "footer", "table"],
        "waitFor": 2000,  # ms — wait for JS rendering
    }

    print(f"[crawl] Calling Firecrawl scrape: {url}")
    result = _firecrawl_request("/scrape", payload)

    # Handle Firecrawl v1 response envelope
    if "error" in result:
        return result

    # Firecrawl v1: result is under 'data' key
    data = result.get("data", result)

    crawl_output = {
        "url": url,
        "html": data.get("html", ""),
        "markdown": data.get("markdown", ""),
        "screenshot": data.get("screenshot", ""),
        "metadata": data.get("metadata", {}),
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }

    # Validate we got meaningful content
    html_len = len(crawl_output["html"])
    if html_len < 100:
        return {
            "error": f"HTML too short ({html_len} chars) — likely blocked or redirect",
            "url": url,
            "raw_response": result,
        }

    print(f"[crawl] OK — HTML: {html_len:,} chars, Screenshot: {'yes' if crawl_output['screenshot'] else 'no'}")
    return crawl_output


def crawl_batch(urls: list[str]) -> list[dict]:
    """Crawl multiple URLs sequentially (Firecrawl batch is paid tier)."""
    results = []
    for url in urls:
        result = crawl_url(url)
        results.append(result)
    return results


def extract_html_snapshot(crawl_result: dict, max_chars: int = 50000) -> str:
    """
    Extract a truncated HTML snapshot suitable for LLM analysis.
    Prioritizes structural elements (nav, header, main sections).
    """
    html = crawl_result.get("html", "")
    if not html:
        return crawl_result.get("markdown", "")[:max_chars]

    # Return truncated HTML — DeepSeek handles the structural extraction
    return html[:max_chars]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CompetitorLens Crawler")
    parser.add_argument("url", help="URL to crawl")
    parser.add_argument("--output", "-o", default="/tmp/cl_raw.json")
    parser.add_argument("--no-screenshot", action="store_true")
    args = parser.parse_args()

    result = crawl_url(args.url, include_screenshot=not args.no_screenshot)

    if "error" in result:
        print(f"[ERROR] {result['error']}")
        if "detail" in result:
            print(f"        {result['detail']}")
        exit(1)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nSaved to: {args.output}")
    print(f"HTML:     {len(result.get('html', '')):,} chars")
    print(f"Markdown: {len(result.get('markdown', '')):,} chars")
    print(f"Screenshot: {result.get('screenshot', 'none')}")

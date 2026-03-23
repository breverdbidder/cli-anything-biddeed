"""
test_seowise.py — SEOWise Agent (S3.3)
10 binary tests: meta tags, sitemap, structured data, Core Web Vitals.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_seowise_import():
    from cli_anything.designwise.core.seo_agent import SEOWiseAgent
    assert SEOWiseAgent is not None


def test_seowise_constants():
    from cli_anything.designwise.core.seo_agent import META_TITLE_MAX, META_DESC_MAX, CORE_WEB_VITALS_TARGETS
    assert META_TITLE_MAX == 60
    assert META_DESC_MAX == 160
    assert CORE_WEB_VITALS_TARGETS["lcp"] == 2.5
    assert CORE_WEB_VITALS_TARGETS["fid"] == 100
    assert CORE_WEB_VITALS_TARGETS["cls"] == 0.1


def test_seowise_init():
    from cli_anything.designwise.core.seo_agent import SEOWiseAgent
    agent = SEOWiseAgent(supabase_url="http://test", supabase_key="key")
    assert agent.supabase_url == "http://test"


def test_generate_sitemap_default_routes():
    """Sitemap generates XML with expected default routes."""
    from cli_anything.designwise.core.seo_agent import SEOWiseAgent
    agent = SEOWiseAgent()
    result = asyncio.run(agent.generate_sitemap())
    assert result["generated"] is True
    assert result["route_count"] >= 5
    assert "zonewise.ai" in result["sitemap_url"]


def test_generate_sitemap_custom_routes():
    """Sitemap accepts custom routes list."""
    from cli_anything.designwise.core.seo_agent import SEOWiseAgent
    agent = SEOWiseAgent()
    routes = ["/", "/explorer", "/pricing"]
    result = asyncio.run(agent.generate_sitemap(routes=routes))
    assert result["route_count"] == 3
    assert result["routes"] == routes


def test_structured_data_types():
    """Structured data returns WebApplication + Organization + Product schemas."""
    from cli_anything.designwise.core.seo_agent import SEOWiseAgent, SCHEMA_TYPES
    agent = SEOWiseAgent()
    result = asyncio.run(agent.add_structured_data())
    for schema_type in SCHEMA_TYPES:
        assert schema_type in result["schemas"]
    assert result["schemas"]["WebApplication"]["@type"] == "WebApplication"
    assert result["schemas"]["Organization"]["@type"] == "Organization"


def test_scan_meta_tags_network_error():
    """meta scan returns error dict on network failure."""
    from cli_anything.designwise.core.seo_agent import SEOWiseAgent
    agent = SEOWiseAgent()
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(side_effect=Exception("connection refused"))
        result = asyncio.run(agent.scan_meta_tags("https://localhost:0"))
    assert "error" in result or result.get("score", 0) == 0


def test_scan_meta_tags_missing_tags():
    """Meta scan flags missing title and description."""
    from cli_anything.designwise.core.seo_agent import SEOWiseAgent
    agent = SEOWiseAgent()

    class FakeResp:
        text = "<html><body>No meta here</body></html>"
        status_code = 200

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return FakeResp()

    with patch("httpx.AsyncClient", return_value=FakeClient()):
        result = asyncio.run(agent.scan_meta_tags("https://zonewise.ai"))
    violations = result.get("violations", [])
    checks_failed = [v["check"] for v in violations]
    assert "title" in checks_failed
    assert "description" in checks_failed


def test_run_requires_url_or_sitemap():
    """run() without args returns error."""
    from cli_anything.designwise.core.seo_agent import SEOWiseAgent
    agent = SEOWiseAgent()
    result = asyncio.run(agent.run())
    assert "error" in result


def test_run_sitemap_mode():
    """run(sitemap=True) returns generated sitemap."""
    from cli_anything.designwise.core.seo_agent import SEOWiseAgent
    agent = SEOWiseAgent()
    result = asyncio.run(agent.run(sitemap=True))
    assert result["generated"] is True
    assert result["route_count"] > 0

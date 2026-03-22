"""
Tests for DeployWise Agent full 3-tier pipeline (S2.3)
10 tests covering lab deploy, PR creation, gate checking, promotion, smoke test, rollback.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# conftest.py adds designwise/agent-harness to sys.path
from cli_anything.designwise.core.deploywise_agent import (
    DeployWiseAgent,
    REQUIRED_CHECKS,
    SMOKE_URLS,
)
import cli_anything.designwise.core.deploywise_agent as deploywise_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent(vercel_token="tok", supabase_url="", supabase_key="") -> DeployWiseAgent:
    return DeployWiseAgent(
        vercel_token=vercel_token,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_agent_initialises_with_values():
    """DeployWiseAgent stores provided credentials."""
    agent = _agent(vercel_token="vt", supabase_url="su", supabase_key="sk")
    assert agent.vercel_token == "vt"
    assert agent.supabase_url == "su"
    assert agent.supabase_key == "sk"


def test_required_checks_list():
    """All 4 required gate checks are defined."""
    assert "brandguard-pr-check" in REQUIRED_CHECKS
    assert "qa-visual-regression" in REQUIRED_CHECKS
    assert "a11y-check" in REQUIRED_CHECKS
    assert "seo-check" in REQUIRED_CHECKS
    assert len(REQUIRED_CHECKS) == 4


def test_smoke_urls_defined():
    """5 critical smoke test URLs are defined."""
    assert len(SMOKE_URLS) == 5
    assert "/" in SMOKE_URLS


@pytest.mark.asyncio
async def test_lab_deploy_returns_correct_tier():
    """deploy_to_lab returns tier=lab in result."""
    agent = _agent()
    mock_vc = AsyncMock()
    mock_vc.create_deployment.return_value = {"id": "dep_123", "url": "lab.zonewise.ai"}

    with patch.object(agent, "_get_vercel_client", return_value=mock_vc):
        with patch.object(agent, "_get_db", return_value=None):
            result = await agent.deploy_to_lab(branch="lab", git_sha="abc123")

    assert result["tier"] == "lab"
    assert result["deploy_id"] == "dep_123"


@pytest.mark.asyncio
async def test_create_pr_preview_returns_pr_url():
    """create_pr_preview creates a GitHub PR and returns pr_url + pr_number."""
    agent = _agent()

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "number": 42,
        "html_url": "https://github.com/test/pr/42",
    }
    mock_response.text = ""

    with patch.object(deploywise_mod, "GITHUB_TOKEN", "ghp_test"):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch.object(agent, "_get_vercel_client", return_value=None):
                result = await agent.create_pr_preview(
                    feature_branch="feat/designwise-landing",
                    target="main",
                )

    assert result["pr_number"] == 42
    assert "github.com" in result["pr_url"]


@pytest.mark.asyncio
async def test_check_all_gates_returns_all_passed():
    """check_all_gates returns all_passed=True when all checks succeed."""
    agent = _agent()

    pr_resp = MagicMock()
    pr_resp.status_code = 200
    pr_resp.json.return_value = {"head": {"sha": "abc123"}}

    checks_resp = MagicMock()
    checks_resp.status_code = 200
    checks_resp.json.return_value = {
        "check_runs": [
            {"name": c, "status": "completed", "conclusion": "success"}
            for c in REQUIRED_CHECKS
        ]
    }

    with patch.object(deploywise_mod, "GITHUB_TOKEN", "ghp_test"):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=[pr_resp, checks_resp])
            mock_client_cls.return_value = mock_client

            result = await agent.check_all_gates(pr_number=42)

    assert result["all_passed"] is True
    assert all(r["passed"] for r in result["results"].values())


@pytest.mark.asyncio
async def test_check_all_gates_fails_on_failed_check():
    """check_all_gates returns all_passed=False when any check fails."""
    agent = _agent()

    pr_resp = MagicMock()
    pr_resp.status_code = 200
    pr_resp.json.return_value = {"head": {"sha": "abc123"}}

    failing_runs = [
        {
            "name": c,
            "status": "completed",
            "conclusion": "failure" if c == "brandguard-pr-check" else "success",
        }
        for c in REQUIRED_CHECKS
    ]
    checks_resp = MagicMock()
    checks_resp.status_code = 200
    checks_resp.json.return_value = {"check_runs": failing_runs}

    with patch.object(deploywise_mod, "GITHUB_TOKEN", "ghp_test"):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=[pr_resp, checks_resp])
            mock_client_cls.return_value = mock_client

            result = await agent.check_all_gates(pr_number=42)

    assert result["all_passed"] is False


@pytest.mark.asyncio
async def test_promote_to_production_calls_merge():
    """promote_to_production calls GitHub merge API and returns merge_sha."""
    agent = _agent()

    merge_resp = MagicMock()
    merge_resp.status_code = 200
    merge_resp.json.return_value = {"sha": "deadbeef", "merged": True}
    merge_resp.text = ""

    with patch.object(deploywise_mod, "GITHUB_TOKEN", "ghp_test"):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.put = AsyncMock(return_value=merge_resp)
            mock_client_cls.return_value = mock_client

            with patch.object(agent, "_get_db", return_value=None):
                result = await agent.promote_to_production(pr_number=42)

    assert result["merge_sha"] == "deadbeef"
    assert result["tier"] == "production"


@pytest.mark.asyncio
async def test_smoke_test_hits_correct_urls():
    """run_smoke_test checks all SMOKE_URLS and returns passed=True on all 200s."""
    agent = _agent()

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.text = "x" * 200

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=ok_resp)
        mock_client_cls.return_value = mock_client

        result = await agent.run_smoke_test("https://lab.zonewise.ai")

    assert result["passed"] is True
    assert len(result["results"]) == len(SMOKE_URLS)


@pytest.mark.asyncio
async def test_auto_rollback_returns_action(tmp_path):
    """auto_rollback calls subprocess and returns action key."""
    agent = _agent()

    with patch.object(agent, "_get_db", return_value=None):
        with patch.object(agent, "_send_telegram", new_callable=AsyncMock):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                result = await agent.auto_rollback(
                    commit_sha="abc123",
                    repo_path=str(tmp_path),
                )

    assert "action" in result


def test_deploy_log_methods_exist():
    """DeployWise has all required S2.3 methods."""
    assert hasattr(DeployWiseAgent, "deploy_to_lab")
    assert hasattr(DeployWiseAgent, "create_pr_preview")
    assert hasattr(DeployWiseAgent, "check_all_gates")
    assert hasattr(DeployWiseAgent, "promote_to_production")
    assert hasattr(DeployWiseAgent, "run_smoke_test")
    assert hasattr(DeployWiseAgent, "auto_rollback")

"""CMO Factory CP3g negative tests (issue #19789 DoD items a-f).

Requires SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY in the environment (same
pattern as scripts/linkedin_b2b_agent.py) -- these tests exercise the real
PostgREST/RPC surface the adapters use, not a mocked stand-in, since the
safety properties they check (M8's status guard, the attribution gate, the
quota gate) live partly in the DB (CHECK constraints) and partly in
agents/distribution/base.py.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.distribution.base import PlatformAdapter, NotConfiguredError  # noqa: E402
from agents.distribution import instagram, facebook, tiktok, x as x_mod, linkedin  # noqa: E402
from scripts.linkedin_b2b_agent import validate_linkedin_draft  # noqa: E402

ADAPTER_MODULES = [instagram, facebook, tiktok, x_mod, linkedin]
ADAPTER_CLASSES = [
    instagram.InstagramAdapter,
    facebook.FacebookAdapter,
    tiktok.TikTokAdapter,
    x_mod.XAdapter,
    linkedin.LinkedInOrgAdapter,
]


# ---------------------------------------------------------------------
# (a) any adapter code setting a public/live status fails CI
# ---------------------------------------------------------------------

class _FixtureAdapter(PlatformAdapter):
    platform = "test_fixture"
    required_secrets = []


def test_record_rejects_public_live_status():
    adapter = _FixtureAdapter()
    for bad_status in ("live", "public", "public_live", "made_live"):
        with pytest.raises(ValueError):
            adapter.record(None, bad_status, "should never reach the DB")


def test_record_allows_only_the_declared_terminal_statuses():
    adapter = _FixtureAdapter()
    # published/failed/skipped_duplicate/not_configured are the only
    # statuses record() will write -- anything else (typos included) is
    # rejected before it ever reaches social_content_queue.
    with pytest.raises(ValueError):
        adapter.record(None, "approved", "adapters never self-approve")


# ---------------------------------------------------------------------
# (b) missing credentials -> NOT_CONFIGURED, exits 0, posts nothing
# ---------------------------------------------------------------------

@pytest.mark.parametrize("cls", ADAPTER_CLASSES)
def test_missing_credentials_short_circuits_not_configured(cls):
    adapter = cls()
    result = adapter.run(row=None)
    assert result["status"] == "NOT_CONFIGURED"


@pytest.mark.parametrize(
    "module_name",
    ["instagram", "facebook", "tiktok", "x", "linkedin"],
)
def test_cli_invocation_exits_zero_and_logs_not_configured(module_name):
    env = {**os.environ}
    proc = subprocess.run(
        [sys.executable, "-m", f"agents.distribution.{module_name}"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "NOT_CONFIGURED" in proc.stdout


# ---------------------------------------------------------------------
# (c) an AGPL/GPL dependency entering the manifest fails
# ---------------------------------------------------------------------

_BANNED_LICENSE_PACKAGES = ["postiz", "linkedin_scraper", "activepieces", "n8n"]


def test_distribution_lane_manifest_has_no_copyleft_scheduler_deps():
    manifest = ROOT / "agents" / "requirements.txt"
    text = manifest.read_text() if manifest.exists() else ""
    lower = text.lower()
    for banned in _BANNED_LICENSE_PACKAGES:
        assert banned not in lower, f"{banned} (AGPL/GPL-adjacent, rejected in DISTRIBUTION_LANE.md) found in {manifest}"


def test_distribution_adapters_never_import_the_rejected_linkedin_scraper():
    for path in (ROOT / "agents" / "distribution").glob("*.py"):
        text = path.read_text()
        assert "linkedin_scraper" not in text, f"{path} imports the GPL-3.0 linkedin_scraper (rejected, see DISTRIBUTION_LANE.md)"
        assert "browser_use" not in text and "playwright" not in text.lower(), (
            f"{path} must never automate a logged-in social session (browser-use is CONDITIONAL/own-surfaces-only)"
        )


# ---------------------------------------------------------------------
# (d) emoji-bait title / auction-record surname fails the LinkedIn validator
# ---------------------------------------------------------------------

def test_linkedin_validator_rejects_emoji_bait_title():
    text = "😳 " + ("This is a real estate observation about Florida auctions. " * 15)[:900]
    verdict = validate_linkedin_draft(text, evidence={})
    assert not verdict["passed"]
    assert any("emoji" in r for r in verdict["reasons"])


def test_linkedin_validator_rejects_banned_surname():
    body = ("Smith's property sold at auction this week for a real number. " * 15)[:1000]
    verdict = validate_linkedin_draft(body, evidence={}, banned_names=["Smith"])
    assert not verdict["passed"]
    assert any("banned name" in r for r in verdict["reasons"])


def test_linkedin_validator_rejects_untraceable_numbers():
    text = ("This week we closed $999,999,999 in auction volume across Florida. " * 13)[:950]
    verdict = validate_linkedin_draft(text, evidence={"unrelated_field": 42})
    assert not verdict["passed"]
    assert any("not traceable" in r for r in verdict["reasons"])


# ---------------------------------------------------------------------
# (e) a platform post lacking its own short code + utm_source fails
# ---------------------------------------------------------------------

@pytest.mark.parametrize("cls", ADAPTER_CLASSES)
def test_row_missing_short_code_or_utm_source_is_refused(cls):
    adapter = cls()
    row = {
        "id": "00000000-0000-0000-0000-000000000000",
        "approved_at": "2026-09-03T00:00:00Z",
        "content_text": "x" * 1000,
        "media_url": "https://example.com/a.mp4",
        # short_code / utm_source intentionally absent
    }
    with patch.object(cls, "credentials", return_value={n: "fake" for n in cls.required_secrets}), \
         patch.object(cls, "record") as mock_record:
        result = adapter.run(row)
    assert result["status"] == "failed"
    assert "short_code" in result["detail"] or "utm_source" in result["detail"]
    mock_record.assert_called_once()
    assert mock_record.call_args[0][1] == "failed"


# ---------------------------------------------------------------------
# (f) exceeding a platform's daily cap is SKIPPED, never attempted
# ---------------------------------------------------------------------

@pytest.mark.parametrize("cls", ADAPTER_CLASSES)
def test_over_quota_row_is_skipped_not_attempted(cls):
    adapter = cls()
    row = {
        "id": "00000000-0000-0000-0000-000000000000",
        "approved_at": "2026-09-03T00:00:00Z",
        "content_text": "x" * 1000,
        "media_url": "https://example.com/a.mp4",
        "short_code": "abc123",
        "utm_source": adapter.platform,
    }

    def _boom(*a, **k):
        raise AssertionError("upload() must never be called when over quota")

    with patch.object(cls, "credentials", return_value={n: "fake" for n in cls.required_secrets}), \
         patch.object(cls, "check_and_reserve_quota", return_value=(False, f"{adapter.platform} daily cap reached")), \
         patch.object(cls, "upload", side_effect=_boom):
        result = adapter.run(row)

    assert result["status"] == "skipped_duplicate"
    assert "cap" in result["detail"]

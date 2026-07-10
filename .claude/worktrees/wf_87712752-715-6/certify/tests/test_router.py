"""
Unit tests for certify/router.py

Tests the four DoD invariants:
1. Gate FAIL can never yield final_certify=True
2. No model tier can emit certify (authority always 'gate')
3. Malformed screen JSON → escalate (never clean)
4. Forced shadow disagreement → auto-tighten + Sentinel alert
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from certify.router import (
    CertDecision,
    GateResult,
    ScreenResult,
    _parse_screen,
    route,
)


# ---------------------------------------------------------------------------
# 1. Gate FAIL → final_certify=False always
# ---------------------------------------------------------------------------
class TestGateFailNeverCertifies(unittest.TestCase):

    def _make_fail_gate(self):
        return GateResult(
            pass_count=7,
            verdict="fail",
            letters={"A": True, "B": False, "C": True, "D": True,
                     "E": True, "F": True, "G": False, "H": True,
                     "I": False, "J": True},
            detail={ltr: {"metric": None, "detail": ""} for ltr in "ABCDEFGHIJ"},
        )

    @patch("certify.router._run_gate")
    @patch("certify.router._run_opus_review")
    @patch("certify.router._persist_trail")
    def test_gate_fail_yields_not_certified(self, mock_persist, mock_opus, mock_gate):
        mock_gate.return_value = self._make_fail_gate()
        mock_opus.return_value = ("Gate fail diagnosis", 500, 100)
        mock_persist.return_value = None

        cfg = {
            "haiku_confidence_floor": 0.90,
            "sonnet_confidence_floor": 0.85,
            "shadow_audit_rate": 0.0,
            "min_tier": "haiku",
        }
        dec = route("test_county", "run-test-001", cfg)

        self.assertFalse(dec.final_certify,
                         "Gate FAIL must never yield final_certify=True")
        self.assertEqual(dec.final_tier, "gate_fail")
        self.assertTrue(dec.t3_invoked)

    @patch("certify.router._run_gate")
    @patch("certify.router._run_opus_review")
    @patch("certify.router._persist_trail")
    def test_gate_fail_skips_haiku_sonnet(self, mock_persist, mock_opus, mock_gate):
        mock_gate.return_value = self._make_fail_gate()
        mock_opus.return_value = ("diag", 100, 50)
        mock_persist.return_value = None

        with patch("certify.router._call_screen") as mock_screen:
            cfg = {
                "haiku_confidence_floor": 0.90,
                "sonnet_confidence_floor": 0.85,
                "shadow_audit_rate": 0.0,
                "min_tier": "haiku",
            }
            route("test_county", "run-test-002", cfg)
            mock_screen.assert_not_called()


# ---------------------------------------------------------------------------
# 2. authority='gate' always; screens cannot certify
# ---------------------------------------------------------------------------
class TestAuthorityAlwaysGate(unittest.TestCase):

    def _make_pass_gate(self):
        return GateResult(
            pass_count=10,
            verdict="pass",
            letters={ltr: True for ltr in "ABCDEFGHIJ"},
            detail={ltr: {"metric": 97.0, "detail": "ok"} for ltr in "ABCDEFGHIJ"},
        )

    @patch("certify.router._run_gate")
    @patch("certify.router._call_screen")
    @patch("certify.router._persist_trail")
    def test_t1_cert_authority_is_gate(self, mock_persist, mock_screen, mock_gate):
        mock_gate.return_value = self._make_pass_gate()
        mock_screen.return_value = ScreenResult(
            verdict="clean", confidence=0.95, reason="no anomalies",
            raw='{"verdict":"clean","confidence":0.95,"reason":"no anomalies"}',
            tokens_in=800, tokens_out=150,
        )
        mock_persist.return_value = None

        cfg = {
            "haiku_confidence_floor": 0.90,
            "sonnet_confidence_floor": 0.85,
            "shadow_audit_rate": 0.0,
            "min_tier": "haiku",
        }
        dec = route("brevard", "run-auth-001", cfg)

        self.assertEqual(dec.authority, "gate",
                         "authority must always be 'gate'")
        self.assertTrue(dec.final_certify)
        self.assertEqual(dec.final_tier, "t1")

    @patch("certify.router._run_gate")
    @patch("certify.router._call_screen")
    @patch("certify.router._persist_trail")
    def test_t2_cert_authority_is_gate(self, mock_persist, mock_screen, mock_gate):
        mock_gate.return_value = self._make_pass_gate()
        # T1 escalates, T2 cleans
        mock_screen.side_effect = [
            ScreenResult(verdict="escalate", confidence=0.70, reason="anomaly flag",
                         raw="{}", tokens_in=800, tokens_out=100),
            ScreenResult(verdict="clean", confidence=0.90, reason="resolved",
                         raw="{}", tokens_in=800, tokens_out=120),
        ]
        mock_persist.return_value = None

        cfg = {
            "haiku_confidence_floor": 0.90,
            "sonnet_confidence_floor": 0.85,
            "shadow_audit_rate": 0.0,
            "min_tier": "haiku",
        }
        dec = route("duval", "run-auth-002", cfg)

        self.assertEqual(dec.authority, "gate")
        self.assertTrue(dec.final_certify)
        self.assertEqual(dec.final_tier, "t2")


# ---------------------------------------------------------------------------
# 3. Malformed JSON → escalate (never clean)
# ---------------------------------------------------------------------------
class TestMalformedScreenParsing(unittest.TestCase):

    def test_missing_verdict_key(self):
        raw = '{"confidence": 0.95, "reason": "ok"}'
        result = _parse_screen(raw, tokens_in=800, tokens_out=100)
        self.assertEqual(result.verdict, "escalate")
        self.assertFalse(result.parse_ok)

    def test_invalid_verdict_value(self):
        raw = '{"verdict": "pass", "confidence": 0.95, "reason": "ok"}'
        result = _parse_screen(raw, tokens_in=800, tokens_out=100)
        self.assertEqual(result.verdict, "escalate")
        self.assertFalse(result.parse_ok)

    def test_confidence_out_of_range(self):
        raw = '{"verdict": "clean", "confidence": 1.5, "reason": "ok"}'
        result = _parse_screen(raw, tokens_in=800, tokens_out=100)
        self.assertEqual(result.verdict, "escalate")
        self.assertFalse(result.parse_ok)

    def test_empty_response(self):
        result = _parse_screen("", tokens_in=0, tokens_out=0)
        self.assertEqual(result.verdict, "escalate")
        self.assertFalse(result.parse_ok)

    def test_plain_text_response(self):
        raw = "The gate results look clean to me, I would certify this county."
        result = _parse_screen(raw, tokens_in=800, tokens_out=50)
        self.assertEqual(result.verdict, "escalate",
                         "Plain text (not JSON) must always escalate")
        self.assertFalse(result.parse_ok)

    def test_markdown_fenced_valid_json(self):
        raw = '```json\n{"verdict": "clean", "confidence": 0.92, "reason": "all good"}\n```'
        result = _parse_screen(raw, tokens_in=800, tokens_out=120)
        self.assertEqual(result.verdict, "clean")
        self.assertTrue(result.parse_ok)
        self.assertAlmostEqual(result.confidence, 0.92)

    def test_valid_escalate_response(self):
        raw = '{"verdict": "escalate", "confidence": 0.88, "reason": "B metric >100%"}'
        result = _parse_screen(raw, tokens_in=800, tokens_out=100)
        self.assertEqual(result.verdict, "escalate")
        self.assertTrue(result.parse_ok)

    def test_null_confidence(self):
        raw = '{"verdict": "clean", "confidence": null, "reason": "ok"}'
        result = _parse_screen(raw, tokens_in=800, tokens_out=100)
        self.assertEqual(result.verdict, "escalate")
        self.assertFalse(result.parse_ok)


# ---------------------------------------------------------------------------
# 4. Shadow disagreement → auto-tighten + Sentinel
# ---------------------------------------------------------------------------
class TestShadowAuditTighten(unittest.TestCase):

    @patch("certify.router._sb_rpc")
    @patch("certify.router._sb_post")
    @patch("certify.router._sb_patch")
    @patch("certify.router._run_opus_review")
    def test_disagreement_triggers_tighten_and_sentinel(
        self, mock_opus, mock_patch, mock_post, mock_rpc
    ):
        from certify.router import GateResult, _shadow_audit_sample

        gate = GateResult(
            pass_count=10, verdict="pass",
            letters={ltr: True for ltr in "ABCDEFGHIJ"},
            detail={ltr: {"metric": 97.0, "detail": "ok"} for ltr in "ABCDEFGHIJ"},
        )
        # Opus says "anomaly detected" — disagrees with cheap-path cert
        mock_opus.return_value = ("Anomaly detected: B metric looks suspicious", 900, 200)

        result = _shadow_audit_sample(
            trail_id=999,
            county_slug="test_county",
            run_id="run-shadow-001",
            gate=gate,
        )

        # Should disagree
        self.assertFalse(result, "Opus disagreement should return False")

        # certify_shadow_tighten must be called
        mock_rpc.assert_called_once_with("certify_shadow_tighten", {})

        # Sentinel alert must be posted
        sentinel_calls = [
            c for c in mock_post.call_args_list
            if c[0][0] == "sentinel_alerts"
        ]
        self.assertGreater(len(sentinel_calls), 0,
                           "Sentinel alert must be posted on shadow disagreement")

    @patch("certify.router._sb_rpc")
    @patch("certify.router._sb_post")
    @patch("certify.router._sb_patch")
    @patch("certify.router._run_opus_review")
    def test_agreement_no_tighten(self, mock_opus, mock_patch, mock_post, mock_rpc):
        from certify.router import GateResult, _shadow_audit_sample

        gate = GateResult(
            pass_count=10, verdict="pass",
            letters={ltr: True for ltr in "ABCDEFGHIJ"},
            detail={ltr: {"metric": 97.0, "detail": "ok"} for ltr in "ABCDEFGHIJ"},
        )
        mock_opus.return_value = ("No anomaly detected. Certify.", 900, 150)

        result = _shadow_audit_sample(999, "brevard", "run-shadow-002", gate)

        self.assertTrue(result)
        mock_rpc.assert_not_called()


if __name__ == "__main__":
    unittest.main()

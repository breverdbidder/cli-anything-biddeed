#!/usr/bin/env python3
"""
signal_detector.py — Deployment Failure Signal Detector
Issue: breverdbidder/cli-anything-biddeed#101

Adapted from JiuwenClaw's failure detection patterns, focused on English
deployment error patterns: Vercel build errors, 503 responses, missing
NEXT_DATA values, and infrastructure failures.

Distinct from evolution/signal_detector.py (which targets skill eval regressions).
This module targets deployment health: HTTP, DOM, JS runtime, CDN errors.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from verify_deployment import CheckResult, VerifyResult


# ── Signal Types ──────────────────────────────────────────────────────────────

class DeploySignalType(str, Enum):
    HTTP_ERROR = "http_error"           # 4xx/5xx response
    SLOW_LOAD = "slow_load"             # Load time > threshold
    BUILD_ERROR = "build_error"         # Vercel/Next.js build failure in DOM
    SELECTOR_MISSING = "selector_missing"  # Expected element not found
    HYDRATION_FAILURE = "hydration_failure"  # __NEXT_DATA__ missing
    CDN_MISS = "cdn_miss"               # CDN/edge error headers
    PLAYWRIGHT_ERROR = "playwright_error"   # Browser-level failure
    HEALTHY = "healthy"                 # No signals — all clear


# ── Patterns (ported + extended from JiuwenClaw) ─────────────────────────────

# DOM text patterns that indicate build/runtime failure
_BUILD_ERROR_PATTERNS = [
    re.compile(r"application error", re.IGNORECASE),
    re.compile(r"internal server error", re.IGNORECASE),
    re.compile(r"this page could not be found", re.IGNORECASE),
    re.compile(r"500\s*internal", re.IGNORECASE),
    re.compile(r"build\s+failed", re.IGNORECASE),
    re.compile(r"DEPLOYMENT_ERROR", re.IGNORECASE),
    re.compile(r"getServerSideProps.*failed", re.IGNORECASE | re.DOTALL),
    re.compile(r"Unhandled Runtime Error", re.IGNORECASE),
    re.compile(r"ChunkLoadError", re.IGNORECASE),
    re.compile(r"ENOENT.*page", re.IGNORECASE),
]

# HTTP status codes that indicate deployment problems
_HTTP_ERROR_CODES = {400, 401, 403, 404, 500, 502, 503, 504, 520, 521, 522, 524}

# CDN/edge-layer signals in response headers (checked via page URL changes)
_CDN_ERROR_PATTERNS = [
    re.compile(r"cloudflare.*error", re.IGNORECASE),
    re.compile(r"vercel.*error", re.IGNORECASE),
    re.compile(r"origin\s+unreachable", re.IGNORECASE),
    re.compile(r"524\s+a\s+timeout", re.IGNORECASE),
]

# Load time thresholds (ms)
LOAD_WARN_MS = 5_000
LOAD_FAIL_MS = 8_000


# ── Signal Dataclass ──────────────────────────────────────────────────────────

@dataclass
class DeploySignal:
    signal_type: DeploySignalType
    url: str
    severity: str           # "critical" | "warning" | "info"
    message: str
    evidence: str           # What triggered detection
    check_name: Optional[str] = None  # Which CheckResult failed
    auto_repairable: bool = False     # Whether auto_repair.py can fix this

    def to_dict(self) -> dict:
        return {
            "signal_type": self.signal_type.value,
            "url": self.url,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
            "check_name": self.check_name,
            "auto_repairable": self.auto_repairable,
        }


# ── Detector ──────────────────────────────────────────────────────────────────

class DeploymentSignalDetector:
    """
    Analyzes VerifyResult objects and extracts actionable deployment signals.

    Usage:
        detector = DeploymentSignalDetector()
        signals = detector.detect(verify_result)
        for sig in signals:
            print(sig.severity, sig.message)
    """

    def detect(self, result: VerifyResult) -> list[DeploySignal]:
        """Detect all deployment signals from a VerifyResult."""
        signals: list[DeploySignal] = []

        # ── Playwright/browser-level errors ──────────────────────────────────
        for err in result.errors:
            signals.append(DeploySignal(
                signal_type=DeploySignalType.PLAYWRIGHT_ERROR,
                url=result.url,
                severity="critical",
                message=f"Browser error during verification",
                evidence=err[:200],
                auto_repairable=False,
            ))

        # ── HTTP status ──────────────────────────────────────────────────────
        if result.http_code in _HTTP_ERROR_CODES:
            is_server_error = result.http_code >= 500
            signals.append(DeploySignal(
                signal_type=DeploySignalType.HTTP_ERROR,
                url=result.url,
                severity="critical" if is_server_error else "warning",
                message=f"HTTP {result.http_code} response",
                evidence=f"HTTP status code: {result.http_code}",
                check_name="http_status",
                auto_repairable=is_server_error,  # 5xx may be auto-repairable
            ))

        # ── Per-check analysis ────────────────────────────────────────────────
        failed_checks = {c.name: c for c in result.checks if not c.passed}

        if "http_status" in failed_checks:
            pass  # Already handled above

        if "load_time" in failed_checks:
            severity = "critical" if result.load_ms > LOAD_FAIL_MS else "warning"
            signals.append(DeploySignal(
                signal_type=DeploySignalType.SLOW_LOAD,
                url=result.url,
                severity=severity,
                message=f"Slow page load: {result.load_ms:.0f}ms",
                evidence=f"Load time {result.load_ms:.0f}ms exceeds {LOAD_FAIL_MS}ms threshold",
                check_name="load_time",
                auto_repairable=False,
            ))

        if "next_hydration" in failed_checks:
            signals.append(DeploySignal(
                signal_type=DeploySignalType.HYDRATION_FAILURE,
                url=result.url,
                severity="critical",
                message="Next.js hydration failed — __NEXT_DATA__ missing",
                evidence="window.__NEXT_DATA__ evaluated to falsy",
                check_name="next_hydration",
                auto_repairable=False,
            ))

        if "no_vercel_error" in failed_checks:
            signals.append(DeploySignal(
                signal_type=DeploySignalType.BUILD_ERROR,
                url=result.url,
                severity="critical",
                message="Vercel build/runtime error detected in page body",
                evidence=failed_checks["no_vercel_error"].detail,
                check_name="no_vercel_error",
                auto_repairable=True,
            ))

        # ── Selector failures ─────────────────────────────────────────────────
        selector_failures = [name for name in failed_checks if name.startswith("selector:")]
        for name in selector_failures:
            sel = name.split("selector:", 1)[1]
            signals.append(DeploySignal(
                signal_type=DeploySignalType.SELECTOR_MISSING,
                url=result.url,
                severity="warning",
                message=f"Expected element not found: {sel}",
                evidence=failed_checks[name].detail,
                check_name=name,
                auto_repairable=False,
            ))

        # ── No signals → healthy ──────────────────────────────────────────────
        if not signals:
            signals.append(DeploySignal(
                signal_type=DeploySignalType.HEALTHY,
                url=result.url,
                severity="info",
                message="All checks passed — deployment healthy",
                evidence=f"{len(result.checks)} checks passed, HTTP {result.http_code}, {result.load_ms:.0f}ms",
                auto_repairable=False,
            ))

        return signals

    def classify_batch(self, results: list[VerifyResult]) -> dict[str, list[DeploySignal]]:
        """Classify a batch of results. Returns {url: [signals]}."""
        return {r.url: self.detect(r) for r in results}

    def critical_signals(self, signals: list[DeploySignal]) -> list[DeploySignal]:
        """Filter to only critical severity signals."""
        return [s for s in signals if s.severity == "critical"]

    def needs_issue(self, signals: list[DeploySignal]) -> bool:
        """True if any critical signal warrants a SUMMIT issue."""
        return any(s.severity == "critical" for s in signals)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Analyze a verify_deployment JSON result for signals")
    parser.add_argument("result_file", help="Path to JSON output from verify_deployment.py --json")
    parser.add_argument("--critical-only", action="store_true")
    args = parser.parse_args()

    with open(args.result_file) as f:
        raw_results = json.load(f)

    detector = DeploymentSignalDetector()
    all_signals: list[DeploySignal] = []

    for r in raw_results:
        # Reconstruct minimal VerifyResult from JSON
        vr = VerifyResult(
            url=r["url"],
            status=r["status"],
            http_code=r["http_code"],
            load_ms=r["load_ms"],
            verified_at=r.get("verified_at", ""),
        )
        vr.checks = [CheckResult(name=c["name"], passed=c["passed"], detail=c["detail"]) for c in r.get("checks", [])]
        vr.errors = r.get("errors", [])

        sigs = detector.detect(vr)
        if args.critical_only:
            sigs = detector.critical_signals(sigs)
        all_signals.extend(sigs)

    print(json.dumps([s.to_dict() for s in all_signals], indent=2))
    sys.exit(1 if any(s.severity == "critical" for s in all_signals) else 0)

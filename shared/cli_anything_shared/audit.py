"""Audit logging for CLI-Anything BidDeed tools.

Logs every command invocation to Supabase audit_log table.
Graceful failure: if Supabase unavailable, logs to stderr.
"""

import functools
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from typing import Callable, Optional


def _hash_args(args: tuple, kwargs: dict) -> str:
    """Create a short hash of command arguments for audit trail."""
    raw = json.dumps({"args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in kwargs.items()}}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def log_audit(
    cli: str,
    command: str,
    duration_ms: int,
    result_summary: str = "",
    cost_usd: float = 0.0,
    user: str = "local",
    args_hash: str = "",
) -> Optional[dict]:
    """Write an audit log entry to Supabase. Returns row or None on failure."""
    entry = {
        "cli": cli,
        "command": command,
        "args_hash": args_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_ms": duration_ms,
        "cost_usd": cost_usd,
        "result_summary": result_summary[:500],  # Truncate
        "user": user,
    }
    try:
        from .supabase import persist_result
        return persist_result("audit_log", entry, cli_name=cli.replace("cli-anything-", ""))
    except Exception as e:
        print(f"[audit] Failed to log: {e}", file=sys.stderr)
        return None


def audit_logged(cli_name: str = ""):
    """Decorator factory for Click commands. Logs invocation to audit_log.

    Usage:
        @cli.command()
        @audit_logged("cli-anything-auction")
        @click.argument("case")
        def analyze(case):
            ...

    Or without args (cli_name derived from function):
        @audit_logged()
        def analyze(case):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result_summary = ""
            try:
                result = func(*args, **kwargs)
                result_summary = "success"
                return result
            except Exception as e:
                result_summary = f"error: {type(e).__name__}: {str(e)[:200]}"
                raise
            finally:
                duration_ms = int((time.time() - start) * 1000)
                effective_cli = cli_name or f"cli-anything-{func.__module__.split('.')[-2] if '.' in (func.__module__ or '') else 'unknown'}"
                log_audit(
                    cli=effective_cli,
                    command=func.__name__,
                    duration_ms=duration_ms,
                    result_summary=result_summary,
                    args_hash=_hash_args(args, kwargs),
                )
        return wrapper
    return decorator

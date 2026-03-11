"""Cost tracking and budget enforcement for CLI-Anything BidDeed tools.

Tracks LLM token usage and costs per invocation. Enforces budgets.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# Pricing per 1M tokens (USD)
PRICING = {
    "claude-sonnet-4.5": {"input": 3.00, "output": 15.00},
    "claude-opus-4.6": {"input": 5.00, "output": 25.00},
    "gemini-2.5-flash": {"input": 0.00, "output": 0.00},  # Free tier
    "deepseek-v3.2": {"input": 0.28, "output": 0.42},
}

DEFAULT_BUDGET = 1.00  # USD per command


class BudgetExceeded(Exception):
    """Raised when cost exceeds budget."""
    pass


@dataclass
class CostEntry:
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    timestamp: str


@dataclass
class CostTracker:
    """Track LLM costs within a command invocation.

    Usage:
        tracker = CostTracker(budget=1.00, cli="auction", command="analyze")
        tracker.log(model="claude-sonnet-4.5", tokens_in=500, tokens_out=200)
        tracker.enforce_budget()  # raises BudgetExceeded if over
        summary = tracker.summary()
    """
    budget: float = DEFAULT_BUDGET
    cli: str = ""
    command: str = ""
    entries: list = field(default_factory=list)
    _start_time: float = field(default_factory=time.time)

    def log(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Log a single LLM call. Returns cost in USD."""
        pricing = PRICING.get(model, {"input": 3.00, "output": 15.00})
        cost = (tokens_in * pricing["input"] / 1_000_000) + (tokens_out * pricing["output"] / 1_000_000)
        entry = CostEntry(
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost, 6),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.entries.append(entry)
        return cost

    @property
    def total_cost(self) -> float:
        return round(sum(e.cost_usd for e in self.entries), 6)

    @property
    def total_tokens_in(self) -> int:
        return sum(e.tokens_in for e in self.entries)

    @property
    def total_tokens_out(self) -> int:
        return sum(e.tokens_out for e in self.entries)

    def enforce_budget(self) -> None:
        """Raise BudgetExceeded if total cost exceeds budget."""
        if self.total_cost > self.budget:
            raise BudgetExceeded(
                f"Budget exceeded: ${self.total_cost:.4f} > ${self.budget:.2f} "
                f"({len(self.entries)} calls, {self.total_tokens_in + self.total_tokens_out} tokens)"
            )

    def summary(self) -> dict:
        """Return cost summary as dict (for JSON output / Supabase logging)."""
        return {
            "cli": self.cli,
            "command": self.command,
            "budget_usd": self.budget,
            "total_cost_usd": self.total_cost,
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "calls": len(self.entries),
            "duration_ms": int((time.time() - self._start_time) * 1000),
            "entries": [
                {"model": e.model, "tokens_in": e.tokens_in, "tokens_out": e.tokens_out, "cost_usd": e.cost_usd}
                for e in self.entries
            ],
        }

    def persist(self, cli_name: str = "shared") -> Optional[dict]:
        """Log cost summary to Supabase daily_quota_usage. Fails gracefully."""
        try:
            from .supabase import persist_result
            return persist_result("daily_quota_usage", self.summary(), cli_name)
        except Exception as e:
            import sys
            print(f"[cost] Failed to persist: {e}", file=sys.stderr)
            return None

    def __enter__(self):
        self._start_time = time.time()
        return self

    def __exit__(self, *args):
        pass

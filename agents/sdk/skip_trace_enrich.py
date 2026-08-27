"""Claude Agent SDK example: single-shot skip-trace enrichment via the Tracerfy MCP server.

Per MAS_SOP_ADDENDUM_A.md §A.7 step 2 — code-complete, network-inert by default.
Every live call is gated behind TRACERFY_LIVE=1 (default off) so importing or
constructing this module never touches the Tracerfy connector/API, which is
blocked pending founder-funded credits (Addendum A §A.7 blocking gate).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from claude_agent_sdk.types import McpHttpServerConfig

TRACERFY_LIVE = os.environ.get("TRACERFY_LIVE", "0") == "1"


@dataclass
class SkipTraceResult:
    subject_query: str
    live: bool
    summary: str


def _tracerfy_mcp_config() -> McpHttpServerConfig:
    """Build the tracerfy MCP server config from env, mirroring .mcp.json §A.3.

    Does not connect — the SDK only opens the MCP session when a query() call
    actually runs, which only happens under the TRACERFY_LIVE gate below.
    """
    return McpHttpServerConfig(type="http", url=os.environ["TRACERFY_MCP_URL"])


def _build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        mcp_servers={"tracerfy": _tracerfy_mcp_config()},
        allowed_tools=["mcp__tracerfy"],
        system_prompt=(
            "You are a D2 Data skip-trace subagent. Use the tracerfy MCP tools "
            "to resolve the subject to current contact records. Return a "
            "concise summary only — no raw PII beyond what the caller asked for."
        ),
        max_turns=4,
        permission_mode="bypassPermissions",
    )


async def enrich_skip_trace(subject_query: str) -> SkipTraceResult:
    """Run one skip-trace lookup for `subject_query` (e.g. "Jane Doe, 123 Main St, Brevard FL").

    Network-inert unless TRACERFY_LIVE=1: the founder gate for Tracerfy credits
    is open (Addendum A §A.7), so this returns a stub result instead of calling
    the vendor MCP.
    """
    if not TRACERFY_LIVE:
        return SkipTraceResult(
            subject_query=subject_query,
            live=False,
            summary="TRACERFY_LIVE unset — skipped live MCP call (credits gate not yet funded).",
        )

    options = _build_options()
    summary_parts: list[str] = []
    async for message in query(prompt=f"Skip-trace lookup: {subject_query}", options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    summary_parts.append(block.text)
        elif isinstance(message, ResultMessage):
            break

    return SkipTraceResult(
        subject_query=subject_query,
        live=True,
        summary="\n".join(summary_parts).strip(),
    )


def main() -> None:
    result = asyncio.run(enrich_skip_trace("example subject — dry run"))
    print(result)


if __name__ == "__main__":
    main()

"""CLI Integration — bridges click commands to ToolRegistry agents.

Provides run_tool() helper that click commands use instead of direct core imports.
Every CLI command gets automatic: permission gating, logging, metrics, timing.

Usage in CLI:
    from cli_anything_shared.cli_integration import create_agent, run_tool

    _agent = create_agent("zonewise", permission="workspace-write")

    @county.command("list")
    def county_list(state):
        result = run_tool(_agent, "zonewise_county_list", state=state)
        output(result)
"""

import click
from typing import Any, Optional

from .tool_registry import PermissionMode
from .agent_base import AgentBase


_PERMISSION_MAP = {
    "read-only": PermissionMode.READ_ONLY,
    "workspace-write": PermissionMode.WORKSPACE_WRITE,
    "danger-full-access": PermissionMode.DANGER_FULL,
}


def create_agent(agent_name: str, permission: str = "read-only") -> AgentBase:
    """Create an agent by name with the specified permission level.

    Args:
        agent_name: One of 'zonewise', 'auction', 'spatial', 'swimintel'.
        permission: Permission string ('read-only', 'workspace-write', 'danger-full-access').

    Returns:
        Initialized agent with tools registered.
    """
    from .agents import ALL_AGENTS
    perm = _PERMISSION_MAP.get(permission, PermissionMode.READ_ONLY)
    agent_cls = ALL_AGENTS.get(agent_name)
    if not agent_cls:
        raise ValueError(f"Unknown agent: {agent_name}. Available: {list(ALL_AGENTS.keys())}")
    return agent_cls(permission=perm)


def run_tool(agent: AgentBase, tool_name: str, **kwargs: Any) -> Any:
    """Execute a tool through the agent's registry and return the result.

    On success: returns the result dict directly (unwrapped from ToolResult).
    On failure: raises click.ClickException with the error message.

    This is the bridge between click commands and the ToolRegistry.
    """
    result = agent.execute_tool(tool_name, kwargs)
    if result.ok:
        return result.result
    raise click.ClickException(result.error)


def print_agent_status(agent: AgentBase) -> None:
    """Print agent status including metrics. Useful for /status commands."""
    import json
    status = agent.status()
    metrics = status.pop("metrics", {})
    click.echo(f"Agent: {status['agent']}")
    click.echo(f"Permission: {status['permission']}")
    click.echo(f"Tools: {status['tools_available']}/{status['tools_registered']} available")
    click.echo(f"Messages: {status['messages']} ({status['estimated_tokens']} est. tokens)")
    click.echo(f"Uptime: {status['uptime_seconds']}s")
    if metrics.get("total_calls"):
        click.echo(f"Calls: {metrics['total_calls']} (errors: {metrics['total_errors']}, denials: {metrics['total_denials']})")

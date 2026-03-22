"""
UTCC Classifier — keyword-based task routing.

Maps task descriptions to executor types and target platforms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TaskRoute:
    task_type: str       # logical type label stored in task_registry
    platform: str        # compute platform: hetzner | gha | modal
    workflow: str        # GHA workflow filename to dispatch (empty = Hetzner direct)
    dispatch_type: str   # repository_dispatch type value


# Order matters — first match wins
ROUTING_TABLE: list[tuple[re.Pattern, TaskRoute]] = [
    # Modal spatial / data conquest
    (
        re.compile(r"\b(conquer|conquest|modal|spatial|ingest|county)\b", re.I),
        TaskRoute("modal_conquest", "modal", "modal-spatial.yml", "modal-conquest"),
    ),
    # YouTube / transcript analysis
    (
        re.compile(r"\b(transcript|youtube|yt|video|watch)\b", re.I),
        TaskRoute("transcript", "hetzner", "summit-transcript.yml", "transcript"),
    ),
    # Sentinel / health monitoring
    (
        re.compile(r"\b(sentinel|health|monitor|watchdog|alert|ping)\b", re.I),
        TaskRoute("sentinel", "gha", "sentinel.yml", "sentinel"),
    ),
    # ZoneWise / zoning data
    (
        re.compile(r"\b(zonewise|zone|zoning|parcel|land.?use)\b", re.I),
        TaskRoute("zonewise", "hetzner", "summit-zonewise.yml", "zonewise"),
    ),
    # Competitor intelligence
    (
        re.compile(r"\b(competitor|competitorlens|comp.?intel|rival)\b", re.I),
        TaskRoute("competitorlens", "hetzner", "summit-competitorlens.yml", "competitorlens"),
    ),
    # Auction / foreclosure data
    (
        re.compile(r"\b(auction|foreclosure|brief|morning.?brief)\b", re.I),
        TaskRoute("auction", "gha", "auction-morning.yml", "auction-brief"),
    ),
    # Deploy / build tasks
    (
        re.compile(r"\b(deploy|build|publish|release)\b", re.I),
        TaskRoute("deploy", "gha", "dispatch-gha.yml", "gha-dispatch"),
    ),
]

# Default route when no keyword matches
DEFAULT_ROUTE = TaskRoute("gha_executor", "gha", "dispatch-gha.yml", "gha-dispatch")


def classify_task(task: str) -> TaskRoute:
    """
    Classify a task description and return a TaskRoute.

    Args:
        task: Natural language task description or prompt.

    Returns:
        TaskRoute with task_type, platform, workflow, and dispatch_type.

    Example:
        >>> r = classify_task("Run county conquer for Brevard")
        >>> r.task_type
        'modal_conquest'
    """
    for pattern, route in ROUTING_TABLE:
        if pattern.search(task):
            return route
    return DEFAULT_ROUTE


def classify_batch(tasks: list[str]) -> list[TaskRoute]:
    """Classify multiple tasks, returning one route per task."""
    return [classify_task(t) for t in tasks]


def route_summary(task: str) -> str:
    """Human-readable routing summary for a task."""
    r = classify_task(task)
    return (
        f"type={r.task_type} platform={r.platform} "
        f"workflow={r.workflow} dispatch={r.dispatch_type}"
    )

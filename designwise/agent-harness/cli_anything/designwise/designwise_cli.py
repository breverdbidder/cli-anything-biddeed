"""
DesignWise Squad — CLI Entry Point.
13 AI agents for ZoneWise.AI UI lifecycle.
Usage: python -m cli_anything.designwise.designwise_cli [agent] [args]
"""

import argparse
import sys
import json
import importlib
import os


AGENTS = {
    "commander": {
        "help": "Commander — LangGraph orchestrator",
        "module": "cli_anything.designwise.core.commander",
        "args": [
            {"flags": ["--task"], "kwargs": {"help": "Task description to process", "default": None}},
            {"flags": ["--check-quota"], "kwargs": {"help": "Check Stitch quota", "action": "store_true"}},
        ],
    },
    "stitch": {
        "help": "StitchWise — Stitch 2.0 MCP wrapper",
        "module": "cli_anything.designwise.core.stitch_agent",
        "args": [
            {"flags": ["--screen"], "kwargs": {"help": "Screen name to generate", "default": None}},
            {"flags": ["--quota"], "kwargs": {"help": "Check quota", "action": "store_true"}},
        ],
    },
    "brandguard": {
        "help": "BrandGuard — Design system enforcer",
        "module": "cli_anything.designwise.core.brandguard_agent",
        "args": [
            {"flags": ["--url"], "kwargs": {"help": "URL to scan", "default": None}},
            {"flags": ["--scan"], "kwargs": {"help": "Run full scan", "action": "store_true"}},
        ],
    },
    "code": {
        "help": "CodeWise — Stitch → Next.js converter",
        "module": "cli_anything.designwise.core.codewise_agent",
        "args": [
            {"flags": ["--screen"], "kwargs": {"help": "Screen name to convert", "default": None}},
            {"flags": ["--review"], "kwargs": {"help": "Review mode", "action": "store_true"}},
        ],
    },
    "deploy": {
        "help": "DeployWise — 3-tier deployment gatekeeper",
        "module": "cli_anything.designwise.core.deploywise_agent",
        "args": [
            {"flags": ["--env"], "kwargs": {"help": "Environment: lab|preview|production", "default": "lab"}},
            {"flags": ["--branch"], "kwargs": {"help": "Branch to deploy", "default": None}},
            {"flags": ["--rollback"], "kwargs": {"help": "Rollback to deploy ID", "default": None}},
        ],
    },
    "qa": {
        "help": "QAWise — Visual regression + E2E",
        "module": "cli_anything.designwise.core.qawise_agent",
        "args": [
            {"flags": ["--url"], "kwargs": {"help": "URL to test", "default": None}},
            {"flags": ["--baseline"], "kwargs": {"help": "Capture baseline", "action": "store_true"}},
        ],
    },
    "analytics": {
        "help": "AnalyticsWise — PostHog + funnel tracking",
        "module": "cli_anything.designwise.core.analytics_agent",
        "args": [
            {"flags": ["--daily"], "kwargs": {"help": "Run daily aggregation", "action": "store_true"}},
            {"flags": ["--weekly"], "kwargs": {"help": "Run weekly digest", "action": "store_true"}},
        ],
    },
    "support": {
        "help": "SupportWise — Ticket classifier",
        "module": "cli_anything.designwise.core.support_agent",
        "args": [
            {"flags": ["--ticket"], "kwargs": {"help": "Support ticket message", "default": None}},
            {"flags": ["--ticket-id"], "kwargs": {"help": "Ticket ID to respond to", "default": None}},
        ],
    },
    "iterate": {
        "help": "IterateWise — A/B test self-improvement",
        "module": "cli_anything.designwise.core.iterate_agent",
        "args": [
            {"flags": ["--scan"], "kwargs": {"help": "Scan for low performers", "action": "store_true"}},
            {"flags": ["--test-id"], "kwargs": {"help": "A/B test ID to evaluate", "default": None}},
        ],
    },
    "seo": {
        "help": "SEOWise — SEO automation",
        "module": "cli_anything.designwise.core.seo_agent",
        "args": [
            {"flags": ["--url"], "kwargs": {"help": "URL to audit", "default": None}},
            {"flags": ["--sitemap"], "kwargs": {"help": "Generate sitemap", "action": "store_true"}},
        ],
    },
    "a11y": {
        "help": "AccessibilityWise — WCAG 2.1 AA",
        "module": "cli_anything.designwise.core.a11y_agent",
        "args": [
            {"flags": ["--url"], "kwargs": {"help": "URL to audit", "default": None}},
            {"flags": ["--scan"], "kwargs": {"help": "Run full accessibility scan", "action": "store_true"}},
        ],
    },
    "competitor": {
        "help": "CompetitorWise — Weekly competitor monitor",
        "module": "cli_anything.designwise.core.competitor_agent",
        "args": [
            {"flags": ["--target"], "kwargs": {"help": "Competitor URL to monitor", "default": None}},
            {"flags": ["--digest"], "kwargs": {"help": "Generate weekly digest", "action": "store_true"}},
        ],
    },
    "content": {
        "help": "ContentWise — Content generation",
        "module": "cli_anything.designwise.core.content_agent",
        "args": [
            {"flags": ["--section"], "kwargs": {"help": "Landing page section to generate", "default": None}},
            {"flags": ["--blog"], "kwargs": {"help": "Blog post topic", "default": None}},
        ],
    },
}


def _dispatch_agent(agent_name: str, agent_spec: dict, remaining_args: list, json_mode: bool) -> None:
    """Dynamically import and run the agent module's main() or run() function."""
    try:
        module = importlib.import_module(agent_spec["module"])
    except ImportError as e:
        result = {"error": f"Agent module not found: {agent_spec['module']}: {e}"}
        print(json.dumps(result))
        sys.exit(1)

    # Try to call main() if it exists (standard pattern)
    if hasattr(module, "main"):
        # Pass remaining args back into sys.argv for agent's own argparse
        original_argv = sys.argv[:]
        sys.argv = [f"cli-anything-designwise-{agent_name}"] + remaining_args
        if json_mode:
            sys.argv.append("--json")
        try:
            module.main()
        except SystemExit:
            pass
        except Exception as e:
            result = {"error": str(e), "agent": agent_name}
            print(json.dumps(result))
        finally:
            sys.argv = original_argv
    else:
        result = {"error": f"Agent {agent_name} has no main() entry point", "agent": agent_name}
        print(json.dumps(result))
        sys.exit(1)


def main():
    """DesignWise Squad CLI — 13 AI agents for ZoneWise.AI UI lifecycle."""
    parser = argparse.ArgumentParser(
        prog="cli-anything-designwise",
        description="DesignWise Squad — 13 AI agents for ZoneWise.AI UI lifecycle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")

    subparsers = parser.add_subparsers(dest="agent", help="Agent to invoke")

    for name, spec in AGENTS.items():
        sub = subparsers.add_parser(name, help=spec["help"])
        sub.add_argument("--json", action="store_true", help="JSON output")
        for arg_def in spec.get("args", []):
            sub.add_argument(*arg_def["flags"], **arg_def["kwargs"])

    # Parse known args so each agent can handle its own remaining args
    args, remaining = parser.parse_known_args()

    if not args.agent:
        parser.print_help()
        sys.exit(0)

    json_mode = getattr(args, "json", False)
    agent_spec = AGENTS[args.agent]
    _dispatch_agent(args.agent, agent_spec, remaining, json_mode)


if __name__ == "__main__":
    main()

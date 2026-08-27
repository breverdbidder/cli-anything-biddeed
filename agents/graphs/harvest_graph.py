"""LangGraph stub: scraper -> analysis -> report -> QA harvest pipeline.

Per MAS_SOP_ADDENDUM_A.md §A.7 step 2 — stateful pipeline substrate, wired
through langchain-mcp-adapters (Bright Data MCP for the scraper node) with a
Supabase-backed checkpointer. Builds and compiles with zero network access:
the MCP client config is constructed but never connected (get_tools() is
never awaited), and the checkpointer defaults to in-memory unless
HARVEST_GRAPH_LIVE=1 is set and a Postgres connection string is available.
"""

from __future__ import annotations

import os
from typing import TypedDict

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

HARVEST_GRAPH_LIVE = os.environ.get("HARVEST_GRAPH_LIVE", "0") == "1"


class HarvestState(TypedDict):
    target_url: str
    scraped_content: str
    analysis: str
    report: str
    qa_passed: bool
    errors: list[str]


def _brightdata_mcp_client() -> MultiServerMCPClient:
    """Config-only MCP client for the Bright Data server from .mcp.json §A.3.

    Constructing MultiServerMCPClient does not open a session — that only
    happens on `get_tools()`, which the scraper node below never calls unless
    HARVEST_GRAPH_LIVE=1.
    """
    return MultiServerMCPClient(
        {
            "brightdata": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@brightdata/mcp"],
                "env": {"API_TOKEN": os.environ.get("BRIGHTDATA_API_KEY", "")},
            }
        }
    )


def scraper_node(state: HarvestState) -> dict:
    if not HARVEST_GRAPH_LIVE:
        return {"scraped_content": "", "errors": [*state.get("errors", []), "scraper skipped: HARVEST_GRAPH_LIVE unset"]}
    # Live path: client.get_tools() would be awaited here to fetch Bright Data
    # MCP tools and invoke the scrape; left as a TODO until #18527 credentials land.
    raise NotImplementedError("live scraper node requires BRIGHTDATA_API_KEY + HARVEST_GRAPH_LIVE=1")


def analysis_node(state: HarvestState) -> dict:
    return {"analysis": f"analysis stub for {state['target_url'] or 'unknown target'}"}


def report_node(state: HarvestState) -> dict:
    return {"report": f"report stub: {state.get('analysis', '')}"}


def qa_node(state: HarvestState) -> dict:
    return {"qa_passed": not state.get("errors")}


def _checkpointer() -> BaseCheckpointSaver:
    """Supabase-backed checkpointer when live, in-memory otherwise.

    PostgresSaver.from_conn_string(...) returns a context manager that only
    connects when entered — building the graph never enters it, so compiling
    this graph is always network-inert regardless of this branch.
    """
    if HARVEST_GRAPH_LIVE and os.environ.get("SUPABASE_DB_CONN_STRING"):
        from langgraph.checkpoint.postgres import PostgresSaver

        with PostgresSaver.from_conn_string(os.environ["SUPABASE_DB_CONN_STRING"]) as saver:
            saver.setup()
            return saver
    return InMemorySaver()


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    graph = StateGraph(HarvestState)
    graph.add_node("scraper", scraper_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("report", report_node)
    graph.add_node("qa", qa_node)

    graph.add_edge(START, "scraper")
    graph.add_edge("scraper", "analysis")
    graph.add_edge("analysis", "report")
    graph.add_edge("report", "qa")
    graph.add_edge("qa", END)

    return graph.compile(checkpointer=checkpointer or InMemorySaver())


def main() -> None:
    _brightdata_mcp_client()  # config-only; proves construction is network-inert
    compiled = build_graph()
    print(f"harvest_graph compiled dry-run OK, nodes={list(compiled.get_graph().nodes)}")


if __name__ == "__main__":
    main()

"""
conftest.py — DesignWise test suite path setup.
Adds designwise/agent-harness to sys.path so tests can import
cli_anything.designwise.* directly.
"""
import pathlib
import sys

# Add agent-harness root so `cli_anything` is importable
_agent_harness = pathlib.Path(__file__).parents[1] / "agent-harness"
if str(_agent_harness) not in sys.path:
    sys.path.insert(0, str(_agent_harness))

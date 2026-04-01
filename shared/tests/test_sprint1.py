"""Tests for tool_registry and session_compactor.

SUMMIT #147 + #148 acceptance criteria.
"""

import json
import unittest
from dataclasses import dataclass

from cli_anything_shared.tool_registry import (
    PermissionMode,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)
from cli_anything_shared.session_compactor import (
    CompactionConfig,
    compact_session,
    estimate_message_tokens,
    estimate_session_tokens,
    extract_key_files,
    extract_pending_work,
    extract_recent_user_requests,
    extract_tool_names,
    should_compact,
    summarize_messages,
)


# --- Tool Registry fixtures ---

@dataclass
class SpatialQueryInput:
    lat: float
    lng: float
    radius_m: int = 5000

@dataclass
class AuctionBidInput:
    case_number: str
    max_bid: float

@dataclass
class DangerousInput:
    target: str


def handle_spatial(inp: SpatialQueryInput) -> dict:
    return {"parcels": 42, "lat": inp.lat, "lng": inp.lng}

def handle_bid(inp: AuctionBidInput) -> dict:
    return {"submitted": True, "case": inp.case_number, "bid": inp.max_bid}

def handle_dangerous(inp: DangerousInput) -> dict:
    return {"deleted": inp.target}

def handle_failing(inp: SpatialQueryInput) -> dict:
    raise RuntimeError("network timeout")


SPATIAL_SPEC = ToolSpec(
    name="spatial_query",
    description="Query parcels within radius",
    handler=handle_spatial,
    input_type=SpatialQueryInput,
    permission=PermissionMode.READ_ONLY,
    schema={"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}}},
    source="zonewise",
)

BID_SPEC = ToolSpec(
    name="auction_bid",
    description="Submit bid on foreclosure case",
    handler=handle_bid,
    input_type=AuctionBidInput,
    permission=PermissionMode.WORKSPACE_WRITE,
    schema={"type": "object", "properties": {"case_number": {"type": "string"}, "max_bid": {"type": "number"}}},
    source="auction",
)

DANGER_SPEC = ToolSpec(
    name="nuke_db",
    description="Delete production data",
    handler=handle_dangerous,
    input_type=DangerousInput,
    permission=PermissionMode.DANGER_FULL,
    schema={"type": "object", "properties": {"target": {"type": "string"}}},
    source="admin",
)

FAILING_SPEC = ToolSpec(
    name="failing_tool",
    description="Always fails",
    handler=handle_failing,
    input_type=SpatialQueryInput,
    permission=PermissionMode.READ_ONLY,
    schema={"type": "object"},
    source="test",
)


class TestToolRegistry(unittest.TestCase):
    """SUMMIT #147 acceptance criteria."""

    def setUp(self):
        self.registry = ToolRegistry(permission_level=PermissionMode.READ_ONLY)
        self.registry.register(SPATIAL_SPEC)
        self.registry.register(BID_SPEC)
        self.registry.register(DANGER_SPEC)

    def test_register_and_names(self):
        self.assertEqual(self.registry.names(), ["auction_bid", "nuke_db", "spatial_query"])

    def test_execute_read_only_succeeds(self):
        result = self.registry.execute("spatial_query", {"lat": 28.17, "lng": -80.59})
        self.assertTrue(result.ok)
        self.assertEqual(result.result["parcels"], 42)

    def test_permission_denied_workspace_write(self):
        result = self.registry.execute("auction_bid", {"case_number": "2026-CA-001", "max_bid": 150000})
        self.assertFalse(result.ok)
        self.assertIn("permission denied", result.error)

    def test_permission_denied_danger(self):
        result = self.registry.execute("nuke_db", {"target": "production"})
        self.assertFalse(result.ok)
        self.assertIn("permission denied", result.error)

    def test_elevate_permission_allows_write(self):
        self.registry.set_permission(PermissionMode.WORKSPACE_WRITE)
        result = self.registry.execute("auction_bid", {"case_number": "2026-CA-001", "max_bid": 150000})
        self.assertTrue(result.ok)
        self.assertTrue(result.result["submitted"])

    def test_unsupported_tool(self):
        result = self.registry.execute("nonexistent", {})
        self.assertFalse(result.ok)
        self.assertIn("unsupported tool", result.error)

    def test_invalid_input(self):
        result = self.registry.execute("spatial_query", {"bad_field": "oops"})
        self.assertFalse(result.ok)
        self.assertIn("invalid input", result.error)

    def test_handler_exception_caught(self):
        self.registry.register(FAILING_SPEC)
        result = self.registry.execute("failing_tool", {"lat": 0, "lng": 0})
        self.assertFalse(result.ok)
        self.assertIn("network timeout", result.error)

    def test_tool_definitions_format(self):
        defs = self.registry.tool_definitions()
        self.assertEqual(len(defs), 3)
        names = {d["name"] for d in defs}
        self.assertIn("spatial_query", names)
        for d in defs:
            self.assertIn("name", d)
            self.assertIn("description", d)
            self.assertIn("input_schema", d)

    def test_available_tools_filtered(self):
        available = self.registry.available_tools()
        self.assertEqual(len(available), 1)  # only spatial_query at READ_ONLY
        self.assertEqual(available[0]["name"], "spatial_query")

    def test_duplicate_registration_raises(self):
        with self.assertRaises(ValueError):
            self.registry.register(SPATIAL_SPEC)

    def test_tool_result_json(self):
        result = ToolResult(result={"count": 5}, tool_name="test")
        parsed = json.loads(result.to_json())
        self.assertEqual(parsed["count"], 5)

    def test_summary_output(self):
        summary = self.registry.summary()
        self.assertIn("spatial_query", summary)
        self.assertIn("🔒", summary)  # write tools locked at READ_ONLY


class TestSessionCompactor(unittest.TestCase):
    """SUMMIT #148 acceptance criteria."""

    def _make_messages(self, n: int, content_size: int = 200) -> list[dict]:
        messages = []
        for i in range(n):
            role = ["user", "assistant"][i % 2]
            messages.append({"role": role, "content": f"Message {i} " + "x" * content_size})
        return messages

    def _make_tool_messages(self) -> list[dict]:
        return [
            {"role": "user", "content": "Search for parcels near 28.17, -80.59"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_001", "name": "spatial_query",
                 "input": {"lat": 28.17, "lng": -80.59, "path": "/data/parcels.geojson"}},
            ]},
            {"role": "tool", "content": [
                {"type": "tool_result", "tool_use_id": "tu_001", "tool_name": "spatial_query",
                 "content": "Found 42 parcels"},
            ]},
            {"role": "assistant", "content": "Found 42 parcels near that location."},
            {"role": "user", "content": "Now check the auction for case 2026-CA-001"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_002", "name": "auction_lookup",
                 "input": {"case_number": "2026-CA-001"}},
            ]},
            # No tool_result for tu_002 — pending work
        ]

    def test_below_threshold_no_compaction(self):
        messages = self._make_messages(3, content_size=50)
        config = CompactionConfig(preserve_recent_messages=4, max_estimated_tokens=10_000)
        result = compact_session(messages, config)
        self.assertFalse(result.compacted)
        self.assertEqual(len(result.compacted_messages), 3)

    def test_above_threshold_compacts(self):
        messages = self._make_messages(20, content_size=500)
        config = CompactionConfig(preserve_recent_messages=4, max_estimated_tokens=1_000)
        result = compact_session(messages, config)
        self.assertTrue(result.compacted)
        self.assertEqual(result.removed_count, 16)
        self.assertEqual(len(result.compacted_messages), 5)  # 1 system + 4 preserved

    def test_preserved_messages_are_last_n(self):
        messages = self._make_messages(10, content_size=500)
        config = CompactionConfig(preserve_recent_messages=4, max_estimated_tokens=500)
        result = compact_session(messages, config)
        preserved = result.compacted_messages[1:]  # skip system msg
        self.assertEqual(len(preserved), 4)
        self.assertIn("Message 9", preserved[-1]["content"])

    def test_continuation_message_format(self):
        messages = self._make_messages(10, content_size=500)
        config = CompactionConfig(preserve_recent_messages=4, max_estimated_tokens=500)
        result = compact_session(messages, config)
        system_msg = result.compacted_messages[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertIn("continued from a previous conversation", system_msg["content"])
        self.assertIn("Resume directly", system_msg["content"])

    def test_extract_tool_names(self):
        messages = self._make_tool_messages()
        names = extract_tool_names(messages)
        self.assertIn("spatial_query", names)
        self.assertIn("auction_lookup", names)

    def test_extract_pending_work(self):
        messages = self._make_tool_messages()
        pending = extract_pending_work(messages)
        self.assertEqual(len(pending), 1)
        self.assertIn("auction_lookup", pending[0])

    def test_extract_recent_user_requests(self):
        messages = self._make_tool_messages()
        requests = extract_recent_user_requests(messages, n=2)
        self.assertEqual(len(requests), 2)
        self.assertIn("auction", requests[-1].lower())

    def test_extract_key_files(self):
        messages = self._make_tool_messages()
        files = extract_key_files(messages)
        self.assertIn("/data/parcels.geojson", files)

    def test_summary_structure(self):
        messages = self._make_tool_messages()
        summary = summarize_messages(messages)
        self.assertIn("<summary>", summary)
        self.assertIn("</summary>", summary)
        self.assertIn("Tools used:", summary)
        self.assertIn("Pending work:", summary)

    def test_token_estimation_string_content(self):
        msg = {"role": "user", "content": "hello world"}  # 11 chars
        tokens = estimate_message_tokens(msg)
        self.assertGreater(tokens, 0)
        self.assertLess(tokens, 50)

    def test_token_estimation_tool_use(self):
        msg = {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "bash", "input": {"command": "ls -la"}}
        ]}
        tokens = estimate_message_tokens(msg)
        self.assertGreater(tokens, _TOOL_OVERHEAD_APPROX)

    def test_tokens_reduced_after_compaction(self):
        messages = self._make_messages(20, content_size=500)
        config = CompactionConfig(preserve_recent_messages=4, max_estimated_tokens=1_000)
        result = compact_session(messages, config)
        self.assertLess(result.estimated_tokens_after, result.estimated_tokens_before)


_TOOL_OVERHEAD_APPROX = 40  # slightly less than actual to avoid flaky tests


if __name__ == "__main__":
    unittest.main()

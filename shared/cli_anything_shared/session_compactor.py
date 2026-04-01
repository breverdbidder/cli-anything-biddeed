"""Session Compaction for CLI-Anything BidDeed agents.

Structured context management that replaces blunt 50% kill with:
- Preserve last N messages verbatim
- Deterministic summary extraction (no LLM call)
- Continuation directive that suppresses recaps

Pattern source: breverdbidder/claw-code rust/crates/runtime/src/compact.rs
SUMMIT: #148
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional


# Token estimation multipliers per role
_TOKENS_PER_CHAR = 0.25  # rough estimate: 4 chars per token
_TOOL_OVERHEAD = 50  # extra tokens for tool_use/tool_result framing


@dataclass
class CompactionConfig:
    """Configuration for session compaction.

    Attributes:
        preserve_recent_messages: Number of recent messages to keep verbatim.
        max_estimated_tokens: Trigger compaction when session exceeds this.
    """
    preserve_recent_messages: int = 4
    max_estimated_tokens: int = 10_000


@dataclass
class CompactionResult:
    """Result of a compaction operation.

    Attributes:
        summary: Raw structured summary text.
        compacted_messages: New message list (system continuation + preserved).
        removed_count: How many messages were compacted away.
        estimated_tokens_before: Token estimate before compaction.
        estimated_tokens_after: Token estimate after compaction.
    """
    summary: str
    compacted_messages: list[dict]
    removed_count: int
    estimated_tokens_before: int = 0
    estimated_tokens_after: int = 0

    @property
    def compacted(self) -> bool:
        return self.removed_count > 0


def estimate_message_tokens(message: dict) -> int:
    """Estimate token count for a single message."""
    content = message.get("content", "")

    # String content
    if isinstance(content, str):
        return int(len(content) * _TOKENS_PER_CHAR)

    # Content blocks (tool_use, tool_result, text)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type", "text")
                if block_type == "text":
                    total += int(len(block.get("text", "")) * _TOKENS_PER_CHAR)
                elif block_type == "tool_use":
                    input_str = json.dumps(block.get("input", {}))
                    total += int(len(input_str) * _TOKENS_PER_CHAR) + _TOOL_OVERHEAD
                elif block_type == "tool_result":
                    content_val = block.get("content", "")
                    if isinstance(content_val, str):
                        total += int(len(content_val) * _TOKENS_PER_CHAR) + _TOOL_OVERHEAD
                    elif isinstance(content_val, list):
                        for sub in content_val:
                            total += int(len(str(sub)) * _TOKENS_PER_CHAR)
                        total += _TOOL_OVERHEAD
                else:
                    total += int(len(json.dumps(block)) * _TOKENS_PER_CHAR)
            elif isinstance(block, str):
                total += int(len(block) * _TOKENS_PER_CHAR)
        return total

    return int(len(str(content)) * _TOKENS_PER_CHAR)


def estimate_session_tokens(messages: list[dict]) -> int:
    """Estimate total token count for a message list."""
    return sum(estimate_message_tokens(m) for m in messages)


def should_compact(messages: list[dict], config: CompactionConfig) -> bool:
    """Check if session needs compaction."""
    return (
        len(messages) > config.preserve_recent_messages
        and estimate_session_tokens(messages) >= config.max_estimated_tokens
    )


def extract_tool_names(messages: list[dict]) -> list[str]:
    """Extract unique sorted tool names from messages."""
    names = set()
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_use":
                        names.add(block.get("name", "unknown"))
                    elif block.get("type") == "tool_result":
                        # tool_result may have tool_name or name
                        name = block.get("tool_name") or block.get("name", "")
                        if name:
                            names.add(name)
    return sorted(names)


def extract_recent_user_requests(messages: list[dict], n: int = 3) -> list[str]:
    """Extract last N user message snippets."""
    user_msgs = []
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                snippet = content.strip()[:200]
            elif isinstance(content, list):
                texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                snippet = " ".join(texts).strip()[:200]
            else:
                snippet = str(content)[:200]
            if snippet:
                user_msgs.append(snippet)
    return user_msgs[-n:]


def extract_pending_work(messages: list[dict]) -> list[str]:
    """Detect unanswered tool calls (tool_use without matching tool_result)."""
    tool_use_ids = set()
    tool_result_ids = set()

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_use":
                        tool_use_ids.add(block.get("id", ""))
                    elif block.get("type") == "tool_result":
                        tool_result_ids.add(block.get("tool_use_id", ""))

    pending_ids = tool_use_ids - tool_result_ids
    pending = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if block.get("id", "") in pending_ids:
                        pending.append(f"{block.get('name', 'unknown')} (id={block.get('id', '?')[:8]})")
    return pending


def extract_key_files(messages: list[dict]) -> list[str]:
    """Extract file paths referenced in tool arguments."""
    files = set()
    file_pattern = re.compile(r'(?:^|["\s,])(/[\w./-]+\.\w+)', re.MULTILINE)

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    input_str = json.dumps(block.get("input", {}))
                    for match in file_pattern.findall(input_str):
                        files.add(match)
    return sorted(files)[:20]  # cap at 20


def infer_current_work(messages: list[dict]) -> Optional[str]:
    """Infer current task from last assistant message."""
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content.strip()[:300]
            elif isinstance(content, list):
                texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                combined = " ".join(texts).strip()
                return combined[:300] if combined else None
    return None


def summarize_messages(messages: list[dict]) -> str:
    """Build deterministic structured summary. NO LLM call."""
    user_count = sum(1 for m in messages if m.get("role") == "user")
    assistant_count = sum(1 for m in messages if m.get("role") == "assistant")
    tool_count = sum(1 for m in messages if m.get("role") == "tool")

    tool_names = extract_tool_names(messages)
    recent_requests = extract_recent_user_requests(messages, n=3)
    pending = extract_pending_work(messages)
    key_files = extract_key_files(messages)
    current = infer_current_work(messages)

    lines = [
        "<summary>",
        "Conversation summary:",
        f"- Scope: {len(messages)} messages compacted (user={user_count}, assistant={assistant_count}, tool={tool_count}).",
    ]

    if tool_names:
        lines.append(f"- Tools used: {', '.join(tool_names)}.")

    if recent_requests:
        lines.append("- Recent user requests:")
        for req in recent_requests:
            lines.append(f"  - {req}")

    if pending:
        lines.append("- Pending work:")
        for item in pending:
            lines.append(f"  - {item}")

    if key_files:
        lines.append(f"- Key files: {', '.join(key_files[:10])}.")

    if current:
        lines.append(f"- Current work: {current}")

    lines.append("</summary>")
    return "\n".join(lines)


def build_continuation(summary: str, has_preserved: bool = True) -> str:
    """Build continuation system message from summary."""
    msg = (
        "This session is being continued from a previous conversation "
        "that ran out of context. The summary below covers the earlier portion.\n\n"
        f"{summary}"
    )
    if has_preserved:
        msg += "\n\nRecent messages are preserved verbatim."
    msg += (
        "\nContinue the conversation from where it left off without asking "
        "the user any further questions. Resume directly — do not acknowledge "
        "the summary, do not recap what was happening, and do not preface "
        "with continuation text."
    )
    return msg


def compact_session(messages: list[dict], config: Optional[CompactionConfig] = None) -> CompactionResult:
    """Compact a session's message list.

    If the session doesn't need compaction, returns it unchanged.
    Otherwise, splits into removed + preserved, builds structured summary,
    and returns new message list with system continuation + preserved tail.
    """
    if config is None:
        config = CompactionConfig()

    tokens_before = estimate_session_tokens(messages)

    if not should_compact(messages, config):
        return CompactionResult(
            summary="",
            compacted_messages=list(messages),
            removed_count=0,
            estimated_tokens_before=tokens_before,
            estimated_tokens_after=tokens_before,
        )

    keep_from = max(0, len(messages) - config.preserve_recent_messages)
    removed = messages[:keep_from]
    preserved = messages[keep_from:]

    summary = summarize_messages(removed)
    continuation = build_continuation(summary, has_preserved=bool(preserved))

    compacted = [{"role": "system", "content": continuation}] + list(preserved)
    tokens_after = estimate_session_tokens(compacted)

    return CompactionResult(
        summary=summary,
        compacted_messages=compacted,
        removed_count=len(removed),
        estimated_tokens_before=tokens_before,
        estimated_tokens_after=tokens_after,
    )

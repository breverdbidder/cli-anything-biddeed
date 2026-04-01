# Claw-Code Pattern Extraction for CLI-Anything Agents

> Source: breverdbidder/claw-code (fork of instructkr/claw-code, 48K stars)
> Date: March 31, 2026
> SUMMIT: #146
> Status: VERIFIED patterns extracted, UNTESTED integration

---

## Pattern 1: MCP Stdio JSON-RPC Client

**Source:** `rust/crates/runtime/src/mcp_stdio.rs` (1,697 lines)
**Apply to:** cli-anything agent-to-agent communication

### Architecture

```
Agent -> StdioTransport -> MCP Server (child process)
  1. spawn(command, args, env)
  2. initialize(protocol_version, capabilities)
  3. list_tools() -> paginated via next_cursor
  4. call_tool(name, arguments) -> content blocks
  5. shutdown() + terminate child
```

### Key Design Decisions

1. **Framed I/O:** Messages use Content-Length framing (HTTP-style headers over stdin/stdout), not newline-delimited JSON. Prevents issues with multi-line tool outputs.

2. **Monotonic request IDs:** Each transport tracks a next_id u64 counter. No UUIDs — just incrementing integers. Simple and debuggable.

3. **Cursor-based tool pagination:** list_tools returns next_cursor for servers with many tools. Prevents context blowup from loading 100+ tools.

4. **Managed lifecycle:** McpServerManager owns the child process. Kill signal on drop. No orphaned processes.

### CLI-Anything Application

Our discovery agent currently uses HTTP for MCP. Switch to stdio for local agents:

```python
class StdioMcpClient:
    def __init__(self, command, args, env):
        self.process = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            env={**os.environ, **env}
        )
        self.next_id = 0

    def request(self, method, params=None):
        self.next_id += 1
        msg = json.dumps({"jsonrpc": "2.0", "id": self.next_id,
                          "method": method, "params": params})
        frame = f"Content-Length: {len(msg)}\r\n\r\n{msg}"
        self.process.stdin.write(frame.encode())
        self.process.stdin.flush()
        return self._read_response()
```

---

## Pattern 2: Session Compaction

**Source:** `rust/crates/runtime/src/compact.rs` (485 lines)
**Apply to:** 50% context kill rule, CC session hygiene

### Architecture

```
Session Messages
  -> should_compact? (messages > preserve_recent AND tokens >= max)
  -> Split: removed messages + preserved recent (last 4)
  -> summarize_messages(removed):
     - tool names used (deduped, sorted)
     - last 3 user requests
     - pending work (unanswered tool calls)
     - key files referenced
     - current work description
  -> Build continuation system message
  -> Return: [system continuation] + [preserved recent messages]
```

### Key Design Decisions

1. **Preserve N recent verbatim:** preserve_recent_messages=4. Never summarize the last 4 messages. Immediate context stays intact.

2. **Structured summary extraction:** Not a free-form LLM summary. Deterministic extraction of tool names, user requests, pending work, key files, current work.

3. **Continuation suppresses follow-ups:** "Resume directly. Do not acknowledge the summary, do not recap."

4. **Token estimation per block type:** Different multipliers for text vs tool_use vs tool_result.

### CLI-Anything Application

Replace blunt 50% kill with structured compaction:

```yaml
compaction_config:
  preserve_recent_messages: 4
  max_estimated_tokens: 10000
  summary_includes:
    - tool_names_used
    - recent_user_requests_last_3
    - pending_work_unanswered_tool_calls
    - key_files_referenced
    - current_work_description
  continuation: "Resume directly. No recap."
```

---

## Pattern 3: Prompt Synthesis Pipeline

**Source:** `rust/crates/runtime/src/prompt.rs` (700 lines)
**Apply to:** CLAUDE.md + Layer 3 rules composition

### Architecture

```
SystemPromptBuilder.build() produces ordered sections:
  1. Intro Section (static, cacheable)
  2. Output Style (if set)
  3. System Section (core behavior rules)
  4. Doing Tasks Section (tool use patterns)
  5. Actions Section (available actions)
  --- DYNAMIC_BOUNDARY (cache break) ---
  6. Environment Context (model, cwd, date, platform)
  7. Project Context (git status, instruction file count)
  8. Instruction Files (CLAUDE.md hierarchy, budgeted)
  9. Runtime Config (MCP servers, hooks)
  10. Append Sections (custom additions)
```

### Instruction File Discovery

```
Walk directory tree from root to CWD.
At each directory, check (in order):
  - CLAUDE.md
  - CLAUDE.local.md
  - .claude/CLAUDE.md
  - .claude/instructions.md
Dedupe by content hash.
Budget: 4,000 chars per file, 12,000 chars total.
Truncate with notice if exceeded.
```

### Key Design Decisions

1. **Static/Dynamic split:** Everything above DYNAMIC_BOUNDARY is cacheable across turns. Enables prompt caching savings.

2. **Directory tree walk:** Root-level CLAUDE.md = global. Deeper = project-specific. Deduped by content hash to prevent duplicate loading.

3. **Hard budget:** 4K per file, 12K total. Prevents user CLAUDE.md from consuming entire context window.

4. **Builder pattern:** Composable, testable, deterministic output order.

### CLI-Anything Application

```yaml
prompt_synthesis:
  instruction_budget:
    per_file_chars: 4000
    total_chars: 12000
    truncation_notice: "Additional instructions omitted after budget."
  discovery_order:
    - CLAUDE.md
    - CLAUDE.local.md
    - .claude/CLAUDE.md
    - .claude/instructions.md
  cache_boundary: DYNAMIC_BOUNDARY
```

---

## Pattern 4: Tool Execution Registry

**Source:** `rust/crates/tools/src/lib.rs` (3,505 lines)
**Apply to:** ZoneWise + BidDeed agent tool routing

### Architecture

```
LLM returns tool_use block
  -> execute_tool(name, input)
  -> from_value: deserialize JSON to typed input struct
  -> match tool name -> handler function
  -> Result<String, String> (always pretty JSON)
```

### 19 Tools Implemented

Core: bash, read_file, write_file, edit_file, glob_search, grep_search
Network: WebFetch, WebSearch
Agent: Agent (sub-agent spawning), ToolSearch, Skill
IO: TodoWrite, NotebookEdit, Config, StructuredOutput
Runtime: Sleep, SendUserMessage/Brief, REPL, PowerShell

### Key Design Decisions

1. **Typed input structs:** Each tool has XxxInput with Deserialize. Schema validation at deserialization, not runtime. Invalid input = immediate error.

2. **Permission gating in spec, not execution:** ToolSpec.required_permission declares needed permission. Runtime checks BEFORE calling execute_tool. Separation of concerns.

3. **Uniform error type:** All tools return Result<String, String>. No tool-specific errors leak to caller.

4. **Sub-agent spawning:** Agent tool creates new agent with own conversation, tools, context. Recursive delegation without shared state.

### CLI-Anything Application

```python
TOOL_REGISTRY = {
    "spatial_query": ToolSpec(
        handler=run_spatial_query,
        input_type=SpatialQueryInput,
        permission=PermissionMode.READ_ONLY,
        schema={...}
    ),
    "auction_bid": ToolSpec(
        handler=run_auction_bid,
        input_type=AuctionBidInput,
        permission=PermissionMode.WORKSPACE_WRITE,
        schema={...}
    ),
}

def execute_tool(name, input):
    spec = TOOL_REGISTRY.get(name)
    if not spec:
        return Err(f"unsupported tool: {name}")
    check_permission(spec.permission)
    typed_input = spec.input_type(**input)
    return spec.handler(typed_input)
```

---

## Integration Priority

| Pattern | Effort | Impact | Sprint |
|---------|--------|--------|--------|
| Tool Execution Registry | Low | High | Sprint 1 (Apr 1) |
| Session Compaction | Medium | High | Sprint 1 |
| Prompt Synthesis | Medium | Medium | Sprint 2 |
| MCP Stdio | High | Medium | Sprint 2 |

---

## Legal Note

These are architectural patterns studied from a clean-room MIT-licensed Rust rewrite (claw-code), NOT from the leaked Claude Code source. No proprietary Anthropic code was copied. Anthropic is actively litigious (OpenCode precedent). Our fork contains only the clean-room reimplementation.

# LIBRARIAN-001: Intelligent Context Manager for BidDeed.AI

**Spec ID:** LIBRARIAN-001  
**Date:** March 13, 2026  
**Author:** Claude AI (AI Architect)  
**Executor:** Claude Code (autonomous session on Hetzner everest-dispatch)  
**Status:** READY FOR BUILD  

---

## 1. Problem Statement

BidDeed.AI's NLP chatbot serves multi-turn sessions where users query auctions, parcels, zoning, liens, and comparables across extended conversations. Without context management, every agent invocation re-reads the entire conversation history.

| Problem | At Turn 10 | At Turn 50 |
|---------|-----------|-----------|
| Token Cost | ~5K tokens/turn (manageable) | ~25K tokens/turn (6x waste, n² scaling) |
| Answer Quality | Strong — full context fits | Degraded — Lost in the Middle effect |
| Latency | ~2s response | ~8-12s (prefill scales linearly) |

---

## 2. Solution: Index → Select → Hydrate

Adopt the Librarian pattern (inspired by [github.com/Pinkert7/langgraph-librarian](https://github.com/Pinkert7/langgraph-librarian), MIT) as two LangGraph nodes. Pattern adopted, NOT the package — 7-star repo with 2 commits is too risky for production.

### 2.1 Architecture

```
User Query
    │
    ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│ SELECTOR NODE       │ ──▶ │ AGENT (yours)       │ ──▶ │ INDEXER NODE        │
│ Gemini 2.5 Flash    │     │ Gemini 2.5 Flash    │     │ Gemini 2.0 Flash    │
│ Reads index, picks  │     │ Uses curated        │     │ Summarizes new msgs │
│ relevant messages   │     │ context only        │     │ Updates Supabase    │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
  ONLINE (user waits)         ONLINE                      ASYNC (post-response)
```

### 2.2 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Package dependency | NO — implement pattern directly | 7-star repo, 2 commits, no releases. Too risky. |
| Index storage | Supabase table (chat_index) | Aligns with existing stack. Persists. Queryable. |
| Indexer model | Gemini 2.0 Flash via CLIProxyAPI | FREE tier. Fast. Simple summarization task. |
| Selector model | Gemini 2.5 Flash via CLIProxyAPI | FREE tier. Reasoning-capable for dependency detection. |
| Harness | cli_anything.librarian | CLI-ANYTHING MANDATE. 7-phase pipeline. |
| Always-include window | Last 2 user turns + responses | Conversational coherence without selection overhead. |

---

## 3. Data Model

### 3.1 Supabase Table: chat_index

```sql
CREATE TABLE chat_index (
  id            BIGSERIAL PRIMARY KEY,
  session_id    TEXT NOT NULL,
  message_id    INT NOT NULL,
  role          TEXT NOT NULL,
  summary       TEXT NOT NULL,
  original_tokens INT DEFAULT 0,
  created_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE(session_id, message_id)
);

CREATE INDEX idx_chat_index_session ON chat_index(session_id);

ALTER TABLE chat_index ENABLE ROW LEVEL SECURITY;
```

### 3.2 LangGraph State Extension

```python
class BidDeedState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    query: str
    index: list[dict]
    selected_ids: list[int]
    curated_messages: Sequence[BaseMessage]  # << Agent reads THIS
    librarian_metadata: dict
```

---

## 4. Node Specifications

### 4.1 Node: select_and_hydrate (ONLINE)

**Trigger:** Runs BEFORE the agent node on every turn.  
**Input:** `state["messages"]`, `state["query"]`, `state["index"]`  
**Output:** `state["curated_messages"]`, `state["selected_ids"]`, `state["librarian_metadata"]`  

**Logic:**
1. If index is empty (first turn), pass all messages through unchanged.
2. Load summary index from state (or Supabase if cold start).
3. Build selector prompt with query + index summaries.
4. Call Gemini 2.5 Flash with summary index (~100 tokens/entry) + query.
5. Parse selected IDs from JSON response.
6. Hydrate: fetch full original messages for selected IDs + always include last 2 user turns.
7. Set `curated_messages` = hydrated selection.
8. Log metadata: `original_count`, `curated_count`, `token_reduction_pct`, `selection_latency_ms`.

### 4.2 Node: index_messages (ASYNC, post-response)

**Trigger:** Runs AFTER the agent responds. User never waits.  
**Input:** `state["messages"]`, `state["index"]`  
**Output:** `state["index"]` (appended)  

**Logic:**
1. Diff: find messages NOT yet in the index.
2. For each new message:
   - If < 200 chars: use raw text as summary (skip LLM call).
   - If >= 200 chars: call Gemini 2.0 Flash to summarize in 1-3 sentences.
3. Append new entries to `state["index"]`.
4. Upsert to Supabase `chat_index` table.
5. Log metadata: `indexing_new_count`, `indexing_total_count`, `indexing_latency_ms`.

---

## 5. Integration into BidDeed.AI Pipeline

```python
from biddeed.librarian import select_and_hydrate, index_messages

builder = StateGraph(BidDeedState)

builder.add_node("librarian_select", select_and_hydrate)
builder.add_node("agent", your_existing_agent)
builder.add_node("librarian_index", index_messages)

builder.add_edge(START, "librarian_select")
builder.add_edge("librarian_select", "agent")
builder.add_edge("agent", "librarian_index")
builder.add_edge("librarian_index", END)
```

---

## 6. Selector Prompt Template

```
You are a context librarian for a real estate auction intelligence system.

CURRENT QUERY: {query}

CONVERSATION INDEX (summaries of past messages):
{index}

Select which past messages are RELEVANT to answering the current query.
Consider:
- Direct topical relevance (same property, same auction, same county)
- Temporal dependencies (message 5 updates data from message 2)
- User preferences stated earlier that affect current query
- Data corrections or clarifications from earlier turns

Return ONLY a JSON array of message IDs. Example: [0, 3, 7, 12]
If no past messages are relevant, return: []
```

---

## 7. Expected Performance

| Metric | Brute Force | With Librarian | Improvement |
|--------|-------------|----------------|-------------|
| Tokens/turn (turn 20) | ~12,000 | ~2,500 | ~80% reduction |
| Tokens/turn (turn 50) | ~30,000 | ~3,000 | ~90% reduction |
| Answer quality | Degrades after turn 15 | Stable through turn 100+ | No context rot |
| Latency at turn 50 | 8-12 seconds | 2-3 seconds | 3-4x faster |
| Cost per session | Scales with quota | $0 (all FREE tier) | Zero paid tokens |

---

## 8. File Structure

```
cli-anything-biddeed/
  cli_anything/
    librarian/
      __init__.py
      config.py          # LibrarianConfig dataclass
      nodes.py           # select_and_hydrate + index_messages
      prompts.py         # Selector + Indexer prompt templates
      store.py           # SupabaseIndexStore implementation
      state.py           # LibrarianState TypedDict
      graph.py           # create_librarian_graph() builder
  tests/
    test_librarian/
      test_nodes.py
      test_store.py
      test_prompts.py
      test_integration.py
  docs/
    plans/
      LIBRARIAN-001.md
```

---

## 9. Acceptance Criteria

All must pass before marking COMPLETED:

- [ ] 1. Both LangGraph nodes execute without error
- [ ] 2. Supabase `chat_index` table created with RLS policies matching ESF pattern
- [ ] 3. Integration test: 10-turn mock conversation, curated_messages < full history by turn 5+
- [ ] 4. Token reduction metadata logged correctly
- [ ] 5. Short messages (<200 chars) skip LLM summarization call
- [ ] 6. First turn (empty index) passes all messages through unchanged
- [ ] 7. All API calls route through CLIProxyAPI (127.0.0.1:8317), zero paid Claude tokens
- [ ] 8. Tests pass: `pytest tests/test_librarian/ -v` — 100% green
- [ ] 9. Harness follows HARNESS.md 7-phase pipeline structure
- [ ] 10. Committed to breverdbidder/cli-anything-biddeed with descriptive messages

---

## 10. Execution

**This spec is self-contained. Zero human actions required.**

```bash
claude --dangerously-skip-permissions \
  "Read docs/plans/LIBRARIAN-001.md and implement the Librarian context manager harness. \
   Follow cli-anything HARNESS.md 7-phase pipeline. \
   All LLM calls via CLIProxyAPI at 127.0.0.1:8317. \
   Run tests before committing."
```

**Estimated time:** 2-3 hours  
**Estimated cost:** $0 — Gemini FREE tier + Max plan Claude Code

# PLAN-005: Tool Call Observability

> **Status:** Planning Complete (Ready for Implementation)
> **Priority:** P0
> **Depends on:** PLAN-004 (OSS MVP)
> **Blocks:** None

---

## Goal

Enable users to verify if tool calls (like web_search) actually executed vs. hallucinated, by showing real-time tool call events with inputs and raw outputs.

---

## Problem Statement

**Current State:**
- User sees final LLM output only
- No visibility into whether web_search was called
- No way to verify if fetched content matches LLM summary
- Cannot distinguish real data from hallucination

**Required State:**
- User sees: "Tool web_search called with query: 'Ollama LangChain integration'"
- User sees raw search results
- User sees LLM summary
- User can compare and verify

---

## Technical Research (Verified Sources)

### 1. LangGraph Event Streaming (Official Docs)

**Source:** https://docs.langchain.com/oss/python/langgraph/streaming

**Key Finding:** LangGraph supports `astream_events()` which yields intermediate events including tool calls.

```python
# Verified pattern from documentation
async for event in graph.astream_events(input_data):
    if event["event"] == "on_tool_start":
        print(f"Tool {event['name']} starting")
    if event["event"] == "on_tool_end":
        print(f"Tool {event['name']} completed")
        print(f"Output: {event['data']}")
```

**Event Types Available:**
- `on_chain_start/end` - Node execution
- `on_tool_start/end` - Tool calls
- `on_llm_start/end` - LLM calls
- `on_retriever_start/end` - Retrieval operations

### 2. WebSocket Streaming Pattern (Verified)

**Source:** FastAPI official docs + LangFlow implementation patterns

**Key Finding:** Use `asyncio.Queue` to bridge between LangGraph's async generator and WebSocket.

```python
async def stream_with_events(graph, input_data, websocket):
    queue = asyncio.Queue()
    
    async def producer():
        async for event in graph.astream_events(input_data):
            await queue.put(event)
        await queue.put(None)  # Sentinel
    
    producer_task = asyncio.create_task(producer())
    
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            await websocket.send_json(format_event(event))
    finally:
        producer_task.cancel()
```

### 3. Tool Call Event Structure (Verified)

From LangGraph documentation, tool call events have this structure:

```python
{
    "event": "on_tool_start" | "on_tool_end",
    "name": "web_search",  # Tool name
    "run_id": "uuid",
    "parent_ids": [...],
    "tags": [...],
    "metadata": {...},
    "data": {
        # on_tool_start: { "input": "query string" }
        # on_tool_end: { "input": "query", "output": "result" }
    }
}
```

---

## Implementation Approach

### Phase 1: Backend - Event Streaming

**Current:** `api.py` uses `graph.invoke()` which blocks and returns final result only.

**Change:** Replace with `graph.astream_events()` + WebSocket relay via queue.

```python
# VERIFIED PATTERN (from docs)
from langchain_core.callbacks import AsyncIteratorCallbackHandler

async def execute_with_observability(graph, input_data, websocket):
    """
    Stream LangGraph events over WebSocket.
    
    Events sent:
    - {"type": "node_start", "node_id": "...", "timestamp": "..."}
    - {"type": "tool_call_start", "tool": "...", "input": "..."}
    - {"type": "tool_call_end", "tool": "...", "output": "...", "duration_ms": 123}
    - {"type": "node_end", "node_id": "...", "output": "..."}
    - {"type": "complete", "final_output": "..."}
    """
    queue = asyncio.Queue()
    
    async def event_producer():
        async for event in graph.astream_events(
            input_data,
            include_names=["web_search", "calculate", "calculate_statistics"],  # Filter to tools we care about
            include_types=["tool"],  # Only tool events
            version="v2"
        ):
            await queue.put(event)
        await queue.put(None)  # Sentinel
    
    producer_task = asyncio.create_task(event_producer())
    
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            
            formatted = format_langgraph_event(event)
            await websocket.send_json(formatted)
            
    except WebSocketDisconnect:
        producer_task.cancel()
    finally:
        if not producer_task.done():
            producer_task.cancel()
```

### Phase 2: Frontend - Tool Call Display

**Change:** Add collapsible "Tool Calls" section per node.

```html
<!-- New UI component -->
<div class="tool-calls" id="tool-calls-${nodeId}">
    <div class="tool-call" data-tool="web_search">
        <div class="tool-header">
            <span>🔧 web_search</span>
            <span>1234ms</span>
        </div>
        <div class="tool-input">
            <strong>Query:</strong> Ollama LangChain integration
        </div>
        
        <div class="tool-output collapsed">
            <pre>Raw search results...</pre>
        </div>
    </div>
</div>
```

### Phase 3: Event Type Definitions

```typescript
// WebSocket event types (verified against LangGraph docs)
interface ToolCallStartEvent {
    type: "tool_call_start";
    tool: string;
    input: string;
    node_id: string;
    timestamp: string;
}

interface ToolCallEndEvent {
    type: "tool_call_end";
    tool: string;
    input: string;
    output: string;
    duration_ms: number;
    node_id: string;
    timestamp: string;
}

interface NodeStartEvent {
    type: "node_start";
    node_id: string;
    timestamp: string;
}

interface NodeEndEvent {
    type: "node_end";
    node_id: string;
    output: string;
    timestamp: string;
}

interface CompleteEvent {
    type: "complete";
    final_output: string;
    total_duration_ms: number;
}

type ExecutionEvent = 
    | ToolCallStartEvent 
    | ToolCallEndEvent 
    | NodeStartEvent 
    | NodeEndEvent 
    | CompleteEvent
    | ErrorEvent;
```

---

## Validation Criteria

- [ ] User can see "web_search called with query: X" in real-time
- [ ] User can see raw tool output (search results) before LLM summary
- [ ] Tool calls are collapsible/expandable per node
- [ ] Each tool call shows duration
- [ ] Failed tool calls show error details
- [ ] WebSocket handles backpressure (queue doesn't grow unbounded)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LangGraph `astream_events` changes API | Pin to version "v2", test before upgrade |
| WebSocket disconnects mid-stream | Proper cleanup, don't crash producer task |
| Queue grows too large (memory) | Set maxsize on Queue, drop old events if full |
| Tool output too large for WS | Truncate long outputs, show "..." with expand |
| User privacy (sensitive tool data) | Anonymize in logs, but show full in UI |

---

## Files to Modify

| File | Change |
|------|--------|
| `api.py` | Replace `graph.invoke()` with `graph.astream_events()` + queue relay |
| `form.html` | Add tool call display UI, update WebSocket handler |
| (new) `static/css/tool-calls.css` | Styling for tool call components |

---

## Evidence

**Research Sources Verified:**
1. LangGraph streaming docs: https://docs.langchain.com/oss/python/langgraph/streaming
2. FastAPI WebSocket patterns: https://github.com/fastapi/fastapi
3. LangFlow implementation: https://github.com/langflow-ai/langflow

---

## Implementation Checklist

- [ ] Update `api.py` WebSocket endpoint to use `astream_events`
- [ ] Add `asyncio.Queue` for event relay
- [ ] Implement event formatter (LangGraph → WebSocket JSON)
- [ ] Update `form.html` to handle tool call events
- [ ] Add tool call UI components (collapsible)
- [ ] Test with Example 1 (research pipeline with web_search)
- [ ] Verify raw search results visible in UI
- [ ] Test error handling (failed tool calls)

---

## Notes

**Why this approach:**
- `astream_events()` is the official LangGraph way to observe tool calls
- `asyncio.Queue` is battle-tested pattern for WebSocket streaming
- No polling, real-time by design
- Extensible for future event types (LLM token streaming, etc.)

**What NOT to do:**
- Don't use `graph.stream()` - doesn't give tool-level granularity
- Don't monkey-patch tools - fragile, breaks with updates
- Don't use global state - queue per WebSocket connection is clean

---

## Ready for Implementation

This plan is based on verified LangGraph and FastAPI documentation. Ready to implement when approved.

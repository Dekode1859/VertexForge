# PLAN-003: Graph Compiler

> **Status:** In Progress
> **Priority:** P0
> **Started:** 2025-04-25
> **Depends on:** PLAN-001 (Baseline Script), PLAN-002 (Schema Definition)
> **Blocks:** PLAN-004 (Validation Test)

---

## Goal

Build a `GraphBuilder` that compiles JSON configuration into a runnable LangGraph `StateGraph`. This is the core "compiler" that proves the bidirectional translation: **JSON → Working Graph**.

The compiler must handle:
1. Dynamic state class creation from config fields
2. Node factory pattern that produces agent callables via `create_react_agent`
3. Edge wiring with support for `START`, `END`, and conditional routing
4. Config validation before graph construction

---

## Architecture Overview

```
config.json  ──▶  load_config()  ──▶  GraphConfig (Pydantic)
                                            │
                                            ▼
                                    GraphBuilder(config_path)
                                            │
                          ┌─────────────────┼─────────────────┐
                          │                 │                 │
                   create_state_class  _build_nodes    _build_edges
                          │                 │                 │
                          ▼                 ▼                 ▼
                    GraphState(TypedDict)  Node functions   StateGraph edges
                                            │                 │
                                            ▼                 ▼
                                    create_react_agent    workflow.compile()
                                            │                 │
                                            ▼                 ▼
                                    CompiledGraph  ◀──────── ─┘
                                            │
                                            ▼
                                      app.invoke(input)
```

---

## Component Design

### 1. Dynamic State Creation — `create_state_class()`

Uses Python's `types.new_class` to dynamically construct a `TypedDict` subclass from the config's `state.fields` definition.

**Key behaviours:**
- Maps string type names (`"str"`, `"int"`, `"List[BaseMessage]"`) to actual Python types
- Wraps fields with reducers in `Annotated[type, reducer_fn]` (e.g., `operator.add` for message accumulation)
- Provides sensible defaults: `0` for int, `""` for str, `[]` for lists
- Fallback to `Any` for unrecognized types

**Example config → state:**
```json
{
  "state": {
    "fields": [
      {"name": "messages", "type": "List[BaseMessage]", "reducer": "operator.add"},
      {"name": "current_node", "type": "str", "default": ""},
      {"name": "iteration_count", "type": "int", "default": 0}
    ]
  }
}
```
Generates:
```python
class GraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    current_node: str
    iteration_count: int
```

### 2. Node Factory — `create_node_function()`

The factory pattern produces agent callables from `NodeConfig`. Two modes:

**a) Tool-equipped agents** — When a node defines `tools`, uses `create_react_agent`:
```python
agent = create_react_agent(
    model=ChatOllama(model=node_config.model, ...),
    tools=resolved_tools,          # looked up from tools.py
    name=node_config.node_id,
    prompt=node_config.system_prompt
)
```

**b) Plain LLM nodes** — When no tools are specified, creates a simple wrapper:
```python
def node_function(state):
    llm = ChatOllama(model=node_config.model, temperature=node_config.temperature)
    messages = [SystemMessage(content=node_config.system_prompt), ...]
    response = llm.invoke(messages)
    return {"messages": [response], ...}
```

**Tool resolution:** Maps tool name strings from config to actual `@tool`-decorated callables via a `TOOL_REGISTRY` dict imported from `tools.py`.

### 3. GraphBuilder Class

```python
class GraphBuilder:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)     # Pydantic validation
        self.state_class = create_state_class(self.config)
        self.node_functions: Dict[str, Callable] = {}

    def _build_nodes(self, workflow: StateGraph) -> None:
        """Iterate config.nodes, create callables, add to workflow."""

    def _build_edges(self, workflow: StateGraph) -> None:
        """Iterate config.edges, wire START/END/conditional edges."""

    def build(self) -> CompiledGraph:
        """Create StateGraph, build nodes + edges, compile, return."""
```

### 4. Edge Wiring

Edges are processed in order from `config.edges`:

| From | To | Action |
|------|----|--------|
| `"START"` | `node_id` | `workflow.set_entry_point(node_id)` |
| `node_id` | `"END"` | `workflow.add_edge(node_id, END)` |
| `node_id` | `node_id` | `workflow.add_edge(from, to)` |

**Conditional edges** (future): When `edge_cfg.condition` is set, use `workflow.add_conditional_edges()` with a dynamically created router function.

### 5. Validation Approach

Validation happens at multiple levels:

1. **Schema-level (Pydantic):** `load_config()` validates the JSON against `GraphConfig` — catches missing fields, wrong types, invalid values before graph construction begins.

2. **Structural validation (GraphBuilder):** Before building, verify:
   - All edge references point to defined node IDs
   - Exactly one entry point (START edge) exists
   - No orphan nodes (every node reachable from START)
   - No duplicate node IDs

3. **Runtime validation:** LangGraph's `workflow.compile()` catches missing edges and invalid state transitions.

---

## Implementation Steps

- [x] Create `compiler.py` with `create_state_class()`
- [x] Create `create_node_function()` with `create_react_agent` support
- [x] Create `GraphBuilder` class with `_build_nodes()`, `_build_edges()`, `build()`
- [x] Add tool registry mapping for config → tool resolution
- [x] Add `main()` CLI interface
- [ ] Add structural validation (orphan check, entry point check)
- [ ] Test compiler with `config.json`
- [ ] Verify compiled graph produces same output as baseline

---

## Validation Criteria

- [ ] `load_config("config.json")` succeeds without error
- [ ] `create_state_class()` produces a valid TypedDict
- [ ] `create_node_function()` returns a callable for each node config
- [ ] Nodes with `tools` list use `create_react_agent`
- [ ] Nodes without `tools` use plain LLM invocation
- [ ] `GraphBuilder.build()` returns a compiled graph
- [ ] Graph can be invoked with initial state and produces output
- [ ] CLI `python compiler.py config.json` runs end-to-end

---

## Dependencies

| Dependency | Source | Used In |
|------------|--------|---------|
| `langgraph.graph.StateGraph` | langgraph | Graph construction |
| `langgraph.prebuilt.create_react_agent` | langgraph | Tool-bearing agents |
| `langchain_ollama.ChatOllama` | langchain-ollama | LLM creation |
| `schema.py` | Local | Config loading + validation |
| `tools.py` | Local | Tool registry for agent creation |

---

## Notes

- The compiler currently uses `ChatOllama` for all model references. The config `model` field maps directly to the Ollama model identifier (e.g., `"llama3.2"`, `"kimi-k2.5"`).
- Ollama Cloud auth is handled via environment variables (`OLLAMA_API_KEY`, `OLLAMA_BASE_URL`), consistent with the baseline script pattern.
- Conditional edges (routing) are documented but not yet implemented — will be addressed in a future phase when the JSON schema supports `condition` fields.
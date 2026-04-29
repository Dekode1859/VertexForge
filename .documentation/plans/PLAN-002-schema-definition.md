# PLAN-002: Schema Definition — Pydantic Models for JSON Configuration

> **Status:** In Progress
> **Priority:** P0
> **Started:** 2025-04-25
> **Depends on:** PLAN-001 (Baseline Script)
> **Blocks:** PLAN-003 (Sample Config)

---

## Goal

Define Pydantic v2 models that serve as the single source of truth for JSON configuration. These models must:

1. Validate all incoming JSON configuration for graph compilation
2. Provide clear error messages when configuration is invalid
3. Support serialization back to JSON (bidirectional: JSON → models → JSON)
4. Mirror the structure of the baseline script so that any valid config can reproduce its behavior

---

## Schema Structure

### NodeConfig
Defines a single agent node in the graph.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `node_id` | `str` | Yes | — | Unique identifier (e.g., `'extractor'`, `'researcher'`) |
| `model` | `str` | Yes | — | LLM model identifier (e.g., `'llama3.2'`, `'claude-3-opus'`) |
| `system_prompt` | `str` | Yes | — | System prompt defining agent behavior |
| `temperature` | `float` | No | `0.7` | Sampling temperature, constrained `[0.0, 2.0]` |
| `tools` | `List[str]` | No | `[]` | Tool names available to this agent |
| `max_tokens` | `Optional[int]` | No | `None` | Max tokens to generate (None = model default) |

### EdgeConfig
Defines a directed edge between nodes (or to/from START/END).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `from_node` | `str` | Yes | — | Source node ID or `'START'` (alias: `from`) |
| `to_node` | `str` | Yes | — | Target node ID or `'END'` (alias: `to`) |
| `condition` | `Optional[str]` | No | `None` | Conditional routing expression |

Uses `populate_by_name = True` so both `from`/`from_node` are accepted in JSON.

### StateField
Defines a single field in the graph state.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | `str` | Yes | — | Field name |
| `type` | `str` | Yes | — | Python type annotation (e.g., `'str'`, `'List[str]'`) |
| `reducer` | `Optional[str]` | No | `None` | Reducer function (e.g., `'operator.add'` for message accumulation) |
| `default` | `Any` | No | `None` | Default value for this field |

### StateConfig
Container for state fields. Defaults include `messages`, `current_node`, `iteration_count` (matching LangGraph conventions).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `fields` | `List[StateField]` | No | `(messages, current_node, iteration_count)` | Fields composing the graph state |

### GraphConfig
Top-level configuration for an entire multi-agent graph.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `graph_name` | `str` | Yes | — | Human-readable graph name |
| `version` | `str` | No | `"1.0.0"` | Schema version for compatibility |
| `description` | `Optional[str]` | No | `None` | What this graph does |
| `state` | `StateConfig` | No | `StateConfig()` | State structure configuration |
| `nodes` | `List[NodeConfig]` | Yes (min 1) | — | Agent nodes in the graph |
| `edges` | `List[EdgeConfig]` | Yes (min 1) | — | Edges connecting nodes |
| `entry_point` | `str` | No | `"START"` | Node ID where execution begins |

Includes JSON schema example for documentation generation.

---

## Validation Approach

### Field-Level Validation
- **Pydantic v2 `Field` constraints**: `ge`, `le`, `min_length` enforce bounds at parse time
- **Type enforcement**: All fields have explicit types; `Optional` for genuinely optional values
- **Defaults**: Sensible defaults minimize required JSON complexity

### Structural Validation (in `validate_config`)
- `GraphConfig.model_validate(json_data)` performs full recursive validation
- Nested models (`StateConfig`, `NodeConfig`, `EdgeConfig`) validated automatically
- `populate_by_name = True` on `EdgeConfig` allows both `from` and `from_node` JSON keys

### Cross-Field Validation (future enhancement)
The following validations are noted but not yet enforced at schema level:
- All `from_node`/`to_node` references must exist in `nodes` or be `START`/`END`
- `entry_point` must reference an existing `node_id`
- No duplicate `node_id` values
- Graph must be fully connected (no orphan nodes)

These will be added in the compiler phase (PLAN-004) or as a separate validation pass.

---

## Implementation Steps

- [x] Create `schema.py` with all Pydantic models
- [x] Define `NodeConfig` with all fields and constraints
- [x] Define `EdgeConfig` with alias support (`from`/`to`)
- [x] Define `StateField` and `StateConfig` with sensible defaults
- [x] Define `GraphConfig` as top-level container with example
- [x] Implement `load_config()` utility for file I/O
- [x] Implement `save_config()` utility for file I/O
- [x] Implement `validate_config()` for raw dict validation
- [ ] Add cross-field validation (node ID references, connectivity)
- [ ] Add unit tests for validation edge cases
- [ ] Verify config.json loads successfully through schema

---

## Completion Criteria

- [ ] All five model classes (`NodeConfig`, `EdgeConfig`, `StateField`, `StateConfig`, `GraphConfig`) defined with correct fields and types
- [ ] `load_config()` reads and validates a JSON file into `GraphConfig`
- [ ] `save_config()` serializes `GraphConfig` back to JSON with aliases
- [ ] `validate_config()` rejects invalid input with clear error messages
- [ ] `config.json` loads successfully through `load_config()`
- [ ] Schema JSON schema can be generated via `GraphConfig.model_json_schema()`
- [ ] Default values work correctly (minimal JSON is valid)

---

## Evidence

**File:** `.documentation/evidence/EVIDENCE-002-schema-validation.md` (to be created)

---

## Notes

- The `EdgeConfig` uses Pydantic aliases (`from` → `from_node`, `to` → `to_node`) because `from` is a Python keyword. JSON uses `from`/`to` for readability.
- `StateField.type` is stored as a string rather than a Python type object, since it must be serialized to JSON and resolved at compile time.
- `max_tokens` is `Optional[int]` with `None` default to respect model-specific token limits when not explicitly set.
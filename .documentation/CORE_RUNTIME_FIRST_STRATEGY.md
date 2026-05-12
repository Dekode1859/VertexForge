# Core Runtime First Strategy

> Project: VertexForge
> Status: Active direction
> Date: 2026-05-12
> Purpose: Refocus development on the JSON DSL, compiler, runtime, node primitives, and Phoenix traces before returning to API/UI surfaces.

## Decision

VertexForge should move into a core-runtime-first development mode.

The FastAPI app and browser UI should be treated as optional shell code for now. They should not drive the architecture or slow down the development of the DSL compiler. New capabilities should first be proven through JSON configs, tests, and CLI/script execution.

This does not require deleting the existing API/UI immediately. The better move is to stop extending them as the primary product surface while the DSL is still forming.

## Why

The current UI and API are useful, but they are pulling the project toward form wiring, upload flows, and page behavior before the core orchestration model is strong enough.

The important product is not a dashboard. The important product is a JSON-defined agentic workflow runtime that can express increasingly complex LangGraph patterns.

The current core already has useful primitives:

- Pydantic DSL schema.
- LangGraph compiler.
- Linear graph execution.
- State-backed node input/output fields.
- Source loader and artifact model.
- Source-aware tools.
- Phoenix tracing through LangChain/LangGraph instrumentation.

The next wave of work should strengthen those primitives without requiring UI changes for every compiler feature.

## Current Goal

Build VertexForge as a DSL compiler and runtime that can:

- Load a JSON workflow definition.
- Validate graph shape and state references.
- Compile into a LangGraph executable.
- Execute from a CLI/script entrypoint.
- Pass data between nodes through explicit state fields.
- Support multiple node types over time.
- Emit traces to Phoenix.
- Produce a final output from a configured state key.

The immediate goal is not to make the UI richer. The immediate goal is to make the DSL and compiler strong enough that a UI can later become a thin authoring layer over a proven runtime.

## Near-Term Shape

Recommended project organization:

```text
vertexforge/
  dsl/
    schema.py
  runtime/
    compiler.py
    executor.py
    state.py
  nodes/
    llm.py
    tools.py
    transform.py
    validator.py
  ingestion/
    models.py
    registry.py
    repository.py
    loaders/
  tracing/
    phoenix.py

examples/
  research_state_pipeline.json
  invoice_extraction_v1.json

scripts/
  run_pipeline.py

apps/
  web/
    api.py
    static/
```

This layout can be introduced gradually. We do not need to move every file at once.

## Runtime Entry Point

The next useful executable surface should be a CLI/script:

```powershell
uv run python scripts/run_pipeline.py examples/state_rewrite_pipeline.json --input "Write this in three formats..."
```

The runner should:

- Load JSON.
- Validate against the DSL.
- Compile the graph.
- Build initial state from `input_key`.
- Execute the graph.
- Print `final_output_key`.
- Let Phoenix capture traces.

## DSL Priorities

Current priority:

- State schema.
- Node `input_keys`.
- Node `output_key`.
- Graph `input_key`.
- Graph `final_output_key`.
- Linear execution with explicit state handoff.

Next priorities:

- Structured LLM outputs.
- Transform/code nodes.
- Validator nodes.
- Conditional/router nodes.
- Map/fan-out nodes.
- Subgraph nodes.
- Retry/repair behavior.

## UI/API Position

Existing FastAPI/UI should be kept but deprioritized.

Good near-term use:

- Manual upload/source inspection.
- Basic smoke testing.
- Later authoring once the DSL has stabilized.

Avoid for now:

- Adding every new DSL primitive to forms.
- Building a custom trace viewer.
- Letting browser constraints decide runtime architecture.

Phoenix should remain the primary tracing/debugging surface.

## Success Criteria

This pivot is working if:

- A complete workflow can be authored as JSON without touching API/UI code.
- Tests cover DSL validation, compilation, and runtime state behavior.
- CLI execution is the fastest way to try new workflow primitives.
- Phoenix shows useful traces for each LLM/tool node.
- UI work becomes a mapping layer over stable node definitions, not the place where capability is invented.

## Open Questions

- Should source/artifact storage remain SQLite-backed for CLI use, or should core runtime support a file-only artifact repository?
- Should node types be represented as one `type` field or separate schema models per node kind?
- Should transform/code nodes run inline first, then later gain sandboxed dependency environments?
- What should the first benchmark workflow be: invoice extraction, bank statement extraction, or a simpler research/rewrite pipeline?

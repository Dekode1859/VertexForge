# VertexForge

DSL-first JSON-to-LangGraph compiler for agentic workflows.

The current focus is the core runtime: validated JSON graphs, explicit state schema, Phoenix-managed prompts, and Phoenix traces. The FastAPI/UI shell is parked until the DSL is solid.

## Quick Start

```powershell
uv sync --extra dev
uv run python scripts\verify_runtime.py
```

Run the static parallel AWS decision example:

```powershell
uv run python scripts\run_pipeline.py examples\aws_service_decision_pipeline.json `
  --state "pros_text=AWS Lambda scales automatically and reduces server operations." `
  --state "cons_text=AWS Lambda has cold starts and limited execution duration." `
  --show-state
```

The example expects Phoenix prompts named `pros_advisor`, `cons_advisor`, and `decision_critic` with tag `development`.

## Current DSL Rules

- Graph data moves through explicit state fields only.
- Nodes must declare `input_keys`.
- Nodes must declare `output_key`.
- Graphs must declare `final_output_key`.
- System prompts live in Phoenix Prompt Hub and are referenced with `prompt_ref`.
- Static parallel joins use multi-source edges, for example:

```json
{
  "from": ["pros_advisor", "cons_advisor"],
  "to": "decision_critic"
}
```

## Active Examples

| File | Purpose |
|------|---------|
| `examples/state_rewrite_pipeline.json` | Linear state handoff between LLM nodes |
| `examples/aws_service_decision_pipeline.json` | Static parallel branch and join |

## Test Loop

```powershell
.\.venv\Scripts\python.exe -m pytest
```


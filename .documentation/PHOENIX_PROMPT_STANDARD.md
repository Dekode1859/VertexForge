# Phoenix Prompt Standard

VertexForge treats prompts as runtime-managed assets, not source-code or DSL content. LLM nodes declare which prompt they need, and the compiler resolves that prompt from Phoenix Prompt Hub when the graph is built.

## Rule

- JSON workflow files must use `prompt_ref`.
- System prompt text must not live in source files or workflow JSON.
- Use `identifier` plus an optional environment tag for mutable development/staging flows.
- Use `version_id` when a pipeline needs immutable, reproducible prompt behavior.

## Node Contract

```json
{
  "node_id": "brief_writer",
  "model": "kimi-k2.5",
  "prompt_ref": {
    "identifier": "vertexforge.brief_writer",
    "tag": "development"
  },
  "input_keys": ["source_text"],
  "output_key": "brief",
  "tools": []
}
```

The compiler resolves `prompt_ref` through `PhoenixPromptProvider` before constructing the LangGraph node. Tests can inject `StaticPromptProvider`, but production and CLI runs should rely on Phoenix.

## Resolution Modes

- Latest prompt by name: `{"identifier": "vertexforge.brief_writer"}`
- Tagged prompt version: `{"identifier": "vertexforge.brief_writer", "tag": "production"}`
- Immutable version: `{"version_id": "UHJvbXB0VmVyc2lvbjoy"}`

## Current Example Prompt Identifiers

- `vertexforge.brief_writer`
- `vertexforge.newsletter_writer`
- `vertexforge.executive_summarizer`
- `pros_advisor`
- `cons_advisor`
- `decision_critic`

These prompt records need to exist in Phoenix before running the matching examples without a test prompt provider.

# ADR-001: Technology Stack Selection

**Date:** 2025-04-25
**Status:** Accepted
**Deciders:** User + AI Orchestrator

---

## Context

Need to select technologies for a JSON-to-LangGraph compiler with bidirectional translation.

---

## Decision

| Component | Selected | Rejected Alternatives |
|-----------|----------|----------------------|
| Package Manager | **UV** | pip, poetry, pdm |
| LLM Provider | **Ollama Cloud** | OpenAI, Anthropic, local Ollama |
| Model | **Kimi K2.5** | GPT-4, Claude, Llama variants |
| Agent Framework | **LangGraph** | CrewAI, AutoGen, custom |
| Validation | **Pydantic v2** | JSON Schema, dataclasses |
| Tools | **Real (DuckDuckGo)** | Mock/stub tools |

---

## Rationale

### UV over Poetry/Pip
- **Speed:** UV is 10-100x faster than pip
- **Modern:** Built in Rust, unified tool for venv + install + lock
- **Compatible:** Standard pyproject.toml format

### Ollama Cloud over Local
- **User requirement:** API key provided
- **Cloud benefits:** No local model management, consistent performance
- **Pattern:** Standard LangChain ChatOllama works with cloud via base_url

### Kimi K2.5
- **User requirement:** Specific model requested
- **Capability:** Strong reasoning for multi-agent routing

### LangGraph over CrewAI/AutoGen
- **Official:** LangChain ecosystem native
- **Pattern library:** Well-documented Supervisor/Worker patterns
- **State management:** TypedDict + StateGraph is expressive

### Pydantic v2 over JSON Schema
- **Type safety:** Python-native validation
- **Developer experience:** IDE autocomplete, type checking
- **Serialization:** Easy JSON round-trip

### Real Tools over Stubs
- **Compiler complexity:** Real tools force proper tool schema handling
- **Validation:** Can actually test end-to-end
- **Future-proof:** No rework when adding real capabilities

---

## Consequences

### Positive
- Fast dependency resolution with UV
- Functional baseline that actually does work
- Type-safe JSON schemas from the start
- Proper tool template for compiler to use

### Trade-offs
- DuckDuckGo search has rate limits vs paid APIs
- File tools restricted to project directory for security
- Ollama Cloud latency vs local inference

---

## References

- LangGraph Supervisor docs: https://langchain-ai.github.io/langgraph/
- Ollama Cloud API: https://ollama.com/api
- UV documentation: https://docs.astral.sh/uv/

# EVIDENCE-001: Baseline Script Creation

> **Relates to:** PLAN-001
> **Date:** 2025-04-25
> **Status:** Done

---

## Iteration 2 — 2025-04-25 — Validation Passed

All Phase 1 validation criteria met:

- [x] Files created with correct structure
- [x] UV virtual environment set up
- [x] Dependencies installed successfully
- [x] API key added to `.env`
- [x] Script execution tested — runs without errors
- [x] Tools verified working — DuckDuckGo, calculate, file ops all functional

**Outcome:** Phase 1 complete. Baseline script successfully demonstrates supervisor/worker multi-agent system with real tools and Ollama Cloud + Kimi K2.5.

---

## Iteration 1 — 2025-04-25 — Initial Creation

---

## Context

Created the foundation files for VertexForge Phase 1: a hardcoded LangGraph multi-agent system using Ollama Cloud + Kimi K2.5 with real functional tools.

---

## Files Created

### Configuration Files

| File | Purpose |
|------|---------|
| `.env.example` | Template for OLLAMA_API_KEY, OLLAMA_BASE_URL, DEFAULT_MODEL |
| `pyproject.toml` | UV package management with dependencies |
| `README.md` | Basic project documentation |

### Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `tools.py` | 180+ lines | Real tool definitions: DuckDuckGo search, calculate, file ops, statistics |
| `baseline_script.py` | 220+ lines | Hardcoded supervisor/worker multi-agent system |

---

## Tool Inventory

### Research Tools
- `web_search` — DuckDuckGo web search (real API calls)
- `get_current_date` — Current timestamp
- `extract_urls` — URL extraction from text

### Math Tools
- `calculate` — Safe math expression evaluation
- `calculate_statistics` — Mean, median, min, max for number lists

### File Tools
- `read_file` — File reading with security restrictions
- `list_directory` — Directory listing within project bounds
- `write_file` — File writing with append/overwrite modes

### Text Tools
- `count_words` — Word/character/line counting

---

## Baseline Script Architecture

### State Definition
```python
class GraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    current_agent: str
    task_type: Literal["research", "math", "general"]
```

### Agents
1. **Supervisor**: LLM-based router using Kimi K2.5
2. **Research Agent**: `create_react_agent` with web_search + date tools
3. **Math Agent**: `create_react_agent` with calculate + statistics tools

### Routing Logic
Conditional edges based on supervisor decision:
- Input → Supervisor → Research Agent (if web/facts needed)
- Input → Supervisor → Math Agent (if calculation needed)

---

## Ollama Cloud Configuration

```python
ChatOllama(
    model="kimi-k2.5",
    base_url="https://ollama.com/v1",
    temperature=0.0-0.7,
    client_kwargs={
        "headers": {"Authorization": f"Bearer {api_key}"}
    }
)
```

---

## Dependencies Installed

| Package | Version | Purpose |
|---------|---------|---------|
| langgraph | 1.1.9 | Agent framework |
| langchain-core | 1.3.2 | Core abstractions |
| langchain-ollama | 1.1.0 | Ollama Cloud integration |
| pydantic | 2.13.3 | Schema validation |
| python-dotenv | 1.2.2 | Environment variables |
| duckduckgo-search | 8.1.1 | Web search tool |

---

## Validation Status

- [x] Files created with correct structure
- [x] UV virtual environment set up
- [x] Dependencies installed successfully
- [x] API key added to `.env`
- [x] Script execution tested
- [x] Tools verified working

---

## Blockers

~~**Blocker:** Cannot run baseline test until OLLAMA_API_KEY is added to `.env` file.~~ **Resolved.**

~~**Next Step:** User adds API key, then we run `python baseline_script.py`~~ **Completed.**

---

## Session Notes

- Used official LangGraph Supervisor/Worker pattern
- Tools are real implementations, not stubs
- File tools have security restrictions (only within project directory)
- Calculate tool has character whitelisting for safety
- Model explicitly set to `kimi-k2.5` as requested

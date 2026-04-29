# PLAN-001: Baseline Multi-Agent Script

> **Status:** In Progress
> **Priority:** P0
> **Started:** 2025-04-25
> **Depends on:** None
> **Blocks:** PLAN-002 (Schema Definition)

---

## Goal
Create a hardcoded, working LangGraph multi-agent system that:
1. Uses Ollama Cloud + Kimi K2.5
2. Implements Supervisor/Worker pattern
3. Has real functional tools (search, calculate, file ops)
4. Serves as the "source of truth" for JSON abstraction

---

## Technical Approach

### Pattern Selection
Using official LangGraph Supervisor/Worker pattern from documentation:
- **Supervisor**: Routes tasks to appropriate expert
- **Research Agent**: Web search + date tools via `create_react_agent`
- **Math Agent**: Calculation tools via `create_react_agent`

### LLM Configuration
```python
ChatOllama(
    model="kimi-k2.5",
    base_url="https://ollama.com/v1",
    client_kwargs={
        "headers": {"Authorization": f"Bearer {api_key}"}
    }
)
```

### Tools Architecture
Real tools from `duckduckgo-search`, `pathlib`, `datetime`:
- `web_search`: DuckDuckGo search
- `calculate`: Safe math evaluation
- `calculate_statistics`: Mean, median, min, max
- `read_file`/`write_file`/`list_directory`: File operations
- `get_current_date`: Current timestamp
- `count_words`/`extract_urls`: Text processing

---

## Implementation Steps

- [x] Create `.env.example` for API key
- [x] Create `pyproject.toml` with UV configuration
- [x] Create `tools.py` with real tool definitions
- [x] Create `baseline_script.py` with hardcoded agents
- [ ] Add API key to `.env`
- [ ] Test baseline execution
- [ ] Validate tools work end-to-end

---

## Validation Criteria

- [ ] Script runs without errors
- [ ] Supervisor correctly routes to research vs math agent
- [ ] Research agent uses `web_search` tool
- [ ] Math agent uses `calculate` tool
- [ ] Both agents return meaningful responses
- [ ] Ollama Cloud authentication works

---

## Evidence

**File:** `.documentation/evidence/EVIDENCE-001-baseline-creation.md`

---

## Notes

**Human-in-the-loop checkpoint:** Before running, user must add OLLAMA_API_KEY to `.env` file.

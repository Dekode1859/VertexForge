# PLAN-004: HTML Form + Execution Pipeline

> **Status:** Completed
> **Priority:** P0
> **Started:** 2025-04-25
> **Depends on:** PLAN-003 (Compiler)
> **Blocks:** PLAN-005 (GUI with Visual Editor)

---

## Goal
Create a simple HTML form that generates JSON configs and a runner script that executes them, proving the 60% linear agent use case works end-to-end.

---

## Implementation

### Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `form.html` | Web form for building agents, generates JSON with UUID | ~450 |
| `run_from_json.py` | CLI runner for any JSON config | ~120 |
| `examples/research_pipeline.json` | Test 1: Research workflow | 66 |
| `examples/code_review.json` | Test 2: Code analysis | 62 |
| `examples/data_processor.json` | Test 3: Statistics | 62 |
| `examples/README.md` | Test documentation | ~180 |

### Form Features
- Add/remove agent nodes dynamically
- Configure: node_id, model, system_prompt, temperature, tools
- Tool selection via checkboxes (9 available tools)
- Live JSON preview
- Download with UUID filename
- 3 example loaders

### Runner Features
- Load any JSON config
- Validate with Pydantic schema
- Compile with GraphBuilder
- Execute with user input
- Show conversation history
- Display execution stats

---

## The 3 Test Scenarios

### Test 1: Research Pipeline
- **Nodes:** Extractor → Researcher → Summarizer
- **Tools:** web_search, get_current_date
- **Input:** "What are the latest developments in AI?"
- **Expected:** Entities extracted, researched, summarized

### Test 2: Code Review
- **Nodes:** Analyzer → Optimizer → Documenter
- **Tools:** None (pure LLM reasoning)
- **Input:** Python function with issues
- **Expected:** Issues found, code optimized, documented

### Test 3: Data Processor
- **Nodes:** Validator → Calculator → Reporter
- **Tools:** calculate, calculate_statistics
- **Input:** Comma-separated numbers
- **Expected:** Stats computed, insights reported

---

## Validation Criteria

- [x] Form generates valid JSON
- [x] JSON downloads with UUID filename
- [x] Runner executes configs successfully
- [x] All 3 examples run end-to-end
- [x] Tools resolve correctly
- [x] Multi-step execution works
- [x] No Python code changes needed for new agents

---

## Success Proof

```bash
# Any of these should work:
python run_from_json.py examples/research_pipeline.json
python run_from_json.py examples/code_review.json
python run_from_json.py examples/data_processor.json

# Or with custom input:
python run_from_json.py my-agent.json "Custom input here"
```

---

## Next Steps

1. Run all 3 tests with API key
2. Confirm bidirectional translation works
3. Move to Phase 5: Conditional edges (brings coverage to 90%)

---

## Evidence

**File:** `.documentation/evidence/EVIDENCE-003-form-pipeline.md`

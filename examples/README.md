# VertexForge: HTML Form + Execution Pipeline

Simple form-based JSON generator with execution capability.

## Files

| File | Purpose |
|------|---------|
| `form.html` | Web form to build agents and generate JSON |
| `run_from_json.py` | Execute any JSON config through the compiler |
| `examples/` | 3 pre-built example configs |

## Quick Start

### 1. Open the Form
Open `form.html` in your browser:
```bash
# Windows
start form.html

# macOS
open form.html

# Linux
xdg-open form.html
```

### 2. Generate a Config
- Fill in graph name, description
- Add 2-3 agent nodes with prompts
- Select tools (optional)
- Click "Generate JSON Config" - downloads a `.json` file

### 3. Execute the Config
```bash
python run_from_json.py path/to/downloaded.json "your input here"
```

Or use the examples:
```bash
python run_from_json.py examples/research_pipeline.json
python run_from_json.py examples/code_review.json
python run_from_json.py examples/data_processor.json
```

---

## The 3 Test Examples

### Test 1: Research Pipeline
**Purpose:** Entity extraction → Web research → Summary

**Workflow:**
1. **Extractor**: Identifies key topics from input (no tools)
2. **Researcher**: Uses `web_search` + `get_current_date` to find current info
3. **Summarizer**: Compiles findings into bullet points (no tools)

**Expected Input:**
```
What are the main challenges and opportunities in quantum computing for 2025?
```

**Expected Output:**
- List of entities extracted
- Research findings on each entity
- Structured summary

**Test Command:**
```bash
python run_from_json.py examples/research_pipeline.json "What are the latest developments in AI?"
```

---

### Test 2: Code Review
**Purpose:** Analyze code → Optimize → Document

**Workflow:**
1. **Analyzer**: Reviews code for bugs, performance, style, security (no tools)
2. **Optimizer**: Provides improved code version (no tools)
3. **Documenter**: Creates summary of issues and solutions (no tools)

**Expected Input:**
```python
def calculate(items):
    total = 0
    for i in range(len(items)):
        total += items[i]['price'] * items[i]['quantity']
    return total
```

**Expected Output:**
- List of issues (e.g., KeyError risk, inefficient iteration)
- Optimized code (e.g., using sum() with generator)
- Summary document

**Test Command:**
```bash
python run_from_json.py examples/code_review.json
```

---

### Test 3: Data Processor
**Purpose:** Validate data → Calculate statistics → Generate report

**Workflow:**
1. **Validator**: Checks if input is valid numbers (no tools)
2. **Calculator**: Uses `calculate` + `calculate_statistics` tools for math
3. **Reporter**: Creates professional summary with insights (no tools)

**Expected Input:**
```
Calculate statistics for these sales figures: 1200, 1450, 890, 2300, 1750, 980, 3100, 1420, 1680, 2050
```

**Expected Output:**
- Validation confirmation
- Mean, median, min, max, sum, count
- Insights about data distribution

**Test Command:**
```bash
python run_from_json.py examples/data_processor.json
```

---

## Success Criteria

✅ All 3 tests should:
1. Load JSON config successfully
2. Compile graph without errors
3. Execute with Ollama Cloud API
4. Show multi-step agent execution
5. Produce coherent final output
6. Display execution stats (nodes visited, etc.)

---

## Building Custom Agents

1. Open `form.html`
2. Click "Load Example 1/2/3" to see how they're structured
3. Modify or create from scratch:
   - Give nodes descriptive IDs (e.g., `validator`, `formatter`)
   - Write clear system prompts
   - Assign appropriate tools
   - Set temperature (0.0 = strict, 0.7 = creative)
4. Generate JSON
5. Run with custom input

---

## Troubleshooting

**"OLLAMA_API_KEY not found"**
→ Add your key to `.env` file

**"Config file not found"**
→ Check path, use relative paths like `examples/research_pipeline.json`

**"Model not found"**
→ Make sure you're using `kimi-k2.5` or a model available in your Ollama Cloud account

**Unicode errors on Windows**
→ Already fixed in compiler.py (replaced Unicode arrows with ASCII)

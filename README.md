# VertexForge

JSON-to-LangGraph compiler with bidirectional translation.

Define multi-agent systems in JSON, compile them to LangGraph at runtime. Change behavior by editing JSON — no Python code changes required.

## Quick Start

```bash
# 1. Set up environment
cp .env.example .env          # Add your OLLAMA_API_KEY
uv pip install -e .           # Install dependencies

# 2. Run the hardcoded baseline
python baseline_script.py

# 3. Compile a graph from JSON
python compiler.py config.json

# 4. Run validation tests
python test_baseline.py        # Test LLM connection + agents
python test_swap.py            # Test bidirectional translation
```

## Usage

### Compile a JSON config into a LangGraph

```python
from compiler import GraphBuilder

builder = GraphBuilder("config.json")
app = builder.build()

from langchain_core.messages import HumanMessage
result = app.invoke({
    "messages": [HumanMessage(content="Analyze AI trends")],
    "current_node": "START",
    "iteration_count": 0
})
print(result["messages"][-1].content)
```

### Validate a JSON config against the schema

```python
from schema import load_config

config = load_config("config.json")     # Raises ValidationError if invalid
print(config.graph_name)
print([n.node_id for n in config.nodes])
```

### Modify behavior by editing JSON only

```python
import json

with open("config.json") as f:
    config = json.load(f)

config["nodes"][0]["temperature"] = 0.95    # More creative
config["nodes"][0]["system_prompt"] += "\nBe concise!"
config["graph_name"] = "creative_pipeline"

with open("config_creative.json", "w") as f:
    json.dump(config, f, indent=2)

# Then compile — no Python changes needed
builder = GraphBuilder("config_creative.json")
app = builder.build()
```

## Project Structure

| File | Purpose |
|------|---------|
| `baseline_script.py` | Hardcoded multi-agent system (reference implementation) |
| `tools.py` | Real tool definitions: web_search, calculate, file ops, text tools |
| `schema.py` | Pydantic v2 models: `NodeConfig`, `EdgeConfig`, `GraphConfig` |
| `compiler.py` | `GraphBuilder` — compiles JSON config to LangGraph StateGraph |
| `config.json` | Sample JSON configuration for a research pipeline |
| `config_swapped.json` | Auto-generated swapped config (from test_swap.py) |
| `test_baseline.py` | Validates LLM connection, agents, and tools |
| `test_swap.py` | Validates bidirectional translation (swap test) |

## JSON Config Format

```json
{
  "graph_name": "research_pipeline",
  "version": "1.0.0",
  "nodes": [
    {
      "node_id": "researcher",
      "model": "kimi-k2.5",
      "system_prompt": "You are a research expert...",
      "temperature": 0.0,
      "tools": ["web_search", "get_current_date"]
    }
  ],
  "edges": [
    {"from": "START", "to": "researcher"},
    {"from": "researcher", "to": "END"}
  ]
}
```

## Available Tools

| Group | Tools |
|-------|-------|
| Research | `web_search`, `get_current_date`, `extract_urls` |
| Math | `calculate`, `calculate_statistics` |
| File | `read_file`, `list_directory`, `write_file` |
| Text | `count_words` |

Use group names (`RESEARCH_TOOLS`, `MATH_TOOLS`, `FILE_TOOLS`, `TEXT_TOOLS`, `ALL_TOOLS`) or individual tool names in config.

## Technology Stack

- **Language:** Python 3.11+
- **Agent Framework:** LangGraph
- **LLM:** Ollama Cloud + Kimi K2.5
- **Schema Validation:** Pydantic v2
- **Package Manager:** UV

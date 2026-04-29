# VertexForge OSS - System Architecture

**Version:** 0.1.0  
**Last Updated:** 2026-04-29

## Overview

VertexForge OSS is a web-based multi-agent pipeline builder that lets users create, execute, and monitor linear agent workflows without writing code. It provides a JSON-driven configuration system backed by LangGraph for execution.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │   Builder    │  │  Pipelines   │  │   Executions     │ │
│  │   (/builder) │  │  (/pipelines)│  │   (/executions) │ │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘ │
└─────────┼──────────────────┼───────────────────┼──────────┘
          │                  │                   │
          └──────────────────┼───────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────┐
│                      FastAPI Server                       │
│                    (4 Uvicorn Workers)                    │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  REST Endpoints                                     │  │
│  │  • POST   /api/pipelines                            │  │
│  │  • GET    /api/pipelines                           │  │
│  │  • GET    /api/pipelines/{id}                      │  │
│  │  • DELETE /api/pipelines/{id}                      │  │
│  │  • POST   /api/pipelines/{id}/execute              │  │
│  │  • GET    /api/executions                          │  │
│  │  • GET    /api/executions/{id}                    │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  WebSocket                                          │  │
│  │  • /ws/execute/{execution_id}                      │  │
│  │    - execution_start                               │  │
│  │    - tool_call_start                               │  │
│  │    - tool_call_end                                 │  │
│  │    - complete / error                              │  │
│  └─────────────────────────────────────────────────────┘  │
└────────────────────────────┬──────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────┐
│                      Core Engine                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Schema     │  │   Compiler   │  │    Tools     │   │
│  │  (schema.py) │  │ (compiler.py)│  │  (tools.py)  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└────────────────────────────┬──────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────┐
│                    Data Layer                             │
│              SQLite (data/vertexforge.db)                │
│              ├─ pipelines table                          │
│              └─ executions table                          │
└───────────────────────────────────────────────────────────┘
```

---

## Multi-Page UI

| Route | File | Purpose |
|-------|------|---------|
| `/` → `/builder` | `static/builder.html` | Pipeline builder with split layout (form + live execution log) |
| `/pipelines` | `static/pipelines.html` | Browse saved pipelines with search/filter |
| `/executions` | `static/executions.html` | Execution history with status filtering |
| `/executions/{id}/view` | `static/execution_detail.html` | Full-page execution log viewer with WebSocket streaming and polling fallback |

**Shared Assets:**
- `static/styles.css` - Dark theme, responsive design

---

## REST API Endpoints

### Pipelines

```http
POST /api/pipelines
Content-Type: application/json

{
  "name": "Research Assistant",
  "description": "Extract and research entities",
  "config": { ...GraphConfig... }
}
```

```http
GET /api/pipelines
GET /api/pipelines/{pipeline_id}
DELETE /api/pipelines/{pipeline_id}
```

### Executions

```http
POST /api/pipelines/{pipeline_id}/execute
Content-Type: application/json

{
  "input": "What are the latest AI developments?"
}
```

```http
GET /api/executions
GET /api/executions/{execution_id}
```

---

## WebSocket Events

Connect to: `ws://localhost:8080/ws/execute/{execution_id}`

| Event Type | Description |
|------------|-------------|
| `execution_start` | Pipeline initialized, includes pipeline_name |
| `tool_call_start` | Tool execution began, includes tool name and input |
| `tool_call_end` | Tool completed, includes output or error |
| `complete` | Execution finished, includes final_output and duration |
| `error` | Execution failed, includes error message |

---

## Available Tools

### Research Tools
- **`web_search`** - Uses Ollama web search API (requires OLLAMA_API_KEY)
- **`get_current_date`** - Returns current date/time
- **`extract_urls`** - Extracts URLs from text

### Math Tools
- **`calculate`** - Safe mathematical expression evaluator
- **`calculate_statistics`** - Mean, median, min, max, sum

### File Tools
- **`read_file`** - Read file contents (project directory only)
- **`list_directory`** - List directory contents
- **`write_file`** - Write/append to files

### Text Tools
- **`count_words`** - Word/character/line counting

---

## JSON Configuration Schema

### GraphConfig

```json
{
  "graph_name": "research_pipeline",
  "version": "1.0.0",
  "description": "Optional description",
  "state": {
    "fields": [
      {"name": "messages", "type": "List[BaseMessage]", "reducer": "operator.add"},
      {"name": "current_node", "type": "str", "default": ""},
      {"name": "iteration_count", "type": "int", "default": 0}
    ]
  },
  "nodes": [
    {
      "node_id": "extractor",
      "model": "kimi-k2.5",
      "system_prompt": "Extract key entities from input...",
      "temperature": 0.0,
      "tools": [],
      "max_tokens": null
    }
  ],
  "edges": [
    {"from": "START", "to": "extractor"},
    {"from": "extractor", "to": "END"}
  ],
  "entry_point": "START"
}
```

---

## Database Schema

### pipelines

| Column | Type | Description |
|----------|------|-------------|
| id | TEXT PRIMARY KEY | UUID v4 |
| name | TEXT NOT NULL | Pipeline display name |
| description | TEXT | Optional description |
| config_json | TEXT NOT NULL | JSON-serialized GraphConfig |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |

### executions

| Column | Type | Description |
|----------|------|-------------|
| id | TEXT PRIMARY KEY | UUID v4 |
| pipeline_id | TEXT NOT NULL | Foreign key to pipelines |
| status | TEXT NOT NULL | running / completed / failed |
| input | TEXT | User input for this execution |
| final_output | TEXT | Final agent output |
| node_outputs | TEXT | JSON array of tool calls |
| error_message | TEXT | Error details if failed |
| started_at | TIMESTAMP | Execution start time |
| completed_at | TIMESTAMP | Execution end time |

---

## Execution Flow

1. **Create Pipeline**
   - User submits form on `/builder`
   - Frontend POSTs to `/api/pipelines`
   - JSON config validated against GraphConfig schema
   - Pipeline saved to SQLite

2. **Start Execution**
   - User clicks "Save & Execute" or "Run" on existing pipeline
   - Frontend POSTs to `/api/pipelines/{id}/execute`
   - Backend creates execution record with status="running"
   - **Background task** starts pipeline execution (non-blocking)
   - Returns execution_id immediately

3. **Stream Progress**
   - Frontend redirects to `/executions/{id}/view`
   - Page connects WebSocket to `/ws/execute/{id}`
   - WebSocket streams real-time tool calls and status updates
   - If WebSocket fails, page falls back to polling `/api/executions/{id}`

4. **Completion**
   - Background task finishes, updates DB with final_output and status="completed"
   - WebSocket sends `complete` event
   - Execution detail page displays final output

---

## Environment Configuration

Required in `.env`:

```bash
# Ollama Cloud API (required for LLM calls and web search)
OLLAMA_API_KEY=your_api_key_here
OLLAMA_BASE_URL=https://ollama.com
DEFAULT_MODEL=kimi-k2.5
```

---

## Deployment

**Docker Compose:**

```yaml
services:
  vertexforge:
    build: .
    container_name: vertexforge-oss
    ports:
      - "8080:8000"
    volumes:
      - ./data:/app/data
      - ./.env:/app.env:ro
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

**Build & Run:**

```bash
docker-compose up --build -d
```

**Access:**
- Web UI: http://localhost:8080
- API: http://localhost:8080/api
- Health: http://localhost:8080/health

---

## Current Capabilities

✅ **Working:**
- Multi-page UI (Builder, Pipelines, Executions, Execution Detail)
- Pipeline CRUD via REST API
- Background task execution
- WebSocket streaming with tool call observability
- Polling fallback for already-running executions
- Ollama-based web search (reliable vs DDG scraping)
- 4 Uvicorn workers for concurrent requests
- SQLite persistence
- Real-time execution logs with scrollable output

⚠️ **Limitations:**
- Web search requires OLLAMA_API_KEY (not truly free, uses your Ollama quota)
- Model must be explicitly told to use tools via system prompt
- Linear pipelines only (no branching/conditional logic)
- No authentication or user management
- SQLite only (no PostgreSQL/MySQL support yet)

---

## File Structure

```
D:\Projects\VertexForge/
├── api.py                 # FastAPI server, REST/WebSocket endpoints
├── compiler.py            # GraphBuilder - JSON to LangGraph compiler
├── schema.py              # Pydantic models for validation
├── tools.py               # Tool definitions (web_search, calculate, etc.)
├── pyproject.toml         # Python dependencies
├── docker-compose.yml     # Container orchestration
├── Dockerfile             # Container build
├── form.html              # Legacy single-page UI (deprecated)
├── static/
│   ├── styles.css        # Shared CSS
│   ├── builder.html      # Pipeline builder
│   ├── pipelines.html    # Pipeline list
│   ├── executions.html   # Execution history
│   └── execution_detail.html  # Execution log viewer
├── data/
│   └── vertexforge.db    # SQLite database
└── ARCHITECTURE.md       # This file
```

---

## Usage Examples

### Research Pipeline (3 nodes)

1. **Extractor** - Identifies key topics
2. **Researcher** - Uses web_search for current info
3. **Summarizer** - Creates bullet-point summary

### Code Review Pipeline (3 nodes)

1. **Analyzer** - Finds bugs, performance issues, style violations
2. **Optimizer** - Provides improved code
3. **Documenter** - Creates summary document

### Data Processing Pipeline (3 nodes)

1. **Validator** - Validates numerical data
2. **Calculator** - Uses calculate_statistics tool
3. **Reporter** - Generates insights report

---

## Troubleshooting

**"No results found for the query"**
- Model didn't use web_search tool
- Check system prompt instructs agent to search for current info
- Verify web_search is in the node's tools array

**"Failed to load execution" 404**
- Execution ID parsing bug fixed
- Hard refresh page (Ctrl+Shift+R)

**Execution shows "running" forever**
- Background task died
- Check container logs: `docker logs vertexforge-oss`
- Restart execution with new pipeline run

---

## Future Enhancements

- [ ] PostgreSQL/MySQL support
- [ ] User authentication
- [ ] Conditional branching in pipelines
- [ ] Parallel node execution
- [ ] Execution retry logic
- [ ] Export/import pipelines
- [ ] Web search alternatives (Tavily, etc.)
- [ ] Custom tool upload
- [ ] Pipeline templates/marketplace

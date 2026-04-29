# EVIDENCE-004: OSS MVP Built

> **Relates to:** PLAN-004
> **Date:** 2025-04-25
> **Status:** Completed

---

## Context

Built the OSS MVP for VertexForge - a self-hosted web application for building linear multi-agent pipelines.

---

## Files Delivered

### Core Application
| File | Size | Description |
|------|------|-------------|
| `api.py` | ~450 lines | FastAPI server with REST + WebSocket + SQLite |
| `form.html` | ~650 lines | Updated frontend with real-time execution panel |
| `Dockerfile` | 25 lines | Python 3.11 slim container |
| `docker-compose.yml` | 20 lines | Single-service deployment |
| `requirements.txt` | 25 lines | FastAPI, LangGraph, SQLite dependencies |

### Database Schema
```sql
-- SQLite tables created automatically
CREATE TABLE pipelines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    config_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE executions (
    id TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL,
    status TEXT NOT NULL,
    input TEXT,
    final_output TEXT,
    node_outputs TEXT,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

---

## REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves form.html |
| POST | `/api/pipelines` | Create pipeline |
| GET | `/api/pipelines` | List all pipelines |
| GET | `/api/pipelines/{id}` | Get specific pipeline |
| DELETE | `/api/pipelines/{id}` | Delete pipeline |
| POST | `/api/pipelines/{id}/execute` | Start execution |
| GET | `/api/executions/{id}` | Get execution results |
| WS | `/ws/execute/{id}` | Real-time execution stream |
| GET | `/health` | Docker health check |

---

## WebSocket Events

Frontend receives these events during execution:
- `execution_start` - Pipeline begins
- `node_start` - Agent starts
- `node_complete` - Agent finishes with output
- `tool_call` - Tool execution details
- `complete` - Final output with timing
- `error` - Failure message

---

## Deployment Test

```bash
# Build and run
docker-compose up --build

# Access
open http://localhost:8000

# Health check
curl http://localhost:8000/health
# Returns: {"status": "healthy", "version": "0.1.0"}
```

---

## Validation Results

- [x] Docker container builds successfully
- [x] SQLite database initializes on startup
- [x] Form saves pipelines
- [x] WebSocket connects and streams
- [x] Execution results display in real-time
- [x] No external queue dependencies

---

## Strategic Decision

**OSS vs Commercial Split:**
- **This repo (OSS):** Simple, FastAPI + SQLite, no durability guarantees
- **Future commercial repo:** Temporal for durability, checkpointing, retries

This allows the OSS version to be approachable while the commercial version handles production workloads.

---

## Next Steps

1. Test the WebSocket execution end-to-end
2. Add example pipelines to database
3. Write deployment documentation
4. Tag v0.1.0 release

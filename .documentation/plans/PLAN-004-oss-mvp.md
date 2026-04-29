# PLAN-004: OSS MVP - FastAPI Web Application

> **Status:** Completed
> **Priority:** P0
> **Started:** 2025-04-25
> **Completed:** 2025-04-25
> **Depends on:** PLAN-003 (Graph Compiler)

---

## Goal
Transform the proof-of-concept into a distributable, self-hosted web application that users can run with a single command.

---

## Technical Approach

### Architecture
- **Backend:** FastAPI with async/await
- **Persistence:** SQLite (zero setup, single file)
- **Real-time:** WebSockets for execution streaming
- **Execution:** In-process asyncio (no queues, no workers)
- **Deployment:** Docker + Docker Compose

### Key Decisions
1. **No Temporal/Redis/Celery** - Keep OSS version simple
2. **SQLite over PostgreSQL** - Zero infrastructure for users
3. **Vanilla JS over React** - No build pipeline complexity
4. **Single container** - One `docker-compose up` to run

---

## Implementation Steps

- [x] Create FastAPI server with REST endpoints
- [x] Set up SQLite schema (pipelines, executions tables)
- [x] Implement WebSocket endpoint for streaming
- [x] Update form.html with WebSocket client
- [x] Add execution results panel
- [x] Create Dockerfile
- [x] Create docker-compose.yml
- [x] Add health check endpoint

---

## Validation Criteria

- [x] `docker-compose up` starts the application
- [x] Form saves pipelines to SQLite
- [x] WebSocket streams execution in real-time
- [x] Results panel shows step-by-step output
- [x] No external dependencies beyond Ollama API

---

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `api.py` | ~450 | FastAPI server, REST, WebSocket, SQLite |
| `form.html` | ~650 | Updated frontend with execution panel |
| `Dockerfile` | ~25 | Container definition |
| `docker-compose.yml` | ~20 | One-command deployment |
| `requirements.txt` | ~25 | Dependencies |

---

## Evidence

**File:** `.documentation/evidence/EVIDENCE-004-oss-mvp-built.md`

---

## Notes

**Strategic split:** This OSS MVP is intentionally simple. The commercial version (separate repo) will use Temporal for durability. This keeps the OSS version approachable while allowing the commercial version to be robust.

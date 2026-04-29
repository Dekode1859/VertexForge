# ADR-002: OSS vs Commercial Split

**Date:** 2025-04-25
**Status:** Accepted
**Deciders:** User (Pratik)

---

## Context

VertexForge has two target use cases:
1. **OSS users:** Want to self-host simple multi-agent pipelines
2. **Commercial users:** Need durable execution, retries, observability

The question is whether to build one codebase with optional durability, or split into two separate products.

---

## Decision

**Split into two separate repositories:**

| Aspect | OSS Version | Commercial Version |
|--------|-------------|---------------------|
| **Repository** | `VertexForge` (public) | Private repo (future) |
| **Execution** | In-process asyncio | Temporal workflows |
| **Persistence** | SQLite | PostgreSQL + Temporal |
| **Durability** | None (re-run on failure) | Full checkpointing |
| **Complexity** | Single container | Kubernetes + Temporal |
| **Target** | Developers, hobbyists | Teams, enterprises |

---

## Rationale

### Why Split?

1. **Simplicity for OSS:**
   - One `docker-compose up` and it works
   - No infrastructure to manage
   - Easy to understand and modify

2. **Complexity for Commercial:**
   - Temporal adds significant infrastructure
   - Worker processes, queues, databases
   - Worth it for production, overkill for OSS

3. **Different audiences:**
   - OSS users want to tinker
   - Commercial users want reliability

### Why Not One Codebase?

- **Conditional complexity** makes both versions worse
- **Temporal overhead** even when not used
- **Harder to reason about** - two execution paths
- **Deployment confusion** - is this simple or durable mode?

---

## Consequences

### Positive
- OSS version stays approachable
- Commercial version can be truly robust
- Clear value differentiation
- Each codebase optimized for its use case

### Negative
- Two codebases to maintain (mitigated: share compiler.py)
- Feature parity decisions needed
- User confusion about which to choose

---

## Shared Components

Both versions share:
- `schema.py` - Pydantic models
- `compiler.py` - JSON to StateGraph (with Temporal adapter for commercial)
- `tools.py` - Tool definitions

Only execution layer differs:
- OSS: `api.py` with asyncio
- Commercial: Temporal workflows

---

## Migration Path

Users can start with OSS, migrate to commercial if they need:
- Durability
- Execution history
- Automatic retries
- Multi-user teams

Export JSON config from OSS, import to commercial.

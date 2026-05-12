"""
VertexForge OSS API
FastAPI server for the open-source multi-agent compiler.

Features:
- REST endpoints for pipeline CRUD
- WebSocket execution with real-time streaming
- SQLite persistence
- In-process execution (no queues, no distributed systems)
- Phoenix observability tracing
"""

import json
import asyncio
import sqlite3
import uuid
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from vertexforge.compiler import GraphBuilder, _build_initial_state, _extract_final_output
from vertexforge.ingestion import IngestionService, SqliteArtifactRepository, create_default_registry
from vertexforge.schema import GraphConfig
from langchain_core.messages import HumanMessage

# Phoenix Observability - setup tracing before any LangChain/LangGraph imports
phoenix_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
if phoenix_endpoint:
    try:
        from phoenix.otel import register
        from openinference.instrumentation.langchain import LangChainInstrumentor
        
        tracer_provider = register(
            endpoint=f"{phoenix_endpoint}/v1/traces",
            project_name=os.getenv("PHOENIX_PROJECT_NAME", "vertexforge"),
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        print(f"[OK] Phoenix tracing enabled: {phoenix_endpoint}")
    except Exception as e:
        print(f"[WARN] Phoenix tracing not enabled: {e}")

# Database setup
DB_PATH = Path("data/vertexforge.db")
DB_PATH.parent.mkdir(exist_ok=True)
SOURCE_STORAGE_DIR = Path("data/sources")
ARTIFACT_STORAGE_DIR = Path("data/artifacts")


def init_db():
    """Initialize SQLite database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            config_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS executions (
            id TEXT PRIMARY KEY,
            pipeline_id TEXT NOT NULL,
            status TEXT NOT NULL,
            input TEXT,
            final_output TEXT,
            node_outputs TEXT,
            error_message TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
        )
    """)
    
    conn.commit()
    conn.close()


def get_ingestion_repository() -> SqliteArtifactRepository:
    """Create an ingestion repository backed by the main app database."""
    return SqliteArtifactRepository(
        db_path=DB_PATH,
        artifact_root=ARTIFACT_STORAGE_DIR,
    )


def get_ingestion_service() -> IngestionService:
    """Create the ingestion service."""
    return IngestionService(
        repository=get_ingestion_repository(),
        registry=create_default_registry(),
    )


def save_uploaded_file(upload: UploadFile) -> Path:
    """Persist an uploaded file to local storage."""
    SOURCE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    original_name = Path(upload.filename or "upload.bin").name
    target_dir = SOURCE_STORAGE_DIR / uuid.uuid4().hex
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / original_name
    with target_path.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)
    return target_path


# Execution state tracking
active_executions: Dict[str, Dict] = {}


async def run_pipeline_execution(execution_id: str):
    """Background task to run pipeline execution."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get execution info
        cursor.execute("SELECT * FROM executions WHERE id = ?", (execution_id,))
        execution = cursor.fetchone()
        if not execution:
            conn.close()
            return
        
        # Get pipeline config
        cursor.execute("SELECT * FROM pipelines WHERE id = ?", (execution["pipeline_id"],))
        pipeline = cursor.fetchone()
        conn.close()
        
        if not pipeline:
            return
        
        try:
            config = GraphConfig.model_validate(json.loads(pipeline["config_json"]))
            builder = GraphBuilder(config, artifact_repository=get_ingestion_repository())
            graph = builder.build()
        except Exception as e:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE executions SET status = ?, error_message = ?, completed_at = ? WHERE id = ?",
                ("failed", str(e), datetime.now().isoformat(), execution_id)
            )
            conn.commit()
            conn.close()
            return
        
        # Track execution
        start_time = datetime.now()
        tool_calls = []
        
        active_executions[execution_id] = {
            "status": "running",
            "start_time": start_time,
            "tool_calls": tool_calls
        }
        
        try:
            initial_state = _build_initial_state(config, execution["input"])
            async for event in graph.astream_events(
                initial_state,
                version="v2",
            ):
                event_type = event.get("event", "")
                
                if event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")
                    tool_calls.append({"tool": tool_name, "output": str(tool_output)})
            
            # Get final result
            result = graph.invoke(initial_state)
            final_output = _extract_final_output(config, result)
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE executions 
                SET status = ?, final_output = ?, node_outputs = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    "completed",
                    final_output,
                    json.dumps(tool_calls),
                    datetime.now().isoformat(),
                    execution_id
                )
            )
            conn.commit()
            conn.close()
            
            active_executions[execution_id]["status"] = "completed"
            
        except Exception as e:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE executions SET status = ?, error_message = ?, completed_at = ? WHERE id = ?",
                ("failed", str(e), datetime.now().isoformat(), execution_id)
            )
            conn.commit()
            conn.close()
            active_executions[execution_id]["status"] = "failed"
            
    except Exception as e:
        print(f"Background execution error: {e}")


# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


app = FastAPI(
    title="VertexForge OSS",
    description="Open-source multi-agent linear compiler",
    version="0.1.0",
    lifespan=lifespan
)

# Serve static files (form.html, etc.)
# Create static dir if it doesn't exist
import os
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Pydantic models for API
class PipelineCreate(BaseModel):
    name: str = Field(..., description="Pipeline name")
    description: Optional[str] = Field(None, description="Pipeline description")
    config: Dict = Field(..., description="JSON configuration")


class PipelineResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    config: Dict
    created_at: str


class ExecutionRequest(BaseModel):
    input: str = Field(..., description="Input text for the pipeline")


class ExecutionResponse(BaseModel):
    id: str
    pipeline_id: str
    status: str
    input: str
    started_at: str


class NodeOutput(BaseModel):
    node_id: str
    input: str
    output: str
    tools_used: List[str]
    duration_ms: int


class SourceResponse(BaseModel):
    source_id: str
    filename: str
    display_name: str
    mime_type: str
    file_extension: str
    size_bytes: int
    sha256: str
    storage_uri: str
    detected_type: str
    upload_status: str
    created_at: str
    artifact_count: int = 0


class ArtifactResponse(BaseModel):
    artifact_id: str
    source_id: str
    parent_artifact_id: Optional[str]
    artifact_type: str
    subtype: str
    title: Optional[str]
    status: str
    content_format: str
    content_uri: Optional[str]
    preview_text: Optional[str]
    payload: Dict = Field(default_factory=dict)
    metadata: Dict = Field(default_factory=dict)
    provenance: Dict = Field(default_factory=dict)
    extraction: Dict = Field(default_factory=dict)
    created_at: str


def build_source_response(source, artifact_count: int = 0) -> SourceResponse:
    """Convert a source model into an API response."""
    return SourceResponse(
        source_id=source.source_id,
        filename=source.filename,
        display_name=source.display_name,
        mime_type=source.mime_type,
        file_extension=source.file_extension,
        size_bytes=source.size_bytes,
        sha256=source.sha256,
        storage_uri=source.storage_uri,
        detected_type=source.detected_type,
        upload_status=source.upload_status,
        created_at=source.created_at,
        artifact_count=artifact_count,
    )


def build_artifact_response(artifact) -> ArtifactResponse:
    """Convert an artifact model into an API response."""
    return ArtifactResponse(
        artifact_id=artifact.artifact_id,
        source_id=artifact.source_id,
        parent_artifact_id=artifact.parent_artifact_id,
        artifact_type=artifact.artifact_type,
        subtype=artifact.subtype,
        title=artifact.title,
        status=artifact.status,
        content_format=artifact.content_format,
        content_uri=artifact.content_uri,
        preview_text=artifact.preview_text,
        payload=artifact.payload,
        metadata=artifact.metadata,
        provenance=artifact.provenance,
        extraction=artifact.extraction,
        created_at=artifact.created_at,
    )


# Database helpers
def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# REST Endpoints
def serve_page(filename: str) -> HTMLResponse:
    """Helper to serve HTML files from static directory."""
    path = Path("static") / filename
    if not path.exists():
        path = Path(filename)
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect root to builder."""
    return serve_page("builder.html")


@app.get("/builder", response_class=HTMLResponse)
async def builder_page():
    """Serve the pipeline builder page."""
    return serve_page("builder.html")


@app.get("/pipelines", response_class=HTMLResponse)
async def pipelines_page():
    """Serve the saved pipelines list page."""
    return serve_page("pipelines.html")


@app.get("/executions", response_class=HTMLResponse)
async def executions_page():
    """Serve the executions history page."""
    return serve_page("executions.html")


@app.get("/executions/{execution_id}/view", response_class=HTMLResponse)
async def execution_detail_page(execution_id: str):
    """Serve the execution detail/log viewer page."""
    return serve_page("execution_detail.html")


@app.get("/sources", response_class=HTMLResponse)
async def sources_page():
    """Serve the ingestion sources page."""
    return serve_page("sources.html")


@app.post("/api/pipelines", response_model=PipelineResponse)
async def create_pipeline(pipeline: PipelineCreate):
    """Create a new pipeline configuration."""
    pipeline_id = str(uuid.uuid4())

    try:
        config_obj = GraphConfig.model_validate(pipeline.config)
        GraphBuilder(config_obj, artifact_repository=get_ingestion_repository()).validate_structure()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid config: {str(e)}")
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO pipelines (id, name, description, config_json)
        VALUES (?, ?, ?, ?)
        """,
        (pipeline_id, pipeline.name, pipeline.description, json.dumps(pipeline.config))
    )
    
    conn.commit()
    
    # Fetch created record
    cursor.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,))
    row = cursor.fetchone()
    conn.close()
    
    return PipelineResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        config=json.loads(row["config_json"]),
        created_at=row["created_at"]
    )


@app.get("/api/pipelines", response_model=List[PipelineResponse])
async def list_pipelines():
    """List all saved pipelines."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM pipelines ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        PipelineResponse(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            config=json.loads(row["config_json"]),
            created_at=row["created_at"]
        )
        for row in rows
    ]


@app.get("/api/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: str):
    """Get a specific pipeline by ID."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    return PipelineResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        config=json.loads(row["config_json"]),
        created_at=row["created_at"]
    )


@app.delete("/api/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    """Delete a pipeline."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM pipelines WHERE id = ?", (pipeline_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    conn.commit()
    conn.close()
    
    return {"message": "Pipeline deleted"}


from fastapi import BackgroundTasks

@app.post("/api/pipelines/{pipeline_id}/execute", response_model=ExecutionResponse)
async def execute_pipeline(pipeline_id: str, request: ExecutionRequest, background_tasks: BackgroundTasks):
    """Start pipeline execution (runs in background, use WebSocket for progress)."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify pipeline exists
    cursor.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    # Create execution record
    execution_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO executions (id, pipeline_id, status, input)
        VALUES (?, ?, ?, ?)
        """,
        (execution_id, pipeline_id, "running", request.input)
    )
    
    conn.commit()
    conn.close()
    
    # Start execution in background - WebSocket just streams, doesn't trigger
    background_tasks.add_task(run_pipeline_execution, execution_id)
    
    return ExecutionResponse(
        id=execution_id,
        pipeline_id=pipeline_id,
        status="running",
        input=request.input,
        started_at=datetime.now().isoformat()
    )


@app.get("/api/executions/{execution_id}")
async def get_execution(execution_id: str):
    """Get execution status and results."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM executions WHERE id = ?", (execution_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return {
        "id": row["id"],
        "pipeline_id": row["pipeline_id"],
        "status": row["status"],
        "input": row["input"],
        "final_output": row["final_output"],
        "node_outputs": json.loads(row["node_outputs"]) if row["node_outputs"] else [],
        "error_message": row["error_message"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"]
    }


@app.get("/api/executions")
async def list_executions():
    """List all executions with pipeline names."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT e.id, e.pipeline_id, e.status, e.input, e.final_output,
               e.error_message, e.started_at, e.completed_at,
               p.name as pipeline_name
        FROM executions e
        JOIN pipelines p ON e.pipeline_id = p.id
        ORDER BY e.started_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row["id"],
            "pipeline_id": row["pipeline_id"],
            "pipeline_name": row["pipeline_name"],
            "status": row["status"],
            "input": row["input"],
            "final_output": row["final_output"],
            "error_message": row["error_message"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"]
        }
        for row in rows
    ]


@app.post("/api/sources/upload", response_model=SourceResponse)
async def upload_source(file: UploadFile = File(...)):
    """Upload a file and ingest it into source/artifact storage."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename")

    try:
        saved_path = save_uploaded_file(file)
        result = get_ingestion_service().ingest_file(saved_path)
        return build_source_response(result.source, artifact_count=len(result.artifacts))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Source ingestion failed: {exc}") from exc
    finally:
        await file.close()


@app.get("/api/sources", response_model=List[SourceResponse])
async def list_sources():
    """List all ingested sources."""
    repository = get_ingestion_repository()
    sources = repository.list_sources()
    return [
        build_source_response(source, artifact_count=len(repository.list_artifacts(source.source_id)))
        for source in sources
    ]


@app.get("/api/sources/{source_id}", response_model=SourceResponse)
async def get_source(source_id: str):
    """Get a single ingested source."""
    repository = get_ingestion_repository()
    source = repository.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return build_source_response(source, artifact_count=len(repository.list_artifacts(source_id)))


@app.get("/api/sources/{source_id}/artifacts", response_model=List[ArtifactResponse])
async def get_source_artifacts(source_id: str):
    """List artifacts generated for a source."""
    repository = get_ingestion_repository()
    source = repository.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return [build_artifact_response(artifact) for artifact in repository.list_artifacts(source_id)]


# WebSocket for real-time execution streaming
class ExecutionManager:
    """Manages active WebSocket connections for execution streaming."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, execution_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[execution_id] = websocket
    
    def disconnect(self, execution_id: str):
        self.active_connections.pop(execution_id, None)
    
    async def send_event(self, execution_id: str, event: Dict):
        if execution_id in self.active_connections:
            await self.active_connections[execution_id].send_json(event)


manager = ExecutionManager()


@app.websocket("/ws/execute/{execution_id}")
async def websocket_execute(websocket: WebSocket, execution_id: str):
    """
    WebSocket endpoint for real-time execution streaming with tool call observability.
    
    Events sent:
    - execution_start: Pipeline begins
    - tool_call_start: Tool execution starts (with input)
    - tool_call_end: Tool execution completes (with output)
    - complete: Final output with timing
    - error: Failure message
    """
    await manager.connect(execution_id, websocket)
    connection_open = True
    
    async def safe_send(event):
        """Safely send event to WebSocket, ignore if connection closed."""
        nonlocal connection_open
        if not connection_open:
            return
        try:
            await websocket.send_json(event)
        except (WebSocketDisconnect, RuntimeError):
            connection_open = False
    
    try:
        # Get execution info
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM executions WHERE id = ?", (execution_id,))
        execution = cursor.fetchone()
        
        if not execution:
            await safe_send({"type": "error", "message": "Execution not found"})
            return
        
        # Get pipeline config
        cursor.execute("SELECT * FROM pipelines WHERE id = ?", (execution["pipeline_id"],))
        pipeline = cursor.fetchone()
        conn.close()
        
        if not pipeline:
            await safe_send({"type": "error", "message": "Pipeline not found"})
            return
        
        try:
            config = GraphConfig.model_validate(json.loads(pipeline["config_json"]))
            builder = GraphBuilder(config, artifact_repository=get_ingestion_repository())
            graph = builder.build()
        except Exception as e:
            await safe_send({"type": "error", "message": f"Compilation error: {str(e)}"})
            return
        
        initial_state = _build_initial_state(config, execution["input"])
        
        # Track execution
        start_time = datetime.now()
        tool_calls = []
        final_result = None
        
        try:
            # Send start event
            await safe_send({
                "type": "execution_start",
                "execution_id": execution_id,
                "pipeline_name": pipeline["name"],
                "timestamp": start_time.isoformat()
            })
            
            # Execute graph with event streaming
            # astream_events runs the graph AND streams events
            async for event in graph.astream_events(
                initial_state,
                version="v2",
            ):
                event_type = event.get("event", "")
                
                if event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", "")
                    
                    await safe_send({
                        "type": "tool_call_start",
                        "tool": tool_name,
                        "input": str(tool_input) if tool_input else "",
                        "timestamp": datetime.now().isoformat()
                    })
                
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")
                    tool_error = event.get("data", {}).get("error", "")
                    
                    tool_calls.append({
                        "tool": tool_name,
                        "output": str(tool_output) if tool_output else ""
                    })
                    
                    await safe_send({
                        "type": "tool_call_end",
                        "tool": tool_name,
                        "output": str(tool_output) if tool_output else "",
                        "error": str(tool_error) if tool_error else "",
                        "timestamp": datetime.now().isoformat()
                    })
            
            # After streaming completes, get final state
            # The astream_events already ran the graph, so we need to get the result
            # We can re-run with invoke or track state during streaming
            # For now, invoke again (inefficient but works for MVP)
            result = graph.invoke(initial_state)
            final_result = result
            
            # Calculate duration
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            
            final_output = _extract_final_output(config, result)
            
            # Update execution record
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE executions 
                SET status = ?, final_output = ?, node_outputs = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    "completed",
                    final_output,
                    json.dumps(tool_calls),
                    datetime.now().isoformat(),
                    execution_id
                )
            )
            conn.commit()
            conn.close()
            
            # Send completion event
            await safe_send({
                "type": "complete",
                "final_output": final_output,
                "total_duration_ms": duration,
                "nodes_executed": result.get("iteration_count", 0),
                "tool_calls_count": len(tool_calls)
            })
            
        except Exception as e:
            # Update execution record with error
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE executions 
                SET status = ?, error_message = ?, completed_at = ?
                WHERE id = ?
                """,
                ("failed", str(e), datetime.now().isoformat(), execution_id)
            )
            conn.commit()
            conn.close()
            
            await safe_send({"type": "error", "message": str(e)})
    
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(execution_id)


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker."""
    return {"status": "healthy", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


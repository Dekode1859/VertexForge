"""Persistence interfaces for ingestion sources and artifacts."""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path

from vertexforge.ingestion.models import ArtifactRecord, IngestionResult, SourceRecord


class ArtifactRepository(ABC):
    """Abstract persistence contract for ingestion data."""

    @abstractmethod
    def init_storage(self) -> None:
        """Initialize persistence primitives."""

    @abstractmethod
    def save_ingestion(self, result: IngestionResult) -> IngestionResult:
        """Persist a source and its artifacts."""

    @abstractmethod
    def list_sources(self) -> list[SourceRecord]:
        """Return stored sources."""

    @abstractmethod
    def get_source(self, source_id: str) -> SourceRecord | None:
        """Return a stored source if it exists."""

    @abstractmethod
    def list_artifacts(self, source_id: str) -> list[ArtifactRecord]:
        """Return stored artifacts for a source."""

    @abstractmethod
    def get_artifact_payload(self, artifact_id: str) -> dict:
        """Return a persisted artifact payload."""


class SqliteArtifactRepository(ArtifactRepository):
    """SQLite-backed repository with JSON payload files on disk."""

    def __init__(self, db_path: Path, artifact_root: Path) -> None:
        self.db_path = db_path
        self.artifact_root = artifact_root
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.init_storage()

    def init_storage(self) -> None:
        """Create tables if they do not exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                display_name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                file_extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                storage_uri TEXT NOT NULL,
                detected_type TEXT NOT NULL,
                upload_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                parent_artifact_id TEXT,
                sort_order INTEGER NOT NULL,
                artifact_type TEXT NOT NULL,
                subtype TEXT NOT NULL,
                title TEXT,
                status TEXT NOT NULL,
                content_format TEXT NOT NULL,
                content_uri TEXT NOT NULL,
                preview_text TEXT,
                metadata_json TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                extraction_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES sources(source_id)
            )
            """
        )
        conn.commit()
        conn.close()

    def save_ingestion(self, result: IngestionResult) -> IngestionResult:
        """Persist the source and all artifacts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        self._save_source(cursor, result.source)

        saved_artifacts: list[ArtifactRecord] = []
        for sort_order, artifact in enumerate(result.artifacts):
            payload_path = self._write_payload(artifact)
            stored = artifact.model_copy(update={"content_uri": payload_path.resolve().as_uri()})
            self._save_artifact(cursor, stored, sort_order)
            saved_artifacts.append(stored)

        conn.commit()
        conn.close()
        return IngestionResult(source=result.source, artifacts=saved_artifacts)

    def list_artifacts(self, source_id: str) -> list[ArtifactRecord]:
        """Fetch all persisted artifacts for a source."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT artifact_id, source_id, parent_artifact_id, artifact_type, subtype, title,
                   status, content_format, content_uri, preview_text, metadata_json,
                   provenance_json, extraction_json, created_at
            FROM artifacts
            WHERE source_id = ?
            ORDER BY sort_order ASC, created_at ASC, artifact_id ASC
            """,
            (source_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        artifacts: list[ArtifactRecord] = []
        for row in rows:
            artifacts.append(
                ArtifactRecord(
                    artifact_id=row["artifact_id"],
                    source_id=row["source_id"],
                    parent_artifact_id=row["parent_artifact_id"],
                    artifact_type=row["artifact_type"],
                    subtype=row["subtype"],
                    title=row["title"],
                    status=row["status"],
                    content_format=row["content_format"],
                    content_uri=row["content_uri"],
                    preview_text=row["preview_text"],
                    payload=self.get_artifact_payload(row["artifact_id"]),
                    metadata=json.loads(row["metadata_json"]),
                    provenance=json.loads(row["provenance_json"]),
                    extraction=json.loads(row["extraction_json"]),
                    created_at=row["created_at"],
                )
            )
        return artifacts

    def list_sources(self) -> list[SourceRecord]:
        """Fetch all persisted sources."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT source_id, filename, display_name, mime_type, file_extension, size_bytes,
                   sha256, storage_uri, detected_type, upload_status, created_at
            FROM sources
            ORDER BY created_at DESC, source_id DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_source(row) for row in rows]

    def get_source(self, source_id: str) -> SourceRecord | None:
        """Fetch a single source."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT source_id, filename, display_name, mime_type, file_extension, size_bytes,
                   sha256, storage_uri, detected_type, upload_status, created_at
            FROM sources
            WHERE source_id = ?
            """,
            (source_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return self._row_to_source(row)

    def get_artifact_payload(self, artifact_id: str) -> dict:
        """Read a JSON payload from disk."""
        payload_path = self.artifact_root / f"{artifact_id}.json"
        return json.loads(payload_path.read_text(encoding="utf-8"))

    def _write_payload(self, artifact: ArtifactRecord) -> Path:
        """Write an artifact payload to disk."""
        payload_path = self.artifact_root / f"{artifact.artifact_id}.json"
        payload_path.write_text(json.dumps(artifact.payload, indent=2), encoding="utf-8")
        return payload_path

    def _save_source(self, cursor: sqlite3.Cursor, source: SourceRecord) -> None:
        """Insert or replace a source row."""
        cursor.execute(
            """
            INSERT OR REPLACE INTO sources (
                source_id, filename, display_name, mime_type, file_extension, size_bytes,
                sha256, storage_uri, detected_type, upload_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.source_id,
                source.filename,
                source.display_name,
                source.mime_type,
                source.file_extension,
                source.size_bytes,
                source.sha256,
                source.storage_uri,
                source.detected_type,
                source.upload_status,
                source.created_at,
            ),
        )

    def _row_to_source(self, row: sqlite3.Row) -> SourceRecord:
        """Convert a SQLite row to a source model."""
        return SourceRecord(
            source_id=row["source_id"],
            filename=row["filename"],
            display_name=row["display_name"],
            mime_type=row["mime_type"],
            file_extension=row["file_extension"],
            size_bytes=row["size_bytes"],
            sha256=row["sha256"],
            storage_uri=row["storage_uri"],
            detected_type=row["detected_type"],
            upload_status=row["upload_status"],
            created_at=row["created_at"],
        )

    def _save_artifact(
        self,
        cursor: sqlite3.Cursor,
        artifact: ArtifactRecord,
        sort_order: int,
    ) -> None:
        """Insert or replace an artifact row."""
        cursor.execute(
            """
            INSERT OR REPLACE INTO artifacts (
                artifact_id, source_id, parent_artifact_id, sort_order, artifact_type, subtype, title,
                status, content_format, content_uri, preview_text, metadata_json,
                provenance_json, extraction_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact.artifact_id,
                artifact.source_id,
                artifact.parent_artifact_id,
                sort_order,
                artifact.artifact_type,
                artifact.subtype,
                artifact.title,
                artifact.status,
                artifact.content_format,
                artifact.content_uri or "",
                artifact.preview_text,
                json.dumps(artifact.metadata),
                json.dumps(artifact.provenance),
                json.dumps(artifact.extraction),
                artifact.created_at,
            ),
        )


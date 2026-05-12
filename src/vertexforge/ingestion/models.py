"""Normalized models for ingestion sources and artifacts."""

from __future__ import annotations

import hashlib
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def build_source_id() -> str:
    """Create a source identifier."""
    return f"src_{uuid.uuid4().hex[:12]}"


def build_artifact_id() -> str:
    """Create an artifact identifier."""
    return f"art_{uuid.uuid4().hex[:12]}"


def calculate_sha256(path: Path) -> str:
    """Compute the SHA-256 checksum for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SourceRecord(BaseModel):
    """Uploaded source metadata."""

    source_id: str
    filename: str
    display_name: str
    mime_type: str
    file_extension: str
    size_bytes: int
    sha256: str
    storage_uri: str
    detected_type: str
    upload_status: str = "uploaded"
    created_at: str = Field(default_factory=utc_now_iso)

    @classmethod
    def from_path(cls, path: Path, detected_type: str) -> "SourceRecord":
        """Build a source record for a local file."""
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return cls(
            source_id=build_source_id(),
            filename=path.name,
            display_name=path.stem,
            mime_type=mime_type,
            file_extension=path.suffix.lower(),
            size_bytes=path.stat().st_size,
            sha256=calculate_sha256(path),
            storage_uri=path.resolve().as_uri(),
            detected_type=detected_type,
        )


class ArtifactRecord(BaseModel):
    """Normalized artifact emitted by a loader."""

    artifact_id: str
    source_id: str
    parent_artifact_id: str | None = None
    artifact_type: str
    subtype: str
    title: str | None = None
    status: str = "ready"
    content_format: str = "json"
    content_uri: str | None = None
    preview_text: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    extraction: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        artifact_type: str,
        subtype: str,
        title: str | None = None,
        parent_artifact_id: str | None = None,
        preview_text: str | None = None,
        payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        extraction: dict[str, Any] | None = None,
        content_format: str = "json",
    ) -> "ArtifactRecord":
        """Convenience constructor with generated identifier."""
        return cls(
            artifact_id=build_artifact_id(),
            source_id=source_id,
            parent_artifact_id=parent_artifact_id,
            artifact_type=artifact_type,
            subtype=subtype,
            title=title,
            preview_text=preview_text,
            payload=payload or {},
            metadata=metadata or {},
            provenance=provenance or {},
            extraction=extraction or {},
            content_format=content_format,
        )


class IngestionResult(BaseModel):
    """A source and its emitted artifacts."""

    source: SourceRecord
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


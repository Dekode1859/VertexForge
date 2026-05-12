"""Ingestion layer primitives for source loading and artifact storage."""

from vertexforge.ingestion.models import ArtifactRecord, IngestionResult, SourceRecord
from vertexforge.ingestion.registry import IngestionService, LoaderRegistry, create_default_registry
from vertexforge.ingestion.repository import ArtifactRepository, SqliteArtifactRepository

__all__ = [
    "ArtifactRecord",
    "ArtifactRepository",
    "IngestionResult",
    "IngestionService",
    "LoaderRegistry",
    "SourceRecord",
    "SqliteArtifactRepository",
    "create_default_registry",
]


"""Base contract for pluggable ingestion loaders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from vertexforge.ingestion.models import IngestionResult, SourceRecord


class BaseLoader(ABC):
    """Loader interface for deterministic source ingestion."""

    name: str
    detected_type: str
    supported_extensions: tuple[str, ...]

    def can_load(self, path: Path) -> bool:
        """Return whether the loader supports the file."""
        return path.suffix.lower() in self.supported_extensions

    def build_source(self, path: Path) -> SourceRecord:
        """Create a standardized source record for the file."""
        return SourceRecord.from_path(path, detected_type=self.detected_type)

    @abstractmethod
    def load(self, path: Path) -> IngestionResult:
        """Load a file and return normalized artifacts."""



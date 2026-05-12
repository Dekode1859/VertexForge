"""Loader registry and ingestion service."""

from __future__ import annotations

from pathlib import Path

from vertexforge.ingestion.loaders.base import BaseLoader
from vertexforge.ingestion.loaders.document import DocumentLoader
from vertexforge.ingestion.loaders.pdf import PdfLoader
from vertexforge.ingestion.loaders.spreadsheet import SpreadsheetLoader
from vertexforge.ingestion.models import IngestionResult
from vertexforge.ingestion.repository import ArtifactRepository


class LoaderRegistry:
    """Registry for pluggable source loaders."""

    def __init__(self) -> None:
        self._loaders: list[BaseLoader] = []

    def register(self, loader: BaseLoader) -> None:
        """Register a loader instance."""
        self._loaders.append(loader)

    def get_loader_for_path(self, path: Path) -> BaseLoader:
        """Resolve the first loader that supports the file."""
        for loader in self._loaders:
            if loader.can_load(path):
                return loader
        raise ValueError(f"No loader registered for extension '{path.suffix.lower()}'")

    def load(self, path: Path) -> IngestionResult:
        """Load a path through the matching loader."""
        return self.get_loader_for_path(path).load(path)


def create_default_registry() -> LoaderRegistry:
    """Create the built-in loader registry."""
    registry = LoaderRegistry()
    registry.register(DocumentLoader())
    registry.register(SpreadsheetLoader())
    registry.register(PdfLoader())
    return registry


class IngestionService:
    """High-level ingestion coordinator."""

    def __init__(self, repository: ArtifactRepository, registry: LoaderRegistry | None = None) -> None:
        self.repository = repository
        self.registry = registry or create_default_registry()

    def ingest_file(self, path: Path) -> IngestionResult:
        """Load a file and persist the source plus its artifacts."""
        result = self.registry.load(path)
        return self.repository.save_ingestion(result)


"""Deterministic loader for plain-text document formats."""

from __future__ import annotations

from pathlib import Path

from vertexforge.ingestion.loaders.base import BaseLoader
from vertexforge.ingestion.models import ArtifactRecord, IngestionResult


class DocumentLoader(BaseLoader):
    """Loader for plain text and markdown documents."""

    name = "document_loader"
    detected_type = "document"
    supported_extensions = (".md", ".txt")

    def load(self, path: Path) -> IngestionResult:
        """Read the file and emit document and text artifacts."""
        source = self.build_source(path)
        text = path.read_text(encoding="utf-8", errors="replace")

        lines = text.splitlines()
        document_artifact = ArtifactRecord.create(
            source_id=source.source_id,
            artifact_type="document",
            subtype="plain_text_document",
            title=source.display_name,
            preview_text=text[:200] or None,
            payload={
                "character_count": len(text),
                "word_count": len(text.split()),
                "line_count": len(lines),
                "contains_extractable_text": bool(text.strip()),
            },
            provenance={
                "source_filename": source.filename,
                "origin_loader": self.name,
                "extraction_method": "direct_text_read",
            },
            extraction={"confidence": 1.0, "warnings": [], "fallback_used": False},
        )

        text_artifact = ArtifactRecord.create(
            source_id=source.source_id,
            parent_artifact_id=document_artifact.artifact_id,
            artifact_type="text_block",
            subtype="document_full_text",
            title=f"{source.display_name} text",
            preview_text=text[:200] or None,
            payload={"text": text},
            provenance={
                "source_filename": source.filename,
                "block_index": 0,
                "origin_loader": self.name,
                "extraction_method": "direct_text_read",
            },
            extraction={"confidence": 1.0, "warnings": [], "fallback_used": False},
            content_format="text",
        )

        return IngestionResult(source=source, artifacts=[document_artifact, text_artifact])


"""Thin PDF ingestion with page-level deterministic extraction."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from vertexforge.ingestion.loaders.base import BaseLoader
from vertexforge.ingestion.models import ArtifactRecord, IngestionResult


def _looks_tabular(text: str) -> bool:
    """Heuristic to flag text that may represent table-like structure."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    numeric_lines = sum(bool(re.search(r"\d", line)) for line in lines)
    delimiter_lines = sum(("  " in line) or ("\t" in line) for line in lines)
    return len(lines) >= 3 and numeric_lines >= 2 and delimiter_lines >= 1


class PdfLoader(BaseLoader):
    """Thin PDF loader that emits document and page artifacts."""

    name = "pdf_loader"
    detected_type = "pdf"
    supported_extensions = (".pdf",)

    def load(self, path: Path) -> IngestionResult:
        """Load a PDF using native text extraction only."""
        source = self.build_source(path)
        if source.size_bytes == 0:
            raise ValueError("PDF file is empty (0 bytes)")

        try:
            reader = PdfReader(str(path))
        except PdfReadError as exc:
            raise ValueError(f"Failed to read PDF: {exc}") from exc

        page_artifacts: list[ArtifactRecord] = []
        contains_text = False

        document_artifact = ArtifactRecord.create(
            source_id=source.source_id,
            artifact_type="document",
            subtype="pdf_document",
            title=source.display_name,
            provenance={
                "source_filename": source.filename,
                "origin_loader": self.name,
                "origin_parser": "pypdf",
                "extraction_method": "native_pdf_parse",
            },
            extraction={"confidence": 1.0, "warnings": [], "fallback_used": False, "ocr_used": False},
        )

        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            contains_text = contains_text or bool(text.strip())
            warnings: list[str] = []
            low_text = len(text.strip()) < 20
            possible_image_only = not bool(text.strip())
            possible_tabular_content = _looks_tabular(text)

            if possible_image_only:
                warnings.append("page_has_no_extractable_text")
            elif low_text:
                warnings.append("page_has_low_text")
            if possible_tabular_content:
                warnings.append("possible_tabular_content")

            page_artifact = ArtifactRecord.create(
                source_id=source.source_id,
                parent_artifact_id=document_artifact.artifact_id,
                artifact_type="page",
                subtype="pdf_page",
                title=f"Page {index}",
                preview_text=text[:200] or None,
                payload={
                    "page_number": index,
                    "text": text,
                    "character_count": len(text),
                    "line_count": len(text.splitlines()),
                    "possible_image_only": possible_image_only,
                    "low_text": low_text,
                    "possible_tabular_content": possible_tabular_content,
                },
                provenance={
                    "source_filename": source.filename,
                    "page_number": index,
                    "origin_loader": self.name,
                    "origin_parser": "pypdf",
                    "extraction_method": "native_pdf_parse",
                },
                extraction={
                    "confidence": 1.0 if text.strip() else 0.25,
                    "warnings": warnings,
                    "fallback_used": False,
                    "ocr_used": False,
                },
                content_format="text",
            )
            page_artifacts.append(page_artifact)

        document_artifact.payload = {
            "page_count": len(reader.pages),
            "contains_extractable_text": contains_text,
        }
        if not contains_text:
            document_artifact.extraction["warnings"] = ["document_may_require_ocr"]

        return IngestionResult(source=source, artifacts=[document_artifact, *page_artifacts])


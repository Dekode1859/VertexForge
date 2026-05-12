"""Built-in ingestion loaders."""

from vertexforge.ingestion.loaders.document import DocumentLoader
from vertexforge.ingestion.loaders.pdf import PdfLoader
from vertexforge.ingestion.loaders.spreadsheet import SpreadsheetLoader

__all__ = ["DocumentLoader", "PdfLoader", "SpreadsheetLoader"]


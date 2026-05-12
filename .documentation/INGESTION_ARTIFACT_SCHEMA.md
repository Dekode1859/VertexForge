# Ingestion Artifact Schema and Loader Plugin Contract

> **Project:** VertexForge
> **Phase:** D1 Design
> **Status:** Draft for implementation
> **Purpose:** Define the ingestion artifact model, loader plugin contract, storage expectations, and downstream usage patterns for generalized workflow orchestration.

---

## 1. Goal

VertexForge needs a loader layer that can ingest common enterprise files and convert them into **normalized artifacts** that later workflow nodes can:

- inspect in the UI
- route through pipelines
- transform into tables, chunks, or images
- use in RAG
- connect across documents
- trace back to their original source

The loader layer should **not** do opinionated LLM reasoning by default.

Its job is to:

1. detect the source type
2. extract what can be extracted deterministically
3. preserve provenance and confidence
4. normalize the output into a shared artifact schema
5. expose thin previews in the UI

This design intentionally separates:

- **ingestion**
- **analysis**
- **retrieval**
- **generation**

---

## 2. Design Principles

### 2.1 Loader-first, not LLM-first

Initial ingestion should prefer deterministic extraction:

- native PDF text extraction before OCR
- spreadsheet parsing before LLM interpretation
- markdown/text parsing before semantic chunking

LLMs should sit on top of artifacts, not inside the base loader path.

### 2.2 Multi-view output

Each source should produce more than one representation when possible:

- raw metadata
- text view
- structured blocks
- tables
- image references
- preview-friendly output

### 2.3 Provenance is mandatory

Every extracted unit should be traceable to its source:

- file
- page
- sheet
- cell range
- block index
- extraction method

### 2.4 Thin UI visibility

The dashboard should show:

- uploaded sources
- detected file type
- extraction status
- warnings
- extracted artifact counts
- previews

It should not become a custom observability platform.

### 2.5 Swappable persistence

The ingestion system should target an abstract repository interface so that:

- SQLite works now
- PostgreSQL can replace it later
- object/file storage can evolve independently

---

## 3. Scope for Initial Loader System

### 3.1 Initial implementation priority

The first implementation should focus on the loader types that are:

- easiest to validate deterministically
- most useful in document-heavy business workflows
- least dependent on LLM interpretation

Recommended order:

1. Document loader
2. Spreadsheet loader
3. PDF loader

### 3.2 First-wave loaders

These loaders are in scope for the first working ingestion system:

1. Document loader
2. Spreadsheet loader
3. PDF loader

### 3.3 Next-wave loaders

Useful after the first milestone:

1. HTML loader
2. JSON/XML structured loader
3. Email loader
4. Image loader

### 3.4 Out of scope for initial implementation

- audio/video loaders
- browser-native page capture
- advanced semantic chunking inside loaders
- knowledge graph creation during ingestion
- full custom workflow visualization
- image understanding pipelines
- LLM-based table reconstruction during base ingestion

---

## 4. Core Model

The loader system should treat uploaded files as **sources** and extracted outputs as **artifacts**.

### 4.1 Source

A **Source** is the uploaded object itself.

Suggested fields:

```json
{
  "source_id": "src_01H...",
  "workspace_id": "ws_01H...",
  "filename": "audited_financials_2024.pdf",
  "display_name": "Audited Financials 2024",
  "mime_type": "application/pdf",
  "file_extension": ".pdf",
  "size_bytes": 1827364,
  "sha256": "abc123...",
  "storage_uri": "file://... or blob://...",
  "detected_type": "pdf",
  "upload_status": "uploaded",
  "created_at": "2026-05-04T12:00:00Z"
}
```

### 4.2 Artifact

An **Artifact** is a normalized extracted object created from a source.

Artifacts should support multiple kinds:

- `document`
- `page`
- `sheet`
- `text_block`
- `table`
- `image`
- `ocr_text`
- `chunk`
- `metadata`

Suggested top-level artifact shape:

```json
{
  "artifact_id": "art_01H...",
  "source_id": "src_01H...",
  "parent_artifact_id": null,
  "artifact_type": "table",
  "subtype": "spreadsheet_sheet_table",
  "title": "Income Statement",
  "status": "ready",
  "content_format": "json",
  "content_uri": "artifact://art_01H...",
  "preview_text": "Revenue | COGS | EBITDA ...",
  "metadata": {},
  "provenance": {},
  "extraction": {},
  "created_at": "2026-05-04T12:00:03Z"
}
```

### 4.3 Provenance

Each artifact must preserve location in the original source.

Suggested provenance shape:

```json
{
  "source_filename": "audited_financials_2024.pdf",
  "page_number": 42,
  "sheet_name": null,
  "cell_range": null,
  "block_index": 7,
  "bbox": [120, 300, 1080, 670],
  "origin_loader": "pdf_loader",
  "origin_parser": "pymupdf",
  "extraction_method": "native_text"
}
```

### 4.4 Extraction metadata

Suggested extraction metadata shape:

```json
{
  "confidence": 0.97,
  "warnings": [],
  "ocr_used": false,
  "table_detection_used": true,
  "fallback_used": false,
  "language": "en"
}
```

---

## 5. Recommended Artifact Types

### 5.1 Document artifact

Represents the source as a logical document.

Useful fields:

- `document_type_guess`
- `page_count`
- `sheet_count`
- `contains_images`
- `contains_tables`
- `contains_extractable_text`
- `warnings`

### 5.2 Page artifact

Useful for PDFs and image-heavy sources.

Useful fields:

- `page_number`
- `native_text`
- `ocr_text`
- `image_uri`
- `text_confidence`

### 5.3 Sheet artifact

Useful for spreadsheets.

Useful fields:

- `sheet_name`
- `row_count`
- `column_count`
- `detected_tables`
- `markdown_view`

### 5.4 Table artifact

Tables should be first-class.

Suggested table content shape:

```json
{
  "table_id": "tbl_01H...",
  "headers": ["Year", "Revenue", "EBITDA"],
  "rows": [
    ["2022", "100", "22"],
    ["2023", "120", "30"]
  ],
  "markdown_view": "| Year | Revenue | EBITDA | ...",
  "csv_view": "Year,Revenue,EBITDA\n2022,100,22\n2023,120,30",
  "json_rows": [
    {"Year": "2022", "Revenue": "100", "EBITDA": "22"},
    {"Year": "2023", "Revenue": "120", "EBITDA": "30"}
  ]
}
```

Important distinction:

- spreadsheet tables can be emitted as trusted structured artifacts during ingestion
- PDF tables should not be emitted as trusted structured artifacts by default
- complex table reconstruction from PDFs belongs in a later dedicated extraction workflow

### 5.5 Text block artifact

Represents paragraph-level or section-level text segments.

Useful fields:

- `section_title`
- `text`
- `page_number`
- `block_index`

### 5.6 Image artifact

Represents image-derived assets.

Useful fields:

- `image_uri`
- `page_number`
- `ocr_available`
- `caption_guess`

---

## 5.7 Trusted vs untrusted structural extraction

This distinction is important for VertexForge.

### Trusted structural extraction

These outputs come from file formats where structure is explicit and deterministic enough to preserve directly.

Examples:

- spreadsheet sheets
- spreadsheet tables
- docx paragraph hierarchy
- docx embedded tables
- markdown headings and sections

These can be stored as normalized structured artifacts during ingestion.

### Untrusted or weak structural extraction

These outputs come from formats where visible layout does not guarantee correct machine reconstruction.

Examples:

- complex financial tables inside PDFs
- scanned tables
- OCR-derived row/column guesses
- balance sheet and income statement structures extracted from page images

These should not be treated as trusted base-ingestion artifacts.

At most, ingestion may emit:

- page text
- page image reference
- low-text warnings
- possible tabular-page hints

Actual financial table reconstruction should happen in a later dedicated extraction workflow.

---

## 6. Storage Model

The storage layer should be abstracted behind repository interfaces.

### 6.1 Repository abstraction

Suggested interfaces:

- `SourceRepository`
- `ArtifactRepository`
- `BlobRepository`

### 6.2 Near-term implementation

Recommended first implementation:

- SQLite for metadata and relational links
- filesystem for artifact blobs/previews/raw extracts

### 6.3 Future evolution

The same repository contract should support:

- PostgreSQL for metadata
- S3/GCS/local blob storage for payloads
- vector store integration later

### 6.4 Suggested persistence split

Store in DB:

- IDs
- source metadata
- artifact metadata
- provenance
- extraction status
- lightweight preview text

Store outside DB:

- rendered images
- large OCR payloads
- full markdown exports
- CSV exports
- large JSON table bodies

---

## 7. Loader Plugin Contract

Each loader should be a modular class implementing the same contract.

### 7.1 Loader responsibilities

A loader must:

1. declare what it supports
2. inspect a source
3. extract deterministic content
4. return normalized artifacts
5. emit warnings instead of hiding ambiguity

### 7.2 Suggested interface

```python
class BaseLoader(Protocol):
    loader_name: str

    def supports(self, source: SourceDescriptor) -> bool:
        ...

    def inspect(self, source: SourceDescriptor) -> InspectionResult:
        ...

    def load(self, source: SourceDescriptor, options: LoadOptions) -> LoadResult:
        ...
```

### 7.3 Suggested request models

```python
class SourceDescriptor(BaseModel):
    source_id: str
    path: str
    filename: str
    mime_type: str | None
    extension: str | None
    size_bytes: int | None


class LoadOptions(BaseModel):
    enable_ocr: bool = False
    extract_tables: bool = True
    render_pages: bool = True
    emit_markdown: bool = True
    emit_csv: bool = True
    max_preview_chars: int = 2000
```

### 7.4 Suggested result model

```python
class LoadResult(BaseModel):
    source_record: dict
    artifacts: list[dict]
    warnings: list[str]
    stats: dict
```

### 7.5 Registry contract

Loaders should be registered centrally:

```python
LOADER_REGISTRY = [
    DocumentLoader(),
    SpreadsheetLoader(),
    PdfLoader(),
]
```

Routing should be based on:

1. MIME type
2. extension
3. signature sniffing
4. loader priority

---

## 8. Loader-specific Expectations

## 8.1 PDF Loader

### Responsibilities

- detect whether native text exists
- extract page text when available
- render page images if requested
- mark pages that may require OCR
- optionally flag pages as potential table candidates using deterministic heuristics only

### Output expectations

- document artifact
- page artifacts
- text block artifacts
- image artifacts for page renders if enabled

### Important rules

- do not run OCR automatically just because PDF exists
- do not claim authoritative table extraction during base ingestion
- if text extraction fails or is empty, emit warning:
  - `native_text_missing`
  - `image_only_pdf_possible`
- if deterministic heuristics suggest tabular layout, emit a weak hint only:
  - `possible_tabular_content`

### What PDF ingestion should not do

The base PDF loader should not attempt to produce trusted structured financial tables such as:

- income statement tables
- balance sheet tables
- cash flow statement tables
- capital summaries

Those belong in later extraction workflows that may use:

- OCR
- layout recovery
- LLM-assisted table reconstruction
- validation against expected schemas
- cross-page stitching

### UI preview

- page count
- extractable text yes/no
- OCR recommended yes/no
- pages preview
- extracted text preview
- page warnings
- possible tabular-page markers

## 8.2 Spreadsheet Loader

### Responsibilities

- enumerate sheets
- preserve sheet names
- identify used ranges
- detect likely tables
- emit table views in JSON, markdown, CSV

### Output expectations

- document artifact
- sheet artifacts
- table artifacts
- optional cell-grid artifact for advanced workflows

### Important rules

- preserve row and column provenance
- preserve sheet-level metadata
- do not collapse workbook into plain text only
- spreadsheet-origin tables should be treated as trusted structural artifacts

### UI preview

- number of sheets
- detected tables per sheet
- markdown preview of sheet/table

## 8.3 Document Loader

### Responsibilities

- parse `.docx`, `.txt`, `.md`
- preserve headings where possible
- preserve embedded tables in `.docx`

### Output expectations

- document artifact
- text block artifacts
- table artifacts for docx tables

## 8.4 Image Loader

### Responsibilities

- identify image dimensions and format
- optionally run OCR only when requested
- provide image preview metadata

### Output expectations

- image artifact
- optional OCR text artifact

### Important rules

- by default, ingestion should not assume OCR is always desired
- emit recommendation warnings where helpful

Note:

Image loading is not part of the first implementation milestone. It remains a later extension point.

---

## 9. Examples

## 9.1 PDF Example

### Source

`audited_financials_2024.pdf`

### Detection

- MIME: `application/pdf`
- pages: 126
- native text found on 122 pages
- 4 pages low/no text
- some pages may be flagged as possible tabular pages

### Stored records

**Source**

```json
{
  "source_id": "src_pdf_001",
  "filename": "audited_financials_2024.pdf",
  "detected_type": "pdf"
}
```

**Document artifact**

```json
{
  "artifact_id": "art_doc_pdf_001",
  "source_id": "src_pdf_001",
  "artifact_type": "document",
  "metadata": {
    "page_count": 126,
    "contains_extractable_text": true,
    "ocr_recommended_pages": [88, 89, 90, 91],
    "possible_tabular_pages": [42, 43, 44]
  }
}
```

**Page artifact**

```json
{
  "artifact_id": "art_page_pdf_042",
  "source_id": "src_pdf_001",
  "parent_artifact_id": "art_doc_pdf_001",
  "artifact_type": "page",
  "content_format": "text",
  "preview_text": "Revenue increased due to...",
  "provenance": {
    "page_number": 42,
    "extraction_method": "native_text"
  }
}
```

**Page warning/hint artifact data**

Base PDF ingestion does not emit trusted table artifacts by default.

Instead, page artifacts can carry hints like:

```json
{
  "artifact_id": "art_page_pdf_042",
  "source_id": "src_pdf_001",
  "artifact_type": "page",
  "metadata": {
    "possible_tabular_content": true
  },
  "extraction": {
    "warnings": ["possible_tabular_content"]
  }
}
```

### Downstream usage

- RAG can chunk page text artifacts
- later table-extraction workflows can target flagged pages
- financial analyzers should consume table artifacts only after a dedicated table extraction workflow has produced them
- later OCR node can be run only for flagged pages

## 9.2 Spreadsheet Example

### Source

`financial_model.xlsx`

### Detection

- workbook
- 5 sheets
- 3 sheets contain tabular financial statements

### Stored records

**Sheet artifact**

```json
{
  "artifact_id": "art_sheet_xlsx_is",
  "source_id": "src_xlsx_001",
  "artifact_type": "sheet",
  "title": "Income Statement",
  "metadata": {
    "sheet_name": "Income Statement",
    "row_count": 84,
    "column_count": 12,
    "detected_table_count": 1
  }
}
```

**Table artifact**

```json
{
  "artifact_id": "art_table_xlsx_is_01",
  "source_id": "src_xlsx_001",
  "parent_artifact_id": "art_sheet_xlsx_is",
  "artifact_type": "table",
  "title": "Income Statement Table",
  "content_format": "json",
  "provenance": {
    "sheet_name": "Income Statement",
    "cell_range": "A4:L28"
  }
}
```

### Downstream usage

- line-item analyzers can consume normalized rows
- table-to-text linking nodes can compare disclosures in PDFs
- later graph/RAG steps can index rows with cell provenance

## 9.3 Image Example

### Source

`bank_statement_scan_page1.jpg`

### Detection

- image
- no text available without OCR
- warning emitted

### Stored records

```json
{
  "artifact_id": "art_img_001",
  "source_id": "src_img_001",
  "artifact_type": "image",
  "metadata": {
    "width": 2480,
    "height": 3508,
    "ocr_available": false
  },
  "extraction": {
    "warnings": ["ocr_not_run", "text_not_available_without_ocr"]
  }
}
```

### Downstream usage

- UI can show image-only warning
- later OCR node can take this artifact explicitly as input
- downstream extractors should not assume text exists yet

Note:

This example remains useful for future design, but image ingestion is not part of the first delivery slice.

---

## 10. How Artifacts Feed RAG and Workflow Nodes

Artifacts should be reusable by multiple node types later.

### 10.1 RAG preparation

Future retrieval prep nodes may convert:

- document/page/text block artifacts -> text chunks
- table artifacts -> row-level or table-level chunks
- image OCR artifacts -> OCR chunks

Important distinction:

- spreadsheet table artifacts can feed RAG and analyzers directly after ingestion
- PDF-derived tables should only feed RAG or analyzers after a later extraction workflow has converted page-level PDF artifacts into trusted structured table artifacts

Suggested retrieval metadata:

- `source_id`
- `artifact_id`
- `page_number`
- `sheet_name`
- `table_id`
- `section_title`
- `document_type_guess`

### 10.2 Analyzer nodes

Analyzer nodes should accept explicit artifact inputs such as:

- `table_artifact_ids`
- `text_block_artifact_ids`
- `image_artifact_ids`

This is better than passing only raw text blobs.

### 10.3 Generator nodes

Generators like report or PPT nodes should consume:

- summarized text artifacts
- extracted tables
- analyzer outputs
- traceable citations back to source artifacts

---

## 11. UI Implications

The ingestion UI should expose:

1. uploaded sources list
2. detected source type
3. extraction warnings
4. extracted artifact counts
5. preview tabs:
   - metadata
   - text
   - tables
   - images

Later workflow UI should allow nodes to declare:

- which source artifacts they consume
- whether they consume raw source artifacts or previous node outputs
- what output schema they emit

This supports the future “functional flow-chart” style workflow builder.

---

## 12. Recommended Implementation Sequence

### D1

- define source schema
- define artifact schema
- define loader interface
- define repository interfaces

### D2

- implement loader registry
- implement source type router
- implement SQLite + filesystem repositories

### D3

- implement document loader
- implement spreadsheet loader
- implement PDF loader with thin deterministic page-level extraction only

### D4

- show sources and artifact previews in thin dashboard

### D5

- add retrieval prep nodes on top of artifacts
- add advanced PDF extraction workflows later:
  - OCR workflow
  - table candidate routing
  - LLM-assisted table reconstruction

---

## 13. Open Questions

These should be resolved before implementation starts:

1. Should artifact payloads live in filesystem only, or optionally in DB for small payloads?
2. Should OCR be a loader option, or always a separate explicit workflow node?
3. Do we want a single generic `document_loader` node in workflows, or type-specific loader nodes?
4. How much chunking belongs in ingestion versus later retrieval-prep nodes?
5. What heuristics should define `possible_tabular_content` for PDFs without over-promising structure?

---

## 14. Recommendation

For implementation, the most important thing is to build:

1. a **stable artifact schema**
2. a **loader registry and contract**
3. a **repository abstraction**

before building any workflow-specific logic.

If those three are correct, later RAG, analyzers, prompt references, and generators can all be layered on top cleanly.

from pathlib import Path

from openpyxl import Workbook
from pypdf import PdfWriter

from vertexforge.ingestion.registry import create_default_registry


FIXTURES = Path("tests/fixtures/ingestion")


def create_sample_xlsx(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Income Statement"
    sheet.append(["Year", "Revenue", "EBITDA"])
    sheet.append([2023, 120, 20])
    sheet.append([2024, 150, 24])
    workbook.save(path)


def create_blank_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as handle:
        writer.write(handle)


def test_document_loader_emits_document_and_text_artifacts() -> None:
    registry = create_default_registry()

    result = registry.load(FIXTURES / "sample.md")

    assert result.source.detected_type == "document"
    assert [artifact.artifact_type for artifact in result.artifacts] == ["document", "text_block"]
    assert result.artifacts[0].payload["contains_extractable_text"] is True
    assert "Customer concentration" in result.artifacts[1].payload["text"]


def test_spreadsheet_loader_emits_sheet_and_table_artifacts_for_csv() -> None:
    registry = create_default_registry()

    result = registry.load(FIXTURES / "sample.csv")

    artifact_types = [artifact.artifact_type for artifact in result.artifacts]
    assert artifact_types == ["document", "sheet", "table"]
    table_artifact = result.artifacts[-1]
    assert table_artifact.payload["headers"] == ["Year", "Revenue", "EBITDA"]
    assert table_artifact.payload["rows"][0] == ["2023", "120", "20"]
    assert "Revenue" in table_artifact.payload["markdown"]


def test_spreadsheet_loader_emits_multi_sheet_artifacts_for_xlsx(tmp_path: Path) -> None:
    registry = create_default_registry()
    workbook_path = tmp_path / "financials.xlsx"
    create_sample_xlsx(workbook_path)

    result = registry.load(workbook_path)

    artifact_types = [artifact.artifact_type for artifact in result.artifacts]
    assert artifact_types == ["document", "sheet", "table"]
    assert result.artifacts[1].payload["sheet_name"] == "Income Statement"
    assert result.artifacts[2].payload["rows"][1] == [2024, 150, 24]


def test_pdf_loader_emits_page_artifacts_with_ocr_warning_for_blank_pdf(tmp_path: Path) -> None:
    registry = create_default_registry()
    pdf_path = tmp_path / "blank.pdf"
    create_blank_pdf(pdf_path)

    result = registry.load(pdf_path)

    assert result.source.detected_type == "pdf"
    assert [artifact.artifact_type for artifact in result.artifacts] == ["document", "page"]
    assert result.artifacts[0].payload["contains_extractable_text"] is False
    assert result.artifacts[0].extraction["warnings"] == ["document_may_require_ocr"]
    assert result.artifacts[1].payload["possible_image_only"] is True


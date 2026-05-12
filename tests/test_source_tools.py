from pathlib import Path

from vertexforge.ingestion.registry import IngestionService, create_default_registry
from vertexforge.ingestion.repository import SqliteArtifactRepository
from vertexforge.tools import create_source_tools


FIXTURES = Path("tests/fixtures/ingestion")


def test_source_tools_only_expose_attached_sources_and_allowed_artifacts(tmp_path: Path) -> None:
    repository = SqliteArtifactRepository(
        db_path=tmp_path / "ingestion.db",
        artifact_root=tmp_path / "artifacts",
    )
    service = IngestionService(repository=repository, registry=create_default_registry())

    first = service.ingest_file(FIXTURES / "sample.md")
    second = service.ingest_file(FIXTURES / "sample.csv")

    tools = create_source_tools(
        repository=repository,
        allowed_source_ids=[first.source.source_id],
        allowed_artifact_types=["text_block"],
    )
    tool_map = {tool.name: tool for tool in tools}

    sources_text = tool_map["list_sources"].invoke({})
    assert "sample.md" in sources_text
    assert "sample.csv" not in sources_text

    first_artifacts = repository.list_artifacts(first.source.source_id)
    text_artifact = next(a for a in first_artifacts if a.artifact_type == "text_block")
    document_artifact = next(a for a in first_artifacts if a.artifact_type == "document")

    artifacts_text = tool_map["list_source_artifacts"].invoke({"source_id": first.source.source_id})
    assert "text_block" in artifacts_text
    assert "document (" not in artifacts_text

    read_text = tool_map["read_text_artifact"].invoke({"artifact_id": text_artifact.artifact_id})
    assert "Customer concentration" in read_text

    denied_text = tool_map["read_text_artifact"].invoke({"artifact_id": document_artifact.artifact_id})
    assert "not accessible" in denied_text

    other_source_text = tool_map["get_source_metadata"].invoke({"source_id": second.source.source_id})
    assert "not accessible" in other_source_text


def test_source_search_tool_reads_allowed_artifacts_only(tmp_path: Path) -> None:
    repository = SqliteArtifactRepository(
        db_path=tmp_path / "ingestion.db",
        artifact_root=tmp_path / "artifacts",
    )
    service = IngestionService(repository=repository, registry=create_default_registry())

    source = service.ingest_file(FIXTURES / "sample.md")
    tools = create_source_tools(
        repository=repository,
        allowed_source_ids=[source.source.source_id],
        allowed_artifact_types=["text_block"],
    )
    tool_map = {tool.name: tool for tool in tools}

    result = tool_map["search_artifacts"].invoke({"query": "margin pressure"})

    assert "sample.md" in result
    assert "margin pressure" in result.lower()


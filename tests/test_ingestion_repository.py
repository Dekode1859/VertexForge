from pathlib import Path

from vertexforge.ingestion.registry import IngestionService, create_default_registry
from vertexforge.ingestion.repository import SqliteArtifactRepository


FIXTURES = Path("tests/fixtures/ingestion")


def test_repository_persists_payloads_and_metadata(tmp_path: Path) -> None:
    repository = SqliteArtifactRepository(
        db_path=tmp_path / "ingestion.db",
        artifact_root=tmp_path / "artifacts",
    )
    service = IngestionService(repository=repository, registry=create_default_registry())

    result = service.ingest_file(FIXTURES / "sample.md")
    stored_artifacts = repository.list_artifacts(result.source.source_id)
    text_artifact = next(
        artifact for artifact in stored_artifacts if artifact.artifact_type == "text_block"
    )

    assert len(stored_artifacts) == 2
    assert all(artifact.content_uri for artifact in stored_artifacts)
    assert stored_artifacts[0].provenance["origin_loader"] == "document_loader"
    assert text_artifact.payload["text"].startswith("# Credit Memo Notes")


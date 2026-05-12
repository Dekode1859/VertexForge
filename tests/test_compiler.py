import json
from pathlib import Path

import vertexforge.compiler as compiler
from langchain_core.messages import AIMessage

from vertexforge.compiler import (
    GraphBuilder,
    _build_initial_state,
    _build_node_input,
    _create_llm,
    _extract_final_output,
    _resolve_tools,
)
from vertexforge.ingestion.registry import IngestionService, create_default_registry
from vertexforge.ingestion.repository import SqliteArtifactRepository
from vertexforge.prompts import StaticPromptProvider
from vertexforge.schema import GraphConfig


TEST_PROMPTS = StaticPromptProvider(
    {
        "vertexforge.brief_writer": "Write a brief.",
        "vertexforge.newsletter_writer": "Write a newsletter intro.",
        "vertexforge.executive_summarizer": "Write an executive summary.",
    }
)


def load_sample_config() -> GraphConfig:
    data = json.loads(Path("examples/state_rewrite_pipeline.json").read_text(encoding="utf-8"))
    return GraphConfig.model_validate(data)


def test_create_llm_maps_max_tokens_to_num_predict() -> None:
    llm = _create_llm("kimi-k2.5", temperature=0.2, max_tokens=321)

    assert llm.model == "kimi-k2.5"
    assert llm.temperature == 0.2
    assert llm.num_predict == 321


def test_graph_builder_uses_start_edge_when_entry_point_is_start() -> None:
    builder = GraphBuilder(load_sample_config(), prompt_provider=TEST_PROMPTS)

    assert builder.entry_node == "brief_writer"


def test_graph_builder_supports_direct_entry_point() -> None:
    config = load_sample_config()
    config = config.model_copy(
        update={
            "entry_point": "brief_writer",
            "edges": [edge for edge in config.edges if edge.from_node != "START"],
        }
    )

    builder = GraphBuilder(config, prompt_provider=TEST_PROMPTS)
    app = builder.build()

    assert builder.entry_node == "brief_writer"
    assert app is not None


def test_graph_builder_resolves_multiple_start_edges_for_parallel_graph() -> None:
    data = json.loads(Path("examples/aws_service_decision_pipeline.json").read_text(encoding="utf-8"))
    config = GraphConfig.model_validate(data)
    prompts = StaticPromptProvider(
        {
            "pros_advisor": "Pros prompt",
            "cons_advisor": "Cons prompt",
            "decision_critic": "Critic prompt",
        }
    )

    builder = GraphBuilder(config, prompt_provider=prompts)
    app = builder.build()

    assert builder.entry_nodes == ["pros_advisor", "cons_advisor"]
    assert builder.entry_node == "pros_advisor"
    assert app is not None


def test_graph_builder_supports_source_tools_when_repository_is_available(tmp_path: Path) -> None:
    repository = SqliteArtifactRepository(
        db_path=tmp_path / "ingestion.db",
        artifact_root=tmp_path / "artifacts",
    )
    service = IngestionService(repository=repository, registry=create_default_registry())
    source = service.ingest_file(Path("tests/fixtures/ingestion/sample.md"))

    config = load_sample_config()
    node = config.nodes[0].model_copy(
        update={
            "tools": ["list_sources", "list_source_artifacts", "read_text_artifact"],
            "attached_source_ids": [source.source.source_id],
            "allowed_artifact_types": ["text_block"],
        }
    )
    config = config.model_copy(update={"nodes": [node, *config.nodes[1:]]})

    builder = GraphBuilder(config, artifact_repository=repository, prompt_provider=TEST_PROMPTS)
    app = builder.build()

    assert app is not None


def test_source_attached_node_filters_generic_file_tools_by_default(tmp_path: Path) -> None:
    repository = SqliteArtifactRepository(
        db_path=tmp_path / "ingestion.db",
        artifact_root=tmp_path / "artifacts",
    )
    service = IngestionService(repository=repository, registry=create_default_registry())
    source = service.ingest_file(Path("tests/fixtures/ingestion/sample.md"))

    node = load_sample_config().nodes[0].model_copy(
        update={
            "tools": ["list_sources", "list_source_artifacts", "read_text_artifact", "list_directory", "read_file"],
            "attached_source_ids": [source.source.source_id],
            "allowed_artifact_types": ["text_block"],
            "restrict_to_attached_sources": True,
        }
    )

    resolved = _resolve_tools(node, repository)
    tool_names = [tool.name for tool in resolved]

    assert "list_sources" in tool_names
    assert "read_text_artifact" in tool_names
    assert "list_directory" not in tool_names
    assert "read_file" not in tool_names


def test_source_attached_node_can_opt_back_into_file_tools(tmp_path: Path) -> None:
    repository = SqliteArtifactRepository(
        db_path=tmp_path / "ingestion.db",
        artifact_root=tmp_path / "artifacts",
    )
    service = IngestionService(repository=repository, registry=create_default_registry())
    source = service.ingest_file(Path("tests/fixtures/ingestion/sample.md"))

    node = load_sample_config().nodes[0].model_copy(
        update={
            "tools": ["list_sources", "read_text_artifact", "list_directory"],
            "attached_source_ids": [source.source.source_id],
            "allowed_artifact_types": ["text_block"],
            "restrict_to_attached_sources": False,
        }
    )

    resolved = _resolve_tools(node, repository)
    tool_names = [tool.name for tool in resolved]

    assert "list_sources" in tool_names
    assert "list_directory" in tool_names


def test_build_initial_state_writes_user_input_to_configured_input_key() -> None:
    data = json.loads(Path("examples/state_rewrite_pipeline.json").read_text(encoding="utf-8"))
    data["input_key"] = "raw_input"
    data["state"]["fields"].append({"name": "raw_input", "type": "str", "default": ""})
    config = GraphConfig.model_validate(data)

    state = _build_initial_state(config, "Rewrite this as a newsletter")

    assert state["raw_input"] == "Rewrite this as a newsletter"
    assert "messages" not in state


def test_build_initial_state_accepts_structured_graph_inputs() -> None:
    data = json.loads(Path("examples/aws_service_decision_pipeline.json").read_text(encoding="utf-8"))
    config = GraphConfig.model_validate(data)

    state = _build_initial_state(
        config,
        {
            "pros_text": "AWS Lambda scales automatically.",
            "cons_text": "Cold starts can affect latency-sensitive workloads.",
        },
    )

    assert state["pros_text"] == "AWS Lambda scales automatically."
    assert state["cons_text"] == "Cold starts can affect latency-sensitive workloads."
    assert "messages" not in state


def test_build_node_input_reads_declared_state_keys() -> None:
    node = load_sample_config().nodes[0].model_copy(
        update={"input_keys": ["outline", "facts"]}
    )
    state = {
        "outline": "Opening paragraph",
        "facts": {"topic": "AI", "audience": "analysts"},
    }

    node_input = _build_node_input(node, state)

    assert "outline" in node_input
    assert "Opening paragraph" in node_input
    assert '"audience": "analysts"' in node_input


def test_plain_node_writes_output_key_to_state(monkeypatch) -> None:
    class FakeLLM:
        def invoke(self, _messages):
            return AIMessage(content="Newsletter version")

    monkeypatch.setattr(compiler, "_create_llm", lambda *args, **kwargs: FakeLLM())

    node = load_sample_config().nodes[0].model_copy(
        update={"input_keys": ["raw_input"], "output_key": "newsletter"}
    )
    node_fn = compiler.create_node_function(node, prompt_provider=TEST_PROMPTS)

    update = node_fn({"raw_input": "Make this polished", "iteration_count": 0})

    assert update["newsletter"] == "Newsletter version"
    assert "messages" not in update


def test_extract_final_output_prefers_configured_state_key() -> None:
    data = json.loads(Path("examples/state_rewrite_pipeline.json").read_text(encoding="utf-8"))
    data["final_output_key"] = "newsletter"
    data["state"]["fields"].append({"name": "newsletter", "type": "str", "default": ""})
    config = GraphConfig.model_validate(data)

    assert _extract_final_output(config, {"newsletter": "Final newsletter"}) == "Final newsletter"


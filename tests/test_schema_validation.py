import json
from pathlib import Path

import pytest

from vertexforge.schema import GraphConfig


def load_sample_config() -> dict:
    return json.loads(Path("examples/state_rewrite_pipeline.json").read_text(encoding="utf-8"))


def test_schema_accepts_current_sample_config() -> None:
    config = GraphConfig.model_validate(load_sample_config())

    assert config.graph_name == "state_rewrite_pipeline"
    assert [node.node_id for node in config.nodes] == [
        "brief_writer",
        "newsletter_writer",
        "executive_summarizer",
    ]
    assert config.nodes[0].prompt_ref.identifier == "vertexforge.brief_writer"


def test_schema_rejects_inline_prompt_without_prompt_ref() -> None:
    data = load_sample_config()
    node = data["nodes"][0]
    node.pop("prompt_ref")
    node["system_prompt"] = "This prompt should not be accepted by the DSL."

    with pytest.raises(ValueError, match="prompt_ref"):
        GraphConfig.model_validate(data)


def test_schema_rejects_conditional_edges() -> None:
    data = load_sample_config()
    data["edges"][1]["condition"] = "needs_review"

    with pytest.raises(ValueError, match="Conditional edges are not supported yet"):
        GraphConfig.model_validate(data)


def test_schema_rejects_conflicting_entry_point() -> None:
    data = load_sample_config()
    data["entry_point"] = "newsletter_writer"

    with pytest.raises(ValueError, match="conflicts with START edge"):
        GraphConfig.model_validate(data)


def test_schema_accepts_direct_entry_point_without_start_edge() -> None:
    data = load_sample_config()
    data["entry_point"] = "brief_writer"
    data["edges"] = [edge for edge in data["edges"] if edge["from"] != "START"]

    config = GraphConfig.model_validate(data)

    assert config.entry_point == "brief_writer"


def test_schema_accepts_static_parallel_join_edges() -> None:
    data = json.loads(Path("examples/aws_service_decision_pipeline.json").read_text(encoding="utf-8"))

    config = GraphConfig.model_validate(data)

    start_targets = [edge.to_node for edge in config.edges if edge.from_node == "START"]
    join_edges = [edge for edge in config.edges if isinstance(edge.from_node, list)]
    assert start_targets == ["pros_advisor", "cons_advisor"]
    assert join_edges[0].from_node == ["pros_advisor", "cons_advisor"]
    assert join_edges[0].to_node == "decision_critic"


def test_schema_accepts_node_source_attachments() -> None:
    data = load_sample_config()
    data["nodes"][0]["attached_source_ids"] = ["src_alpha", "src_beta"]
    data["nodes"][0]["allowed_artifact_types"] = ["text_block", "table"]

    config = GraphConfig.model_validate(data)

    assert config.nodes[0].attached_source_ids == ["src_alpha", "src_beta"]
    assert config.nodes[0].allowed_artifact_types == ["text_block", "table"]
    assert config.nodes[0].restrict_to_attached_sources is True


def test_schema_accepts_state_backed_node_io() -> None:
    data = load_sample_config()
    data["input_key"] = "raw_input"
    data["final_output_key"] = "newsletter"
    data["state"]["fields"].extend(
        [
            {"name": "raw_input", "type": "str", "default": ""},
            {"name": "outline", "type": "str", "default": ""},
            {"name": "newsletter", "type": "str", "default": ""},
        ]
    )
    data["nodes"][0]["input_keys"] = ["raw_input"]
    data["nodes"][0]["output_key"] = "outline"
    data["nodes"][1]["input_keys"] = ["outline"]
    data["nodes"][1]["output_key"] = "newsletter"

    config = GraphConfig.model_validate(data)

    assert config.input_key == "raw_input"
    assert config.final_output_key == "newsletter"
    assert config.nodes[0].input_keys == ["raw_input"]
    assert config.nodes[0].output_key == "outline"


def test_schema_rejects_state_io_references_to_missing_fields() -> None:
    data = load_sample_config()
    data["nodes"][0]["input_keys"] = ["missing_input"]

    with pytest.raises(ValueError, match="input_keys reference undefined state fields"):
        GraphConfig.model_validate(data)


def test_schema_rejects_node_without_state_inputs() -> None:
    data = load_sample_config()
    data["nodes"][0].pop("input_keys")

    with pytest.raises(ValueError, match="input_keys"):
        GraphConfig.model_validate(data)


def test_schema_rejects_node_without_state_output() -> None:
    data = load_sample_config()
    data["nodes"][0].pop("output_key")

    with pytest.raises(ValueError, match="output_key"):
        GraphConfig.model_validate(data)


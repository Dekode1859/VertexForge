import json
from pathlib import Path

import pytest

from schema import GraphConfig


def load_sample_config() -> dict:
    return json.loads(Path("config.json").read_text(encoding="utf-8"))


def test_schema_accepts_current_sample_config() -> None:
    config = GraphConfig.model_validate(load_sample_config())

    assert config.graph_name == "research_pipeline"
    assert [node.node_id for node in config.nodes] == ["extractor", "researcher", "summarizer"]


def test_schema_rejects_conditional_edges() -> None:
    data = load_sample_config()
    data["edges"][1]["condition"] = "needs_review"

    with pytest.raises(ValueError, match="Conditional edges are not supported yet"):
        GraphConfig.model_validate(data)


def test_schema_rejects_conflicting_entry_point() -> None:
    data = load_sample_config()
    data["entry_point"] = "researcher"

    with pytest.raises(ValueError, match="conflicts with START edge"):
        GraphConfig.model_validate(data)


def test_schema_accepts_direct_entry_point_without_start_edge() -> None:
    data = load_sample_config()
    data["entry_point"] = "extractor"
    data["edges"] = [edge for edge in data["edges"] if edge["from"] != "START"]

    config = GraphConfig.model_validate(data)

    assert config.entry_point == "extractor"

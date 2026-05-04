import json
from pathlib import Path

from compiler import GraphBuilder, _create_llm
from schema import GraphConfig


def load_sample_config() -> GraphConfig:
    data = json.loads(Path("config.json").read_text(encoding="utf-8"))
    return GraphConfig.model_validate(data)


def test_create_llm_maps_max_tokens_to_num_predict() -> None:
    llm = _create_llm("kimi-k2.5", temperature=0.2, max_tokens=321)

    assert llm.model == "kimi-k2.5"
    assert llm.temperature == 0.2
    assert llm.num_predict == 321


def test_graph_builder_uses_start_edge_when_entry_point_is_start() -> None:
    builder = GraphBuilder(load_sample_config())

    assert builder.entry_node == "extractor"


def test_graph_builder_supports_direct_entry_point() -> None:
    config = load_sample_config()
    config = config.model_copy(
        update={
            "entry_point": "extractor",
            "edges": [edge for edge in config.edges if edge.from_node != "START"],
        }
    )

    builder = GraphBuilder(config)
    app = builder.build()

    assert builder.entry_node == "extractor"
    assert app is not None

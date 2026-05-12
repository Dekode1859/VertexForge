"""UI-free execution helpers for VertexForge JSON workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field

from vertexforge.compiler import GraphBuilder, _build_initial_state, _extract_final_output
from vertexforge.ingestion.repository import ArtifactRepository
from vertexforge.prompts import PromptProvider
from vertexforge.schema import GraphConfig, load_config


class ExecutionResult(BaseModel):
    """Result returned after executing a compiled workflow."""

    final_output: str
    final_state: dict[str, Any] = Field(default_factory=dict)
    graph_name: str
    nodes_executed: int = 0
    final_output_key: str | None = None


def execute_config(
    config: GraphConfig,
    user_input: str | Mapping[str, Any],
    artifact_repository: ArtifactRepository | None = None,
    prompt_provider: PromptProvider | None = None,
) -> ExecutionResult:
    """Compile and execute a validated workflow config."""
    builder = GraphBuilder(
        config,
        artifact_repository=artifact_repository,
        prompt_provider=prompt_provider,
    )
    graph = builder.build()
    initial_state = _build_initial_state(config, user_input)
    final_state = graph.invoke(initial_state)
    final_output = _extract_final_output(config, final_state)

    return ExecutionResult(
        final_output=final_output,
        final_state=dict(final_state),
        graph_name=config.graph_name,
        nodes_executed=int(final_state.get("iteration_count", 0)),
        final_output_key=config.final_output_key,
    )


def execute_file(
    config_path: str | Path,
    user_input: str | Mapping[str, Any],
    artifact_repository: ArtifactRepository | None = None,
    prompt_provider: PromptProvider | None = None,
) -> ExecutionResult:
    """Load, validate, compile, and execute a workflow JSON file."""
    config = load_config(str(config_path))
    return execute_config(
        config,
        user_input,
        artifact_repository=artifact_repository,
        prompt_provider=prompt_provider,
    )


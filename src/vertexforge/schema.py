"""
Schema Definition: Pydantic models for LangGraph JSON configuration.
This defines the structure that compiler.py will consume.
"""

from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vertexforge.prompts import PromptRef


# ============================================================================
# NODE CONFIGURATION
# ============================================================================

class NodeConfig(BaseModel):
    """Configuration for a single agent node in the graph."""
    
    node_id: str = Field(
        ...,
        description="Unique identifier for this node (e.g., 'extractor', 'researcher')"
    )
    
    model: str = Field(
        ...,
        description="LLM model identifier (e.g., 'llama3.2', 'claude-3-opus')"
    )
    
    prompt_ref: PromptRef = Field(
        ...,
        description="Reference to the Phoenix prompt used as this node's system prompt"
    )
    
    temperature: float = Field(
        default=0.7,
        description="Temperature for LLM sampling (0.0 = deterministic, 1.0 = creative)",
        ge=0.0,
        le=2.0
    )
    
    tools: List[str] = Field(
        default=[],
        description="List of tool names available to this agent"
    )
    
    max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum tokens to generate (None = model default)"
    )

    input_keys: List[str] = Field(
        ...,
        description="State fields this node should read as its input."
    )

    output_key: str = Field(
        ...,
        description="State field this node should write its final output into"
    )

    attached_source_ids: List[str] = Field(
        default=[],
        description="Uploaded source IDs that this node is allowed to access via source tools"
    )

    allowed_artifact_types: List[Literal["document", "page", "text_block", "sheet", "table"]] = Field(
        default=[],
        description="Artifact types that this node is allowed to read from attached sources"
    )

    restrict_to_attached_sources: bool = Field(
        default=True,
        description=(
            "When true, generic filesystem tools are filtered out for nodes that use attached "
            "sources, so the agent stays on the source-tool path by default"
        )
    )

    @model_validator(mode="after")
    def validate_node(self) -> "NodeConfig":
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens must be greater than 0 when provided")
        if not self.input_keys:
            raise ValueError("LLM nodes require at least one input_key.")
        return self


# ============================================================================
# EDGE CONFIGURATION
# ============================================================================

class EdgeConfig(BaseModel):
    """Configuration for an edge between nodes."""
    
    from_node: Union[str, List[str]] = Field(
        ...,
        description="Source node ID, 'START' for entry point, or list of source node IDs for joins",
        alias="from"
    )
    
    to_node: str = Field(
        ...,
        description="Target node ID, or 'END' for terminal",
        alias="to"
    )
    
    condition: Optional[str] = Field(
        default=None,
        description="Optional condition expression for conditional routing"
    )
    
    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_edge(self) -> "EdgeConfig":
        if isinstance(self.from_node, list):
            if not self.from_node:
                raise ValueError("Multi-source edges require at least one source node.")
            if "START" in self.from_node or "END" in self.from_node:
                raise ValueError("Multi-source edges can only reference regular node IDs.")
        return self


# ============================================================================
# STATE CONFIGURATION
# ============================================================================

class StateField(BaseModel):
    """Definition of a field in the graph state."""
    
    name: str = Field(..., description="Field name")
    type: str = Field(..., description="Python type annotation (e.g., 'str', 'List[str]')")
    reducer: Optional[str] = Field(
        default=None,
        description="Reducer function (e.g., 'operator.add' for message accumulation)"
    )
    default: Any = Field(
        default=None,
        description="Default value for this field"
    )


class StateConfig(BaseModel):
    """Configuration for the graph state structure."""
    
    fields: List[StateField] = Field(
        default=[
            StateField(name="iteration_count", type="int", reducer="operator.add", default=0)
        ],
        description="Fields that make up the graph state"
    )


# ============================================================================
# MAIN GRAPH CONFIGURATION
# ============================================================================

class GraphConfig(BaseModel):
    """Complete configuration for a LangGraph multi-agent system."""
    
    graph_name: str = Field(
        ...,
        description="Human-readable name for this graph"
    )
    
    version: str = Field(
        default="1.0.0",
        description="Schema version for compatibility"
    )
    
    description: Optional[str] = Field(
        default=None,
        description="What this graph does"
    )
    
    state: StateConfig = Field(
        default_factory=StateConfig,
        description="State structure configuration"
    )
    
    nodes: List[NodeConfig] = Field(
        ...,
        description="Agent nodes in this graph",
        min_length=1
    )
    
    edges: List[EdgeConfig] = Field(
        ...,
        description="Edges connecting nodes",
        min_length=1
    )
    
    entry_point: str = Field(
        default="START",
        description="Node ID where execution begins"
    )

    input_key: Optional[str] = Field(
        default=None,
        description="State field where the graph's initial user input should be stored"
    )

    input_keys: List[str] = Field(
        default=[],
        description="State fields expected when the graph is started with structured inputs"
    )

    final_output_key: Optional[str] = Field(
        default=None,
        description="State field to use as the graph's final user-visible output"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "graph_name": "state_rewrite_pipeline",
                "version": "1.0.0",
                "description": "Rewrite an input through explicit state handoff",
                "input_key": "source_text",
                "final_output_key": "summary",
                "state": {
                    "fields": [
                        {"name": "iteration_count", "type": "int", "reducer": "operator.add", "default": 0},
                        {"name": "source_text", "type": "str", "default": ""},
                        {"name": "summary", "type": "str", "default": ""}
                    ]
                },
                "nodes": [
                    {
                        "node_id": "summarizer",
                        "model": "llama3.2",
                        "prompt_ref": {"identifier": "vertexforge.brief_writer", "tag": "development"},
                        "temperature": 0.0,
                        "tools": [],
                        "input_keys": ["source_text"],
                        "output_key": "summary"
                    }
                ],
                "edges": [
                    {"from": "START", "to": "summarizer"},
                    {"from": "summarizer", "to": "END"}
                ]
            }
        }
    )

    @model_validator(mode="after")
    def validate_graph(self) -> "GraphConfig":
        node_ids = [node.node_id for node in self.nodes]
        unique_node_ids = set(node_ids)
        state_field_names = {field.name for field in self.state.fields}

        if len(unique_node_ids) != len(node_ids):
            duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
            raise ValueError(f"Duplicate node IDs are not allowed: {duplicates}")

        for edge in self.edges:
            if edge.condition is not None:
                raise ValueError(
                    "Conditional edges are not supported yet. "
                    f"Remove condition from edge {edge.from_node} -> {edge.to_node}."
                )
            from_nodes = edge.from_node if isinstance(edge.from_node, list) else [edge.from_node]

            if edge.to_node == "START":
                raise ValueError("Edges cannot target START.")
            if "END" in from_nodes:
                raise ValueError("Edges cannot originate from END.")

        start_targets = [edge.to_node for edge in self.edges if edge.from_node == "START"]

        if self.entry_point == "START":
            if len(start_targets) < 1:
                raise ValueError(
                    "entry_point is START, so at least one START edge is required."
                )
            actual_entries = start_targets
        else:
            if self.entry_point not in unique_node_ids:
                raise ValueError(
                    f"entry_point '{self.entry_point}' is not a valid node ID. "
                    f"Available nodes: {sorted(unique_node_ids)}"
                )
            if start_targets and start_targets != [self.entry_point]:
                raise ValueError(
                    f"entry_point '{self.entry_point}' conflicts with START edges to '{start_targets}'."
                )
            actual_entries = [self.entry_point]

        referenced_nodes = set()
        for edge in self.edges:
            from_nodes = edge.from_node if isinstance(edge.from_node, list) else [edge.from_node]
            for from_node in from_nodes:
                if from_node not in {"START", "END"}:
                    referenced_nodes.add(from_node)
            if edge.to_node not in {"START", "END"}:
                referenced_nodes.add(edge.to_node)

        missing_nodes = sorted(referenced_nodes - unique_node_ids)
        if missing_nodes:
            raise ValueError(f"Edges reference undefined node IDs: {missing_nodes}")

        edge_map: Dict[str, List[str]] = {node_id: [] for node_id in unique_node_ids}
        for edge in self.edges:
            from_nodes = edge.from_node if isinstance(edge.from_node, list) else [edge.from_node]
            if edge.to_node not in {"START", "END"}:
                for from_node in from_nodes:
                    if from_node not in {"START", "END"}:
                        edge_map[from_node].append(edge.to_node)

        reachable = set()
        frontier = list(actual_entries)
        while frontier:
            current = frontier.pop()
            if current in reachable:
                continue
            reachable.add(current)
            frontier.extend(edge_map.get(current, []))

        orphaned_nodes = sorted(unique_node_ids - reachable)
        if orphaned_nodes:
            raise ValueError(
                f"Nodes unreachable from the configured entry point '{actual_entry}': {orphaned_nodes}"
            )

        if self.input_key is not None and self.input_key not in state_field_names:
            raise ValueError(f"input_key '{self.input_key}' is not defined in state fields.")

        missing_graph_input_keys = sorted(set(self.input_keys) - state_field_names)
        if missing_graph_input_keys:
            raise ValueError(
                f"input_keys reference undefined state fields: {missing_graph_input_keys}"
            )

        if self.final_output_key is not None and self.final_output_key not in state_field_names:
            raise ValueError(
                f"final_output_key '{self.final_output_key}' is not defined in state fields."
            )

        for node in self.nodes:
            missing_input_keys = sorted(set(node.input_keys) - state_field_names)
            if missing_input_keys:
                raise ValueError(
                    f"Node '{node.node_id}' input_keys reference undefined state fields: "
                    f"{missing_input_keys}"
                )
            if node.output_key not in state_field_names:
                raise ValueError(
                    f"Node '{node.node_id}' output_key '{node.output_key}' is not defined in state fields."
                )

        return self


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_config(json_data: Dict[str, Any]) -> GraphConfig:
    """Validate raw JSON against the schema."""
    return GraphConfig.model_validate(json_data)


def load_config(path: str) -> GraphConfig:
    """Load and validate a config from JSON file."""
    import json
    with open(path, 'r') as f:
        data = json.load(f)
    return validate_config(data)


def save_config(config: GraphConfig, path: str) -> None:
    """Save config to JSON file with nice formatting."""
    import json
    with open(path, 'w') as f:
        json.dump(config.model_dump(by_alias=True), f, indent=2)


if __name__ == "__main__":
    # Print the schema as JSON
    import json
    print(json.dumps(GraphConfig.model_json_schema(), indent=2))


"""
Schema Definition: Pydantic models for LangGraph JSON configuration.
This defines the structure that compiler.py will consume.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


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
    
    system_prompt: str = Field(
        ...,
        description="The system prompt that defines this agent's behavior"
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


# ============================================================================
# EDGE CONFIGURATION
# ============================================================================

class EdgeConfig(BaseModel):
    """Configuration for an edge between nodes."""
    
    from_node: str = Field(
        ...,
        description="Source node ID, or 'START' for entry point",
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
    
    class Config:
        populate_by_name = True


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
            StateField(name="messages", type="List[BaseMessage]", reducer="operator.add"),
            StateField(name="current_node", type="str", default=""),
            StateField(name="iteration_count", type="int", default=0)
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "graph_name": "research_pipeline",
                "version": "1.0.0",
                "description": "Extract entities, research them, summarize findings",
                "nodes": [
                    {
                        "node_id": "extractor",
                        "model": "llama3.2",
                        "system_prompt": "Extract key entities from the input...",
                        "temperature": 0.0,
                        "tools": []
                    },
                    {
                        "node_id": "researcher",
                        "model": "llama3.2",
                        "system_prompt": "Analyze the extracted entities...",
                        "temperature": 0.7,
                        "tools": []
                    }
                ],
                "edges": [
                    {"from": "START", "to": "extractor"},
                    {"from": "extractor", "to": "researcher"},
                    {"from": "researcher", "to": "END"}
                ]
            }
        }


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

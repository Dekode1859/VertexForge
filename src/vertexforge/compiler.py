"""
Compiler: GraphBuilder that ingests JSON schema and constructs LangGraph StateGraph.

This is the "compiler" that proves bidirectional translation:
  JSON config  â†’  Working LangGraph multi-agent system

Uses create_react_agent for tool-equipped nodes, plain LLM for others.
"""

import operator
import os
import sys
import json
from typing import TypedDict, Annotated, Dict, Any, Callable, List, Mapping, Optional, Union
from types import new_class

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent

from vertexforge.schema import GraphConfig, NodeConfig, load_config
from vertexforge.ingestion.repository import ArtifactRepository
from vertexforge.prompts import PhoenixPromptProvider, PromptProvider
from vertexforge.tools import (
    RESEARCH_TOOLS, MATH_TOOLS, FILE_TOOLS, TEXT_TOOLS,
    ALL_TOOLS, web_search, get_current_date, calculate,
    calculate_statistics, read_file, list_directory, write_file,
    count_words, extract_urls, create_source_tools, SOURCE_TOOL_NAMES,
)

# Load environment variables
load_dotenv()

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "kimi-k2.5")


# ============================================================================
# TOOL REGISTRY
# ============================================================================

# Maps tool name strings from config to actual @tool-decorated callables.
TOOL_REGISTRY: Dict[str, Callable] = {
    "web_search": web_search,
    "get_current_date": get_current_date,
    "calculate": calculate,
    "calculate_statistics": calculate_statistics,
    "read_file": read_file,
    "list_directory": list_directory,
    "write_file": write_file,
    "count_words": count_words,
    "extract_urls": extract_urls,
}

# Convenience group mappings for config shorthand
TOOL_GROUP_REGISTRY: Dict[str, List[Callable]] = {
    "RESEARCH_TOOLS": RESEARCH_TOOLS,
    "MATH_TOOLS": MATH_TOOLS,
    "FILE_TOOLS": FILE_TOOLS,
    "TEXT_TOOLS": TEXT_TOOLS,
    "ALL_TOOLS": ALL_TOOLS,
}

FILE_TOOL_NAMES = {"read_file", "list_directory", "write_file"}


def _message_content(message: Any) -> str:
    """Return the text content for a LangChain message or arbitrary value."""
    return message.content if hasattr(message, "content") else str(message)


def _serialize_state_value(value: Any) -> str:
    """Serialize a state value for inclusion in a node prompt."""
    if isinstance(value, BaseMessage):
        return _message_content(value)
    if isinstance(value, list) and value and all(hasattr(item, "content") for item in value):
        return "\n".join(_message_content(item) for item in value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    return "" if value is None else str(value)


def _state_default(field_type: str, configured_default: Any) -> Any:
    """Return a fresh default value for a configured state field."""
    if configured_default is not None:
        if isinstance(configured_default, (dict, list)):
            return configured_default.copy()
        return configured_default
    if field_type == "int":
        return 0
    if field_type == "float":
        return 0.0
    if field_type == "bool":
        return False
    if field_type == "str":
        return ""
    if "List" in field_type:
        return []
    if "Dict" in field_type:
        return {}
    return None


def _build_initial_state(config: GraphConfig, user_input: str | Mapping[str, Any]) -> Dict[str, Any]:
    """Create the initial graph state from configured defaults and user input."""
    state = {}
    state_field_names = set()
    for field in config.state.fields:
        state_field_names.add(field.name)
        default_value = _state_default(field.type, field.default)
        if default_value is not None:
            state[field.name] = default_value

    if isinstance(user_input, Mapping):
        unknown_keys = sorted(set(user_input) - state_field_names)
        if unknown_keys:
            raise ValueError(f"Initial inputs reference undefined state fields: {unknown_keys}")
        expected_keys = config.input_keys or list(user_input.keys())
        missing_keys = sorted(set(expected_keys) - set(user_input))
        if missing_keys:
            raise ValueError(f"Missing required initial input fields: {missing_keys}")
        state.update(dict(user_input))
    else:
        if not config.input_key:
            raise ValueError("Text input requires graph input_key to be configured.")
        state[config.input_key] = user_input

    state["iteration_count"] = 0
    return state


def _build_node_input(node_config: NodeConfig, state: Dict[str, Any]) -> str:
    """Build the user-facing input for a node from declared state keys."""
    if len(node_config.input_keys) == 1:
        return _serialize_state_value(state.get(node_config.input_keys[0]))

    sections = []
    for key in node_config.input_keys:
        sections.append(f"[{key}]\n{_serialize_state_value(state.get(key))}")
    return "\n\n".join(sections)


def _build_node_update(
    node_config: NodeConfig,
    state: Dict[str, Any],
    final_message: BaseMessage,
) -> Dict[str, Any]:
    """Build the LangGraph state update emitted by a node."""
    update = {
        "iteration_count": 1,
        node_config.output_key: _message_content(final_message),
    }
    return update


def _extract_final_output(config: GraphConfig, state: Dict[str, Any]) -> str:
    """Extract final user-visible output from graph state."""
    if not config.final_output_key:
        raise ValueError("Graph config must define final_output_key.")
    return _serialize_state_value(state.get(config.final_output_key))


# ============================================================================
# DYNAMIC STATE CREATION
# ============================================================================

def create_state_class(config: GraphConfig) -> type:
    """Dynamically create a TypedDict class from config state definition.

    Maps string type names to Python types and wraps fields with reducers
    in Annotated[type, reducer_fn] for LangGraph state accumulation.

    Args:
        config: A validated GraphConfig with state field definitions.

    Returns:
        A TypedDict subclass suitable for StateGraph(state_class).
    """

    # Build annotations dict
    annotations = {}
    defaults = {}

    # Map string type names to actual types
    type_map = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "List": list,
        "List[str]": List[str],
        "Dict": dict,
        "Dict[str, Any]": Dict[str, Any],
        "Any": Any,
    }

    for field in config.state.fields:
        # Resolve the type
        field_type = type_map.get(field.type, Any)

        # If there's a reducer, wrap in Annotated
        if field.reducer:
            if field.reducer == "operator.add":
                annotations[field.name] = Annotated[field_type, operator.add]
            else:
                # Future: support custom reducer names via registry
                annotations[field.name] = field_type
        else:
            annotations[field.name] = field_type

        # Store default value
        if field.default is not None:
            defaults[field.name] = field.default
        elif field.type == "int":
            defaults[field.name] = 0
        elif field.type == "str":
            defaults[field.name] = ""
        elif "List" in field.type:
            defaults[field.name] = []

    # Create the TypedDict
    GraphState = new_class(
        "GraphState",
        (TypedDict,),
        exec_body=lambda ns: ns.update({
            "__annotations__": annotations,
            "__module__": __name__,
        })
    )

    return GraphState


# ============================================================================
# NODE FACTORY
# ============================================================================

def _resolve_tools(
    node_config: NodeConfig,
    repository: Optional[ArtifactRepository] = None,
) -> List[Callable]:
    """Resolve tool name strings from config to actual tool callables.

    Supports both individual tool names and group names (e.g., "RESEARCH_TOOLS").

    Args:
        node_config: Node configuration specifying declared tools and source access.
        repository: Optional artifact repository required for source-aware tools.

    Returns:
        List of @tool-decorated callables.

    Raises:
        ValueError: If a tool name cannot be resolved.
    """
    source_tools_requested = any(name in SOURCE_TOOL_NAMES for name in node_config.tools)
    restrict_file_tools = (
        source_tools_requested
        and bool(node_config.attached_source_ids)
        and node_config.restrict_to_attached_sources
    )

    resolved = []
    for name in node_config.tools:
        if restrict_file_tools and name in FILE_TOOL_NAMES:
            continue
        # Check individual tool registry first
        if name in TOOL_REGISTRY:
            resolved.append(TOOL_REGISTRY[name])
        elif name in SOURCE_TOOL_NAMES:
            if repository is None:
                raise ValueError(
                    f"Tool '{name}' requires an artifact repository, but none was provided."
                )
            resolved.extend(
                create_source_tools(
                    repository=repository,
                    allowed_source_ids=node_config.attached_source_ids,
                    allowed_artifact_types=node_config.allowed_artifact_types,
                )
            )
        # Check group registry
        elif name in TOOL_GROUP_REGISTRY:
            resolved.extend(TOOL_GROUP_REGISTRY[name])
        else:
            raise ValueError(
                f"Unknown tool '{name}'. Available: "
                f"{sorted(list(TOOL_REGISTRY.keys()) + SOURCE_TOOL_NAMES)}, "
                f"Groups: {sorted(TOOL_GROUP_REGISTRY.keys())}"
            )
    # Deduplicate while preserving order (use tool name as hash key)
    seen = set()
    unique = []
    for t in resolved:
        tool_name = getattr(t, '__name__', str(t))
        if tool_name not in seen:
            seen.add(tool_name)
            unique.append(t)
    return unique


def _create_llm(
    model: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> ChatOllama:
    """Create an Ollama LLM client with Cloud auth headers.

    Args:
        model: Ollama model identifier (e.g., 'kimi-k2.5', 'llama3.2').
        temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).

    Returns:
        Configured ChatOllama instance.
    """
    kwargs = {
        "model": model,
        "temperature": temperature,
    }

    if max_tokens is not None:
        kwargs["num_predict"] = max_tokens

    # Add cloud auth if API key is configured
    if OLLAMA_API_KEY:
        kwargs["base_url"] = OLLAMA_BASE_URL
        kwargs["client_kwargs"] = {
            "headers": {"Authorization": f"Bearer {OLLAMA_API_KEY}"}
        }

    return ChatOllama(**kwargs)


def _resolve_system_prompt(
    node_config: NodeConfig,
    prompt_provider: Optional[PromptProvider] = None,
) -> str:
    """Resolve a node's system prompt from Phoenix Prompt Hub."""
    provider = prompt_provider or PhoenixPromptProvider()
    return provider.get_system_prompt(node_config.prompt_ref)


def create_node_function(
    node_config: NodeConfig,
    repository: Optional[ArtifactRepository] = None,
    prompt_provider: Optional[PromptProvider] = None,
) -> Callable:
    """Factory that creates a node callable from configuration.

    Two modes:
    1. **Tool-equipped**: If node_config.tools is non-empty, uses
       `create_react_agent` to build a ReAct agent with tool access.
    2. **Plain LLM**: If no tools, creates a simple wrapper that invokes
       the LLM with system + user messages.

    Args:
        node_config: A validated NodeConfig specifying the agent's behavior.

    Returns:
        A callable suitable for StateGraph.add_node().
    """

    system_prompt = _resolve_system_prompt(node_config, prompt_provider)

    # --- Tool-equipped agent via create_react_agent ---
    if node_config.tools:
        resolved_tools = _resolve_tools(node_config, repository)
        llm = _create_llm(
            node_config.model,
            node_config.temperature,
            node_config.max_tokens,
        )

        agent = create_react_agent(
            model=llm,
            tools=resolved_tools,
            name=node_config.node_id,
            prompt=system_prompt,
        )

        def react_node_function(state: Dict[str, Any]) -> Dict[str, Any]:
            """ReAct agent node â€” delegates to create_react_agent."""
            print(f"\n[{node_config.node_id.upper()}] Processing (ReAct agent with {len(resolved_tools)} tools)...")

            user_content = _build_node_input(node_config, state)
            result = agent.invoke({"messages": [HumanMessage(content=user_content)]})
            final_message = result["messages"][-1]

            print(f"[{node_config.node_id.upper()}] Done (ReAct)")

            return _build_node_update(node_config, state, final_message)

        react_node_function.__name__ = f"{node_config.node_id}_node"
        react_node_function.__doc__ = f"ReAct agent node: {node_config.node_id}"
        return react_node_function

    # --- Plain LLM node ---
    else:
        def node_function(state: Dict[str, Any]) -> Dict[str, Any]:
            """Plain LLM agent node."""
            print(f"\n[{node_config.node_id.upper()}] Processing...")

            llm = _create_llm(
                node_config.model,
                node_config.temperature,
                node_config.max_tokens,
            )

            user_content = _build_node_input(node_config, state)

            # Build messages for the LLM
            prompt_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ]

            # Invoke LLM
            response = llm.invoke(prompt_messages)
            print(f"[{node_config.node_id.upper()}] Output: {response.content[:80]}...")

            return _build_node_update(node_config, state, response)

        node_function.__name__ = f"{node_config.node_id}_node"
        node_function.__doc__ = f"Agent node: {node_config.node_id}"
        return node_function


# ============================================================================
# GRAPH BUILDER
# ============================================================================

class GraphBuilder:
    """Builds a LangGraph StateGraph from JSON configuration.

    Usage:
        builder = GraphBuilder("examples/state_rewrite_pipeline.json")
        app = builder.build()
        result = app.invoke({"source_text": "Hello", "iteration_count": 0})
    """

    def __init__(
        self,
        config_source: Union[str, GraphConfig],
        artifact_repository: Optional[ArtifactRepository] = None,
        prompt_provider: Optional[PromptProvider] = None,
    ):
        """Initialize builder from a JSON config file path or validated config.

        Args:
            config_source: Path to a JSON file or a validated GraphConfig object.

        Raises:
            FileNotFoundError: If config_path doesn't exist.
            pydantic.ValidationError: If JSON doesn't match schema.
        """
        if isinstance(config_source, GraphConfig):
            self.config = config_source
            self.config_path: Optional[str] = None
        else:
            self.config = load_config(config_source)
            self.config_path = config_source
        self.artifact_repository = artifact_repository
        self.prompt_provider = prompt_provider or PhoenixPromptProvider()
        self.state_class = create_state_class(self.config)
        self.node_functions: Dict[str, Callable] = {}
        self.entry_nodes = self._resolve_entry_nodes()
        self.entry_node = self.entry_nodes[0]

    def _resolve_entry_nodes(self) -> List[str]:
        """Resolve the actual starting nodes for execution."""
        if self.config.entry_point != "START":
            return [self.config.entry_point]

        start_nodes = [edge.to_node for edge in self.config.edges if edge.from_node == "START"]
        if start_nodes:
            return start_nodes

        raise ValueError("No START edge found for graph entry point resolution.")

    def _validate_structure(self) -> None:
        """Validate structural integrity of the graph configuration.

        Checks:
        - All edge source/target references point to defined node IDs
        - At least one entry point (START edge) exists
        - No orphan nodes (every node reachable from START)
        - No duplicate node IDs

        Raises:
            ValueError: If any structural issue is found.
        """
        node_ids = {node.node_id for node in self.config.nodes}

        # Check for duplicate node IDs
        if len(node_ids) != len(self.config.nodes):
            seen = set()
            for node in self.config.nodes:
                if node.node_id in seen:
                    raise ValueError(f"Duplicate node ID: {node.node_id}")
                seen.add(node.node_id)

        # Collect all referenced node IDs in edges
        start_edges = []
        referenced_nodes = set()

        for edge in self.config.edges:
            to_node = edge.to_node
            from_nodes = edge.from_node if isinstance(edge.from_node, list) else [edge.from_node]

            if edge.from_node == "START":
                start_edges.append(to_node)
                referenced_nodes.add(to_node)
            elif to_node == "END":
                referenced_nodes.update(from_nodes)
            else:
                referenced_nodes.update(from_nodes)
                referenced_nodes.add(to_node)

        # Check: entry point resolves correctly
        if self.config.entry_point == "START" and not start_edges:
            raise ValueError("No entry point defined. Add an edge from START to a node.")

        # Check: all referenced nodes exist
        for node_ref in referenced_nodes:
            if node_ref not in node_ids:
                raise ValueError(f"Edge references undefined node: '{node_ref}'. Available: {sorted(node_ids)}")

        # Check: all nodes are reachable from START (no orphans)
        # Simple reachability via edges
        reachable = set()
        frontier = set(self.entry_nodes)
        edge_map: Dict[str, List[str]] = {n.node_id: [] for n in self.config.nodes}

        for edge in self.config.edges:
            from_nodes = edge.from_node if isinstance(edge.from_node, list) else [edge.from_node]
            if edge.to_node != "END":
                for from_node in from_nodes:
                    if from_node != "START":
                        edge_map[from_node].append(edge.to_node)

        while frontier:
            current = frontier.pop()
            if current in reachable:
                continue
            reachable.add(current)
            for next_node in edge_map.get(current, []):
                frontier.add(next_node)

        orphans = node_ids - reachable
        if orphans:
            raise ValueError(f"Orphan nodes unreachable from START: {sorted(orphans)}")

    def validate_structure(self) -> None:
        """Validate graph topology without resolving prompts or constructing nodes."""
        self._validate_structure()

    def _build_nodes(self, workflow: StateGraph) -> None:
        """Add all nodes to the workflow.

        Iterates config.nodes, creates agent callables via create_node_function,
        and registers each with the StateGraph.

        Args:
            workflow: The StateGraph under construction.
        """
        for node_cfg in self.config.nodes:
            node_fn = create_node_function(
                node_cfg,
                self.artifact_repository,
                prompt_provider=self.prompt_provider,
            )
            self.node_functions[node_cfg.node_id] = node_fn
            workflow.add_node(node_cfg.node_id, node_fn)
            tools_str = f" (tools: {', '.join(node_cfg.tools)})" if node_cfg.tools else ""
            print(f"  + Added node: {node_cfg.node_id} (model: {node_cfg.model}{tools_str})")

    def _build_edges(self, workflow: StateGraph) -> None:
        """Add all edges to the workflow.

        Handles four edge types:
        - START -> node: Entry edge
        - node -> END: Terminal edge
        - node -> node: Sequential edge
        - [node, node] -> node: Join edge that waits for all listed sources

        Args:
            workflow: The StateGraph under construction.
        """
        for edge_cfg in self.config.edges:
            from_node = edge_cfg.from_node
            to_node = edge_cfg.to_node
            graph_from = START if from_node == "START" else from_node

            if to_node == "END":
                workflow.add_edge(graph_from, END)
                print(f"  -> Edge: {from_node} -> END")
            else:
                workflow.add_edge(graph_from, to_node)
                print(f"  -> Edge: {from_node} -> {to_node}")

            # Future: handle conditional edges via edge_cfg.condition

    def build(self):
        """Build and return the compiled StateGraph.

        Steps:
        1. Validate structural integrity of the config
        2. Create a StateGraph with the dynamic state class
        3. Add all nodes via _build_nodes()
        4. Add all edges via _build_edges()
        5. Compile and return the graph

        Returns:
            A compiled LangGraph that can be invoked with initial state.

        Raises:
            ValueError: If config has structural issues.
            Exception: If LangGraph compilation fails.
        """
        print(f"\nBuilding graph: {self.config.graph_name}")
        print(f"Version: {self.config.version}")
        if self.config.description:
            print(f"Description: {self.config.description}")
        print("-" * 50)

        # Validate before building
        self._validate_structure()

        # Create workflow with dynamic state
        workflow = StateGraph(self.state_class)

        print(f"  -> Entry point(s): {', '.join(self.entry_nodes)}")

        # Build nodes
        self._build_nodes(workflow)

        # Build edges
        self._build_edges(workflow)
        if not any(edge.from_node == "START" for edge in self.config.edges):
            workflow.add_edge(START, self.entry_node)
            print(f"  -> Edge: START -> {self.entry_node}")

        # Compile
        print("-" * 50)
        print("Compiling graph...")

        return workflow.compile()


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Main entry point for running compiled graphs from the CLI.

    Usage:
        python compiler.py                  # Uses default state rewrite example
        python compiler.py path/to/cfg.json # Uses specified config
    """
    # Default config path
    config_path = "examples/state_rewrite_pipeline.json"

    # Allow override via command line
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    print("=" * 60)
    print("VERTEXFORGE: Dynamic Graph Compiler")
    print("=" * 60)

    # Build the graph from JSON
    try:
        builder = GraphBuilder(config_path)
        app = builder.build()
    except Exception as e:
        print(f"\nError building graph: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Get user input
    user_input = input("\nEnter a topic to analyze (or press Enter for default): ")
    if not user_input:
        user_input = "Artificial Intelligence and its impact on software development"

    print(f"\nInput: {user_input}")
    print("=" * 60)

    # Run the graph
    try:
        initial_state = _build_initial_state(builder.config, user_input)
        result = app.invoke(initial_state)

        # Display final output
        print("\n" + "=" * 60)
        print("FINAL OUTPUT:")
        print("=" * 60)
        print(_extract_final_output(builder.config, result))
        print("\n" + "=" * 60)
        print(f"Nodes visited: {result['iteration_count']}")
        print("=" * 60)

    except Exception as e:
        print(f"\nError running graph: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())


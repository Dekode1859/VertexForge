"""
Compiler: GraphBuilder that ingests JSON schema and constructs LangGraph StateGraph.

This is the "compiler" that proves bidirectional translation:
  JSON config  →  Working LangGraph multi-agent system

Uses create_react_agent for tool-equipped nodes, plain LLM for others.
"""

import json
import operator
import os
import sys
from typing import TypedDict, Annotated, Sequence, Dict, Any, Callable, List, Optional
from types import new_class

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent

from schema import GraphConfig, NodeConfig, EdgeConfig, load_config
from tools import (
    RESEARCH_TOOLS, MATH_TOOLS, FILE_TOOLS, TEXT_TOOLS,
    ALL_TOOLS, web_search, get_current_date, calculate,
    calculate_statistics, read_file, list_directory, write_file,
    count_words, extract_urls,
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
        "List[BaseMessage]": Sequence[BaseMessage],
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

def _resolve_tools(tool_names: List[str]) -> List[Callable]:
    """Resolve tool name strings from config to actual tool callables.

    Supports both individual tool names and group names (e.g., "RESEARCH_TOOLS").

    Args:
        tool_names: List of tool name strings from the node config.

    Returns:
        List of @tool-decorated callables.

    Raises:
        ValueError: If a tool name cannot be resolved.
    """
    resolved = []
    for name in tool_names:
        # Check individual tool registry first
        if name in TOOL_REGISTRY:
            resolved.append(TOOL_REGISTRY[name])
        # Check group registry
        elif name in TOOL_GROUP_REGISTRY:
            resolved.extend(TOOL_GROUP_REGISTRY[name])
        else:
            raise ValueError(
                f"Unknown tool '{name}'. Available: "
                f"{sorted(TOOL_REGISTRY.keys())}, "
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


def _create_llm(model: str, temperature: float = 0.7) -> ChatOllama:
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

    # Add cloud auth if API key is configured
    if OLLAMA_API_KEY:
        kwargs["base_url"] = OLLAMA_BASE_URL
        kwargs["client_kwargs"] = {
            "headers": {"Authorization": f"Bearer {OLLAMA_API_KEY}"}
        }

    return ChatOllama(**kwargs)


def create_node_function(node_config: NodeConfig) -> Callable:
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

    # --- Tool-equipped agent via create_react_agent ---
    if node_config.tools:
        resolved_tools = _resolve_tools(node_config.tools)
        llm = _create_llm(node_config.model, node_config.temperature)

        agent = create_react_agent(
            model=llm,
            tools=resolved_tools,
            name=node_config.node_id,
            prompt=node_config.system_prompt,
        )

        def react_node_function(state: Dict[str, Any]) -> Dict[str, Any]:
            """ReAct agent node — delegates to create_react_agent."""
            print(f"\n[{node_config.node_id.upper()}] Processing (ReAct agent with {len(resolved_tools)} tools)...")

            messages_list = state.get("messages", [])
            if not messages_list:
                user_content = "No input provided"
            else:
                last_msg = messages_list[-1]
                user_content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

            result = agent.invoke({"messages": [HumanMessage(content=user_content)]})
            final_message = result["messages"][-1]

            print(f"[{node_config.node_id.upper()}] Done (ReAct)")

            return {
                "messages": [final_message],
                "current_node": node_config.node_id,
                "iteration_count": state.get("iteration_count", 0) + 1,
            }

        react_node_function.__name__ = f"{node_config.node_id}_node"
        react_node_function.__doc__ = f"ReAct agent node: {node_config.node_id}"
        return react_node_function

    # --- Plain LLM node ---
    else:
        def node_function(state: Dict[str, Any]) -> Dict[str, Any]:
            """Plain LLM agent node."""
            print(f"\n[{node_config.node_id.upper()}] Processing...")

            llm = _create_llm(node_config.model, node_config.temperature)

            # Get input (last message)
            messages_list = state.get("messages", [])
            if not messages_list:
                user_content = "No input provided"
            else:
                last_msg = messages_list[-1]
                user_content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

            # Build messages for the LLM
            prompt_messages = [
                SystemMessage(content=node_config.system_prompt),
                HumanMessage(content=user_content),
            ]

            # Invoke LLM
            response = llm.invoke(prompt_messages)
            print(f"[{node_config.node_id.upper()}] Output: {response.content[:80]}...")

            # Return updated state
            return {
                "messages": [response],
                "current_node": node_config.node_id,
                "iteration_count": state.get("iteration_count", 0) + 1,
            }

        node_function.__name__ = f"{node_config.node_id}_node"
        node_function.__doc__ = f"Agent node: {node_config.node_id}"
        return node_function


# ============================================================================
# GRAPH BUILDER
# ============================================================================

class GraphBuilder:
    """Builds a LangGraph StateGraph from JSON configuration.

    Usage:
        builder = GraphBuilder("config.json")
        app = builder.build()
        result = app.invoke({"messages": [HumanMessage(content="Hello")]})
    """

    def __init__(self, config_path: str):
        """Initialize builder from a JSON config file path.

        Args:
            config_path: Path to a JSON file matching the GraphConfig schema.

        Raises:
            FileNotFoundError: If config_path doesn't exist.
            pydantic.ValidationError: If JSON doesn't match schema.
        """
        self.config = load_config(config_path)
        self.state_class = create_state_class(self.config)
        self.node_functions: Dict[str, Callable] = {}

    def _validate_structure(self) -> None:
        """Validate structural integrity of the graph configuration.

        Checks:
        - All edge source/target references point to defined node IDs
        - Exactly one entry point (START edge) exists
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
            from_node = edge.from_node
            to_node = edge.to_node

            if from_node == "START":
                start_edges.append(to_node)
                referenced_nodes.add(to_node)
            elif to_node == "END":
                referenced_nodes.add(from_node)
            else:
                referenced_nodes.add(from_node)
                referenced_nodes.add(to_node)

        # Check: exactly one START edge
        if not start_edges:
            raise ValueError("No entry point defined. Add an edge from START to a node.")
        if len(start_edges) > 1:
            raise ValueError(f"Multiple entry points defined: {start_edges}. Only one START edge is allowed.")

        # Check: all referenced nodes exist
        for node_ref in referenced_nodes:
            if node_ref not in node_ids:
                raise ValueError(f"Edge references undefined node: '{node_ref}'. Available: {sorted(node_ids)}")

        # Check: all nodes are reachable from START (no orphans)
        # Simple reachability via edges
        reachable = set()
        frontier = {start_edges[0]}
        edge_map: Dict[str, List[str]] = {n.node_id: [] for n in self.config.nodes}

        for edge in self.config.edges:
            if edge.from_node != "START" and edge.to_node != "END":
                edge_map[edge.from_node].append(edge.to_node)

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

    def _build_nodes(self, workflow: StateGraph) -> None:
        """Add all nodes to the workflow.

        Iterates config.nodes, creates agent callables via create_node_function,
        and registers each with the StateGraph.

        Args:
            workflow: The StateGraph under construction.
        """
        for node_cfg in self.config.nodes:
            node_fn = create_node_function(node_cfg)
            self.node_functions[node_cfg.node_id] = node_fn
            workflow.add_node(node_cfg.node_id, node_fn)
            tools_str = f" (tools: {', '.join(node_cfg.tools)})" if node_cfg.tools else ""
            print(f"  + Added node: {node_cfg.node_id} (model: {node_cfg.model}{tools_str})")

    def _build_edges(self, workflow: StateGraph) -> None:
        """Add all edges to the workflow.

        Handles three edge types:
        - START → node: Sets entry point
        - node → END: Terminal edge
        - node → node: Sequential edge

        Args:
            workflow: The StateGraph under construction.
        """
        for edge_cfg in self.config.edges:
            from_node = edge_cfg.from_node
            to_node = edge_cfg.to_node

            if from_node == "START":
                workflow.set_entry_point(to_node)
                print(f"  -> Entry point: {to_node}")
            elif to_node == "END":
                workflow.add_edge(from_node, END)
                print(f"  -> Edge: {from_node} -> END")
            else:
                workflow.add_edge(from_node, to_node)
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

        # Build nodes
        self._build_nodes(workflow)

        # Build edges
        self._build_edges(workflow)

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
        python compiler.py                  # Uses default config.json
        python compiler.py path/to/cfg.json # Uses specified config
    """
    # Default config path
    config_path = "config.json"

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
        result = app.invoke({
            "messages": [HumanMessage(content=user_input)],
            "current_node": "START",
            "iteration_count": 0
        })

        # Display final output
        print("\n" + "=" * 60)
        print("FINAL OUTPUT:")
        print("=" * 60)
        print(result["messages"][-1].content)
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
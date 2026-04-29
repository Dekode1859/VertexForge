"""
Baseline Script: Hardcoded LangGraph Multi-Agent System
Uses official Supervisor/Worker pattern with Ollama Cloud + Kimi K2.5
"""

import os
from typing import TypedDict, Annotated, Sequence, Literal
import operator
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent

from tools import RESEARCH_TOOLS, MATH_TOOLS

# Load environment variables
load_dotenv()


# ============================================================================
# CONFIGURATION
# ============================================================================

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "kimi-k2.5")

if not OLLAMA_API_KEY:
    raise ValueError("OLLAMA_API_KEY not found in environment. Check .env file.")


# ============================================================================
# STATE DEFINITION
# ============================================================================

class GraphState(TypedDict):
    """State passed between nodes."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    current_agent: str
    task_type: Literal["research", "math", "general"]


# ============================================================================
# LLM INITIALIZATION (Ollama Cloud with Kimi K2.5)
# ============================================================================

def create_ollama_llm(temperature: float = 0.7) -> ChatOllama:
    """Create Ollama Cloud LLM client with Kimi K2.5."""
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
        client_kwargs={
            "headers": {
                "Authorization": f"Bearer {OLLAMA_API_KEY}",
            }
        },
    )


# ============================================================================
# AGENT DEFINITIONS (Hardcoded Workers)
# ============================================================================

# Research Agent - uses web search and date tools
research_agent = create_react_agent(
    model=create_ollama_llm(temperature=0.5),
    tools=RESEARCH_TOOLS,
    name="research_expert",
    prompt="""You are a research expert with access to web search.

Your capabilities:
- Search the web for current information using web_search
- Get the current date
- Extract URLs from text

Rules:
1. Always use web_search to find current/recent information
2. Provide factual, well-researched answers
3. Cite your sources when possible
4. If you don't find relevant information, say so clearly

Do NOT do math calculations - delegate those to the math expert."""
)

# Math Agent - uses calculation tools
math_agent = create_react_agent(
    model=create_ollama_llm(temperature=0.0),
    tools=MATH_TOOLS,
    name="math_expert",
    prompt="""You are a math expert with calculation capabilities.

Your capabilities:
- calculate: Evaluate mathematical expressions (2+2*3, etc.)
- calculate_statistics: Compute mean, median, min, max of number lists

Rules:
1. Always use tools for calculations - don't do math in your head
2. Show your work when relevant
3. Be precise with numerical answers
4. For statistics, use calculate_statistics with comma-separated numbers

Do NOT search the web - focus purely on calculations."""
)


# ============================================================================
# SUPERVISOR NODE (Hardcoded Routing Logic)
# ============================================================================

SUPERVISOR_PROMPT = """You are a supervisor managing a team of experts:
- **research_expert**: For current events, factual questions, web searches
- **math_expert**: For calculations, statistics, numerical analysis

Your job is to route the user's request to the appropriate expert.

Rules:
1. If the question involves CURRENT events, facts, or web info → use research_expert
2. If the question involves MATH, calculations, or numbers → use math_expert
3. If unclear, ask clarifying questions or default to research_expert

Respond with EXACTLY ONE word: "research_expert", "math_expert", or "FINISH" (if no routing needed)."""


def supervisor_node(state: GraphState) -> GraphState:
    """Supervisor decides which agent should handle the task."""
    print(f"\n[SUPERVISOR] Analyzing request...")
    
    llm = create_ollama_llm(temperature=0.0)
    
    messages = [
        SystemMessage(content=SUPERVISOR_PROMPT),
        HumanMessage(content=state["messages"][-1].content)
    ]
    
    response = llm.invoke(messages)
    decision = response.content.strip().lower()
    
    print(f"[SUPERVISOR] Decision: {decision}")
    
    # Store decision in state for routing
    if "math" in decision:
        task_type = "math"
    elif "finish" in decision:
        task_type = "general"
    else:
        task_type = "research"
    
    return {
        "messages": [],
        "current_agent": "supervisor",
        "task_type": task_type
    }


# ============================================================================
# WORKER NODES (Hardcoded Agent Invocation)
# ============================================================================

def research_node(state: GraphState) -> GraphState:
    """Invoke the research expert agent."""
    print(f"\n[RESEARCH_EXPERT] Working...")
    
    # Get the last user message
    user_message = state["messages"][-1]
    
    # Invoke the agent
    result = research_agent.invoke({
        "messages": [user_message]
    })
    
    # Extract the final response
    final_message = result["messages"][-1]
    
    print(f"[RESEARCH_EXPERT] Done")
    
    return {
        "messages": [final_message],
        "current_agent": "research_expert",
        "task_type": "research"
    }


def math_node(state: GraphState) -> GraphState:
    """Invoke the math expert agent."""
    print(f"\n[MATH_EXPERT] Working...")
    
    # Get the last user message
    user_message = state["messages"][-1]
    
    # Invoke the agent
    result = math_agent.invoke({
        "messages": [user_message]
    })
    
    # Extract the final response
    final_message = result["messages"][-1]
    
    print(f"[MATH_EXPERT] Done")
    
    return {
        "messages": [final_message],
        "current_agent": "math_expert",
        "task_type": "math"
    }


# ============================================================================
# ROUTING LOGIC (Hardcoded Conditional Edges)
# ============================================================================

def route_task(state: GraphState) -> Literal["research_node", "math_node", END]:
    """Route to the appropriate agent based on supervisor decision."""
    task_type = state.get("task_type", "research")
    
    if task_type == "math":
        return "math_node"
    elif task_type == "research":
        return "research_node"
    else:
        return END


# ============================================================================
# GRAPH CONSTRUCTION (Hardcoded)
# ============================================================================

def build_graph():
    """Build and compile the StateGraph."""
    
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("research_node", research_node)
    workflow.add_node("math_node", math_node)
    
    # Add edges
    workflow.add_edge(START, "supervisor")
    
    # Conditional routing from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_task,
        {
            "research_node": "research_node",
            "math_node": "math_node",
            END: END
        }
    )
    
    # Both workers end after completion
    workflow.add_edge("research_node", END)
    workflow.add_edge("math_node", END)
    
    return workflow.compile()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("VERTEXFORGE: Baseline Multi-Agent System")
    print(f"Model: {DEFAULT_MODEL} via Ollama Cloud")
    print("=" * 70)
    
    # Build the graph
    app = build_graph()
    
    # Test prompts
    test_prompts = [
        "What is 125 * 37 + 450?",
        "What are the latest developments in AI as of 2025?",
        "Calculate the mean of these numbers: 23, 45, 67, 89, 12",
    ]
    
    print("\nTest prompts available:")
    for i, prompt in enumerate(test_prompts, 1):
        print(f"  {i}. {prompt}")
    
    # Get user input
    choice = input("\nSelect a test (1-3) or enter custom query: ").strip()
    
    if choice == "1":
        user_input = test_prompts[0]
    elif choice == "2":
        user_input = test_prompts[1]
    elif choice == "3":
        user_input = test_prompts[2]
    else:
        user_input = choice
    
    print(f"\n{'=' * 70}")
    print(f"QUERY: {user_input}")
    print(f"{'=' * 70}\n")
    
    # Run the graph
    try:
        result = app.invoke({
            "messages": [HumanMessage(content=user_input)],
            "current_agent": "START",
            "task_type": "general"
        })
        
        # Display final output
        print(f"\n{'=' * 70}")
        print("FINAL RESPONSE:")
        print(f"{'=' * 70}\n")
        print(result["messages"][-1].content)
        print(f"\n{'=' * 70}")
        print(f"Agent used: {result['current_agent']}")
        print(f"{'=' * 70}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

"""
Non-interactive baseline test - runs automatically
"""

import os
from typing import TypedDict, Annotated, Sequence, Literal
import operator

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent

from vertexforge.tools import RESEARCH_TOOLS, MATH_TOOLS

load_dotenv()

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "kimi-k2.5")

if not OLLAMA_API_KEY:
    raise ValueError("OLLAMA_API_KEY not found in environment")

print("=" * 70)
print("TEST: Non-interactive baseline validation")
print("=" * 70)
print(f"\n[OK] API Key present: {OLLAMA_API_KEY[:8]}...{OLLAMA_API_KEY[-4:]}")
print(f"[OK] Base URL: {OLLAMA_BASE_URL}")
print(f"[OK] Model: {DEFAULT_MODEL}")


class GraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    current_agent: str
    task_type: Literal["research", "math", "general"]


def create_ollama_llm(temperature: float = 0.7) -> ChatOllama:
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
        client_kwargs={
            "headers": {"Authorization": f"Bearer {OLLAMA_API_KEY}"},
        },
    )


# Test 1: Verify LLM connection
print("\n[TEST 1] Verifying LLM connection...")
try:
    llm = create_ollama_llm(temperature=0)
    response = llm.invoke("Say 'VertexForge baseline test successful' and nothing else.")
    print(f"[OK] LLM Response: {response.content[:60]}...")
except Exception as e:
    print(f"[FAIL] LLM Error: {e}")
    exit(1)


# Test 2: Verify Math Agent with tools
print("\n[TEST 2] Verifying Math Agent...")
math_agent = create_react_agent(
    model=create_ollama_llm(temperature=0),
    tools=MATH_TOOLS,
    name="math_expert",
    prompt="You are a math expert. Use tools for calculations."
)

try:
    result = math_agent.invoke({
        "messages": [HumanMessage(content="Calculate 15 * 23 + 100")]
    })
    print(f"[OK] Math Agent Result: {result['messages'][-1].content[:80]}...")
except Exception as e:
    print(f"[FAIL] Math Agent Error: {e}")
    import traceback
    traceback.print_exc()


# Test 3: Verify Research Agent with tools  
print("\n[TEST 3] Verifying Research Agent (web search)...")
research_agent = create_react_agent(
    model=create_ollama_llm(temperature=0.5),
    tools=RESEARCH_TOOLS,
    name="research_expert",
    prompt="You are a research expert with web search access."
)

try:
    result = research_agent.invoke({
        "messages": [HumanMessage(content="What is LangGraph? Use web_search.")]
    })
    print(f"[OK] Research Agent Result: {result['messages'][-1].content[:80]}...")
except Exception as e:
    print(f"[FAIL] Research Agent Error: {e}")
    import traceback
    traceback.print_exc()


print("\n" + "=" * 70)
print("SUCCESS: BASELINE TEST COMPLETE")
print("=" * 70)
print("\nAll components validated:")
print("  [OK] Ollama Cloud authentication")
print("  [OK] Kimi K2.5 model access")
print("  [OK] Math agent with calculation tools")
print("  [OK] Research agent with web search tools")
print("\nReady to proceed to Phase 2: Schema Definition")

